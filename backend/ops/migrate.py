"""产品侧分链迁移 CLI：按「服务 × 数据源 × 租户」遍历执行 Alembic 迁移（幂等）。

用法：

```bash
cd backend
uv run python -m ops.migrate --dry-run                      # 清单预演（不建连）
uv run python -m ops.migrate                                # 各在运服务 × 平台服务库 + 归档库
uv run python -m ops.migrate --target platform              # 仅平台服务库
uv run python -m ops.migrate --code demo --code acme        # 追加服务租户库（库键 tenant_org_{code}）
uv run python -m ops.migrate --target tenant --url "dm+dmPython://SYSDBA:pass@host:5236" --schema MDM_MIGRCHECK
```

- **服务维度**：缺省取本产品清单在运服务（`local_service_keys()`）；`--service` 可重复显式指定；
- **租户维度**：`--code`（可重复，库名基 = 编码）。**不读租户注册库**——`platform_tenant` 库归平台
  `tenant` 服务，产品侧不跨服务直读；租户全集编排由平台侧负责（bms `ops.migrate_tenants`）；
- **链映射**：平台服务库 `mdm_{service}` → 链 `{service}:platform`；服务租户库 `mdm_{service}_{code}`
  → 链 `{service}:tenant`；归档库 `mdm_archive` → 链 `platform:archive`（归档库不服务化）；
- **执行**：逐库经基座 `upgrade_chain`（`command.upgrade(cfg, "head")`）；
- **幂等**：目标 `alembic_version` 已为链 head → 「已是最新（跳过）」；链无脚本 → 「无脚本（跳过）」；
- **失败不中断**：单库失败记 ERROR 并继续，末尾汇总；存在失败退出码 1；
- **`--dry-run`**：仅打印清单（连接串脱敏）与库数量统计，不建连、不迁移。
"""

import argparse
import asyncio
from collections import Counter
from dataclasses import dataclass

from bms_core.core.concurrent import ConcurrentStableList
from bms_core.core.config import Settings, get_settings
from bms_core.core.exceptions import ConfigError
from bms_core.core.objects import BaseValueObject
from bms_core.db.engine import EngineFactory
from bms_core.db.keys import build_platform_db_key, build_tenant_db_key
from bms_core.db.migration import (
    DATASOURCE_ARCHIVE,
    DATASOURCE_PLATFORM,
    DATASOURCE_TENANT,
    MigrationChain,
    archive_chain,
    build_chain_name,
    current_revision,
    head_revision,
    resolve_chain,
    upgrade_chain,
)
from sqlalchemy.engine import make_url

from services.module_registry import local_service_keys

TARGETS = ("all", "platform", "tenants", "tenant", "archive")


@dataclass(frozen=True)
class MigrationTask(BaseValueObject):
    """单个迁移任务（链 / 展示名 / 连接串 / 模式）。"""

    chain: MigrationChain
    label: str
    url: str
    schema: str = ""


@dataclass(frozen=True)
class MigrationSummary(BaseValueObject):
    """批量迁移结果汇总（成功 / 跳过 / 失败）。"""

    succeeded: tuple[str, ...]
    skipped: tuple[str, ...]
    failed: tuple[str, ...]

    @property
    def exit_code(self) -> int:
        """退出码（存在失败为 1）。

        Returns:
            int: 0 全成功 / 1 存在失败。
        """
        return 1 if self.failed else 0


def build_parser() -> argparse.ArgumentParser:
    """构建命令行解析器。

    Returns:
        argparse.ArgumentParser: 解析器。
    """
    parser = argparse.ArgumentParser(description="产品侧分链迁移（服务 × 数据源 × 租户；幂等）")
    parser.add_argument("--target", default="all", choices=TARGETS, help="迁移目标（缺省 all）")
    parser.add_argument("--service", action="append", default=[], help="服务标识（可重复；缺省全部在运服务）")
    parser.add_argument("--code", action="append", default=[], help="租户编码（可重复；库键 tenant_{service}_{code}）")
    parser.add_argument("--url", default="", help="显式连接串（单库模式；含密码，禁止写入日志）")
    parser.add_argument("--schema", default="", help="达梦目标模式（仅达梦生效）")
    parser.add_argument("--dry-run", action="store_true", help="仅打印清单（不建连）")
    return parser


