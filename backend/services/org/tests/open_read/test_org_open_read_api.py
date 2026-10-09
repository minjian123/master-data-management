"""组织只读出口路由用例（Kiwi 2256）：鉴权双通道 / 响应包装形态 / 参数校验 / 用户来源降级。

用法：出口正常路径覆写 `require_org_reader`（专注出口行为）；鉴权分支则**保留真实依赖**，只注入令牌
校验替身，从 HTTP 面断言 401 与放行。
"""

import pytest
from bms_core.api.deps import get_service_client, get_uow
from bms_core.core.concurrent import ConcurrentStableDict, ConcurrentStableList
from bms_core.core.exceptions import AuthError, ServiceUnavailableError
from bms_core.oauth.token import TOKEN_AUDIENCE_SERVICE
from bms_core.oauth.verify import BaseTokenVerifier, VerifiedToken, get_token_verifier
from bms_core.scope.base import ScopeCondition
from bms_core.servicecall.base import BaseServiceClient, ServiceRequest, ServiceResponse
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from mdm_org.api.open_read import dept_scope_from_predicate, require_org_reader
from mdm_org.errors import OrgSourceUnavailableError
from mdm_org.org.user_source import PlatformOrgUserSource
from tests_support import org_env

EXIT_BASE = "/api/v1/org"
"""出口路径前缀（管面占 `/org/posts` 等，出口集中挂 `/org/data-source/*` 等）。"""


class _UnreachableClient(BaseServiceClient):
    """服务间调用替身：任何调用即抛服务不可用（模拟平台用户只读出口不可达）。"""

    plugin_name: str = "unreachable"

    async def call(self, request: ServiceRequest) -> ServiceResponse:
        """发起调用（恒失败）。

        Args:
            request: 调用请求（忽略）。

        Raises:
            ServiceUnavailableError: 恒抛（10007 / 503）。
        """
        del request
        raise ServiceUnavailableError("下游不可达（替身）")


class _VerifierStub(BaseTokenVerifier):
    """令牌校验替身：服务受众按注入的服务标识放行；其余受众一律拒（驱动登录态回落分支）。"""

    plugin_name: str = "stub"

    def __init__(self, *, service: str | None = None) -> None:
        """初始化。

        Args:
            service: 服务受众校验通过时的服务标识；None 表示服务受众也拒。
        """
        self._service = service

    async def verify(self, token: str, *, audience: str) -> VerifiedToken:
        """校验令牌（服务受众按注入值放行，其余恒拒）。

        Args:
            token: 令牌紧凑串（替身忽略）。
            audience: 期望受众。

        Returns:
            VerifiedToken: 服务身份声明（注入空串时服务标识为空，用于覆盖「缺服务标识」分支）。

        Raises:
            AuthError: 非服务受众或未注入服务标识（20001 / 401）。
        """
        del token
        if audience == TOKEN_AUDIENCE_SERVICE and self._service is not None:
            return VerifiedToken(subject="gateway", service=self._service, audience=(audience,))
        raise AuthError("用户令牌不可用（替身）")


async def _prepare(
    service_app: FastAPI,
    session: AsyncSession,
    *,
    client: BaseServiceClient,
    service_identity: bool,
) -> None:
    """装配依赖覆写：会话 / 用户来源客户端 / 出口鉴权（按需放行）。

    Args:
        service_app: 应用实例。
        session: 请求级会话。
        client: 用户来源客户端替身。
        service_identity: 是否绕过出口鉴权（正常路径用）。
    """
    service_app.dependency_overrides[get_uow] = lambda: org_env.make_uow(session)
    service_app.dependency_overrides[get_service_client] = lambda: client
    if service_identity:
        service_app.dependency_overrides[require_org_reader] = lambda: None


