"""分配语义补充用例：重复入参去重、全量覆盖缩小（解绑）与主要项清空。

口径：这三类都是**正常业务路径**（前端重复提交 / 权限调整后收回分配 / 取消主要项），
此前只覆盖了「新增与置位」，故单独成文件补齐。
"""

import pytest
from bms_core.core.concurrent import ConcurrentStableList
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from mdm.services.dept import DeptService
from mdm.services.role_dept import RoleDeptService
from mdm.services.role_post import RolePostService
from mdm.services.user_dept import UserDeptService
from mdm.services.user_post import UserPostService
from tests_support import org_env


async def _env() -> tuple[
    AsyncSession,
    DeptService,
    UserPostService,
    UserDeptService,
    RolePostService,
    RoleDeptService,
    AsyncEngine,
]:
    """装配部门与四类分配服务。

    Returns:
        tuple: （会话，部门服务，用户-岗位，用户-部门，角色-岗位，角色-部门，引擎）。
    """
    session, engine = await org_env.make_session()
    uow = org_env.make_uow(session)
    outbox = org_env.make_outbox()
    config = org_env.make_config()
    return (
        session,
        org_env.make_dept_service(session, uow, outbox, config),
        org_env.make_user_post_service(session, uow, outbox, config),
        org_env.make_user_dept_service(session, uow, outbox, config),
        org_env.make_role_post_service(session, uow, outbox),
        org_env.make_role_dept_service(session, uow, outbox),
        engine,
    )


@pytest.mark.kiwi_id(2255)
async def test_duplicate_ids_are_deduped_on_assign() -> None:
    """重复入参：四类分配均按「保序去重」处理，落库不产生重复关联。"""
    session, depts, user_posts, user_depts, role_posts, role_depts, engine = await _env()
    try:
        dept = await depts.create_dept(code="rd", name="研发中心", parent_id=None, sort=1)
        dept_id = dept.id
        await org_env.commit(session)
        post = await org_env.make_post_service(session, org_env.make_uow(session), org_env.make_outbox()).create_post(
            code="dev", name="开发岗", dept_id=dept_id, sort=1
        )
        post_id = post.id
        await org_env.commit(session)

        duplicates = ConcurrentStableList([post_id, post_id])
        assert await user_posts.assign_user_posts(user_id=2201, post_ids=duplicates) == [post_id]
        await org_env.commit(session)
        assert await user_posts.assign_user_posts(user_id=2201, post_ids=duplicates) == [post_id]
        await org_env.commit(session)

        assert await user_depts.assign_user_depts(user_id=2201, dept_ids=ConcurrentStableList([dept_id, dept_id])) == [
            dept_id
        ]
        await org_env.commit(session)

        assert await role_posts.assign_role_posts(role_id=2201, post_ids=ConcurrentStableList([post_id, post_id])) == [
            post_id
        ]
        await org_env.commit(session)

        assert await role_depts.assign_role_depts(role_id=2201, dept_ids=ConcurrentStableList([dept_id, dept_id])) == [
            dept_id
        ]
        await org_env.commit(session)
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2255)
async def test_role_dept_cover_shrink_unassigns_removed() -> None:
    """全量覆盖缩小：被移除的角色-部门分配软删除并发布解绑事件。"""
    session, depts, _user_posts, _user_depts, _role_posts, role_depts, engine = await _env()
    try:
        first = await depts.create_dept(code="rd", name="研发中心", parent_id=None, sort=1)
        first_id = first.id
        await org_env.commit(session)
        second = await depts.create_dept(code="mkt", name="市场部", parent_id=None, sort=2)
        second_id = second.id
        await org_env.commit(session)

        await role_depts.assign_role_depts(role_id=2301, dept_ids=ConcurrentStableList([first_id, second_id]))
        await org_env.commit(session)
        assert await role_depts.assign_role_depts(role_id=2301, dept_ids=ConcurrentStableList([first_id])) == [first_id]
        await org_env.commit(session)
        assert await role_depts.list_role_depts(2301) == [first_id]
        await org_env.commit(session)
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2255)
async def test_clear_primary_when_absent_is_noop() -> None:
    """清空主要项但当前没有主要项：直接返回，不产生事件与写入。"""
    session, depts, user_posts, _user_depts, _role_posts, _role_depts, engine = await _env()
    try:
        dept = await depts.create_dept(code="rd", name="研发中心", parent_id=None, sort=1)
        post = await org_env.make_post_service(session, org_env.make_uow(session), org_env.make_outbox()).create_post(
            code="dev", name="开发岗", dept_id=dept.id, sort=1
        )
        await org_env.commit(session)

        await user_posts.assign_user_posts(user_id=2401, post_ids=ConcurrentStableList([post.id]))
        await org_env.commit(session)
        await user_posts.set_primary_post(user_id=2401, post_id=None)
        await org_env.commit(session)
        assert await user_posts.primary_post_id(2401) is None
        await org_env.commit(session)
    finally:
        await engine.dispose()
