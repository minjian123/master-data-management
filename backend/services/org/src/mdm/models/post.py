"""岗位模型（`mdm_post`）：归属部门 + 租户内唯一岗位码。"""

from bms_core.models.base import BaseModel
from sqlalchemy import BigInteger, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mdm.models.dept import STATUS_ENABLED

POST_FORM_KEY = "mdm_post"
"""岗位表单标识（`form_key`；多表联合取数的表判别列，保存后不变）。"""


class OrgPost(BaseModel):
    """岗位（`mdm_post`）：归属部门（同库逻辑外键）、岗位码租户内唯一且**创建后可修改**。

    字典系统字段补齐（mdm `01_02/_04`）：`form_key`（表单标识）＋ `parent_id`（非层级字典按
    口径保留冗余，恒空）；`code` / `name` / `status` 已备。
    """

    __tablename__ = "mdm_post"
    __table_args__ = (
        UniqueConstraint("form_key", "deleted_at", name="uq_mdm_post_form_key_deleted_at"),
        UniqueConstraint("code", "deleted_at", name="uq_mdm_post_code_deleted_at"),
        Index("idx_mdm_post_dept_id", "dept_id"),
        Index("idx_mdm_post_status", "status"),
        Index("idx_mdm_post_sort", "sort"),
    )

    form_key: Mapped[str] = mapped_column(String(64), default=POST_FORM_KEY, comment="表单标识（全局唯一；保存后不变）")
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="上级字典 ID（自引用同表 id；非层级字典保留冗余，顶层为空）"
    )
    code: Mapped[str] = mapped_column(
        String(64), comment="岗位码（租户内唯一；格式受 mdm.post_code_pattern 约束；可修改）"
    )
    name: Mapped[str] = mapped_column(String(128), comment="岗位名称")
    dept_id: Mapped[int] = mapped_column(BigInteger, comment="归属部门 id（逻辑外键 → mdm_dept.id，同库）")
    sort: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    status: Mapped[str] = mapped_column(String(16), default=STATUS_ENABLED, comment="状态（enabled / disabled）")