def _masked(url: str) -> str:
    """连接串脱敏（隐藏密码）。

    Args:
        url: 连接串。

    Returns:
        str: 脱敏连接串。
    """
    return make_url(url).render_as_string(hide_password=True)


def resolve_services(requested: list[str]) -> ConcurrentStableList[str]:
    """解析服务维度（显式指定保序去重；缺省取本产品在运服务）。

    Args:
        requested: 命令行指定的服务标识列表。

    Returns:
        ConcurrentStableList[str]: 服务标识列表。

    Raises:
        ConfigError: 缺省解析结果为空。
    """
    if requested:
        return ConcurrentStableList(dict.fromkeys(requested))
    services = ConcurrentStableList(local_service_keys())
    if not services:
        raise ConfigError("产品清单无在运服务（service_key 非空且 status=enabled），请显式 --service")
    return services


def service_tasks(
    services: ConcurrentStableList[str],
    codes: ConcurrentStableList[str],
    *,
    settings: Settings | None = None,
    include_platform: bool = True,
    include_tenants: bool = True,
    include_archive: bool = False,
) -> ConcurrentStableList[MigrationTask]:
    """构建「服务 × 数据源 × 租户」迁移任务清单。

    Args:
        services: 服务标识列表。
        codes: 租户编码列表（库名基 = 编码）。
        settings: 应用配置；None 取全局配置单例。
        include_platform: 是否包含各服务的平台服务库。
        include_tenants: 是否包含各服务的租户库。
        include_archive: 是否包含归档库。

    Returns:
        ConcurrentStableList[MigrationTask]: 任务清单（保序：平台 → 各服务租户 → 归档）。
    """
    resolved = settings or get_settings()
    factory = EngineFactory(resolved, allow_cross_service=True)  # 运维通道：批量迁移按各服务库执行
    tasks: ConcurrentStableList[MigrationTask] = ConcurrentStableList()
    for service in services:
        if include_platform:
            chain = resolve_chain(build_chain_name(service, DATASOURCE_PLATFORM))
            tasks.add(
                MigrationTask(
                    chain=chain,
                    label=build_platform_db_key(service),
                    url=factory.resolved_url(build_platform_db_key(service)),
                )
            )
        if not include_tenants:
            continue
        for code in codes:
            chain = resolve_chain(build_chain_name(service, DATASOURCE_TENANT))
            key = build_tenant_db_key(code, service=service)
            tasks.add(MigrationTask(chain=chain, label=key, url=factory.resolved_url(key)))
    if include_archive:
        tasks.add(MigrationTask(chain=archive_chain(), label="archive", url=factory.resolved_url("archive")))
    return tasks


def build_tasks(args: argparse.Namespace) -> ConcurrentStableList[MigrationTask]:
    """按命令行参数构建迁移任务清单。

    Args:
        args: 命令行参数。

    Returns:
        ConcurrentStableList[MigrationTask]: 任务清单。

    Raises:
        ConfigError: 目标与参数组合非法。
    """
    settings = get_settings()
    factory = EngineFactory(settings, allow_cross_service=True)
    services = resolve_services(args.service)
    codes = ConcurrentStableList(dict.fromkeys(args.code))

    if args.target == "tenant":
        if not args.url:
            raise ConfigError("`--target tenant` 需显式 `--url`（单库模式：演练 / 指定库）")
        service = services[0]
        chain = resolve_chain(build_chain_name(service, DATASOURCE_TENANT))
        return ConcurrentStableList([MigrationTask(chain=chain, label="tenant", url=args.url, schema=args.schema)])

    if args.target == "archive":
        url = args.url or factory.resolved_url("archive")
        return ConcurrentStableList(
            [MigrationTask(chain=archive_chain(), label="archive", url=url, schema=args.schema)]
        )

    if args.target == "platform":
        if args.url:  # 单库模式（演练）：指定服务的平台服务库
            service = services[0]
            chain = resolve_chain(build_chain_name(service, DATASOURCE_PLATFORM))
            return ConcurrentStableList(
                [MigrationTask(chain=chain, label=build_platform_db_key(service), url=args.url, schema=args.schema)]
            )
        return service_tasks(services, ConcurrentStableList(), settings=settings, include_tenants=False)

    if args.target == "tenants" and not codes:
        raise ConfigError("`--target tenants` 需 --code（可重复）指定租户；仅迁移平台服务库请用 --target platform")
    return service_tasks(
        services,
        codes,
        settings=settings,
        include_platform=args.target == "all",
        include_tenants=bool(codes),
        include_archive=args.target == "all",
    )


