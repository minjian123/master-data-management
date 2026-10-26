"""org:tenant 迁移清单（Kiwi 2255）：清单头 / 表集与模型零漂移 / 升降级往返（07C 按业务域）。"""

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from bms_core.db.migration import has_revisions, head_revision, resolve_series, series_metadata, upgrade_series
from bms_core.services.table_registry import series_tables, unit_tables
from sqlalchemy import Connection, Engine, create_engine, inspect
from sqlalchemy.ext.asyncio import create_async_engine

from services.table_registry import ORG_DOMAIN, register

_SERIES = "org:tenant"

_ORG_TABLES = ("mdm_dept", "mdm_post", "mdm_user_post", "mdm_user_dept", "mdm_role_post", "mdm_role_dept")
_ORG_TABLES_BASE = ("mdm_dept", "mdm_post", "mdm_user_post", "mdm_role_post", "mdm_role_dept")
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
    """迁移后库结构 vs 清单元数据的逐项差异（零漂移断言用）。

    **基础设施表不进域清单元数据**（每库一份，由部署单元级建表集管理；架构 39 §4.1 例外），
    故此处只比对 org 域表，`sys_outbox` 等由迁移脚本建的表不计入差异。

    Args:
        connection: 同步连接。

    Returns:
        list[str]: 差异明细（空表示零漂移）。
    """
    context = MigrationContext.configure(connection, opts={"compare_type": True})
    diffs = [str(item) for item in compare_metadata(context, series_metadata(resolve_series(_SERIES)))]
    # 版本记录表（`alembic_version_{domain}`）同样不进域清单元数据
    ignored = (*_INFRA_TABLES, "alembic_version")
    return [item for item in diffs if not any(name in item for name in ignored)]


def _upgrade(url: str) -> None:
    """同步执行链升级（在线模式）。

    Args:
        url: 目标库连接串。
    """
    upgrade_series(resolve_series(_SERIES), url)


def _downgrade(url: str, revision: str) -> None:
    """同步执行链降级到指定修订（往返验证用；连接串经 `-x url=` 显式传入，不落配置）。

    Args:
        url: 目标库连接串。
        revision: 目标修订号。
    """
    from types import SimpleNamespace

    from bms_core.db.migration import alembic_config

    from alembic import command

    config = alembic_config(resolve_series(_SERIES))
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
def test_org_tenant_series_registered() -> None:
    """清单注册：`org:tenant` 有脚本、清单头为 `0005_mdm_form_key`、域表集为六表（基础设施另计）。"""
    register()
    series = resolve_series(_SERIES)
    assert has_revisions(series)
    assert head_revision(series) == "0005_mdm_form_key"
    tables = series_tables(ORG_DOMAIN, "tenant")
    assert all(name in tables for name in _ORG_TABLES)
    unit = unit_tables((ORG_DOMAIN,), "tenant")
    assert all(name in unit for name in (*_ORG_TABLES, *_INFRA_TABLES))


@pytest.mark.kiwi_id(2255)
async def test_org_tenant_migration_upgrades_with_zero_drift(tmp_path: Path) -> None:
    """迁移：`org:tenant` 升到 head 建齐八表，且库结构与模型元数据零漂移。"""
    register()
    url = f"sqlite+aiosqlite:///{tmp_path / 'mdm.db'}"
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
    """降级：回退到 `0001_mdm_tables` 后基础设施三表与 `mdm_user_dept`（0004 建）移除、首建五表保留。"""
    register()
    url = f"sqlite+aiosqlite:///{tmp_path / 'mdm.db'}"
    _upgrade(url)
    _downgrade(url, "0001_mdm_tables")

    names = _sync_table_names(url)

    assert all(name in names for name in _ORG_TABLES_BASE)
    assert "mdm_user_dept" not in names
    assert not any(name in names for name in _INFRA_TABLES)


@pytest.mark.kiwi_id(2268)
def test_dept_code_backfilled_on_upgrade(tmp_path: Path) -> None:
    """存量回填：升级 `0003_dept_code` 后按 `id` 升序补 `DEPT` + 定长序号，且 `code` 置非空。"""
    register()
    url = f"sqlite+aiosqlite:///{tmp_path / 'mdm.db'}"
    _upgrade(url)
    _downgrade(url, "0002_outbox_tables")
    _insert_legacy_depts(url, 2)
    _upgrade(url)

    assert _dept_codes(url) == ["DEPT0001", "DEPT0002"]
    assert _code_column_not_null(url)


