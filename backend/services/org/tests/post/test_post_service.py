"""岗位服务用例（Kiwi 2255）：CRUD / 编码唯一与格式 / 归属部门校验 / 删除引用 / 乐观锁 / 分页。

用例侧注意：**失败调用会回滚事务并使已加载实例过期**，故各用例在首次失败调用前先把 id 取成普通整数。
"""

import pytest
from bms_core.core.exceptions import ConcurrentConflictError
from bms_core.schemas.pagination import BasePageQuery
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from mdm_org.errors import (
    OrgPostCodeExistsError,
    OrgPostCodeFormatError,
    OrgPostDeptUnavailableError,
    OrgPostHasRolesError,
    OrgPostHasUsersError,
    OrgPostNotFoundError,
)
from mdm_org.services.dept import DeptService
from mdm_org.services.post import PostService
from mdm_org.services.role_post import RolePostService
from tests_support import org_env


async def _env(
    *, post_pattern: str | None = None
) -> tuple[AsyncSession, PostService, DeptService, RolePostService, AsyncEngine]:
    """建库并装配岗位服务（含部门 / 角色-岗位服务，便于造引用）。

    Args:
        post_pattern: 岗位码格式覆盖。

    Returns:
        tuple[AsyncSession, PostService, DeptService, RolePostService, AsyncEngine]:
            （会话，岗位服务，部门服务，角色-岗位服务，引擎）。
    """
    session, engine = await org_env.make_session()
    uow = org_env.make_uow(session)
    outbox = org_env.make_outbox()
    config = org_env.make_config(post_pattern=post_pattern)
    return (
        session,
        org_env.make_post_service(session, uow, outbox, config),
        org_env.make_dept_service(session, uow, outbox),
        org_env.make_role_post_service(session, uow, outbox),
        engine,
    )


@pytest.mark.kiwi_id(2255)
async def test_post_create_unique_format_and_dept_guard() -> None:
    """新建岗位：归属部门须存在且启用（330033）、编码唯一（330032）、格式受约束（330036）。"""
    session, posts, depts, _role_posts, engine = await _env()
    try:
        dept = await depts.create_dept(name="研发中心", parent_id=None, sort=1)
        dept_id = dept.id
        await org_env.commit(session)

        post = await posts.create_post(code="dev_lead", name="开发主管", dept_id=dept_id, sort=1)
        assert post.code == "dev_lead" and post.status == "enabled"
        await org_env.commit(session)

        with pytest.raises(OrgPostCodeExistsError) as dup:
            await posts.create_post(code="dev_lead", name="重复", dept_id=dept_id)
        assert dup.value.code == 330032
        await org_env.commit(session)

        with pytest.raises(OrgPostCodeFormatError) as bad_format:
            await posts.create_post(code="1bad-code", name="格式非法", dept_id=dept_id)
        assert bad_format.value.code == 330036
        await org_env.commit(session)

        with pytest.raises(OrgPostDeptUnavailableError) as unavailable:
            await posts.create_post(code="ops", name="运维", dept_id=dept_id + 999999)
        assert unavailable.value.code == 330033
        await org_env.commit(session)

        await depts.update_dept(dept_id=dept_id, status="disabled")
        await org_env.commit(session)
        with pytest.raises(OrgPostDeptUnavailableError):
            await posts.create_post(code="ops", name="运维", dept_id=dept_id)
        await org_env.commit(session)
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2255)
async def test_post_update_version_conflict_and_list() -> None:
    """修改岗位：乐观锁冲突转统一并发冲突；列表分页与筛选可用。"""
    session, posts, depts, _role_posts, engine = await _env()
    try:
        dept = await depts.create_dept(name="研发中心", parent_id=None, sort=1)
        dept_id = dept.id
        await org_env.commit(session)
        post = await posts.create_post(code="dev", name="开发", dept_id=dept_id)
        post_id = post.id
        version = post.version
        await org_env.commit(session)

        updated = await posts.update_post(post_id=post_id, name="开发工程师", version=version)
        assert updated.name == "开发工程师"
        await org_env.commit(session)

        with pytest.raises(ConcurrentConflictError):
            await posts.update_post(post_id=post_id, name="过期版本", version=version)
        await org_env.commit(session)

        with pytest.raises(OrgPostNotFoundError) as missing:
            await posts.update_post(post_id=post_id + 999999, name="不存在")
        assert missing.value.code == 330031
        await org_env.commit(session)

        rows, total = await posts.list_posts(BasePageQuery(page=1, size=10), dept_id=dept_id, keyword="开发")
        assert total == 1 and rows[0].name == "开发工程师"
        await org_env.commit(session)
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2255)
async def test_post_delete_reference_checks() -> None:
    """删除岗位：仍关联用户（330034）/ 仍绑定角色（330035）时拒绝；无引用时软删除。"""
    session, posts, depts, role_posts, engine = await _env()
    uow = org_env.make_uow(session)
    outbox = org_env.make_outbox()
    try:
        dept = await depts.create_dept(name="研发中心", parent_id=None, sort=1)
        dept_id = dept.id
        await org_env.commit(session)
        post = await posts.create_post(code="dev", name="开发", dept_id=dept_id)
        post_id = post.id
        await org_env.commit(session)
        free_post = await posts.create_post(code="qa", name="测试", dept_id=dept_id)
        free_post_id = free_post.id
        await org_env.commit(session)

        user_posts = org_env.make_user_post_service(session, uow, outbox)
        await user_posts.assign_user_posts(user_id=2001, post_ids=org_env.ids(post_id))
        await org_env.commit(session)
        with pytest.raises(OrgPostHasUsersError) as has_users:
            await posts.delete_post(post_id=post_id)
        assert has_users.value.code == 330034
        await org_env.commit(session)

        await role_posts.assign_role_posts(role_id=1001, post_ids=org_env.ids(free_post_id))
        await org_env.commit(session)
        with pytest.raises(OrgPostHasRolesError) as has_roles:
            await posts.delete_post(post_id=free_post_id)
        assert has_roles.value.code == 330035
        await org_env.commit(session)

        await user_posts.purge_user(2001)
        await org_env.commit(session)
        await posts.delete_post(post_id=post_id)
        await org_env.commit(session)
        with pytest.raises(OrgPostNotFoundError):
            await posts.require_post(post_id)
        await org_env.commit(session)

        assert await posts.list_post_users(free_post_id) == []
        assert await posts.list_post_roles(free_post_id) == [1001]
        await org_env.commit(session)
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2255)
async def test_post_code_pattern_from_config() -> None:
    """岗位码格式经 `org.post_code_pattern` 读取（覆盖默认正则）。"""
    session, posts, depts, _role_posts, engine = await _env(post_pattern=r"^P-[0-9]{3}$")
    try:
        dept = await depts.create_dept(name="研发中心", parent_id=None, sort=1)
        dept_id = dept.id
        await org_env.commit(session)
        post = await posts.create_post(code="P-001", name="开发", dept_id=dept_id)
        assert post.code == "P-001"
        await org_env.commit(session)
        with pytest.raises(OrgPostCodeFormatError):
            await posts.create_post(code="dev", name="不符合配置格式", dept_id=dept_id)
        await org_env.commit(session)
    finally:
        await engine.dispose()
