"""org:tenant 链 0003：`org_dept` 增部门编码 `code`（必填 + 租户内唯一 + 存量回填）。

Revision ID: 0003_dept_code
Revises: 0002_outbox_tables
Create Date: 2026-10-08

- 归属链：`org:tenant`（组织服务 × 各租户的租户库）；
- 步骤：加列（可空）→ 按 `id` 升序回填 `DEPT` + 定长 4 位序号 → 置非空 + 复合唯一约束 `(code, deleted_at)`；
- 四库通用：全程 `batch_alter_table`（SQLite 走重建表），不含方言专用类型；
- 幂等：回填只补 `code IS NULL` 的行，重复执行不改变既有编码；
- 降级：删唯一约束 + 删列（「部门编码可改」为应用层行为，无数据回滚项）。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_dept_code"
down_revision: str | None = "0002_outbox_tables"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

CODE_PREFIX = "DEPT"
"""存量部门编码前缀。"""

CODE_DIGITS = 4
"""存量部门编码序号定长（超出自动扩位）。"""

CODE_COMMENT = "部门编码（租户内唯一；格式受 org.dept_code_pattern 约束；可修改）"
"""`code` 列注释。"""


def upgrade() -> None:
    """加 `code` 列、回填存量编码、置非空并加复合唯一约束。"""
    with op.batch_alter_table("org_dept") as batch:
        batch.add_column(sa.Column("code", sa.String(length=64), nullable=True, comment=CODE_COMMENT))
    _backfill_codes()
    with op.batch_alter_table("org_dept") as batch:
        batch.alter_column("code", existing_type=sa.String(length=64), nullable=False, comment=CODE_COMMENT)
        batch.create_unique_constraint("uq_org_dept_code_deleted_at", ["code", "deleted_at"])


def _backfill_codes() -> None:
    """按 `id` 升序回填存量部门编码（`DEPT` + 定长序号；仅补空值行，可重复执行）。"""
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id FROM org_dept WHERE code IS NULL ORDER BY id")).fetchall()
    for index, row in enumerate(rows, start=1):
        connection.execute(
            sa.text("UPDATE org_dept SET code = :code WHERE id = :dept_id"),
            {"code": f"{CODE_PREFIX}{index:0{CODE_DIGITS}d}", "dept_id": row[0]},
        )


def downgrade() -> None:
    """删唯一约束与 `code` 列。"""
    with op.batch_alter_table("org_dept") as batch:
        batch.drop_constraint("uq_org_dept_code_deleted_at", type_="unique")
        batch.drop_column("code")
