"""角色-岗位分配模型（`org_role_post`）：`role_id` 为跨服务逻辑外键。"""

from bms_core.models.base import BaseModel
from sqlalchemy import BigInteger, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class OrgRolePost(BaseModel):
    """角色-岗位分配（`org_role_post`）：雪花 `id` 主键 + `(role_id, post_id, deleted_at)` 复合唯一。"""

    __tablename__ = "org_role_post"
    __table_args__ = (
        UniqueConstraint("role_id", "post_id", "deleted_at", name="uq_org_role_post_role_post_deleted_at"),
        Index("idx_org_role_post_post_id", "post_id"),
    )

    role_id: Mapped[int] = mapped_column(BigInteger, comment="角色 id（逻辑外键 → bms sys_role.id，跨服务）")
    post_id: Mapped[int] = mapped_column(BigInteger, comment="岗位 id（逻辑外键 → org_post.id，同库）")
