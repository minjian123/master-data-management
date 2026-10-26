"""mdm 产品**表归属自持清单**（与 `bms_core.services.table_registry.TableRecord` 同结构）。

- **产品自持**：本清单是 mdm 侧表归属登记的唯一出处（与 mdm《数据库设计》总览
  「已设计数据表登记」及表文件一致）；平台侧 `TABLE_OWNERSHIP` **不登记**产品表。
- **装载期注册**（基座 12_04 注入通道）：经 `register()` 把本清单注册进基座表归属注册表，
  合并视图（`table_ownership_view()`）供迁移清单表集派生（`series_tables`）、开发库自动建表与
  归属校验使用。注册入口：应用装配钩子（`mdm.main.ApplicationFactory.table_records()`）与
  ops / alembic 装载入口。
- **归属业务域（07C）**：每张表声明 `domain = org`——迁移清单按「业务域 × 数据源」组织
  （`org:platform` / `org:tenant`），域标识与承载服务（`mdm`）解耦。
- **同值去重、异值即拒**：与平台侧同 `table_name` 同值去重；任一字段差异即被归属校验判为
  「表名重复登记」而拒（fail-closed）。
"""

from bms_core.core.concurrent import ConcurrentStableList
from bms_core.services.table_registry import Datasource, TableRecord, register_table_records

ORG_DOMAIN = "org"
"""mdm 归属业务域（`deploy/boundaries/domain_layout.json` 的 `domain_key`；迁移清单前缀）。"""

MDM_TABLE_RECORDS: tuple[TableRecord, ...] = (
    TableRecord(
        table_name="mdm_dept",
        owner="mdm",
        domain=ORG_DOMAIN,
        datasource=Datasource.TENANT,
        note="部门（组织架构树）",
    ),
    TableRecord(
        table_name="mdm_post",
        owner="mdm",
        domain=ORG_DOMAIN,
        datasource=Datasource.TENANT,
        note="岗位（归属部门）",
    ),
    TableRecord(
        table_name="mdm_user_post",
        owner="mdm",
        domain=ORG_DOMAIN,
        datasource=Datasource.TENANT,
        note="用户-岗位关联",
    ),
    TableRecord(
        table_name="mdm_user_dept",
        owner="mdm",
        domain=ORG_DOMAIN,
        datasource=Datasource.TENANT,
        note="用户-部门关联（含主要部门标记）",
    ),
    TableRecord(
        table_name="mdm_role_post",
        owner="mdm",
        domain=ORG_DOMAIN,
        datasource=Datasource.TENANT,
        note="角色-岗位分配",
    ),
    TableRecord(
        table_name="mdm_role_dept",
        owner="mdm",
        domain=ORG_DOMAIN,
        datasource=Datasource.TENANT,
        note="角色-部门分配",
    ),
)
"""mdm 组织域六表归属记录（业务域 `org`，租户库 `mdm_{租户}`，迁移清单 `org:tenant`）。"""


def register() -> None:
    """把本产品表归属记录注册进基座（**装载期**调用；同值重复登记无操作，幂等）。

    ops / alembic 等**不经应用装配**的装载入口须显式调用本函数；应用装配路径由基座的
    `table_records()` 钩子在 `create()` 内自动注册（`mdm.main.ApplicationFactory`）。
    """
    register_table_records(ConcurrentStableList(MDM_TABLE_RECORDS))


def table_names() -> tuple[str, ...]:
    """本产品自持的表名清单（插入序；供用例与运维核对）。

    Returns:
        tuple[str, ...]: 表名元组。
    """
    return tuple(record.table_name for record in MDM_TABLE_RECORDS)
