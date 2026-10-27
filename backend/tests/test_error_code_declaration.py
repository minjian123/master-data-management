"""产品自持错误码声明 ↔ 代码逐条对账（07B `02_05` 第七类记录）。

`deploy/registry/mdm.toml` 的 `[[errcodes]]` 段是**对外承诺的唯一声明**，须与
`mdm/errors.py` 的 `OrgErrorCode` 枚举及异常类 `http_status_` 逐条一致：
码集合相同、`http_status` 相同、`message_key` 形如 `mdm.error.<snake>`、描述与级别齐备。

新增用例的 Kiwi 编号由 07B `05_01` 统一登记后回填（本批不标 `kiwi_id`）。
"""

# pyright: reportUnusedFunction=false
# 基座 `bms-core` 为跨仓锁 rev 依赖：`ProductManifest.error_codes` 随 07B `02_05` 进入基座，
# rev 前移前静态检查按已安装版本解析（运行时由 `hasattr` 守卫跳过），故本文件关闭该属性检查。
# pyright: reportAttributeAccessIssue=false, reportUnknownMemberType=false, reportUnknownVariableType=false
import inspect
import tomllib
from pathlib import Path
from typing import cast

import pytest
from bms_core.core.concurrent import ConcurrentStableDict

from mdm import errors as errors_module
from mdm.errors import OrgError, OrgErrorCode

_REPO_ROOT = Path(__file__).resolve().parents[2]
"""mdm 仓根（本文件位于 `backend/tests/`）。"""

_MANIFEST = _REPO_ROOT / "deploy" / "registry" / "mdm.toml"
"""产品自持声明（平台侧按 `[registry].product_manifests` 装载的同一份）。"""


def _declared() -> ConcurrentStableDict[int, ConcurrentStableDict[str, object]]:
    """读取清单 `[[errcodes]]` 段（`code → 声明`）。

    Returns:
        ConcurrentStableDict[int, ConcurrentStableDict[str, object]]: 声明映射。
    """
    payload = tomllib.loads(_MANIFEST.read_text(encoding="utf-8"))
    declared: ConcurrentStableDict[int, ConcurrentStableDict[str, object]] = ConcurrentStableDict()
    for item in payload.get("errcodes", []):
        declared.set(cast("int", item["code"]), ConcurrentStableDict(item))
    return declared


def _raised_status() -> ConcurrentStableDict[int, int]:
    """取代码中实际抛出的「码 → HTTP 状态」（异常类预置值）。

    Returns:
        ConcurrentStableDict[int, int]: 状态映射。
    """
    statuses: ConcurrentStableDict[int, int] = ConcurrentStableDict()
    for _, member in inspect.getmembers(errors_module, lambda item: isinstance(item, type)):
        if not issubclass(member, OrgError) or member is OrgError:
            continue
        error = member()
        statuses.set(error.code, error.http_status)
    return statuses


def test_declared_codes_match_enum() -> None:
    """码集合：声明与 `OrgErrorCode` 枚举完全一致（不漏登、不多登）。"""
    assert set(_declared()) == {int(member) for member in OrgErrorCode}


def test_declared_status_matches_exception_classes() -> None:
    """`http_status`：声明与异常类预置值一致（漂移即失败，防两处口径分叉）。"""
    declared = _declared()
    statuses = _raised_status()
    assert set(statuses) == set(declared)
    for code, status in statuses.items():
        assert cast("int", declared[code]["http_status"]) == status, f"错误码 {code} 状态与异常类不一致"


def test_declared_fields_are_complete() -> None:
    """字段：`message_key` 形如 `mdm.error.<snake>`、业务域 `org`、级别枚举、描述非空、状态启用。"""
    for code, item in _declared().items():
        message_key = str(item["message_key"])
        assert message_key.startswith("mdm.error."), f"错误码 {code} 文案键前缀不符"
        assert message_key.removeprefix("mdm.error.").islower(), f"错误码 {code} 文案键须为小写"
        assert item["domain"] == "org"
        assert item["severity"] in {"info", "warning", "error"}
        assert str(item["description"]).strip()
        assert item.get("status", "enabled") == "enabled"


@pytest.mark.parametrize("code", [330051, 330101, 330113])
def test_manifest_loadable_by_platform(code: int) -> None:
    """装载口径：平台基座能解析该清单并给出注入的 `product_key` / `segment`。

    基座 `bms-core` 为跨仓锁 rev 依赖：`error_codes` 字段随 07B `02_05` 进入基座，
    rev 前移前本用例自动跳过（前移后自动生效，无需改断言）。

    Args:
        code: 抽查的错误码（边界与常用码）。
    """
    from bms_core.registry.products import ProductManifest, load_product_manifest

    if not hasattr(ProductManifest, "error_codes"):
        pytest.skip("bms-core rev 待前移（07B 02_05 跨仓窗口）")
    manifest = load_product_manifest(_MANIFEST)
    records = {record.code: record for record in manifest.error_codes}
    assert records[code].product_key == "mdm"
    assert records[code].segment == "33"
