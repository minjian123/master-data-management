"""工作区根测试夹具入口（实现见 `tests_support.fixtures`；pytest 以 conftest 命名空间发现夹具）。"""

import mdm  # noqa: F401  # 导入即声明工程根覆盖（见 mdm/__init__.py：bms-core 路径依赖）
from tests_support.fixtures import (
    client,
    fake_tenant_source,
    isolate_settings,
    reset_request_context,
    service_app,
)
from tests_support.grants import grant_source

__all__ = [
    "client",
    "fake_tenant_source",
    "grant_source",
    "isolate_settings",
    "reset_request_context",
    "service_app",
]
