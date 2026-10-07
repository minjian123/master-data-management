"""按用户解析角色用例（Kiwi 2256）：岗位链 ∪ 部门链 / 去重 / 缓存与失效代 / 用户来源降级。

口径：岗位链（`org_user_post` → `org_role_post`）∪ 部门链（用户归属部门 → `org_role_dept` 精确匹配，
不含子树）；**不返回用户直接角色**（`sys_user_role` 归 platform，由消费方合并）。
"""

import pytest
from bms_core.core.concurrent import ConcurrentStableList
from bms_core.db.tenant import current_tenant_id_str
from sqlalchemy.ext.asyncio import AsyncSession

from mdm_org.errors import OrgSourceUnavailableError
from mdm_org.services.open_read import bump_user_roles_generation
from tests_support import org_env


async def _seed_roles(session: AsyncSession) -> dict[str, int]:
    """在组织树基础上分配角色：1001 → 开发主管岗；1002 → 开发主管岗 + 研发中心部门；1003 → 研发中心部门。

    Returns:
        dict[str, int]: 组织树关键 id。
    """
    key = dict(await org_env.seed_org_tree(session))
    uow = org_env.make_uow(session)
    outbox = org_env.make_outbox()
    role_posts = org_env.make_role_post_service(session, uow, outbox)
    role_depts = org_env.make_role_dept_service(session, uow, outbox)
    await role_posts.assign_role_posts(role_id=1001, post_ids=org_env.ids(key["lead"]))
    await role_posts.assign_role_posts(role_id=1002, post_ids=org_env.ids(key["lead"]))
    await role_depts.assign_role_depts(role_id=1002, dept_ids=org_env.ids(key["root"]))
    await role_depts.assign_role_depts(role_id=1003, dept_ids=org_env.ids(key["root"]))
    await org_env.commit(session)
    return key


@pytest.mark.kiwi_id(2256)
async def test_user_roles_union_posts_and_dept_chain() -> None:
    """角色并集：岗位链在前、部门链补入并去重；用户不存在于来源时只回岗位链（部门链缺省不参与）。"""
    session, engine = await org_env.make_session()
    try:
        key = await _seed_roles(session)
        source = org_env.make_user_source(
            ConcurrentStableList([org_env.user(2001, nickname="张三", dept_id=key["root"])])
        )
        service = org_env.make_open_read_service(
            session, user_source=source, config=org_env.make_config(user_roles_ttl=0)
        )
        assert list(await service.user_roles(2001)) == [1001, 1002, 1003]

        # 用户不在来源（如已删除）→ 部门链不可解析但不报错，仅岗位链
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
        source = org_env.make_user_source(
            ConcurrentStableList([org_env.user(2001, nickname="张三", dept_id=key["root"])])
        )
        cache = org_env.make_cache()
        service = org_env.make_open_read_service(session, user_source=source, cache=cache)
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
        source = org_env.make_user_source(
            ConcurrentStableList([org_env.user(2001, nickname="张三", dept_id=key["root"])])
        )
        service = org_env.make_open_read_service(
            session, user_source=source, config=org_env.make_config(user_roles_ttl=0)
        )
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
async def test_user_roles_source_unavailable_fail_closed() -> None:
    """用户来源不可达：整体 fail-closed（330101），不接受「少了部门链」的部分结果。"""
    session, engine = await org_env.make_session()
    try:
        await _seed_roles(session)
        service = org_env.make_open_read_service(
            session,
            user_source=org_env.UnavailableUserSource(),
            config=org_env.make_config(user_roles_ttl=0),
        )
        with pytest.raises(OrgSourceUnavailableError) as failure:
            await service.user_roles(2001)
        assert failure.value.code == 330101
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
