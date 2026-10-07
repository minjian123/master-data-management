# mdm 服务运行镜像（按服务参数化；构建上下文为 backend/）
#
# 构建：
#   docker build --provenance=false --build-arg SERVICE=org -t <registry>/mdm-org:<sha> -f deploy/Dockerfile backend/
#   （--provenance=false：BuildKit 默认 attestation 清单推送会被 GitLab Registry 拒绝，报 blob unknown）
# 运行：
#   docker run --rm -p 8000:8000 -e BMS_ENV=<环境> <image>
# 口径：
# - 依赖以 uv.lock 锁定（--frozen）；共享基座 `bms-core` 经 git 源拉取（pyproject 锁提交 SHA）；
# - 工作目录 /opt/mdm/backend：`services` 产品清单模块、`alembic.ini` 与 `config*.toml` 均相对该根定位；
# - venv 落工作目录内（不设 UV_PROJECT_ENVIRONMENT）——共享基座经 site-packages 向上定位工程根
#   （`bms_core.db.migration._find_backend_root`）依赖 `alembic.ini` 在 venv 祖先目录内；
# - 启动入口 `python -m mdm_{service}`（按服务参数化；当前仅 org）。
FROM python:3.14-slim

ARG SERVICE=org
ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple \
    SERVICE=${SERVICE}

# 系统包安全更新（镜像扫描 CRITICAL/HIGH 阻断发版）+ apt 换清华源（与平台侧镜像同口径）
RUN sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources \
 && apt-get update \
 && apt-get upgrade -y \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /opt/mdm/backend
# 工作区元数据：uv.lock 与各成员 pyproject（工作区解析需要；成员源码后续按目标服务 COPY）；
# alembic.ini 供共享基座定位工程根（`bms_core.db.migration._find_backend_root` 向上搜根）；
# config*.toml 为配置基线 / 环境分层（密钥不入配置文件，经 BMS_ 环境变量注入）
COPY pyproject.toml uv.lock alembic.ini config.toml config.*.toml ./
COPY services/org/pyproject.toml services/org/pyproject.toml
# 第三方依赖层（不装工作区成员；锁文件零漂移；共享基座 `bms-core` 为 git 源依赖，随本层装齐）
RUN uv sync --frozen --no-install-workspace --package "mdm-${SERVICE}" && rm -rf /root/.cache

# 工作区成员源码（产品服务清单模块 + 目标服务）
COPY services/module_registry.py services/module_registry.py
COPY services/${SERVICE}/src services/${SERVICE}/src
RUN uv sync --frozen --no-dev --package "mdm-${SERVICE}" && rm -rf /root/.cache

# 迁移能力：分链迁移脚本 + 运维脚本（部署流程内一次性迁移容器复用本镜像，版本与发布一致）
COPY alembic ./alembic
COPY ops ./ops

# 运行时移除 pip（base 镜像自带；其 vendored 依赖会被镜像扫描按包计洞，运行时不需要）
RUN python -m pip uninstall -y pip

ENV PATH=/opt/mdm/backend/.venv/bin:$PATH
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]
CMD ["sh", "-c", "exec python -m mdm_${SERVICE}"]
