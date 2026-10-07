"""角色-岗位分配路由（`/api/v1/org/role-posts`）：插件写入口（全量覆盖 / 解绑）。"""

from typing import Annotated, cast

from bms_core.api.base import BaseRouter, require_auth
from bms_core.api.deps import get_audit_capturer, get_idempotency_store, get_outbox_store, get_uow
from bms_core.audit.base import AuditCapturer
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

from mdm_org.repositories.post import PostRepository
from mdm_org.repositories.role_post import RolePostRepository
from mdm_org.schemas.role_post import RolePostAssignRequest, RolePostIds
from mdm_org.services.role_post import RolePostService

router = BaseRouter(
    key="org_role_posts",
    prefix="/org/role-posts",
    tags=["org-role-posts"],
    dependencies=[Depends(require_auth)],
)

UowDep = Annotated[UnitOfWork, Depends(get_uow)]
OutboxDep = Annotated[BaseOutboxStore, Depends(get_outbox_store)]
AuditDep = Annotated[AuditCapturer, Depends(get_audit_capturer)]
IdempotencyDep = Annotated[IdempotencyStore, Depends(get_idempotency_store)]
IdempotencyKeyHeader = Annotated[str | None, Header(alias=IDEMPOTENCY_HEADER, description="幂等键（可选）")]

_REQUIRE_QUERY = Depends(require_permission("org:query"))
_REQUIRE_UPDATE = Depends(require_permission("org:update"))


def _service(uow: UnitOfWork, outbox: BaseOutboxStore) -> RolePostService:
    """组装角色-岗位分配服务。

    Args:
        uow: 工作单元。
        outbox: 发件箱存储。

    Returns:
        RolePostService: 分配服务。
    """
    session = cast("DbSession", uow.session)
    return RolePostService(RolePostRepository(session), PostRepository(session), uow, outbox)


def _audit(capturer: AuditCapturer, role_id: int) -> None:
    """审计占位：记录一次角色-岗位分配写操作。

    Args:
        capturer: 审计捕获基座。
        role_id: 角色 id。
    """
    capturer.capture(
        table="org_role_post", model_id=role_id, changes=ConcurrentStableList(), actor=current_user_id.get()
    )


@router.get("", dependencies=[_REQUIRE_QUERY])
async def list_role_posts(
    role_id: int,
    uow: UowDep,
    outbox: OutboxDep,
) -> ApiResponse[RolePostIds]:
    """按角色列已分配岗位（「岗位分配」插件）。

    需要 org:query 权限。
    """
    post_ids = await _service(uow, outbox).list_role_posts(role_id)
    return ApiResponse.ok(RolePostIds(post_ids=post_ids))


@router.put("/{role_id}", dependencies=[_REQUIRE_UPDATE])
async def assign_role_posts(
    role_id: int,
    req: RolePostAssignRequest,
    uow: UowDep,
    outbox: OutboxDep,
    audit: AuditDep,
    idempotency: IdempotencyDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> ApiResponse[RolePostIds]:
    """全量覆盖分配角色岗位（diff 后增删单事务）。

    需要 org:update 权限；`role_id` 对 bms 角色逻辑外键（不下库校验）；支持幂等键。
    """
    key = build_idempotency_key(key=idempotency_key, tenant=current_tenant_id_str()) if idempotency_key else ""
    if key and not await idempotency.begin(key):
        payload = await idempotency.load(key)
        if payload is not None:
            return ApiResponse.ok(RolePostIds.model_validate(payload))
    post_ids = await _service(uow, outbox).assign_role_posts(role_id=role_id, post_ids=req.post_ids)
    result = RolePostIds(post_ids=post_ids)
    _audit(audit, role_id)
    if key:
        await idempotency.save(key, result.model_dump(mode="json"))
    return ApiResponse.ok(result)


@router.delete("/{role_id}/{post_id}", dependencies=[_REQUIRE_UPDATE])
async def unassign_role_post(
    role_id: int,
    post_id: int,
    uow: UowDep,
    outbox: OutboxDep,
    audit: AuditDep,
) -> ApiResponse[RolePostIds]:
    """解绑单个角色-岗位。

    需要 org:update 权限；分配不存在抛 330081。
    """
    service = _service(uow, outbox)
    await service.unassign_role_post(role_id=role_id, post_id=post_id)
    post_ids = await service.list_role_posts(role_id)
    _audit(audit, role_id)
    return ApiResponse.ok(RolePostIds(post_ids=post_ids))
