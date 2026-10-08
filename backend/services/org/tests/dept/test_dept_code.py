"""部门编码用例（Kiwi 2268）：必填与响应面 / 格式（默认与参数覆盖）/ 租户内唯一与软删除复用 / 创建后可改。

用例侧注意：**失败调用会回滚事务并使已加载实例过期**，故各用例在首次失败调用前先把 id 取成普通整数。
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from mdm_org.errors import OrgDeptCodeExistsError, OrgDeptCodeFormatError
from mdm_org.services.dept import DeptService
from tests_support import org_env


async def _env(
    *, dept_pattern: str | None = None, max_children: int | None = None
) -> tuple[AsyncSession, DeptService, AsyncEngine]:
    """建库并装配部门服务。

    Args:
        dept_pattern: 部门编码格式覆盖（`org.dept_code_pattern`）。
        max_children: 同级子部门数上限覆盖。

    Returns:
        tuple[AsyncSession, DeptService, AsyncEngine]: （会话，服务，引擎）。
    """
    session, engine = await org_env.make_session()
    service = org_env.make_dept_service(
        session,
        org_env.make_uow(session),
        org_env.make_outbox(),
        org_env.make_config(dept_pattern=dept_pattern, max_children=max_children),
    )
    return session, service, engine


@pytest.mark.kiwi_id(2268)
async def test_dept_code_returned_in_detail_and_tree() -> None:
    """部门编码随明细与树返回（管理面契约带 `code`）。"""
    session, service, engine = await _env()
    try:
        root = await service.create_dept(code="hq", name="总部", parent_id=None, sort=1)
        root_id = root.id
        await org_env.commit(session)
        child = await service.create_dept(code="rd", name="研发中心", parent_id=root_id, sort=1)
        assert child.code == "rd"
        await org_env.commit(session)

        detail = await service.dept_detail(root_id)
        assert detail.code == "hq"
        await org_env.commit(session)

        tree = await service.list_tree()
        assert tree[0].code == "hq"
        assert tree[0].children[0].code == "rd"
        await org_env.commit(session)
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2268)
async def test_dept_code_unique_and_reusable_after_soft_delete() -> None:
    """部门编码租户内唯一（重复 330060）；软删除后编码可复用。"""
    session, service, engine = await _env()
    try:
        root = await service.create_dept(code="hq", name="总部", parent_id=None, sort=1)
        root_id = root.id
        await org_env.commit(session)
        other = await service.create_dept(code="other", name="其它", parent_id=None, sort=2)
        other_id = other.id
        await org_env.commit(session)

        with pytest.raises(OrgDeptCodeExistsError) as duplicate:
            await service.create_dept(code="other", name="重码部门", parent_id=None, sort=3)
        assert duplicate.value.code == 330060
        await org_env.commit(session)

        await service.delete_dept(dept_id=other_id)
        await org_env.commit(session)
        reused = await service.create_dept(code="other", name="复用编码", parent_id=None, sort=3)
        assert reused.code == "other"
        assert reused.id != other_id
        assert reused.id != root_id
        await org_env.commit(session)
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2268)
async def test_dept_code_pattern_from_config() -> None:
    """部门编码格式经 `org.dept_code_pattern` 读取（覆盖默认正则）。"""
    session, service, engine = await _env(dept_pattern=r"^D-[0-9]{3}$")
    try:
        dept = await service.create_dept(code="D-001", name="研发中心", parent_id=None, sort=1)
        assert dept.code == "D-001"
        await org_env.commit(session)

        with pytest.raises(OrgDeptCodeFormatError) as bad:
            await service.create_dept(code="rd", name="不符合配置格式", parent_id=None, sort=2)
        assert bad.value.code == 330061
        await org_env.commit(session)
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2268)
async def test_dept_code_default_format_rules() -> None:
    """部门编码默认格式：首字符须为字母或数字，限字母 / 数字 / 下划线 / 连字符（330061）。"""
    session, service, engine = await _env()
    try:
        with pytest.raises(OrgDeptCodeFormatError) as starts_with_symbol:
            await service.create_dept(code="-abc", name="非法首字符", parent_id=None, sort=1)
        assert starts_with_symbol.value.code == 330061
        await org_env.commit(session)

        with pytest.raises(OrgDeptCodeFormatError):
            await service.create_dept(code="部门码", name="中文编码", parent_id=None, sort=2)
        await org_env.commit(session)

        with pytest.raises(OrgDeptCodeFormatError):
            await service.create_dept(code="with space", name="含空格", parent_id=None, sort=3)
        await org_env.commit(session)

        ok = await service.create_dept(code="DEPT_01-2", name="合法编码", parent_id=None, sort=4)
        assert ok.code == "DEPT_01-2"
        await org_env.commit(session)
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2268)
async def test_dept_code_update_allowed() -> None:
    """部门编码可改：自身同值幂等 / 改码生效 / 与他部门重复 330060 / 格式非法 330061。"""
    session, service, engine = await _env()
    try:
        root = await service.create_dept(code="hq", name="总部", parent_id=None, sort=1)
        root_id = root.id
        await org_env.commit(session)
        other = await service.create_dept(code="other", name="其它", parent_id=None, sort=2)
        other_id = other.id
        await org_env.commit(session)

        same = await service.update_dept(dept_id=root_id, code="hq")
        assert same.code == "hq"
        await org_env.commit(session)

        renamed = await service.update_dept(dept_id=root_id, code="hq-new")
        assert renamed.code == "hq-new"
        await org_env.commit(session)

        with pytest.raises(OrgDeptCodeExistsError) as duplicate:
            await service.update_dept(dept_id=root_id, code="other")
        assert duplicate.value.code == 330060
        await org_env.commit(session)

        with pytest.raises(OrgDeptCodeFormatError):
            await service.update_dept(dept_id=root_id, code="不合法")
        await org_env.commit(session)

        untouched = await service.dept_detail(other_id)
        assert untouched.code == "other"
        await org_env.commit(session)
    finally:
        await engine.dispose()
