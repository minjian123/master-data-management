"""用户-部门分配路由（`/api/v1/org/user-depts`）：插件写入口（全量覆盖 / 解绑 / 主要部门置位）。"""

from typing import Annotated, cast

from bms_core.api.base import BaseRouter, require_auth
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
from bms_core.permission.base import require_permission
from bms_core.schemas.common import ApiResponse
from fastapi import Depends, Header

from mdm_org.repositories.dept import DeptRepository
from mdm_org.repositories.user_dept import UserDeptRepository
from mdm_org.schemas.user_dept import UserDeptAssignRequest, UserDeptIds, UserDeptPrimaryRequest
from mdm_org.services.open_read import bump_user_roles_generation
from mdm_org.services.user_dept import UserDeptService

router = BaseRouter(
    key="org_user_depts",
    prefix="/org/user-depts",
    tags=["org-user-depts"],
    dependencies=[Depends(require_auth)],
)

UowDep = Annotated[UnitOfWork, Depends(get_uow)]
ConfigDep = Annotated[BaseConfigSource, Depends(get_config_source)]
CacheDep = Annotated[CacheRegion, Depends(get_cache_region)]
OutboxDep = Annotated[BaseOutboxStore, Depends(get_outbox_store)]
AuditDep = Annotated[AuditCapturer, Depends(get_audit_capturer)]
IdempotencyDep = Annotated[IdempotencyStore, Depends(get_idempotency_store)]
IdempotencyKeyHeader = Annotated[str | None, Header(alias=IDEMPOTENCY_HEADER, description="幂等键（可选）")]

_REQUIRE_QUERY = Depends(require_permission("org:query"))
_REQUIRE_UPDATE = Depends(require_permission("org:update"))


def _service(uow: UnitOfWork, config: BaseConfigSource, outbox: BaseOutboxStore) -> UserDeptService:
    """组装用户-部门分配服务。

    Args:
        uow: 工作单元。
        config: 系统参数取数。
        outbox: 发件箱存储。

    Returns:
        UserDeptService: 分配服务。
    """
    session = cast("DbSession", uow.session)
    return UserDeptService(UserDeptRepository(session), DeptRepository(session), uow, config, outbox)


def _audit(capturer: AuditCapturer, user_id: int) -> None:
    """审计占位：记录一次用户-部门分配写操作。

    Args:
        capturer: 审计捕获基座。
        user_id: 用户 id。
    """
    capturer.capture(
        table="org_user_dept", model_id=user_id, changes=ConcurrentStableList(), actor=current_user_id.get()
    )


async def _ids(service: UserDeptService, user_id: int) -> UserDeptIds:
    """组装「已分配部门 + 主要部门」响应。

    Args:
        service: 分配服务。
        user_id: 用户 id。

    Returns:
        UserDeptIds: 响应体。
    """
    return UserDeptIds(
        dept_ids=await service.list_user_depts(user_id),
        primary_dept_id=await service.primary_dept_id(user_id),
    )


@router.get("/{user_id}", dependencies=[_REQUIRE_QUERY])
async def list_user_depts(
    user_id: int,
    uow: UowDep,
    config: ConfigDep,
    outbox: OutboxDep,
) -> ApiResponse[UserDeptIds]:
    """按用户查已分配部门（含主要部门）。

    需要 org:query 权限；供 bms 用户管理页具名插槽插件回显。
    """
    return ApiResponse.ok(await _ids(_service(uow, config, outbox), user_id))


@router.put("/{user_id}", dependencies=[_REQUIRE_UPDATE])
async def assign_user_depts(
    user_id: int,
    req: UserDeptAssignRequest,
    uow: UowDep,
    config: ConfigDep,
    outbox: OutboxDep,
    cache: CacheDep,
    audit: AuditDep,
    idempotency: IdempotencyDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> ApiResponse[UserDeptIds]:
    """全量覆盖分配用户部门（diff 后增删单事务）。

    需要 org:update 权限；单用户部门数受上限约束（330112）；被移除项若为主要部门则同事务清空标记；支持幂等键。
    """
    key = build_idempotency_key(key=idempotency_key, tenant=current_tenant_id_str()) if idempotency_key else ""
    if key and not await idempotency.begin(key):
        payload = await idempotency.load(key)
        if payload is not None:
            return ApiResponse.ok(UserDeptIds.model_validate(payload))
    service = _service(uow, config, outbox)
    await service.assign_user_depts(user_id=user_id, dept_ids=req.dept_ids)
    result = await _ids(service, user_id)
    _audit(audit, user_id)
    await bump_user_roles_generation(cache, current_tenant_id_str())
    if key:
        await idempotency.save(key, result.model_dump(mode="json"))
    return ApiResponse.ok(result)


@router.delete("/{user_id}/{dept_id}", dependencies=[_REQUIRE_UPDATE])
async def unassign_user_dept(
    user_id: int,
    dept_id: int,
    uow: UowDep,
    config: ConfigDep,
    outbox: OutboxDep,
    cache: CacheDep,
    audit: AuditDep,
) -> ApiResponse[UserDeptIds]:
    """解绑单个用户-部门。

    需要 org:update 权限；关联不存在抛 330111；若被解绑项为主要部门则标记随之清空。
    """
    service = _service(uow, config, outbox)
    await service.unassign_user_dept(user_id=user_id, dept_id=dept_id)
    result = await _ids(service, user_id)
    _audit(audit, user_id)
    await bump_user_roles_generation(cache, current_tenant_id_str())
    return ApiResponse.ok(result)


@router.put("/{user_id}/primary", dependencies=[_REQUIRE_UPDATE])
async def set_primary_dept(
    user_id: int,
    req: UserDeptPrimaryRequest,
    uow: UowDep,
    config: ConfigDep,
    outbox: OutboxDep,
    cache: CacheDep,
    audit: AuditDep,
) -> ApiResponse[UserDeptIds]:
    """置位 / 清除主要部门（同事务互斥置位）。

    需要 org:update 权限；`dept_id` 为空表示清除；置位目标须已分配，否则 330113；
    主要部门不参与角色解析（解析按全部已分配部门）。
    """
    service = _service(uow, config, outbox)
    await service.set_primary_dept(user_id=user_id, dept_id=req.dept_id)
    result = await _ids(service, user_id)
    _audit(audit, user_id)
    await bump_user_roles_generation(cache, current_tenant_id_str())
    return ApiResponse.ok(result)
