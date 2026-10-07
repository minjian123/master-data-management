"""角色-部门分配请求 / 响应契约。"""

from typing import Annotated

from bms_core.core.concurrent import ConcurrentStableList
from bms_core.schemas.base import CONTRACT_COLLECTION, CONTRACT_STABLE_LIST, BaseSchema
from pydantic import Field


class RoleDeptAssignRequest(BaseSchema):
    """全量覆盖分配角色部门请求（diff 后增删）。"""

    dept_ids: Annotated[ConcurrentStableList[int], CONTRACT_COLLECTION] = Field(
        default_factory=CONTRACT_STABLE_LIST, description="目标部门 id 清单（全量覆盖）"
    )


class RoleDeptIds(BaseSchema):
    """角色已分配部门 id 清单。"""

    dept_ids: Annotated[ConcurrentStableList[int], CONTRACT_COLLECTION] = Field(default_factory=CONTRACT_STABLE_LIST)
