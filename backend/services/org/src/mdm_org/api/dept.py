"""部门路由（`/api/v1/org/depts`）：树查询与维护（写入含幂等键与审计占位）。"""

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

from mdm_org.models.dept import OrgDept
from mdm_org.repositories.dept import DeptRepository
from mdm_org.repositories.post import PostRepository
from mdm_org.repositories.role_dept import RoleDeptRepository
from mdm_org.repositories.user_post import UserPostRepository
from mdm_org.schemas.dept import (
    DeptCreateRequest,
    DeptItem,
    DeptMoveRequest,
    DeptRoleIds,
    DeptTree,
    DeptUpdateRequest,
    DeptUserIds,
)
from mdm_org.services.dept import DeptService

TABLE_NAME = "org_dept"
"""审计占位表名。"""

router = BaseRouter(
    key="org_depts",
    prefix="/org/depts",
    tags=["org-depts"],
    dependencies=[Depends(require_auth)],
)

UowDep = Annotated[UnitOfWork, Depends(get_uow)]
ConfigDep = Annotated[BaseConfigSource, Depends(get_config_source)]
OutboxDep = Annotated[BaseOutboxStore, Depends(get_outbox_store)]
AuditDep = Annotated[AuditCapturer, Depends(get_audit_capturer)]
IdempotencyDep = Annotated[IdempotencyStore, Depends(get_idempotency_store)]
IdempotencyKeyHeader = Annotated[str | None, Header(alias=IDEMPOTENCY_HEADER, description="幂等键（可选）")]

_REQUIRE_QUERY = Depends(require_permission("org:query"))
_REQUIRE_CREATE = Depends(require_permission("org:create"))
_REQUIRE_UPDATE = Depends(require_permission("org:update"))
_REQUIRE_DELETE = Depends(require_permission("org:delete"))


def _service(uow: UnitOfWork, config: BaseConfigSource, outbox: BaseOutboxStore) -> DeptService:
    """组装部门服务（请求级会话注入）。

    Args:
        uow: 工作单元。
        config: 系统参数取数。
        outbox: 发件箱存储。

    Returns:
        DeptService: 部门服务。
    """
    session = cast("DbSession", uow.session)
    return DeptService(
        DeptRepository(session),
        PostRepository(session),
        UserPostRepository(session),
        RoleDeptRepository(session),
        uow,
        config,
        outbox,
    )


def _item(dept: OrgDept) -> DeptItem:
    """部门 → 响应明细。

    Args:
        dept: 部门记录。

    Returns:
        DeptItem: 响应明细。
    """
    return DeptItem.model_validate(dept)


def _audit(capturer: AuditCapturer, dept: OrgDept) -> None:
    """审计占位：记录一次部门写操作（真实字段级审计随审计阶段）。

    Args:
        capturer: 审计捕获基座。
        dept: 部门记录。
    """
    capturer.capture(
        table=TABLE_NAME,
        model_id=dept.id,
        changes=ConcurrentStableList(),
        actor=current_user_id.get(),
    )


@router.get("", dependencies=[_REQUIRE_QUERY])
async def list_depts(
    uow: UowDep,
    config: ConfigDep,
    outbox: OutboxDep,
    status: str | None = None,
) -> ApiResponse[DeptTree]:
    """部门树。

    需要 org:query 权限；一次性返回（不分页），可按状态过滤。
    """
    nodes = await _service(uow, config, outbox).list_tree(status=status)
    return ApiResponse.ok(DeptTree(items=nodes))


