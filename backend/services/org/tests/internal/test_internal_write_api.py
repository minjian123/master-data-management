"""组织域内部分配端点用例：四组「全量覆盖 + 主要项」写通道的 HTTP 全链路与幂等回放。

口径：内部面鉴权按**能力分配**判定（07B `03_01`；四个端点各一项 `mdm.org.*.assign`），故用例在
应用启动后登记授权视图来源替身（`grant_source`，覆盖远端来源）并授予四项能力，再替换令牌校验器
（返回 `service=platform` 的服务身份）走真实依赖链；库为临时文件 SQLite，每请求独立会话
（不复用同一 session，避免跨请求残留事务）。
数据准备走管理面路由（仅替换认证依赖），不直接操作仓储。
"""

import os
from collections.abc import AsyncIterator
from typing import Any

import pytest
from bms_core.api.base import require_auth
from bms_core.api.deps import get_idempotency_store
from bms_core.core.concurrent import ConcurrentStableFrozenList
from bms_core.db.migration import import_models
from bms_core.models.base import Base
from bms_core.oauth.verify import BaseTokenVerifier, VerifiedToken, get_token_verifier
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

from mdm.capabilities import ORG_CAPABILITIES
from services.table_registry import register as register_product_tables
from tests_support.grants import StaticGrantSource

BASE = "/api/v1/mdm/internal"
"""内部写通道前缀。"""

ADMIN = "/api/v1/mdm"
"""管理面前缀（造数用）。"""


class _PlatformVerifier(BaseTokenVerifier):
    """令牌校验替身：服务受众恒返回 `platform` 身份（白名单内）。"""

    plugin_name: str = "platform-stub"

    async def verify(self, token: str, *, audience: str) -> VerifiedToken:
        """返回服务身份声明。

        Args:
            token: 令牌串（替身忽略）。
            audience: 期望受众。

        Returns:
            VerifiedToken: 服务身份声明。
        """
        del token
        return VerifiedToken(subject="gateway", service="platform", audience=ConcurrentStableFrozenList((audience,)))


class _ReplayStore:
    """幂等键存储替身：`begin` 恒拒、`load` 返回上次结果。"""

    def __init__(self, payload: dict[str, Any] | None) -> None:
        self.payload = payload
        self.saved: list[tuple[str, dict[str, Any]]] = []

    async def begin(self, key: str) -> bool:
        """判定是否首次提交（替身恒为重复）。"""
        del key
        return False

    async def load(self, key: str) -> dict[str, Any] | None:
        """取上次结果。"""
        del key
        return self.payload

    async def save(self, key: str, payload: dict[str, Any]) -> None:
        """记录结果。"""
        self.saved.append((key, payload))


@pytest.fixture(autouse=True)
async def prepared_db(isolate_settings: None) -> AsyncIterator[None]:
    """建表（临时租户库）：HTTP 路径按库读写，不自动建表。

    Args:
        isolate_settings: 配置隔离夹具。

    Yields:
        None: 用例运行期。
    """
    del isolate_settings
    register_product_tables()
    import_models("mdm")
    engine = create_async_engine(os.environ["BMS_DATABASE__TENANTS__URL"])
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()
    yield


@pytest.fixture
def overrides(service_app: FastAPI, grant_source: StaticGrantSource) -> None:
    """放行管理面认证、注入服务身份校验器，并授予四组内部分配能力。

    Args:
        service_app: 应用实例。
        grant_source: 授权视图来源替身（授予 `platform` 四项 `mdm.org.*.assign` 能力）。
    """
    for capability in ORG_CAPABILITIES:
        grant_source.grant(capability)
    service_app.dependency_overrides[require_auth] = lambda: None
    service_app.dependency_overrides[get_token_verifier] = lambda: _PlatformVerifier()


async def _seed(client: AsyncClient) -> dict[str, int]:
    """经管理面造「部门 + 岗位」两个目标。

    Args:
        client: 测试客户端。

    Returns:
        dict[str, int]: `dept` / `post` 两个 id。
    """
    dept = await client.post(f"{ADMIN}/depts", json={"code": "hq", "name": "总部"})
    dept_id = int(dept.json()["data"]["id"])
    post = await client.post(f"{ADMIN}/posts", json={"code": "dev", "name": "开发岗", "dept_id": dept_id})
    return {"dept": dept_id, "post": int(post.json()["data"]["id"])}


