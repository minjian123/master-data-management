"""mdm 产品 `form_key` 清单校验（**离线**，无库依赖）。

校验目标：产品自持清单 `services/form_registry.py::MDM_FORM_RECORDS` 与 ORM 模型双向一致，
`form_key` 跨表全局唯一且 `data_source_key` 同名闭合；关联表不落系统字段（mdm `01_02/_04`）。

用法：

```bash
cd backend
uv run python -m ops.check_forms
```

校验面：

1. **清单**：非空；`form_key` / `table` / `data_source_key` 格式合法（`^[a-z][a-z0-9_]*$`）；
   `form_key` 与 `table` 均不重复（跨表全局唯一）；`data_source_key == form_key`（同名闭合）；
   `FormRegistry(MDM_FORM_RECORDS).validate()` 无问题（复用基座校验）。
2. **模型侧**：每条记录的表在 `Base.metadata` 中存在、含 `form_key` 列、列缺省值等于清单值、
   存在 `(form_key, deleted_at)` 复合唯一（约束名 `uq_{表}_form_key_deleted_at`）。
3. **反向**：`Base.metadata` 中凡含 `form_key` 列的表须登记进清单（防「表落了字段却没进清单」）。
4. **字典字段**：字典表须含 `parent_id` 列。
5. **关联表**：4 张关联表**不得**含 `form_key` / `parent_id`（关联表不套明细口径）。

冲突 / 非法 → 打印明细并退出码 1；通过 → 退出码 0。
"""

import argparse
import importlib
import re
import sys
from collections.abc import Iterable, Sequence

from bms_core.core.concurrent import ConcurrentStableList
from bms_core.models.base import Base
from bms_core.registry.forms import FORM_KEY_PATTERN, FormRecord, FormRegistry
from sqlalchemy import MetaData, UniqueConstraint

from mdm_org.models import MODEL_MODULES
from services.form_registry import MDM_FORM_RECORDS
from services.table_registry import table_names as product_table_names

KEY_RE = re.compile(FORM_KEY_PATTERN)
"""标识格式（与基座 `FORM_KEY_PATTERN` 同源）。"""

FORM_KEY_COLUMN = "form_key"
"""系统字段列名：表单标识。"""

PARENT_ID_COLUMN = "parent_id"
"""系统字段列名：上级字典 ID。"""

DELETED_AT_COLUMN = "deleted_at"
"""软删除列（复合唯一第二列）。"""

DICT_TABLES = ("org_dept", "org_post")
"""本产品字典表（须落字典系统字段 5 项）。"""

ASSOCIATION_TABLES = ("org_user_dept", "org_role_dept", "org_role_post", "org_user_post")
"""多对多关联表（**不落** `form_key` / `parent_id`）。"""


def load_models() -> MetaData:
    """导入服务包声明的全部模型模块（注册 `Base.metadata`）。

    Returns:
        MetaData: 已含组织域六表的基座元数据。
    """
    for module in MODEL_MODULES:
        importlib.import_module(module)
    return Base.metadata


def unique_columns(table_name: str, metadata: MetaData) -> dict[str, tuple[str, ...]]:
    """取表上全部唯一约束（约束名 → 列名元组）。

    Args:
        table_name: 物理表名。
        metadata: 模型元数据。

    Returns:
        dict[str, tuple[str, ...]]: 唯一约束映射（无表时为空）。
    """
    table = metadata.tables.get(table_name)
    if table is None:
        return {}
    return {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint) and constraint.name is not None
    }


def diff_records(records: Iterable[FormRecord]) -> list[str]:
    """纯函数：清单自身校验（格式 / 唯一 / 同名闭合）。

    Args:
        records: 待校验的表单标识记录。

    Returns:
        list[str]: 问题描述列表（空 = 通过）。
    """
    issues: list[str] = []
    items = list(records)
    if not items:
        return ["清单为空：MDM_FORM_RECORDS 未登记任何表单标识"]
    seen_keys: set[str] = set()
    seen_tables: set[str] = set()
    for record in items:
        if not KEY_RE.match(record.form_key):
            issues.append(f"form_key 格式非法：{record.form_key!r}（须 {FORM_KEY_PATTERN}）")
        if record.form_key in seen_keys:
            issues.append(f"form_key 跨表重复：{record.form_key!r}（须全局唯一）")
        seen_keys.add(record.form_key)
        if not KEY_RE.match(record.table):
            issues.append(f"表名格式非法：{record.table!r}")
        if record.table in seen_tables:
            issues.append(f"表名重复登记：{record.table!r}")
        seen_tables.add(record.table)
        if not record.name:
            issues.append(f"名称缺失：{record.form_key!r}")
        if not record.data_source_key:
            issues.append(f"data_source_key 缺失：{record.form_key!r}")
        elif record.data_source_key != record.form_key:
            issues.append(
                f"data_source_key 未同名闭合：{record.form_key!r} → {record.data_source_key!r}"
                "（须 form_key 同名，与 bms DATA_SOURCE_CATALOG 对齐）"
            )
    for issue in FormRegistry(ConcurrentStableList(items)).validate():
        issues.append(f"基座校验未通过：{issue}")
    return issues


