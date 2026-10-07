"""组织主数据服务工程级测试夹具入口（实现见 `tests_support.fixtures`，口径与工作区根一致）。"""

from tests_support.fixtures import (
    client,
    fake_tenant_source,
    isolate_settings,
    reset_request_context,
    service_app,
)

__all__ = [
    "client",
    "fake_tenant_source",
    "isolate_settings",
    "reset_request_context",
    "service_app",
]
