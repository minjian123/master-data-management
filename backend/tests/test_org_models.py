"""组织域模型声明（Kiwi 2255）：五表元数据 / 基类 / 唯一约束命名与复合列 / 模型模块登记。"""

import pytest
from bms_core.db.migration import service_model_modules
from bms_core.models.base import Base, BaseModel
from sqlalchemy import UniqueConstraint

from mdm_org.models.dept import OrgDept
from mdm_org.models.post import OrgPost
from mdm_org.models.role_dept import OrgRoleDept
from mdm_org.models.role_post import OrgRolePost
from mdm_org.models.user_dept import OrgUserDept
from mdm_org.models.user_post import OrgUserPost

_MODELS = (OrgDept, OrgPost, OrgUserPost, OrgUserDept, OrgRolePost, OrgRoleDept)


@pytest.mark.kiwi_id(2255)
def test_org_models_declared_on_base_model() -> None:
    """六表均已声明（模型继承基座 `BaseModel`、表名与元数据一致、含软删除与乐观锁列）。"""
    for model in _MODELS:
        assert issubclass(model, BaseModel)
        assert model.__tablename__ in Base.metadata.tables
        columns = model.__table__.columns
        assert {"deleted_at", "version", "created_at", "updated_at"} <= set(columns.keys())


@pytest.mark.kiwi_id(2255)
def test_association_tables_use_id_pk_with_composite_unique() -> None:
    """关联表口径（2026-10-07 修订）：雪花 `id` 主键 + 业务列复合唯一（含 `deleted_at`）。"""
    expectations = {
        OrgUserPost: ("uq_org_user_post_user_post_deleted_at", ("user_id", "post_id", "deleted_at")),
        OrgUserDept: ("uq_org_user_dept_user_dept_deleted_at", ("user_id", "dept_id", "deleted_at")),
        OrgRolePost: ("uq_org_role_post_role_post_deleted_at", ("role_id", "post_id", "deleted_at")),
        OrgRoleDept: ("uq_org_role_dept_role_dept_deleted_at", ("role_id", "dept_id", "deleted_at")),
    }
    for model, (constraint_name, columns) in expectations.items():
        assert "id" in model.__table__.columns, "关联表以雪花 id 为主键"
        unique = {
            constraint.name: tuple(column.name for column in constraint.columns)
            for constraint in model.__table__.constraints
            if isinstance(constraint, UniqueConstraint)
        }
        assert unique[constraint_name] == columns


@pytest.mark.kiwi_id(2255)
def test_model_module_declaration_resolves_via_package_prefix() -> None:
    """模型模块经 `[app].package_prefix = mdm` 解析（bms 12_04）：包名前缀为 mdm 时取到六表模块。"""
    modules = service_model_modules("org")
    assert modules == (
        "mdm_org.models.dept",
        "mdm_org.models.post",
        "mdm_org.models.user_post",
        "mdm_org.models.user_dept",
        "mdm_org.models.role_post",
        "mdm_org.models.role_dept",
    )