@router.post("", dependencies=[_REQUIRE_CREATE])
async def create_dept(
    req: DeptCreateRequest,
    uow: UowDep,
    config: ConfigDep,
    outbox: OutboxDep,
    audit: AuditDep,
    idempotency: IdempotencyDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> ApiResponse[DeptItem]:
    """新建部门。

    需要 org:create 权限；部门编码必填且租户内唯一（格式受 `org.dept_code_pattern` 约束）；
    同父部门名称唯一；支持幂等键。
    """
    key = build_idempotency_key(key=idempotency_key, tenant=current_tenant_id_str()) if idempotency_key else ""
    if key and not await idempotency.begin(key):
        payload = await idempotency.load(key)
        if payload is not None:
            return ApiResponse.ok(DeptItem.model_validate(payload))
    dept = await _service(uow, config, outbox).create_dept(
        code=req.code, name=req.name, parent_id=req.parent_id, sort=req.sort
    )
    result = _item(dept)
    _audit(audit, dept)
    if key:
        await idempotency.save(key, result.model_dump(mode="json"))
    return ApiResponse.ok(result)


@router.get("/{dept_id}", dependencies=[_REQUIRE_QUERY])
async def get_dept(
    dept_id: int,
    uow: UowDep,
    config: ConfigDep,
    outbox: OutboxDep,
) -> ApiResponse[DeptItem]:
    """部门详情（含 `ancestors` 路径）。

    需要 org:query 权限；不存在抛 330051。
    """
    dept = await _service(uow, config, outbox).dept_detail(dept_id)
    return ApiResponse.ok(_item(dept))


@router.put("/{dept_id}", dependencies=[_REQUIRE_UPDATE])
async def update_dept(
    dept_id: int,
    req: DeptUpdateRequest,
    uow: UowDep,
    config: ConfigDep,
    outbox: OutboxDep,
    audit: AuditDep,
) -> ApiResponse[DeptItem]:
    """修改部门（编码 / 名称 / 排序 / 状态）。

    需要 org:update 权限；编码可改（格式与唯一校验、自身同值豁免）；`version` 提供时做乐观锁比对（冲突转统一并发冲突）。
    """
    dept = await _service(uow, config, outbox).update_dept(
        dept_id=dept_id,
        code=req.code,
        name=req.name,
        sort=req.sort,
        status=req.status,
        version=req.version,
    )
    _audit(audit, dept)
    return ApiResponse.ok(_item(dept))


@router.put("/{dept_id}/move", dependencies=[_REQUIRE_UPDATE])
async def move_dept(
    dept_id: int,
    req: DeptMoveRequest,
    uow: UowDep,
    config: ConfigDep,
    outbox: OutboxDep,
    audit: AuditDep,
) -> ApiResponse[DeptItem]:
    """移动部门（级联维护子树 `ancestors`）。

    需要 org:update 权限；防环（新父不得为自身或其后代，330053）。
    """
    dept = await _service(uow, config, outbox).move_dept(dept_id=dept_id, new_parent_id=req.parent_id)
    _audit(audit, dept)
    return ApiResponse.ok(_item(dept))


@router.delete("/{dept_id}", dependencies=[_REQUIRE_DELETE])
async def delete_dept(
    dept_id: int,
    uow: UowDep,
    config: ConfigDep,
    outbox: OutboxDep,
    audit: AuditDep,
) -> ApiResponse[DeptItem]:
    """删除部门（有引用拒绝，软删除）。

    需要 org:delete 权限；子部门 / 岗位 / 角色分配存在时拒绝（330054 / 330055 / 330056）。
    """
    service = _service(uow, config, outbox)
    dept = await service.dept_detail(dept_id)
    await service.delete_dept(dept_id=dept_id)
    _audit(audit, dept)
    return ApiResponse.ok(_item(dept))


@router.get("/{dept_id}/users", dependencies=[_REQUIRE_QUERY])
async def list_dept_users(
    dept_id: int,
    uow: UowDep,
    config: ConfigDep,
    outbox: OutboxDep,
) -> ApiResponse[DeptUserIds]:
    """部门（含子树）归属用户列表。

    需要 org:query 权限；用户名称回显经组织主数据只读契约（01_03）。
    """
    user_ids = await _service(uow, config, outbox).list_subtree_users(dept_id)
    return ApiResponse.ok(DeptUserIds(user_ids=user_ids))


@router.get("/{dept_id}/roles", dependencies=[_REQUIRE_QUERY])
async def list_dept_roles(
    dept_id: int,
    uow: UowDep,
    config: ConfigDep,
    outbox: OutboxDep,
) -> ApiResponse[DeptRoleIds]:
    """部门角色分配回显。

    需要 org:query 权限。
    """
    role_ids = await _service(uow, config, outbox).list_dept_roles(dept_id)
    return ApiResponse.ok(DeptRoleIds(role_ids=role_ids))
