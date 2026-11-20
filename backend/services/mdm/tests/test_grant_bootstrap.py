"""启动期授权视图引导用例（07B `03_01`）

覆盖 mdm 侧三件事：① 生产装配的启动钩子清单含远端授权引导；② 单测（无平台对端）不登记该钩子，
授权视图改由静态来源提供；③ 平台不可达时引导**拒启**（`CatalogError`），被收编端点首访同样
fail-closed。

口径：07B 拍板「启动期失败一律拒启，不带病启动」——早前「告警降级 + 置 `grant_view_degraded`」
的写法已废弃（降级标记随之移除）。
"""

from types import SimpleNamespace

import pytest
from bms_core.collaboration import ensure_grant_view
from bms_core.collaboration.bootstrap import bootstrap_remote_capability_grants
from bms_core.core.exceptions import CatalogError
from fastapi import FastAPI

from mdm import main as main_module
from mdm.main import ApplicationFactory


def test_startup_hooks_include_grant_bootstrap(monkeypatch: pytest.MonkeyPatch) -> None:
    """生产装配：启动钩子清单含授权视图引导（顺序上晚于装配，与声明上报 / 建表解耦）。

    直接替换工厂里读取的配置单例（不切真实 `BMS_ENV=prod`，避免触发生产必填键校验）。
    """
    monkeypatch.setattr(main_module, "get_settings", lambda: SimpleNamespace(app=SimpleNamespace(env="prod")))
    hooks = ApplicationFactory().startup_hooks()
    assert bootstrap_remote_capability_grants in hooks


def test_startup_hooks_skipped_in_test_env() -> None:
    """测试态无平台对端：不登记该钩子（授权视图由 `tests_support/grants.py` 静态来源提供）。"""
    assert list(ApplicationFactory().startup_hooks()) == []


async def test_startup_rejects_when_platform_unreachable(service_app: FastAPI) -> None:
    """平台不可达：引导抛 `CatalogError` 拒启；被收编端点首访仍 fail-closed。"""
    with pytest.raises(CatalogError):
        await bootstrap_remote_capability_grants(service_app)

    with pytest.raises(CatalogError):
        await ensure_grant_view(provider="mdm")
