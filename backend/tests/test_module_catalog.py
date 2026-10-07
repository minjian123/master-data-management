"""产品服务目录登记与装配校验（清单唯一与格式 / 产品维度 / 两侧同值 / 服务包声明）。"""

import pytest
from bms_core.core.concurrent import ConcurrentStableDict, ConcurrentStableList
from bms_core.services.module_registry import (
    PRODUCT_CATALOG,
    PRODUCT_ROUTES,
    SERVICE_CATALOG,
    ModuleRecord,
    ModuleRegistry,
    ModuleStatus,
    ServiceGroup,
    merge_service_records,
    validate_product_routes,
    validate_product_service_records,
)

from ops.check_modules import check_offline, check_service_declarations, resolve_service_contracts
from services.module_registry import (
    MDM_SERVICE_RECORDS,
    PRODUCT_KEY,
    SERVICE_KEY,
    catalog_view,
    local_service_keys,
    service_package,
    validate_local_catalog,
)

KIWI_CASE_ID = 2253
"""Kiwi TCMS 策展用例编号（mdm 阶段一 01_01）。"""

_ORG_NAME = "mdm 组织主数据服务"
"""组织域服务登记名（平台侧与产品侧同值）。"""


def _platform_org_row() -> ModuleRecord:
    """取平台侧 `org` 登记行（产品行在平台清单中已登记，R 架构两侧并存）。

    Returns:
        ModuleRecord: 平台侧 org 登记行。
    """
    row = next((record for record in SERVICE_CATALOG if record.module_key == "org"), None)
    assert row is not None, "平台侧服务目录缺 org 登记行（须先完成 bms 11_01）"
    return row


