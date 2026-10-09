"""用户-部门分配请求 / 响应契约。"""

from typing import Annotated

from bms_core.core.concurrent import ConcurrentStableList
from bms_core.schemas.base import CONTRACT_COLLECTION, CONTRACT_STABLE_LIST, BaseSchema
from pydantic import Field


class UserDeptAssignRequest(BaseSchema):
    """全量覆盖分配用户部门请求（diff 后增删）。"""

    dept_ids: Annotated[ConcurrentStableList[int], CONTRACT_COLLECTION] = Field(
        default_factory=CONTRACT_STABLE_LIST, description="目标部门 id 清单（全量覆盖）"
    )


class UserDeptIds(BaseSchema):
    """用户已分配部门 id 清单与主要部门。"""

    dept_ids: Annotated[ConcurrentStableList[int], CONTRACT_COLLECTION] = Field(default_factory=CONTRACT_STABLE_LIST)
    primary_dept_id: int | None = Field(default=None, description="主要部门 id（未设置时为空）")


class UserDeptPrimaryRequest(BaseSchema):
    """主要部门置位请求（不传 / `null` 表示清除主要标记）。"""

    dept_id: int | None = Field(default=None, description="主要部门 id；不传 / null 表示清除")