@pytest.mark.kiwi_id(2340)
def test_form_key_backfilled_on_upgrade(tmp_path: Path) -> None:
    """存量回填：升级 `0005_mdm_form_key` 后存量部门 / 岗位行 `form_key` 取表常量、`parent_id` 保持空。"""
    register()
    url = f"sqlite+aiosqlite:///{tmp_path / 'mdm.db'}"
    _upgrade(url)
    _downgrade(url, "0004_user_dept_and_primary")
    _insert_legacy_org_rows(url)
    _upgrade(url)

    assert _form_key_values(url, "mdm_dept") == ["mdm_dept"]
    assert _form_key_values(url, "mdm_post") == ["mdm_post"]
    assert _post_parent_ids(url) == [None]


def _sync_engine(url: str) -> Engine:
    """构造同步引擎（SQLite 文件库；迁移前造数与迁移后核对用）。

    Args:
        url: 异步连接串（`sqlite+aiosqlite:///...`）。

    Returns:
        Engine: 同步引擎（用完即 dispose）。
    """
    return create_engine(url.replace("+aiosqlite", ""))


def _insert_legacy_depts(url: str, count: int) -> None:
    """在无 `code` 列的旧结构上插入存量部门（回填验证用）。

    Args:
        url: 目标库连接串。
        count: 插入条数。
    """
    engine = _sync_engine(url)
    try:
        with engine.begin() as connection:
            for index in range(count):
                connection.execute(
                    sa.text(
                        "INSERT INTO mdm_dept (id, ancestors, name, sort, status, created_at, updated_at, version)"
                        " VALUES (:dept_id, '/', :name, 0, 'enabled', :now, :now, 1)"
                    ),
                    {
                        "dept_id": 9001 + index,
                        "name": f"存量部门{index + 1}",
                        "now": datetime(2026, 10, 8, tzinfo=UTC),
                    },
                )
    finally:
        engine.dispose()


def _dept_codes(url: str) -> list[str]:
    """取部门编码（按 `id` 升序）。

    Args:
        url: 目标库连接串。

    Returns:
        list[str]: 编码列表。
    """
    engine = _sync_engine(url)
    try:
        with engine.connect() as connection:
            rows = connection.execute(sa.text("SELECT code FROM mdm_dept ORDER BY id")).fetchall()
            return [str(row[0]) for row in rows]
    finally:
        engine.dispose()


def _code_column_not_null(url: str) -> bool:
    """`mdm_dept.code` 是否已置为非空（迁移第三步）。

    Args:
        url: 目标库连接串。

    Returns:
        bool: 非空 True。
    """
    engine = _sync_engine(url)
    try:
        with engine.connect() as connection:
            columns = [item for item in inspect(connection).get_columns("mdm_dept") if item["name"] == "code"]
            return bool(columns) and columns[0]["nullable"] is False
    finally:
        engine.dispose()


def _insert_legacy_org_rows(url: str) -> None:
    """在 `0004` 结构上插入存量部门 / 岗位（`form_key` 回填验证用）。

    Args:
        url: 目标库连接串。
    """
    engine = _sync_engine(url)
    now = datetime(2026, 10, 20, tzinfo=UTC)
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO mdm_dept (id, code, ancestors, name, sort, status, created_at, updated_at, version)"
                    " VALUES (:dept_id, 'DEPT0001', '/', '存量部门', 0, 'enabled', :now, :now, 1)"
                ),
                {"dept_id": 9001, "now": now},
            )
            connection.execute(
                sa.text(
                    "INSERT INTO mdm_post (id, code, name, dept_id, sort, status, created_at, updated_at, version)"
                    " VALUES (:post_id, 'POST0001', '存量岗位', :dept_id, 0, 'enabled', :now, :now, 1)"
                ),
                {"post_id": 9101, "dept_id": 9001, "now": now},
            )
    finally:
        engine.dispose()


def _form_key_values(url: str, table: str) -> list[str]:
    """取表内 `form_key` 取值（回填核对）。

    Args:
        url: 目标库连接串。
        table: 物理表名（`mdm_dept` / `mdm_post`）。

    Returns:
        list[str]: `form_key` 取值列表。
    """
    engine = _sync_engine(url)
    try:
        with engine.connect() as connection:
            rows = connection.execute(sa.text(f"SELECT form_key FROM {table} ORDER BY id")).fetchall()
            return [str(row[0]) for row in rows]
    finally:
        engine.dispose()


def _post_parent_ids(url: str) -> list[int | None]:
    """取岗位 `parent_id` 取值（非层级字典应为空）。

    Args:
        url: 目标库连接串。

    Returns:
        list[int | None]: `parent_id` 取值列表。
    """
    engine = _sync_engine(url)
    try:
        with engine.connect() as connection:
            rows = connection.execute(sa.text("SELECT parent_id FROM mdm_post ORDER BY id")).fetchall()
            return [row[0] for row in rows]
    finally:
        engine.dispose()
