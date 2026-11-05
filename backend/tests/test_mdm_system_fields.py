"""组织主数据系统字段对齐（Kiwi 2340）：字典表 `form_key` / `parent_id` 与复合唯一、关联表不处置。"""

import pytest
from sqlalchemy import UniqueConstraint

from mdm.models.dept import DEPT_FORM_KEY, MdmDept
from mdm.models.post import POST_FORM_KEY, MdmPost
from mdm.models.role_dept import MdmRoleDept
from mdm.models.role_post import MdmRolePost
from mdm.models.user_dept import MdmUserDept
from mdm.models.user_post import MdmUserPost


def _unique_columns(model: type[MdmDept] | type[MdmPost]) -> dict[str, tuple[str, ...]]:
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
    """`mdm_dept`：`form_key` 非空、缺省 `mdm_dept`、`(form_key, deleted_at)` 复合唯一；`parent_id` 已备。"""
    column = MdmDept.__table__.columns["form_key"]
    assert column.nullable is False
    assert column.type.length == 64
    assert getattr(column.default, "arg", None) == DEPT_FORM_KEY == "mdm_dept"
    assert _unique_columns(MdmDept)["uq_mdm_dept_form_key_deleted_at"] == ("form_key", "deleted_at")
    assert "parent_id" in MdmDept.__table__.columns


@pytest.mark.kiwi_id(2340)
def test_post_carries_form_key_and_parent_id() -> None:
    """`mdm_post`：`form_key` 非空 + 复合唯一；`parent_id` 可空（非层级字典冗余，顶层为空）。"""
    column = MdmPost.__table__.columns["form_key"]
    assert column.nullable is False
    assert column.type.length == 64
    assert getattr(column.default, "arg", None) == POST_FORM_KEY == "mdm_post"
    assert _unique_columns(MdmPost)["uq_mdm_post_form_key_deleted_at"] == ("form_key", "deleted_at")
    parent = MdmPost.__table__.columns["parent_id"]
    assert parent.nullable is True
    assert parent.default is None
    assert parent.server_default is None


@pytest.mark.kiwi_id(2340)
def test_association_tables_keep_no_system_fields() -> None:
    """4 张关联表不落 `form_key` / `parent_id`（关联表不套明细口径）。"""
    for model in (MdmUserDept, MdmUserPost, MdmRoleDept, MdmRolePost):
        columns = set(model.__table__.columns.keys())
        assert "form_key" not in columns, model.__tablename__
        assert "parent_id" not in columns, model.__tablename__
