"""组织域仓储用例：批量 / 计数等**非主干路径**的查询口径（供规则引用与统计使用）。

口径：仓储层只做 SQL 组装与结果规整，断言点集中在「空入参短路」「不存在返回 0」「非空统计正确」。
"""

import pytest
from bms_core.core.concurrent import ConcurrentStableList

from mdm_org.repositories.dept import DeptRepository
from mdm_org.repositories.role_dept import RoleDeptRepository
from mdm_org.repositories.role_post import RolePostRepository
from mdm_org.repositories.user_dept import UserDeptRepository
from mdm_org.repositories.user_post import UserPostRepository
from tests_support import org_env


@pytest.mark.kiwi_id(2255)
async def test_dept_repository_batch_and_reference_counts() -> None:
    """部门仓储：批量取得空入参短路；引用计数在不存在时 0、存在时含自身与子树。"""
    session, engine = await org_env.make_session()
    try:
        key = await org_env.seed_org_tree(session)
        depts = DeptRepository(session)

        assert list(await depts.list_by_ids(ConcurrentStableList())) == []
        assert await depts.count_referenced(999999) == 0
        assert await depts.count_referenced(key["root"]) == 2  # 研发中心 + 平台组
        await org_env.commit(session)
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2255)
async def test_user_dept_repository_dept_filters_and_counts() -> None:
    """用户-部门仓储：按部门 / 批量部门取关联、按用户与部门计数（空入参短路、无关联为 0）。"""
    session, engine = await org_env.make_session()
    try:
        key = await org_env.seed_org_tree(session)
        user_depts = UserDeptRepository(session)

        assert list(await user_depts.list_by_dept(key["root"])) == []
        assert list(await user_depts.list_by_depts(ConcurrentStableList())) == []
        assert await user_depts.count_by_user(2001) == 0
        assert await user_depts.count_by_dept(key["root"]) == 0
        await org_env.commit(session)

        service = org_env.make_user_dept_service(session, org_env.make_uow(session), org_env.make_outbox())
        await service.assign_user_depts(user_id=2001, dept_ids=ConcurrentStableList([key["root"]]))
        await org_env.commit(session)

        assert [link.dept_id for link in await user_depts.list_by_dept(key["root"])] == [key["root"]]
        assert [link.dept_id for link in await user_depts.list_by_depts(ConcurrentStableList([key["root"]]))] == [
            key["root"]
        ]
        assert await user_depts.count_by_user(2001) == 1
        assert await user_depts.count_by_dept(key["root"]) == 1
        await org_env.commit(session)
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2255)
async def test_role_and_user_post_repository_flush_and_counts() -> None:
    """角色-岗位/角色-部门仓储刷新与空入参短路；用户-岗位仓储按用户计数。"""
    session, engine = await org_env.make_session()
    try:
        await org_env.seed_org_tree(session)
        role_posts = RolePostRepository(session)
        role_depts = RoleDeptRepository(session)
        user_posts = UserPostRepository(session)

        await role_posts.flush()
        await role_depts.flush()
        assert list(await role_posts.list_by_posts(ConcurrentStableList())) == []
        assert await user_posts.count_by_user(2001) == 1
        await org_env.commit(session)
    finally:
        await engine.dispose()
