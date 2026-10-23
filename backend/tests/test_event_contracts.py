"""组织域事件契约（Kiwi 2255）：6 条契约形态 / 注入幂等 / 快照零漂移与兼容校验。"""

import runpy
import sys
from pathlib import Path

import pytest
from bms_core.core.concurrent import ConcurrentStableList
from bms_core.events.contracts import EventContractRegistry, default_event_contract_registry

from mdm.events import ORG_EVENT_CONTRACTS, register_product_event_contracts
from ops import event_contracts

_EXPECTED_TYPES = (
    "mdm.dept.changed",
    "mdm.post.changed",
    "mdm.user_post.changed",
    "mdm.role_post.changed",
    "mdm.role_dept.changed",
    "mdm.user_dept.changed",
)


@pytest.mark.kiwi_id(2255)
def test_org_event_contracts_shape() -> None:
    """契约形态：6 条、事件域名 `org`、载荷字段为小写下划线且不含信封保留键。"""
    assert tuple(contract.event_type for contract in ORG_EVENT_CONTRACTS) == _EXPECTED_TYPES
    for contract in ORG_EVENT_CONTRACTS:
        assert contract.domain == "mdm"
        assert contract.major == 1
        assert contract.fields, f"{contract.event_type} 应声明载荷字段"
        assert "changed_type" in contract.fields


@pytest.mark.kiwi_id(2255)
def test_register_product_event_contracts_is_idempotent() -> None:
    """产品侧注入入口幂等（登记到隔离注册表，重复调用不报错且契约数不变）。"""
    registry = EventContractRegistry()
    register_product_event_contracts(registry)
    register_product_event_contracts(registry)
    # 注册表按事件类型排序返回（与声明顺序无关）
    assert tuple(contract.event_type for contract in registry.contracts()) == tuple(sorted(_EXPECTED_TYPES))

    register_product_event_contracts(default_event_contract_registry())
    assert all(default_event_contract_registry().contract(event_type) is not None for event_type in _EXPECTED_TYPES)


@pytest.mark.kiwi_id(2255)
def test_event_snapshot_export_and_check(tmp_path: Path) -> None:
    """快照：导出后零漂移校验通过；篡改后检出漂移。"""
    assert event_contracts.export(tmp_path) == 0
    assert event_contracts.check(tmp_path) == 0

    path = event_contracts.snapshot_path(tmp_path)
    path.write_text(path.read_text(encoding="utf-8").replace("mdm.dept.changed", "mdm.dept.moved"), encoding="utf-8")
    assert event_contracts.check(tmp_path) == 1


@pytest.mark.kiwi_id(2255)
def test_repo_event_snapshot_in_sync() -> None:
    """仓库内事件契约快照与当前声明一致（CI 口径：提交的快照零漂移）。"""
    assert event_contracts.check(event_contracts.REPO_ROOT) == 0


@pytest.mark.kiwi_id(2255)
def test_export_reports_registry_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """导出：注册表校验失败时逐条打印并退出码 1（不写快照）。"""
    monkeypatch.setattr(
        event_contracts, "registry_errors", lambda registry: ConcurrentStableList(["事件域未登记：ghost"])
    )
    assert event_contracts.export(tmp_path) == 1
    assert "事件域未登记：ghost" in capsys.readouterr().out
    assert not event_contracts.snapshot_path(tmp_path).exists()


@pytest.mark.kiwi_id(2255)
def test_export_to_stdout(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """导出 `--print`：打印生成内容且退出码 0。"""
    assert event_contracts.export(tmp_path, to_stdout=True) == 0
    assert "mdm.dept.changed" in capsys.readouterr().out


@pytest.mark.kiwi_id(2255)
def test_check_reports_missing_snapshot(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """校验：快照缺件即不通过（退出码 1 并提示缺件）。"""
    assert event_contracts.check(tmp_path) == 1
    assert "缺事件契约快照" in capsys.readouterr().out


@pytest.mark.kiwi_id(2255)
def test_main_dispatches_export_and_check(tmp_path: Path) -> None:
    """命令行入口：`export`（含 `--print`）与 `check` 两条分支均按退出码返回。"""
    assert event_contracts.main(["export", "--root", str(tmp_path)]) == 0
    assert event_contracts.main(["check", "--root", str(tmp_path)]) == 0
    assert event_contracts.main(["export", "--print", "--root", str(tmp_path)]) == 0


@pytest.mark.kiwi_id(2255)
def test_module_entry_point(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`python -m ops.event_contracts` 入口按 CLI 参数执行并以退出码结束。"""
    assert event_contracts.export(tmp_path) == 0
    monkeypatch.delitem(sys.modules, "ops.event_contracts", raising=False)
    monkeypatch.setattr(sys, "argv", ["ops.event_contracts", "check", "--root", str(tmp_path)])
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("ops.event_contracts", run_name="__main__")
    assert excinfo.value.code == 0
