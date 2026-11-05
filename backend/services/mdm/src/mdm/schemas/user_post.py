"""用户-岗位分配请求 / 响应契约。"""

from typing import Annotated

from bms_core.core.concurrent import ConcurrentStableList
from bms_core.schemas.base import CONTRACT_COLLECTION, CONTRACT_STABLE_LIST, BaseSchema
from pydantic import Field


class UserPostAssignRequest(BaseSchema):
    """全量覆盖分配用户岗位请求（diff 后增删）。"""

    post_ids: Annotated[ConcurrentStableList[int], CONTRACT_COLLECTION] = Field(
        default_factory=CONTRACT_STABLE_LIST, description="目标岗位 id 清单（全量覆盖）"
    )


class UserPostIds(BaseSchema):
    """用户已分配岗位 id 清单与主要岗位。"""

    post_ids: Annotated[ConcurrentStableList[int], CONTRACT_COLLECTION] = Field(default_factory=CONTRACT_STABLE_LIST)
    primary_post_id: int | None = Field(default=None, description="主要岗位 id（未设置时为空）")


class UserPostPrimaryRequest(BaseSchema):
    """主要岗位置位请求（不传 / `null` 表示清除主要标记）。"""

    post_id: int | None = Field(default=None, description="主要岗位 id；不传 / null 表示清除")
