"""契约门禁命令行：独立基线管理 + 破坏性变更比对（**产品侧自持**）。

用法::

    uv run python -m ops.contract_gate check                 # 基线 ↔ 实时公开契约，破坏性变更即失败
    uv run python -m ops.contract_gate check --service org   # 指定服务
    uv run python -m ops.contract_gate check --engine oasdiff            # 强制 oasdiff（缺 docker 即失败）
    uv run python -m ops.contract_gate check --engine structural         # 强制结构化判定
    uv run python -m ops.contract_gate baseline-update --all # 人工更新基线（走评审合入）

口径（任务 01_03 详细设计 §9）：

- 基线 `deploy/contracts/baseline/<service>.json` 为**已放行的兼容契约**（入 Git，仅经评审更新）；
- 当前值取**实时公开契约**（`ops.contract_snapshot.build_openapi` 内存构建），不依赖已提交快照；
- **判定引擎两选一**（`--engine` 缺省 `auto`）：
  - `oasdiff`：`tufin/oasdiff:v1.32.1` 的 `breaking`（「只加不删」），需 docker（CI 内可用）；
  - `structural`：**内置结构化「只加不删」判定**（路径 · 操作 · 响应状态码 · 组件 schema 属性均不得删除；
    新增一律放行），供无 docker 的本机 / 精简 runner 使用；判定严于 oasdiff 的加性放行面等价。
  `auto` 在 docker 可用时用 oasdiff、否则回落 structural（并显式打印所选引擎，不静默降级）。
- 破坏性变更升级大版本（`/api/v2` 并行）后更新基线，不得原地破坏。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from bms_core.core.concurrent import ConcurrentStableDict, ConcurrentStableList
from bms_core.services.service_contract import BASELINE_DIR, contract_file_name, render_contract_json

from ops.contract_snapshot import REPO_ROOT, build_openapi, enabled_local_records, snapshot_path

OASDIFF_IMAGE = "tufin/oasdiff:v1.32.1"
"""oasdiff 固定 tag 镜像（与 bms 侧同版本，便于口径对齐）。"""

OASDIFF_COMMAND = "docker"
"""oasdiff 调用命令（经 docker 运行固定 tag 镜像；单测可注入桩替换）。"""

ENGINE_AUTO = "auto"
ENGINE_OASDIFF = "oasdiff"
ENGINE_STRUCTURAL = "structural"
ENGINES: tuple[str, ...] = (ENGINE_AUTO, ENGINE_OASDIFF, ENGINE_STRUCTURAL)
"""判定引擎取值（`auto` 按 docker 可用性选择）。"""

_HTTP_METHODS: tuple[str, ...] = ("get", "post", "put", "delete", "patch", "head", "options")
"""公开契约中计为「操作」的 HTTP 方法（小写，与 OpenAPI 一致）。"""

Runner = Callable[[ConcurrentStableList[str]], "subprocess.CompletedProcess[str]"]
"""子进程执行器类型（默认 docker；单测注入桩，不真联）。"""

DiffRunner = Callable[[Path, Path, str], tuple[int, str, str]]
"""单次 oasdiff 比对执行器类型：`(基线, 当前, 镜像) -> (返回码, stdout, stderr)`。"""


@dataclass(frozen=True)
class BreakingResult:
    """单服务契约比对结果。"""

    service: str
    count: int
    raw: str
    ok: bool
    engine: str = ENGINE_STRUCTURAL
    error: str = ""


def baseline_dir(root: Path) -> Path:
    """契约基线目录。

    Args:
        root: 仓库根。

    Returns:
        Path: `<root>/deploy/contracts/baseline`。
    """
    return root / BASELINE_DIR


def baseline_path(root: Path, service_key: str) -> Path:
    """单服务契约基线文件路径。

    Args:
        root: 仓库根。
        service_key: 服务标识。

    Returns:
        Path: `<root>/deploy/contracts/baseline/<service_key>.json`。
    """
    return baseline_dir(root) / contract_file_name(service_key)


def structural_breaking(baseline: Mapping[str, object], current: Mapping[str, object]) -> ConcurrentStableList[str]:
    """结构化「只加不删」判定：列出基线中被删除的路径 / 操作 / 响应码 / schema 属性。

    新增一律放行（加性变更不构成破坏）；判定面覆盖 oasdiff `breaking` 的主要破坏类
    （删端点 / 删方法 / 删响应码 / 删 schema / 删 schema 属性）。

    Args:
        baseline: 基线契约映射。
        current: 当前契约映射。

    Returns:
        ConcurrentStableList[str]: 破坏性变更清单；空表示兼容。
    """
    problems: ConcurrentStableList[str] = ConcurrentStableList()
    base_paths = _mapping(baseline.get("paths"))
    current_paths = _mapping(current.get("paths"))
    for path, base_item in base_paths.items():
        current_item = _mapping(current_paths.get(path)) if path in current_paths else ConcurrentStableDict()
        if not current_item:
            problems.add(f"删除路径：{path}")
            continue
        for method, base_operation in _mapping(base_item).items():
            if method.lower() not in _HTTP_METHODS:
                continue
            operation = _mapping(current_item.get(method))
            if not operation:
                problems.add(f"删除操作：{method.upper()} {path}")
                continue
            problems.update(_removed_responses(path, method, base_operation, operation))
    problems.update(_removed_schemas(baseline, current))
    return problems


def _removed_responses(
    path: str,
    method: str,
    base_operation: object,
    operation: Mapping[str, object],
) -> ConcurrentStableList[str]:
    """列出单个操作中被删除的响应状态码。

    Args:
        path: 路径。
        method: HTTP 方法。
        base_operation: 基线操作对象。
        operation: 当前操作对象。

    Returns:
        ConcurrentStableList[str]: 破坏性变更清单。
    """
    problems: ConcurrentStableList[str] = ConcurrentStableList()
    base_responses = _mapping(_mapping(base_operation).get("responses"))
    current_responses = _mapping(operation.get("responses"))
    for status in base_responses:
        if status not in current_responses:
            problems.add(f"删除响应码：{method.upper()} {path} [{status}]")
    return problems


def _removed_schemas(baseline: Mapping[str, object], current: Mapping[str, object]) -> ConcurrentStableList[str]:
    """列出被删除的组件 schema 及其被删除的属性。

    Args:
        baseline: 基线契约映射。
        current: 当前契约映射。

    Returns:
        ConcurrentStableList[str]: 破坏性变更清单。
    """
    problems: ConcurrentStableList[str] = ConcurrentStableList()
    base_schemas = _schemas(baseline)
    current_schemas = _schemas(current)
    for name, base_schema in base_schemas.items():
        current_schema = _mapping(current_schemas.get(name)) if name in current_schemas else ConcurrentStableDict()
        if not current_schema:
            problems.add(f"删除组件 schema：{name}")
            continue
        base_properties = _mapping(_mapping(base_schema).get("properties"))
        current_properties = _mapping(current_schema.get("properties"))
        for prop in base_properties:
            if prop not in current_properties:
                problems.add(f"删除 schema 属性：{name}.{prop}")
    return problems


def _schemas(openapi: Mapping[str, object]) -> ConcurrentStableDict[str, object]:
    """取契约 `components.schemas`。

    Args:
        openapi: 契约映射。

    Returns:
        ConcurrentStableDict[str, object]: schema 映射。
    """
    return _mapping(_mapping(openapi.get("components")).get("schemas"))


def _mapping(value: object) -> ConcurrentStableDict[str, object]:
    """把值规整为字符串键插入序映射（非映射返回空映射）。

    Args:
        value: 待规整值。

    Returns:
        ConcurrentStableDict[str, object]: 规整后的映射。
    """
    result: ConcurrentStableDict[str, object] = ConcurrentStableDict()
    if isinstance(value, Mapping):
        for key, item in cast("Mapping[object, object]", value).items():
            result.set(str(key), item)
    return result


def count_breaking(raw: str) -> int:
    """从 oasdiff 输出解析破坏性变更条目数。

    Args:
        raw: oasdiff `--format json` 的标准输出。

    Returns:
        int: 破坏性变更条目数（空输出 0；解析失败按非空行计）。
    """
    text = raw.strip()
    if not text:
        return 0
    try:
        decoded: object = json.loads(text)
    except json.JSONDecodeError:
        return sum(1 for line in text.splitlines() if line.strip())
    if isinstance(decoded, list):
        return len(cast("list[object]", decoded))
    if isinstance(decoded, dict):
        nested = cast("dict[str, object]", decoded).get("breaking")
        if isinstance(nested, list):
            return len(cast("list[object]", nested))
    return 1


def docker_available() -> bool:
    """docker 可执行文件是否在 PATH 中。

    Returns:
        bool: 可用 True。
    """
    return shutil.which(OASDIFF_COMMAND) is not None


def _run_command(command: ConcurrentStableList[str]) -> subprocess.CompletedProcess[str]:
    """默认子进程执行器（docker）。

    Args:
        command: 完整命令行。

    Returns:
        subprocess.CompletedProcess[str]: 执行结果（不抛异常，由调用方判返回码）。
    """
    return subprocess.run(list(command), capture_output=True, text=True, check=False)


def oasdiff_args() -> ConcurrentStableList[str]:
    """oasdiff `breaking` 子命令参数（容器内路径 `/base.json` / `/cur.json`）。

    Returns:
        ConcurrentStableList[str]: 参数列表。
    """
    return ConcurrentStableList(["breaking", "--fail-on", "ERR", "--format", "json", "/base.json", "/cur.json"])


def docker_diff(
    baseline: Path,
    current: Path,
    image: str,
    *,
    run: Runner = _run_command,
) -> tuple[int, str, str]:
    """用 oasdiff 容器比对两份契约（`docker create` + `docker cp` + `docker start -a`）。

    不使用 bind mount：契约门禁 job 运行在容器内时其路径在宿主 daemon 上不可见。

    Args:
        baseline: 基线契约文件。
        current: 当前契约文件。
        image: oasdiff 镜像（含 tag）。
        run: 子进程执行器（单测注入桩）。

    Returns:
        tuple[int, str, str]: 返回码 / 标准输出 / 标准错误。
    """
    name = f"mdm-contract-gate-{os.getpid()}-{baseline.stem}"
    run(ConcurrentStableList([OASDIFF_COMMAND, "rm", "-f", name]))
    created = run(ConcurrentStableList([OASDIFF_COMMAND, "create", "--name", name, image, *oasdiff_args()]))
    if created.returncode != 0:
        return created.returncode, created.stdout or "", created.stderr or ""
    try:
        for source, target in ((baseline, "/base.json"), (current, "/cur.json")):
            copied = run(ConcurrentStableList([OASDIFF_COMMAND, "cp", str(source), f"{name}:{target}"]))
            if copied.returncode != 0:
                return copied.returncode, copied.stdout or "", copied.stderr or ""
        started = run(ConcurrentStableList([OASDIFF_COMMAND, "start", "-a", name]))
        return started.returncode, started.stdout or "", started.stderr or ""
    finally:
        run(ConcurrentStableList([OASDIFF_COMMAND, "rm", "-f", name]))


def compare_service(
    root: Path,
    service_key: str,
    *,
    engine: str = ENGINE_AUTO,
    image: str = OASDIFF_IMAGE,
    diff: DiffRunner = docker_diff,
) -> BreakingResult:
    """比对单服务基线 ↔ 实时公开契约。

    Args:
        root: 仓库根。
        service_key: 服务标识。
        engine: 判定引擎（`auto` / `oasdiff` / `structural`）。
        image: oasdiff 镜像。
        diff: oasdiff 比对执行器（单测注入桩）。

    Returns:
        BreakingResult: 比对结果（`ok=False` 表示工具 / 构建 / 基线失败，非破坏性变更）。
    """
    baseline = baseline_path(root, service_key)
    if not baseline.is_file():
        return BreakingResult(service_key, 0, "", False, engine, error=f"基线缺件：{baseline}")
    try:
        openapi = build_openapi(service_key)
    except RuntimeError as exc:
        return BreakingResult(service_key, 0, "", False, engine, error=f"契约构建失败：{exc}")
    selected = _select_engine(engine)
    if selected == ENGINE_OASDIFF:
        return _compare_with_oasdiff(service_key, baseline, openapi, image=image, diff=diff)
    return _compare_structurally(service_key, baseline, openapi)


def _select_engine(engine: str) -> str:
    """解析实际使用的判定引擎（`auto` 按 docker 可用性选择）。

    Args:
        engine: 请求的引擎。

    Returns:
        str: 实际引擎（`oasdiff` / `structural`）。
    """
    if engine == ENGINE_STRUCTURAL:
        return ENGINE_STRUCTURAL
    if engine == ENGINE_OASDIFF:
        return ENGINE_OASDIFF
    return ENGINE_OASDIFF if docker_available() else ENGINE_STRUCTURAL


def _compare_with_oasdiff(
    service_key: str,
    baseline: Path,
    openapi: ConcurrentStableDict[str, Any],
    *,
    image: str,
    diff: DiffRunner,
) -> BreakingResult:
    """用 oasdiff 容器比对（需 docker）。

    Args:
        service_key: 服务标识。
        baseline: 基线文件。
        openapi: 实时公开契约。
        image: oasdiff 镜像。
        diff: 比对执行器。

    Returns:
        BreakingResult: 比对结果。
    """
    with tempfile.TemporaryDirectory(prefix="mdm-contract-") as tmp:
        current = Path(tmp) / contract_file_name(service_key)
        current.write_text(render_contract_json(openapi), encoding="utf-8")
        try:
            returncode, stdout, stderr = diff(baseline, current, image)
        except OSError as exc:
            return BreakingResult(
                service_key,
                0,
                "",
                False,
                ENGINE_OASDIFF,
                error=f"oasdiff 调用失败：{exc}（确认已预拉 {image}）",
            )
    raw = f"{stdout or ''}{stderr or ''}".strip()
    if returncode not in (0, 1):
        return BreakingResult(
            service_key,
            0,
            raw,
            False,
            ENGINE_OASDIFF,
            error=f"oasdiff 返回码 {returncode}（确认已预拉 {image}）",
        )
    return BreakingResult(service_key, count_breaking(stdout or ""), raw, True, ENGINE_OASDIFF)


def _compare_structurally(
    service_key: str,
    baseline: Path,
    openapi: ConcurrentStableDict[str, Any],
) -> BreakingResult:
    """用内置结构化判定比对（无需 docker）。

    Args:
        service_key: 服务标识。
        baseline: 基线文件。
        openapi: 实时公开契约。

    Returns:
        BreakingResult: 比对结果。
    """
    try:
        base_doc = json.loads(baseline.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return BreakingResult(service_key, 0, "", False, ENGINE_STRUCTURAL, error=f"基线不可解析：{exc}")
    if not isinstance(base_doc, dict):
        return BreakingResult(service_key, 0, "", False, ENGINE_STRUCTURAL, error="基线非对象")
    problems = structural_breaking(cast("dict[str, object]", base_doc), openapi)
    raw = "\n".join(problems)
    return BreakingResult(service_key, len(problems), raw, True, ENGINE_STRUCTURAL)


def check(
    root: Path,
    *,
    services: ConcurrentStableList[str] | None = None,
    engine: str = ENGINE_AUTO,
    image: str = OASDIFF_IMAGE,
    diff: DiffRunner = docker_diff,
) -> int:
    """逐服务比对基线 ↔ 实时公开契约，破坏性变更即失败。

    Args:
        root: 仓库根。
        services: 目标服务（缺省取本产品全部启用服务）。
        engine: 判定引擎。
        image: oasdiff 镜像。
        diff: oasdiff 比对执行器。

    Returns:
        int: 退出码（0 全部兼容；1 存在破坏性变更 / 缺件 / 工具失败）。
    """
    targets = services if services is not None else ConcurrentStableList(_local_service_keys())
    problems: ConcurrentStableList[BreakingResult] = ConcurrentStableList()
    for service_key in targets:
        result = compare_service(root, service_key, engine=engine, image=image, diff=diff)
        if not result.ok:
            print(f"[contract_gate] 服务 {service_key}：{result.error}")
            problems.add(result)
            continue
        if result.count:
            problems.add(result)
            print(
                f"[contract_gate] 服务 {service_key}：检测到 {result.count} 项破坏性变更"
                f"（基线 → 当前；引擎 {result.engine}）"
            )
            for line in result.raw.splitlines():
                if line.strip():
                    print(f"    {line}")
            print(
                f"    若为预期破坏性变更：uv run python -m ops.contract_gate baseline-update --service {service_key}"
                "（更新基线后提交并走评审合入；确需破坏时应升大版本 /api/v2 并行）"
            )
    if problems:
        print(f"[contract_gate] 不通过：{len(problems)} 个服务存在破坏性变更或异常")
        return 1
    print(f"[contract_gate] 通过：{len(targets)} 个在运服务公开契约与基线兼容（引擎 {_select_engine(engine)}）")
    return 0


def baseline_update(root: Path, *, services: ConcurrentStableList[str]) -> int:
    """把当前快照复制为基线（预期破坏性变更时人工执行；不自动提交）。

    Args:
        root: 仓库根。
        services: 目标服务集合。

    Returns:
        int: 退出码（0 全部成功；1 有缺件）。
    """
    target_dir = baseline_dir(root)
    target_dir.mkdir(parents=True, exist_ok=True)
    failures = 0
    for service_key in services:
        source = snapshot_path(root, service_key)
        if not source.is_file():
            print(f"[contract_gate] 当前快照缺件：{source}", file=sys.stderr)
            failures += 1
            continue
        target = baseline_path(root, service_key)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"[contract_gate] 已更新基线：{target}")
    return 1 if failures else 0


def _local_service_keys() -> tuple[str, ...]:
    """本产品启用的服务标识（快照遍历口径）。

    Returns:
        tuple[str, ...]: 服务标识元组。
    """
    return tuple(cast("str", record.service_key) for record in enabled_local_records())


def _select_services(service: str | None, all_services: bool) -> ConcurrentStableList[str]:
    """解析目标服务集合。

    Args:
        service: 单个服务标识（可空）。
        all_services: 是否全部服务。

    Returns:
        ConcurrentStableList[str]: 目标服务列表。

    Raises:
        SystemExit: 既未指定服务也未指定 `--all` 时。
    """
    if all_services:
        return ConcurrentStableList(_local_service_keys())
    if service:
        return ConcurrentStableList([service])
    raise SystemExit("请指定 --service <服务> 或 --all")


def main(argv: ConcurrentStableList[str] | None = None) -> int:
    """命令行入口。

    Args:
        argv: 参数列表（缺省取 `sys.argv[1:]`）。

    Returns:
        int: 退出码。
    """
    parser = argparse.ArgumentParser(description="契约门禁：基线管理 / 破坏性变更比对（产品侧自持）")
    parser.add_argument("command", choices=("check", "baseline-update"))
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="仓库根（缺省自动定位）")
    parser.add_argument("--service", help="单个服务标识（check / baseline-update）")
    parser.add_argument("--all", dest="all_services", action="store_true", help="全部在运服务（baseline-update）")
    parser.add_argument("--engine", choices=ENGINES, default=ENGINE_AUTO, help="判定引擎（缺省 auto）")
    parser.add_argument("--image", default=OASDIFF_IMAGE, help="oasdiff 镜像（缺省固定 tag）")
    args = parser.parse_args(argv)
    if args.command == "check":
        services = ConcurrentStableList([args.service]) if args.service else None
        return check(args.root, services=services, engine=args.engine, image=args.image)
    return baseline_update(args.root, services=_select_services(args.service, args.all_services))


if __name__ == "__main__":
    raise SystemExit(main())
