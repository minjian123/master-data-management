#!/bin/sh
# 依赖重装（mdm 前后端）：还原 → 安装（前端 pnpm / 后端 uv）→ 再次外置。
# 用法：bash scripts/tools/deps/重装依赖.sh [--frozen|--no-frozen|--frontend-only|--backend-only]
#   （不带参数默认 --frozen，与 CI 口径一致：pnpm install --frozen-lockfile / uv sync --frozen）
#
# 前端与后端同口径：依赖实体在本地依赖仓（默认 $HOME/dev-deps/mdm），仓内原位为符号链接。
#   - 前端：frontend/**/node_modules  → $DEPS_DIR/frontend/**/node_modules
#   - 后端：backend/.venv             → $DEPS_DIR/backend-venv
# 后端外置依赖基座 `bms_core.core.paths` 的工程根定位（不穿透符号链接），随 pyproject 锁定的
# bms-core SHA 提供。
set -eu

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPTS_DIR/../../.." 2>/dev/null && pwd || true)"
WS="$REPO_ROOT/frontend"

# ---- 工作区根校验：路径前缀重复会把 REPO_ROOT 推深一层，安装/外置都会落错位置。
if [ -z "$REPO_ROOT" ] || [ ! -f "$WS/pnpm-workspace.yaml" ]; then
    echo "[重装依赖] 工作区定位失败：${WS:-（上跳三级目录不存在）} 下没有 pnpm-workspace.yaml" >&2
    echo "[重装依赖] 请在 mdm 仓根执行 bash scripts/tools/deps/重装依赖.sh，勿叠加仓名前缀。" >&2
    exit 2
fi

MODE="${1:---frozen}"
case "$MODE" in
    --frozen) INSTALL_ARGS="--frozen-lockfile" ;;
    --no-frozen) INSTALL_ARGS="" ;;
    --frontend-only) INSTALL_ARGS="--frozen-lockfile" ;;
    --backend-only) INSTALL_ARGS="--frozen-lockfile" ;;
    *) echo "[重装依赖] 未知参数：$MODE（支持 --frozen / --no-frozen / --frontend-only / --backend-only）" >&2; exit 2 ;;
esac

# 1) 先还原（移除外置符号链接，安装器才能正常重建项目内目录）
sh "$SCRIPTS_DIR/还原依赖.sh"

# 2) 安装
if [ "$MODE" = "--backend-only" ]; then
    (cd "$REPO_ROOT/backend" && uv sync --frozen)
elif [ "$MODE" = "--frontend-only" ]; then
    cd "$WS"
    # shellcheck disable=SC2086
    pnpm install $INSTALL_ARGS
else
    (cd "$REPO_ROOT/backend" && uv sync --frozen)
    cd "$WS"
    # shellcheck disable=SC2086
    pnpm install $INSTALL_ARGS
fi

# 3) 再次外置
sh "$SCRIPTS_DIR/外置依赖.sh"
echo "[重装依赖] 完成。"
