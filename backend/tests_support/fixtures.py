"""跨服务测试共用夹具：配置环境隔离 + 假租户源 + 应用 / 客户端。

夹具以模块级函数定义，各 `conftest.py` 直接导入即可被 pytest 发现（conftest 命名空间发现夹具），
避免在工作区根与服务工程各写一份。
"""

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from bms_core.core.config import Settings, get_settings
from bms_core.core.context import (
    current_client_ip,
    current_request_id,
    current_tenant,
    current_tenant_context_var,
    current_trace_id,
    current_user_id,
)
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from mdm_org.main import ApplicationFactory
from tests_support.tenant_source import install_fake_tenant_source

__all__ = [
    "client",
    "fake_tenant_source",
    "isolate_settings",
    "reset_request_context",
    "service_app",
]

_PROVIDER_KEYS = (
    "METRICS",
    "TRACER",
    "SERVICE_CLIENT",
    "SESSION_STORE",
    "RATE_LIMITER",
    "CAPTCHA",
    "MASKING",
)
"""需关闭真实实现的外部 provider 段（单测不引入全局导出线程、不真实外呼、不连 Redis）。"""


@pytest.fixture(autouse=True)
def isolate_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """隔离配置：清 `BMS_` 环境变量 → 固定 test 环境 → 临时 SQLite 库 → 关闭外部真实实现。

    Args:
        monkeypatch: pytest monkeypatch 夹具。
        tmp_path: 用例级临时目录（临时 SQLite 库落此，不写仓库、不依赖平台租户注册库）。

    Yields:
        None: 用例运行期。
    """
    for key in list(os.environ):
        if key.startswith("BMS_") and not key.startswith("BMS_TEST_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("BMS_ENV", "test")
    # 临时库：清 sqlite_dir 基址与连接串模板，使显式 URL 生效
    monkeypatch.setenv("BMS_DATABASE__SQLITE_DIR", "")
    monkeypatch.setenv("BMS_DATABASE__PLATFORM__URL_TEMPLATE", "")
    monkeypatch.setenv("BMS_DATABASE__TENANTS__URL_TEMPLATE", "")
    monkeypatch.setenv("BMS_DATABASE__PLATFORM__URL", f"sqlite+aiosqlite:///{tmp_path / 'mdm_platform.db'}")
    monkeypatch.setenv("BMS_DATABASE__TENANTS__URL", f"sqlite+aiosqlite:///{tmp_path / 'mdm_tenant_demo.db'}")
    for key in _PROVIDER_KEYS:
        monkeypatch.setenv(f"BMS_{key}__PROVIDER", "")
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def fake_tenant_source(monkeypatch: pytest.MonkeyPatch) -> None:
    """租户源替身：应用装配时改注入 `FakeTenantSource`（单测不连租户注册库）。

    Args:
        monkeypatch: pytest monkeypatch 夹具。
    """
    install_fake_tenant_source(monkeypatch)


@pytest.fixture(autouse=True)
def reset_request_context() -> Iterator[None]:
    """用例结束后复位请求上下文（链路 / 请求 / 来源 / 租户 / 用户），防跨用例污染。

    Yields:
        None: 用例运行期。
    """
    yield
    current_trace_id.set(None)
    current_request_id.set(None)
    current_client_ip.set(None)
    current_tenant.set(None)
    current_tenant_context_var.set(None)
    current_user_id.set(None)


@pytest.fixture
async def service_app() -> AsyncIterator[FastAPI]:
    """本服务应用实例夹具（经 lifespan 装配；供应用级断言与 `client` 共用）。

    Yields:
        FastAPI: 应用实例。
    """
    app = ApplicationFactory().create(None)
    async with app.router.lifespan_context(app):
        yield app


@pytest.fixture
async def client(service_app: FastAPI) -> AsyncIterator[AsyncClient]:
    """ASGITransport 异步客户端夹具（复用 `service_app`）。

    Args:
        service_app: 上一夹具构造的应用实例。

    Yields:
        AsyncClient: 内存 ASGI 客户端。
    """
    async with AsyncClient(transport=ASGITransport(app=service_app), base_url="http://test") as c:
        yield c
