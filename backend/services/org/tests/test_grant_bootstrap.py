"""启动期授权视图引导用例（07B `03_01`）

覆盖详细设计 §6 用例 20 的 mdm 侧：装配期登记**远端来源**（授权权威在平台库）+ 启动钩子预热
本服务承载域（`org`）的 `provider` 视图；平台未就绪时**告警降级不拒启**，被收编端点首访仍
fail-closed（`CatalogError`）。
"""

import pytest
from bms_core.collaboration import ensure_grant_view
from bms_core.collaboration.bootstrap import (
    GRANT_VIEW_DEGRADED_FLAG,
    bootstrap_remote_capability_grants,
)
from bms_core.core.exceptions import CatalogError
from fastapi import FastAPI


def test_startup_hooks_include_grant_bootstrap(service_app: FastAPI) -> None:
    """启动钩子清单含授权视图引导（顺序上晚于装配，与声明上报 / 建表解耦）。"""
    hooks = service_app.state.startup_hooks

    assert bootstrap_remote_capability_grants in hooks


async def test_startup_degrades_when_platform_unreachable(service_app: FastAPI) -> None:
    """平台不可达（单测 `service_client` 为 null 占位）：降级但不拒启，首访 fail-closed。"""
    assert getattr(service_app.state, GRANT_VIEW_DEGRADED_FLAG) is True

    with pytest.raises(CatalogError):
        await ensure_grant_view(provider="org")
