"""组织只读出口路由（`/api/v1/org`）：组织数据源 / 名称回显 / 按用户解析角色。

- **出口与管面路径分离**：出口挂 `/org/data-source/{users,posts,dept-tree}`、`/org/resolve-names` 与
  `/org/user-roles`（管面占 `/org/posts` 等且带 `org:*` 权限码，两者语义与契约均不同）；
- **鉴权双通道**（`require_org_reader`）：已登录用户经 `require_auth`（网关可信身份或本地用户令牌 +
  会话标记）；服务间调用经**服务 JWT**（`aud=service`）且签发方在调用方白名单内；
- **数据范围与脱敏强制接入**：路由级 `get_dept_scope`（读基座 `DataScope` 并解析部门范围）与
  `Depends(get_masker)`（激活掩码上下文，`OrgUser.masked_fields` 生效）；调用方不可绕过（无旁路端点）；
- 出口**不挂 `org:*` 权限码**（面向跨产品消费、与平台 RBAC 解耦）。
"""

from collections.abc import Iterable
from typing import Annotated, cast

from bms_core.api.base import BaseRouter, page_query, require_auth
from bms_core.api.deps import (
    get_cache_region,
    get_config_source,
    get_masker,
    get_service_client,
    get_session_store,
    get_token_verifier,
    get_uow,
)
from bms_core.cache.base import CacheRegion
from bms_core.config.base import BaseConfigSource
from bms_core.core.concurrent import ConcurrentStableList
from bms_core.core.config import Settings
from bms_core.core.exceptions import AuthError, ParamError
from bms_core.core.logging import get_logger
from bms_core.core.plugin import resolve_plugin
from bms_core.db.session import DbSession
from bms_core.db.unit_of_work import UnitOfWork
from bms_core.oauth.token import TOKEN_AUDIENCE_SERVICE
from bms_core.oauth.verify import BaseTokenVerifier
from bms_core.schemas.common import ApiResponse
from bms_core.schemas.pagination import BasePageQuery, BasePageResponse
from bms_core.scope.base import DataScope, ScopeCondition
from bms_core.servicecall.base import BaseServiceClient
from bms_core.session.base import BaseSessionStore
from fastapi import Depends, Request

from mdm_org.org.base import OrgPost, OrgUser
from mdm_org.org.default import DbOrgDataSource, DbOrgNameResolver
from mdm_org.org.user_source import PlatformOrgUserSource
from mdm_org.repositories.dept import DeptRepository
from mdm_org.repositories.post import PostRepository
from mdm_org.repositories.role_dept import RoleDeptRepository
from mdm_org.repositories.role_post import RolePostRepository
from mdm_org.repositories.user_dept import UserDeptRepository
from mdm_org.repositories.user_post import UserPostRepository
from mdm_org.schemas.open_read import OrgDeptTree, OrgNameRefs, OrgUserRoles
from mdm_org.services.open_read import OpenReadService

ORG_READER_SERVICES: tuple[str, ...] = ("platform",)
"""允许经**服务身份**调用组织只读出口的调用方服务标识（`VerifiedToken.service`）。

当前唯一消费方为 bms platform（角色 / 授权与权限计算同落 platform 服务租户库）；后续接入方按需追加。
"""

MAX_RESOLVE_IDS = 200
"""名称回显单次 id 数上限（超限即参数校验错误，防误用大集合拖垮出口）。"""

DEPT_SCOPE_FIELDS: tuple[str, ...] = ("dept_id", "dept_ids")
"""数据范围条件中按部门限定的字段名（其余形态忽略）。"""

_LOGGER = get_logger("mdm.org.open_read")