@pytest.mark.kiwi_id(2256)
async def test_exit_endpoints_wrap_contract_shapes(service_app: FastAPI, client: AsyncClient) -> None:
    """出口四取数端点：响应包装形态（`items` / 分页 `list`）/ 关键字与部门过滤 / 用户手机邮箱字段。"""
    session, engine = await org_env.make_session()
    try:
        key = await org_env.seed_org_tree(session)
        users = ConcurrentStableList([org_env.user(2001, nickname="张三", phone="13800000001", email="a@example.com")])
        await _prepare(
            service_app,
            session,
            client=org_env.StubPlatformClient(users),
            service_identity=True,
        )

        tree = await client.get(f"{EXIT_BASE}/data-source/dept-tree")
        assert tree.status_code == 200
        body = tree.json()
        assert body["code"] == 0
        assert [node["name"] for node in body["data"]["items"]] == ["研发中心", "市场部"]

        posts = await client.get(
            f"{EXIT_BASE}/data-source/posts",
            params={"dept_id": key["root"], "include_children": True},
        )
        posts_body = posts.json()["data"]
        assert [item["code"] for item in posts_body["list"]] == ["dev_lead", "dev"]
        assert posts_body["total"] == 2 and posts_body["page"] == 1

        users_resp = await client.get(f"{EXIT_BASE}/data-source/users", params={"keyword": "张"})
        user_items = users_resp.json()["data"]["list"]
        # 雪花 id 在响应中按字符串序列化（前端按字符串消费）
        assert [int(item["id"]) for item in user_items] == [2001]
        assert user_items[0]["nickname"] == "张三"
        assert "dept_id" not in user_items[0], "用户归属部门归 mdm `org_user_dept`，出口不再带该字段"

        roles = await client.get(f"{EXIT_BASE}/user-roles", params={"user_id": 2001})
        assert roles.json()["data"] == {"role_ids": []}
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2256)
async def test_resolve_names_wraps_items_and_validates_params(service_app: FastAPI, client: AsyncClient) -> None:
    """名称回显：`items` 包装、未命中占位；目标非法 / id 非整数 / id 数超上限一律参数错误（10001）。"""
    session, engine = await org_env.make_session()
    try:
        key = await org_env.seed_org_tree(session)
        await _prepare(
            service_app,
            session,
            client=org_env.StubPlatformClient(ConcurrentStableList([org_env.user(2001, nickname="张三")])),
            service_identity=True,
        )

        resp = await client.get(
            f"{EXIT_BASE}/resolve-names",
            params={"target": "post", "id_in": f"{key['eng']},999999"},
        )
        items = resp.json()["data"]["items"]
        assert items[0]["name"] == "开发工程师" and items[0]["exists"] is True
        assert items[1] == {"id": "999999", "name": "", "target": "post", "exists": False, "status": "disabled"}

        resp = await client.get(f"{EXIT_BASE}/resolve-names", params={"target": "user", "id_in": "2001"})
        assert resp.json()["data"]["items"][0]["name"] == "张三"

        # 业务失败统一 HTTP 200 + 统一响应 code（对齐基座口径，不裸 4xx / 500）
        bad_target = await client.get(f"{EXIT_BASE}/resolve-names", params={"target": "role", "id_in": "1"})
        assert bad_target.status_code == 200 and bad_target.json()["code"] == 10001

        bad_id = await client.get(f"{EXIT_BASE}/resolve-names", params={"target": "post", "id_in": "abc"})
        assert bad_id.status_code == 200 and bad_id.json()["code"] == 10001

        too_many = await client.get(
            f"{EXIT_BASE}/resolve-names",
            params={"target": "post", "id_in": ",".join(str(index) for index in range(201))},
        )
        assert too_many.json()["code"] == 10001

        # 空段 / 尾逗号被忽略（去重保序）
        blanks = await client.get(f"{EXIT_BASE}/resolve-names", params={"target": "post", "id_in": ",,"})
        assert blanks.json()["data"]["items"] == []
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2256)
async def test_user_dimension_degrades_when_platform_unreachable(service_app: FastAPI, client: AsyncClient) -> None:
    """用户来源不可达：用户维度出口 330101（业务失败，HTTP 200）；组织维度与按用户解析角色不受影响。"""
    session, engine = await org_env.make_session()
    try:
        await org_env.seed_org_tree(session)
        await _prepare(service_app, session, client=_UnreachableClient(), service_identity=True)

        resp = await client.get(f"{EXIT_BASE}/data-source/users")
        assert resp.status_code == 200 and resp.json()["code"] == 330101

        # 按用户解析角色不再依赖平台用户来源（部门链取本域 `org_user_dept`）→ 正常返回
        roles = await client.get(f"{EXIT_BASE}/user-roles", params={"user_id": 2001})
        assert roles.json()["code"] == 0 and roles.json()["data"]["role_ids"] == []

        posts = await client.get(f"{EXIT_BASE}/data-source/posts", params={"keyword": "dev"})
        assert posts.json()["code"] == 0
        assert [item["code"] for item in posts.json()["data"]["list"]] == ["dev_lead", "dev"]

        tree = await client.get(f"{EXIT_BASE}/data-source/dept-tree")
        assert [node["name"] for node in tree.json()["data"]["items"]] == ["研发中心", "市场部"]
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2256)
async def test_exit_rejects_missing_credentials(service_app: FastAPI, client: AsyncClient) -> None:
    """出口鉴权：无任何凭证即 401（回落登录态校验，不因出口而放行）。"""
    session, engine = await org_env.make_session()
    try:
        await _prepare(
            service_app,
            session,
            client=org_env.StubPlatformClient(),
            service_identity=False,
        )
        resp = await client.get(f"{EXIT_BASE}/data-source/dept-tree")
        assert resp.status_code == 401 and resp.json()["code"] == 20001
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2256)
async def test_exit_service_identity_whitelist(service_app: FastAPI, client: AsyncClient) -> None:
    """出口鉴权：白名单内服务身份（platform）放行；白名单外服务身份拒绝；非服务令牌回落登录态校验。"""
    session, engine = await org_env.make_session()
    try:
        await org_env.seed_org_tree(session)
        await _prepare(
            service_app,
            session,
            client=org_env.StubPlatformClient(),
            service_identity=False,
        )
        service_app.dependency_overrides[get_token_verifier] = lambda: _VerifierStub(service="platform")
        headers = {"Authorization": "Bearer stub-token"}
        allowed = await client.get(f"{EXIT_BASE}/data-source/dept-tree", headers=headers)
        assert allowed.status_code == 200
        assert [node["name"] for node in allowed.json()["data"]["items"]] == ["研发中心", "市场部"]

        service_app.dependency_overrides[get_token_verifier] = lambda: _VerifierStub(service="identity")
        denied = await client.get(f"{EXIT_BASE}/data-source/dept-tree", headers=headers)
        assert denied.status_code == 401 and denied.json()["code"] == 20001

        # 非服务令牌（服务受众校验失败）→ 回落登录态校验（替身对 api 受众同样拒）→ 401
        service_app.dependency_overrides[get_token_verifier] = lambda: _VerifierStub()
        fallback = await client.get(f"{EXIT_BASE}/data-source/dept-tree", headers=headers)
        assert fallback.status_code == 401 and fallback.json()["code"] == 20001

        # 有效服务令牌但缺服务标识（sub=gateway 之类）→ 明确拒绝，不当作登录态放行
        service_app.dependency_overrides[get_token_verifier] = lambda: _VerifierStub(service="")
        nameless = await client.get(f"{EXIT_BASE}/data-source/dept-tree", headers=headers)
        assert nameless.status_code == 401 and nameless.json()["code"] == 20001
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2256)
async def test_exit_contract_is_separated_from_admin_face(service_app: FastAPI, client: AsyncClient) -> None:
    """出口与管理面路径分离：`/org/posts` 仍是管理面（出口挂 `/org/data-source/posts`）。"""
    session, engine = await org_env.make_session()
    try:
        await _prepare(
            service_app,
            session,
            client=org_env.StubPlatformClient(),
            service_identity=True,
        )
        admin = await client.get(f"{EXIT_BASE}/posts")
        assert admin.status_code in (200, 401, 403)

        exit_posts = await client.get(f"{EXIT_BASE}/data-source/posts")
        assert exit_posts.status_code == 200 and exit_posts.json()["code"] == 0
    finally:
        await engine.dispose()


