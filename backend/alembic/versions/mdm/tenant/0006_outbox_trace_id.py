"""mdm:tenant 链 0006：发件箱补链路 id（`sys_outbox.trace_id`）。

Revision ID: 0006_outbox_trace_id
Revises: 0005_mdm_form_key
Create Date: 2026-11-05

背景：基座 `bms_core.models.outbox.SysOutbox` 已增 `trace_id`（写入时取请求上下文 / OTel，
投递保真供消费端续接），mdm 的 `0002_outbox_tables` 建表时尚未包含该列。2026-11-05
PostgreSQL / 达梦真库演练比对「库结构 ↔ 模型」时检出，故补一条**增量**迁移（不改历史迁移，
既有 `mdm` / `mdm_demo` / `mdm_acme` 库可随部署直接升级到 head）。

- 可空列：存量事件没有链路 id，补列不阻塞写入；
- 不建索引：链路 id 只用于排障关联查询，非高频过滤条件。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_outbox_trace_id"
down_revision: str | None = "0005_mdm_form_key"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """`sys_outbox` 增可空 `trace_id`（链路 id）。"""
    op.add_column(
        "sys_outbox",
        sa.Column(
            "trace_id",
            sa.String(length=64),
            nullable=True,
            comment="链路 id（写入时取请求上下文 / OTel，投递保真供消费端续接）",
        ),
    )


def downgrade() -> None:
    """移除 `sys_outbox.trace_id`。"""
    op.drop_column("sys_outbox", "trace_id")
