"""工作区根测试夹具入口（实现见 `tests_support.fixtures`；pytest 以 conftest 命名空间发现夹具）。"""

import mdm  # noqa: F401  # 导入即声明工程根覆盖（见 mdm/__init__.py：bms-core 路径依赖）
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
    """会话起始：清空共享测试库并钉定工程根（口径见 `prepare_shared_db_session`）。

    Args:
        session: pytest 会话对象（未使用）。
    """
    del session
    from tests_support.fixtures import prepare_shared_db_session

    prepare_shared_db_session()
