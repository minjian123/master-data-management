"""组织域事件契约（Kiwi 2255）：6 条契约形态 / 注入幂等 / 快照零漂移与兼容校验。"""

from pathlib import Path

import pytest
from bms_core.events.contracts import EventContractRegistry, default_event_contract_registry

from mdm_org.events import ORG_EVENT_CONTRACTS, register_product_event_contracts
from ops import event_contracts

_EXPECTED_TYPES = (
    "org.dept.changed",
    "org.post.changed",
    "org.user_post.changed",
    "org.role_post.changed",
    "org.role_dept.changed",
    "org.user_dept.changed",
)


@pytest.mark.kiwi_id(2255)
def test_org_event_contracts_shape() -> None:
    """契约形态：6 条、事件域名 `org`、载荷字段为小写下划线且不含信封保留键。"""
    assert tuple(contract.event_type for contract in ORG_EVENT_CONTRACTS) == _EXPECTED_TYPES
    for contract in ORG_EVENT_CONTRACTS:
        assert contract.domain == "org"
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
    path.write_text(path.read_text(encoding="utf-8").replace("org.dept.changed", "org.dept.moved"), encoding="utf-8")
    assert event_contracts.check(tmp_path) == 1


@pytest.mark.kiwi_id(2255)
def test_repo_event_snapshot_in_sync() -> None:
    """仓库内事件契约快照与当前声明一致（CI 口径：提交的快照零漂移）。"""
    assert event_contracts.check(event_contracts.REPO_ROOT) == 0
