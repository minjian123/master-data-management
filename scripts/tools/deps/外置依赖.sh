#!/usr/bin/env bash
# 依赖外置（mdm 前端） —— Linux 入口脚本（转调同名 .py 单一实现；逻辑见 外置依赖.py）
# 对应 Windows 入口 外置依赖.bat
# 用法: ./外置依赖.sh [--dry-run]（于 mdm 仓根执行）
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$HERE/外置依赖.py" "$@"
