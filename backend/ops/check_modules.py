"""CI 产品服务目录校验（**离线**）：清单唯一与格式 + 产品维度断言 + 产品清单齐备 + 服务包契约声明。

用法：

```bash
cd backend
uv run python -m ops.check_modules            # 离线断言（当前唯一模式）
uv run python -m ops.check_modules --offline  # 显式声明离线（与 bms 侧 CLI 口径兼容）
```

校验面（全部离线，无库依赖）：

1. **产品自持声明**（toml，07B `02_01`）：`deploy/registry/mdm.toml` 经基座同一实现
   （`inspect_product_manifests`）解析并做**六类校验**——能力重名 / 提供方业务域登记 /
   归属一致 / 访问面在对端契约中定位 / 契约版本兼容 / 种子入口可解析；跳过项与降级提示一律打印
   （不静默）；通过后注册进运行期视图（供产品维度断言使用）；
2. **清单与产品维度**：`services.module_registry.validate_local_catalog()`——合并视图（平台清单 +
   产品清单记录）经 `ModuleRegistry.validate()` 校验注册要素唯一与格式 / 分组 / 版本 / 产品归属 /
   产品级路由映射；产品维度四条断言；
3. **服务包契约声明**：扫描 `services/*/src/mdm_*/__init__.py` 的 `CONTRACT_VERSION`（AST 静态读取，
   不导入服务包），与清单登记值比对主版本；服务工程与清单**双向核对**（工程存在但未登记即失败）。

冲突 / 非法 → 打印明细并退出码 1；通过 → 退出码 0。

> **为何无接库对账**：平台库 `sys_module` / `sys_product` 归平台 `platform` 服务库（bms 侧
> `ops.check_modules` 对账），产品侧不跨服务直读；mdm 侧以离线清单 + 产品自持声明为门禁。
"""

import argparse
import ast
import json
import sys
from pathlib import Path

from bms_core.core.concurrent import ConcurrentStableDict, ConcurrentStableList
from bms_core.core.version import contract_major
from bms_core.registry.products import inspect_product_manifests, register_manifest
from bms_core.services.module_registry import SERVICE_CATALOG, ModuleRecord

from services.module_registry import (
    MDM_SERVICE_RECORDS,
    PRODUCT_KEY,
    SERVICE_KEY,
    validate_local_catalog,
)

_SERVICES_DIR = Path(__file__).resolve().parents[1] / "services"
"""服务工程根（`backend/services`）。"""

_MANIFEST = Path(__file__).resolve().parents[2] / "deploy" / "registry" / "mdm.toml"
"""产品自持声明（toml；由 `bms_core.registry.products.local_manifest_paths` 自动发现装载）。"""

_REPO_ROOT = Path(__file__).resolve().parents[2]
"""仓库根（`backend/ops/check_modules.py` 上两级）。"""

_CONTRACT_CONSTANT = "CONTRACT_VERSION"
"""服务包自报契约版本常量名。"""

_SERVICE_NAME_CONSTANT = "SERVICE_NAME"
"""服务包自报服务标识常量名（目录名可保留分类，服务键以此为准）。"""


def build_parser() -> argparse.ArgumentParser:
    """构建命令行解析器。

    Returns:
        argparse.ArgumentParser: 解析器。
    """
    parser = argparse.ArgumentParser(description="mdm 产品服务目录校验（离线清单 + 产品维度 + 两侧同值）")
    parser.add_argument("--offline", action="store_true", help="离线校验（mdm 产品侧恒离线，本开关为口径兼容）")
    parser.add_argument(
        "--render-domain-layout",
        action="store_true",
        help="由本仓清单第九类 [[domains]] 渲染 deploy/boundaries/domain_layout.json（生成物）",
    )
    parser.add_argument(
        "--check-domain-layout",
        action="store_true",
        help="比对 deploy/boundaries/domain_layout.json 与清单渲染结果（不一致即失败；不写文件）",
    )
    return parser


def _extract_constant(init_path: Path, name: str) -> str | None:
    """AST 静态提取服务包 `__init__.py` 的字符串常量。

    Args:
        init_path: 服务包 `__init__.py` 路径。
        name: 常量名。

    Returns:
        str | None: 常量值；未声明或非字符串字面量返回 None。
    """
    module = ast.parse(init_path.read_text(encoding="utf-8"))
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return node.value.value
        return None
    return None


