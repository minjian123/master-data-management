"""mdm:tenant 链 0005：`mdm_dept` / `mdm_post` 落系统字段 `form_key`（`mdm_post` 另落 `parent_id`）。

Revision ID: 0005_mdm_form_key
Revises: 0004_user_dept_and_primary
Create Date: 2026-10-22

- 归属链：`mdm:tenant`（组织服务 × 各租户的租户库）；
- 口径来源：bms《数据库开发规范》§3.1.3（字典系统字段 5 项）——`form_key` / `code` / `name` /
  `status` / `parent_id`；mdm 表 `code` / `name` / `status` 已备，本迁移只补缺项（mdm `01_02/_04`）；
- 步骤：`mdm_dept` 加 `form_key`（带 `server_default='mdm_dept'` 回填存量）→ 独立 batch 移除
  `server_default` 并建 `(form_key, deleted_at)` 复合唯一；`mdm_post` 同上（缺省 `'mdm_post'`）
  并加 `parent_id`（可空、无缺省、**不建索引**，非层级字典恒 `NULL`）；
- 四库通用：全程 `batch_alter_table`（SQLite 走重建表），不含方言专用类型；
- 存量数据：`form_key` 由 DDL 缺省回填（每表同值，属设计意图——多表联合取数的表判别列），
  `parent_id` 保持 `NULL`，**无业务回填**；
- 降级：删两张表的唯一约束与新增列（`mdm_post` 先删 `parent_id`）。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_mdm_form_key"
down_revision: str | None = "0004_user_dept_and_primary"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

DEPT_FORM_KEY = "mdm_dept"
"""部门表 `form_key` 常量（与模型 `DEPT_FORM_KEY` 一致）。"""

POST_FORM_KEY = "mdm_post"
"""岗位表 `form_key` 常量（与模型 `POST_FORM_KEY` 一致）。"""

FORM_KEY_COMMENT = "表单标识（全局唯一；保存后不变）"
"""`form_key` 列注释。"""

PARENT_ID_COMMENT = "上级字典 ID（自引用同表 id；非层级字典保留冗余，顶层为空）"
"""`parent_id` 列注释。"""


def upgrade() -> None:
    """两张字典表加 `form_key`（回填后移除缺省）与复合唯一；`mdm_post` 另加 `parent_id`。"""
    with op.batch_alter_table("mdm_dept") as batch:
        batch.add_column(
            sa.Column(
                "form_key",
                sa.String(length=64),
                nullable=False,
                server_default=DEPT_FORM_KEY,
                comment=FORM_KEY_COMMENT,
            )
        )
    with op.batch_alter_table("mdm_dept") as batch:
        batch.alter_column(
            "form_key",
            existing_type=sa.String(length=64),
            server_default=None,
            comment=FORM_KEY_COMMENT,
        )
        batch.create_unique_constraint("uq_mdm_dept_form_key_deleted_at", ["form_key", "deleted_at"])

    with op.batch_alter_table("mdm_post") as batch:
        batch.add_column(
            sa.Column(
                "form_key",
                sa.String(length=64),
                nullable=False,
                server_default=POST_FORM_KEY,
                comment=FORM_KEY_COMMENT,
            )
        )
        batch.add_column(sa.Column("parent_id", sa.BigInteger(), nullable=True, comment=PARENT_ID_COMMENT))
    with op.batch_alter_table("mdm_post") as batch:
        batch.alter_column(
            "form_key",
            existing_type=sa.String(length=64),
            server_default=None,
            comment=FORM_KEY_COMMENT,
        )
        batch.create_unique_constraint("uq_mdm_post_form_key_deleted_at", ["form_key", "deleted_at"])


def downgrade() -> None:
    """删两张表的唯一约束与新增列（`mdm_post` 先删 `parent_id`）。"""
    with op.batch_alter_table("mdm_post") as batch:
        batch.drop_constraint("uq_mdm_post_form_key_deleted_at", type_="unique")
        batch.drop_column("parent_id")
        batch.drop_column("form_key")
    with op.batch_alter_table("mdm_dept") as batch:
        batch.drop_constraint("uq_mdm_dept_form_key_deleted_at", type_="unique")
        batch.drop_column("form_key")
