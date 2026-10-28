#!/usr/bin/env python3
"""开发环入口（薄包装）：只跑本次 git 改动相关内容，实现在 engkit `run-changed`。

口径与 bms 同构（见《AI开发规范》「开发环 / 推送环」）：
- 后端：直接依赖选测（不做传递 import 闭包），不跑覆盖率、不退化工程级全量；
- 前端：只跑受影响包（`pnpm -C frontend --filter <包> test`，不带覆盖率）；
- 静态：只对改动文件跑 `ruff check` + `ruff format --check`；
- 推送前预检（`engkit preflight`）仍按传递闭包 + 100% 覆盖率执行。

mdm 以路径依赖装 engkit，故本入口只做 `uv run engkit run-changed` 的参数与退出码转发。

用法（在仓库根）::

    python3 scripts/tools/preflight/测试改动内容.py [--changed-from origin/main]
                                                   [--changed-file <路径>]...
                                                   [--jobs auto|N|off] [--timeout N]
                                                   [--no-lint] [--no-frontend]
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
"""仓库根。"""


def main() -> int:
    """入口。

    Returns:
        int: 退出码（与 engkit `run-changed` 一致）。
    """
    argv = ["uv", "run", "--project", str(_ROOT / "backend"), "engkit", "run-changed", *sys.argv[1:]]
    return subprocess.run(argv, cwd=_ROOT, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
