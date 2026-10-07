"""产品侧事件契约快照 CLI（**产品侧自持**）：导出 / 零漂移 + 兼容校验。

用法::

    uv run python -m ops.event_contracts export            # 导出（覆盖写入 deploy/events/contracts.json）
    uv run python -m ops.event_contracts export --print     # 导出并打印
    uv run python -m ops.event_contracts check              # 零漂移 + 兼容校验（CI / 预检用）

- **契约来源**：产品侧声明模块 `mdm_org.events`（经 `register_product_event_contracts()` 登记），
  与平台默认契约合并（本产品服务不注册平台契约，合并结果即本产品 5 条 `org.*`）；
- **事件域校验**：域名须在服务目录 `SERVICE_CATALOG.event_domain` 登记（`org` 已登记）；
- **确定性**：同代码 → 同文本（缩进 2 / 键排序 / 非 ASCII 直出），供 Git 比对与零漂移校验；
- **兼容**：与快照比对（事件类型不得消失 + 字段只增不删 + 订阅覆盖）。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bms_core.core.concurrent import ConcurrentStableList
from bms_core.events.contracts import (
    EVENT_SNAPSHOT_PATH,
    EventContractRegistry,
    check_snapshot_compatibility,
    parse_event_snapshot,
    render_event_snapshot,
    validate_event_registry,
)
from bms_core.services.module_registry import known_event_domains

from mdm_org.events import register_product_event_contracts

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = _BACKEND_ROOT.parent
"""仓库根（`backend/` 的父目录）。"""


def snapshot_path(root: Path) -> Path:
    """事件契约快照文件路径。

    Args:
        root: 仓库根。

    Returns:
        Path: `<root>/deploy/events/contracts.json`。
    """
    return root / EVENT_SNAPSHOT_PATH


def build_registry() -> EventContractRegistry:
    """构建事件契约注册表（本产品契约登记到隔离实例）。

    Returns:
        EventContractRegistry: 已登记本产品事件契约的注册表。
    """
    registry = EventContractRegistry()
    register_product_event_contracts(registry)
    return registry


def registry_errors(registry: EventContractRegistry) -> ConcurrentStableList[str]:
    """校验注册表（契约与订阅命名 / 版本 / 字段 + 事件域已登记）。

    Args:
        registry: 事件契约注册表。

    Returns:
        ConcurrentStableList[str]: 违规明细；空列表表示通过。
    """
    return ConcurrentStableList(validate_event_registry(registry, domains=known_event_domains()))


def export(root: Path, *, to_stdout: bool = False) -> int:
    """导出事件契约快照。

    Args:
        root: 仓库根。
        to_stdout: 是否同时打印生成内容。

    Returns:
        int: 退出码（0 成功；1 校验失败）。
    """
    registry = build_registry()
    errors = registry_errors(registry)
    if errors:
        for message in errors:
            print(f"  - {message}")
        return 1
    text = render_event_snapshot(registry)
    path = snapshot_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if to_stdout:
        print(text, end="")
    else:
        print(f"[event_contracts] 已生成 {path}（契约 {len(registry.contracts())} 条）")
    return 0


def check(root: Path) -> int:
    """校验快照零漂移与兼容（事件类型不得消失 / 字段只增不删 / 订阅覆盖）。

    Args:
        root: 仓库根。

    Returns:
        int: 退出码（0 一致；1 缺件 / 漂移 / 不兼容 / 注册表非法）。
    """
    registry = build_registry()
    problems = registry_errors(registry)
    path = snapshot_path(root)
    if not path.is_file():
        problems.add(f"缺事件契约快照：{path}")
    else:
        text = path.read_text(encoding="utf-8")
        if text != render_event_snapshot(registry):
            problems.add("快照与当前事件契约漂移（重新运行 export）")
        previous = parse_event_snapshot(json.loads(text))
        problems.update(check_snapshot_compatibility(ConcurrentStableList(previous[0]), registry))
    if problems:
        print(f"[event_contracts] 不通过：{len(problems)} 项")
        for message in problems:
            print(f"  - {message}")
        return 1
    print(f"[event_contracts] 通过：契约 {len(registry.contracts())} 条、快照零漂移且兼容")
    return 0


def main(argv: list[str] | None = None) -> int:
    """命令行入口。

    Args:
        argv: 参数列表（缺省取 `sys.argv[1:]`）。

    Returns:
        int: 退出码。
    """
    parser = argparse.ArgumentParser(description="导出 / 校验本产品事件契约快照")
    parser.add_argument("command", choices=("export", "check"), help="export 导出；check 零漂移 + 兼容校验")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="仓库根（缺省自动定位）")
    parser.add_argument("--print", dest="to_stdout", action="store_true", help="export 时打印生成内容")
    args = parser.parse_args(argv)
    if args.command == "export":
        return export(args.root, to_stdout=bool(args.to_stdout))
    return check(args.root)


if __name__ == "__main__":
    raise SystemExit(main())
