#!/bin/sh
# 依赖外置（mdm 前端）：把项目内 node_modules 整体搬移至本地依赖仓，原位留符号链接。
# 效果：磁盘占用归零、依赖不出项目（检索/扫描工具默认不跟随符号链接即扫不到）。
#
# 与 bms 同名脚本同口径，两处 mdm 特有差异：
#   1) **工作区根是 `frontend/`**（pnpm-workspace.yaml 所在），不是仓根；仓根另有校验。
#   2) 前端把平台基座包（@bms/*）以 file: 引工作区 bms 克隆，故 node_modules 内存在指向
#      **项目外**（兄弟仓 bms 或本仓源码）的相对软链；node_modules 整体搬移后相对基准改变，
#      这些链必断，本脚本在搬移前先解析出它们的绝对目标、搬移后重写为绝对路径。
#
# 用法：
#   bash scripts/tools/deps/外置依赖.sh [--dry-run]      # 于 mdm 仓根执行
#
# 本地依赖仓目录（本地资源信息，不入公开文档）：
#   1) 环境变量 DEPS_DIR；
#   2) mdm/deploy/.env 中的 DEPS_DIR=（存在时）；
#   3) 缺省 $HOME/dev-deps/mdm。
#
# 配套：还原依赖.sh（搬回原位）、重装依赖.sh（还原→安装→再外置）。
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." 2>/dev/null && pwd || true)"
WS="$REPO_ROOT/frontend"

# ---- 仓库/工作区根校验：脚本按「脚本位置上跳三级」定位仓根，一旦调用时路径前缀重复
#      （如在 mdm 仓内又写成 `mdm/scripts/...`），REPO_ROOT 会被推深一层，软链随即被建到
#      `<仓>/<仓名>/…` 幽灵目录。此处就地快速失败，不做任何建链动作。
if [ -z "$REPO_ROOT" ] || [ ! -f "$WS/pnpm-workspace.yaml" ]; then
    echo "[外置依赖] 工作区定位失败：${WS:-（上跳三级目录不存在）} 下没有 pnpm-workspace.yaml" >&2
    echo "[外置依赖] 请在 mdm 仓根执行 bash scripts/tools/deps/外置依赖.sh，勿叠加仓名前缀。" >&2
    exit 2
fi

# ---- 解析本地依赖仓目录（环境变量 > deploy/.env > 缺省）----
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
DEPS_DIR="$(cd "$DEPS_DIR" 2>/dev/null && pwd || printf '%s' "$DEPS_DIR")"

DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

run() {
    if [ "$DRY_RUN" = 1 ]; then
        echo "[dry-run] $*"
    else
        "$@"
    fi
}

echo "[外置依赖] 仓库根：$REPO_ROOT"
echo "[外置依赖] 工作区：$WS"
echo "[外置依赖] 本地依赖仓：$DEPS_DIR"

# ---- 步骤 1：搬移前解析「跨拓扑软链」的绝对目标 与 待搬移目录清单 ----
# 跨拓扑判据：软链目标不在任何「待搬移的 node_modules 根」之内。这类链在目录整体搬移后
# 相对基准改变，必然断裂（同一 node_modules 树内部的 .pnpm 链随整树搬移，相对关系不变，
# 天然继续有效，无需处理）。
MANIFEST="$(mktemp)"
LIST="$(mktemp)"
trap 'rm -f "$MANIFEST" "$LIST"' EXIT INT TERM

python3 - "$REPO_ROOT" "$WS" "$MANIFEST" "$LIST" <<'PY'
import os
import sys

repo_root, ws, manifest_path, list_path = sys.argv[1:5]
repo_root = os.path.abspath(repo_root)
ws = os.path.abspath(ws)

# 收集待搬移的 node_modules 根：命中即记录且不深入（整树作为一个单位搬移）
roots = []
for dirpath, dirnames, _ in os.walk(ws, followlinks=False):
    kept = []
    for name in dirnames:
        p = os.path.join(dirpath, name)
        if name == 'node_modules' and not os.path.islink(p):
            roots.append(p)
        else:
            kept.append(name)
    dirnames[:] = kept
roots.sort()

# 与仓同名的嵌套目录＝路径前缀重复误建出的幽灵目录，跳过
ghost = os.path.basename(repo_root) + os.sep
roots = [r for r in roots if not os.path.relpath(r, repo_root).startswith(ghost)]

inside = lambda p: any(p == r or p.startswith(r + os.sep) for r in roots)

