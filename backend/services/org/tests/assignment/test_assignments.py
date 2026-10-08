"""分配服务用例（Kiwi 2255）：用户-岗位全量覆盖（diff）/ 上限 / 解绑 / 用户删除清理；角色两向分配。

用例侧注意：**失败调用会回滚事务并使已加载实例过期**，故各用例在首次失败调用前先把 id 取成普通整数。
"""

import pytest
from bms_core.models.outbox import SysOutbox
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mdm_org.errors import (
    OrgDeptNotFoundError,
    OrgPostNotFoundError,
    OrgRoleDeptNotFoundError,
    OrgRolePostNotFoundError,
    OrgUserPostLimitExceededError,
    OrgUserPostNotFoundError,
)
from tests_support import org_env


async def _seed(session: AsyncSession) -> tuple[int, int, int]:
    """造前置数据（部门 + 两岗位）。

    Args:
        session: 请求级会话。

    Returns:
        tuple[int, int, int]: （部门 id，岗位 1 id，岗位 2 id）。
    """
    uow = org_env.make_uow(session)
    outbox = org_env.make_outbox()
    depts = org_env.make_dept_service(session, uow, outbox)
    posts = org_env.make_post_service(session, uow, outbox)
    dept = await depts.create_dept(code="rd", name="研发中心", parent_id=None, sort=1)
    dept_id = dept.id
    await org_env.commit(session)
    post_a = await posts.create_post(code="dev", name="开发", dept_id=dept_id)
    post_a_id = post_a.id
    await org_env.commit(session)
    post_b = await posts.create_post(code="qa", name="测试", dept_id=dept_id)
    post_b_id = post_b.id
    await org_env.commit(session)
    return dept_id, post_a_id, post_b_id


