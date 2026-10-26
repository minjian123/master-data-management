"""表归属自持登记与基座注入（Kiwi 2255）：清单形态 / 装载期注册 / 合并视图与清单表集派生（bms 12_04；07C 按域）。"""

from collections.abc import Iterator

import pytest
from bms_core.core.concurrent import ConcurrentStableList, ConcurrentStableSet
from bms_core.services.table_registry import (
    TABLE_OWNERSHIP,
    Datasource,
    TableOwnershipRegistry,
    TableStatus,
    injected_table_records,
    reset_table_records,
    series_tables,
    table_owner,
    table_ownership_view,
    unit_tables,
)

from services.table_registry import MDM_TABLE_RECORDS, ORG_DOMAIN, register, table_names


@pytest.fixture(autouse=True)
def _reset_injected_records() -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    """每个用例前后清空产品注入记录（进程级注册表隔离）。"""
    reset_table_records()
    yield
    reset_table_records()


@pytest.mark.kiwi_id(2255)
def test_mdm_table_records_shape() -> None:
    """mdm 自持清单：六表、归属 `org`、租户库、状态启用（与数据库设计登记一致）。"""
    assert table_names() == (
        "mdm_dept",
        "mdm_post",
        "mdm_user_post",
        "mdm_user_dept",
        "mdm_role_post",
        "mdm_role_dept",
    )
    for record in MDM_TABLE_RECORDS:
        assert record.owner == "mdm"
        assert record.domain == ORG_DOMAIN
        assert record.datasource == Datasource.TENANT
        assert record.status == TableStatus.ENABLED


@pytest.mark.kiwi_id(2255)
def test_register_injects_into_series_and_view() -> None:
    """装载期注册：注入记录进合并视图与 `org:tenant` 清单表集；清空后回到平台清单。"""
    assert "mdm_dept" not in series_tables(ORG_DOMAIN, Datasource.TENANT)
    assert table_owner("mdm_dept") is None

    register()

    assert len(injected_table_records()) == 6
    assert table_owner("mdm_dept") == "mdm"
    assert len(table_ownership_view()) == len(TABLE_OWNERSHIP) + 6
    series = series_tables(ORG_DOMAIN, Datasource.TENANT)
    assert all(name in series for name in table_names())
    # 基础设施表不进域清单（每库一份，由部署单元级建表集追加；架构 39 §4.1 例外）
    infra = ConcurrentStableSet({"sys_outbox", "sys_event_consumed", "sys_event_dead_letter"})
    assert not (infra & series)
    unit = unit_tables((ORG_DOMAIN,), Datasource.TENANT)
    assert infra <= unit
    assert all(name in unit for name in table_names())
    assert TableOwnershipRegistry().validate() == []
    assert not series_tables(ORG_DOMAIN, Datasource.ARCHIVE), "租户层产品表不进归档清单"

    reset_table_records()
    assert "mdm_dept" not in series_tables(ORG_DOMAIN, Datasource.TENANT)


@pytest.mark.kiwi_id(2255)
def test_register_is_idempotent() -> None:
    """重复注册无副作用（同值去重，视图条目数不叠加）。"""
    register()
    register()
    assert len(injected_table_records()) == 6
    assert len(table_ownership_view()) == len(TABLE_OWNERSHIP) + 6
    assert ConcurrentStableList(MDM_TABLE_RECORDS) == injected_table_records()
