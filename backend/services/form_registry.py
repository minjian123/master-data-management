"""mdm 产品 **`form_key` 自持清单**（与 `bms_core.registry.forms.FormRecord` 同结构）。

- **产品自持**：本清单是 mdm 侧表单标识登记的唯一出处（与 mdm《数据库设计》表文件一致）；
  平台侧 `FORM_CATALOG` **不登记**产品表，避免产品值写进基座清单。
- **装载期注入**（基座装配钩子）：应用工厂覆写 `form_records()` 返回本清单，基座经
  `merge_form_records(injected=...)` 与 `FORM_CATALOG` 拼接为**应用级视图**
  （`app.state.form_registry`，`GET /api/v1/form-keys` 取该视图）；无进程级注册表、不改常量。
- **取值口径**（2026-10-22 拍板）：`form_key` ＝ 表名同名（`org_dept` / `org_post`），
  `data_source_key` 与 `form_key` **同名闭合**（1:1），与 bms `DATA_SOURCE_CATALOG` 的
  `org_dept` / `org_post` 两条跨项目登记对齐，供通用页面路由直接解析。
- **不落范围**：明细表、多对多关联表（`org_user_dept` / `org_role_dept` / `org_role_post` /
  `org_user_post`）与基础设施表不登记（口径见 bms《数据库开发规范》「系统字段」节）。
"""

from bms_core.core.concurrent import ConcurrentStableList
from bms_core.registry.forms import FormKind, FormRecord, FormStatus

MDM_FORM_RECORDS: tuple[FormRecord, ...] = (
    FormRecord(
        form_key="org_dept",
        table="org_dept",
        name="部门",
        kind=FormKind.DICT.value,
        status=FormStatus.ENABLED.value,
        data_source_key="org_dept",
    ),
    FormRecord(
        form_key="org_post",
        table="org_post",
        name="岗位",
        kind=FormKind.DICT.value,
        status=FormStatus.ENABLED.value,
        data_source_key="org_post",
    ),
)
"""mdm 组织域字典表 `form_key` 记录（插入序；`form_key` 与 `data_source_key` 同名闭合）。"""


def form_records() -> ConcurrentStableList[FormRecord]:
    """本产品表单标识记录清单（插入序副本；供应用装配钩子与用例消费）。

    Returns:
        ConcurrentStableList[FormRecord]: 表单标识记录（插入序）。
    """
    return ConcurrentStableList(MDM_FORM_RECORDS)


def form_record(table: str) -> FormRecord | None:
    """按物理表名取登记记录（供校验脚本与运维核对）。

    Args:
        table: 物理表名（如 `org_dept`）。

    Returns:
        FormRecord | None: 命中记录；未登记返回 `None`。
    """
    for record in MDM_FORM_RECORDS:
        if record.table == table:
            return record
    return None


def form_keys() -> tuple[str, ...]:
    """本产品表单标识清单（插入序；供校验脚本与用例断言）。

    Returns:
        tuple[str, ...]: 表单标识元组。
    """
    return tuple(record.form_key for record in MDM_FORM_RECORDS)
