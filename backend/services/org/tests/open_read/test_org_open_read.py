"""组织只读出口取数用例（Kiwi 2256）：数据源三取数 / 部门过滤过渡口径 / 数据范围 / 名称回显。

用例侧注意：**失败调用会回滚事务并使已加载实例过期**，故各用例在首次失败调用前先把 id 取成普通整数。
"""

import pytest
from bms_core.core.concurrent import ConcurrentStableList
from bms_core.core.exceptions import ParamError

from tests_support import org_env


@pytest.mark.kiwi_id(2256)
async def test_users_dept_filter_derivation_empty_candidate_and_cap() -> None:
    """用户取数：部门过滤经「岗位归属部门」派生候选集（含子树）；空候选直接空页；超上限拒。"""
    session, engine = await org_env.make_session()
    try:
        key = await org_env.seed_org_tree(session)
        users = ConcurrentStableList(
            [
                org_env.user(2001, nickname="张三"),
                org_env.user(2002, nickname="李四"),
                org_env.user(3001, nickname="王五", status="disabled"),
            ]
        )
        source = org_env.make_user_source(users)
        data_source = org_env.make_data_source(session, user_source=source)

        page = await data_source.users(dept_id=key["root"], include_children=True)
        assert [item.id for item in page.list] == [2001, 2002]
        assert page.total == 2
        assert source.query_calls == 1
        await org_env.commit(session)

        page = await data_source.users(dept_id=key["root"])
        assert [item.id for item in page.list] == [2001]
        await org_env.commit(session)

        # 部门不存在 → 候选为空：直接空页且**不发起下游取数**
        blank_source = org_env.make_user_source(users)
        blank = org_env.make_data_source(session, user_source=blank_source)
        empty = await blank.users(dept_id=key["other"] + 999999)
        assert empty.total == 0 and list(empty.list) == []
        assert blank_source.query_calls == 0
        await org_env.commit(session)

        # 关键字 / 状态透传到来源
        page = await data_source.users("李")
        assert [item.id for item in page.list] == [2002]
        page = await data_source.users(status="disabled")
        assert [item.id for item in page.list] == [3001]
        await org_env.commit(session)

        # 候选集规模上限（超限提示改用关键字检索）
        capped = org_env.make_data_source(session, user_source=source, config=org_env.make_config(max_filter_ids=1))
        with pytest.raises(ParamError):
            await capped.users(dept_id=key["root"], include_children=True)
        await org_env.commit(session)
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2256)
async def test_posts_and_dept_tree_with_data_scope() -> None:
    """岗位取数与部门树：部门含子级过滤、关键字 / 状态过滤；数据范围限定外的部门不可见 / 不入树；树节点带部门编码。"""
    session, engine = await org_env.make_session()
    try:
        key = await org_env.seed_org_tree(session)
        source = org_env.make_user_source()
        scoped = org_env.make_data_source(
            session,
            user_source=source,
            dept_scope=ConcurrentStableList([key["root"], key["child"]]),
        )

        page = await scoped.posts(dept_id=key["root"], include_children=True)
        assert [item.code for item in page.list] == ["dev_lead", "dev"]
        assert page.total == 2
        await org_env.commit(session)

        # 数据范围外的部门岗位（市场部 / 销售）不可见
        page = await scoped.posts(keyword="销售")
        assert page.total == 0
        await org_env.commit(session)

        page = await scoped.posts(keyword="dev", status="enabled")
        assert [item.code for item in page.list] == ["dev_lead", "dev"]
        await org_env.commit(session)

        # 部门树：范围外部门不入树；仍在范围的子部门父节点缺省时上提为根（树自根可达）；节点带部门编码
        tree = list(await scoped.dept_tree())
        assert [node.name for node in tree] == ["研发中心"]
        assert [node.code for node in tree] == ["rd"]
        assert [child.name for child in tree[0].children] == ["平台组"]
        assert [child.code for child in tree[0].children] == ["rd-platform"]
        await org_env.commit(session)

        # 不限定时全量树（按 sort / id 序）；出口契约携带部门编码
        plain = org_env.make_data_source(session, user_source=source)
        assert [node.name for node in await plain.dept_tree()] == ["研发中心", "市场部"]
        assert [node.code for node in await plain.dept_tree()] == ["rd", "mkt"]
        filtered = await plain.dept_tree(status="enabled")
        assert [node.name for node in filtered] == ["研发中心", "市场部"]
        await org_env.commit(session)
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2256)
async def test_resolve_names_targets_order_and_placeholder() -> None:
    """名称回显：三类目标均可回显、保持请求插入序、未命中项占位（不存在 + 不可用）；目标非法即拒。"""
    session, engine = await org_env.make_session()
    try:
        key = await org_env.seed_org_tree(session)
        source = org_env.make_user_source(ConcurrentStableList([org_env.user(2001, nickname="张三")]))
        resolver = org_env.make_resolver(session, user_source=source)

        refs = list(await resolver.resolve_names("post", org_env.ids(key["eng"], 999999, key["lead"])))
        assert [ref.id for ref in refs] == [key["eng"], 999999, key["lead"]]
        assert refs[0].name == "开发工程师" and refs[0].exists is True and refs[0].target == "post"
        assert refs[1].name == "" and refs[1].exists is False and refs[1].status == "disabled"
        await org_env.commit(session)

        refs = list(await resolver.resolve_names("dept", org_env.ids(key["root"])))
        assert refs[0].name == "研发中心" and refs[0].exists is True
        await org_env.commit(session)

        # 用户回显取用户来源；昵称缺省回落用户名；不存在用户占位
        refs = list(await resolver.resolve_names("user", org_env.ids(2001, 2002)))
        assert refs[0].name == "张三" and refs[0].exists is True
        assert refs[1].exists is False
        await org_env.commit(session)

        with pytest.raises(ParamError):
            await resolver.resolve_names("role", org_env.ids(1))
        await org_env.commit(session)
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2256)
async def test_posts_scope_intersection_with_single_dept_filter() -> None:
    """部门过滤与数据范围取交：范围外部门被过滤掉时（交集为空）直接空页。"""
    session, engine = await org_env.make_session()
    try:
        key = await org_env.seed_org_tree(session)
        source = org_env.make_user_source()
        scoped = org_env.make_data_source(session, user_source=source, dept_scope=ConcurrentStableList([key["root"]]))
        page = await scoped.posts(dept_id=key["other"])
        assert page.total == 0
        users_page = await scoped.users(dept_id=key["other"])
        assert users_page.total == 0 and source.query_calls == 0
        await org_env.commit(session)
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2256)
async def test_posts_pagination_bounds() -> None:
    """岗位分页：`size` 限定页大小、`total` 为筛选总数（与列表同口径）。"""
    session, engine = await org_env.make_session()
    try:
        key = await org_env.seed_org_tree(session)
        source = org_env.make_user_source()
        data_source = org_env.make_data_source(session, user_source=source)
        page = await data_source.posts(dept_id=key["root"], include_children=True, size=1)
        assert len(list(page.list)) == 1 and page.total == 2 and page.size == 1
        await org_env.commit(session)
    finally:
        await engine.dispose()