def _scoped(predicate: object) -> ConcurrentStableList[int]:
    """取数据范围解析结果的部门 id（不限定视为空便于断言）。

    Args:
        predicate: 数据范围读条件。

    Returns:
        ConcurrentStableList[int]: 限定部门 id（不限定 / 不可识别视为空）。
    """
    resolved = dept_scope_from_predicate(predicate)
    return ConcurrentStableList() if resolved is None else resolved


@pytest.mark.kiwi_id(2256)
async def test_data_scope_predicate_parsing() -> None:
    """数据范围读条件解析：部门条件（单条 / 序列 / 数字字符串）限定部门；其他形态与不可识别值处理。

    RBAC 未交付期间 `DataScope` 为占位（`read_predicate()` 返回 None）→ 不限定；条件为部门形态时
    按之限定，其余形态记 warning 后忽略（不误判为「允许全部」以外的语义）。
    """
    assert dept_scope_from_predicate(None) is None
    assert _scoped(ScopeCondition(field="dept_id", operator="in", value=[3, 4])) == [3, 4]
    assert _scoped(ScopeCondition(field="dept_ids", value="5")) == [5]
    assert _scoped(ScopeCondition(field="dept_id", value=9)) == [9]
    assert _scoped(ConcurrentStableList([ScopeCondition(field="dept_id", operator="eq", value=7)])) == [7]
    # 条件值中的布尔 / 非数字字符串 / None 一律忽略，负整数字符串可用
    assert _scoped(ScopeCondition(field="dept_id", value=[True, 1, "2", "-3", "x", None])) == [1, 2, -3]
    # 非部门形态忽略（回落不限定）；部门形态但取值不可识别 → 空集（不误放宽为全量）
    assert dept_scope_from_predicate(ScopeCondition(field="user_id", operator="eq", value=1)) is None
    assert _scoped(ScopeCondition(field="dept_id", operator="eq", value=None)) == []


