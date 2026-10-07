"""角色-部门分配模型（`org_role_dept`）：`role_id` 为跨服务逻辑外键。"""

from bms_core.models.base import BaseModel
from sqlalchemy import BigInteger, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class OrgRoleDept(BaseModel):
    """角色-部门分配（`org_role_dept`）：雪花 `id` 主键 + `(role_id, dept_id, deleted_at)` 复合唯一。"""

    __tablename__ = "org_role_dept"
    __table_args__ = (
        UniqueConstraint("role_id", "dept_id", "deleted_at", name="uq_org_role_dept_role_dept_deleted_at"),
        Index("idx_org_role_dept_dept_id", "dept_id"),
    )

    role_id: Mapped[int] = mapped_column(BigInteger, comment="角色 id（逻辑外键 → bms sys_role.id，跨服务）")
    dept_id: Mapped[int] = mapped_column(BigInteger, comment="部门 id（逻辑外键 → org_dept.id，同库）")
