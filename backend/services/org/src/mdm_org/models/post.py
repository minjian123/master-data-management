"""岗位模型（`org_post`）：归属部门 + 租户内唯一岗位码。"""

from bms_core.models.base import BaseModel
from sqlalchemy import BigInteger, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mdm_org.models.dept import STATUS_ENABLED


class OrgPost(BaseModel):
    """岗位（`org_post`）：归属部门（同库逻辑外键）、岗位码租户内唯一且**创建后可修改**。"""

    __tablename__ = "org_post"
    __table_args__ = (
        UniqueConstraint("code", "deleted_at", name="uq_org_post_code_deleted_at"),
        Index("idx_org_post_dept_id", "dept_id"),
        Index("idx_org_post_status", "status"),
        Index("idx_org_post_sort", "sort"),
    )

    code: Mapped[str] = mapped_column(
        String(64), comment="岗位码（租户内唯一；格式受 org.post_code_pattern 约束；可修改）"
    )
    name: Mapped[str] = mapped_column(String(128), comment="岗位名称")
    dept_id: Mapped[int] = mapped_column(BigInteger, comment="归属部门 id（逻辑外键 → org_dept.id，同库）")
    sort: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    status: Mapped[str] = mapped_column(String(16), default=STATUS_ENABLED, comment="状态（enabled / disabled）")
