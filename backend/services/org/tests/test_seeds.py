"""mdm 默认数据种子（07B `02_03` 真实播种）：业务码 `mdm` + 4 条权限码。

**断言面**：入口签名符合基座分支处理器范式（`async def entry(session, args) -> None`）；
按自然键幂等（业务码按 `code`、权限码按 `(business_id, action_id)`）；
业务码已存在且名称不同 → 抛 `ParamError`；动作码未登记 → 抛 `ParamError`；
`expected_rows()` 为纯函数（供平台编排器事务前冲突预检）。

新建用例的 Kiwi 编号由 07B `05_01` 统一登记后回填。
"""

from pathlib import Path
from typing import cast

import pytest
from bms_core.core.concurrent import ConcurrentStableDict, ConcurrentStableFrozenDict
from bms_core.core.exceptions import ParamError
from bms_core.models.base import Base
from bms_core.models.platform.permission_meta import SysAction, SysBusiness, SysPermission
from bms_core.tenant.seed.contract import ExpectedRow
from sqlalchemy import Table, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mdm.seeds import seed_admin_codes
from mdm.seeds.permissions import BUSINESS_CODE, BUSINESS_NAME, PERMISSION_ACTIONS, expected_rows

_TABLES: list[Table] = [
    cast("Table", SysBusiness.__table__),
    cast("Table", SysAction.__table__),
    cast("Table", SysPermission.__table__),
]
"""种子涉及的表（`sys_business` / `sys_permission` / `sys_action`，归平台服务库）。"""


async def _session(tmp_path: Path, *, with_actions: bool = True) -> tuple[AsyncSession, object]:
    """建库并返回会话与引擎。

    Args:
        tmp_path: 临时目录。
        with_actions: 是否预置动作码（`query` / `create` / `update` / `delete`）。

    Returns:
        tuple[AsyncSession, object]: （会话, 引擎）。
    """
    url = f"sqlite+aiosqlite:///{tmp_path / 'platform.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as connection:
        await connection.run_sync(lambda conn: Base.metadata.create_all(conn, tables=_TABLES))
    if with_actions:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as seed_session:
            for code in PERMISSION_ACTIONS:
                seed_session.add(SysAction(code=code, name=code))
            await seed_session.commit()
    return async_sessionmaker(engine, expire_on_commit=False)(), engine


async def _count(session: AsyncSession, model: object) -> int:
    """统计表行数。

    Args:
        session: 会话。
        model: ORM 模型。

    Returns:
        int: 行数。
    """
    table = cast("Table", model.__table__)  # type: ignore[attr-defined]
    return len((await session.execute(select(table))).all())


def test_expected_rows_is_pure_function() -> None:
    """`expected_rows()` 返回业务码期望行，连续两次调用一致（纯函数，不连库）。"""
    first = expected_rows()
    second = expected_rows()
    assert list(first) == list(second)
    assert len(first) == 1
    row: ExpectedRow = first[0]
    assert row.table == "sys_business"
    assert row.key == ConcurrentStableFrozenDict({"code": BUSINESS_CODE})
    assert row.values == ConcurrentStableFrozenDict({"name": BUSINESS_NAME})


async def test_seed_admin_codes_writes_business_and_permissions(tmp_path: Path) -> None:
    """首次播种：写业务码 `mdm` + 4 条权限码。"""
    session, engine = await _session(tmp_path)
    try:
        await seed_admin_codes(session, ConcurrentStableDict())
        await session.commit()
        assert await _count(session, SysBusiness) == 1
        assert await _count(session, SysPermission) == len(PERMISSION_ACTIONS)
        business = (await session.execute(select(SysBusiness))).scalar_one()
        assert business.code == BUSINESS_CODE
        assert business.name == BUSINESS_NAME
    finally:
        await session.close()
        await engine.dispose()  # type: ignore[attr-defined]


async def test_seed_admin_codes_is_idempotent(tmp_path: Path) -> None:
    """重复执行幂等：业务码与权限码均不重复写入。"""
    session, engine = await _session(tmp_path)
    try:
        await seed_admin_codes(session, ConcurrentStableDict())
        await session.commit()
        permissions = await _count(session, SysPermission)
        await seed_admin_codes(session, ConcurrentStableDict())
        await session.commit()
        assert await _count(session, SysBusiness) == 1
        assert await _count(session, SysPermission) == permissions
    finally:
        await session.close()
        await engine.dispose()  # type: ignore[attr-defined]


async def test_seed_admin_codes_rejects_conflicting_business_name(tmp_path: Path) -> None:
    """业务码已存在且名称不同 → `ParamError`（声明与库中数据不一致，不静默覆盖）。"""
    session, engine = await _session(tmp_path)
    try:
        session.add(SysBusiness(code=BUSINESS_CODE, name="被改过的名字", status="enabled"))
        await session.commit()
        with pytest.raises(ParamError, match="已存在且名称不同"):
            await seed_admin_codes(session, ConcurrentStableDict())
    finally:
        await session.close()
        await engine.dispose()  # type: ignore[attr-defined]


async def test_seed_admin_codes_requires_registered_actions(tmp_path: Path) -> None:
    """动作码未登记 → `ParamError`（须先在平台登记动词）。"""
    session, engine = await _session(tmp_path, with_actions=False)
    try:
        with pytest.raises(ParamError, match="动作码未登记"):
            await seed_admin_codes(session, ConcurrentStableDict())
    finally:
        await session.close()
        await engine.dispose()  # type: ignore[attr-defined]


async def test_seed_admin_codes_skips_existing_permissions(tmp_path: Path) -> None:
    """既有权限码行存在 → 跳过（不重复插入、不报错）。"""
    session, engine = await _session(tmp_path)
    try:
        await seed_admin_codes(session, ConcurrentStableDict())
        await session.commit()
        before = await _count(session, SysPermission)
        await seed_admin_codes(session, ConcurrentStableDict())
        await session.commit()
        assert await _count(session, SysPermission) == before
    finally:
        await session.close()
        await engine.dispose()  # type: ignore[attr-defined]
