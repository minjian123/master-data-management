"""用户-部门关联模型（`org_user_dept`）：多对多 + 主要部门标记；`user_id` 为跨服务逻辑外键。"""

from bms_core.models.base import BaseModel
from sqlalchemy import BigInteger, Boolean, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class OrgUserDept(BaseModel):
    """用户-部门关联（`org_user_dept`）：雪花 `id` 主键 + `(user_id, dept_id, deleted_at)` 复合唯一。

    `is_primary` 为该用户的**主要部门**标记（同用户至多一个）；唯一性由服务侧在
    同一写事务内互斥置位保证（不使用部分唯一索引，见《数据库设计》方言特性口径）。
    """

    __tablename__ = "org_user_dept"
    __table_args__ = (
        UniqueConstraint("user_id", "dept_id", "deleted_at", name="uq_org_user_dept_user_dept_deleted_at"),
        Index("idx_org_user_dept_dept_id", "dept_id"),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, comment="用户 id（逻辑外键 → bms sys_user.id，跨服务）")
    dept_id: Mapped[int] = mapped_column(BigInteger, comment="部门 id（逻辑外键 → org_dept.id，同库）")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, comment="主要部门标记（同用户至多一个）")
