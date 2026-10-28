"""mdm 产品服务目录本地登记（**产品自持清单**，与 `bms_core.services.module_registry` 同口径）。

- **单一来源**：本清单是 mdm 侧产品服务注册要素（域简称 ↔ 表前缀 ↔ 业务码 ↔ 错误码段 ↔ 事件域）
  的登记出处，须与《[mdm 主数据管理规划](../../mdm文档/规划/mdm主数据管理规划.md)》「标识符登记」
  及《[mdm 英文简称规范](../../mdm文档/规范/英文简称规范.md)》一致（不一致以规划 / 规范为准）。
- **产品自持 + 清单装载（2026-10-23 拍板）**：本清单同时写入产品登记清单
  `deploy/registry/mdm.toml`（服务行 / 产品档案 / 产品路由 / 数据源条目），平台侧按
  `[registry].product_manifests` 装载——**基座不再硬编码产品行**（机制同选项集装载时注册）。
- **校验**：`validate_local_catalog()` 离线执行（模块键 / 表前缀 / 事件域 / 服务键 / 错误码段
  唯一与格式 + 产品维度四条断言），由 `ops.check_modules` 与用例调用。
"""

from bms_core.core.concurrent import ConcurrentStableList
from bms_core.services.module_registry import (
    SERVICE_CATALOG,
    ModuleRecord,
    ModuleRegistry,
    ModuleStatus,
    ProductRecord,
    ProductRouteRecord,
    ServiceGroup,
    merge_service_records,
    register_product_records,
    register_product_routes,
    register_service_records,
    validate_product_service_records,
)

PRODUCT_KEY = "mdm"
"""mdm 产品标识（须与产品登记清单 `deploy/registry/mdm.toml` 及产品路由映射一致）。"""

SERVICE_KEY = "mdm"
"""运行服务标识（本产品当前唯一在运服务；产品维度校验的「含运行服务登记行」基准）。"""

MDM_SERVICE_RECORDS: tuple[ModuleRecord, ...] = (
    ModuleRecord(
        module_key="mdm",
        service_key="mdm",
        name="mdm 主数据服务",
        table_prefix="mdm_",
        business_code="mdm",
        errcode_segment="33",
        event_domain="mdm",
        service_group=ServiceGroup.PRODUCT,
        build_batch=3,
        product_key=PRODUCT_KEY,
        status=ModuleStatus.ENABLED,
        tenant_base=True,
    ),
)
"""mdm 产品服务清单（唯一在运服务 `mdm`；与 `deploy/registry/mdm.toml` 的 `services` 段逐字段同值）。

- 四要素：`service_key=mdm` / `module_key=mdm` / `table_prefix=mdm_` / `event_domain=mdm`；
- 对外命名空间经平台侧产品路由映射为 `/api/mdm/v1/mdm/...`（域段与上游服务同名）；
- `errcode_segment=33`（沿用组织域已登记段位 `33xxxx`，段号注册即定、不随服务名变更）；
- `build_batch=3`（产品批次）、`status=enabled`（已接入）；
- `tenant_base=True`：租户恒开通（角色 / 用户组织归属的基座；07B `03_01` 起由产品自持清单声明）。
"""

MDM_PRODUCT_RECORDS: tuple[ProductRecord, ...] = (
    ProductRecord(
        product_key=PRODUCT_KEY,
        name="主数据管理",
        frontend_package_source="mdm#frontend",
    ),
)
"""mdm 产品档案（与 `deploy/registry/mdm.toml` 的 `products` 段同值）。"""

MDM_PRODUCT_ROUTES: tuple[ProductRouteRecord, ...] = (
    ProductRouteRecord(
        product_key=PRODUCT_KEY,
        domain=SERVICE_KEY,
        service_key=SERVICE_KEY,
        description="mdm 主数据服务（对外 /api/mdm/v1/mdm/...）",
    ),
)
"""mdm 产品级路由映射（与 `deploy/registry/mdm.toml` 的 `product_routes` 段同值）。"""

# 装载时注册（模块导入即登记；迁移链派生 / 库键解析 / 表归属前缀校验 / 应用装配校验读合并视图）。
# 幂等：同键同值覆盖，异值即拒。
register_product_records(MDM_PRODUCT_RECORDS)
register_service_records(ConcurrentStableList(MDM_SERVICE_RECORDS))
register_product_routes(MDM_PRODUCT_ROUTES)


def service_package(service_key: str) -> str:
    """服务包名（mdm 侧命名规则：`mdm_{服务键}`；服务键即产品名时去重为 `mdm`）。

    与基座 `bms_core.db.migration.service_package()` 同规则（前缀 = 服务标识去重），
    供运维脚本（清单校验扫描服务工程 / 契约快照内存构建应用）定位包。

    Args:
        service_key: 服务标识（如 `mdm`）。

    Returns:
        str: 服务包名（`mdm`）。
    """
    return PRODUCT_KEY if service_key == PRODUCT_KEY else f"{PRODUCT_KEY}_{service_key}"


def local_service_keys() -> tuple[str, ...]:
    """本产品在运服务标识（清单中 `service_key` 非空且启用；保持清单顺序）。

    Returns:
        tuple[str, ...]: 服务标识元组。
    """
    return tuple(
        record.service_key
        for record in MDM_SERVICE_RECORDS
        if record.service_key is not None and record.status == ModuleStatus.ENABLED
    )


def platform_records() -> ConcurrentStableList[ModuleRecord]:
    """平台侧服务目录清单（`bms_core` 内置 `SERVICE_CATALOG`；产品行由产品清单装载）。

    Returns:
        ConcurrentStableList[ModuleRecord]: 平台服务目录记录（插入序）。
    """
    return ConcurrentStableList(SERVICE_CATALOG)


def catalog_view() -> ConcurrentStableList[ModuleRecord]:
    """应用级服务目录视图（平台清单 + 本产品清单，同值去重后的合并结果）。

    Returns:
        ConcurrentStableList[ModuleRecord]: 合并清单（平台清单顺序在前）。
    """
    return merge_service_records(SERVICE_CATALOG, ConcurrentStableList(MDM_SERVICE_RECORDS))


def validate_local_catalog(
    *, service_key: str = SERVICE_KEY, product_key: str = PRODUCT_KEY
) -> ConcurrentStableList[str]:
    """离线校验本产品服务目录（清单唯一与格式 + 产品维度断言）。

    两条检查面：

    1. **清单校验**：合并视图（平台清单 + 本产品清单）经 `ModuleRegistry.validate()`——注册要素
       唯一与格式、分组 / 批次 / 版本 / 产品维度（含 `product_key` 已登记）、产品级路由映射；
    2. **产品维度断言**（`validate_product_service_records`）：注入记录非空 / 均为产品分组 /
       产品归属与声明一致 / 含运行服务登记行。

    产品档案（`mdm`）与产品级路由由产品登记清单装载后进入校验基准，故校验前先装载
    `deploy/registry/mdm.toml`（`load_product_manifests`）；未装载时按产品维度断言报错（fail-closed）。

    Args:
        service_key: 运行服务标识（缺省 `mdm`）。
        product_key: 产品标识（缺省 `mdm`）。

    Returns:
        ConcurrentStableList[str]: 冲突 / 非法明细；空列表表示通过。
    """
    errors = ConcurrentStableList(ModuleRegistry(catalog_view()).validate())
    errors.update(
        validate_product_service_records(
            ConcurrentStableList(MDM_SERVICE_RECORDS), service_key=service_key, product_key=product_key
        )
    )
    return errors
