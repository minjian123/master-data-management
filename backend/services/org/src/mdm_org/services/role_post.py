"""角色-岗位分配服务：按角色查岗位 / 全量覆盖（diff 后增删单事务）/ 解绑。"""

from typing import cast

from bms_core.core.concurrent import ConcurrentStableDict, ConcurrentStableList, ConcurrentStableSet
from bms_core.core.objects import BaseFrameworkObject
from bms_core.db.session import DbSession
from bms_core.db.tenant import current_tenant_id_str
from bms_core.db.unit_of_work import UnitOfWork
from bms_core.events.base import EventEnvelope
from bms_core.outbox.base import BaseOutboxStore

from mdm_org.errors import OrgPostNotFoundError, OrgRolePostNotFoundError
from mdm_org.events import ROLE_POST_CHANGED_EVENT
from mdm_org.repositories.post import PostRepository
from mdm_org.repositories.role_post import RolePostRepository

CHANGE_ASSIGNED = "assigned"
"""变更类型：分配。"""

CHANGE_UNASSIGNED = "unassigned"
"""变更类型：解绑。"""


class RolePostService(BaseFrameworkObject):
    """角色-岗位分配服务（全量覆盖为「diff 后增删」单事务）。"""

    def __init__(
        self,
        role_posts: RolePostRepository,
        posts: PostRepository,
        uow: UnitOfWork,
        outbox: BaseOutboxStore,
    ) -> None:
        """初始化。

        Args:
            role_posts: 角色-岗位分配仓储。
            posts: 岗位仓储（岗位存在性校验）。
            uow: 工作单元（事务边界）。
            outbox: 事务性发件箱。
        """
        self._role_posts = role_posts
        self._posts = posts
        self._uow = uow
        self._outbox = outbox

    @property
    def _session(self) -> DbSession:
        """当前事务会话。

        Returns:
            DbSession: 请求级会话。
        """
        return cast("DbSession", self._uow.session)

    async def list_role_posts(self, role_id: int) -> ConcurrentStableList[int]:
        """按角色取已分配岗位 id。

        Args:
            role_id: 角色 id。

        Returns:
            ConcurrentStableList[int]: 岗位 id（插入序）。
        """
        return ConcurrentStableList(link.post_id for link in await self._role_posts.list_by_role(role_id))

    async def assign_role_posts(
        self, *, role_id: int, post_ids: ConcurrentStableList[int]
    ) -> ConcurrentStableList[int]:
        """全量覆盖分配角色岗位（diff 后增删，单事务）。

        Args:
            role_id: 角色 id。
            post_ids: 目标岗位 id 清单（全量）。

        Returns:
            ConcurrentStableList[int]: 分配后的岗位 id（插入序）。

        Raises:
            OrgPostNotFoundError: 目标岗位不存在（330031）。
        """
        target = _dedupe(post_ids)
        async with self._uow.begin():
            for post_id in target:
                if await self._posts.get(post_id) is None:
                    raise OrgPostNotFoundError(f"岗位不存在：{post_id}")
            existing = await self._role_posts.list_by_role(role_id)
            target_set = ConcurrentStableSet(target)
            for link in existing:
                if link.post_id not in target_set:
                    await self._role_posts.soft_delete(link.id)
                    await self._publish(role_id, link.post_id, CHANGE_UNASSIGNED)
            existing_ids = ConcurrentStableSet(link.post_id for link in existing)
            for post_id in target:
                if post_id not in existing_ids:
                    await self._role_posts.create(role_id=role_id, post_id=post_id)
                    await self._publish(role_id, post_id, CHANGE_ASSIGNED)
        return target

    async def unassign_role_post(self, *, role_id: int, post_id: int) -> None:
        """解绑单个角色-岗位（软删除）。

        Args:
            role_id: 角色 id。
            post_id: 岗位 id。

        Raises:
            OrgRolePostNotFoundError: 分配不存在（330081）。
        """
        async with self._uow.begin():
            link = await self._role_posts.get_active(role_id=role_id, post_id=post_id)
            if link is None:
                raise OrgRolePostNotFoundError(f"角色-岗位分配不存在：role={role_id}, post={post_id}")
            await self._role_posts.soft_delete(link.id)
            await self._publish(role_id, post_id, CHANGE_UNASSIGNED)

    async def _publish(self, role_id: int, post_id: int, changed_type: str) -> None:
        """发布角色-岗位变更事件（同事务写发件箱）。

        Args:
            role_id: 角色 id。
            post_id: 岗位 id。
            changed_type: 变更类型。
        """
        await self._outbox.enqueue(
            self._session,
            EventEnvelope(
                event_type=ROLE_POST_CHANGED_EVENT,
                payload=ConcurrentStableDict(
                    {"role_id": str(role_id), "post_id": str(post_id), "changed_type": changed_type}
                ),
                tenant_id=current_tenant_id_str(),
                aggregate_key=f"org.role_post:{role_id}",
            ),
        )


def _dedupe(values: ConcurrentStableList[int]) -> ConcurrentStableList[int]:
    """保序去重。

    Args:
        values: 原始值列表。

    Returns:
        ConcurrentStableList[int]: 去重后的值（插入序）。
    """
    unique: ConcurrentStableList[int] = ConcurrentStableList()
    for value in values:
        if value not in unique:
            unique.add(value)
    return unique
