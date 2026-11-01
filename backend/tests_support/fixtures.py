"""跨服务测试共用夹具：配置环境隔离 + 假租户源 + 应用 / 客户端。

夹具以模块级函数定义，各 `conftest.py` 直接导入即可被 pytest 发现（conftest 命名空间发现夹具），
避免在工作区根与服务工程各写一份。
"""

import os
from collections.abc import AsyncIterator, Callable, Iterator
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
from bms_core.testing.fixtures import (
    ns,
    shared_platform_db_url,
    shared_platform_engine,
    shared_tenant_db_url,
    shared_tenant_engine,
)
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from mdm.main import ApplicationFactory
from tests_support.tenant_source import install_fake_tenant_source

__all__ = [
    "client",
    "fake_tenant_source",
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

_KEPT_ENV_PREFIXES = ("BMS_TEST_", "BMS_BACKEND_ROOT")
"""清环境变量时**保留**的键前缀（`BMS_TEST_` 是测试专用前缀；`BMS_BACKEND_ROOT` 是工程根定位覆盖）。"""


@pytest.fixture(autouse=True)
def isolate_settings(
    monkeypatch: pytest.MonkeyPatch, shared_platform_db_url: str, shared_tenant_db_url: str
) -> Iterator[None]:
    """隔离配置：清 `BMS_` 环境变量 → 固定 test 环境 → **共享测试库** → 关闭外部真实实现。

    注意 `BMS_BACKEND_ROOT` **必须保留**：它由 `mdm` 包导入期声明（路径依赖接入 bms 源码后，
    基座按它定位本仓 `config.toml` / 迁移链）。清掉会让配置定位回落到 bms 仓的 `config.toml`
    （Redis 幂等存储 / 缓存等真实实现被启用），用例随后连不上 Redis 而报 503。

    **单库化（04-6-2 批 5）**：平台库 / 租户库一律指向 `.cache/test/{platform,tenant}.db`
    （准备集 `tests_support.shared_db` 一次性建表播种），用例靠命名空间叠加、不再每例一份临时库；
    `own_db` 白名单文件（迁移 / 运维 CLI / 播种编排）显式依赖 `isolated_*_db_url` 走独占库。

    Args:
        monkeypatch: pytest monkeypatch 夹具。
        shared_platform_db_url: 共享平台库连接串（会话级）。
        shared_tenant_db_url: 共享租户库连接串（会话级）。

    Yields:
        None: 用例运行期。
    """
    for key in list(os.environ):
        if key.startswith("BMS_") and not key.startswith(_KEPT_ENV_PREFIXES):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("BMS_ENV", "test")
    # 共享库：清 sqlite_dir 基址与连接串模板，使显式 URL 生效
    monkeypatch.setenv("BMS_DATABASE__SQLITE_DIR", "")
    monkeypatch.setenv("BMS_DATABASE__PLATFORM__URL_TEMPLATE", "")
    monkeypatch.setenv("BMS_DATABASE__TENANTS__URL_TEMPLATE", "")
    monkeypatch.setenv("BMS_DATABASE__PLATFORM__URL", shared_platform_db_url)
    monkeypatch.setenv("BMS_DATABASE__TENANTS__URL", shared_tenant_db_url)
    # 单测不走上报 / 拉取注册表的启动链（基座 `registry.register_on_startup` 文档口径：单测置 false）。
    # 生产 / 部署态仍为 true：启动期上报本仓清单并投影平台权威快照，失败拒启。
    monkeypatch.setenv("BMS_REGISTRY__REGISTER_ON_STARTUP", "false")
    for key in _PROVIDER_KEYS:
        monkeypatch.setenv(f"BMS_{key}__PROVIDER", "")
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def platform_db_prepare() -> Callable[[str], None]:
    """共享平台库准备集回调（mdm 侧实现，见 `tests_support.shared_db`）。

    Returns:
        Callable[[str], None]: 接受连接串的准备函数。
    """
    from tests_support.shared_db import prepare_platform

    return prepare_platform


@pytest.fixture(scope="session")
def tenant_db_prepare() -> Callable[[str], None]:
    """共享租户库准备集回调（同上）。

    Returns:
        Callable[[str], None]: 接受连接串的准备函数。
    """
    from tests_support.shared_db import prepare_tenant

    return prepare_tenant


@pytest.fixture
def isolated_platform_db_url(tmp_path: Path, platform_db_prepare: Callable[[str], None]) -> str:
    """白名单（`own_db`）用例专用**独占**平台库：每用例一份 tmp 库 + 播种。

    Args:
        tmp_path: 用例级临时目录。
        platform_db_prepare: 共享平台库准备集（种子租户与主键对齐同源）。

    Returns:
        str: 独占平台库连接串。
    """
    url = f"sqlite+aiosqlite:///{tmp_path / 'mdm_platform_isolated.db'}"
    platform_db_prepare(url)
    return url


@pytest.fixture
def isolated_tenant_db_url(tmp_path: Path, tenant_db_prepare: Callable[[str], None]) -> str:
    """白名单（`own_db`）用例专用**独占**租户库：每用例一份 tmp 库 + 参数种子。

    Args:
        tmp_path: 用例级临时目录。
        tenant_db_prepare: 共享租户库准备集。

    Returns:
        str: 独占租户库连接串。
    """
    url = f"sqlite+aiosqlite:///{tmp_path / 'mdm_tenant_isolated.db'}"
    tenant_db_prepare(url)
    return url


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