def resolve_service_contracts(services_dir: Path = _SERVICES_DIR) -> ConcurrentStableDict[str, str | None]:
    """扫描服务工程读各自报契约版本（目录名保留分类，服务键取包内 `SERVICE_NAME`）。

    Args:
        services_dir: 服务工程根。

    Returns:
        ConcurrentStableDict[str, str | None]: {服务键: 自报契约版本}；已声明但非字符串字面量为 None。
    """
    declarations: ConcurrentStableDict[str, str | None] = ConcurrentStableDict()
    for entry in sorted(services_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        for init_path in sorted((entry / "src").glob("*/__init__.py")):
            if init_path.parent.name == "__pycache__":
                continue
            service_name = _extract_constant(init_path, _SERVICE_NAME_CONSTANT) or entry.name
            declarations.set(service_name, _extract_constant(init_path, _CONTRACT_CONSTANT))
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


def load_and_register_manifest(manifest_path: Path = _MANIFEST) -> ConcurrentStableList[str]:
    """装载并校验产品自持声明（toml），通过后注册进运行期视图。

    校验复用基座同一实现（`inspect_product_manifests`，含能力 / 种子两段六类校验）；
    跳过项与降级提示（如产品包不可导入时的种子入口校验）直接打印，不计入失败。

    Args:
        manifest_path: 产品自持声明路径。

    Returns:
        ConcurrentStableList[str]: 阻断性问题（空列表表示已注册成功）。
    """
    inspection = inspect_product_manifests([manifest_path])
    for warning in inspection.warnings:
        print(f"[服务目录] {warning}")
    if inspection.errors:
        return ConcurrentStableList(inspection.errors)
    for manifest in inspection.manifests:
        register_manifest(manifest)
    return ConcurrentStableList()


def check_offline(services_dir: Path = _SERVICES_DIR) -> ConcurrentStableList[str]:
    """离线校验：产品自持声明 / 产品维度 / 两侧同值 + 服务包声明比对。

    Args:
        services_dir: 服务工程根。

    Returns:
        ConcurrentStableList[str]: 冲突 / 非法明细。
    """
    errors = load_and_register_manifest()
    errors.update(validate_local_catalog())
    errors.update(check_service_declarations(MDM_SERVICE_RECORDS, resolve_service_contracts(services_dir)))
    return errors




DOMAIN_LAYOUT_PATH = Path("deploy/boundaries/domain_layout.json")
"""域布局生成物路径（相对仓根；07B `04_02` 重开：由清单第九类渲染，勿手改）。"""


def render_domain_layout() -> dict[str, object]:
    """由本仓清单第九类 `[[domains]]` 渲染域布局文档（生成物内容）。

    Returns:
        dict[str, object]: 与既有 `domain_layout.json` 逐字段同构的文档。
    """
    from bms_core.registry.products import load_product_manifests

    loaded = list(load_product_manifests(ConcurrentStableList()))
    domains: list[dict[str, object]] = []
    shared: list[str] = []
    seen_domain: set[str] = set()
    seen_shared: set[str] = set()
    for manifest in loaded:
        for entry in manifest.domains:
            if entry.domain_key in seen_domain:
                continue
            seen_domain.add(entry.domain_key)
            item: dict[str, object] = {"domain_key": entry.domain_key}
            if entry.name:
                item["name"] = entry.name
            item.update(
                {
                    "service_key": entry.service_key,
                    "status": entry.status,
                    "paths": list(entry.paths),
                    "public_api": list(entry.public_api),
                }
            )
            domains.append(item)
        for path in manifest.domain_shared_paths:
            if path in seen_shared:
                continue
            seen_shared.add(path)
            shared.append(path)
    return {"version": 1, "domains": domains, "shared_paths": shared}


def _run_domain_layout(args: argparse.Namespace) -> int:
    """域布局生成物：渲染（`--render-domain-layout`）或比对（`--check-domain-layout`）。

    Args:
        args: 命令行参数。

    Returns:
        int: 退出码（0 通过 / 1 不一致）。
    """
    document = render_domain_layout()
    target = _REPO_ROOT / DOMAIN_LAYOUT_PATH
    if args.render_domain_layout:
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(document, ensure_ascii=False, indent=2)
        target.write_text(payload + "\n", encoding="utf-8", newline="\n")
        print(f"[域布局] 已渲染：{target}（{len(document['domains'])} 域 / {len(document['shared_paths'])} 域外路径）")
        return 0
    if not target.is_file():
        print(f"[域布局] 生成物缺失：{target}（跑 --render-domain-layout 生成）")
        return 1
    try:
        current = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[域布局] 生成物 JSON 非法：{target}（{exc}）")
        return 1
    expected = json.loads(json.dumps(document, ensure_ascii=False))
    if current != expected:
        print(f"[域布局] 生成物与清单不一致：{target}（手改过或清单已变更；跑 --render-domain-layout 重新生成）")
        return 1
    print(f"[域布局] 生成物与清单一致：{target}")
    return 0

def main(argv: ConcurrentStableList[str] | None = None) -> int:
    """入口：离线校验（唯一模式）。

    Args:
        argv: 命令行参数。

    Returns:
        int: 退出码（0 通过 / 1 失败）。
    """
    args = build_parser().parse_args(argv)
    if args.render_domain_layout or args.check_domain_layout:
        return _run_domain_layout(args)
    errors = check_offline()
    if errors:
        for error in errors:
            print(f"[服务目录] {error}")
        print(f"[服务目录] 校验失败（{len(errors)} 项）")
        return 1
    scope = f"产品清单 {len(MDM_SERVICE_RECORDS)} 项（产品 {PRODUCT_KEY} / 运行服务 {SERVICE_KEY}）"
    print(
        f"[服务目录] 校验通过（{scope} + 平台清单 {len(SERVICE_CATALOG)} 行合并 + 产品自持声明"
        "（含能力 / 种子段）+ 服务包声明）"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(ConcurrentStableList(sys.argv[1:])))
