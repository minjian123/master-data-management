"""契约门禁用例（Kiwi 2256）：基线管理 / 结构化「只加不删」判定 / oasdiff 调用链（注入桩，不真联）。

覆盖口径：基线缺件与不可解析、破坏性变更四类（删路径 / 删操作 / 删响应码 / 删 schema 与属性）、
加性变更放行、CLI 参数校验、docker 调用编排（create / cp / start / rm）。
"""

import json
import runpy
import subprocess
import sys
from pathlib import Path

import pytest
from bms_core.core.concurrent import ConcurrentStableDict, ConcurrentStableList

from ops import contract_gate
from ops.contract_gate import (
    ENGINE_OASDIFF,
    ENGINE_STRUCTURAL,
    BreakingResult,
    baseline_path,
    baseline_update,
    check,
    compare_service,
    count_breaking,
    docker_diff,
    main,
    oasdiff_args,
    structural_breaking,
)
from ops.contract_snapshot import contracts_dir, snapshot_path


def _doc(*, paths: object, schemas: object | None = None) -> ConcurrentStableDict[str, object]:
    """构造最小契约文档。

    Args:
        paths: `paths` 段。
        schemas: `components.schemas` 段；None 取空。

    Returns:
        ConcurrentStableDict[str, object]: 契约文档。
    """
    return ConcurrentStableDict(
        {
            "info": ConcurrentStableDict({"version": "0.1.0"}),
            "paths": paths,
            "components": ConcurrentStableDict({"schemas": schemas if schemas is not None else ConcurrentStableDict()}),
        }
    )


def test_structural_breaking_detects_removals_and_allows_additions() -> None:
    """结构化判定：删路径 / 操作 / 响应码 / schema / 属性均判破坏；新增一律放行。"""
    baseline = _doc(
        paths=ConcurrentStableDict(
            {
                "/a": ConcurrentStableDict(
                    {"get": ConcurrentStableDict({"responses": ConcurrentStableDict({"200": {}, "404": {}})})}
                ),
                "/b": ConcurrentStableDict({"get": ConcurrentStableDict({"responses": ConcurrentStableDict()})}),
            }
        ),
        schemas=ConcurrentStableDict(
            {"OrgUser": ConcurrentStableDict({"properties": ConcurrentStableDict({"id": {}, "phone": {}})})}
        ),
    )
    unchanged = _doc(
        paths=ConcurrentStableDict(
            {
                "/a": ConcurrentStableDict(
                    {"get": ConcurrentStableDict({"responses": ConcurrentStableDict({"200": {}, "404": {}})})}
                ),
                "/b": ConcurrentStableDict({"get": ConcurrentStableDict({"responses": ConcurrentStableDict()})}),
                "/c": ConcurrentStableDict({"get": ConcurrentStableDict({"responses": ConcurrentStableDict()})}),
            }
        ),
        schemas=ConcurrentStableDict(
            {
                "OrgUser": ConcurrentStableDict({"properties": ConcurrentStableDict({"id": {}, "phone": {}, "x": {}})}),
                "OrgPost": ConcurrentStableDict({"properties": ConcurrentStableDict({})}),
            }
        ),
    )
    assert list(structural_breaking(baseline, unchanged)) == []

    broken = _doc(
        paths=ConcurrentStableDict(
            {
                "/a": ConcurrentStableDict(
                    {"get": ConcurrentStableDict({"responses": ConcurrentStableDict({"200": {}})})}
                )
            }
        ),
        schemas=ConcurrentStableDict(
            {"OrgUser": ConcurrentStableDict({"properties": ConcurrentStableDict({"id": {}})})}
        ),
    )
    problems = list(structural_breaking(baseline, broken))
    assert any("删除路径：/b" in item for item in problems)
    assert any("删除响应码：GET /a [404]" in item for item in problems)
    assert any("删除 schema 属性：OrgUser.phone" in item for item in problems)
    assert len(problems) == 3


def test_count_breaking_parses_oasdiff_output() -> None:
    """oasdiff 输出解析：空 / JSON 数组 / `breaking` 键 / 非 JSON 文本。"""
    assert count_breaking("") == 0
    assert count_breaking("   ") == 0
    assert count_breaking(json.dumps([{}, {}])) == 2
    assert count_breaking(json.dumps({"breaking": [{}]})) == 1
    assert count_breaking(json.dumps({"other": []})) == 1
    assert count_breaking("line one\nline two") == 2


