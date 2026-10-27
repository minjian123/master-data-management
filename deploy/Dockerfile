# mdm 服务运行镜像（服务标识 `mdm`；服务工程目录保留分类 `services/org`；构建上下文为**工作区根**）
#
# 构建（在工作区根执行——`mdm/` 与 `bms/` 平级并置）：
#   docker build --provenance=false -t <registry>/mdm:<sha> -f mdm/deploy/Dockerfile .
#   （--provenance=false：BuildKit 默认 attestation 清单推送会被 GitLab Registry 拒绝，报 blob unknown）
# 运行：
#   docker run --rm -p 8000:8000 -e BMS_ENV=<环境> <image>
# 口径：
# - 构建上下文为**工作区根**（2026-10-27 拍板：`bms-core` 改**路径依赖**接入工作区 bms 源码）：
#   镜像需自包含 ① bms 基座源码（`bms/backend/libs/bms_core` → `/opt/bms/...`，使 pyproject 里
#   `../../bms/backend/libs/bms_core` 在容器内同样成立）、② `mdm/deploy/{registry,boundaries,contracts}`
#   （产品自持声明 / 域布局 / 公开契约，供启动期装载校验与「码 → 状态 / 文案键」渲染）；
#   上下文排除规则见**工作区根** `.dockerignore`；
# - 依赖以 uv.lock 锁定（--frozen）；`engkit` 仍为跨仓 git 源依赖（锁提交 SHA），需构建期可读该仓；
# - 工作目录 /opt/mdm/backend：`services` 产品清单模块、`alembic.ini` 与 `config*.toml` 均相对该根定位；
#   声明目录相对该根的父级（`/opt/mdm/deploy/...`）；
# - 工程根显式覆盖 `BMS_BACKEND_ROOT`：基座按「本文件上溯 `alembic.ini`」定位工程根，基座源码在
#   `/opt/bms` 时会错位，故显式声明（取值无效 fail-closed）；
# - 启动入口 `python -m mdm`（服务包名 = 服务标识；前缀与服务同名时去重）。
FROM python:3.14-slim

ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple \
    SERVICE=org \
    BMS_BACKEND_ROOT=/opt/mdm/backend

# 系统包安全更新（镜像扫描 CRITICAL/HIGH 阻断发版）+ apt 换清华源（与平台侧镜像同口径）
RUN sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources \
 && apt-get update \
 && apt-get upgrade -y \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

# 共享基座源码（路径依赖目标）：放到 `/opt/bms/...`，使 pyproject 的相对路径在容器内成立
COPY bms/backend/libs/bms_core /opt/bms/backend/libs/bms_core

WORKDIR /opt/mdm/backend
# 工作区元数据：uv.lock 与各成员 pyproject（工作区解析需要；成员源码后续按目标服务 COPY）；
# alembic.ini 供共享基座定位工程根（`bms_core.core.paths.resolve_backend_root` 向上搜根）；
# config*.toml 为配置基线 / 环境分层（密钥不入配置文件，经 BMS_ 环境变量注入）
COPY mdm/backend/pyproject.toml mdm/backend/uv.lock mdm/backend/alembic.ini mdm/backend/config.toml mdm/backend/config.*.toml ./
COPY mdm/backend/services/org/pyproject.toml services/org/pyproject.toml
# 第三方依赖层（不装工作区成员；锁文件零漂移；共享基座按路径依赖就地安装，engkit 为 git 源随本层装齐）
RUN uv sync --frozen --no-install-workspace --package mdm && rm -rf /root/.cache

# 工作区成员源码（产品服务清单模块 + 目标服务）
COPY mdm/backend/services/module_registry.py services/module_registry.py
COPY mdm/backend/services/${SERVICE}/src services/${SERVICE}/src
RUN uv sync --frozen --no-dev --package mdm && rm -rf /root/.cache

# 迁移能力：分链迁移脚本 + 运维脚本（部署流程内一次性迁移容器复用本镜像，版本与发布一致）
COPY mdm/backend/alembic ./alembic
COPY mdm/backend/ops ./ops

# 产品自持声明 / 域布局 / 公开契约（相对工作目录父级：/opt/mdm/deploy/...）
# 装配期装载清单时据此定位对端契约与域布局；缺件即装载校验失败（拒启），不静默跳过
COPY mdm/deploy/registry ../deploy/registry
COPY mdm/deploy/boundaries ../deploy/boundaries
COPY mdm/deploy/contracts ../deploy/contracts

# 运行时移除 pip（base 镜像自带；其 vendored 依赖会被镜像扫描按包计洞，运行时不需要）
RUN python -m pip uninstall -y pip

ENV PATH=/opt/mdm/backend/.venv/bin:$PATH
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]
CMD ["python", "-m", "mdm"]
