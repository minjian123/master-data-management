"""服务目录产品维度护栏用例：产品清单记录非法 / 归属不一致均被拒（fail-closed）。

产品行**自持**（`deploy/registry/mdm.json` + 装载期注册），平台侧不再保留同值行；
`platform_records()` 保留为平台清单的只读视图（供外部对账使用），一并断言其可用。
"""

import dataclasses

import pytest
from bms_core.core.concurrent import ConcurrentStableList
from bms_core.services.module_registry import SERVICE_CATALOG

from services import module_registry
from services.module_registry import MDM_SERVICE_RECORDS, validate_local_catalog


@pytest.mark.kiwi_id(2253)
def test_platform_records_view_is_available() -> None:
    """平台清单视图：与基座内置清单同量同序（供外部对账读取）。"""
    records = module_registry.platform_records()
    assert len(records) == len(SERVICE_CATALOG)
    assert [record.module_key for record in records] == [record.module_key for record in SERVICE_CATALOG]


@pytest.mark.kiwi_id(2253)
def test_validate_local_catalog_rejects_illegal_and_mismatched(monkeypatch: pytest.MonkeyPatch) -> None:
    """产品维度：格式非法 / 表前缀与模块键不一致 / 产品归属不一致，均被拒并给出原因。"""
    base = MDM_SERVICE_RECORDS[0]
    illegal = dataclasses.replace(base, module_key="Bad", table_prefix="Bad")
    mismatch = dataclasses.replace(base, module_key="mdmx", table_prefix="mdmx_", product_key="biz")
    monkeypatch.setattr(module_registry, "MDM_SERVICE_RECORDS", ConcurrentStableList([illegal, mismatch]))

    errors = validate_local_catalog()
    joined = "；".join(errors)
    assert "module_key 非法" in joined
    assert "产品归属与声明不一致" in joined