def test_compare_service_reports_missing_baseline_and_unparsable(tmp_path: Path) -> None:
    """基线缺件 / 不可解析 → `ok=False`（工具异常，不算破坏性变更）。"""
    missing = compare_service(tmp_path, "org", engine=ENGINE_STRUCTURAL)
    assert missing.ok is False and "基线缺件" in missing.error

    broken_dir = contract_gate.baseline_dir(tmp_path)
    broken_dir.mkdir(parents=True, exist_ok=True)
    baseline_path(tmp_path, "org").write_text("{不合法", encoding="utf-8")
    unparsable = compare_service(tmp_path, "org", engine=ENGINE_STRUCTURAL)
    assert unparsable.ok is False and "基线不可解析" in unparsable.error


def test_compare_service_detects_tampered_baseline(tmp_path: Path) -> None:
    """篡改基线（加一条当前不存在的路径）→ 结构化判定报破坏性变更。"""
    target = baseline_path(tmp_path, "org")
    target.parent.mkdir(parents=True, exist_ok=True)
    current = json.loads(contract_gate.snapshot_path(contract_gate.REPO_ROOT, "org").read_text(encoding="utf-8"))
    current["paths"]["/api/v1/org/retired"] = current["paths"]["/api/v1/org/resolve-names"]
    target.write_text(json.dumps(current, ensure_ascii=False), encoding="utf-8")

    result = compare_service(tmp_path, "org", engine=ENGINE_STRUCTURAL)
    assert result.ok is True and result.count == 1
    assert "/api/v1/org/retired" in result.raw


def test_repo_baseline_is_compatible() -> None:
    """仓库当前基线 ↔ 实时公开契约兼容（与 CI 门禁同口径）。"""
    assert compare_service(contract_gate.REPO_ROOT, "org", engine=ENGINE_STRUCTURAL).count == 0
    assert check(contract_gate.REPO_ROOT, engine=ENGINE_STRUCTURAL) == 0


def test_baseline_update_copies_snapshot_and_reports_missing(tmp_path: Path) -> None:
    """基线更新：由当前快照复制；快照缺件即失败返回 1。"""
    assert baseline_update(tmp_path, services=ConcurrentStableList(["org"])) == 1

    contracts_dir(tmp_path).mkdir(parents=True, exist_ok=True)
    snapshot_path(tmp_path, "org").write_text('{"paths": {}}', encoding="utf-8")
    assert baseline_update(tmp_path, services=ConcurrentStableList(["org"])) == 0
    assert baseline_path(tmp_path, "org").read_text(encoding="utf-8") == '{"paths": {}}'


def test_main_requires_explicit_baseline_target() -> None:
    """CLI：`baseline-update` 未给 `--service` / `--all` 即显式拒绝。"""
    with pytest.raises(SystemExit):
        main(ConcurrentStableList(["baseline-update"]))


def test_main_check_structural_engine_passes() -> None:
    """CLI：`check --engine structural` 对当前仓库返回 0（无破坏性变更）。"""
    assert main(ConcurrentStableList(["check", "--engine", ENGINE_STRUCTURAL])) == 0


def test_oasdiff_args_and_docker_orchestration() -> None:
    """oasdiff 容器编排：`create` → `cp` 两份契约 → `start -a` → `rm -f`（含失败短路）。"""
    assert list(oasdiff_args())[:2] == ["breaking", "--fail-on"]
    assert oasdiff_args()[-2:] == ["/base.json", "/cur.json"]

    calls: ConcurrentStableList[ConcurrentStableList[str]] = ConcurrentStableList()

    def _runner(command: ConcurrentStableList[str]) -> subprocess.CompletedProcess[str]:
        calls.add(command)
        return subprocess.CompletedProcess(list(command), 0, "", "")

    code, out, err = docker_diff(Path("/tmp/base.json"), Path("/tmp/cur.json"), "img:1", run=_runner)
    assert (code, out, err) == (0, "", "")
    verbs = [command[1] for command in calls]
    assert verbs == ["rm", "create", "cp", "cp", "start", "rm"]
    assert calls[1][-len(oasdiff_args()) - 1] == "img:1"
    assert calls[1][-len(oasdiff_args()) :] == list(oasdiff_args())

    failing: ConcurrentStableList[ConcurrentStableList[str]] = ConcurrentStableList()

    def _failing(command: ConcurrentStableList[str]) -> subprocess.CompletedProcess[str]:
        failing.add(command)
        return subprocess.CompletedProcess(list(command), 125, "", "docker daemon down")

    code, out, err = docker_diff(Path("/tmp/base.json"), Path("/tmp/cur.json"), "img:1", run=_failing)
    assert code == 125 and "daemon down" in err
    assert [command[1] for command in failing] == ["rm", "create"]


