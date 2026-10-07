"""配置分层、库名前缀派生与服务身份回写（配置加载可证）。"""

import pytest
from bms_core.core.config import get_settings
from bms_core.db.keys import archive_database_name, platform_database_name, tenant_database_name
from fastapi import FastAPI

KIWI_CASE_ID = 2253
"""Kiwi TCMS 策展用例编号（mdm 阶段一 01_01）。"""


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_minimal_config_loads_with_mdm_name_prefix() -> None:
    """最小差异配置可加载：应用名就位、库名前缀 `mdm`、服务标识留空待服务包声明回写。"""
    settings = get_settings()
    assert settings.app.name == "mdm 主数据管理"
    assert settings.database.name_prefix == "mdm"
    assert settings.app.service == ""


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_database_names_derive_from_prefix() -> None:
    """库名派生：平台服务库 / 服务租户库 / 归档库一律取 `[database].name_prefix`（mdm）。"""
    prefix = get_settings().database.name_prefix
    assert platform_database_name("org", prefix=prefix) == "mdm_org"
    assert tenant_database_name("org", "demo", prefix=prefix) == "mdm_org_demo"
    assert archive_database_name(prefix=prefix) == "mdm_archive"


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_test_env_overlay_disables_auto_create() -> None:
    """环境覆盖生效：test 环境关闭开发库自动建表（结构真值走迁移）。"""
    assert get_settings().app.env == "test"
    assert get_settings().database.auto_create is False


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_dev_env_overlay_enables_debug_and_auto_create(monkeypatch: pytest.MonkeyPatch) -> None:
    """环境覆盖生效：dev 覆盖开启调试与开发库自动建表（未显式覆盖项回落基线值）。"""
    monkeypatch.setenv("BMS_ENV", "dev")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.app.env == "dev"
    assert settings.app.debug is True
    assert settings.database.auto_create is True
    assert settings.database.name_prefix == "mdm"


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_env_var_overrides_toml(monkeypatch: pytest.MonkeyPatch) -> None:
    """优先级：`BMS_` 环境变量覆盖 TOML 配置（连接串 / 库名前缀一律经配置读取，不写死代码）。"""
    monkeypatch.setenv("BMS_DATABASE__NAME_PREFIX", "mdmx")
    get_settings.cache_clear()
    assert get_settings().database.name_prefix == "mdmx"
    assert platform_database_name("org", prefix=get_settings().database.name_prefix) == "mdmx_org"


@pytest.mark.kiwi_id(KIWI_CASE_ID)
async def test_service_identity_written_back_to_settings(service_app: FastAPI) -> None:
    """服务身份回写：应用装配后服务标识为 `org`（链名 / 库名 / 探针响应的共同来源）。"""
    assert service_app.state.service_identity.name == "org"
    assert get_settings().app.service == "org"


@pytest.mark.kiwi_id(KIWI_CASE_ID)
async def test_event_domains_include_product_domain(service_app: FastAPI) -> None:
    """事件契约域取应用级视图：产品服务自有事件域 `org` 随注入记录生效（01_03 事件发布前置）。"""
    assert "org" in service_app.state.module_registry.event_domains()
