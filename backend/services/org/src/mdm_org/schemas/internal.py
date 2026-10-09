"""组织域**内部写通道**请求契约（`/api/v1/org/internal/*`；宿主编排以服务身份写入）。

- 写语义与公开面**完全一致**：全量覆盖（diff 后增删单事务）+（用户侧）主要项两步置位；
- 请求体：目标集合 + 主要项 id（`null` ＝ 清除；角色侧无主要项语义，故不提供该字段）；
- 响应体**复用公开面** `UserPostIds` / `UserDeptIds` / `RolePostIds` / `RoleDeptIds`（回「生效后集合 + 主要项」）。
"""

from typing import Annotated

from bms_core.core.concurrent import ConcurrentStableList
from bms_core.schemas.base import CONTRACT_COLLECTION, CONTRACT_STABLE_LIST, BaseSchema
from pydantic import Field

__all__ = [
    "InternalRoleDeptRequest",
    "InternalRolePostRequest",
    "InternalUserDeptRequest",
    "InternalUserPostRequest",
]


class InternalUserPostRequest(BaseSchema):
    """内部全量覆盖用户岗位（含主要岗位）。"""

    post_ids: Annotated[ConcurrentStableList[int], CONTRACT_COLLECTION] = Field(
        default_factory=CONTRACT_STABLE_LIST, description="目标岗位 id 清单（全量覆盖）"
    )
    primary_post_id: int | None = Field(default=None, description="主要岗位 id；不传 / null 表示清除")


class InternalUserDeptRequest(BaseSchema):
    """内部全量覆盖用户部门（含主要部门）。"""

    dept_ids: Annotated[ConcurrentStableList[int], CONTRACT_COLLECTION] = Field(
        default_factory=CONTRACT_STABLE_LIST, description="目标部门 id 清单（全量覆盖）"
    )
    primary_dept_id: int | None = Field(default=None, description="主要部门 id；不传 / null 表示清除")


class InternalRolePostRequest(BaseSchema):
    """内部全量覆盖角色岗位（角色侧无主要项语义）。"""

    post_ids: Annotated[ConcurrentStableList[int], CONTRACT_COLLECTION] = Field(
        default_factory=CONTRACT_STABLE_LIST, description="目标岗位 id 清单（全量覆盖）"
    )


class InternalRoleDeptRequest(BaseSchema):
    """内部全量覆盖角色部门（角色侧无主要项语义）。"""

    dept_ids: Annotated[ConcurrentStableList[int], CONTRACT_COLLECTION] = Field(
        default_factory=CONTRACT_STABLE_LIST, description="目标部门 id 清单（全量覆盖）"
    )
