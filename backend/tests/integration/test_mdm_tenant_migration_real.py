"""mdm:tenant 真库迁移用例（PostgreSQL / 达梦；标记 `integration`，Kiwi 2431）。

- **环境守卫**：`MDM_TEST_PG_URL` / `MDM_TEST_DM_URL` 未配置即跳过，不阻塞默认用例；
- **对象生命周期**：库 / 模式由执行脚本创建（`mdm_migrcheck_pg` / `MDM_MIGRCHECK`），
  用例只建删该对象内的表，不触碰 `mdm` / `mdm_demo` / `mdm_acme`；
- **零漂移**：PostgreSQL 用 Alembic `compare_metadata`（含基础设施表、排除版本表）；
  达梦的标识符按大写折叠，且 dmSQLAlchemy 的 autogenerate 反射路径有缺陷，故改为
  **结构快照比对**（表 / 列 / 可空 / 类型 / 索引 / 主键，类型按达梦同义词归一）；
- **幂等**：连续迁移两次，第二次仍停在 head（`ops.migrate` 的「已是最新」判据同源）。
"""

# ruff: noqa: I001  # `mdm` 必须先于 bms_core 导入（工程根覆盖），与 isort 分组冲突

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from typing import Any

import mdm  # noqa: F401  # 钉定工程根（必须先于 bms_core 导入）
import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from bms_core.db.migration import head_revision, resolve_series, series_metadata, upgrade_series
from bms_core.models.base import BaseModel
from sqlalchemy import Engine, inspect

from services.table_registry import register

_SERIES = "mdm:tenant"
_MDM_TABLES = ("mdm_dept", "mdm_post", "mdm_user_post", "mdm_user_dept", "mdm_role_post", "mdm_role_dept")
_INFRA_TABLES = ("sys_outbox", "sys_event_consumed", "sys_event_dead_letter")
_VERSION_TABLE = "alembic_version_mdm"
_PG_URL_ENV = "MDM_TEST_PG_URL"
_DM_URL_ENV = "MDM_TEST_DM_URL"
_DM_SCHEMA_ENV = "MDM_TEST_DM_SCHEMA"
_DEFAULT_DM_SCHEMA = "MDM_MIGRCHECK"

pytestmark = [pytest.mark.integration, pytest.mark.kiwi_id(2431)]

if sys.platform == "win32":  # psycopg 异步不支持 Proactor（本地 Windows 演练用）
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@dataclass(frozen=True)
class _Target:
    """真库目标（方言 / 连接串 / 模式）。

    Args:
        dialect: `postgres` 或 `dm8`。
        url: 连接串。
        schema: 达梦模式名（其他方言为空串）。
    """

    dialect: str
    url: str
    schema: str = ""


@pytest.fixture(params=["postgres", "dm8"])
def target(request: pytest.FixtureRequest) -> _Target:
    """真库目标（未配置环境变量即跳过）。

    Args:
        request: pytest 参数夹具。

    Returns:
        _Target: 目标连接信息。
    """
    if request.param == "postgres":
        url = os.environ.get(_PG_URL_ENV, "")
        if not url:
            pytest.skip(f"未配置 {_PG_URL_ENV}，跳过 PostgreSQL 真库迁移用例")
        return _Target(dialect="postgres", url=url)
    url = os.environ.get(_DM_URL_ENV, "")
    if not url:
        pytest.skip(f"未配置 {_DM_URL_ENV}，跳过达梦真库迁移用例")
    return _Target(dialect="dm8", url=url, schema=os.environ.get(_DM_SCHEMA_ENV, _DEFAULT_DM_SCHEMA))


def _engine(target: _Target) -> Engine:
    """构造目标同步引擎（达梦驱动本身为同步方言）。

    Args:
        target: 真库目标。

    Returns:
        Engine: 同步引擎（调用方负责 dispose）。
    """
    return sa.create_engine(target.url, isolation_level="AUTOCOMMIT")


def _tables(target: _Target) -> set[str]:
    """取目标对象内的表名集合（统一小写）。

    Args:
        target: 真库目标。

    Returns:
        set[str]: 表名集合。
    """
    engine = _engine(target)
    try:
        with engine.connect() as connection:
            names = inspect(connection).get_table_names(schema=target.schema or None)
    finally:
        engine.dispose()
    return {str(name).lower() for name in names}


def _columns(target: _Target, table: str) -> set[str]:
    """取指定表的列名集合（统一小写）。

    Args:
        target: 真库目标。
        table: 表名。

    Returns:
        set[str]: 列名集合。
    """
    engine = _engine(target)
    try:
        with engine.connect() as connection:
            columns = inspect(connection).get_columns(table, schema=target.schema or None)
    finally:
        engine.dispose()
    return {str(column["name"]).lower() for column in columns}


def _cleanup(target: _Target) -> None:
    """删除目标对象内的 mdm 表（幂等；按外键依赖倒序）。

    Args:
        target: 真库目标。
    """
    order = ("mdm_user_post", "mdm_role_post", "mdm_role_dept", "mdm_user_dept", "mdm_post", "mdm_dept")
    engine = _engine(target)
    try:
        with engine.connect() as connection:
            for table in (*order, *_INFRA_TABLES, _VERSION_TABLE):
                if target.dialect == "dm8":
                    statement = f"DROP TABLE {target.schema}.{table.upper()} CASCADE CONSTRAINTS"
                else:
                    statement = f'DROP TABLE IF EXISTS "{table}" CASCADE'
                try:
                    connection.exec_driver_sql(statement)
                except sa.exc.DatabaseError:
                    continue  # 表 / 模式不存在即跳过（幂等清理）
    finally:
        engine.dispose()


