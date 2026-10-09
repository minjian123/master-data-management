"""用户-岗位分配服务：按用户查岗位 / 全量覆盖（diff 后增删单事务）/ 解绑 / 用户删除清理。"""

from typing import cast

from bms_core.config.base import BaseConfigSource
from bms_core.core.concurrent import ConcurrentStableDict, ConcurrentStableList, ConcurrentStableSet
from bms_core.core.objects import BaseFrameworkObject
from bms_core.db.session import DbSession
from bms_core.db.tenant import current_tenant_id_str
from bms_core.db.unit_of_work import UnitOfWork
from bms_core.events.base import EventEnvelope
from bms_core.outbox.base import BaseOutboxStore

from mdm_org import config as org_config
from mdm_org.errors import (
    OrgPostNotFoundError,
    OrgUserPostLimitExceededError,
    OrgUserPostNotFoundError,
    OrgUserPrimaryNotAssignedError,
)
from mdm_org.events import USER_POST_CHANGED_EVENT
from mdm_org.repositories.post import PostRepository
from mdm_org.repositories.user_post import UserPostRepository

CHANGE_ASSIGNED = "assigned"
"""变更类型：分配。"""

CHANGE_UNASSIGNED = "unassigned"
"""变更类型：解绑。"""

CHANGE_PRIMARY = "primary"
"""变更类型：主要岗位置位 / 清除。"""


