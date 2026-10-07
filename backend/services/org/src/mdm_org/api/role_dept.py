"""角色-部门分配路由（`/api/v1/org/role-depts`）：插件写入口（全量覆盖 / 解绑）。"""

from typing import Annotated, cast

from bms_core.api.base import BaseRouter, require_auth
from bms_core.api.deps import get_audit_capturer, get_cache_region, get_idempotency_store, get_outbox_store, get_uow
from bms_core.audit.base import AuditCapturer
from bms_core.cache.base import CacheRegion
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
from mdm_org.repositories.role_dept import RoleDeptRepository
from mdm_org.schemas.role_dept import RoleDeptAssignRequest, RoleDeptIds
from mdm_org.services.open_read import bump_user_roles_generation
from mdm_org.services.role_dept import RoleDeptService

router = BaseRouter(
    key="org_role_depts",
    prefix="/org/role-depts",
    tags=["org-role-depts"],
    dependencies=[Depends(require_auth)],
)

UowDep = Annotated[UnitOfWork, Depends(get_uow)]
CacheDep = Annotated[CacheRegion, Depends(get_cache_region)]
OutboxDep = Annotated[BaseOutboxStore, Depends(get_outbox_store)]
AuditDep = Annotated[AuditCapturer, Depends(get_audit_capturer)]
IdempotencyDep = Annotated[IdempotencyStore, Depends(get_idempotency_store)]
IdempotencyKeyHeader = Annotated[str | None, Header(alias=IDEMPOTENCY_HEADER, description="幂等键（可选）")]

_REQUIRE_QUERY = Depends(require_permission("org:query"))
_REQUIRE_UPDATE = Depends(require_permission("org:update"))


def _service(uow: UnitOfWork, outbox: BaseOutboxStore) -> RoleDeptService:
    """组装角色-部门分配服务。

    Args:
        uow: 工作单元。
        outbox: 发件箱存储。

    Returns:
        RoleDeptService: 分配服务。
    """
    session = cast("DbSession", uow.session)
    return RoleDeptService(RoleDeptRepository(session), DeptRepository(session), uow, outbox)


def _audit(capturer: AuditCapturer, role_id: int) -> None:
    """审计占位：记录一次角色-部门分配写操作。

    Args:
        capturer: 审计捕获基座。
        role_id: 角色 id。
    """
    capturer.capture(
        table="org_role_dept", model_id=role_id, changes=ConcurrentStableList(), actor=current_user_id.get()
    )


@router.get("", dependencies=[_REQUIRE_QUERY])
async def list_role_depts(
    role_id: int,
    uow: UowDep,
    outbox: OutboxDep,
) -> ApiResponse[RoleDeptIds]:
    """按角色列已分配部门（「部门分配」插件）。

    需要 org:query 权限。
    """
    dept_ids = await _service(uow, outbox).list_role_depts(role_id)
    return ApiResponse.ok(RoleDeptIds(dept_ids=dept_ids))


@router.put("/{role_id}", dependencies=[_REQUIRE_UPDATE])
async def assign_role_depts(
    role_id: int,
    req: RoleDeptAssignRequest,
    uow: UowDep,
    outbox: OutboxDep,
    cache: CacheDep,
    audit: AuditDep,
    idempotency: IdempotencyDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> ApiResponse[RoleDeptIds]:
    """全量覆盖分配角色部门（diff 后增删单事务）。

    需要 org:update 权限；`role_id` 对 bms 角色逻辑外键（不下库校验）；支持幂等键。
    """
    key = build_idempotency_key(key=idempotency_key, tenant=current_tenant_id_str()) if idempotency_key else ""
    if key and not await idempotency.begin(key):
        payload = await idempotency.load(key)
        if payload is not None:
            return ApiResponse.ok(RoleDeptIds.model_validate(payload))
    dept_ids = await _service(uow, outbox).assign_role_depts(role_id=role_id, dept_ids=req.dept_ids)
    result = RoleDeptIds(dept_ids=dept_ids)
    _audit(audit, role_id)
    await bump_user_roles_generation(cache, current_tenant_id_str())
    if key:
        await idempotency.save(key, result.model_dump(mode="json"))
    return ApiResponse.ok(result)


@router.delete("/{role_id}/{dept_id}", dependencies=[_REQUIRE_UPDATE])
async def unassign_role_dept(
    role_id: int,
    dept_id: int,
    uow: UowDep,
    outbox: OutboxDep,
    cache: CacheDep,
    audit: AuditDep,
) -> ApiResponse[RoleDeptIds]:
    """解绑单个角色-部门。

    需要 org:update 权限；分配不存在抛 330091。
    """
    service = _service(uow, outbox)
    await service.unassign_role_dept(role_id=role_id, dept_id=dept_id)
    dept_ids = await service.list_role_depts(role_id)
    _audit(audit, role_id)
    await bump_user_roles_generation(cache, current_tenant_id_str())
    return ApiResponse.ok(RoleDeptIds(dept_ids=dept_ids))
