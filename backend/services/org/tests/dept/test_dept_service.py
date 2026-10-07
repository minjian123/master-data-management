"""部门服务用例（Kiwi 2255）：树维护 / 级联移动 / 防环 / 引用拒绝 / 上限校验 / 事件发布。

用例侧注意：**失败调用会回滚事务并使已加载实例过期**，故各用例在首次失败调用前先把 id 取成普通整数。
"""

import pytest
from bms_core.models.outbox import SysOutbox
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from mdm_org.errors import (
    OrgDeptChildrenLimitError,
    OrgDeptCycleError,
    OrgDeptDepthExceededError,
    OrgDeptHasChildrenError,
    OrgDeptHasRolesError,
    OrgDeptNameExistsError,
    OrgDeptNotFoundError,
    OrgDeptParentUnavailableError,
    OrgDeptReferencedError,
)
from mdm_org.services.dept import DeptService
from tests_support import org_env


async def _env(
    *, max_depth: int | None = None, max_children: int | None = None
) -> tuple[AsyncSession, DeptService, AsyncEngine]:
    """建库并装配部门服务。

    Args:
        max_depth: 部门树最大深度覆盖。
        max_children: 同级子部门数上限覆盖。

    Returns:
        tuple[AsyncSession, DeptService, AsyncEngine]: （会话，服务，引擎）。
    """
    session, engine = await org_env.make_session()
    service = org_env.make_dept_service(
        session,
        org_env.make_uow(session),
        org_env.make_outbox(),
        org_env.make_config(max_depth=max_depth, max_children=max_children),
    )
    return session, service, engine


