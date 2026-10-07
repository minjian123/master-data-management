"""契约门禁用例（Kiwi 2256）：基线管理 / 结构化「只加不删」判定 / oasdiff 调用链（注入桩，不真联）。

覆盖口径：基线缺件与不可解析、破坏性变更四类（删路径 / 删操作 / 删响应码 / 删 schema 与属性）、
加性变更放行、CLI 参数校验、docker 调用编排（create / cp / start / rm）。
"""

import json
import subprocess
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
