"""组织主数据系统字段对齐（Kiwi 2340）：字典表 `form_key` / `parent_id` 与复合唯一、关联表不处置。"""

import pytest
from sqlalchemy import UniqueConstraint

from mdm_org.models.dept import DEPT_FORM_KEY, OrgDept
from mdm_org.models.post import POST_FORM_KEY, OrgPost
from mdm_org.models.role_dept import OrgRoleDept
from mdm_org.models.role_post import OrgRolePost
from mdm_org.models.user_dept import OrgUserDept
from mdm_org.models.user_post import OrgUserPost


def _unique_columns(model: type[OrgDept] | type[OrgPost]) -> dict[str, tuple[str, ...]]:
    """取模型唯一约束（约束名 → 列名元组）。

    Args:
        model: 字典表模型。

    Returns:
        dict[str, tuple[str, ...]]: 唯一约束映射。
    """
    return {
        str(constraint.name): tuple(column.name for column in constraint.columns)
        for constraint in model.__table__.constraints
        if isinstance(constraint, UniqueConstraint) and constraint.name is not None
    }


@pytest.mark.kiwi_id(2340)
def test_dept_carries_form_key() -> None:
    """`org_dept`：`form_key` 非空、缺省 `org_dept`、`(form_key, deleted_at)` 复合唯一；`parent_id` 已备。"""
    column = OrgDept.__table__.columns["form_key"]
    assert column.nullable is False
    assert column.type.length == 64
    assert getattr(column.default, "arg", None) == DEPT_FORM_KEY == "org_dept"
    assert _unique_columns(OrgDept)["uq_org_dept_form_key_deleted_at"] == ("form_key", "deleted_at")
    assert "parent_id" in OrgDept.__table__.columns


@pytest.mark.kiwi_id(2340)
def test_post_carries_form_key_and_parent_id() -> None:
    """`org_post`：`form_key` 非空 + 复合唯一；`parent_id` 可空（非层级字典冗余，顶层为空）。"""
    column = OrgPost.__table__.columns["form_key"]
    assert column.nullable is False
    assert column.type.length == 64
    assert getattr(column.default, "arg", None) == POST_FORM_KEY == "org_post"
    assert _unique_columns(OrgPost)["uq_org_post_form_key_deleted_at"] == ("form_key", "deleted_at")
    parent = OrgPost.__table__.columns["parent_id"]
    assert parent.nullable is True
    assert parent.default is None
    assert parent.server_default is None


@pytest.mark.kiwi_id(2340)
def test_association_tables_keep_no_system_fields() -> None:
    """4 张关联表不落 `form_key` / `parent_id`（关联表不套明细口径）。"""
    for model in (OrgUserDept, OrgUserPost, OrgRoleDept, OrgRolePost):
        columns = set(model.__table__.columns.keys())
        assert "form_key" not in columns, model.__tablename__
        assert "parent_id" not in columns, model.__tablename__
