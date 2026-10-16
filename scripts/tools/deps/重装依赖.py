#!/usr/bin/env python3
"""依赖重装（mdm 前后端）：还原 → 安装（前端 pnpm / 后端 uv）→ 再次外置。

用法（在 mdm 仓根执行，Linux / Windows 通用）：
    python3 scripts/tools/deps/重装依赖.py [--frozen|--no-frozen|--frontend-only|--backend-only]
    （不带参数默认 --frozen，与 CI 口径一致：pnpm install --frozen-lockfile / uv sync --frozen）
    （Linux 亦可经同名 .sh 瘦包装调用；Windows 亦可经同名 .bat 瘦包装调用）

前端与后端同口径：依赖实体在本地依赖仓（默认 $HOME/dev-deps/mdm），仓内原位为链接。
  - 前端：frontend/**/node_modules  → $DEPS_DIR/frontend/**/node_modules
  - 后端：backend/.venv             → $DEPS_DIR/backend-venv
后端外置依赖基座 `bms_core.core.paths` 的工程根定位（不穿透链接），随 pyproject 锁定的
bms-core SHA 提供。
"""

import os
import subprocess
import sys

import deps_common as common

PREFIX = "重装依赖"

_MODES = {
    "--frozen": ["--frozen-lockfile"],
    "--no-frozen": [],
    "--frontend-only": ["--frozen-lockfile"],
    "--backend-only": ["--frozen-lockfile"],
}


def main(argv):
    args = argv[1:]
    mode = args[0] if args else "--frozen"
    if mode not in _MODES:
        sys.stderr.write(f"[{PREFIX}] 未知参数：{mode}"
                         "（支持 --frozen / --no-frozen / --frontend-only / --backend-only）\n")
        return 2
    install_args = _MODES[mode]

    root = common.find_repo_root(__file__, PREFIX)
    os.chdir(root)
    ws = os.path.join(root, "frontend")

    # 解析并以环境变量导出：子脚本（还原/外置）读取一致值
    deps_dir = common.resolve_deps_dir(root)
    os.environ["DEPS_DIR"] = deps_dir
    print(f"[{PREFIX}] 本地依赖仓：{deps_dir}")

    here = os.path.dirname(os.path.abspath(__file__))

    def run(cmd, cwd, label):
        print(f"[{PREFIX}] {label}")
        code = subprocess.call(cmd, cwd=cwd)
        if code != 0:
            sys.stderr.write(f"[{PREFIX}] {label} 失败（exit={code}），中止。\n")
            sys.exit(1)

    # 1) 先还原（移除外置链接，安装器才能正常重建项目内目录）
    run([sys.executable, os.path.join(here, "还原依赖.py")], root, "还原依赖")

    # 2) 安装
    # 后端一律在 `backend/` 下执行（工程根在 `backend/`，仓根没有 pyproject.toml）：
    # 还原后 `.venv` 已回到 `backend/.venv` 真实目录，uv sync 就地同步该环境。
    if mode == "--backend-only":
        run(["uv", "sync", "--frozen"], os.path.join(root, "backend"), "uv sync --frozen（backend）")
    elif mode == "--frontend-only":
        run(["pnpm", "install"] + install_args, ws, "pnpm install（frontend/）")
    else:
        run(["uv", "sync", "--frozen"], os.path.join(root, "backend"), "uv sync --frozen（backend）")
        run(["pnpm", "install"] + install_args, ws, "pnpm install（frontend/）")

    # 3) 再次外置
    run([sys.executable, os.path.join(here, "外置依赖.py")], root, "外置依赖")
    print(f"[{PREFIX}] 完成。")
    return 0


if __name__ == "__main__":
    common.configure_stdio()
    sys.exit(main(sys.argv))
