"""部门请求 / 响应契约（集合字段一律插入序集合类 + 契约元数据内联标注）。"""

from typing import Annotated

from bms_core.core.concurrent import ConcurrentStableList
from bms_core.schemas.base import CONTRACT_COLLECTION, CONTRACT_STABLE_LIST, BaseSchema
from pydantic import Field


class DeptTreeNode(BaseSchema):
    """部门树节点（递归；`children` 为子节点）。"""

    id: int
    parent_id: int | None = None
    code: str
    name: str
    ancestors: str
    sort: int
    status: str
    children: Annotated[ConcurrentStableList[DeptTreeNode], CONTRACT_COLLECTION] = Field(
        default_factory=CONTRACT_STABLE_LIST
    )


DeptTreeNode.model_rebuild()


class DeptTree(BaseSchema):
    """部门树响应（一次性返回、不分页）。"""

    items: Annotated[ConcurrentStableList[DeptTreeNode], CONTRACT_COLLECTION] = Field(
        default_factory=CONTRACT_STABLE_LIST
    )


class DeptItem(BaseSchema):
    """部门明细（扁平）。"""

    id: int
    parent_id: int | None = None
    code: str
    name: str
    ancestors: str
    sort: int
    status: str


class DeptCreateRequest(BaseSchema):
    """新建部门请求。"""

    code: str = Field(
        min_length=1, max_length=64, description="部门编码（租户内唯一；格式受 org.dept_code_pattern 约束）"
    )
    name: str = Field(min_length=1, max_length=128, description="部门名称（同父唯一）")
    parent_id: int | None = Field(default=None, description="父部门 id（空 = 根部门）")
    sort: int = Field(default=0, description="同级排序")


class DeptUpdateRequest(BaseSchema):
    """修改部门请求（未传字段不改）。"""

    code: str | None = Field(default=None, min_length=1, max_length=64, description="部门编码（可改）")
    name: str | None = Field(default=None, min_length=1, max_length=128, description="部门名称")
    sort: int | None = Field(default=None, description="同级排序")
    status: str | None = Field(default=None, description="状态（enabled / disabled）")
    version: int | None = Field(default=None, description="客户端版本（乐观锁比对）")


class DeptMoveRequest(BaseSchema):
    """移动部门请求。"""

    parent_id: int | None = Field(default=None, description="新父部门 id（空 = 移至根层级）")
    version: int | None = Field(default=None, description="客户端版本（乐观锁比对）")


class DeptUserIds(BaseSchema):
    """部门（含子树）归属用户 id 清单。"""

    user_ids: Annotated[ConcurrentStableList[int], CONTRACT_COLLECTION] = Field(default_factory=CONTRACT_STABLE_LIST)


class DeptRoleIds(BaseSchema):
    """部门角色分配回显（角色 id 清单）。"""

    role_ids: Annotated[ConcurrentStableList[int], CONTRACT_COLLECTION] = Field(default_factory=CONTRACT_STABLE_LIST)