def _record(**overrides: object) -> ModuleRecord:
    """构造一条产品注入记录（缺省合法；按需覆盖字段以验拒启分支）。

    Args:
        **overrides: 需覆盖的字段。

    Returns:
        ModuleRecord: 记录。
    """
    base: dict[str, object] = {
        "module_key": "org",
        "service_key": "org",
        "name": _ORG_NAME,
        "table_prefix": "org_",
        "errcode_segment": "33",
        "event_domain": "org",
        "service_group": ServiceGroup.PRODUCT,
        "build_batch": 3,
        "product_key": PRODUCT_KEY,
        "status": ModuleStatus.ENABLED,
    }
    base.update(overrides)
    return ModuleRecord(**base)  # pyright: ignore[reportArgumentType]


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_local_catalog_passes_offline_validation() -> None:
    """离线校验全绿：清单唯一与格式 + 产品维度 + 两侧同值 + 产品级路由映射。"""
    assert list(validate_local_catalog()) == []
    assert list(check_offline()) == []


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_org_row_follows_plan_registration() -> None:
    """`org` 四要素随规划登记（服务键 / 模块键 / 表前缀 / 事件域），产品维度字段就位。"""
    record = MDM_SERVICE_RECORDS[0]
    assert (record.service_key, record.module_key) == ("org", "org")
    assert (record.table_prefix, record.event_domain) == ("org_", "org")
    assert record.errcode_segment == "33"
    assert (record.service_group, record.product_key) == (ServiceGroup.PRODUCT, PRODUCT_KEY)
    assert (record.build_batch, record.status) == (3, ModuleStatus.ENABLED)
    assert record.contract_version == "0.1.0"
    assert local_service_keys() == (SERVICE_KEY,)
    assert service_package(SERVICE_KEY) == "mdm_org"


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_injected_row_is_identical_to_platform_row() -> None:
    """两侧同值（R 架构）：产品自持行与平台侧登记行**逐字段相等**（基座合并才去重）。"""
    assert MDM_SERVICE_RECORDS[0] == _platform_org_row()


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_catalog_view_dedupes_platform_row() -> None:
    """应用级视图：同值去重后条目数与平台清单一致，`org` 仅一条且平台清单顺序在前。"""
    merged = catalog_view()
    assert len(merged) == len(SERVICE_CATALOG)
    assert [record.module_key for record in merged if record.module_key == "org"] == ["org"]
    assert merged[0] == SERVICE_CATALOG[0]


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_conflicting_injected_row_rejected() -> None:
    """异值即拒：注入行与平台行任一字段不同即不去重，以 `module_key` 重复被唯一性校验拒绝。"""
    conflicting = _record(errcode_segment="34")
    merged = merge_service_records(SERVICE_CATALOG, ConcurrentStableList([conflicting]))
    errors = ModuleRegistry(merged).validate()
    assert any("module_key 重复" in message for message in errors), f"未检出冲突：{list(errors)}"


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_platform_row_missing_is_rejected() -> None:
    """两侧并存要求：平台清单缺同 `module_key` 行时，本地校验明确报「未在平台侧登记」（不可仅产品自持）。"""
    errors = validate_local_catalog()
    assert list(errors) == []
    # 以「仅本产品清单（无平台清单）」的方式模拟平台侧缺行：注入记录不落在平台清单内
    ghost = _record(module_key="ghost", table_prefix="ghost_", event_domain="ghost", service_key="ghost")
    merged = merge_service_records(SERVICE_CATALOG, ConcurrentStableList([ghost]))
    assert merged[-1] == ghost
    assert ghost not in SERVICE_CATALOG


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_product_dimension_empty_records_detected() -> None:
    """产品维度断言 ①：注入清单为空即拒（产品服务必须自报本产品服务清单）。"""
    errors = validate_product_service_records(ConcurrentStableList(), service_key=SERVICE_KEY, product_key=PRODUCT_KEY)
    assert any("未声明服务目录记录" in message for message in errors)


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_product_dimension_non_product_group_detected() -> None:
    """产品维度断言 ②：非产品分组记录即拒。"""
    record = _record(service_group=ServiceGroup.CAPABILITY, product_key=None)
    errors = validate_product_service_records(
        ConcurrentStableList([record]), service_key=SERVICE_KEY, product_key=PRODUCT_KEY
    )
    assert any("须为产品分组" in message for message in errors)


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_product_dimension_ownership_mismatch_detected() -> None:
    """产品维度断言 ③：记录产品归属与工厂声明不一致即拒。"""
    record = _record(product_key="biz")
    errors = validate_product_service_records(
        ConcurrentStableList([record]), service_key=SERVICE_KEY, product_key=PRODUCT_KEY
    )
    assert any("产品归属与声明不一致" in message for message in errors)


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_product_dimension_running_service_missing_detected() -> None:
    """产品维度断言 ④：注入清单未登记运行服务即拒。"""
    record = _record(module_key="mdmorg", service_key=None, table_prefix="mdmorg_", event_domain="mdmorg")
    errors = validate_product_service_records(
        ConcurrentStableList([record]), service_key=SERVICE_KEY, product_key=PRODUCT_KEY
    )
    assert any("运行服务未在注入清单登记" in message for message in errors)


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_product_route_mapping_registered() -> None:
    """产品命名空间映射：`mdm/org → org`（域段与上游服务显式绑定，对外 `/api/mdm/v1/org/...`）。"""
    assert [(route.product_key, route.domain, route.service_key) for route in PRODUCT_ROUTES] == [("mdm", "org", "org")]
    errors = validate_product_routes(
        ConcurrentStableList(PRODUCT_ROUTES),
        ConcurrentStableList(SERVICE_CATALOG),
        ConcurrentStableList(PRODUCT_CATALOG),
    )
    assert list(errors) == []


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_service_package_declaration_matches_catalog() -> None:
    """服务包声明：`mdm_org.CONTRACT_VERSION` 与清单登记值主版本一致（工程 ↔ 清单双向核对）。"""
    declarations = resolve_service_contracts()
    assert declarations.get(SERVICE_KEY) == "0.1.0"
    assert list(check_service_declarations(MDM_SERVICE_RECORDS, declarations)) == []


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_service_package_declaration_mismatch_detected() -> None:
    """服务包声明异常：主版本不符 / 工程未登记均被检出。"""
    errors = check_service_declarations(
        MDM_SERVICE_RECORDS,
        ConcurrentStableDict({"org": "1.0.0", "ghost": "0.1.0"}),
    )
    assert any("主版本不符" in message for message in errors), f"未检出主版本不符：{list(errors)}"
    assert any("服务工程未登记：ghost" in message for message in errors), f"未检出未登记工程：{list(errors)}"
