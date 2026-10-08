"""部门模型（`org_dept`）：组织架构树（`ancestors` 祖先路径 + 父子自引用）。"""

from bms_core.models.base import BaseModel
from sqlalchemy import BigInteger, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

ROOT_ANCESTORS = "/"
"""根部门祖先路径（根部门 `parent_id` 为空、`ancestors` 取本值）。"""

STATUS_ENABLED = "enabled"
"""启用状态。"""

STATUS_DISABLED = "disabled"
"""停用状态。"""


class OrgDept(BaseModel):
    """部门（`org_dept`）：父子树 + `ancestors` 路径（子树查询与 `@dept_subtree` 展开）；部门编码租户内唯一。

    部门编码 `code` 必填、租户内唯一、**创建后可修改**（格式受 `org.dept_code_pattern` 约束）。
    """

    __tablename__ = "org_dept"
    __table_args__ = (
        UniqueConstraint("code", "deleted_at", name="uq_org_dept_code_deleted_at"),
        UniqueConstraint("parent_id", "name", "deleted_at", name="uq_org_dept_parent_name_deleted_at"),
        Index("idx_org_dept_parent_id", "parent_id"),
        Index("idx_org_dept_status", "status"),
        Index("idx_org_dept_ancestors", "ancestors"),
    )

    code: Mapped[str] = mapped_column(
        String(64), comment="部门编码（租户内唯一；格式受 org.dept_code_pattern 约束；可修改）"
    )
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="父部门 id（逻辑外键 → 本表 id，同库）；根部门为空"
    )
    ancestors: Mapped[str] = mapped_column(
        String(512), default=ROOT_ANCESTORS, comment="祖先 id 路径（如 /1/5/9/），供子树查询"
    )
    name: Mapped[str] = mapped_column(String(128), comment="部门名称（同父唯一）")
    sort: Mapped[int] = mapped_column(Integer, default=0, comment="同级排序")
    status: Mapped[str] = mapped_column(String(16), default=STATUS_ENABLED, comment="状态（enabled / disabled）")
