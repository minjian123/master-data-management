"""服务目录两侧同值护栏用例：产品自持行未在平台登记 / 与平台登记行异值均被拒（fail-closed）。

补充口径：`platform_records()` 是平台清单的只读视图（供外部对账使用），一并断言其可用。
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
def test_validate_local_catalog_rejects_unregistered_and_mismatched(monkeypatch: pytest.MonkeyPatch) -> None:
    """两侧同值：产品行未在平台登记、或同名行字段异值，均被拒并给出原因。"""
    base = MDM_SERVICE_RECORDS[0]
    ghost = dataclasses.replace(base, module_key="ghost")
    mismatch = dataclasses.replace(base, name="不同的服务名")
    monkeypatch.setattr(module_registry, "MDM_SERVICE_RECORDS", ConcurrentStableList([ghost, mismatch]))

    errors = validate_local_catalog()
    assert any("未在平台侧服务目录登记" in message for message in errors)
    assert any("与平台侧登记行不同值" in message for message in errors)
