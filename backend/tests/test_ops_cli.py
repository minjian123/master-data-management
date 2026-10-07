"""运维脚本（ops）CLI 用例：清单校验 / 契约快照 / 分链迁移 / 建库。"""

from pathlib import Path

import pytest
from bms_core.core.config import get_settings

from ops import check_modules, contract_snapshot, db_admin, migrate
from services.module_registry import MDM_SERVICE_RECORDS, SERVICE_KEY

KIWI_CASE_ID = 2253
"""Kiwi TCMS 策展用例编号（mdm 阶段一 01_01）。"""


def _enable_sqlite_templates(monkeypatch: pytest.MonkeyPatch) -> None:
    """开启 SQLite 连接串模板（贴近 dev 口径：按服务 / 租户派生库文件）。

    Args:
        monkeypatch: pytest monkeypatch 夹具。
    """
    monkeypatch.setenv("BMS_DATABASE__PLATFORM__URL_TEMPLATE", "sqlite+aiosqlite:///./mdm_{service}.db")
    monkeypatch.setenv("BMS_DATABASE__TENANTS__URL_TEMPLATE", "sqlite+aiosqlite:///./mdm_{service}_{tenant}.db")
    get_settings.cache_clear()


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_check_modules_cli_passes(capsys: pytest.CaptureFixture[str]) -> None:
    """清单校验 CLI：离线校验通过（退出码 0）且打印产品清单与平台侧对账范围。"""
    assert check_modules.main([]) == 0
    assert check_modules.main(["--offline"]) == 0
    assert "校验通过" in capsys.readouterr().out


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_check_modules_parser_defaults() -> None:
    """CLI 参数：`--offline` 为口径兼容开关（mdm 产品侧恒离线）。"""
    args = check_modules.build_parser().parse_args(["--offline"])
    assert args.offline is True


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_contract_snapshot_export_and_check(tmp_path: Path) -> None:
    """契约快照：导出 `deploy/contracts/org.json` 后可零漂移校验（退出码 0）。"""
    assert contract_snapshot.export(tmp_path) == 0
    snapshot = contract_snapshot.snapshot_path(tmp_path, SERVICE_KEY)
    assert snapshot.is_file()
    assert contract_snapshot.check(tmp_path) == 0
    assert contract_snapshot.enabled_local_records() == MDM_SERVICE_RECORDS


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_contract_snapshot_detects_drift_and_missing(tmp_path: Path) -> None:
    """契约快照：缺件与漂移均被检出（退出码 1）。"""
    assert contract_snapshot.check(tmp_path) == 1  # 无快照文件 → 缺件
    assert contract_snapshot.export(tmp_path) == 0
    contract_snapshot.snapshot_path(tmp_path, SERVICE_KEY).write_text("{}\n", encoding="utf-8")
    assert contract_snapshot.check(tmp_path) == 1  # 内容漂移


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_contract_snapshot_cli(tmp_path: Path) -> None:
    """契约快照 CLI：`export` / `check` 子命令可执行。"""
    assert contract_snapshot.main(["export", "--root", str(tmp_path)]) == 0
    assert contract_snapshot.main(["check", "--root", str(tmp_path)]) == 0


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_contract_snapshot_build_app_imports_service_package() -> None:
    """内存构建：按 mdm 命名规则定位服务包并构造应用（不启 lifespan、不连库）。"""
    app = contract_snapshot.build_app(SERVICE_KEY)
    assert app.title == "mdm 组织主数据服务"


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_migrate_dry_run_lists_mdm_databases(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """分链迁移 dry-run：列出平台服务库与归档库（库名前缀 `mdm`），不建连。"""
    _enable_sqlite_templates(monkeypatch)
    assert migrate.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "platform_org" in out
    assert "mdm_org.db" in out
    assert "mdm_archive.db" in out


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_migrate_dry_run_with_tenant_codes(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """分链迁移 dry-run（租户维度）：`--code` 派生服务租户库 `mdm_org_demo`。"""
    _enable_sqlite_templates(monkeypatch)
    assert migrate.main(["--dry-run", "--code", "demo"]) == 0
    out = capsys.readouterr().out
    assert "tenant_org_demo" in out
    assert "mdm_org_demo.db" in out


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_migrate_skips_chains_without_scripts(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """分链迁移实跑：本期 org 链无脚本 → 逐目标「无脚本（跳过）」且退出码 0（不建连、不建表）。"""
    _enable_sqlite_templates(monkeypatch)
    assert migrate.main([]) == 0
    assert "无脚本（跳过）" in capsys.readouterr().out


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_migrate_target_platform_and_archive(monkeypatch: pytest.MonkeyPatch) -> None:
    """分链迁移目标解析：`platform` / `archive` 目标清单可构建（dry-run）。"""
    _enable_sqlite_templates(monkeypatch)
    assert migrate.main(["--dry-run", "--target", "platform"]) == 0
    assert migrate.main(["--dry-run", "--target", "archive"]) == 0


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_migrate_tenant_single_database_requires_url(capsys: pytest.CaptureFixture[str]) -> None:
    """单库模式：`--target tenant` 缺 `--url` 即明确报错（退出码 1）。"""
    assert migrate.main(["--target", "tenant"]) == 1
    assert "需显式 `--url`" in capsys.readouterr().out


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_migrate_tenants_target_requires_codes() -> None:
    """租户目标：`--target tenants` 缺 `--code` 即明确报错（退出码 1）。"""
    assert migrate.main(["--target", "tenants"]) == 1


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_migrate_resolve_services_explicit_and_default() -> None:
    """服务维度：显式指定保序去重；缺省取本产品在运服务。"""

    assert list(migrate.resolve_services(["org", "org"])) == ["org"]
    assert list(migrate.resolve_services([])) == [SERVICE_KEY]


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_db_admin_dry_run_describes_target(capsys: pytest.CaptureFixture[str]) -> None:
    """建库 CLI：dry-run 解析目标并脱敏打印（不建连）。"""
    assert db_admin.main(["exists", "--url", "sqlite+aiosqlite:////tmp/mdm_migrcheck.db", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "dry-run" in out
    assert "mdm_migrcheck" in out


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_db_admin_exists_on_temporary_sqlite(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """建库 CLI：`exists` 对临时 SQLite 库判定（不存在 → 退出码 0 且提示不存在）。"""
    url = f"sqlite+aiosqlite:///{tmp_path / 'mdm_migrcheck.db'}"
    assert db_admin.main(["exists", "--url", url]) == 0
    assert "不存在" in capsys.readouterr().out
