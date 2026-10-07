"""org:tenant 链首：组织主数据五表（部门 / 岗位 / 用户-岗位 / 角色-岗位 / 角色-部门）。

Revision ID: 0001_org_tables
Revises:
Create Date: 2026-10-07

口径：脚本方言无关（三库共用）；公共字段对齐基座 `BaseModel`（雪花 `id` / 审计 / 软删除 / `version`）；
表结构以 mdm《数据库设计》表文件为唯一事实源。
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa

from alembic import op

revision: str = "0001_org_tables"
down_revision: str | None = None
branch_labels: Sequence[str] | None = ("org:tenant",)
depends_on: Sequence[str] | None = None


def _common_columns() -> tuple[sa.Column[Any], ...]:
    """公共字段（对齐基座 `BaseModel`）。

    Returns:
        tuple[sa.Column[Any], ...]: 公共列元组（每次调用返回新实例，供多表复用）。
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
    """建五表（含唯一约束、业务索引与公共软删除索引）。"""
    op.create_table(
        "org_dept",
        *_common_columns(),
        sa.Column(
            "parent_id",
            sa.BigInteger(),
            nullable=True,
            comment="父部门 id（逻辑外键 → 本表 id，同库）；根部门为空",
        ),
        sa.Column(
            "ancestors",
            sa.String(length=512),
            nullable=False,
            server_default=sa.text("'/'"),
            comment="祖先 id 路径（如 /1/5/9/）",
        ),
        sa.Column("name", sa.String(length=128), nullable=False, comment="部门名称（同父唯一）"),
        sa.Column("sort", sa.Integer(), nullable=False, server_default=sa.text("0"), comment="同级排序"),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'enabled'"),
            comment="状态（enabled / disabled）",
        ),
        sa.UniqueConstraint("parent_id", "name", "deleted_at", name="uq_org_dept_parent_name_deleted_at"),
    )
    op.create_index("idx_org_dept_deleted_at", "org_dept", ["deleted_at"])
    op.create_index("idx_org_dept_parent_id", "org_dept", ["parent_id"])
    op.create_index("idx_org_dept_status", "org_dept", ["status"])
    op.create_index("idx_org_dept_ancestors", "org_dept", ["ancestors"])

    op.create_table(
        "org_post",
        *_common_columns(),
        sa.Column("code", sa.String(length=64), nullable=False, comment="岗位码（租户内唯一）"),
        sa.Column("name", sa.String(length=128), nullable=False, comment="岗位名称"),
        sa.Column("dept_id", sa.BigInteger(), nullable=False, comment="归属部门 id（逻辑外键 → org_dept.id）"),
        sa.Column("sort", sa.Integer(), nullable=False, server_default=sa.text("0"), comment="排序"),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'enabled'"),
            comment="状态（enabled / disabled）",
        ),
        sa.UniqueConstraint("code", "deleted_at", name="uq_org_post_code_deleted_at"),
    )
    op.create_index("idx_org_post_deleted_at", "org_post", ["deleted_at"])
    op.create_index("idx_org_post_dept_id", "org_post", ["dept_id"])
    op.create_index("idx_org_post_status", "org_post", ["status"])
    op.create_index("idx_org_post_sort", "org_post", ["sort"])

    op.create_table(
        "org_user_post",
        *_common_columns(),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户 id（逻辑外键 → bms sys_user.id，跨服务）"),
        sa.Column("post_id", sa.BigInteger(), nullable=False, comment="岗位 id（逻辑外键 → org_post.id，同库）"),
        sa.UniqueConstraint("user_id", "post_id", "deleted_at", name="uq_org_user_post_user_post_deleted_at"),
    )
    op.create_index("idx_org_user_post_deleted_at", "org_user_post", ["deleted_at"])
    op.create_index("idx_org_user_post_post_id", "org_user_post", ["post_id"])

    op.create_table(
        "org_role_post",
        *_common_columns(),
        sa.Column("role_id", sa.BigInteger(), nullable=False, comment="角色 id（逻辑外键 → bms sys_role.id，跨服务）"),
        sa.Column("post_id", sa.BigInteger(), nullable=False, comment="岗位 id（逻辑外键 → org_post.id，同库）"),
        sa.UniqueConstraint("role_id", "post_id", "deleted_at", name="uq_org_role_post_role_post_deleted_at"),
    )
    op.create_index("idx_org_role_post_deleted_at", "org_role_post", ["deleted_at"])
    op.create_index("idx_org_role_post_post_id", "org_role_post", ["post_id"])

    op.create_table(
        "org_role_dept",
        *_common_columns(),
        sa.Column("role_id", sa.BigInteger(), nullable=False, comment="角色 id（逻辑外键 → bms sys_role.id，跨服务）"),
        sa.Column("dept_id", sa.BigInteger(), nullable=False, comment="部门 id（逻辑外键 → org_dept.id，同库）"),
        sa.UniqueConstraint("role_id", "dept_id", "deleted_at", name="uq_org_role_dept_role_dept_deleted_at"),
    )
    op.create_index("idx_org_role_dept_deleted_at", "org_role_dept", ["deleted_at"])
    op.create_index("idx_org_role_dept_dept_id", "org_role_dept", ["dept_id"])


def downgrade() -> None:
    """逆序删五表。"""
    for table in ("org_role_dept", "org_role_post", "org_user_post", "org_post", "org_dept"):
        op.drop_table(table)