@pytest.mark.kiwi_id(2256)
async def test_platform_user_source_maps_rows_and_fails_closed() -> None:
    """用户来源实现：只读行归一（`name` → 昵称 / 联系方式 / 头像恒空；**部门不再取自平台**）；不可达 /
    非 2xx / 业务失败 / 返回契约非法一律 330101（fail-closed，不静默降级为空）。"""
    users = ConcurrentStableList([org_env.user(2001, nickname="张三", phone="13800000001")])
    source = PlatformOrgUserSource(org_env.StubPlatformClient(users))

    page = await source.query("张", status="enabled")
    assert [item.id for item in page.list] == [2001]
    assert page.list[0].nickname == "张三" and page.list[0].avatar is None
    assert page.total == 1 and page.page == 1 and page.size == 20
    assert [item.id for item in await source.by_ids(org_env.ids(2001, 2002))] == [2001]
    assert list(await source.by_ids(org_env.ids())) == []

    with pytest.raises(OrgSourceUnavailableError) as unreachable:
        await PlatformOrgUserSource(_UnreachableClient()).query()
    assert unreachable.value.code == 330101

    with pytest.raises(OrgSourceUnavailableError):
        await PlatformOrgUserSource(org_env.StubPlatformClient(users, status_code=503)).query()

    with pytest.raises(OrgSourceUnavailableError):
        await PlatformOrgUserSource(org_env.StubPlatformClient(users, code=10010)).query()

    with pytest.raises(OrgSourceUnavailableError):
        await PlatformOrgUserSource(
            org_env.StubPlatformClient(payload=ConcurrentStableDict({"code": 0, "message": "", "data": "非法"}))
        ).query()

    with pytest.raises(OrgSourceUnavailableError):
        await PlatformOrgUserSource(
            org_env.StubPlatformClient(
                payload=ConcurrentStableDict(
                    {"code": 0, "message": "", "data": ConcurrentStableDict({"list": [{"id": 1}]})}
                )
            )
        ).query()

    with pytest.raises(OrgSourceUnavailableError):
        await PlatformOrgUserSource(
            org_env.StubPlatformClient(
                payload=ConcurrentStableDict(
                    {
                        "code": 0,
                        "message": "",
                        "data": ConcurrentStableDict(
                            {
                                "list": [
                                    ConcurrentStableDict(
                                        {"id": "1", "username": "u1", "name": "非法 id", "status": "enabled"}
                                    )
                                ]
                            }
                        ),
                    }
                )
            )
        ).query()