@pytest.mark.kiwi_id(2255)
async def test_dept_create_tree_and_ancestors() -> None:
    """新建部门：`ancestors` 路径正确、树结构可查、详情可取、不存在抛 330051。"""
    session, service, engine = await _env()
    try:
        root = await service.create_dept(name="总部", parent_id=None, sort=1)
        root_id = root.id
        assert root.ancestors == "/"
        await org_env.commit(session)
        child = await service.create_dept(name="研发中心", parent_id=root_id, sort=1)
        child_id = child.id
        assert child.ancestors == f"/{root_id}/"
        await org_env.commit(session)
        grand = await service.create_dept(name="平台组", parent_id=child_id, sort=1)
        grand_id = grand.id
        assert grand.ancestors == f"/{root_id}/{child_id}/"
        await org_env.commit(session)

        tree = await service.list_tree()
        assert len(tree) == 1
        assert tree[0].name == "总部"
        assert tree[0].children[0].name == "研发中心"
        assert tree[0].children[0].children[0].name == "平台组"
        assert tree[0].children[0].children[0].status == "enabled"

        detail = await service.dept_detail(root_id)
        assert detail.name == "总部"
        await org_env.commit(session)
        with pytest.raises(OrgDeptNotFoundError) as missing:
            await service.dept_detail(grand_id + 999999)
        assert missing.value.code == 330051
        await org_env.commit(session)
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2255)
async def test_dept_move_cascades_and_rejects_cycle() -> None:
    """移动部门：级联更新子树 `ancestors`；移入自身 / 自身后代被拒（330053）。"""
    session, service, engine = await _env()
    try:
        root = await service.create_dept(name="A", parent_id=None, sort=1)
        root_id = root.id
        await org_env.commit(session)
        child = await service.create_dept(name="A1", parent_id=root_id, sort=1)
        child_id = child.id
        await org_env.commit(session)
        grand = await service.create_dept(name="A1a", parent_id=child_id, sort=1)
        grand_id = grand.id
        await org_env.commit(session)
        other = await service.create_dept(name="B", parent_id=None, sort=2)
        other_id = other.id
        await org_env.commit(session)

        moved = await service.move_dept(dept_id=child_id, new_parent_id=other_id)
        assert moved.parent_id == other_id
        assert moved.ancestors == f"/{other_id}/"
        await org_env.commit(session)

        descendant = await service.dept_detail(grand_id)
        assert descendant.ancestors == f"/{other_id}/{child_id}/"
        await org_env.commit(session)

        with pytest.raises(OrgDeptCycleError) as cycle:
            await service.move_dept(dept_id=other_id, new_parent_id=grand_id)
        assert cycle.value.code == 330053
        await org_env.commit(session)

        with pytest.raises(OrgDeptCycleError):
            await service.move_dept(dept_id=other_id, new_parent_id=other_id)
        await org_env.commit(session)
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2255)
async def test_dept_delete_reference_checks() -> None:
    """删除部门：有子部门 / 岗位 / 角色分配时拒绝；无引用时软删除（随后不可见）。"""
    session, service, engine = await _env()
    uow = org_env.make_uow(session)
    outbox = org_env.make_outbox()
    try:
        root = await service.create_dept(name="根", parent_id=None, sort=1)
        root_id = root.id
        await org_env.commit(session)
        child = await service.create_dept(name="子", parent_id=root_id, sort=1)
        child_id = child.id
        await org_env.commit(session)

        with pytest.raises(OrgDeptHasChildrenError) as has_children:
            await service.delete_dept(dept_id=root_id)
        assert has_children.value.code == 330054
        await org_env.commit(session)

        post_service = org_env.make_post_service(session, uow, outbox)
        await post_service.create_post(code="dev", name="开发", dept_id=child_id)
        await org_env.commit(session)
        with pytest.raises(OrgDeptReferencedError) as referenced:
            await service.delete_dept(dept_id=child_id)
        assert referenced.value.code == 330055
        await org_env.commit(session)

        other = await service.create_dept(name="另一部门", parent_id=None, sort=2)
        other_id = other.id
        await org_env.commit(session)
        role_dept_service = org_env.make_role_dept_service(session, uow, outbox)
        await role_dept_service.assign_role_depts(role_id=1001, dept_ids=org_env.ids(other_id))
        await org_env.commit(session)
        with pytest.raises(OrgDeptHasRolesError) as has_roles:
            await service.delete_dept(dept_id=other_id)
        assert has_roles.value.code == 330056
        await org_env.commit(session)

        leaf = await service.create_dept(name="无引用叶子", parent_id=None, sort=3)
        leaf_id = leaf.id
        await org_env.commit(session)
        await service.delete_dept(dept_id=leaf_id)
        await org_env.commit(session)
        with pytest.raises(OrgDeptNotFoundError):
            await service.dept_detail(leaf_id)
        await org_env.commit(session)
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2255)
async def test_dept_validation_limits_and_duplicates() -> None:
    """校验：同父重名（330059）/ 子节点数上限（330058）/ 深度上限（330057）/ 父部门停用（330052）。"""
    session, service, engine = await _env(max_depth=2, max_children=1)
    try:
        root = await service.create_dept(name="根", parent_id=None, sort=1)
        root_id = root.id
        await org_env.commit(session)
        child = await service.create_dept(name="子", parent_id=root_id, sort=1)
        child_id = child.id
        await org_env.commit(session)

        with pytest.raises(OrgDeptNameExistsError) as dup:
            await service.create_dept(name="子", parent_id=root_id, sort=2)
        assert dup.value.code == 330059
        await org_env.commit(session)

        with pytest.raises(OrgDeptChildrenLimitError) as limit:
            await service.create_dept(name="子二", parent_id=root_id, sort=2)
        assert limit.value.code == 330058
        await org_env.commit(session)

        with pytest.raises(OrgDeptDepthExceededError) as depth:
            await service.create_dept(name="孙", parent_id=child_id, sort=1)
        assert depth.value.code == 330057
        await org_env.commit(session)

        await service.update_dept(dept_id=child_id, status="disabled")
        await org_env.commit(session)
        with pytest.raises(OrgDeptParentUnavailableError) as unavailable:
            await service.create_dept(name="寄子", parent_id=child_id, sort=1)
        assert unavailable.value.code == 330052
        await org_env.commit(session)
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2255)
async def test_dept_publishes_changed_event() -> None:
    """事件：部门新建经事务性发件箱写入 `org.dept.changed`（契约 enforce 放行）。"""
    session, service, engine = await _env()
    try:
        dept = await service.create_dept(name="总部", parent_id=None, sort=1)
        dept_id = dept.id
        await org_env.commit(session)
        rows = (await session.execute(select(SysOutbox))).scalars().all()
        assert [item.event_type for item in rows] == ["org.dept.changed"]
        assert int(str(rows[0].payload["dept_id"])) == dept_id
        assert rows[0].payload["changed_type"] == "created"
        await org_env.commit(session)
    finally:
        await engine.dispose()
