"""岗位路由（`/api/v1/org/posts`）：分页列表与维护。"""

from typing import Annotated, cast

from bms_core.api.base import BaseRouter, page_query, require_auth
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
from bms_core.schemas.pagination import BasePageQuery, BasePageResponse
from fastapi import Depends, Header

from mdm_org.models.post import OrgPost
from mdm_org.repositories.dept import DeptRepository
from mdm_org.repositories.post import PostRepository
from mdm_org.repositories.role_post import RolePostRepository
from mdm_org.repositories.user_post import UserPostRepository
from mdm_org.schemas.post import (
    PostCreateRequest,
    PostItem,
    PostRoleIds,
    PostUpdateRequest,
    PostUserIds,
)
from mdm_org.services.post import PostService

TABLE_NAME = "org_post"
"""审计占位表名。"""

router = BaseRouter(
    key="org_posts",
    prefix="/org/posts",
    tags=["org-posts"],
    dependencies=[Depends(require_auth)],
)

UowDep = Annotated[UnitOfWork, Depends(get_uow)]
ConfigDep = Annotated[BaseConfigSource, Depends(get_config_source)]
OutboxDep = Annotated[BaseOutboxStore, Depends(get_outbox_store)]
AuditDep = Annotated[AuditCapturer, Depends(get_audit_capturer)]
PageDep = Annotated[BasePageQuery, Depends(page_query)]
IdempotencyDep = Annotated[IdempotencyStore, Depends(get_idempotency_store)]
IdempotencyKeyHeader = Annotated[str | None, Header(alias=IDEMPOTENCY_HEADER, description="幂等键（可选）")]

_REQUIRE_QUERY = Depends(require_permission("org:query"))
_REQUIRE_CREATE = Depends(require_permission("org:create"))
_REQUIRE_UPDATE = Depends(require_permission("org:update"))
_REQUIRE_DELETE = Depends(require_permission("org:delete"))


def _service(uow: UnitOfWork, config: BaseConfigSource, outbox: BaseOutboxStore) -> PostService:
    """组装岗位服务（请求级会话注入）。

    Args:
        uow: 工作单元。
        config: 系统参数取数。
        outbox: 发件箱存储。

    Returns:
        PostService: 岗位服务。
    """
    session = cast("DbSession", uow.session)
    return PostService(
        PostRepository(session),
        DeptRepository(session),
        UserPostRepository(session),
        RolePostRepository(session),
        uow,
        config,
        outbox,
    )


def _item(post: OrgPost) -> PostItem:
    """岗位 → 响应明细。

    Args:
        post: 岗位记录。

    Returns:
        PostItem: 响应明细。
    """
    return PostItem.model_validate(post)


def _audit(capturer: AuditCapturer, post: OrgPost) -> None:
    """审计占位：记录一次岗位写操作。

    Args:
        capturer: 审计捕获基座。
        post: 岗位记录。
    """
    capturer.capture(
        table=TABLE_NAME,
        model_id=post.id,
        changes=ConcurrentStableList(),
        actor=current_user_id.get(),
    )


@router.get("", dependencies=[_REQUIRE_QUERY])
async def list_posts(
    query: PageDep,
    uow: UowDep,
    config: ConfigDep,
    outbox: OutboxDep,
    dept_id: int | None = None,
    status: str | None = None,
    keyword: str | None = None,
) -> ApiResponse[BasePageResponse[PostItem]]:
    """岗位列表（分页；按部门 / 状态 / 关键字筛选）。

    需要 org:query 权限；排序字段经白名单校验。
    """
    rows, total = await _service(uow, config, outbox).list_posts(query, dept_id=dept_id, status=status, keyword=keyword)
    return ApiResponse.ok(
        BasePageResponse[PostItem](
            list=ConcurrentStableList(_item(row) for row in rows),
            total=total,
            page=query.page,
            size=query.size,
        )
    )


@router.post("", dependencies=[_REQUIRE_CREATE])
async def create_post(
    req: PostCreateRequest,
    uow: UowDep,
    config: ConfigDep,
    outbox: OutboxDep,
    audit: AuditDep,
    idempotency: IdempotencyDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> ApiResponse[PostItem]:
    """新建岗位。

    需要 org:create 权限；岗位码租户内唯一且受格式约束；支持幂等键。
    """
    key = build_idempotency_key(key=idempotency_key, tenant=current_tenant_id_str()) if idempotency_key else ""
    if key and not await idempotency.begin(key):
        payload = await idempotency.load(key)
        if payload is not None:
            return ApiResponse.ok(PostItem.model_validate(payload))
    post = await _service(uow, config, outbox).create_post(
        code=req.code, name=req.name, dept_id=req.dept_id, sort=req.sort
    )
    result = _item(post)
    _audit(audit, post)
    if key:
        await idempotency.save(key, result.model_dump(mode="json"))
    return ApiResponse.ok(result)


@router.get("/{post_id}", dependencies=[_REQUIRE_QUERY])
async def get_post(
    post_id: int,
    uow: UowDep,
    config: ConfigDep,
    outbox: OutboxDep,
) -> ApiResponse[PostItem]:
    """岗位详情。

    需要 org:query 权限；不存在抛 330031。
    """
    post = await _service(uow, config, outbox).require_post(post_id)
    return ApiResponse.ok(_item(post))


@router.put("/{post_id}", dependencies=[_REQUIRE_UPDATE])
async def update_post(
    post_id: int,
    req: PostUpdateRequest,
    uow: UowDep,
    config: ConfigDep,
    outbox: OutboxDep,
    audit: AuditDep,
) -> ApiResponse[PostItem]:
    """修改岗位（`code` 不可改）。

    需要 org:update 权限；`version` 提供时做乐观锁比对。
    """
    post = await _service(uow, config, outbox).update_post(
        post_id=post_id,
        name=req.name,
        dept_id=req.dept_id,
        sort=req.sort,
        status=req.status,
        version=req.version,
    )
    _audit(audit, post)
    return ApiResponse.ok(_item(post))


@router.delete("/{post_id}", dependencies=[_REQUIRE_DELETE])
async def delete_post(
    post_id: int,
    uow: UowDep,
    config: ConfigDep,
    outbox: OutboxDep,
    audit: AuditDep,
) -> ApiResponse[PostItem]:
    """删除岗位（有引用拒绝，软删除）。

    需要 org:delete 权限；仍关联用户 / 角色分配时拒绝（330034 / 330035）。
    """
    service = _service(uow, config, outbox)
    post = await service.require_post(post_id)
    await service.delete_post(post_id=post_id)
    _audit(audit, post)
    return ApiResponse.ok(_item(post))


@router.get("/{post_id}/users", dependencies=[_REQUIRE_QUERY])
async def list_post_users(
    post_id: int,
    uow: UowDep,
    config: ConfigDep,
    outbox: OutboxDep,
) -> ApiResponse[PostUserIds]:
    """岗位下用户列表。

    需要 org:query 权限。
    """
    user_ids = await _service(uow, config, outbox).list_post_users(post_id)
    return ApiResponse.ok(PostUserIds(user_ids=user_ids))


@router.get("/{post_id}/roles", dependencies=[_REQUIRE_QUERY])
async def list_post_roles(
    post_id: int,
    uow: UowDep,
    config: ConfigDep,
    outbox: OutboxDep,
) -> ApiResponse[PostRoleIds]:
    """岗位角色分配回显。

    需要 org:query 权限。
    """
    role_ids = await _service(uow, config, outbox).list_post_roles(post_id)
    return ApiResponse.ok(PostRoleIds(role_ids=role_ids))
