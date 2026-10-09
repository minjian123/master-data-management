"""按用户解析角色用例（Kiwi 2256）：岗位链 ∪ 部门链 / 去重 / 缓存与失效代 / 用户来源降级。

口径：岗位链（`org_user_post` → `org_role_post`）∪ 部门链（**用户已分配部门**（`org_user_dept`，全部、
不按主要项）→ `org_role_dept` 精确匹配，不含子树）；**不返回用户直接角色**（`sys_user_role` 归 platform，
由消费方合并）。**2026-10-09 修订**：部门链来源由「平台用户归属部门」改本域 `org_user_dept`。
"""

import pytest
from bms_core.core.concurrent import ConcurrentStableList
from bms_core.db.tenant import current_tenant_id_str
from sqlalchemy.ext.asyncio import AsyncSession

from mdm_org.services.open_read import bump_user_roles_generation
from tests_support import org_env


async def _seed_roles(session: AsyncSession) -> dict[str, int]:
    """在组织树基础上分配角色：1001 → 开发主管岗；1002 → 开发主管岗 + 研发中心部门；1003 → 研发中心部门。

    同时给用户 2001 分配研发中心部门（部门链起点改本域 `org_user_dept`）。

    Returns:
        dict[str, int]: 组织树关键 id。
    """
    key = dict(await org_env.seed_org_tree(session))
    uow = org_env.make_uow(session)
    outbox = org_env.make_outbox()
    role_posts = org_env.make_role_post_service(session, uow, outbox)
    role_depts = org_env.make_role_dept_service(session, uow, outbox)
    user_depts = org_env.make_user_dept_service(session, uow, outbox)
    await role_posts.assign_role_posts(role_id=1001, post_ids=org_env.ids(key["lead"]))
    await role_posts.assign_role_posts(role_id=1002, post_ids=org_env.ids(key["lead"]))
    await role_depts.assign_role_depts(role_id=1002, dept_ids=org_env.ids(key["root"]))
    await role_depts.assign_role_depts(role_id=1003, dept_ids=org_env.ids(key["root"]))
    await user_depts.assign_user_depts(user_id=2001, dept_ids=org_env.ids(key["root"]))
    await org_env.commit(session)
    return key


@pytest.mark.kiwi_id(2256)
async def test_user_roles_union_posts_and_dept_chain() -> None:
    """角色并集：岗位链在前、部门链补入并去重；未分配岗位 / 部门时为空且不报错。"""
    session, engine = await org_env.make_session()
    try:
        await _seed_roles(session)
        service = org_env.make_open_read_service(session, config=org_env.make_config(user_roles_ttl=0))
        assert list(await service.user_roles(2001)) == [1001, 1002, 1003]

        # 未分配任何岗位 / 部门 → 两条链皆空
        assert list(await service.user_roles(2002)) == []
        await org_env.commit(session)
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2256)
async def test_user_roles_cache_hit_and_generation_bump() -> None:
    """结果缓存：同租户同用户重复请求命中缓存；推进失效代后立即失效并读到新值。"""
    session, engine = await org_env.make_session()
    try:
        key = await _seed_roles(session)
        cache = org_env.make_cache()
        service = org_env.make_open_read_service(session, cache=cache)
        first = list(await service.user_roles(2001))
        assert first == [1001, 1002, 1003]

        # 写侧未推进失效代 → 仍命中缓存（新增分配不可见）
        await org_env.commit(session)
        uow = org_env.make_uow(session)
        outbox = org_env.make_outbox()
        role_posts = org_env.make_role_post_service(session, uow, outbox)
        await role_posts.assign_role_posts(role_id=1004, post_ids=org_env.ids(key["lead"]))
        await org_env.commit(session)
        assert list(await service.user_roles(2001)) == first

        # 推进失效代（写侧调用）→ 旧键不可达（岗位链在前、部门链补入）
        await bump_user_roles_generation(cache, current_tenant_id_str())
        assert list(await service.user_roles(2001)) == [1001, 1002, 1004, 1003]
        await org_env.commit(session)
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2256)
async def test_user_roles_ttl_zero_bypasses_cache() -> None:
    """缓存关闭（TTL ≤ 0）：每次直查，新增分配立即可见（无需推进失效代）。"""
    session, engine = await org_env.make_session()
    try:
        key = await _seed_roles(session)
        service = org_env.make_open_read_service(session, config=org_env.make_config(user_roles_ttl=0))
        assert list(await service.user_roles(2001)) == [1001, 1002, 1003]
        await org_env.commit(session)
        uow = org_env.make_uow(session)
        outbox = org_env.make_outbox()
        role_posts = org_env.make_role_post_service(session, uow, outbox)
        await role_posts.assign_role_posts(role_id=1005, post_ids=org_env.ids(key["lead"]))
        await org_env.commit(session)
        assert list(await service.user_roles(2001)) == [1001, 1002, 1005, 1003]
        await org_env.commit(session)
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2256)
async def test_user_roles_independent_of_platform_user_source() -> None:
    """用户来源不可达**不影响**按用户解析角色：部门链取本域 `org_user_dept`，无平台依赖。"""
    session, engine = await org_env.make_session()
    try:
        await _seed_roles(session)
        service = org_env.make_open_read_service(
            session,
            user_source=org_env.UnavailableUserSource(),
            config=org_env.make_config(user_roles_ttl=0),
        )
        assert list(await service.user_roles(2001)) == [1001, 1002, 1003]
        await org_env.commit(session)
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2256)
async def test_open_read_service_delegates_data_source_calls() -> None:
    """出口服务编排：数据源三取数与名称回显经服务转发（路由层只做参数与包装）。"""
    session, engine = await org_env.make_session()
    try:
        key = await org_env.seed_org_tree(session)
        source = org_env.make_user_source(ConcurrentStableList([org_env.user(2001, nickname="张三")]))
        service = org_env.make_open_read_service(session, user_source=source)
        assert [item.code for item in (await service.posts(keyword="dev")).list] == ["dev_lead", "dev"]
        assert [node.name for node in await service.dept_tree()] == ["研发中心", "市场部"]
        assert [item.id for item in (await service.users("张")).list] == [2001]
        refs = list(await service.resolve_names("dept", org_env.ids(key["root"])))
        assert refs[0].name == "研发中心"
        await org_env.commit(session)
    finally:
        await engine.dispose()
