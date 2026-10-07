"""org:tenant 迁移链（Kiwi 2255）：链头 / 表集与模型零漂移 / 升降级往返。"""

import asyncio
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from bms_core.db.migration import chain_metadata, has_revisions, head_revision, resolve_chain, upgrade_chain
from bms_core.services.table_registry import chain_tables
from sqlalchemy import Connection, inspect
from sqlalchemy.ext.asyncio import create_async_engine

from services.table_registry import register

_CHAIN = "org:tenant"

_ORG_TABLES = ("org_dept", "org_post", "org_user_post", "org_role_post", "org_role_dept")
_INFRA_TABLES = ("sys_outbox", "sys_event_consumed", "sys_event_dead_letter")


def _table_names(connection: Connection) -> set[str]:
    """取库内表名集合。

    Args:
        connection: 同步连接。

    Returns:
        set[str]: 表名集合。
    """
    return set(inspect(connection).get_table_names())


def _metadata_diff(connection: Connection) -> list[str]:
    """迁移后库结构 vs 链元数据的逐项差异（零漂移断言用）。

    Args:
        connection: 同步连接。

    Returns:
        list[str]: 差异明细（空表示零漂移）。
    """
    context = MigrationContext.configure(connection, opts={"compare_type": True})
    return [str(item) for item in compare_metadata(context, chain_metadata(resolve_chain(_CHAIN)))]


def _upgrade(url: str) -> None:
    """同步执行链升级（在线模式）。

    Args:
        url: 目标库连接串。
    """
    upgrade_chain(resolve_chain(_CHAIN), url)


def _downgrade(url: str, revision: str) -> None:
    """同步执行链降级到指定修订（往返验证用；连接串经 `-x url=` 显式传入，不落配置）。

    Args:
        url: 目标库连接串。
        revision: 目标修订号。
    """
    from types import SimpleNamespace

    from bms_core.db.migration import alembic_config

    from alembic import command

    config = alembic_config(resolve_chain(_CHAIN))
    config.cmd_opts = SimpleNamespace(x=[f"url={url}"])  # pyright: ignore[reportAttributeAccessIssue]
    command.downgrade(config, revision)


def _sync_table_names(url: str) -> set[str]:
    """经同步引擎取表名集合（降级后核对用）。

    Args:
        url: 异步连接串（SQLite 文件库）。

    Returns:
        set[str]: 表名集合。
    """
    from sqlalchemy import create_engine

    engine = create_engine(url.replace("+aiosqlite", ""))
    try:
        with engine.connect() as connection:
            return set(inspect(connection).get_table_names())
    finally:
        engine.dispose()


@pytest.mark.kiwi_id(2255)
def test_org_tenant_chain_registered() -> None:
    """链注册：`org:tenant` 有脚本、链头为 `0002_outbox_tables`、表集含五表 + 基础设施三表。"""
    register()
    chain = resolve_chain(_CHAIN)
    assert has_revisions(chain)
    assert head_revision(chain) == "0002_outbox_tables"
    tables = chain_tables("org", "tenant")
    assert all(name in tables for name in (*_ORG_TABLES, *_INFRA_TABLES))


@pytest.mark.kiwi_id(2255)
async def test_org_tenant_migration_upgrades_with_zero_drift(tmp_path: Path) -> None:
    """迁移：`org:tenant` 升到 head 建齐八表，且库结构与模型元数据零漂移。"""
    register()
    url = f"sqlite+aiosqlite:///{tmp_path / 'org.db'}"
    await asyncio.to_thread(_upgrade, url)

    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            names = await connection.run_sync(_table_names)
            diffs = await connection.run_sync(_metadata_diff)
    finally:
        await engine.dispose()

    assert all(name in names for name in (*_ORG_TABLES, *_INFRA_TABLES))
    assert diffs == []


@pytest.mark.kiwi_id(2255)
def test_org_tenant_migration_downgrades(tmp_path: Path) -> None:
    """降级：回退到 `0001_org_tables` 后基础设施三表移除、业务五表保留。"""
    register()
    url = f"sqlite+aiosqlite:///{tmp_path / 'org.db'}"
    _upgrade(url)
    _downgrade(url, "0001_org_tables")

    names = _sync_table_names(url)

    assert all(name in names for name in _ORG_TABLES)
    assert not any(name in names for name in _INFRA_TABLES)
