#!/usr/bin/env bash
# 依赖重装（mdm 前后端） —— Linux 入口脚本（转调同名 .py 单一实现；逻辑见 重装依赖.py）
# 对应 Windows 入口 重装依赖.bat
# 用法: ./重装依赖.sh [--frozen|--no-frozen|--frontend-only|--backend-only]（于 mdm 仓根执行）
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$HERE/重装依赖.py" "$@"
