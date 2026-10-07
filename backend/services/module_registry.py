"""mdm 产品服务目录本地登记（**产品自持清单**，与 `bms_core.services.module_registry` 同口径）。

- **单一来源**：本清单是 mdm 侧产品服务注册要素（域简称 ↔ 表前缀 ↔ 业务码 ↔ 错误码段 ↔ 事件域）
  的登记出处，须与《[mdm 主数据管理规划](../../mdm文档/规划/mdm主数据管理规划.md)》「标识符登记」
  及《[mdm 英文简称规范](../../mdm文档/规范/英文简称规范.md)》一致（不一致以规划 / 规范为准）。
- **两侧同值（R 架构，2026-10-07 拍板）**：平台侧 `SERVICE_CATALOG` 亦登记同 `module_key` 行
  （供网关、迁移链、库键与表归属派生），本清单注入**同值记录**；基座 `merge_service_records()`
  按「同 `module_key` 同值去重、异值即拒」处理——任一字段差异即拒启（两侧不漂移）。
- **校验**：`validate_local_catalog()` 离线执行（模块键 / 表前缀 / 事件域 / 服务键 / 错误码段
  唯一与格式 + 产品维度四条断言 + 与平台侧登记行同值比对），由 `ops.check_modules` 与用例调用。
"""

from bms_core.core.concurrent import ConcurrentStableList
from bms_core.services.module_registry import (
    SERVICE_CATALOG,
    ModuleRecord,
    ModuleRegistry,
    ModuleStatus,
    ServiceGroup,
    merge_service_records,
    validate_product_service_records,
)

PRODUCT_KEY = "mdm"
"""mdm 产品标识（须与平台侧 `PRODUCT_CATALOG` 登记及产品路由映射一致）。"""

SERVICE_KEY = "org"
"""运行服务标识（本产品当前唯一在运服务；产品维度校验的「含运行服务登记行」基准）。"""

MDM_SERVICE_RECORDS: tuple[ModuleRecord, ...] = (
    ModuleRecord(
        module_key="org",
        service_key="org",
        name="mdm 组织主数据服务",
        table_prefix="org_",
        errcode_segment="33",
        event_domain="org",
        service_group=ServiceGroup.PRODUCT,
        build_batch=3,
        product_key=PRODUCT_KEY,
        status=ModuleStatus.ENABLED,
    ),
)
"""mdm 产品服务清单（首条 = 组织主数据域；与 bms 平台侧 `org` 登记行逐字段同值）。

- 四要素**随规划登记**（`service_key=org` / `module_key=org` / `table_prefix=org_` / `event_domain=org`），
  对外命名空间经平台侧 `PRODUCT_ROUTES` 映射为 `/api/mdm/v1/org/...`（域段与上游服务解耦）；
- `errcode_segment=33`（错误码段 `33xxxx`）、`build_batch=3`（产品批次）、`status=enabled`（已接入）；
- 业务码（权限码前缀 `org`）不参与注册要素唯一性校验，登记口径见 mdm 规划与简称规范。
"""


def service_package(service_key: str) -> str:
    """服务包名（mdm 侧命名规则：`mdm_{服务键}`）。

    供运维脚本（清单校验扫描服务工程 / 契约快照内存构建应用）定位包；与镜像名 `mdm-{service}`、
    Compose 服务名 `{service}` 同源。

    Args:
        service_key: 服务标识（如 `org`）。

    Returns:
        str: 服务包名（如 `mdm_org`）。
    """
    return f"mdm_{service_key}"


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
    """平台侧服务目录清单（`bms_core` 内置 `SERVICE_CATALOG`，产品行在其中已登记）。

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
    """离线校验本产品服务目录（清单唯一与格式 + 产品维度断言 + 两侧同值比对）。

    三条检查面：

    1. **清单校验**：合并视图（平台清单 + 注入记录）经 `ModuleRegistry.validate()`——注册要素
       唯一与格式、分组 / 批次 / 版本 / 产品维度（含 `product_key` 须在 `PRODUCT_CATALOG` 登记）、
       产品级路由映射（`PRODUCT_ROUTES` 的 `mdm/org → org`）；
    2. **产品维度断言**（`validate_product_service_records`）：注入记录非空 / 均为产品分组 /
       产品归属与声明一致 / 含运行服务登记行；
    3. **两侧同值**（R 架构）：每条注入记录须在平台清单中已登记且**逐字段同值**——两侧并存才可
       在平台侧派生网关路由、迁移链、库键与表归属；缺失或异值即拒（fail-closed，不静默取一侧）。

    Args:
        service_key: 运行服务标识（缺省 `org`）。
        product_key: 产品标识（缺省 `mdm`）。

    Returns:
        ConcurrentStableList[str]: 冲突 / 非法明细；空列表表示通过。
    """
    errors = ConcurrentStableList(ModuleRegistry(catalog_view()).validate())
    injected = ConcurrentStableList(MDM_SERVICE_RECORDS)
    errors.update(validate_product_service_records(injected, service_key=service_key, product_key=product_key))
    platform_by_key = {record.module_key: record for record in SERVICE_CATALOG}
    for record in injected:
        existing = platform_by_key.get(record.module_key)
        if existing is None:
            errors.add(f"{record.module_key}：产品自持行未在平台侧服务目录登记（须在 bms 登记同值行）")
        elif existing != record:
            errors.add(f"{record.module_key}：与平台侧登记行不同值（平台 {existing!r}，产品 {record!r}）")
    return errors