@pytest.mark.kiwi_id(2255)
async def test_user_post_assign_diff_limit_unassign_and_purge() -> None:
    """用户-岗位：全量覆盖 diff 后增删、上限（330072）、解绑（330071）、用户删除清理幂等。"""
    session, engine = await org_env.make_session()
    try:
        dept_id, post_a, post_b = await _seed(session)
        uow = org_env.make_uow(session)
        outbox = org_env.make_outbox()
        service = org_env.make_user_post_service(session, uow, outbox, org_env.make_config(max_per_user=2))

        assert await service.assign_user_posts(user_id=2001, post_ids=org_env.ids(post_a, post_b)) == [
            post_a,
            post_b,
        ]
        await org_env.commit(session)

        assert await service.assign_user_posts(user_id=2001, post_ids=org_env.ids(post_b)) == [post_b]
        await org_env.commit(session)
        assert await service.list_user_posts(2001) == [post_b]
        await org_env.commit(session)

        posts = org_env.make_post_service(session, uow, outbox)
        post_c = await posts.create_post(code="ops", name="运维", dept_id=dept_id)
        post_c_id = post_c.id
        await org_env.commit(session)
        with pytest.raises(OrgUserPostLimitExceededError) as limit:
            await service.assign_user_posts(user_id=2002, post_ids=org_env.ids(post_a, post_b, post_c_id))
        assert limit.value.code == 330072
        await org_env.commit(session)

        with pytest.raises(OrgPostNotFoundError):
            await service.assign_user_posts(user_id=2003, post_ids=org_env.ids(post_a + 999999))
        await org_env.commit(session)

        with pytest.raises(OrgUserPostNotFoundError) as missing:
            await service.unassign_user_post(user_id=2001, post_id=post_a)
        assert missing.value.code == 330071
        await org_env.commit(session)

        await service.unassign_user_post(user_id=2001, post_id=post_b)
        await org_env.commit(session)
        assert await service.list_user_posts(2001) == []
        await org_env.commit(session)

        await service.assign_user_posts(user_id=2004, post_ids=org_env.ids(post_a))
        await org_env.commit(session)
        assert await service.purge_user(2004) == 1
        await org_env.commit(session)
        assert await service.purge_user(2004) == 0
        await org_env.commit(session)

        rows = (await session.execute(select(SysOutbox))).scalars().all()
        assert "org.user_post.changed" in {item.event_type for item in rows}
        await org_env.commit(session)
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2255)
async def test_role_post_and_role_dept_assign_and_unassign() -> None:
    """角色-岗位 / 角色-部门：全量覆盖 diff、解绑与不存在分支（330081 / 330091 / 330051）。"""
    session, engine = await org_env.make_session()
    try:
        dept_id, post_a, post_b = await _seed(session)
        uow = org_env.make_uow(session)
        outbox = org_env.make_outbox()
        role_posts = org_env.make_role_post_service(session, uow, outbox)
        role_depts = org_env.make_role_dept_service(session, uow, outbox)

        assert await role_posts.assign_role_posts(role_id=1001, post_ids=org_env.ids(post_a, post_b)) == [
            post_a,
            post_b,
        ]
        await org_env.commit(session)
        assert await role_posts.assign_role_posts(role_id=1001, post_ids=org_env.ids(post_a)) == [post_a]
        await org_env.commit(session)
        assert await role_posts.list_role_posts(1001) == [post_a]
        await org_env.commit(session)

        with pytest.raises(OrgRolePostNotFoundError) as missing_role_post:
            await role_posts.unassign_role_post(role_id=1001, post_id=post_b)
        assert missing_role_post.value.code == 330081
        await org_env.commit(session)

        with pytest.raises(OrgPostNotFoundError):
            await role_posts.assign_role_posts(role_id=1001, post_ids=org_env.ids(post_a + 999999))
        await org_env.commit(session)

        assert await role_depts.assign_role_depts(role_id=1001, dept_ids=org_env.ids(dept_id)) == [dept_id]
        await org_env.commit(session)
        assert await role_depts.list_role_depts(1001) == [dept_id]
        await org_env.commit(session)

        with pytest.raises(OrgDeptNotFoundError):
            await role_depts.assign_role_depts(role_id=1002, dept_ids=org_env.ids(dept_id + 999999))
        await org_env.commit(session)

        with pytest.raises(OrgRoleDeptNotFoundError) as missing_role_dept:
            await role_depts.unassign_role_dept(role_id=1002, dept_id=dept_id)
        assert missing_role_dept.value.code == 330091
        await org_env.commit(session)

        await role_depts.unassign_role_dept(role_id=1001, dept_id=dept_id)
        await org_env.commit(session)
        assert await role_depts.list_role_depts(1001) == []
        await org_env.commit(session)

        rows = (await session.execute(select(SysOutbox))).scalars().all()
        event_types = {item.event_type for item in rows}
        assert "org.role_post.changed" in event_types
        assert "org.role_dept.changed" in event_types
        await org_env.commit(session)
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2255)
async def test_dept_subtree_users_aggregation() -> None:
    """部门（含子树）归属用户聚合：子树岗位下的用户去重汇总。"""
    session, engine = await org_env.make_session()
    try:
        dept_id, post_a, _post_b = await _seed(session)
        uow = org_env.make_uow(session)
        outbox = org_env.make_outbox()
        depts = org_env.make_dept_service(session, uow, outbox)
        posts = org_env.make_post_service(session, uow, outbox)
        user_posts = org_env.make_user_post_service(session, uow, outbox)

        sub = await depts.create_dept(code="rd-platform", name="平台组", parent_id=dept_id, sort=1)
        sub_id = sub.id
        await org_env.commit(session)
        sub_post = await posts.create_post(code="infra", name="基础架构", dept_id=sub_id)
        sub_post_id = sub_post.id
        await org_env.commit(session)
        await user_posts.assign_user_posts(user_id=3001, post_ids=org_env.ids(post_a))
        await org_env.commit(session)
        await user_posts.assign_user_posts(user_id=3002, post_ids=org_env.ids(sub_post_id))
        await org_env.commit(session)

        users = await depts.list_subtree_users(dept_id)
        assert sorted(users) == [3001, 3002]
        await org_env.commit(session)
        roles = await depts.list_dept_roles(dept_id)
        assert roles == []
        await org_env.commit(session)
    finally:
        await engine.dispose()