cross = []
for root in roots:
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for name in list(dirnames) + list(filenames):
            p = os.path.join(dirpath, name)
            if not os.path.islink(p):
                continue
            raw = os.readlink(p)
            if os.path.isabs(raw):
                continue  # 绝对链不受搬移影响
            target = os.path.normpath(os.path.join(dirpath, raw))
            if not inside(target):
                rel = os.path.relpath(p, repo_root)
                cross.append((rel, target))

with open(list_path, 'w', encoding='utf-8') as fh:
    for r in roots:
        fh.write(os.path.relpath(r, repo_root) + '\n')
with open(manifest_path, 'w', encoding='utf-8') as fh:
    for rel, target in sorted(cross):
        fh.write(rel + '\t' + target + '\n')

print(f"[外置依赖] 待搬移 node_modules 根：{len(roots)} 个")
for r in roots:
    print(f"[外置依赖]   - {os.path.relpath(r, repo_root)}")
print(f"[外置依赖] 需重写为绝对路径的跨拓扑软链：{len(cross)} 条")
for rel, target in sorted(cross):
    print(f"[外置依赖]   - {rel} -> {target}")
PY

# ---- 步骤 2：逐个搬移 + 原位符号链接 ----
count=0
while IFS= read -r rel; do
    [ -n "$rel" ] || continue
    src="$REPO_ROOT/$rel"
    dest="$DEPS_DIR/$rel"
    echo "[外置] $rel"
    count=$((count + 1))
    if [ "$DRY_RUN" = 1 ]; then continue; fi
    mkdir -p "$(dirname "$dest")"
    rm -rf "$dest" 2>/dev/null || true
    mv "$src" "$dest"
    ln -s "$dest" "$src"
done < "$LIST"
echo "[外置] 完成：共 $count 个依赖目录。"

# ---- 步骤 3：按搬移前解析的绝对目标重写跨拓扑软链 ----
# 幂等：已指向绝对路径的链在步骤 1 即被跳过（不写入 manifest）。
fix_count=0
while IFS="$(printf '\t')" read -r rel target; do
    [ -n "${rel:-}" ] || continue
    link="$DEPS_DIR/$rel"
    echo "[修复] $rel -> $target"
    fix_count=$((fix_count + 1))
    if [ "$DRY_RUN" = 1 ]; then continue; fi
    ln -snf "$target" "$link"
done < "$MANIFEST"
echo "[外置] 跨拓扑软链重写：$fix_count 条。"

# ---- 步骤 4：后端 .venv 外置 ----
# 与前端同口径：真实目录搬到依赖仓，原位留符号链接。可行前提是基座工程根定位
# （`bms_core.core.paths.resolve_backend_root`，随锁定的 bms-core SHA 提供）**不穿透符号
# 链接**——外置态下包体虽在依赖仓，仍能经 `backend/.venv/...` 的字面层级上溯到仓库内工程根。
# 依赖仓已有环境时以依赖仓为准：仓内若残留真实目录（历史上 UV_PROJECT_ENVIRONMENT 在非交互
# shell 失效时留下）即删除，避免两份环境并存混淆。
externalize_backend_venv() {
    live="$REPO_ROOT/backend/.venv"
    store="$DEPS_DIR/backend-venv"
    if [ -L "$live" ]; then
        echo "[跳过] backend/.venv 是符号链接（已外置）"
        return 0
    fi
    if [ -d "$store" ]; then
        if [ -d "$live" ]; then
            echo "[外置] backend/.venv：依赖仓已有环境，删除仓内残留目录（以依赖仓为准）"
            if [ "$DRY_RUN" != 1 ]; then rm -rf "$live"; else echo "[dry-run] rm -rf $live"; fi
        else
            echo "[外置] backend/.venv：采用依赖仓现有环境（原位建符号链接）"
        fi
        if [ "$DRY_RUN" != 1 ]; then ln -s "$store" "$live"; else echo "[dry-run] ln -s $store $live"; fi
        return 0
    fi
    if [ -d "$live" ]; then
        echo "[外置] backend/.venv"
        if [ "$DRY_RUN" = 1 ]; then return 0; fi
        mkdir -p "$DEPS_DIR"
        mv "$live" "$store"
        ln -s "$store" "$live"
    else
        echo "[跳过] backend/.venv 不存在（先 uv sync 生成）"
    fi
}
externalize_backend_venv

echo "[外置] 查看本地依赖仓体积： du -sh \"$DEPS_DIR\""
echo "[外置] 确认项目内为符号链接： ls -la frontend/node_modules backend/.venv"
