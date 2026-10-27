#!/bin/sh
# bms 基座克隆准备（2026-10-27 起）：`bms-core` 已改为**路径依赖**
# （`backend/pyproject.toml` 的 `../../bms/backend/libs/bms_core`），故后端 job 必须先让
# `../bms` 存在，`uv sync --frozen` 才能按 `uv.lock` 装齐基座。
#
# 用法：`. scripts/tools/ci/bms_setup.sh`（在 `cd backend` 之前执行）
#
# 口径：
#   1. 克隆目录固定为 `<仓根>/../bms`——与本地工作区布局（`mdm/` 与 `bms/` 平级）同构，
#      使 pyproject 里的相对路径在本地与 CI 一致；
#   2. `BMS_REF` 为 CI 侧锁定 ref（分支 / tag / 提交）；**缺省 main**：升级基座只改 CI 变量，
#      不再改 product 仓的 pyproject rev（本地永远跟随工作区 bms 工作树）；
#   3. 拉取失败即失败（不静默跳过）——基座缺失时 `uv sync --frozen` 必然报错，早失败可归因清晰；
#   4. runner 工作区跨作业复用：已有克隆即 fetch + checkout。

BMS_REPO_ROOT="${CI_PROJECT_DIR:-$(cd "$(dirname "$0")/../../.." && pwd)}"
BMS_CLONE_DIR="${BMS_REPO_ROOT}/../bms"
BMS_REF="${BMS_REF:-main}"

if [ ! -d "${BMS_CLONE_DIR}/.git" ]; then
    BMS_SCHEME="${CI_SERVER_URL%%://*}"
    BMS_HOSTPORT="${CI_SERVER_URL#*://}"
    BMS_DEFAULT_URL="${BMS_SCHEME}://gitlab-ci-token:${CI_JOB_TOKEN:-}@${BMS_HOSTPORT}/bms/bms.git"
    git clone --quiet --no-checkout "${BMS_REPO_URL:-${BMS_DEFAULT_URL}}" "${BMS_CLONE_DIR}"
fi
git -C "${BMS_CLONE_DIR}" fetch --quiet origin "${BMS_REF}" || true
git -C "${BMS_CLONE_DIR}" checkout --quiet "${BMS_REF}"

if [ ! -d "${BMS_CLONE_DIR}/backend/libs/bms_core" ]; then
    echo "[bms] 基座源码缺失：${BMS_CLONE_DIR}/backend/libs/bms_core（子模块或 ref 异常）" >&2
    exit 1
fi
echo "[bms] 克隆就绪：${BMS_CLONE_DIR} @ ${BMS_REF}"
