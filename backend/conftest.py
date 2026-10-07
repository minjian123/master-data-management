"""工作区根测试夹具入口（实现见 `tests_support.fixtures`；pytest 以 conftest 命名空间发现夹具）。"""

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
