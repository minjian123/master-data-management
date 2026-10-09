"""org:tenant 链 0004：新建 `org_user_dept`（用户-部门多对多 + 主要部门）与 `org_user_post.is_primary`。

Revision ID: 0004_user_dept_and_primary
Revises: 0003_dept_code
Create Date: 2026-10-09

- 归属链：`org:tenant`（组织服务 × 各租户的租户库）；
- 步骤：建 `org_user_dept`（雪花 `id` 主键 + 审计 / 软删除 / `version` + `(user_id, dept_id, deleted_at)` 复合唯一
  + `dept_id` 索引）→ 给 `org_user_post` 加 `is_primary`（先用 `server_default` 承载存量行，再回落默认以与模型零漂移）；
- 四库通用：全程 `op.create_table` / `batch_alter_table`（SQLite 走重建表），不含方言专用类型；
- 存量数据：新表为空、`org_user_post.is_primary` 存量行取假（「无主要岗位」），**无业务回填**；
- 降级：删 `org_user_post.is_primary` → 删 `dept_id` 索引 → 删 `org_user_dept` 表。
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa

from alembic import op

revision: str = "0004_user_dept_and_primary"
down_revision: str | None = "0003_dept_code"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

PRIMARY_COMMENT = "主要标记（同用户至多一个；由服务侧写事务互斥置位保证）"
"""`is_primary` 列注释。"""

USER_ID_COMMENT = "用户 id（逻辑外键 → bms sys_user.id，跨服务）"
"""`user_id` 列注释。"""

DEPT_ID_COMMENT = "部门 id（逻辑外键 → org_dept.id，同库）"
"""`dept_id` 列注释。"""


def _common_columns() -> tuple[sa.Column[Any], ...]:
    """公共字段（对齐基座 `BaseModel`；与 `0001_org_tables` 同口径）。

    Returns:
        tuple[sa.Column[Any], ...]: 公共列元组（每次调用返回新实例）。
    """
    return (
        sa.Column("id", sa.BigInteger(), primary_key=True, comment="主键（雪花 ID）"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="创建时间（UTC）"),
        sa.Column("created_by", sa.BigInteger(), nullable=True, comment="创建人"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, comment="更新时间（UTC）"),
        sa.Column("updated_by", sa.BigInteger(), nullable=True, comment="更新人"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="软删除时间（NULL=未删）"),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1"), comment="乐观锁版本"),
    )


def upgrade() -> None:
    """建 `org_user_dept` 表并给 `org_user_post` 加 `is_primary`。"""
    op.create_table(
        "org_user_dept",
        *_common_columns(),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment=USER_ID_COMMENT),
        sa.Column("dept_id", sa.BigInteger(), nullable=False, comment=DEPT_ID_COMMENT),
        sa.Column("is_primary", sa.Boolean(), nullable=False, comment=PRIMARY_COMMENT),
        sa.UniqueConstraint("user_id", "dept_id", "deleted_at", name="uq_org_user_dept_user_dept_deleted_at"),
    )
    op.create_index("idx_org_user_dept_deleted_at", "org_user_dept", ["deleted_at"])
    op.create_index("idx_org_user_dept_dept_id", "org_user_dept", ["dept_id"])

    with op.batch_alter_table("org_user_post") as batch:
        batch.add_column(
            sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false(), comment=PRIMARY_COMMENT)
        )
    with op.batch_alter_table("org_user_post") as batch:
        batch.alter_column("is_primary", existing_type=sa.Boolean(), server_default=None, comment=PRIMARY_COMMENT)


def downgrade() -> None:
    """删 `org_user_post.is_primary`、删索引并删 `org_user_dept` 表。"""
    with op.batch_alter_table("org_user_post") as batch:
        batch.drop_column("is_primary")
    op.drop_index("idx_org_user_dept_dept_id", table_name="org_user_dept")
    op.drop_index("idx_org_user_dept_deleted_at", table_name="org_user_dept")
    op.drop_table("org_user_dept")
