"""mdm 侧共享测试库准备集（04-6-2）：`platform` / `tenant` 两个逻辑数据源的建库与播种。

与 bms 仓 `backend/tests_support/shared_db.py` 同构（同一 .ready 版本戳机制），差异在**建表集**：

- mdm 仓的 `known_domains()` 只登记本产品域（`org` 等），`domains_metadata(..., DATASOURCE_TENANT)`
  派生的租户库建表集已含 `mdm_*` 六表 + 基础设施表；
- 平台库（`sys_tenant` / `sys_config` / `sys_user` / 会话与发件箱）不在 mdm 的域布局里，
  故**显式导入基座平台模型**后再 `Base.metadata.create_all`。

口径（《测试规范》「测试数据」）：每个逻辑数据源只有一套库、全 worker 共用、用例叠加；
种子租户主键对齐到测试租户源口径（`demo → 1001` / `acme → 2002`）。
"""

from __future__ import annotations

import asyncio

from bms_core.config.seed import seed_configs
from bms_core.core.exceptions import ConfigError
from bms_core.db.bootstrap import domains_metadata
from bms_core.db.migration import DATASOURCE_TENANT, known_domains
from bms_core.models.base import SQLITE_PADDED_WIDTH, Base
from bms_core.tenant.seed.tenant import seed_tenants
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

SEED_TENANT_IDS: tuple[tuple[str, int], ...] = (("demo", 1001), ("acme", 2002))
"""种子租户编码 → 固定主键（与 bms 测试租户源口径一致）。"""

# 基座平台模型：mdm 的域布局不含这些域，需显式导入后由 `Base.metadata.create_all` 建表
_PLATFORM_MODEL_MODULES: tuple[str, ...] = (
    "bms_core.config.models",
    "bms_core.models.identity.identity_provider",
    "bms_core.models.identity.session",
    "bms_core.models.identity.user_identity",
    "bms_core.models.outbox",
    "bms_core.models.platform.capability_grant",
    "bms_core.models.platform.catalog",
    "bms_core.models.platform.declaration",
    "bms_core.models.platform.icon",
    "bms_core.models.platform.menu_form",
    "bms_core.models.platform.permission_meta",
    "bms_core.models.platform.role",
    "bms_core.models.platform.task",
    "bms_core.models.platform.tenant_topology",
    "bms_core.models.platform.user",
    "bms_core.models.tenant.tenant",
    "bms_core.models.tenant.tenant_database",
    "bms_core.models.tenant.tenant_module",
    "bms_core.models.tenant.tenant_quota",
    "bms_core.models.tenant.user_tenant",
)


def prepare_platform(url: str) -> None:
    """准备平台库：基座平台模型建表 → 种子租户 → 主键对齐。

    Args:
        url: 共享平台库连接串。
    """
    asyncio.run(_prepare_platform(url))


async def _prepare_platform(url: str) -> None:
    """平台库准备集的异步实现（见 `prepare_platform`）。

    Args:
        url: 共享平台库连接串。
    """
    import importlib

    from services.table_registry import register

    for module in _PLATFORM_MODEL_MODULES:
        importlib.import_module(module)
    register()

    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await _enable_concurrency(engine)
    finally:
        await engine.dispose()
    await seed_tenants(url)
    await _align_seed_tenant_ids(url)


async def _align_seed_tenant_ids(url: str) -> None:
    """把种子租户主键对齐到测试租户源口径（含库名对照行；幂等）。

    Args:
        url: 共享平台库连接串。
    """
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            for code, tenant_id in SEED_TENANT_IDS:
                await connection.execute(
                    text(
                        "UPDATE sys_tenant_database SET tenant_id = :new WHERE tenant_id = "
                        "(SELECT id FROM sys_tenant WHERE code = :code AND deleted_at IS NULL)"
                    ),
                    {"new": str(tenant_id).zfill(SQLITE_PADDED_WIDTH), "code": code},
                )
                await connection.execute(
                    text("UPDATE sys_tenant SET id = :new WHERE code = :code AND deleted_at IS NULL"),
                    {"new": str(tenant_id).zfill(SQLITE_PADDED_WIDTH), "code": code},
                )
    finally:
        await engine.dispose()


def prepare_tenant(url: str) -> None:
    """准备租户库：按「域 × 数据源」派生建表集 → 平台默认参数种子。

    Args:
        url: 共享租户库连接串。
    """
    asyncio.run(_prepare_tenant(url))


async def _prepare_tenant(url: str) -> None:
    """租户库准备集的异步实现（见 `prepare_tenant`）。

    Args:
        url: 共享租户库连接串。
    """
    metadata = _tenant_metadata()
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(metadata.create_all)
        await _enable_concurrency(engine)
    finally:
        await engine.dispose()
    await _seed_configs(url)


def _tenant_metadata():  # 返回 MetaData，注解留空避免上层类型依赖
    """租户库建表集元数据（域并集 + 基础设施表；域布局缺失时回落全模型并集）。

    Returns:
        MetaData: 建表集元数据。
    """
    try:
        return domains_metadata(known_domains(), DATASOURCE_TENANT)
    except ConfigError:
        return Base.metadata


async def _seed_configs(url: str) -> None:
    """写入平台默认参数（幂等）。

    Args:
        url: 共享租户库连接串。
    """
    engine = create_async_engine(url, poolclass=NullPool)
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            await seed_configs(session)
            await session.commit()
    finally:
        await engine.dispose()


async def _enable_concurrency(engine: AsyncEngine) -> None:
    """设置写锁等待上限（`busy_timeout`），与 bms 侧同口径。

    Args:
        engine: 共享库引擎。
    """
    autocommit = engine.execution_options(isolation_level="AUTOCOMMIT")
    try:
        async with autocommit.connect() as connection:
            await connection.exec_driver_sql("PRAGMA busy_timeout=30000")
    finally:
        await autocommit.dispose()


__all__ = ["SEED_TENANT_IDS", "prepare_platform", "prepare_tenant"]
