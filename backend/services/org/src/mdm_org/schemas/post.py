"""岗位请求 / 响应契约。"""

from typing import Annotated

from bms_core.core.concurrent import ConcurrentStableList
from bms_core.schemas.base import CONTRACT_COLLECTION, CONTRACT_STABLE_LIST, BaseSchema
from pydantic import Field


class PostItem(BaseSchema):
    """岗位明细。"""

    id: int
    code: str
    name: str
    dept_id: int
    sort: int
    status: str


class PostCreateRequest(BaseSchema):
    """新建岗位请求。"""

    code: str = Field(min_length=1, max_length=64, description="岗位码（租户内唯一；创建后不可改）")
    name: str = Field(min_length=1, max_length=128, description="岗位名称")
    dept_id: int = Field(description="归属部门 id（须存在且启用）")
    sort: int = Field(default=0, description="排序")


class PostUpdateRequest(BaseSchema):
    """修改岗位请求（未传字段不改；`code` 不可改）。"""

    name: str | None = Field(default=None, min_length=1, max_length=128, description="岗位名称")
    dept_id: int | None = Field(default=None, description="归属部门 id")
    sort: int | None = Field(default=None, description="排序")
    status: str | None = Field(default=None, description="状态（enabled / disabled）")
    version: int | None = Field(default=None, description="客户端版本（乐观锁比对）")


class PostUserIds(BaseSchema):
    """岗位下用户 id 清单。"""

    user_ids: Annotated[ConcurrentStableList[int], CONTRACT_COLLECTION] = Field(default_factory=CONTRACT_STABLE_LIST)


class PostRoleIds(BaseSchema):
    """岗位角色分配回显（角色 id 清单）。"""

    role_ids: Annotated[ConcurrentStableList[int], CONTRACT_COLLECTION] = Field(default_factory=CONTRACT_STABLE_LIST)
