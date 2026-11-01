"""组织主数据服务工程级测试夹具入口（实现见 `tests_support.fixtures`，口径与工作区根一致）。"""

from tests_support.fixtures import (
    client,
    fake_tenant_source,
    isolate_settings,
    ns,
    platform_db_prepare,
    reset_request_context,
    service_app,
    shared_platform_db_url,
    shared_platform_engine,
    shared_tenant_db_url,
    shared_tenant_engine,
    tenant_db_prepare,
)
from tests_support.grants import grant_source

__all__ = [
    "client",
    "fake_tenant_source",
    "grant_source",
    "isolate_settings",
    "ns",
    "platform_db_prepare",
    "reset_request_context",
    "service_app",
    "shared_platform_db_url",
    "shared_platform_engine",
    "shared_tenant_db_url",
    "shared_tenant_engine",
    "tenant_db_prepare",
]
