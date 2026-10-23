"""管理面路由用例：部门 / 岗位端点的 HTTP 全链路（鉴权以依赖覆写放行，专注路由与服务装配）。

口径：路由层的职责是「参数解析 → 服务调用 → 响应包装 → 审计占位」，服务层行为另有用例覆盖；
本文件按端点走通一次正常路径，保证契约面与装配面不因重构而断链。
"""

import os
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from bms_core.api.base import require_auth
from bms_core.api.deps import get_idempotency_store
from bms_core.db.migration import import_models
from bms_core.models.base import Base
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

from services.table_registry import register as register_product_tables

BASE = "/api/v1/mdm"
"""管理面路由前缀。"""


@pytest.fixture(autouse=True)
async def prepared_db(isolate_settings: None) -> AsyncIterator[None]:
    """建表：按隔离后的租户库连接串建出本产品与共享表（HTTP 路径按库读写，不自动建表）。

    Args:
        isolate_settings: 配置隔离夹具（保证环境变量已就位）。

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
def authorized(service_app: FastAPI) -> Iterator[None]:
    """放行认证依赖（权限检查器在测试配置下为空实现）。

    Args:
        service_app: 应用实例。

    Yields:
        None: 用例期间认证依赖被替换为直接放行。
    """
    service_app.dependency_overrides[require_auth] = lambda: None
    yield
    service_app.dependency_overrides.clear()


@pytest.mark.kiwi_id(2255)
async def test_dept_routes_full_cycle(client: AsyncClient, authorized: None) -> None:
    """部门路由：列表 / 新建 / 明细 / 更新 / 移动 / 子用户 / 子角色 / 删除 全端点走通。"""
    empty = await client.get(f"{BASE}/depts")
    assert empty.status_code == 200

    created = await client.post(f"{BASE}/depts", json={"code": "hq", "name": "总部", "sort": 1})
    assert created.status_code == 200
    dept_id = created.json()["data"]["id"]

    detail = await client.get(f"{BASE}/depts/{dept_id}")
    assert detail.status_code == 200 and detail.json()["data"]["code"] == "hq"

    updated = await client.put(f"{BASE}/depts/{dept_id}", json={"name": "集团总部"})
    assert updated.status_code == 200 and updated.json()["data"]["name"] == "集团总部"

    moved = await client.put(f"{BASE}/depts/{dept_id}/move", json={"parent_id": None})
    assert moved.status_code == 200

    users = await client.get(f"{BASE}/depts/{dept_id}/users")
    assert users.status_code == 200 and users.json()["data"]["user_ids"] == []

    roles = await client.get(f"{BASE}/depts/{dept_id}/roles")
    assert roles.status_code == 200 and roles.json()["data"]["role_ids"] == []

    deleted = await client.delete(f"{BASE}/depts/{dept_id}")
    assert deleted.status_code == 200 and deleted.json()["data"]["id"] == dept_id


@pytest.mark.kiwi_id(2255)
async def test_post_routes_full_cycle(client: AsyncClient, authorized: None) -> None:
    """岗位路由：列表 / 新建 / 明细 / 更新 / 子用户 / 子角色 / 删除 全端点走通。"""
    dept = await client.post(f"{BASE}/depts", json={"code": "hq", "name": "总部"})
    dept_id = dept.json()["data"]["id"]

    empty = await client.get(f"{BASE}/posts")
    assert empty.status_code == 200

    created = await client.post(f"{BASE}/posts", json={"code": "dev", "name": "开发岗", "dept_id": dept_id})
    assert created.status_code == 200
    post_id = created.json()["data"]["id"]

    detail = await client.get(f"{BASE}/posts/{post_id}")
    assert detail.status_code == 200 and detail.json()["data"]["code"] == "dev"

    updated = await client.put(f"{BASE}/posts/{post_id}", json={"name": "研发岗"})
    assert updated.status_code == 200 and updated.json()["data"]["name"] == "研发岗"

    users = await client.get(f"{BASE}/posts/{post_id}/users")
    assert users.status_code == 200 and users.json()["data"]["user_ids"] == []

    roles = await client.get(f"{BASE}/posts/{post_id}/roles")
    assert roles.status_code == 200 and roles.json()["data"]["role_ids"] == []

    deleted = await client.delete(f"{BASE}/posts/{post_id}")
    assert deleted.status_code == 200 and deleted.json()["data"]["id"] == post_id


class _ReplayStore:
    """幂等键存储替身：`begin` 恒拒（视为重复提交）、`load` 返回上次结果。"""

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


@pytest.mark.kiwi_id(2255)
async def test_dept_and_post_create_replay_by_idempotency_key(
    service_app: FastAPI, client: AsyncClient, authorized: None
) -> None:
    """幂等键重放：同键重复提交直接返回上次结果（不重复落库），部门 / 岗位两路由同口径。"""

    def _override(payload: dict[str, Any]) -> None:
        store = _ReplayStore(payload)
        service_app.dependency_overrides[get_idempotency_store] = lambda: store

    _override(
        {"id": 7, "parent_id": None, "code": "hq", "name": "总部", "ancestors": "/", "sort": 0, "status": "enabled"}
    )
    dept = await client.post(
        f"{BASE}/depts",
        json={"code": "hq", "name": "总部"},
        headers={"Idempotency-Key": "dept-key"},
    )
    assert dept.status_code == 200 and str(dept.json()["data"]["id"]) == "7"

    _override({"id": 9, "code": "dev", "name": "开发岗", "dept_id": 1, "sort": 0, "status": "enabled"})
    post = await client.post(
        f"{BASE}/posts",
        json={"code": "dev", "name": "开发岗", "dept_id": 1},
        headers={"Idempotency-Key": "post-key"},
    )
    assert post.status_code == 200 and str(post.json()["data"]["id"]) == "9"


@pytest.mark.kiwi_id(2255)
async def test_create_with_idempotency_key_saves_result(client: AsyncClient, authorized: None) -> None:
    """幂等键首次提交：正常落库并保存结果（供同键重放取用），部门 / 岗位两路由同口径。"""
    dept = await client.post(
        f"{BASE}/depts", json={"code": "hq", "name": "总部"}, headers={"Idempotency-Key": "fresh-dept"}
    )
    assert dept.status_code == 200
    post = await client.post(
        f"{BASE}/posts",
        json={"code": "dev", "name": "开发岗", "dept_id": dept.json()["data"]["id"]},
        headers={"Idempotency-Key": "fresh-post"},
    )
    assert post.status_code == 200


@pytest.mark.kiwi_id(2255)
async def test_user_assignment_routes(client: AsyncClient, authorized: None) -> None:
    """用户分配路由：用户-岗位与用户-部门的列表 / 全量覆盖 / 主要项置位 / 解绑全端点走通。"""
    dept = await client.post(f"{BASE}/depts", json={"code": "hq", "name": "总部"})
    dept_id = dept.json()["data"]["id"]
    post = await client.post(f"{BASE}/posts", json={"code": "dev", "name": "开发岗", "dept_id": dept_id})
    post_id = post.json()["data"]["id"]
    user_id = 1001

    assigned_posts = await client.put(f"{BASE}/user-posts/{user_id}", json={"post_ids": [post_id]})
    assert assigned_posts.status_code == 200 and assigned_posts.json()["data"]["post_ids"]

    listed_posts = await client.get(f"{BASE}/user-posts", params={"user_id": user_id})
    assert listed_posts.status_code == 200

    primary_post = await client.put(f"{BASE}/user-posts/{user_id}/primary", json={"post_id": post_id})
    assert primary_post.status_code == 200 and str(primary_post.json()["data"]["primary_post_id"]) == str(post_id)

    unassigned_post = await client.delete(f"{BASE}/user-posts/{user_id}/{post_id}")
    assert unassigned_post.status_code == 200

    assigned_depts = await client.put(f"{BASE}/user-depts/{user_id}", json={"dept_ids": [dept_id]})
    assert assigned_depts.status_code == 200 and assigned_depts.json()["data"]["dept_ids"]

    listed_depts = await client.get(f"{BASE}/user-depts/{user_id}")
    assert listed_depts.status_code == 200

    primary_dept = await client.put(f"{BASE}/user-depts/{user_id}/primary", json={"dept_id": dept_id})
    assert primary_dept.status_code == 200 and str(primary_dept.json()["data"]["primary_dept_id"]) == str(dept_id)

    unassigned_dept = await client.delete(f"{BASE}/user-depts/{user_id}/{dept_id}")
    assert unassigned_dept.status_code == 200


@pytest.mark.kiwi_id(2255)
async def test_role_assignment_routes(client: AsyncClient, authorized: None) -> None:
    """角色分配路由：角色-岗位与角色-部门的列表 / 全量覆盖 / 解绑全端点走通。"""
    dept = await client.post(f"{BASE}/depts", json={"code": "hq", "name": "总部"})
    dept_id = dept.json()["data"]["id"]
    post = await client.post(f"{BASE}/posts", json={"code": "dev", "name": "开发岗", "dept_id": dept_id})
    post_id = post.json()["data"]["id"]
    role_id = 2001

    assigned_posts = await client.put(f"{BASE}/role-posts/{role_id}", json={"post_ids": [post_id]})
    assert assigned_posts.status_code == 200
    assert (await client.get(f"{BASE}/role-posts", params={"role_id": role_id})).status_code == 200
    assert (await client.delete(f"{BASE}/role-posts/{role_id}/{post_id}")).status_code == 200

    assigned_depts = await client.put(f"{BASE}/role-depts/{role_id}", json={"dept_ids": [dept_id]})
    assert assigned_depts.status_code == 200
    assert (await client.get(f"{BASE}/role-depts", params={"role_id": role_id})).status_code == 200
    assert (await client.delete(f"{BASE}/role-depts/{role_id}/{dept_id}")).status_code == 200


@pytest.mark.kiwi_id(2255)
async def test_assignment_routes_idempotency_replay(
    service_app: FastAPI, client: AsyncClient, authorized: None
) -> None:
    """分配类路由幂等：同键重复提交直接返回上次结果（四个分配端点同口径）。"""
    stores: list[_ReplayStore] = []

    def _override(payload: dict[str, Any]) -> None:
        store = _ReplayStore(payload)
        stores.append(store)
        service_app.dependency_overrides[get_idempotency_store] = lambda: store

    _override({"post_ids": [5], "primary_post_id": 5})
    user_posts = await client.put(
        f"{BASE}/user-posts/1001", json={"post_ids": [5]}, headers={"Idempotency-Key": "up-replay"}
    )
    assert user_posts.status_code == 200 and str(user_posts.json()["data"]["primary_post_id"]) == "5"

    _override({"dept_ids": [6], "primary_dept_id": 6})
    user_depts = await client.put(
        f"{BASE}/user-depts/1001", json={"dept_ids": [6]}, headers={"Idempotency-Key": "ud-replay"}
    )
    assert user_depts.status_code == 200 and str(user_depts.json()["data"]["primary_dept_id"]) == "6"

    _override({"post_ids": [5]})
    role_posts = await client.put(
        f"{BASE}/role-posts/2001", json={"post_ids": [5]}, headers={"Idempotency-Key": "rp-replay"}
    )
    assert role_posts.status_code == 200

    _override({"dept_ids": [6]})
    role_depts = await client.put(
        f"{BASE}/role-depts/2001", json={"dept_ids": [6]}, headers={"Idempotency-Key": "rd-replay"}
    )
    assert role_depts.status_code == 200
    assert len(stores) == 4


@pytest.mark.kiwi_id(2255)
async def test_assignment_routes_idempotency_missing_payload_and_save(
    service_app: FastAPI, client: AsyncClient, authorized: None
) -> None:
    """分配类路由幂等：键被占用但无结果时继续执行；首次提交（带键）时保存结果。"""
    dept = await client.post(f"{BASE}/depts", json={"code": "hq", "name": "总部"})
    dept_id = dept.json()["data"]["id"]
    post = await client.post(f"{BASE}/posts", json={"code": "dev", "name": "开发岗", "dept_id": dept_id})
    post_id = post.json()["data"]["id"]

    service_app.dependency_overrides[get_idempotency_store] = lambda: _ReplayStore(None)
    assert (
        await client.put(f"{BASE}/user-posts/1002", json={"post_ids": [post_id]}, headers={"Idempotency-Key": "a"})
    ).status_code == 200
    assert (
        await client.put(f"{BASE}/user-depts/1002", json={"dept_ids": [dept_id]}, headers={"Idempotency-Key": "b"})
    ).status_code == 200
    assert (
        await client.put(f"{BASE}/role-posts/2002", json={"post_ids": [post_id]}, headers={"Idempotency-Key": "c"})
    ).status_code == 200
    assert (
        await client.put(f"{BASE}/role-depts/2002", json={"dept_ids": [dept_id]}, headers={"Idempotency-Key": "d"})
    ).status_code == 200

    service_app.dependency_overrides.pop(get_idempotency_store, None)
    assert (
        await client.put(f"{BASE}/user-posts/1003", json={"post_ids": [post_id]}, headers={"Idempotency-Key": "e"})
    ).status_code == 200
    assert (
        await client.put(f"{BASE}/user-depts/1003", json={"dept_ids": [dept_id]}, headers={"Idempotency-Key": "f"})
    ).status_code == 200
    assert (
        await client.put(f"{BASE}/role-posts/2003", json={"post_ids": [post_id]}, headers={"Idempotency-Key": "g"})
    ).status_code == 200
    assert (
        await client.put(f"{BASE}/role-depts/2003", json={"dept_ids": [dept_id]}, headers={"Idempotency-Key": "h"})
    ).status_code == 200


@pytest.mark.kiwi_id(2255)
async def test_create_continues_when_idempotency_payload_missing(
    service_app: FastAPI, client: AsyncClient, authorized: None
) -> None:
    """幂等键被占用但无结果（上次异常中断）：继续正常落库，不返回空响应。"""
    service_app.dependency_overrides[get_idempotency_store] = lambda: _ReplayStore(None)
    dept = await client.post(
        f"{BASE}/depts", json={"code": "hq", "name": "总部"}, headers={"Idempotency-Key": "half-dept"}
    )
    assert dept.status_code == 200
    post = await client.post(
        f"{BASE}/posts",
        json={"code": "dev", "name": "开发岗", "dept_id": dept.json()["data"]["id"]},
        headers={"Idempotency-Key": "half-post"},
    )
    assert post.status_code == 200
