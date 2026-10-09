"""组织主数据服务路由聚合：模块路由经服务级登记表统一挂到 `/api/v1`。

探针路由（`/healthz` `/readyz`）由共享应用基座统一挂载，不在此处登记。
01_02 登记部门 / 岗位 / 用户-岗位 / 角色-岗位 / 角色-部门五组管理面路由；
01_02 嵌套子任务 `02` 追加用户-部门分配路由（`/org/user-depts`，含主要部门置位）；
01_03 登记只读出口路由（组织数据源 / 名称回显 / 按用户解析角色，路径挂 `/org/data-source/*` 等）。
"""

from bms_core.api.base import BaseRouter, mount_service_routers
from bms_core.core.concurrent import ConcurrentStableList

from mdm_org.api import dept, open_read, post, role_dept, role_post, user_dept, user_post

api_router = mount_service_routers(
    ConcurrentStableList[BaseRouter](
        [
            dept.router,
            post.router,
            user_post.router,
            user_dept.router,
            role_post.router,
            role_dept.router,
            open_read.router,
        ]
    )
)