@pytest.mark.kiwi_id(2274)
async def test_internal_write_endpoints_assign_and_echo(client: AsyncClient, overrides: None) -> None:
    """四组内部写端点：全量覆盖 + 主要项落位，响应回生效后集合（与公开面同源）。"""
    key = await _seed(client)
    headers = {"Authorization": "Bearer service-token", "X-Tenant-ID": "demo"}

    user_posts = await client.put(
        f"{BASE}/user-posts/2002",
        json={"post_ids": [key["post"]], "primary_post_id": key["post"]},
        headers=headers,
    )
    assert user_posts.status_code == 200
    assert str(user_posts.json()["data"]["primary_post_id"]) == str(key["post"])

    user_depts = await client.put(
        f"{BASE}/user-depts/2002",
        json={"dept_ids": [key["dept"]], "primary_dept_id": key["dept"]},
        headers=headers,
    )
    assert user_depts.status_code == 200
    assert str(user_depts.json()["data"]["primary_dept_id"]) == str(key["dept"])

    role_posts = await client.put(f"{BASE}/role-posts/9001", json={"post_ids": [key["post"]]}, headers=headers)
    assert role_posts.status_code == 200

    role_depts = await client.put(f"{BASE}/role-depts/9001", json={"dept_ids": [key["dept"]]}, headers=headers)
    assert role_depts.status_code == 200


@pytest.mark.kiwi_id(2274)
async def test_internal_write_idempotency_replay_and_save(
    service_app: FastAPI, client: AsyncClient, overrides: None
) -> None:
    """幂等键：同键重放直接返回上次结果；键被占用但无结果时继续执行并保存结果。"""
    key = await _seed(client)
    headers = {"Authorization": "Bearer service-token", "X-Tenant-ID": "demo", "Idempotency-Key": "k-1"}

    service_app.dependency_overrides[get_idempotency_store] = lambda: _ReplayStore(
        {"post_ids": [key["post"]], "primary_post_id": key["post"]}
    )
    replayed = await client.put(f"{BASE}/user-posts/2001", json={"post_ids": [key["post"]]}, headers=headers)
    assert replayed.status_code == 200
    assert str(replayed.json()["data"]["primary_post_id"]) == str(key["post"])

    service_app.dependency_overrides[get_idempotency_store] = lambda: _ReplayStore(
        {"dept_ids": [key["dept"]], "primary_dept_id": None}
    )
    replayed_depts = await client.put(f"{BASE}/user-depts/2001", json={"dept_ids": [key["dept"]]}, headers=headers)
    assert replayed_depts.status_code == 200

    store = _ReplayStore(None)
    service_app.dependency_overrides[get_idempotency_store] = lambda: store
    executed = await client.put(f"{BASE}/role-posts/9002", json={"post_ids": [key["post"]]}, headers=headers)
    assert executed.status_code == 200
    assert store.saved, "首次提交应保存结果供同键重放"

    store_depts = _ReplayStore(None)
    service_app.dependency_overrides[get_idempotency_store] = lambda: store_depts
    executed_depts = await client.put(f"{BASE}/role-depts/9002", json={"dept_ids": [key["dept"]]}, headers=headers)
    assert executed_depts.status_code == 200
    assert store_depts.saved


@pytest.mark.kiwi_id(2274)
async def test_internal_write_without_primary_and_first_submit(
    service_app: FastAPI, client: AsyncClient, overrides: None
) -> None:
    """不带主要项的分派：跳过第二次服务调用；首次提交（带键）保存结果供同键重放。"""
    key = await _seed(client)
    headers = {"Authorization": "Bearer service-token", "X-Tenant-ID": "demo", "Idempotency-Key": "k-2"}

    user_posts_store = _ReplayStore(None)
    service_app.dependency_overrides[get_idempotency_store] = lambda: user_posts_store
    user_posts = await client.put(f"{BASE}/user-posts/2003", json={"post_ids": [key["post"]]}, headers=headers)
    assert user_posts.status_code == 200
    assert user_posts_store.saved, "首次提交应保存结果"

    user_depts_store = _ReplayStore(None)
    service_app.dependency_overrides[get_idempotency_store] = lambda: user_depts_store
    user_depts = await client.put(f"{BASE}/user-depts/2003", json={"dept_ids": [key["dept"]]}, headers=headers)
    assert user_depts.status_code == 200
    assert user_depts_store.saved, "首次提交应保存结果"


@pytest.mark.kiwi_id(2274)
async def test_internal_role_assignment_replays_idempotent_payload(
    service_app: FastAPI, client: AsyncClient, overrides: None
) -> None:
    """角色侧两个端点的同键重放：直接返回上次结果（不重复落库）。"""
    key = await _seed(client)
    headers = {"Authorization": "Bearer service-token", "X-Tenant-ID": "demo", "Idempotency-Key": "k-3"}

    service_app.dependency_overrides[get_idempotency_store] = lambda: _ReplayStore({"post_ids": [key["post"]]})
    role_posts = await client.put(f"{BASE}/role-posts/9003", json={"post_ids": [key["post"]]}, headers=headers)
    assert role_posts.status_code == 200
    assert [int(item) for item in role_posts.json()["data"]["post_ids"]] == [key["post"]]

    service_app.dependency_overrides[get_idempotency_store] = lambda: _ReplayStore({"dept_ids": [key["dept"]]})
    role_depts = await client.put(f"{BASE}/role-depts/9003", json={"dept_ids": [key["dept"]]}, headers=headers)
    assert role_depts.status_code == 200
    assert [int(item) for item in role_depts.json()["data"]["dept_ids"]] == [key["dept"]]
