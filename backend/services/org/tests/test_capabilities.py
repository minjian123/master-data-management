"""能力名常量与清单同值断言（07B `03_01`）

口径：mdm 是 `mdm.org.*` 能力的**声明方**，能力名同时出现在「代码常量」（`mdm/capabilities.py`，
端点声明用）与「清单」（`deploy/registry/mdm.toml` 的 `[[collaborations]]`，授权与注册用）。
本用例把两份取值锁在一条断言上：改名只改一处即红，避免静默漂移。
"""

from pathlib import Path

from bms_core.core.concurrent import ConcurrentStableDict, ConcurrentStableList
from bms_core.registry.products import local_manifest_paths, parse_manifest_text
from bms_core.services.module_registry import CollaborationRecord

from mdm.capabilities import ORG_CAPABILITIES

PRODUCT_KEY = "mdm"
"""本产品标识（清单归属）。"""

PLATFORM_CONSUMER = "platform"
"""收编能力的默认消费方（宿主编排服务）。"""


def _declared(paths: ConcurrentStableList[Path] | None = None) -> ConcurrentStableDict[str, CollaborationRecord]:
    """读清单，取 `mdm` 产品声明的能力记录（非本产品的清单跳过）。

    Args:
        paths: 待解析清单路径（缺省取本仓自持清单）。

    Returns:
        ConcurrentStableDict[str, CollaborationRecord]: `{能力名: 记录}`。
    """
    declared: ConcurrentStableDict[str, CollaborationRecord] = ConcurrentStableDict()
    for path in paths if paths is not None else local_manifest_paths():
        manifest = parse_manifest_text(path.read_text(encoding="utf-8"), source=str(path))
        if manifest.product_key != PRODUCT_KEY:
            continue
        for record in manifest.collaborations:
            declared.set(record.name, record)
    return declared


def test_org_capabilities_match_manifest() -> None:
    """五个端点能力逐项在清单中声明：同域（org）／有访问面／默认消费方含 platform。"""
    declared = _declared()

    missing = [name for name in ORG_CAPABILITIES if name not in declared]
    assert missing == [], f"清单缺能力声明：{missing}"

    for name in ORG_CAPABILITIES:
        record = declared[name]
        assert record.domain == "org", f"能力 {name} 的提供方业务域应为 org"
        assert record.path, f"能力 {name} 缺访问面路径"
        assert PLATFORM_CONSUMER in record.default_consumers, f"能力 {name} 的默认消费方缺 {PLATFORM_CONSUMER}"


def test_declared_skips_foreign_manifest(tmp_path: Path) -> None:
    """非本产品的清单不参与取值（多产品并置时不得串味）。"""
    foreign = tmp_path / "other.toml"
    foreign.write_text('product_key = "other"\n', encoding="utf-8")
    paths = ConcurrentStableList(local_manifest_paths())
    paths.add(foreign)

    declared = _declared(paths)

    assert set(ORG_CAPABILITIES) <= set(declared)


def test_org_capabilities_are_unique_and_namespaced() -> None:
    """常量集合无重复、且全部落在本产品命名空间（防止复制粘贴串到别的产品）。"""
    assert len(set(ORG_CAPABILITIES)) == len(ORG_CAPABILITIES)
    assert all(name.startswith(f"{PRODUCT_KEY}.org.") for name in ORG_CAPABILITIES)
