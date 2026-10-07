"""用户-岗位分配路由（`/api/v1/org/user-posts`）：插件写入口（全量覆盖 / 解绑）。"""

from typing import Annotated, cast

from bms_core.api.base import BaseRouter, require_auth
from bms_core.api.deps import get_audit_capturer, get_config_source, get_idempotency_store, get_outbox_store, get_uow
from bms_core.audit.base import AuditCapturer
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

from mdm_org.repositories.post import PostRepository
from mdm_org.repositories.user_post import UserPostRepository
from mdm_org.schemas.user_post import UserPostAssignRequest, UserPostIds
from mdm_org.services.user_post import UserPostService

router = BaseRouter(
    key="org_user_posts",
    prefix="/org/user-posts",
    tags=["org-user-posts"],
    dependencies=[Depends(require_auth)],
)

UowDep = Annotated[UnitOfWork, Depends(get_uow)]
ConfigDep = Annotated[BaseConfigSource, Depends(get_config_source)]
OutboxDep = Annotated[BaseOutboxStore, Depends(get_outbox_store)]
AuditDep = Annotated[AuditCapturer, Depends(get_audit_capturer)]
IdempotencyDep = Annotated[IdempotencyStore, Depends(get_idempotency_store)]
IdempotencyKeyHeader = Annotated[str | None, Header(alias=IDEMPOTENCY_HEADER, description="幂等键（可选）")]

_REQUIRE_QUERY = Depends(require_permission("org:query"))
_REQUIRE_UPDATE = Depends(require_permission("org:update"))


def _service(uow: UnitOfWork, config: BaseConfigSource, outbox: BaseOutboxStore) -> UserPostService:
    """组装用户-岗位分配服务。

    Args:
        uow: 工作单元。
        config: 系统参数取数。
        outbox: 发件箱存储。

    Returns:
        UserPostService: 分配服务。
    """
    session = cast("DbSession", uow.session)
    return UserPostService(UserPostRepository(session), PostRepository(session), uow, config, outbox)


def _audit(capturer: AuditCapturer, user_id: int) -> None:
    """审计占位：记录一次用户-岗位分配写操作。

    Args:
        capturer: 审计捕获基座。
        user_id: 用户 id。
    """
    capturer.capture(
        table="org_user_post", model_id=user_id, changes=ConcurrentStableList(), actor=current_user_id.get()
    )


@router.get("", dependencies=[_REQUIRE_QUERY])
async def list_user_posts(
    user_id: int,
    uow: UowDep,
    config: ConfigDep,
    outbox: OutboxDep,
) -> ApiResponse[UserPostIds]:
    """按用户查已分配岗位。

    需要 org:query 权限；供 bms 用户管理页具名插槽插件回显。
    """
    post_ids = await _service(uow, config, outbox).list_user_posts(user_id)
    return ApiResponse.ok(UserPostIds(post_ids=post_ids))


@router.put("/{user_id}", dependencies=[_REQUIRE_UPDATE])
async def assign_user_posts(
    user_id: int,
    req: UserPostAssignRequest,
    uow: UowDep,
    config: ConfigDep,
    outbox: OutboxDep,
    audit: AuditDep,
    idempotency: IdempotencyDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> ApiResponse[UserPostIds]:
    """全量覆盖分配用户岗位（diff 后增删单事务）。

    需要 org:update 权限；单用户岗位数受上限约束（330072）；支持幂等键。
    """
    key = build_idempotency_key(key=idempotency_key, tenant=current_tenant_id_str()) if idempotency_key else ""
    if key and not await idempotency.begin(key):
        payload = await idempotency.load(key)
        if payload is not None:
            return ApiResponse.ok(UserPostIds.model_validate(payload))
    post_ids = await _service(uow, config, outbox).assign_user_posts(user_id=user_id, post_ids=req.post_ids)
    result = UserPostIds(post_ids=post_ids)
    _audit(audit, user_id)
    if key:
        await idempotency.save(key, result.model_dump(mode="json"))
    return ApiResponse.ok(result)


@router.delete("/{user_id}/{post_id}", dependencies=[_REQUIRE_UPDATE])
async def unassign_user_post(
    user_id: int,
    post_id: int,
    uow: UowDep,
    config: ConfigDep,
    outbox: OutboxDep,
    audit: AuditDep,
) -> ApiResponse[UserPostIds]:
    """解绑单个用户-岗位。

    需要 org:update 权限；关联不存在抛 330071。
    """
    service = _service(uow, config, outbox)
    await service.unassign_user_post(user_id=user_id, post_id=post_id)
    post_ids = await service.list_user_posts(user_id)
    _audit(audit, user_id)
    return ApiResponse.ok(UserPostIds(post_ids=post_ids))
