#!/bin/sh
# engkit 克隆准备（13_07）：后端的 ruff 规则基线在 engkit 仓 `toolchain/ruff-base.toml`（文件路径），
# 故凡跑 ruff 的 job 都必须先有克隆；本脚本按 `ENGKIT_REV` 检出并导出 `ENGKIT_HOME`。
#
# 用法（**source**，需要把 ENGKIT_HOME 导给后续步骤）：`. scripts/tools/ci/engkit_setup.sh`
#
# 口径：
#   1. `ENGKIT_REV` 缺省值只在本文件一处；升级只改这里 + `backend/pyproject.toml` 的 `rev`；
#   2. 克隆地址用 `CI_SERVER_URL`（含协议与端口）——`CI_SERVER_HOST` 不含端口，会连到 :80 超时；
#   3. runner 工作区跨作业复用：已有克隆即只做 checkout；
#   4. `uv sync --frozen` 另按 pyproject 的 rev 拉 engkit 包（提供 ruff / pyright 版本与命令），
#      与克隆是**两条都要有**的路径（基线读文件，包提供工具）。

ENGKIT_REPO_ROOT="${CI_PROJECT_DIR:-$(cd "$(dirname "$0")/../../.." && pwd)}"
ENGKIT_CLONE_DIR="${ENGKIT_REPO_ROOT}/../engkit"
ENGKIT_REF="${ENGKIT_REV:-bb2199f26ef815a4f4ebaee72af28f97076837e2}"

if [ ! -d "${ENGKIT_CLONE_DIR}/.git" ]; then
    ENGKIT_SCHEME="${CI_SERVER_URL%%://*}"
    ENGKIT_HOSTPORT="${CI_SERVER_URL#*://}"
    ENGKIT_DEFAULT_URL="${ENGKIT_SCHEME}://gitlab-ci-token:${CI_JOB_TOKEN:-}@${ENGKIT_HOSTPORT}/bms/engkit.git"
    git clone --quiet --no-checkout "${ENGKIT_REPO_URL:-${ENGKIT_DEFAULT_URL}}" "${ENGKIT_CLONE_DIR}"
fi
git -C "${ENGKIT_CLONE_DIR}" checkout --quiet "${ENGKIT_REF}"

ENGKIT_HOME="${ENGKIT_CLONE_DIR}"
export ENGKIT_HOME
echo "[engkit] 克隆就绪：${ENGKIT_HOME} @ ${ENGKIT_REF}"
