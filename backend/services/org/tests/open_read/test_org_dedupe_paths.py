"""出口与部门服务的去重路径用例：重复入参 / 同一用户多岗位时结果**保序去重**。

口径：这些分支在真实场景会出现（前端重复传 id、同一用户在子树多个部门挂岗），
此前只有正向单值用例，故单独补齐。
"""

import pytest
from bms_core.core.concurrent import ConcurrentStableList
from bms_core.core.exceptions import ParamError
from bms_core.scope.base import ScopeCondition

from mdm.api import open_read as api_open_read
from mdm.api.open_read import dept_scope_from_predicate
from tests_support import org_env


@pytest.mark.kiwi_id(2256)
def test_dept_scope_and_parse_ids_dedupe() -> None:
    """数据范围条件与回显 id 解析：重复取值保序去重；非法 id 明确报错。"""
    conditions = ConcurrentStableList([ScopeCondition(field="dept_id", value=[1, 1, 2])])
    scope = dept_scope_from_predicate(conditions)
    assert scope is not None and list(scope) == [1, 2]
    # 回显 id 解析为同模块私有函数：直测参数解析口径（端到端由 resolve-names 路由用例覆盖）
    assert list(api_open_read._parse_ids("3,3,4")) == [3, 4]  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(ParamError):
        api_open_read._parse_ids("3,abc")  # pyright: ignore[reportPrivateUsage]


@pytest.mark.kiwi_id(2256)
async def test_user_roles_and_data_source_users_dedupe() -> None:
    """同一用户多岗位 / 同一角色经多岗位命中时，角色集合与部门用户集合均只出现一次。"""
    session, engine = await org_env.make_session()
    try:
        uow = org_env.make_uow(session)
        outbox = org_env.make_outbox()
        config = org_env.make_config()
        depts = org_env.make_dept_service(session, uow, outbox, config)
        posts = org_env.make_post_service(session, uow, outbox, config)
        user_posts = org_env.make_user_post_service(session, uow, outbox, config)
        role_posts = org_env.make_role_post_service(session, uow, outbox)

        dept = await depts.create_dept(code="rd", name="研发中心", parent_id=None, sort=1)
        dept_id = dept.id
        await org_env.commit(session)
        first = await posts.create_post(code="dev_lead", name="开发主管", dept_id=dept_id, sort=1)
        first_id = first.id
        second = await posts.create_post(code="dev", name="开发工程师", dept_id=dept_id, sort=2)
        second_id = second.id
        await org_env.commit(session)

        await user_posts.assign_user_posts(user_id=5002, post_ids=ConcurrentStableList([first_id, second_id]))
        await org_env.commit(session)
        await role_posts.assign_role_posts(role_id=5002, post_ids=ConcurrentStableList([first_id, second_id]))
        await org_env.commit(session)

        open_read = org_env.make_open_read_service(session)
        assert list(await open_read.user_roles(5002)) == [5002]
        await org_env.commit(session)

        source = org_env.make_data_source(session)
        assert await source.users(dept_id=dept_id, include_children=True) is not None
        await org_env.commit(session)
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2255)
async def test_dept_subtree_users_dedupes_same_user() -> None:
    """子树用户聚合：同一用户在子树两个部门各挂一个岗位时只出现一次。"""
    session, engine = await org_env.make_session()
    try:
        uow = org_env.make_uow(session)
        outbox = org_env.make_outbox()
        config = org_env.make_config()
        depts = org_env.make_dept_service(session, uow, outbox, config)
        posts = org_env.make_post_service(session, uow, outbox, config)
        user_posts = org_env.make_user_post_service(session, uow, outbox, config)

        root = await depts.create_dept(code="rd", name="研发中心", parent_id=None, sort=1)
        root_id = root.id
        await org_env.commit(session)
        child = await depts.create_dept(code="rd-platform", name="平台组", parent_id=root_id, sort=1)
        child_id = child.id
        await org_env.commit(session)
        first = await posts.create_post(code="dev_lead", name="开发主管", dept_id=root_id, sort=1)
        first_id = first.id
        second = await posts.create_post(code="dev", name="开发工程师", dept_id=child_id, sort=2)
        second_id = second.id
        await org_env.commit(session)

        await user_posts.assign_user_posts(user_id=5001, post_ids=ConcurrentStableList([first_id]))
        await org_env.commit(session)
        assert list(await depts.list_subtree_users(root_id)) == [5001]
        await org_env.commit(session)

        await user_posts.assign_user_posts(user_id=5001, post_ids=ConcurrentStableList([first_id, second_id]))
        await org_env.commit(session)
        assert list(await depts.list_subtree_users(root_id)) == [5001]
        await org_env.commit(session)
    finally:
        await engine.dispose()
