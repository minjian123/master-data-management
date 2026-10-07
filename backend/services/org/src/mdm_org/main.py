"""组织主数据服务入口：应用工厂 `ApplicationFactory`（共享基座 + 产品服务装配）。

产品服务装配（bms 12_03）只额外声明两处：① 覆写 `service_records()` 返回本产品服务清单
（与 `bms_core` 同口径 `ModuleRecord`）；② 声明 `product_key`。基座据此形成应用级服务目录视图
（平台清单 + 注入记录，**同 `module_key` 同值去重、异值即拒**）并做产品维度 fail-closed 校验。

运行工作目录为 `backend/`（`services` 产品清单模块与 `alembic.ini` 均相对该根定位）。
"""

from bms_core.application import BaseServiceApplicationFactory
from bms_core.core.concurrent import ConcurrentStableList
from bms_core.services.module_registry import ModuleRecord
from bms_core.services.table_registry import TableRecord
from fastapi import APIRouter

from mdm_org import CONTRACT_VERSION, SERVICE_NAME, SERVICE_TITLE, __version__
from mdm_org.api.router import api_router
from mdm_org.events import register_product_event_contracts
from services.module_registry import MDM_SERVICE_RECORDS
from services.table_registry import MDM_TABLE_RECORDS

PRODUCT_KEY = "mdm"
"""产品标识（mdm 主数据管理；与应用工厂声明、平台侧登记行一致）。"""

# 事件契约登记（进程级默认注册表；幂等）：启动期事件契约校验与契约快照共用
# （`[event].contract_mode` 缺省 enforce，未登记契约拒发 10010）
register_product_event_contracts()


class ApplicationFactory(BaseServiceApplicationFactory):
    """应用工厂：mdm 组织主数据服务（通用装配由共享基座承载）。"""

    key: str = "application_factory"
    service_name: str = SERVICE_NAME
    service_title: str = SERVICE_TITLE
    version: str = __version__
    contract_version: str = CONTRACT_VERSION
    # 产品标识：基座声明为 `str | None`（`None` = 平台服务、非空 = 产品服务）——此处保持基类类型宽度
    # 并赋本产品标识（值非空即进入产品维度 fail-closed 校验）。
    product_key: str | None = PRODUCT_KEY

    def service_records(self) -> tuple[ModuleRecord, ...]:
        """本产品服务清单（产品自持；与 bms 平台侧 `SERVICE_CATALOG` 同 `module_key` 行逐字段同值）。

        基座把本清单与平台清单拼接为**应用级视图**（`app.state.module_registry`），启动离线校验 /
        接库对账 / 事件契约域一律以该视图为准；两侧同值由 `merge_service_records()` 去重，
        任一字段差异即以 `module_key` 重复被拒（fail-closed）。

        Returns:
            tuple[ModuleRecord, ...]: mdm 产品服务登记记录（插入序）。
        """
        return MDM_SERVICE_RECORDS

    def table_records(self) -> tuple[TableRecord, ...]:
        """本产品表归属记录（产品自持；基座装配期登记并置**合并视图**）。

        基座把本清单注册进表归属注册表（`register_table_records`），迁移链派生
        （`chain_tables`）、开发库自动建表与归属校验一律取「平台清单 + 注入记录」的合并视图
        （同 `table_name` 同值去重、异值即拒；bms 12_04）。

        Returns:
            tuple[TableRecord, ...]: mdm 组织域表归属记录（插入序）。
        """
        return MDM_TABLE_RECORDS

    def service_routers(self) -> ConcurrentStableList[APIRouter]:
        """业务路由（探针路由由基座统一挂载）。

        Returns:
            ConcurrentStableList[APIRouter]: 业务聚合路由。
        """
        return ConcurrentStableList([api_router])