async def run_tasks(tasks: ConcurrentStableList[MigrationTask]) -> MigrationSummary:
    """逐库执行迁移（幂等；单库失败不中断）。

    Args:
        tasks: 任务清单。

    Returns:
        MigrationSummary: 结果汇总。
    """
    succeeded: ConcurrentStableList[str] = ConcurrentStableList()
    skipped: ConcurrentStableList[str] = ConcurrentStableList()
    failed: ConcurrentStableList[str] = ConcurrentStableList()
    for task in tasks:
        chain = task.chain
        head = head_revision(chain)
        if head is None:
            skipped.add(task.label)
            print(f"[migrate] {chain.name} {task.label} → 无脚本（跳过）")
            continue
        try:
            current = await current_revision(task.url, schema=task.schema)
            if current == head:
                skipped.add(task.label)
                print(f"[migrate] {chain.name} {task.label} → 已是最新（跳过）")
                continue
            await asyncio.to_thread(upgrade_chain, chain, task.url, schema=task.schema)
        except Exception as exc:  # 单库失败不中断整批
            failed.add(task.label)
            print(f"[migrate] {chain.name} {task.label} → 失败：{type(exc).__name__}: {exc}")
            continue
        succeeded.add(task.label)
        print(f"[migrate] {chain.name} {task.label} → 迁移完成（{current or '未迁移'} → {head}）")
    return MigrationSummary(succeeded=tuple(succeeded), skipped=tuple(skipped), failed=tuple(failed))


def _counts(tasks: ConcurrentStableList[MigrationTask]) -> str:
    """库数量统计（按数据源类别）。

    Args:
        tasks: 任务清单。

    Returns:
        str: 统计文案（如「平台服务库 1 / 归档库 1」）。
    """
    labels = {
        DATASOURCE_PLATFORM: "平台服务库",
        DATASOURCE_TENANT: "服务租户库",
        DATASOURCE_ARCHIVE: "归档库",
    }
    counts = Counter(task.chain.datasource for task in tasks)
    detail = "、".join(f"{labels.get(name, name)} {count}" for name, count in sorted(counts.items()))
    return f"共 {len(tasks)} 个目标（{detail}）"


async def run(args: argparse.Namespace) -> int:
    """执行批量迁移。

    Args:
        args: 命令行参数。

    Returns:
        int: 退出码（存在失败为 1）。
    """
    tasks = build_tasks(args)
    print(f"[migrate] 待迁移 {len(tasks)} 个目标（target={args.target}）")
    for task in tasks:
        suffix = f" schema={task.schema}" if task.schema else ""
        print(f"[migrate] {task.chain.name:<22} {task.label:<28} {_masked(task.url)}{suffix}")
    if args.dry_run:
        print(f"[migrate] 库数量：{_counts(tasks)}")
        print("[migrate] dry-run：不建连、不迁移")
        return 0
    summary = await run_tasks(tasks)
    print(
        f"[migrate] 汇总：成功 {len(summary.succeeded)}、跳过 {len(summary.skipped)}、失败 {len(summary.failed)}"
        + (f"（失败：{', '.join(summary.failed)}）" if summary.failed else "")
    )
    print(f"[migrate] 库数量：{_counts(tasks)}")
    return summary.exit_code


def main(argv: ConcurrentStableList[str] | None = None) -> int:
    """入口。

    Args:
        argv: 命令行参数。

    Returns:
        int: 退出码。
    """
    args = build_parser().parse_args(argv)
    try:
        return asyncio.run(run(args))
    except ConfigError as exc:
        print(f"[migrate] 失败：{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
