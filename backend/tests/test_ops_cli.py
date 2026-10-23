"""运维脚本（ops）CLI 用例：清单校验 / 契约快照 / 分链迁移 / 建库。"""

import runpy
import sys
import types
from pathlib import Path

import pytest
from bms_core.core.config import get_settings
from bms_core.core.exceptions import ConfigError

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
    """契约快照：导出 `deploy/contracts/mdm.json` 后可零漂移校验（退出码 0）。"""
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
    assert "platform_mdm" in out
    assert "mdm.db" in out
    assert "mdm_archive.db" in out


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_migrate_dry_run_with_tenant_codes(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """分链迁移 dry-run（租户维度）：`--code` 派生服务租户库 `mdm_demo`。"""
    _enable_sqlite_templates(monkeypatch)
    assert migrate.main(["--dry-run", "--code", "demo"]) == 0
    out = capsys.readouterr().out
    assert "tenant_mdm_demo" in out
    assert "mdm_demo.db" in out


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

    assert list(migrate.resolve_services(["mdm", "mdm"])) == ["mdm"]
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


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_db_admin_create_exists_drop_cycle(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """建库 CLI：`create` → `exists`（存在）→ `drop` 闭环，均退出码 0 且打印结果。"""
    url = f"sqlite+aiosqlite:///{tmp_path / 'mdm_cycle.db'}"
    assert db_admin.main(["create", "--url", url]) == 0
    assert "新建" in capsys.readouterr().out
    assert db_admin.main(["create", "--url", url]) == 0  # 幂等：已存在跳过
    assert "已存在（跳过）" in capsys.readouterr().out
    assert db_admin.main(["exists", "--url", url]) == 0
    assert "存在" in capsys.readouterr().out
    assert db_admin.main(["drop", "--url", url]) == 0
    assert "已删除" in capsys.readouterr().out
    assert db_admin.main(["drop", "--url", url]) == 0  # 幂等：不存在跳过
    assert "不存在（跳过）" in capsys.readouterr().out


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_db_admin_reports_config_error(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """建库 CLI：目标解析失败（`ConfigError`）→ 打印原因并退出码 1。"""

    def _raise(coro: object) -> int:
        coro.close()
        raise ConfigError("连接串非法")

    monkeypatch.setattr(db_admin, "asyncio", types.SimpleNamespace(run=_raise))
    assert db_admin.main(["exists", "--url", "sqlite://"]) == 1
    assert "连接串非法" in capsys.readouterr().out


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_db_admin_module_entry_point(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`python -m ops.db_admin` 入口按 CLI 参数执行并以退出码结束。"""
    url = f"sqlite+aiosqlite:///{tmp_path / 'mdm_entry.db'}"
    monkeypatch.delitem(sys.modules, "ops.db_admin", raising=False)
    monkeypatch.setattr(sys, "argv", ["ops.db_admin", "exists", "--url", url])
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("ops.db_admin", run_name="__main__")
    assert excinfo.value.code == 0


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_contract_snapshot_build_app_reports_package_and_factory_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """内存构建失败三态：服务包缺失 / 缺应用工厂 / 应用构建抛错，均转 `RuntimeError` 并带原因。"""

    def _missing(_name: str) -> types.ModuleType:
        raise ModuleNotFoundError("No module named 'mdm_missing'")

    monkeypatch.setattr(contract_snapshot, "import_module", _missing)
    with pytest.raises(RuntimeError, match="服务包缺失"):
        contract_snapshot.build_app("missing")

    monkeypatch.setattr(contract_snapshot, "import_module", lambda _name: types.SimpleNamespace())
    with pytest.raises(RuntimeError, match="缺少 ApplicationFactory"):
        contract_snapshot.build_app("mdm")

    class _Boom:
        def create(self, _settings: object) -> object:
            raise ValueError("起不来")

    monkeypatch.setattr(
        contract_snapshot, "import_module", lambda _name: types.SimpleNamespace(ApplicationFactory=_Boom)
    )
    with pytest.raises(RuntimeError, match="服务应用构建失败"):
        contract_snapshot.build_app("mdm")


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_contract_snapshot_export_reports_validation_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """导出：单服务契约校验失败时汇总打印并退出码 1（不写文件）。"""
    monkeypatch.setattr(contract_snapshot, "_validate", lambda record, openapi: ["契约缺 title"])
    assert contract_snapshot.export(tmp_path) == 1
    assert "契约缺 title" in capsys.readouterr().err
    assert not contract_snapshot.snapshot_path(tmp_path, SERVICE_KEY).exists()


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_contract_snapshot_export_to_stdout(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """导出 `--print`：打印生成内容（供人工比对）且退出码 0。"""
    assert contract_snapshot.export(tmp_path, to_stdout=True) == 0
    assert '"openapi"' in capsys.readouterr().out


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_contract_snapshot_check_reports_validation_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """校验：快照存在但契约校验失败时归入问题清单并退出码 1。"""
    assert contract_snapshot.export(tmp_path) == 0
    monkeypatch.setattr(contract_snapshot, "_validate", lambda record, openapi: ["契约版本不符"])
    assert contract_snapshot.check(tmp_path) == 1
    assert "契约版本不符" in capsys.readouterr().err


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_migrate_single_database_targets(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """单库模式：`--target tenant` / `--target platform` 带 `--url` 时按指定库建任务（dry-run 不建连）。"""
    url = f"sqlite+aiosqlite:///{tmp_path / 'mdm_single.db'}"
    assert migrate.main(["--target", "tenant", "--url", url, "--dry-run"]) == 0
    assert "tenant" in capsys.readouterr().out
    assert migrate.main(["--target", "platform", "--url", url, "--dry-run"]) == 0
    assert "platform_mdm" in capsys.readouterr().out


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_migrate_requires_running_service(monkeypatch: pytest.MonkeyPatch) -> None:
    """服务维度缺省解析为空（产品清单无在运服务）即明确报错，不静默空跑。"""
    monkeypatch.setattr(migrate, "local_service_keys", lambda: [])
    with pytest.raises(ConfigError, match="产品清单无在运服务"):
        migrate.resolve_services([])


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_migrate_service_tasks_without_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    """任务清单：`include_platform=False` 时只出服务租户库与归档库（按需裁剪）。"""
    _enable_sqlite_templates(monkeypatch)
    tasks = migrate.service_tasks(
        migrate.ConcurrentStableList(["mdm"]),
        migrate.ConcurrentStableList(["demo"]),
        include_platform=False,
        include_archive=True,
    )
    chain_names = [task.chain.name for task in tasks]
    assert all(not name.startswith("mdm:platform") for name in chain_names)
    assert any(name.startswith("mdm:tenant") for name in chain_names)
    assert any(name.startswith("platform:archive") for name in chain_names)


@pytest.mark.kiwi_id(KIWI_CASE_ID)
async def test_migrate_run_tasks_reports_three_outcomes(monkeypatch: pytest.MonkeyPatch) -> None:
    """执行汇总：已最新（跳过）/ 迁移完成（成功）/ 抛错（失败）三类结果均如实登记。"""
    chain = migrate.resolve_chain(migrate.build_chain_name("mdm", migrate.DATASOURCE_PLATFORM))
    tasks = migrate.ConcurrentStableList(
        [migrate.MigrationTask(chain=chain, label="mdm", url="sqlite+aiosqlite:///mdm_run.db")]
    )
    monkeypatch.setattr(migrate, "head_revision", lambda _chain: "rev_head")

    async def _current(url: str, schema: str | None = None) -> str:
        return "rev_head"

    monkeypatch.setattr(migrate, "current_revision", _current)
    summary = await migrate.run_tasks(tasks)
    assert summary.skipped == ("mdm",)

    async def _stale(url: str, schema: str | None = None) -> str:
        return "rev_old"

    upgrades: list[str] = []
    monkeypatch.setattr(migrate, "current_revision", _stale)
    monkeypatch.setattr(migrate, "upgrade_chain", lambda _chain, _url, schema=None: upgrades.append(_url))
    summary = await migrate.run_tasks(tasks)
    assert summary.succeeded == ("mdm",) and upgrades

    async def _boom(url: str, schema: str | None = None) -> str:
        raise RuntimeError("连不上库")

    monkeypatch.setattr(migrate, "current_revision", _boom)
    summary = await migrate.run_tasks(tasks)
    assert summary.failed == ("mdm",)


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_migrate_module_entry_point(monkeypatch: pytest.MonkeyPatch) -> None:
    """`python -m ops.migrate` 入口按 CLI 参数执行并以退出码结束。"""
    monkeypatch.delitem(sys.modules, "ops.migrate", raising=False)
    monkeypatch.setattr(sys, "argv", ["ops.migrate", "--dry-run"])
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("ops.migrate", run_name="__main__")
    assert excinfo.value.code == 0


@pytest.mark.kiwi_id(KIWI_CASE_ID)
def test_contract_snapshot_module_entry_point(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`python -m ops.contract_snapshot` 入口按 CLI 参数执行并以退出码结束。"""
    assert contract_snapshot.export(tmp_path) == 0
    monkeypatch.delitem(sys.modules, "ops.contract_snapshot", raising=False)
    monkeypatch.setattr(sys, "argv", ["ops.contract_snapshot", "check", "--root", str(tmp_path)])
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("ops.contract_snapshot", run_name="__main__")
    assert excinfo.value.code == 0
