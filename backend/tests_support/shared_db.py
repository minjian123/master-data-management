"""mdm 侧共享测试库准备集（薄壳）：转发基座通用实现 `bms_core.testing.shared_db`。

2026-11-04 收敛：准备集实现下沉基座（只依赖 `bms_core` 自身），平台仓 / mdm / msg 共用一份，
本仓只在此声明差异：

- **平台库**：先注册本产品表归属（`services.table_registry.register()`，供归属视图与对账用例），
  再导入 mdm 自有模型（`mdm.models::MODEL_MODULES`）后建表；本仓平台库仅作测试底座，不种服务目录；
  种子租户与主键对齐沿用基座默认（`demo → 1001` / `acme → 2002`，与 `FakeTenantSource` 同口径）。
- **租户库**：域集合取本仓已知域（`mdm`，由 `deploy/boundaries/domain_layout.json` 与表归属派生），
  建表集经基座 `domains_metadata` 按「域 × 数据源」派生，已含 `mdm_*` 六表 + 基础设施表。

`.ready` 版本戳由本文件源码摘要派生（`bms_core.testing.fixtures::version_for`），准备内容一改即自动重建。
"""

from __future__ import annotations

from bms_core.testing import shared_db as base_shared_db
from bms_core.testing.shared_db import SEED_TENANT_IDS

from services.table_registry import register as register_tables

__all__ = ["SEED_TENANT_IDS", "prepare_platform", "prepare_tenant"]


def _product_model_modules() -> tuple[str, ...]:
    """本产品自有模型模块（导入即把表登记进 `Base.metadata`）。

    Returns:
        tuple[str, ...]: 模型模块清单。
    """
    from mdm.models import MODEL_MODULES

    return tuple(MODEL_MODULES)


def prepare_platform(url: str) -> None:
    """准备平台库：表归属登记 → 导入产品模型 → 建表 → 种子租户 → 主键对齐（幂等）。

    Args:
        url: 共享平台库连接串。
    """
    register_tables()
    base_shared_db.prepare_platform(url, model_modules=_product_model_modules())


def prepare_tenant(url: str) -> None:
    """准备租户库：域并集（`mdm`）建表 → 系统参数种子（幂等）。

    Args:
        url: 共享租户库连接串。
    """
    register_tables()
    base_shared_db.prepare_tenant(url, model_modules=_product_model_modules())