class UserPostService(BaseFrameworkObject):
    """用户-岗位分配服务（全量覆盖为「diff 后增删」单事务）。"""

    def __init__(
        self,
        user_posts: UserPostRepository,
        posts: PostRepository,
        uow: UnitOfWork,
        config: BaseConfigSource,
        outbox: BaseOutboxStore,
    ) -> None:
        """初始化。

        Args:
            user_posts: 用户-岗位关联仓储。
            posts: 岗位仓储（岗位存在性校验）。
            uow: 工作单元（事务边界）。
            config: 系统参数取数。
            outbox: 事务性发件箱。
        """
        self._user_posts = user_posts
        self._posts = posts
        self._uow = uow
        self._config = config
        self._outbox = outbox

    @property
    def _session(self) -> DbSession:
        """当前事务会话。

        Returns:
            DbSession: 请求级会话。
        """
        return cast("DbSession", self._uow.session)

    async def list_user_posts(self, user_id: int) -> ConcurrentStableList[int]:
        """按用户取已分配岗位 id。

        Args:
            user_id: 用户 id。

        Returns:
            ConcurrentStableList[int]: 岗位 id（插入序）。
        """
        return ConcurrentStableList(link.post_id for link in await self._user_posts.list_by_user(user_id))

    async def primary_post_id(self, user_id: int) -> int | None:
        """取该用户的主要岗位 id（未置位返回 None）。

        Args:
            user_id: 用户 id。

        Returns:
            int | None: 主要岗位 id。
        """
        for link in await self._user_posts.list_by_user(user_id):
            if link.is_primary:
                return link.post_id
        return None

    async def assign_user_posts(
        self, *, user_id: int, post_ids: ConcurrentStableList[int]
    ) -> ConcurrentStableList[int]:
        """全量覆盖分配用户岗位（diff 后增删，单事务；受单用户岗位数上限约束）。

        Args:
            user_id: 用户 id。
            post_ids: 目标岗位 id 清单（全量）。

        Returns:
            ConcurrentStableList[int]: 分配后的岗位 id（插入序）。

        Raises:
            OrgPostNotFoundError: 目标岗位不存在（330031）。
            OrgUserPostLimitExceededError: 单用户岗位数超上限（330072）。
        """
        target = _dedupe(post_ids)
        limit = await org_config.read_int(
            self._config, org_config.POST_MAX_PER_USER_KEY, org_config.DEFAULT_POST_MAX_PER_USER
        )
        if len(target) > limit:
            raise OrgUserPostLimitExceededError(f"单用户岗位数超上限：{limit}")
        async with self._uow.begin():
            for post_id in target:
                if await self._posts.get(post_id) is None:
                    raise OrgPostNotFoundError(f"岗位不存在：{post_id}")
            existing = await self._user_posts.list_by_user(user_id)
            target_set = ConcurrentStableSet(target)
            for link in existing:
                if link.post_id not in target_set:
                    link.is_primary = False
                    await self._user_posts.soft_delete(link.id)
                    await self._publish(user_id, link.post_id, CHANGE_UNASSIGNED)
            existing_ids = ConcurrentStableSet(link.post_id for link in existing)
            for post_id in target:
                if post_id not in existing_ids:
                    await self._user_posts.create(user_id=user_id, post_id=post_id, is_primary=False)
                    await self._publish(user_id, post_id, CHANGE_ASSIGNED)
            await self._user_posts.flush()
        return target

    async def set_primary_post(self, *, user_id: int, post_id: int | None) -> None:
        """置位 / 清除主要岗位（同事务互斥置位：先清该用户既有主要项，再置位目标项）。

        Args:
            user_id: 用户 id。
            post_id: 目标岗位 id；None 表示清除主要标记。

        Raises:
            OrgUserPrimaryNotAssignedError: 置位目标不在该用户已分配集合内（330113）。
        """
        async with self._uow.begin():
            if post_id is None:
                current = await self._user_posts.list_by_user(user_id)
                primary = next((link for link in current if link.is_primary), None)
                if primary is None:
                    return
                target_post = primary.post_id
                await self._user_posts.clear_primary(user_id)
                await self._user_posts.flush()
                await self._publish(user_id, target_post, CHANGE_PRIMARY)
                return
            link = await self._user_posts.get_active(user_id=user_id, post_id=post_id)
            if link is None:
                raise OrgUserPrimaryNotAssignedError(f"主要岗位置位目标未分配：user={user_id}, post={post_id}")
            await self._user_posts.clear_primary(user_id)
            link.is_primary = True
            await self._user_posts.flush()
            await self._publish(user_id, post_id, CHANGE_PRIMARY)

    async def unassign_user_post(self, *, user_id: int, post_id: int) -> None:
        """解绑单个用户-岗位（软删除）。

        Args:
            user_id: 用户 id。
            post_id: 岗位 id。

        Raises:
            OrgUserPostNotFoundError: 关联不存在（330071）。
        """
        async with self._uow.begin():
            link = await self._user_posts.get_active(user_id=user_id, post_id=post_id)
            if link is None:
                raise OrgUserPostNotFoundError(f"用户-岗位关联不存在：user={user_id}, post={post_id}")
            link.is_primary = False
            await self._user_posts.soft_delete(link.id)
            await self._user_posts.flush()
            await self._publish(user_id, post_id, CHANGE_UNASSIGNED)

    async def purge_user(self, user_id: int) -> int:
        """清理某用户的全部岗位关联（消费 `sys.user.deleted`；**幂等**）。

        Args:
            user_id: 用户 id。

        Returns:
            int: 本次清理的关联条数（重复消费为 0）。
        """
        async with self._uow.begin():
            links = await self._user_posts.list_by_user(user_id)
            for link in links:
                link.is_primary = False
                await self._user_posts.soft_delete(link.id)
                await self._publish(user_id, link.post_id, CHANGE_UNASSIGNED)
            await self._user_posts.flush()
        return len(links)

    async def _publish(self, user_id: int, post_id: int, changed_type: str) -> None:
        """发布用户-岗位变更事件（同事务写发件箱）。

        Args:
            user_id: 用户 id。
            post_id: 岗位 id。
            changed_type: 变更类型。
        """
        await self._outbox.enqueue(
            self._session,
            EventEnvelope(
                event_type=USER_POST_CHANGED_EVENT,
                payload=ConcurrentStableDict(
                    {"user_id": str(user_id), "post_id": str(post_id), "changed_type": changed_type}
                ),
                tenant_id=current_tenant_id_str(),
                aggregate_key=f"org.user_post:{user_id}",
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