async def require_org_reader(
    request: Request,
    verifier: Annotated[BaseTokenVerifier, Depends(get_token_verifier)],
    store: Annotated[BaseSessionStore, Depends(get_session_store)],
) -> None:
    """出口鉴权（双通道）：服务身份（白名单）优先，否则回落登录态校验。

    服务间调用（东西向直连不经网关）由基座边缘信任按服务 JWT 验签并解析租户（`tenant_id` claim）；
    未被识别为服务身份时一律走 `require_auth`（网关可信身份 / 本地用户令牌 + 会话标记）。

    Args:
        request: 请求对象。
        verifier: 统一令牌校验器。
        store: 会话标记存储。

    Raises:
        AuthError: 缺少 / 无效凭证；或服务身份不在允许清单（20001 / 401）。
        SessionAuthError: 登录态会话标记缺失 / 不一致（20012 / 401）。
    """
    token = _bearer_token(request.headers.get("Authorization"))
    if token is not None:
        service = await _service_identity(verifier, token)
        if service is not None:
            if service in ORG_READER_SERVICES:
                return
            raise AuthError("服务身份不在允许清单")
    await require_auth(request, verifier, store)


async def get_dept_scope(request: Request) -> ConcurrentStableList[int] | None:
    """数据范围依赖：读基座 `DataScope` 并解析为「限定部门 id 集合」。

    RBAC 未交付期间 `DataScope` 为占位实现（`read_predicate()` 返回 None）→ 不限定；
    条件为部门形态（`dept_id` / `dept_ids`）时按之限定；其余形态记录告警后忽略（真实规则随 RBAC 阶段）。

    Args:
        request: 请求对象。

    Returns:
        ConcurrentStableList[int] | None: 限定部门 id；None 表示不限定。
    """
    settings = cast("Settings", request.app.state.settings)
    scope = cast(
        "DataScope",
        resolve_plugin("data_scope", settings.data_scope.provider, expected_version=DataScope.contract_version),
    )
    return dept_scope_from_predicate(scope.read_predicate())


router = BaseRouter(
    key="org_open_read",
    prefix="/org",
    tags=["org-open-read"],
    dependencies=[Depends(require_org_reader), Depends(get_masker)],
)

UowDep = Annotated[UnitOfWork, Depends(get_uow)]
ConfigDep = Annotated[BaseConfigSource, Depends(get_config_source)]
CacheDep = Annotated[CacheRegion, Depends(get_cache_region)]
ClientDep = Annotated[BaseServiceClient, Depends(get_service_client)]
PageDep = Annotated[BasePageQuery, Depends(page_query)]
ScopeDep = Annotated[ConcurrentStableList[int] | None, Depends(get_dept_scope)]


@router.get("/data-source/users")
async def list_users(
    query: PageDep,
    scope: ScopeDep,
    uow: UowDep,
    config: ConfigDep,
    cache: CacheDep,
    client: ClientDep,
    dept_id: int | None = None,
    include_children: bool = False,
    status: str | None = None,
    keyword: str | None = None,
) -> ApiResponse[BasePageResponse[OrgUser]]:
    """组织数据源 · 用户（关键字 / 部门 / 含子级 / 状态 / 分页）。

    部门过滤口径：映射为「该部门含子树下岗位、且用户已分配该岗位」的候选集——
    用户归属部门归本域 `org_user_dept`（2026-10-09 起），**不经平台字段**（`sys_user` 不落组织字段）。
    """
    service = _service(scope, uow, config, cache, client)
    return ApiResponse.ok(
        await service.users(
            keyword,
            dept_id=dept_id,
            include_children=include_children,
            status=status,
            page=query.page,
            size=query.size,
        )
    )


@router.get("/data-source/posts")
async def list_posts(
    query: PageDep,
    scope: ScopeDep,
    uow: UowDep,
    config: ConfigDep,
    cache: CacheDep,
    client: ClientDep,
    dept_id: int | None = None,
    include_children: bool = False,
    status: str | None = None,
    keyword: str | None = None,
) -> ApiResponse[BasePageResponse[OrgPost]]:
    """组织数据源 · 岗位（关键字 / 部门含子级 / 状态 / 分页）。"""
    service = _service(scope, uow, config, cache, client)
    return ApiResponse.ok(
        await service.posts(
            keyword,
            dept_id=dept_id,
            include_children=include_children,
            status=status,
            page=query.page,
            size=query.size,
        )
    )


