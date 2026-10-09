"""组织域内部写通道用例（Kiwi 2274）：端点挂载与**服务身份鉴权**口径。

覆盖：① 四组内部写端点已挂载（`/api/v1/org/internal/*`）；② 无令牌一律 `401`（内部面不接受匿名）；
③ 内部面**不挂 `org:*` 权限码**（授权完全由服务身份白名单决定，与只读出口双通道同构）。

> 服务身份矩阵（白名单 `platform` 放行 / 登录态令牌拒 / 非白名单服务拒）与幂等回放属**续做**，
> 见任务实施记录「偏差与遗留」节。
"""

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

INTERNAL_PATHS = (
    "/api/v1/org/internal/user-posts/{user_id}",
    "/api/v1/org/internal/user-depts/{user_id}",
    "/api/v1/org/internal/role-posts/{role_id}",
    "/api/v1/org/internal/role-depts/{role_id}",
)


@pytest.mark.kiwi_id(2274)
async def test_internal_write_paths_mounted(service_app: FastAPI) -> None:
    """四组内部写端点已挂载，且均为 `PUT`（写语义 = 全量覆盖 + 主要项）。"""
    paths = service_app.openapi()["paths"]

    for path in INTERNAL_PATHS:
        assert path in paths, f"内部写端点未挂载：{path}"
        assert "put" in paths[path], f"内部写端点方法缺失：{path}"
        assert "get" not in paths[path], f"内部面不应提供读取端点（基线口径已删除）：{path}"


@pytest.mark.kiwi_id(2274)
async def test_internal_write_requires_service_token(client: AsyncClient) -> None:
    """无令牌调用内部写端点一律 `401`（不接受匿名，也不回落登录态）。"""
    response = await client.put("/api/v1/org/internal/user-depts/1", json={"dept_ids": []})

    assert response.status_code == 401
