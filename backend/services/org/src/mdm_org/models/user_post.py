"""用户-岗位关联模型（`org_user_post`）：多对多；`user_id` 为跨服务逻辑外键。"""

from bms_core.models.base import BaseModel
from sqlalchemy import BigInteger, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class OrgUserPost(BaseModel):
    """用户-岗位关联（`org_user_post`）：雪花 `id` 主键 + `(user_id, post_id, deleted_at)` 复合唯一。"""

    __tablename__ = "org_user_post"
    __table_args__ = (
        UniqueConstraint("user_id", "post_id", "deleted_at", name="uq_org_user_post_user_post_deleted_at"),
        Index("idx_org_user_post_post_id", "post_id"),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, comment="用户 id（逻辑外键 → bms sys_user.id，跨服务）")
    post_id: Mapped[int] = mapped_column(BigInteger, comment="岗位 id（逻辑外键 → org_post.id，同库）")
