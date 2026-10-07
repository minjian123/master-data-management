"""CI 产品服务目录校验（**离线**）：清单唯一与格式 + 产品维度断言 + 两侧同值 + 服务包契约声明。

用法：

```bash
cd backend
uv run python -m ops.check_modules            # 离线断言（当前唯一模式）
uv run python -m ops.check_modules --offline  # 显式声明离线（与 bms 侧 CLI 口径兼容）
```

校验面（全部离线，无库依赖）：

1. **清单与产品维度**：`services.module_registry.validate_local_catalog()`——合并视图（平台清单 +
   产品注入记录）经 `ModuleRegistry.validate()` 校验注册要素唯一与格式 / 分组 / 版本 / 产品归属 /
   产品级路由映射；产品维度四条断言；**两侧同值**（注入记录须在平台清单中已登记且逐字段同值）；
2. **服务包契约声明**：扫描 `services/*/src/mdm_*/__init__.py` 的 `CONTRACT_VERSION`（AST 静态读取，
   不导入服务包），与清单登记值比对主版本；服务工程与清单**双向核对**（工程存在但未登记即失败）。

冲突 / 非法 → 打印明细并退出码 1；通过 → 退出码 0。

> **为何无接库对账**：平台库 `sys_module` / `sys_product` 归平台 `platform` 服务库（bms 侧
> `ops.check_modules` 对账），产品侧不跨服务直读；mdm 侧以离线清单 + 两侧同值为门禁。
"""

import argparse
import ast
import sys
from pathlib import Path

from bms_core.core.concurrent import ConcurrentStableDict, ConcurrentStableList
from bms_core.core.version import contract_major
from bms_core.services.module_registry import SERVICE_CATALOG, ModuleRecord

from services.module_registry import (
    MDM_SERVICE_RECORDS,
    PRODUCT_KEY,
    SERVICE_KEY,
    service_package,
    validate_local_catalog,
)

_SERVICES_DIR = Path(__file__).resolve().parents[1] / "services"
"""服务工程根（`backend/services`）。"""

_CONTRACT_CONSTANT = "CONTRACT_VERSION"
"""服务包自报契约版本常量名。"""


def build_parser() -> argparse.ArgumentParser:
    """构建命令行解析器。

    Returns:
        argparse.ArgumentParser: 解析器。
    """
    parser = argparse.ArgumentParser(description="mdm 产品服务目录校验（离线清单 + 产品维度 + 两侧同值）")
    parser.add_argument("--offline", action="store_true", help="离线校验（mdm 产品侧恒离线，本开关为口径兼容）")
    return parser


def _extract_contract_version(init_path: Path) -> str | None:
    """AST 静态提取服务包 `__init__.py` 的 `CONTRACT_VERSION` 字符串字面量。

    Args:
        init_path: 服务包 `__init__.py` 路径。

    Returns:
        str | None: 常量值；未声明或非字符串字面量返回 None。
    """
    module = ast.parse(init_path.read_text(encoding="utf-8"))
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == _CONTRACT_CONSTANT for target in node.targets):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return node.value.value
        return None
    return None


def resolve_service_contracts(services_dir: Path = _SERVICES_DIR) -> ConcurrentStableDict[str, str | None]:
    """扫描服务工程读各自报契约版本（包名按 mdm 命名规则 `mdm_{服务键}`）。

    Args:
        services_dir: 服务工程根。

    Returns:
        ConcurrentStableDict[str, str | None]: {服务键: 自报契约版本}；已声明但非字符串字面量为 None。
    """
    declarations: ConcurrentStableDict[str, str | None] = ConcurrentStableDict()
    for entry in sorted(services_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        init_path = entry / "src" / service_package(entry.name) / "__init__.py"
        if init_path.is_file():
            declarations.set(entry.name, _extract_contract_version(init_path))
    return declarations


def check_service_declarations(
    catalog: ConcurrentStableList[ModuleRecord] | tuple[ModuleRecord, ...],
    declarations: ConcurrentStableDict[str, str | None],
) -> ConcurrentStableList[str]:
    """服务工程声明 ↔ 清单双向核对（工程未登记 / 未声明常量 / 主版本不符）。

    Args:
        catalog: 产品服务清单（`MDM_SERVICE_RECORDS`）。
        declarations: 服务工程自报契约版本映射。

    Returns:
        ConcurrentStableList[str]: 冲突 / 非法明细。
    """
    errors: ConcurrentStableList[str] = ConcurrentStableList()
    expected = {module.service_key for module in catalog if module.service_key}
    for name in sorted(declarations):
        if name not in expected:
            errors.add(f"服务工程未登记：{name}")
    for module in catalog:
        if module.service_key is None or module.service_key not in declarations:
            continue
        declared = declarations[module.service_key]
        if declared is None:
            errors.add(f"{module.service_key}：服务包未声明 CONTRACT_VERSION")
            continue
        declared_major = contract_major(declared)
        if declared_major is None:
            errors.add(f"{module.service_key}：服务包契约版本非 semver（{declared}）")
            continue
        if declared_major != contract_major(module.contract_version):
            errors.add(
                f"{module.service_key}：服务包契约版本与清单主版本不符"
                f"（服务包 {declared}，清单 {module.contract_version}）"
            )
    return errors


def check_offline(services_dir: Path = _SERVICES_DIR) -> ConcurrentStableList[str]:
    """离线校验：产品清单 / 产品维度 / 两侧同值 + 服务包声明比对。

    Args:
        services_dir: 服务工程根。

    Returns:
        ConcurrentStableList[str]: 冲突 / 非法明细。
    """
    errors = validate_local_catalog()
    errors.update(check_service_declarations(MDM_SERVICE_RECORDS, resolve_service_contracts(services_dir)))
    return errors


def main(argv: ConcurrentStableList[str] | None = None) -> int:
    """入口：离线校验（唯一模式）。

    Args:
        argv: 命令行参数。

    Returns:
        int: 退出码（0 通过 / 1 失败）。
    """
    build_parser().parse_args(argv)
    errors = check_offline()
    if errors:
        for error in errors:
            print(f"[服务目录] {error}")
        print(f"[服务目录] 校验失败（{len(errors)} 项）")
        return 1
    scope = f"产品清单 {len(MDM_SERVICE_RECORDS)} 项（产品 {PRODUCT_KEY} / 运行服务 {SERVICE_KEY}）"
    print(f"[服务目录] 校验通过（{scope} + 平台侧同值 {len(SERVICE_CATALOG)} 行对账 + 服务包声明）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(ConcurrentStableList(sys.argv[1:])))