@router.get("/data-source/dept-tree")
async def get_dept_tree(
    scope: ScopeDep,
    uow: UowDep,
    config: ConfigDep,
    cache: CacheDep,
    client: ClientDep,
    status: str | None = None,
) -> ApiResponse[OrgDeptTree]:
    """组织数据源 · 部门树（一次性返回、不分页；数据范围限定外的部门不入树）。"""
    service = _service(scope, uow, config, cache, client)
    return ApiResponse.ok(OrgDeptTree(items=await service.dept_tree(status=status)))


@router.get("/resolve-names")
async def resolve_names(
    scope: ScopeDep,
    uow: UowDep,
    config: ConfigDep,
    cache: CacheDep,
    client: ClientDep,
    target: str = "user",
    id_in: str = "",
) -> ApiResponse[OrgNameRefs]:
    """名称回显（`target` + `id_in` 逗号分隔；未命中项占位、不抛错）。"""
    service = _service(scope, uow, config, cache, client)
    return ApiResponse.ok(OrgNameRefs(items=await service.resolve_names(target, _parse_ids(id_in))))


@router.get("/user-roles")
async def get_user_roles(
    scope: ScopeDep,
    uow: UowDep,
    config: ConfigDep,
    cache: CacheDep,
    client: ClientDep,
    user_id: int,
) -> ApiResponse[OrgUserRoles]:
    """按用户解析其经岗位 / 部门获得的角色（并集去重；结果短时缓存 + 写侧失效代）。

    供 bms 权限引擎跨服务汇总（用户直接角色 `sys_user_role` 由消费方合并）。
    """
    service = _service(scope, uow, config, cache, client)
    return ApiResponse.ok(OrgUserRoles(role_ids=await service.user_roles(user_id)))


def _service(
    scope: ConcurrentStableList[int] | None,
    uow: UnitOfWork,
    config: BaseConfigSource,
    cache: CacheRegion,
    client: BaseServiceClient,
) -> OpenReadService:
    """组装出口服务（请求级会话 + 数据范围 + 用户来源 + 缓存）。

    Args:
        scope: 数据范围限定的部门 id（None = 不限定）。
        uow: 工作单元（请求级会话）。
        config: 系统参数取数。
        cache: 缓存域。
        client: 服务间调用客户端（用户来源）。

    Returns:
        OpenReadService: 出口服务。
    """
    session = cast("DbSession", uow.session)
    depts = DeptRepository(session)
    posts = PostRepository(session)
    user_posts = UserPostRepository(session)
    users = PlatformOrgUserSource(client)
    return OpenReadService(
        data_source=DbOrgDataSource(
            depts=depts,
            posts=posts,
            user_posts=user_posts,
            users=users,
            config=config,
            dept_scope=scope,
        ),
        resolver=DbOrgNameResolver(depts=depts, posts=posts, users=users),
        user_depts=UserDeptRepository(session),
        user_posts=user_posts,
        role_posts=RolePostRepository(session),
        role_depts=RoleDeptRepository(session),
        cache=cache,
        config=config,
    )