def diff_models(records: Iterable[FormRecord], metadata: MetaData) -> list[str]:
    """纯函数：清单 ↔ 模型双向一致 + 字典 / 关联表口径。

    Args:
        records: 表单标识记录。
        metadata: 模型元数据。

    Returns:
        list[str]: 问题描述列表（空 = 通过）。
    """
    issues: list[str] = []
    items = list(records)
    for record in items:
        table = metadata.tables.get(record.table)
        if table is None:
            issues.append(f"清单表无模型：{record.table!r}（模型未声明）")
            continue
        column = table.columns.get(FORM_KEY_COLUMN)
        if column is None:
            issues.append(f"模型缺 form_key 列：{record.table}")
            continue
        if column.nullable:
            issues.append(f"模型 form_key 列可空：{record.table}")
        default = getattr(column.default, "arg", None)
        if default != record.form_key:
            issues.append(f"模型 form_key 缺省值与清单不符：{record.table} → {default!r}（清单 {record.form_key!r}）")
        expected_name = f"uq_{record.table}_form_key_deleted_at"
        columns = unique_columns(record.table, metadata)
        if columns.get(expected_name) != (FORM_KEY_COLUMN, DELETED_AT_COLUMN):
            issues.append(f"模型缺复合唯一 {expected_name}：{record.table}")
    registered = {record.table for record in items}
    # 反向只在**本产品表集**内核对（`Base.metadata` 同时含基座模型表，不属本产品清单范围）
    for table_name in product_table_names():
        table = metadata.tables.get(table_name)
        if table is not None and FORM_KEY_COLUMN in table.columns and table_name not in registered:
            issues.append(f"模型有 form_key 列但未登记清单：{table_name}")
    for table_name in DICT_TABLES:
        table = metadata.tables.get(table_name)
        if table is None:
            issues.append(f"字典表无模型：{table_name}")
        elif PARENT_ID_COLUMN not in table.columns:
            issues.append(f"字典表缺 parent_id 列：{table_name}")
    for table_name in ASSOCIATION_TABLES:
        table = metadata.tables.get(table_name)
        if table is None:
            issues.append(f"关联表无模型：{table_name}")
            continue
        for column_name in (FORM_KEY_COLUMN, PARENT_ID_COLUMN):
            if column_name in table.columns:
                issues.append(f"关联表不应落 {column_name}：{table_name}")
    return issues


def check() -> list[str]:
    """执行全部离线校验。

    Returns:
        list[str]: 问题描述列表（空 = 通过）。
    """
    metadata = load_models()
    issues = diff_records(MDM_FORM_RECORDS)
    issues.extend(diff_models(MDM_FORM_RECORDS, metadata))
    return issues


def main(argv: Sequence[str] | None = None) -> int:
    """入口：离线校验。

    Args:
        argv: 命令行参数（无选项，保留 argparse 以统一 CLI 形态）。

    Returns:
        int: 退出码（0 通过 / 1 失败）。
    """
    argparse.ArgumentParser(description="mdm 产品 form_key 清单校验（清单 / 模型 / 关联表口径）").parse_args(argv)
    issues = check()
    if issues:
        for issue in issues:
            print(f"[form_key] {issue}")
        print(f"[form_key] 校验失败（{len(issues)} 项）")
        return 1
    keys = ", ".join(record.form_key for record in MDM_FORM_RECORDS)
    print(f"[form_key] 校验通过：清单 {len(MDM_FORM_RECORDS)} 项（{keys}）+ 模型双向一致 + 关联表未落系统字段")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
