"""组织域**内部写通道**路由（`/api/v1/org/internal/*`；宿主编排以服务身份写入）。

- **鉴权**：仅接受**服务身份**（服务 JWT，`aud=service`）且签发方在调用方白名单内＝`platform`
  （bms 平台服务，宿主编排发起方）；登录态令牌与其它服务身份一律拒（`10010` / `20001`）。
  **不挂 `org:*` 权限码**（与只读出口双通道同构，东西向不经网关、无旁路）。
- **幂等**：接受 `Idempotency-Key`（宿主编排生成的同一业务幂等键，按 `tenant` 归一）；同键重复提交
  返回**同结果**（载荷回放，不重复写入）。
- **口径不放松**：复用**同一套服务层**（校验 / 事务 / 事件 / `user-roles` 失效代 / 审计），
  仅因「内部通道」而**不**绕过任何校验。
- **基线快照与收敛版本不提供**（2026-10-09 拍板）：强一致专项（bms `05_07`）已就绪，
  `provider = null` 的过渡期基线与屏障判据属废路径；编排所需「生效后集合」由写端点**响应回带**。
"""

from typing import Annotated, cast

from bms_core.api.base import BaseRouter, require_service
from bms_core.api.deps import (
    get_audit_capturer,
    get_cache_region,
    get_config_source,
    get_idempotency_store,
    get_outbox_store,
    get_uow,
)
from bms_core.audit.base import AuditCapturer
from bms_core.cache.base import CacheRegion
from bms_core.config.base import BaseConfigSource
from bms_core.core.concurrent import ConcurrentStableList
from bms_core.core.context import current_user_id
from bms_core.db.session import DbSession
from bms_core.db.tenant import current_tenant_id_str
from bms_core.db.unit_of_work import UnitOfWork
from bms_core.idempotency.base import IDEMPOTENCY_HEADER, IdempotencyStore, build_idempotency_key
from bms_core.outbox.base import BaseOutboxStore
from bms_core.schemas.common import ApiResponse
from fastapi import Depends, Header

from mdm_org.repositories.dept import DeptRepository
from mdm_org.repositories.post import PostRepository
from mdm_org.repositories.role_dept import RoleDeptRepository
from mdm_org.repositories.role_post import RolePostRepository
from mdm_org.repositories.user_dept import UserDeptRepository
from mdm_org.repositories.user_post import UserPostRepository
from mdm_org.schemas.internal import (
    InternalRoleDeptRequest,
    InternalRolePostRequest,
    InternalUserDeptRequest,
    InternalUserPostRequest,
)
from mdm_org.schemas.role_dept import RoleDeptIds
from mdm_org.schemas.role_post import RolePostIds
from mdm_org.schemas.user_dept import UserDeptIds
from mdm_org.schemas.user_post import UserPostIds
from mdm_org.services.open_read import bump_user_roles_generation
from mdm_org.services.role_dept import RoleDeptService
from mdm_org.services.role_post import RolePostService
from mdm_org.services.user_dept import UserDeptService
from mdm_org.services.user_post import UserPostService

router = BaseRouter(
    key="org_internal_assign",
    prefix="/org/internal",
    tags=["org-internal"],
    dependencies=[Depends(require_service("platform"))],
)

UowDep = Annotated[UnitOfWork, Depends(get_uow)]
ConfigDep = Annotated[BaseConfigSource, Depends(get_config_source)]
CacheDep = Annotated[CacheRegion, Depends(get_cache_region)]
OutboxDep = Annotated[BaseOutboxStore, Depends(get_outbox_store)]
AuditDep = Annotated[AuditCapturer, Depends(get_audit_capturer)]
IdempotencyDep = Annotated[IdempotencyStore, Depends(get_idempotency_store)]
IdempotencyKeyHeader = Annotated[
    str | None, Header(alias=IDEMPOTENCY_HEADER, description="业务幂等键（同键重复提交返回同结果）")
]


def _audit(capturer: AuditCapturer, table: str, model_id: int) -> None:
    """内部写审计占位（与公开面同一捕获器）。

    服务身份下无登录用户 ⇒ `actor` 为空（服务主体由**调用方令牌**与结构化操作日志承载，
    审计表 `actor` 字段语义为「登录用户 id」，不塞入服务标识）。

    Args:
        capturer: 审计捕获基座。
        table: 受影响表名。
        model_id: 受影响实体 id（用户 / 角色）。
    """
    capturer.capture(table=table, model_id=model_id, changes=ConcurrentStableList(), actor=current_user_id.get())


def _user_post_service(uow: UnitOfWork, config: BaseConfigSource, outbox: BaseOutboxStore) -> UserPostService:
    """组装用户-岗位分配服务。"""
    session = cast("DbSession", uow.session)
    return UserPostService(UserPostRepository(session), PostRepository(session), uow, config, outbox)


def _user_dept_service(uow: UnitOfWork, config: BaseConfigSource, outbox: BaseOutboxStore) -> UserDeptService:
    """组装用户-部门分配服务。"""
    session = cast("DbSession", uow.session)
    return UserDeptService(UserDeptRepository(session), DeptRepository(session), uow, config, outbox)


def _role_post_service(uow: UnitOfWork, outbox: BaseOutboxStore) -> RolePostService:
    """组装角色-岗位分配服务。"""
    session = cast("DbSession", uow.session)
    return RolePostService(RolePostRepository(session), PostRepository(session), uow, outbox)


def _role_dept_service(uow: UnitOfWork, outbox: BaseOutboxStore) -> RoleDeptService:
    """组装角色-部门分配服务。"""
    session = cast("DbSession", uow.session)
    return RoleDeptService(RoleDeptRepository(session), DeptRepository(session), uow, outbox)