def _bearer_token(authorization: str | None) -> str | None:
    """取 Bearer 令牌（大小写不敏感）。

    Args:
        authorization: `Authorization` 头原始值。

    Returns:
        str | None: 令牌紧凑串；缺失 / 非 Bearer 为 None。
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return authorization[7:].strip() or None


async def _service_identity(verifier: BaseTokenVerifier, token: str) -> str | None:
    """识别服务身份（`aud=service`）；非服务令牌返回 None（交由登录态校验处理）。

    Args:
        verifier: 统一令牌校验器。
        token: 令牌紧凑串。

    Returns:
        str | None: 调用方服务标识；非服务身份 / 校验失败为 None。

    Raises:
        AuthError: 服务令牌有效但缺少服务标识（20001 / 401）。
    """
    try:
        verified = await verifier.verify(token, audience=TOKEN_AUDIENCE_SERVICE)
    except AuthError:
        return None
    service = verified.service or ""
    if not service:
        raise AuthError("服务身份缺少服务标识")
    return service


def dept_scope_from_predicate(predicate: object) -> ConcurrentStableList[int] | None:
    """把数据范围读条件解析为限定部门 id 集合（无法识别返回 None = 不限定）。

    Args:
        predicate: `DataScope.read_predicate()` 返回值（`ScopeCondition` / 条件序列 / None）。

    Returns:
        ConcurrentStableList[int] | None: 限定部门 id；None 表示不限定。
    """
    if predicate is None:
        return None
    conditions = _as_items(predicate)
    ids: ConcurrentStableList[int] = ConcurrentStableList()
    recognized = False
    for item in conditions:
        if not isinstance(item, ScopeCondition) or item.field not in DEPT_SCOPE_FIELDS:
            _LOGGER.warning("数据范围条件暂不支持，已忽略", field=getattr(item, "field", None))
            continue
        recognized = True
        for value in _int_values(item.value):
            if value not in ids:
                ids.add(value)
    if not recognized:
        return None
    return ids


def _int_values(value: object) -> ConcurrentStableList[int]:
    """取条件值中的整数集合（标量 / 序列 / 数字字符串）。

    Args:
        value: 条件值。

    Returns:
        ConcurrentStableList[int]: 整数集合（不可识别为空）。
    """
    values: ConcurrentStableList[int] = ConcurrentStableList()
    for item in _as_items(value):
        if isinstance(item, bool):
            continue
        if isinstance(item, int):
            values.add(item)
        elif isinstance(item, str) and item.strip().lstrip("-").isdigit():
            values.add(int(item))
    return values


def _as_items(value: object) -> ConcurrentStableList[object]:
    """把数据范围读条件规整为元素序列（标量视为单元素；None 为空）。

    兼容形态：`ScopeCondition` 单条 / 条件序列（内建序列或基座集合类——`ConcurrentStableList` 是
    `Sequence` 而非 `list` 子类，故按 `Iterable` 判定而非具体容器类型）。

    Args:
        value: 条件值。

    Returns:
        ConcurrentStableList[object]: 元素序列。
    """
    items: ConcurrentStableList[object] = ConcurrentStableList()
    if value is None:
        return items
    if isinstance(value, (str, bytes, ScopeCondition)) or not isinstance(value, Iterable):
        items.add(value)
        return items
    for item in cast("Iterable[object]", value):
        items.add(item)
    return items


def _parse_ids(raw: str) -> ConcurrentStableList[int]:
    """解析 `id_in` 查询参数（逗号分隔整数；去重保序、超上限即拒）。

    Args:
        raw: 原始参数值。

    Returns:
        ConcurrentStableList[int]: id 序列。

    Raises:
        ParamError: 元素非整数或数量超上限（10001）。
    """
    ids: ConcurrentStableList[int] = ConcurrentStableList()
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        if not token.lstrip("-").isdigit():
            raise ParamError(f"回显 id 非法：{token!r}")
        value = int(token)
        if value not in ids:
            ids.add(value)
    if len(ids) > MAX_RESOLVE_IDS:
        raise ParamError(f"回显 id 数超上限：{len(ids)} > {MAX_RESOLVE_IDS}")
    return ids


__all__ = [
    "DEPT_SCOPE_FIELDS",
    "MAX_RESOLVE_IDS",
    "ORG_READER_SERVICES",
    "dept_scope_from_predicate",
    "get_dept_scope",
    "require_org_reader",
    "router",
]
