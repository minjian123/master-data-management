"""用户-部门多分配与主要项用例（Kiwi 2272）：全量覆盖 diff / 主要项互斥置位 / 上限 / 解绑（含主要项清空）/ 事件。

用例侧注意：**失败调用会回滚事务并使已加载实例过期**，故各用例在首次失败调用前先把 id 取成普通整数。
"""

import pytest
from bms_core.models.outbox import SysOutbox
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mdm_org.errors import (
    OrgDeptNotFoundError,
    OrgUserDeptLimitExceededError,
    OrgUserDeptNotFoundError,
    OrgUserPrimaryNotAssignedError,
)
from tests_support import org_env


async def _seed(session: AsyncSession) -> tuple[int, int, int, int, int]:
    """造前置数据（三个部门 + 两个岗位）。

    Args:
        session: 请求级会话。

    Returns:
        tuple[int, int, int, int, int]: （部门 1、部门 2、部门 3、岗位 1、岗位 2）id。
    """
    uow = org_env.make_uow(session)
    outbox = org_env.make_outbox()
    depts = org_env.make_dept_service(session, uow, outbox)
    posts = org_env.make_post_service(session, uow, outbox)

    dept_a = await depts.create_dept(code="rd", name="研发中心", parent_id=None, sort=1)
    dept_a_id = dept_a.id
    await org_env.commit(session)
    dept_b = await depts.create_dept(code="qa", name="质量中心", parent_id=None, sort=2)
    dept_b_id = dept_b.id
    await org_env.commit(session)
    dept_c = await depts.create_dept(code="ops", name="运维中心", parent_id=None, sort=3)
    dept_c_id = dept_c.id
    await org_env.commit(session)

    post_a = await posts.create_post(code="dev", name="开发", dept_id=dept_a_id)
    post_a_id = post_a.id
    await org_env.commit(session)
    post_b = await posts.create_post(code="qe", name="测试", dept_id=dept_a_id)
    post_b_id = post_b.id
    await org_env.commit(session)
    return dept_a_id, dept_b_id, dept_c_id, post_a_id, post_b_id


