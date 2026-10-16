#!/usr/bin/env python3
"""依赖外置（mdm）：把项目内 node_modules 整体搬移至本地依赖仓，原位留目录链接。

效果：磁盘占用归零、依赖不出项目（检索/扫描工具默认不跟随链接即扫不到）。

与 bms 同名脚本同口径，两处 mdm 特有差异：
  1) **工作区根是 `frontend/`**（pnpm-workspace.yaml 所在），不是仓根；仓根另有校验。
  2) 前端把平台基座包（@bms/*）以 file: 引工作区 bms 克隆，故 node_modules 内存在指向
     **项目外**（兄弟仓 bms 或本仓源码）的相对软链；node_modules 整体搬移后相对基准改变，
     这些链必断，本脚本在搬移前先解析出它们的绝对目标、搬移后重写为绝对路径。

用法（在 mdm 仓根执行，Linux / Windows 通用）：
    python3 scripts/tools/deps/外置依赖.py [--dry-run]
    （Linux 亦可经同名 .sh 瘦包装调用；Windows 亦可经同名 .bat 瘦包装调用）

本地依赖仓目录（本地资源信息，不入公开文档）：
  1) 环境变量 DEPS_DIR；
  2) mdm/deploy/.env 中的 DEPS_DIR=（存在时）；
  3) 缺省 $HOME/dev-deps/mdm。

配套：还原依赖.py（搬回原位）、重装依赖.py（还原→安装→再外置）。
"""

import os
import sys

import deps_common as common

PREFIX = "外置依赖"


def collect_cross_links(roots, repo_root):
    """搬移前解析「跨拓扑软链」：目标不在任何待搬移 node_modules 根之内的相对软链。

    这类链在目录整体搬移后相对基准改变，必然断裂（同一 node_modules 树内部的相对链
    随整树搬移、相对关系不变，天然继续有效，无需处理）。扫描跳过 `.pnpm` 子树
    （其内部相对链必在树内，不可能是跨拓扑链，跳过以省扫描）。
    """
    cross = []
    for root in roots:
        stack = [root]
        while stack:
            current = stack.pop()
            try:
                entries = list(os.scandir(current))
            except OSError:
                continue
            for entry in entries:
                path = entry.path
                if common.entry_is_link(entry):
                    try:
                        raw = os.readlink(path)
                    except OSError:
                        continue
                    if os.path.isabs(raw):
                        continue  # 绝对链不受搬移影响
                    target = os.path.normpath(os.path.join(os.path.dirname(path), raw))
                    if not any(common.is_within(target, r) for r in roots):
                        cross.append((os.path.relpath(path, repo_root), target))
                    continue
                try:
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                except OSError:
                    continue
                if entry.name in (".pnpm", ".git"):
                    continue
                stack.append(path)
    return sorted(cross)


def main(argv):
    dry_run = "--dry-run" in argv[1:]

    root = common.find_repo_root(__file__, PREFIX)
    os.chdir(root)
    ws = os.path.join(root, "frontend")

    deps_dir = common.resolve_deps_dir(root)
    common.validate_layout(root, deps_dir, PREFIX)
    common.warn_cross_volume(root, deps_dir)

    print(f"[{PREFIX}] 仓库根：{root}")
    print(f"[{PREFIX}] 工作区：{ws}")
    print(f"[{PREFIX}] 本地依赖仓：{deps_dir}")

    # ---- 步骤 1：搬移前解析「跨拓扑软链」的绝对目标 与 待搬移目录清单 ----
    # 与仓库同名的嵌套目录＝路径前缀重复误建出的幽灵目录，跳过（防再次搬移污染依赖仓）
    root_name = os.path.basename(root)
    roots = []
    for path in common.find_node_modules_dirs(ws):
        rel = os.path.relpath(path, root)
        if rel.split(os.sep, 1)[0] == root_name:
            print(f"[跳过] {rel}（位于与仓库同名的嵌套目录，疑似前缀重复误建）")
            continue
        roots.append(path)
    print(f"[{PREFIX}] 待搬移 node_modules 根：{len(roots)} 个")
    for path in roots:
        print(f"[{PREFIX}]   - {os.path.relpath(path, root)}")

    cross = collect_cross_links(roots, root)
    print(f"[{PREFIX}] 需重写为绝对路径的跨拓扑软链：{len(cross)} 条")
    for rel, target in cross:
        print(f"[{PREFIX}]   - {rel} -> {target}")

    # ---- 步骤 2：逐个搬移 + 原位目录链接 ----
    count = 0
    for src in roots:
        rel = os.path.relpath(src, root)
        dest = os.path.join(deps_dir, rel)
        print(f"[外置] {rel}")
        count += 1
        if dry_run:
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.lexists(dest):
            common.remove_path_safe(dest)
        common.move_dir(src, dest)
        common.create_link(src, dest)
    print(f"[外置] 完成：共 {count} 个依赖目录。")

    # ---- 步骤 3：按搬移前解析的绝对目标重写跨拓扑软链 ----
    # 幂等：已指向绝对路径的链在步骤 1 即被跳过（不写入清单）。
    fix_count = 0
    for rel, target in cross:
        link = os.path.join(deps_dir, rel)
        print(f"[修复] {rel} -> {target}")
        fix_count += 1
        if dry_run:
            continue
        if common.is_link(link):
            common.remove_link(link)
        elif os.path.lexists(link):
            common.remove_path_safe(link)
        common.create_link_any(link, target)
    print(f"[外置] 跨拓扑软链重写：{fix_count} 条。")

    # ---- 步骤 4：后端 .venv 外置 ----
    # 与前端同口径：真实目录搬到依赖仓，原位留目录链接。可行前提是基座工程根定位
    # （`bms_core.core.paths.resolve_backend_root`，随锁定的 bms-core SHA 提供）**不穿透
    # 链接**——外置态下包体虽在依赖仓，仍能经 `backend/.venv/...` 的字面层级上溯到仓库内工程根。
    # 依赖仓已有环境时以依赖仓为准：仓内若残留真实目录即删除，避免两份环境并存混淆。
    venv_live = os.path.join(root, "backend", ".venv")
    venv_store = os.path.join(deps_dir, "backend-venv")
    if common.is_link(venv_live):
        print("[跳过] backend/.venv 是链接（已外置）")
    elif os.path.isdir(venv_store):
        if os.path.lexists(venv_live):
            print("[外置] backend/.venv：依赖仓已有环境，删除仓内残留目录（以依赖仓为准）")
            count += 1
            if not dry_run:
                common.remove_path_safe(venv_live)
        else:
            print("[外置] backend/.venv：采用依赖仓现有环境（原位建链接）")
        if dry_run:
            print(f"[dry-run] 建链接 {venv_live} -> {venv_store}")
        else:
            common.create_link(venv_live, venv_store)
    elif os.path.isdir(venv_live):
        print("[外置] backend/.venv")
        count += 1
        if not dry_run:
            os.makedirs(deps_dir, exist_ok=True)
            common.move_dir(venv_live, venv_store)
            common.create_link(venv_live, venv_store)
    else:
        print("[跳过] backend/.venv 不存在（先 uv sync 生成，或本仓未启用后端外置）")

    print(f'[外置] 查看本地依赖仓体积：du -sh "{deps_dir}"（Windows 可看文件夹属性）')
    print("[外置] 确认项目内为链接：ls -la frontend/node_modules backend/.venv（Windows 为 junction）")
    return 0


if __name__ == "__main__":
    common.configure_stdio()
    sys.exit(main(sys.argv))
