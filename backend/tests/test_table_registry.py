"""表归属自持登记与基座注入（Kiwi 2255）：清单形态 / 装载期注册 / 合并视图与链派生（bms 12_04）。"""

from collections.abc import Iterator

import pytest
from bms_core.core.concurrent import ConcurrentStableList, ConcurrentStableSet
from bms_core.services.table_registry import (
    TABLE_OWNERSHIP,
    Datasource,
    TableOwnershipRegistry,
    TableStatus,
    chain_tables,
    injected_table_records,
    reset_table_records,
    table_owner,
    table_ownership_view,
)

from services.table_registry import MDM_TABLE_RECORDS, register, table_names


@pytest.fixture(autouse=True)
def _reset_injected_records() -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    """每个用例前后清空产品注入记录（进程级注册表隔离）。"""
    reset_table_records()
    yield
    reset_table_records()


@pytest.mark.kiwi_id(2255)
def test_mdm_table_records_shape() -> None:
    """mdm 自持清单：五表、归属 `org`、租户库、状态启用（与数据库设计登记一致）。"""
    assert table_names() == ("org_dept", "org_post", "org_user_post", "org_role_post", "org_role_dept")
    for record in MDM_TABLE_RECORDS:
        assert record.owner == "org"
        assert record.datasource == Datasource.TENANT
        assert record.status == TableStatus.ENABLED


@pytest.mark.kiwi_id(2255)
def test_register_injects_into_chain_and_view() -> None:
    """装载期注册：注入记录进合并视图与 `org:tenant` 链派生；清空后回到平台清单。"""
    assert "org_dept" not in chain_tables("org", Datasource.TENANT)
    assert table_owner("org_dept") is None

    register()

    assert len(injected_table_records()) == 5
    assert table_owner("org_dept") == "org"
    assert len(table_ownership_view()) == len(TABLE_OWNERSHIP) + 5
    tenant_chain = chain_tables("org", Datasource.TENANT)
    assert all(name in tenant_chain for name in table_names())
    assert ConcurrentStableSet({"sys_outbox", "sys_event_consumed", "sys_event_dead_letter"}) <= tenant_chain
    assert TableOwnershipRegistry().validate() == []
    assert not chain_tables("org", Datasource.ARCHIVE), "租户层产品表不进归档链"

    reset_table_records()
    assert "org_dept" not in chain_tables("org", Datasource.TENANT)


@pytest.mark.kiwi_id(2255)
def test_register_is_idempotent() -> None:
    """重复注册无副作用（同值去重，视图条目数不叠加）。"""
    register()
    register()
    assert len(injected_table_records()) == 5
    assert len(table_ownership_view()) == len(TABLE_OWNERSHIP) + 5
    assert ConcurrentStableList(MDM_TABLE_RECORDS) == injected_table_records()
