"""组织只读出口响应契约：部门树 / 名称回显序列 / 按用户解析角色结果的包装。

集合字段一律以内联 `Annotated[集合类, CONTRACT_COLLECTION]` 声明（基座集合类须经契约标注
方可作为响应模型字段；防契约 `$defs` 漂移）。前端解析器兼容 `list` / `items` / `records`
包装（`readArray`），故序列类响应用 `items` 包装（与 01_02 的 `DeptTree` 同口径）。

（组织数据源 / 名称回显的**端口契约**在 `mdm_org/org/base.py`——由本模块做 HTTP 响应包装。）
"""

from typing import Annotated

from bms_core.core.concurrent import ConcurrentStableList
from bms_core.schemas.base import CONTRACT_COLLECTION, CONTRACT_STABLE_LIST, BaseSchema
from pydantic import Field

from mdm_org.org.base import OrgDept, OrgNameRef

__all__ = ["OrgDeptTree", "OrgNameRefs", "OrgUserRoles"]


class OrgDeptTree(BaseSchema):
    """组织部门树响应（一次性返回、不分页；`items` 为根节点序列，子节点嵌套）。"""

    items: Annotated[ConcurrentStableList[OrgDept], CONTRACT_COLLECTION] = Field(
        default_factory=CONTRACT_STABLE_LIST, description="部门树根节点序列（`children` 嵌套）"
    )


class OrgNameRefs(BaseSchema):
    """名称回显响应（按请求插入序返回；未命中项占位）。"""

    items: Annotated[ConcurrentStableList[OrgNameRef], CONTRACT_COLLECTION] = Field(
        default_factory=CONTRACT_STABLE_LIST, description="回显项序列（保持请求插入序）"
    )


class OrgUserRoles(BaseSchema):
    """按用户解析其经岗位 / 部门获得的角色（并集去重；不含用户直接角色）。"""

    role_ids: Annotated[ConcurrentStableList[int], CONTRACT_COLLECTION] = Field(
        default_factory=CONTRACT_STABLE_LIST,
        description="角色 id 集合（岗位链在前、部门链补入，去重）",
    )
