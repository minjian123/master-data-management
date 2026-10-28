"""产品服务目录登记与装配校验（清单唯一与格式 / 产品维度 / 两侧同值 / 服务包声明）。"""

import runpy
import sys
from pathlib import Path

import pytest
from bms_core.core.concurrent import ConcurrentStableDict, ConcurrentStableList
from bms_core.services.module_registry import (
    SERVICE_CATALOG,
    ModuleRecord,
    ModuleRegistry,
    ModuleStatus,
    ServiceGroup,
    product_catalog_view,
    product_routes_view,
    validate_product_routes,
    validate_product_service_records,
)

from ops import check_modules
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

_MDM_NAME = "mdm 主数据服务"
"""产品服务登记名（产品自持，不写平台常量）。"""


def _record(**overrides: object) -> ModuleRecord:
    """构造一条产品注入记录（缺省合法；按需覆盖字段以验拒启分支）。

    Args:
        **overrides: 需覆盖的字段。

    Returns:
        ModuleRecord: 记录。
    """
    base: dict[str, object] = {
        "module_key": "mdm",
        "service_key": "mdm",
        "name": _MDM_NAME,
        "table_prefix": "mdm_",
        "errcode_segment": "33",
        "event_domain": "mdm",
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
def test_mdm_row_follows_registration() -> None:
    """`mdm` 四要素（服务键 / 模块键 / 表前缀 / 事件域）与产品维度字段就位。"""
    record = MDM_SERVICE_RECORDS[0]
    assert (record.service_key, record.module_key) == ("mdm", "mdm")
    assert (record.table_prefix, record.event_domain) == ("mdm_", "mdm")
    assert record.errcode_segment == "33"
    assert (record.service_group, record.product_key) == (ServiceGroup.PRODUCT, PRODUCT_KEY)
    assert (record.build_batch, record.status) == (3, ModuleStatus.ENABLED)
    assert record.contract_version == "0.1.0"
    assert local_service_keys() == (SERVICE_KEY,)
    assert service_package(SERVICE_KEY) == "mdm"


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_product_row_not_in_platform_catalog() -> None:
    """产品自持：`mdm` 行**不在平台常量**里（经产品清单 / 装载期注册进入合并视图）。"""
    assert all(record.module_key != "mdm" for record in SERVICE_CATALOG)
    assert MDM_SERVICE_RECORDS[0] not in SERVICE_CATALOG


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_catalog_view_appends_product_row() -> None:
    """应用级视图：平台清单在前、产品行顺延追加（条目 = 平台清单 + 1）。"""
    merged = catalog_view()
    assert len(merged) == len(SERVICE_CATALOG) + 1
    assert [record.module_key for record in merged if record.module_key == "mdm"] == ["mdm"]
    assert merged[0] == SERVICE_CATALOG[0]
    assert merged[-1] == MDM_SERVICE_RECORDS[0]


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_conflicting_rows_rejected() -> None:
    """异值即拒：同 `module_key` 两条异值记录被唯一性校验拒绝（不静默取一侧）。"""
    conflicting = _record(errcode_segment="34")
    errors = ModuleRegistry(ConcurrentStableList([_record(), conflicting])).validate()
    assert any("module_key 重复" in message for message in errors), f"未检出冲突：{list(errors)}"


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_product_record_registered() -> None:
    """产品档案与产品路由经装载期注册进入视图（平台不再硬编码产品行）。"""
    assert PRODUCT_KEY in {record.product_key for record in product_catalog_view()}
    assert [(route.product_key, route.domain, route.service_key) for route in product_routes_view()] == [
        ("mdm", "mdm", "mdm")
    ]


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
    """产品命名空间映射：`mdm/mdm → mdm`（域段与上游服务显式绑定，对外 `/api/mdm/v1/mdm/...`）。"""
    routes = product_routes_view()
    assert [(route.product_key, route.domain, route.service_key) for route in routes] == [("mdm", "mdm", "mdm")]
    errors = validate_product_routes(
        ConcurrentStableList(routes),
        catalog_view(),
        product_catalog_view(),
    )
    assert list(errors) == []


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_service_package_declaration_matches_catalog() -> None:
    """服务包声明：`mdm.CONTRACT_VERSION` 与清单登记值主版本一致（工程 ↔ 清单双向核对）。"""
    declarations = resolve_service_contracts()
    assert declarations.get(SERVICE_KEY) == "0.1.0"
    assert list(check_service_declarations(MDM_SERVICE_RECORDS, declarations)) == []


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_service_package_declaration_mismatch_detected() -> None:
    """服务包声明异常：主版本不符 / 工程未登记均被检出。"""
    errors = check_service_declarations(
        MDM_SERVICE_RECORDS,
        ConcurrentStableDict({"mdm": "1.0.0", "ghost": "0.1.0"}),
    )
    assert any("主版本不符" in message for message in errors), f"未检出主版本不符：{list(errors)}"
    assert any("服务工程未登记：ghost" in message for message in errors), f"未检出未登记工程：{list(errors)}"


def _write_contract_package(root: Path, key: str, body: str) -> None:
    """在临时根下造一个服务工程的 `__init__.py`。

    Args:
        root: 临时服务工程根。
        key: 服务键。
        body: `__init__.py` 内容。
    """
    init = root / key / "src" / service_package(key) / "__init__.py"
    init.parent.mkdir(parents=True, exist_ok=True)
    init.write_text(body, encoding="utf-8")


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_resolve_service_contracts_non_literal_and_missing(tmp_path: Path) -> None:
    """声明解析：非字符串字面量 / 无赋值语句均记 `None`；无 `__init__.py` 与隐藏目录跳过。"""
    _write_contract_package(tmp_path, "mdm", "CONTRACT_VERSION = 1\n")
    _write_contract_package(tmp_path, "other", "import os\n")
    (tmp_path / "empty").mkdir()
    (tmp_path / ".hidden").mkdir()
    # 编译缓存目录同样跳过（其 `__init__.py` 不是服务包声明，误读会造出伪服务键）
    pycache = tmp_path / "mdm" / "src" / "__pycache__"
    pycache.mkdir(parents=True, exist_ok=True)
    (pycache / "__init__.py").write_text("CONTRACT_VERSION = '9.9.9'\n", encoding="utf-8")
    declarations = resolve_service_contracts(tmp_path)
    assert dict(declarations) == {"mdm": None, "other": None}


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_service_declarations_undeclared_and_non_semver() -> None:
    """声明核对：未声明常量 / 常量非 semver / 清单服务缺对应工程 三类均被检出。"""
    undeclared = check_service_declarations(MDM_SERVICE_RECORDS, ConcurrentStableDict({SERVICE_KEY: None}))
    assert any("未声明 CONTRACT_VERSION" in message for message in undeclared)
    non_semver = check_service_declarations(MDM_SERVICE_RECORDS, ConcurrentStableDict({SERVICE_KEY: "v1"}))
    assert any("非 semver" in message for message in non_semver)
    missing_engineering = check_service_declarations(MDM_SERVICE_RECORDS, ConcurrentStableDict())
    assert list(missing_engineering) == []


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_main_reports_offline_errors(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """入口：离线校验有冲突时逐条打印并返回 1。"""
    monkeypatch.setattr(check_modules, "check_offline", lambda: ConcurrentStableList(["冲突一"]))
    assert check_modules.main([]) == 1
    out = capsys.readouterr().out
    assert "冲突一" in out and "校验失败（1 项）" in out


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_module_entry_point_exits_by_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    """`python -m ops.check_modules` 入口：按 CLI 参数执行并以退出码结束。"""
    monkeypatch.delitem(sys.modules, "ops.check_modules", raising=False)
    monkeypatch.setattr(sys, "argv", ["ops.check_modules", "--offline"])
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("ops.check_modules", run_name="__main__")
    assert excinfo.value.code == 0
