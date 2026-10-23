"""mdm 服务标识归并（任务 01_05）闭合用例：服务标识 / 表前缀 / 库名 / 事件域 / 契约文件名全链一致。

断言面（改名闭合，防旧口径回流）：

1. 服务标识与产品标识同为 `mdm`，服务行四要素闭合（`service_key` / `table_prefix` / `event_domain` / 错误码段）；
2. 六表全部 `mdm_` 前缀且归属服务 `mdm`（表前缀首段 = 服务标识，基座硬校验）；
3. `form_key` / `table` / `data_source_key` 三者同名闭合；
4. 事件契约 6 条全部落在 `mdm.` 域（无 `org.` 残留）；
5. 公开契约快照文件名 = 服务标识（`deploy/contracts/mdm.json` 在、旧名不在）；
6. 产品登记清单 `deploy/registry/mdm.json` 的服务行与代码清单逐字段同值；
7. 库名派生：`[database].name_prefix` 等于服务标识时去重（`mdm` / `mdm_{租户}`），不等于时保持拼接。
"""

import json
from pathlib import Path

import pytest
from bms_core.db.keys import platform_database_name, tenant_database_name

from mdm.events.contracts import ORG_EVENT_CONTRACTS
from services.form_registry import MDM_FORM_RECORDS
from services.module_registry import MDM_SERVICE_RECORDS, PRODUCT_KEY, SERVICE_KEY
from services.table_registry import MDM_TABLE_RECORDS

KIWI_CASE_ID = 2348
"""Kiwi TCMS 策展用例编号（mdm 阶段一 01_05）。"""

_REPO_ROOT = Path(__file__).resolve().parents[2]
"""mdm 仓根（本文件位于 `backend/tests/`）。"""

_MANIFEST = _REPO_ROOT / "deploy" / "registry" / "mdm.json"
"""产品登记清单（平台侧按 `[registry].product_manifests` 装载的同一份）。"""

_CONTRACTS_DIR = _REPO_ROOT / "deploy" / "contracts"
"""公开契约快照目录。"""

_TABLE_NAMES = (
    "mdm_dept",
    "mdm_post",
    "mdm_user_post",
    "mdm_user_dept",
    "mdm_role_post",
    "mdm_role_dept",
)
"""组织域六表（服务标识归并后的表名）。"""


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_service_identity_is_mdm() -> None:
    """服务标识与产品标识同为 `mdm`，服务行四要素闭合。"""
    assert SERVICE_KEY == "mdm"
    assert PRODUCT_KEY == "mdm"
    assert len(MDM_SERVICE_RECORDS) == 1
    row = MDM_SERVICE_RECORDS[0]
    assert row.module_key == "mdm"
    assert row.service_key == "mdm"
    assert row.table_prefix == "mdm_"
    assert row.event_domain == "mdm"
    assert row.errcode_segment == "33"
    assert row.product_key == "mdm"


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_table_prefix_follows_service_identity() -> None:
    """六表全部 `mdm_` 前缀且归属服务 `mdm`（表前缀首段 = 服务标识）。"""
    registered = {record.table_name: record.owner for record in MDM_TABLE_RECORDS}
    for table_name in _TABLE_NAMES:
        assert table_name in registered
        assert registered[table_name] == SERVICE_KEY
    assert all(name.startswith("mdm_") for name in registered)


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_form_key_and_data_source_key_close_with_table_name() -> None:
    """`form_key` / `table` / `data_source_key` 三者同名闭合（改名前缀同步后仍闭合）。"""
    assert {record.form_key for record in MDM_FORM_RECORDS} == {"mdm_dept", "mdm_post"}
    for record in MDM_FORM_RECORDS:
        assert record.form_key == record.table
        assert record.data_source_key == record.form_key


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_event_contracts_all_in_mdm_domain() -> None:
    """事件契约 6 条，全部落在 `mdm.` 域（无 `org.` 旧域残留）。"""
    event_types = [contract.event_type for contract in ORG_EVENT_CONTRACTS]
    assert len(event_types) == 6
    assert all(event_type.startswith("mdm.") for event_type in event_types)
    assert not any(event_type.startswith("org.") for event_type in event_types)


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_public_contract_snapshot_named_after_service() -> None:
    """公开契约快照文件名 = 服务标识（新名在、旧名不在）。"""
    assert (_CONTRACTS_DIR / "mdm.json").is_file()
    assert (_CONTRACTS_DIR / "baseline" / "mdm.json").is_file()
    assert not (_CONTRACTS_DIR / "org.json").exists()
    assert not (_CONTRACTS_DIR / "baseline" / "org.json").exists()


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_product_manifest_service_row_matches_code_catalog() -> None:
    """产品登记清单的服务行与代码清单逐字段同值（零漂移，手改 JSON 即红）。"""
    payload = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    assert payload["product_key"] == PRODUCT_KEY
    assert len(payload["services"]) == len(MDM_SERVICE_RECORDS)
    row = MDM_SERVICE_RECORDS[0]
    manifest_row = payload["services"][0]
    assert manifest_row["module_key"] == row.module_key
    assert manifest_row["service_key"] == row.service_key
    assert manifest_row["table_prefix"] == row.table_prefix
    assert manifest_row["event_domain"] == row.event_domain
    assert manifest_row["errcode_segment"] == row.errcode_segment
    assert manifest_row["product_key"] == row.product_key
    route = payload["product_routes"][0]
    assert (route["product_key"], route["domain"], route["service_key"]) == ("mdm", "mdm", "mdm")


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_database_names_dedupe_when_prefix_equals_service() -> None:
    """库名派生：前缀等于服务标识时去重，不等时保持拼接。"""
    assert platform_database_name("mdm", prefix="mdm") == "mdm"
    assert tenant_database_name("mdm", "acme", prefix="mdm") == "mdm_acme"
    assert platform_database_name("org", prefix="bms") == "bms_org"
    assert tenant_database_name("org", "acme", prefix="bms") == "bms_org_acme"