def test_compare_service_oasdiff_reports_tool_failure(tmp_path: Path) -> None:
    """oasdiff 引擎：返回码非 0/1（工具异常）→ `ok=False`；破坏条目数由 stdout 解析。"""
    target = baseline_path(tmp_path, "org")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('{"paths": {}}', encoding="utf-8")

    def _broken_tool(baseline: Path, current: Path, image: str) -> tuple[int, str, str]:
        del baseline, current, image
        return 125, "", "cannot connect to the Docker daemon"

    failed = compare_service(
        tmp_path,
        "org",
        engine=ENGINE_OASDIFF,
        diff=_broken_tool,
    )
    assert failed.ok is False and "oasdiff 返回码 125" in failed.error

    def _breaking_tool(baseline: Path, current: Path, image: str) -> tuple[int, str, str]:
        del baseline, current, image
        return 1, json.dumps([{"id": "deleted-path"}]), ""

    detected = compare_service(tmp_path, "org", engine=ENGINE_OASDIFF, diff=_breaking_tool)
    assert detected.ok is True and detected.count == 1 and detected.engine == ENGINE_OASDIFF


def test_compare_service_auto_engine_follows_docker_availability(monkeypatch: pytest.MonkeyPatch) -> None:
    """`auto` 引擎选择：docker 不可用回落结构化判定（并显式记录所用引擎）。"""
    monkeypatch.setattr(contract_gate, "docker_available", lambda: False)
    result = compare_service(contract_gate.REPO_ROOT, "org")
    assert isinstance(result, BreakingResult)
    assert result.ok is True and result.engine == ENGINE_STRUCTURAL


def test_structural_breaking_skips_non_http_and_removed_operation() -> None:
    """结构化判定：非 HTTP 方法键跳过；基线有而当前缺的方法记「删除操作」。"""
    base = _doc(
        paths=ConcurrentStableDict(
            {
                "/a": ConcurrentStableDict(
                    {
                        "parameters": ConcurrentStableList(),
                        "put": ConcurrentStableDict({"responses": ConcurrentStableDict({"200": {}})}),
                    }
                )
            }
        )
    )
    current = _doc(paths=ConcurrentStableDict({"/a": ConcurrentStableDict({"parameters": ConcurrentStableList()})}))
    problems = structural_breaking(base, current)
    assert list(problems) == ["删除操作：PUT /a"]


def test_structural_breaking_reports_removed_schema() -> None:
    """结构化判定：基线组件 schema 整体消失记「删除组件 schema」。"""
    base = _doc(paths=ConcurrentStableDict(), schemas=ConcurrentStableDict({"OrgDept": {"properties": {}}}))
    current = _doc(paths=ConcurrentStableDict(), schemas=ConcurrentStableDict())
    assert list(structural_breaking(base, current)) == ["删除组件 schema：OrgDept"]


def test_mapping_rejects_non_mapping() -> None:
    """`_mapping`：非映射值规整为空映射（不抛异常）。"""
    assert dict(contract_gate._mapping(["a", "b"])) == {}


def test_count_breaking_dict_without_breaking_key() -> None:
    """oasdiff 输出为对象但无 `breaking` 键 / 非数组对象：按 1 项保守计（不假装通过）。"""
    assert count_breaking('{"summary": "x"}') == 1
    assert count_breaking('"unexpected"') == 1


def test_docker_available_reflects_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """docker 可用性判定跟随 PATH 查找结果。"""
    monkeypatch.setattr(contract_gate.shutil, "which", lambda _name: None)
    assert contract_gate.docker_available() is False
    monkeypatch.setattr(contract_gate.shutil, "which", lambda _name: "/usr/bin/docker")
    assert contract_gate.docker_available() is True