async def _user_post_ids(service: UserPostService, user_id: int) -> UserPostIds:
    """组装「已分配岗位 + 主要岗位」响应。"""
    return UserPostIds(
        post_ids=await service.list_user_posts(user_id), primary_post_id=await service.primary_post_id(user_id)
    )


async def _user_dept_ids(service: UserDeptService, user_id: int) -> UserDeptIds:
    """组装「已分配部门 + 主要部门」响应。"""
    return UserDeptIds(
        dept_ids=await service.list_user_depts(user_id), primary_dept_id=await service.primary_dept_id(user_id)
    )


@router.put("/user-posts/{user_id}")
async def internal_assign_user_posts(
    user_id: int,
    req: InternalUserPostRequest,
    uow: UowDep,
    config: ConfigDep,
    outbox: OutboxDep,
    cache: CacheDep,
    audit: AuditDep,
    idempotency: IdempotencyDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> ApiResponse[UserPostIds]:
    """内部全量覆盖用户岗位 + 主要岗位（服务身份 `platform`）。

    与公开面同源：上限 / 不存在 / 主项归属校验、事件与失效代一致；支持幂等键；响应回生效后集合与主要项。
    """
    key = build_idempotency_key(key=idempotency_key, tenant=current_tenant_id_str()) if idempotency_key else ""
    if key and not await idempotency.begin(key):
        payload = await idempotency.load(key)
        if payload is not None:
            return ApiResponse.ok(UserPostIds.model_validate(payload))
    service = _user_post_service(uow, config, outbox)
    await service.assign_user_posts(user_id=user_id, post_ids=req.post_ids)
    if req.primary_post_id is not None:
        await service.set_primary_post(user_id=user_id, post_id=req.primary_post_id)
    result = await _user_post_ids(service, user_id)
    _audit(audit, "org_user_post", user_id)
    await bump_user_roles_generation(cache, current_tenant_id_str())
    if key:
        await idempotency.save(key, result.model_dump(mode="json"))
    return ApiResponse.ok(result)


@router.put("/user-depts/{user_id}")
async def internal_assign_user_depts(
    user_id: int,
    req: InternalUserDeptRequest,
    uow: UowDep,
    config: ConfigDep,
    outbox: OutboxDep,
    cache: CacheDep,
    audit: AuditDep,
    idempotency: IdempotencyDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> ApiResponse[UserDeptIds]:
    """内部全量覆盖用户部门 + 主要部门（服务身份 `platform`）。"""
    key = build_idempotency_key(key=idempotency_key, tenant=current_tenant_id_str()) if idempotency_key else ""
    if key and not await idempotency.begin(key):
        payload = await idempotency.load(key)
        if payload is not None:
            return ApiResponse.ok(UserDeptIds.model_validate(payload))
    service = _user_dept_service(uow, config, outbox)
    await service.assign_user_depts(user_id=user_id, dept_ids=req.dept_ids)
    if req.primary_dept_id is not None:
        await service.set_primary_dept(user_id=user_id, dept_id=req.primary_dept_id)
    result = await _user_dept_ids(service, user_id)
    _audit(audit, "org_user_dept", user_id)
    await bump_user_roles_generation(cache, current_tenant_id_str())
    if key:
        await idempotency.save(key, result.model_dump(mode="json"))
    return ApiResponse.ok(result)


@router.put("/role-posts/{role_id}")
async def internal_assign_role_posts(
    role_id: int,
    req: InternalRolePostRequest,
    uow: UowDep,
    outbox: OutboxDep,
    cache: CacheDep,
    audit: AuditDep,
    idempotency: IdempotencyDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> ApiResponse[RolePostIds]:
    """内部全量覆盖角色岗位（服务身份 `platform`；角色侧无主要项语义）。"""
    key = build_idempotency_key(key=idempotency_key, tenant=current_tenant_id_str()) if idempotency_key else ""
    if key and not await idempotency.begin(key):
        payload = await idempotency.load(key)
        if payload is not None:
            return ApiResponse.ok(RolePostIds.model_validate(payload))
    service = _role_post_service(uow, outbox)
    await service.assign_role_posts(role_id=role_id, post_ids=req.post_ids)
    result = RolePostIds(post_ids=await service.list_role_posts(role_id))
    _audit(audit, "org_role_post", role_id)
    await bump_user_roles_generation(cache, current_tenant_id_str())
    if key:
        await idempotency.save(key, result.model_dump(mode="json"))
    return ApiResponse.ok(result)


@router.put("/role-depts/{role_id}")
async def internal_assign_role_depts(
    role_id: int,
    req: InternalRoleDeptRequest,
    uow: UowDep,
    outbox: OutboxDep,
    cache: CacheDep,
    audit: AuditDep,
    idempotency: IdempotencyDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> ApiResponse[RoleDeptIds]:
    """内部全量覆盖角色部门（服务身份 `platform`；角色侧无主要项语义）。"""
    key = build_idempotency_key(key=idempotency_key, tenant=current_tenant_id_str()) if idempotency_key else ""
    if key and not await idempotency.begin(key):
        payload = await idempotency.load(key)
        if payload is not None:
            return ApiResponse.ok(RoleDeptIds.model_validate(payload))
    service = _role_dept_service(uow, outbox)
    await service.assign_role_depts(role_id=role_id, dept_ids=req.dept_ids)
    result = RoleDeptIds(dept_ids=await service.list_role_depts(role_id))
    _audit(audit, "org_role_dept", role_id)
    await bump_user_roles_generation(cache, current_tenant_id_str())
    if key:
        await idempotency.save(key, result.model_dump(mode="json"))
    return ApiResponse.ok(result)
