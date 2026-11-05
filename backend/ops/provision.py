"""服务库建库编排（首次部署）：按配置派生「平台服务库 / 服务租户库 / 归档库」并幂等建库。

用法：

```bash
cd backend
uv run python -m ops.provision --dry-run                    # 只列清单（不建连）
uv run python -m ops.provision                               # 建平台服务库 + 归档库
uv run python -m ops.provision --code demo --code acme       # 追加服务租户库（mdm_demo / mdm_acme）
uv run python -m ops.provision --service mdm --code demo      # 显式指定服务
```

- **库名单一来源**：一律经基座 `bms_core.db.keys` 派生（平台服务库 `mdm`、租户库 `mdm_{code}`、
  归档库 `mdm_archive`），不在本脚本拼字符串；
- **连接串取源**：与 `ops.migrate` 同口径——`EngineFactory(allow_cross_service=True).resolved_url(db_key)`，
  密码经配置 / 环境变量注入，日志只打脱敏连接串；
- **幂等**：已存在即跳过（`create_database` 语义），可重复执行；
- **失败不中断**：单库失败记 ERROR 并继续，末尾汇总；存在失败退出码 1；
- **`--dry-run`**：只打印清单，不建连。

与 `ops.migrate` 的分工：本脚本只**建库**（部署第 ② 步），结构由 `ops.migrate` 迁移（第 ③ 步）——
先库后表，避免迁移因库不存在直接失败。
"""

import argparse
import asyncio
from dataclasses import dataclass

from bms_core.core.concurrent import ConcurrentStableList
from bms_core.core.config import Settings, get_settings
from bms_core.core.exceptions import ConfigError
from bms_core.core.objects import BaseValueObject
from bms_core.db.admin import create_database, resolve_target
from bms_core.db.engine import EngineFactory
from bms_core.db.keys import ARCHIVE_DB_KEY, build_platform_db_key, build_tenant_db_key
from sqlalchemy.engine import make_url

from services.module_registry import local_service_keys
from services.table_registry import register as register_product_tables

# 表归属**产品注入**（bms 12_04）：库键解析需要本产品服务键已登记（幂等）
register_product_tables()


@dataclass(frozen=True)
class ProvisionTarget(BaseValueObject):
    """单个建库目标（库键 / 连接串）。"""

    key: str
    url: str


@dataclass(frozen=True)
class ProvisionSummary(BaseValueObject):
    """批量建库结果汇总（新建 / 已存在 / 失败）。"""

    created: tuple[str, ...]
    existing: tuple[str, ...]
    failed: tuple[str, ...]

    @property
    def exit_code(self) -> int:
        """退出码（存在失败为 1）。

        Returns:
            int: 0 全成功 / 1 存在失败。
        """
        return 1 if self.failed else 0


def resolve_services(requested: list[str]) -> ConcurrentStableList[str]:
    """解析服务维度（显式保序去重；缺省取本产品在运服务）。

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


def build_targets(
    services: ConcurrentStableList[str],
    codes: ConcurrentStableList[str],
    *,
    settings: Settings | None = None,
    include_platform: bool = True,
    include_tenants: bool = True,
    include_archive: bool = True,
) -> ConcurrentStableList[ProvisionTarget]:
    """构建「服务 × 数据源 × 租户」建库清单。

    Args:
        services: 服务标识列表。
        codes: 租户编码列表（库名基 = 编码）。
        settings: 应用配置；None 取全局配置单例。
        include_platform: 是否包含各服务的平台服务库。
        include_tenants: 是否包含各服务的租户库。
        include_archive: 是否包含归档库。

    Returns:
        ConcurrentStableList[ProvisionTarget]: 建库清单（保序：平台 → 各服务租户 → 归档）。
    """
    resolved = settings or get_settings()
    factory = EngineFactory(resolved, allow_cross_service=True)  # 运维通道：批量建库按各服务库执行
    targets: ConcurrentStableList[ProvisionTarget] = ConcurrentStableList()
    for service in services:
        if include_platform:
            key = build_platform_db_key(service)
            targets.add(ProvisionTarget(key=key, url=factory.resolved_url(key)))
        if not include_tenants:
            continue
        for code in codes:
            key = build_tenant_db_key(code, service=service)
            targets.add(ProvisionTarget(key=key, url=factory.resolved_url(key)))
    if include_archive:
        targets.add(ProvisionTarget(key=ARCHIVE_DB_KEY, url=factory.resolved_url(ARCHIVE_DB_KEY)))
    return targets


async def run(targets: ConcurrentStableList[ProvisionTarget]) -> ProvisionSummary:
    """逐库建库（幂等；单库失败不中断）。

    Args:
        targets: 建库清单。

    Returns:
        ProvisionSummary: 结果汇总。
    """
    created: ConcurrentStableList[str] = ConcurrentStableList()
    existing: ConcurrentStableList[str] = ConcurrentStableList()
    failed: ConcurrentStableList[str] = ConcurrentStableList()
    for target in targets:
        shown = make_url(target.url).render_as_string(hide_password=True)
        try:
            if await create_database(resolve_target(target.url)):
                created.add(target.key)
                print(f"[provision] {target.key:<24} 新建（{shown}）")
            else:
                existing.add(target.key)
                print(f"[provision] {target.key:<24} 已存在（跳过）")
        except Exception as exc:  # 单库失败不中断，末尾汇总
            failed.add(target.key)
            print(f"[provision] {target.key:<24} 失败：{exc}")
    return ProvisionSummary(created=tuple(created), existing=tuple(existing), failed=tuple(failed))


def build_parser() -> argparse.ArgumentParser:
    """构建命令行解析器。

    Returns:
        argparse.ArgumentParser: 解析器。
    """
    parser = argparse.ArgumentParser(description="服务库建库编排（幂等；逐服务 × 租户 × 归档）")
    parser.add_argument("--service", action="append", default=[], help="服务标识（可重复；缺省全部在运服务）")
    parser.add_argument("--code", action="append", default=[], help="租户编码（可重复；库名基 = 编码）")
    parser.add_argument("--dry-run", action="store_true", help="仅打印清单（不建连）")
    return parser


def main(argv: list[str] | None = None) -> int:
    """入口。

    Args:
        argv: 命令行参数（None 取 `sys.argv`）。

    Returns:
        int: 退出码（0 成功 / 1 存在失败或配置非法）。
    """
    args = build_parser().parse_args(argv)
    try:
        services = resolve_services(args.service)
        targets = build_targets(services, ConcurrentStableList(dict.fromkeys(args.code)))
    except ConfigError as exc:
        print(f"[provision] 失败：{exc}")
        return 1
    print(f"[provision] 待处理 {len(targets)} 个库（dry-run={args.dry_run}）")
    for target in targets:
        shown = make_url(target.url).render_as_string(hide_password=True)
        print(f"[provision]   {target.key:<24} {shown}")
    if args.dry_run:
        return 0
    summary = asyncio.run(run(targets))
    print(
        f"[provision] 完成：新建 {len(summary.created)} / 已存在 {len(summary.existing)} / 失败 {len(summary.failed)}"
    )
    if summary.failed:
        print(f"[provision] 失败清单：{', '.join(summary.failed)}")
    return summary.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