def test_run_command_executes_and_captures() -> None:
    """默认执行器：真实子进程调用并捕获输出（不抛异常）。"""
    completed = contract_gate._run_command(ConcurrentStableList([sys.executable, "-c", "print('gate-ok')"]))
    assert completed.returncode == 0 and "gate-ok" in completed.stdout


def test_docker_diff_reports_copy_failure(tmp_path: Path) -> None:
    """docker 编排：`cp` 失败即返回该返回码（不再 start）。"""
    baseline = tmp_path / "base.json"
    created = tmp_path / "cur.json"
    baseline.write_text("{}", encoding="utf-8")
    created.write_text("{}", encoding="utf-8")
    calls: list[str] = []

    def _run(command: ConcurrentStableList[str]) -> subprocess.CompletedProcess[str]:
        verb = command[1]
        calls.append(verb)
        if verb == "cp":
            return subprocess.CompletedProcess(list(command), 1, "", "no such container")
        return subprocess.CompletedProcess(list(command), 0, "", "")

    code, stdout, stderr = docker_diff(baseline, created, "img:1", run=_run)
    assert (code, stdout) == (1, "")
    assert "no such container" in stderr
    assert "start" not in calls


def test_compare_service_reports_build_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """比对：基线在但实时契约构建失败 → 记为工具失败（不是破坏性变更）。"""
    target = baseline_path(tmp_path, "org")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{}", encoding="utf-8")

    def _boom(_service_key: str) -> object:
        raise RuntimeError("起不来")

    monkeypatch.setattr(contract_gate, "build_openapi", _boom)
    result = compare_service(tmp_path, "org", engine=ENGINE_STRUCTURAL)
    assert result.ok is False and "契约构建失败" in result.error


def test_compare_service_oasdiff_oserror(tmp_path: Path) -> None:
    """比对：oasdiff 调用抛 `OSError` → 明确提示确认镜像已预拉。"""
    target = baseline_path(tmp_path, "org")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{}", encoding="utf-8")

    def _broken(_baseline: Path, _current: Path, _image: str) -> tuple[int, str, str]:
        raise OSError("docker 缺失")

    result = compare_service(tmp_path, "org", engine=ENGINE_OASDIFF, diff=_broken)
    assert result.ok is False and "oasdiff 调用失败" in result.error


def test_compare_structurally_rejects_non_object_baseline(tmp_path: Path) -> None:
    """结构化判定：基线内容不是对象 → 明确报「基线非对象」。"""
    target = baseline_path(tmp_path, "org")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("[]", encoding="utf-8")
    result = compare_service(tmp_path, "org", engine=ENGINE_STRUCTURAL)
    assert result.ok is False and result.error == "基线非对象"


def test_check_prints_breaking_and_tool_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """门禁汇总：工具失败与破坏性变更都计入不通过，并逐行打印明细与处置提示。"""
    monkeypatch.setattr(
        contract_gate,
        "compare_service",
        lambda root, key, **kwargs: BreakingResult(key, 0, "", False, ENGINE_STRUCTURAL, error="工具失败"),
    )
    assert check(tmp_path, services=ConcurrentStableList(["org"])) == 1
    assert "工具失败" in capsys.readouterr().out

    monkeypatch.setattr(
        contract_gate,
        "compare_service",
        lambda root, key, **kwargs: BreakingResult(key, 2, "line1\n\nline2", True, ENGINE_STRUCTURAL),
    )
    assert check(tmp_path, services=ConcurrentStableList(["org"])) == 1
    out = capsys.readouterr().out
    assert "检测到 2 项破坏性变更" in out and "line1" in out and "baseline-update" in out


def test_select_services_all_and_single() -> None:
    """目标服务解析：`--all` 取全部在运服务，`--service` 取单个。"""
    assert list(contract_gate._select_services(None, True))
    assert list(contract_gate._select_services("org", False)) == ["org"]


def test_module_entry_point_exits_by_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`python -m ops.contract_gate` 入口按 CLI 参数执行并以退出码结束（无基线即 1）。"""
    monkeypatch.delitem(sys.modules, "ops.contract_gate", raising=False)
    monkeypatch.setattr(
        sys, "argv", ["ops.contract_gate", "check", "--root", str(tmp_path), "--engine", ENGINE_STRUCTURAL]
    )
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("ops.contract_gate", run_name="__main__")
    assert excinfo.value.code == 1
