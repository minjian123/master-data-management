#!/bin/sh
# 依赖还原（mdm 前端）：删除项目内的外置符号链接，把本地依赖仓中的 node_modules 搬回项目原位。
# 配套用场景：执行 pnpm install 前的必要前置（安装器见到符号链接会误判依赖已齐而跳过）。
#
# 用法：bash scripts/tools/deps/还原依赖.sh [--dry-run]      # 于 mdm 仓根执行
#
# 本地依赖仓目录与环境变量口径同 外置依赖.sh。
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." 2>/dev/null && pwd || true)"
WS="$REPO_ROOT/frontend"

# ---- 仓库/工作区根校验：路径前缀重复会把 REPO_ROOT 推深一层，后续「还原」会把依赖目录
#      搬进幽灵目录、破坏依赖仓。此处就地快速失败。
if [ -z "$REPO_ROOT" ] || [ ! -f "$WS/pnpm-workspace.yaml" ]; then
    echo "[还原依赖] 工作区定位失败：${WS:-（上跳三级目录不存在）} 下没有 pnpm-workspace.yaml" >&2
    echo "[还原依赖] 请在 mdm 仓根执行 bash scripts/tools/deps/还原依赖.sh，勿叠加仓名前缀。" >&2
    exit 2
fi

resolve_deps_dir() {
    if [ -n "${DEPS_DIR:-}" ]; then
        printf '%s' "$DEPS_DIR"
        return 0
    fi
    if [ -f "$REPO_ROOT/deploy/.env" ]; then
        if value=$(grep -E '^DEPS_DIR=' "$REPO_ROOT/deploy/.env" | head -1 | sed 's/^DEPS_DIR=//'); then
            if [ -n "$value" ]; then
                printf '%s' "$value"
                return 0
            fi
        fi
    fi
    printf '%s' "${HOME:-/home/shared}/dev-deps/mdm"
}
DEPS_DIR="$(resolve_deps_dir)"

DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

run() {
    if [ "$DRY_RUN" = 1 ]; then
        echo "[dry-run] $*"
    else
        "$@"
    fi
}

echo "[还原依赖] 仓库根：$REPO_ROOT"
echo "[还原依赖] 本地依赖仓：$DEPS_DIR"

count=0
if [ -d "$DEPS_DIR" ]; then
    tmp_list=$(mktemp)
    # 先收集全部清单再统一搬移：find 遍历中搬走目录会中断遍历（经典陷阱）
    find "$DEPS_DIR" -type d -name node_modules > "$tmp_list" 2>/dev/null
    while IFS= read -r src; do
        rel="${src#"$DEPS_DIR"/}"
        dst="$REPO_ROOT/$rel"
        if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
            # 项目内父目录必须存在（不存在即路径错位，搬回会失败或落到意外位置）
            if [ ! -d "$(dirname "$dst")" ]; then
                echo "[跳过] $rel：项目内父目录不存在，疑似路径错位" >&2
                continue
            fi
            echo "[还原] $rel"
            count=$((count + 1))
            if [ "$DRY_RUN" = 1 ]; then continue; fi
            rm -f "$dst"
            # 目录整体搬回（同分区 rename，保留硬链接 / 链接结构）
            mv "$src" "$dst"
        fi
    done < "$tmp_list"
    rm -f "$tmp_list"

    # ---- 后端 .venv 还原 ----
    # 与前端同口径：删原位符号链接，把依赖仓环境搬回 `backend/.venv`。
    # 安装器（uv sync）面对符号链接形态的 `.venv` 可能要求 `--clear`，故装依赖前必须先还原。
    venv_link="$REPO_ROOT/backend/.venv"
    venv_store="$DEPS_DIR/backend-venv"
    if [ -L "$venv_link" ] && [ -d "$venv_store" ]; then
        echo "[还原] backend/.venv"
        count=$((count + 1))
        if [ "$DRY_RUN" != 1 ]; then
            rm -f "$venv_link"
            mv "$venv_store" "$venv_link"
        fi
    fi
fi
echo "[还原] 完成：共 $count 个依赖目录已搬回。"
echo "[还原] 后续可执行：pnpm install --frozen-lockfile（于 frontend/）"