@pytest.mark.kiwi_id(2272)
async def test_user_dept_assign_diff_limit_unassign_and_purge() -> None:
    """用户-部门：全量覆盖 diff、被移除主要项同事务清空、上限（330112）、不存在（330051 / 330111）、清理幂等。"""
    session, engine = await org_env.make_session()
    try:
        dept_a, dept_b, _dept_c, _post_a, _post_b = await _seed(session)
        uow = org_env.make_uow(session)
        outbox = org_env.make_outbox()
        service = org_env.make_user_dept_service(
            session, uow, outbox, org_env.make_config(max_per_user=2, dept_max_per_user=2)
        )

        assert await service.assign_user_depts(user_id=2101, dept_ids=org_env.ids(dept_a, dept_b)) == [dept_a, dept_b]
        await org_env.commit(session)
        assert await service.list_user_depts(2101) == [dept_a, dept_b]
        await org_env.commit(session)

        # 置位主要部门 → 全量覆盖移除该项 ⇒ 主要项同事务清空（不留悬空）
        await service.set_primary_dept(user_id=2101, dept_id=dept_b)
        await org_env.commit(session)
        assert await service.primary_dept_id(2101) == dept_b
        await org_env.commit(session)

        assert await service.assign_user_depts(user_id=2101, dept_ids=org_env.ids(dept_a)) == [dept_a]
        await org_env.commit(session)
        assert await service.primary_dept_id(2101) is None
        await org_env.commit(session)

        with pytest.raises(OrgUserDeptLimitExceededError) as limit:
            await service.assign_user_depts(user_id=2102, dept_ids=org_env.ids(dept_a, dept_b, _dept_c))
        assert limit.value.code == 330112
        await org_env.commit(session)

        with pytest.raises(OrgDeptNotFoundError):
            await service.assign_user_depts(user_id=2103, dept_ids=org_env.ids(dept_a + 999999))
        await org_env.commit(session)

        with pytest.raises(OrgUserDeptNotFoundError) as missing:
            await service.unassign_user_dept(user_id=2101, dept_id=dept_b)
        assert missing.value.code == 330111
        await org_env.commit(session)

        # 解绑存在项（其为主要项 ⇒ 标记一并清空）
        await service.assign_user_depts(user_id=2101, dept_ids=org_env.ids(dept_a, dept_b))
        await org_env.commit(session)
        await service.set_primary_dept(user_id=2101, dept_id=dept_a)
        await org_env.commit(session)
        await service.unassign_user_dept(user_id=2101, dept_id=dept_a)
        await org_env.commit(session)
        assert await service.list_user_depts(2101) == [dept_b]
        await org_env.commit(session)
        assert await service.primary_dept_id(2101) is None
        await org_env.commit(session)

        assert await service.purge_user(2101) == 1
        await org_env.commit(session)
        assert await service.purge_user(2101) == 0
        await org_env.commit(session)

        rows = (await session.execute(select(SysOutbox))).scalars().all()
        assert "org.user_dept.changed" in {item.event_type for item in rows}
        await org_env.commit(session)
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2272)
async def test_user_dept_primary_mutex_clear_and_invalid_target() -> None:
    """主要部门：互斥置位（置位 B 后 A 自动取消）、重复置位幂等、清除（`None`）、跨用户隔离、未分配项 330113。"""
    session, engine = await org_env.make_session()
    try:
        dept_a, dept_b, dept_c, _post_a, _post_b = await _seed(session)
        uow = org_env.make_uow(session)
        outbox = org_env.make_outbox()
        service = org_env.make_user_dept_service(session, uow, outbox)

        await service.assign_user_depts(user_id=2201, dept_ids=org_env.ids(dept_a, dept_b))
        await org_env.commit(session)

        await service.set_primary_dept(user_id=2201, dept_id=dept_a)
        await org_env.commit(session)
        assert await service.primary_dept_id(2201) == dept_a
        await org_env.commit(session)

        # 互斥：置位 dept_b ⇒ dept_a 自动取消（同事务先清后置）
        await service.set_primary_dept(user_id=2201, dept_id=dept_b)
        await org_env.commit(session)
        assert await service.primary_dept_id(2201) == dept_b
        await org_env.commit(session)

        # 重复置位同一项：幂等
        await service.set_primary_dept(user_id=2201, dept_id=dept_b)
        await org_env.commit(session)
        assert await service.primary_dept_id(2201) == dept_b
        await org_env.commit(session)

        # 清除（`None`）与再次清除（无主要项时幂等）
        await service.set_primary_dept(user_id=2201, dept_id=None)
        await org_env.commit(session)
        assert await service.primary_dept_id(2201) is None
        await org_env.commit(session)
        await service.set_primary_dept(user_id=2201, dept_id=None)
        await org_env.commit(session)
        assert await service.primary_dept_id(2201) is None
        await org_env.commit(session)

        # 跨用户隔离
        await service.assign_user_depts(user_id=2202, dept_ids=org_env.ids(dept_a))
        await org_env.commit(session)
        await service.set_primary_dept(user_id=2202, dept_id=dept_a)
        await org_env.commit(session)
        assert await service.primary_dept_id(2202) == dept_a
        await org_env.commit(session)
        assert await service.primary_dept_id(2201) is None
        await org_env.commit(session)

        # 置位未分配项 ⇒ 330113
        with pytest.raises(OrgUserPrimaryNotAssignedError) as invalid:
            await service.set_primary_dept(user_id=2201, dept_id=dept_c)
        assert invalid.value.code == 330113
        await org_env.commit(session)
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2272)
async def test_user_post_primary_set_and_clear_on_removal() -> None:
    """主要岗位：置位 / 切换 / 清除（`None`）、移除主要项时标记同事务清空、未分配项 330113。"""
    session, engine = await org_env.make_session()
    try:
        _dept_a, _dept_b, _dept_c, post_a, post_b = await _seed(session)
        uow = org_env.make_uow(session)
        outbox = org_env.make_outbox()
        service = org_env.make_user_post_service(session, uow, outbox)

        await service.assign_user_posts(user_id=2301, post_ids=org_env.ids(post_a, post_b))
        await org_env.commit(session)

        await service.set_primary_post(user_id=2301, post_id=post_a)
        await org_env.commit(session)
        assert await service.primary_post_id(2301) == post_a
        await org_env.commit(session)

        # 互斥切换
        await service.set_primary_post(user_id=2301, post_id=post_b)
        await org_env.commit(session)
        assert await service.primary_post_id(2301) == post_b
        await org_env.commit(session)

        # 清除
        await service.set_primary_post(user_id=2301, post_id=None)
        await org_env.commit(session)
        assert await service.primary_post_id(2301) is None
        await org_env.commit(session)

        # 移除主要项 ⇒ 标记清空
        await service.set_primary_post(user_id=2301, post_id=post_a)
        await org_env.commit(session)
        await service.assign_user_posts(user_id=2301, post_ids=org_env.ids(post_b))
        await org_env.commit(session)
        assert await service.primary_post_id(2301) is None
        await org_env.commit(session)

        # 置位未分配项（已被移除）⇒ 330113
        with pytest.raises(OrgUserPrimaryNotAssignedError) as invalid:
            await service.set_primary_post(user_id=2301, post_id=post_a)
        assert invalid.value.code == 330113
        await org_env.commit(session)

        rows = (await session.execute(select(SysOutbox))).scalars().all()
        assert "org.user_post.changed" in {item.event_type for item in rows}
        await org_env.commit(session)
    finally:
        await engine.dispose()
