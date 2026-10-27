"""mdm 组织主数据服务包。"""

import os
from pathlib import Path

__version__ = "0.1.0"

# 工程根显式覆盖（2026-10-27 拍板：`bms-core` 改**路径依赖**接入工作区 bms 源码）：
# 基座的工程根定位（`bms_core.core.paths.resolve_backend_root`）按「本文件向上搜 `alembic.ini`」，
# editable 安装后其文件在 bms 仓内，会搜到 bms 仓根 → 配置 / 迁移 / 模型模块全错位。
# 故在导入期声明本仓 backend 根（基座官方覆盖变量；取值无效时 fail-closed，不静默回落）。
os.environ.setdefault("BMS_BACKEND_ROOT", str(Path(__file__).resolve().parents[4]))

CONTRACT_VERSION = "0.1.0"
"""公开契约（OpenAPI）版本（服务自报；启动与 CI 校验主版本兼容，破坏性变更升主版本）。"""

SERVICE_NAME = "mdm"
"""服务名（`[app].service` 为空时取本声明；用于日志 `service`、探针响应与按服务配置）。"""

SERVICE_TITLE = "mdm 组织主数据服务"
"""服务中文名（用于应用 title）。"""