def _current_revision(target: _Target) -> str | None:
    """读版本记录表当前修订（未迁移返回 None）。

    Args:
        target: 真库目标。

    Returns:
        str | None: 当前修订号。
    """
    engine = _engine(target)
    try:
        with engine.connect() as connection:
            if target.dialect == "dm8":
                connection.exec_driver_sql(f"SET SCHEMA {target.schema}")
            try:
                row = connection.exec_driver_sql(f"SELECT version_num FROM {_VERSION_TABLE}").first()
            except sa.exc.DatabaseError:
                return None
            return None if row is None else str(row[0])
    finally:
        engine.dispose()


def _combined_metadata() -> sa.MetaData:
    """构造比对用元数据（域六表 + 基础设施三表）。

    Returns:
        sa.MetaData: 合并后的元数据。
    """
    metadata = series_metadata(resolve_series(_SERIES))
    for name in _INFRA_TABLES:
        BaseModel.metadata.tables[name].to_metadata(metadata)
    return metadata


def _pg_diff(target: _Target) -> list[str]:
    """PostgreSQL 结构差异（Alembic `compare_metadata`；排除版本表）。

    Args:
        target: 真库目标。

    Returns:
        list[str]: 差异明细（空表示零漂移）。
    """
    engine = _engine(target)
    try:
        with engine.connect() as connection:
            connection.dialect.supports_comments = False  # 注释不计入结构漂移
            context = MigrationContext.configure(connection, opts={"compare_type": True})
            diffs = [str(item) for item in compare_metadata(context, _combined_metadata())]
    finally:
        engine.dispose()
    return [item for item in diffs if _VERSION_TABLE not in item]


def _type_key(type_: sa.types.TypeEngine[Any], dialect: sa.Dialect) -> str:
    """类型签名（达梦同义词归一后比较）。

    Args:
        type_: 列类型。
        dialect: 目标方言。

    Returns:
        str: 归一后的类型签名。
    """
    text = str(type_.compile(dialect=dialect)).lower()
    text = text.replace("varchar2", "varchar").replace("number", "decimal")
    return text.replace(" char)", ")").replace(" ", "")


def _dm_diff(target: _Target) -> list[str]:
    """达梦结构差异（表 / 列 / 可空 / 类型 / 索引 / 主键）。

    Args:
        target: 真库目标。

    Returns:
        list[str]: 差异明细（空表示零漂移）。
    """
    metadata = _combined_metadata()
    expected = {name.lower(): table for name, table in metadata.tables.items()}
    engine = _engine(target)
    diffs: list[str] = []
    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            actual_names = {str(name).lower() for name in inspector.get_table_names(schema=target.schema)}
            for name in sorted(set(expected) - actual_names):
                diffs.append(f"缺表：{name}")
            for name in sorted(actual_names - set(expected) - {_VERSION_TABLE}):
                diffs.append(f"多表：{name}")
            for name in sorted(set(expected) & actual_names):
                table = expected[name]
                columns = {
                    str(column["name"]).lower(): column for column in inspector.get_columns(name, schema=target.schema)
                }
                expected_columns = {column.name.lower(): column for column in table.columns}
                for column in sorted(set(expected_columns) - set(columns)):
                    diffs.append(f"{name} 缺列：{column}")
                for column in sorted(set(columns) - set(expected_columns)):
                    diffs.append(f"{name} 多列：{column}")
                for column in sorted(set(expected_columns) & set(columns)):
                    if bool(expected_columns[column].nullable) != bool(columns[column]["nullable"]):
                        diffs.append(f"{name}.{column} 可空不一致")
                    if _type_key(expected_columns[column].type, connection.dialect) != _type_key(
                        columns[column]["type"], connection.dialect
                    ):
                        diffs.append(f"{name}.{column} 类型不一致")
                expected_indexes = {index.name.lower() for index in table.indexes}
                actual_indexes = {
                    str(index["name"]).lower() for index in inspector.get_indexes(name, schema=target.schema)
                }
                for index in sorted(expected_indexes - actual_indexes):
                    diffs.append(f"{name} 缺索引：{index}")
                for index in sorted(actual_indexes - expected_indexes):
                    diffs.append(f"{name} 多索引：{index}")
                expected_pk = [column.name.lower() for column in table.primary_key.columns]
                actual_pk = [
                    str(column).lower()
                    for column in inspector.get_pk_constraint(name, schema=target.schema)["constrained_columns"]
                ]
                if expected_pk != actual_pk:
                    diffs.append(f"{name} 主键不一致：{expected_pk} != {actual_pk}")
    finally:
        engine.dispose()
    return diffs


def test_mdm_tenant_migration_on_real_database(target: _Target) -> None:
    """真库迁移：升到 head、九表齐备、结构零漂移、二次迁移幂等。"""
    register()
    series = resolve_series(_SERIES)
    head = head_revision(series)
    assert head == "0006_outbox_trace_id"

    _cleanup(target)
    upgrade_series(series, target.url, schema=target.schema)

    assert _current_revision(target) == head
    assert set(_MDM_TABLES + _INFRA_TABLES) <= _tables(target)
    assert "trace_id" in _columns(target, "sys_outbox")
    if target.dialect == "postgres":
        assert _pg_diff(target) == []
    else:
        assert _dm_diff(target) == []

    upgrade_series(series, target.url, schema=target.schema)
    assert _current_revision(target) == head


def test_mdm_tenant_migration_real_cleanup(target: _Target) -> None:
    """清理：删除用例对象内的表后可再次迁移（证明清理幂等、可重复执行）。"""
    register()
    series = resolve_series(_SERIES)
    _cleanup(target)
    assert not (set(_MDM_TABLES) & _tables(target))
    upgrade_series(series, target.url, schema=target.schema)
    assert set(_MDM_TABLES) <= _tables(target)
