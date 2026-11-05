"""组织主数据服务工程级测试夹具入口（实现见 `tests_support.fixtures`，口径与工作区根一致）。"""

from tests_support.fixtures import (
    client,
    fake_tenant_source,
    isolate_settings,
    isolated_platform_db_url,
    isolated_tenant_db_url,
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
    "isolated_platform_db_url",
    "isolated_tenant_db_url",
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


def pytest_sessionstart(session: object) -> None:
    """会话起始：清空共享测试库并钉定工程根（工程级 rootdir 也要执行，口径同工作区根）。

    Args:
        session: pytest 会话对象（未使用）。
    """
    del session
    from tests_support.fixtures import prepare_shared_db_session

    prepare_shared_db_session()
