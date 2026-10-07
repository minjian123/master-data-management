"""组织主数据服务路由聚合：模块路由经服务级登记表统一挂到 `/api/v1`。

探针路由（`/healthz` `/readyz`）由共享应用基座统一挂载，不在此处登记。

本期为工程骨架（无业务端点）——组织主数据维护端点归 01_02、只读出口与用户-岗位契约归 01_03；
届时在 `ConcurrentStableList` 内追加各模块路由（服务级登记表避免多服务同进程登记串扰）。
"""

from bms_core.api.base import BaseRouter, mount_service_routers
from bms_core.core.concurrent import ConcurrentStableList

api_router = mount_service_routers(ConcurrentStableList[BaseRouter]())
