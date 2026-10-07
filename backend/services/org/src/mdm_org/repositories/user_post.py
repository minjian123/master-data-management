"""用户-岗位关联仓储（`org_user_post`）。"""

from bms_core.core.concurrent import ConcurrentStableList, ConcurrentStableSet
from bms_core.repositories.base_db_repository import BaseDbRepository
from sqlalchemy import func, select

from mdm_org.models.user_post import OrgUserPost


class UserPostRepository(BaseDbRepository[OrgUserPost]):
    """用户-岗位关联仓储（按用户 / 岗位双向查询）。"""

    model = OrgUserPost
    sortable_fields = ConcurrentStableSet({"id", "user_id", "post_id", "created_at"})

    async def flush(self) -> None:
        """刷新会话（服务层同事务内改 ORM 属性后调用）。"""
        await self._session.flush()

    async def list_by_user(self, user_id: int) -> ConcurrentStableList[OrgUserPost]:
        """取用户已分配岗位关联。

        Args:
            user_id: 用户 id。

        Returns:
            ConcurrentStableList[OrgUserPost]: 关联记录（插入序）。
        """
        statement = self._select().where(self._column("user_id") == user_id)
        return ConcurrentStableList((await self._session.execute(statement)).scalars().all())

    async def list_by_post(self, post_id: int) -> ConcurrentStableList[OrgUserPost]:
        """取岗位下用户关联。

        Args:
            post_id: 岗位 id。

        Returns:
            ConcurrentStableList[OrgUserPost]: 关联记录（插入序）。
        """
        statement = self._select().where(self._column("post_id") == post_id)
        return ConcurrentStableList((await self._session.execute(statement)).scalars().all())

    async def list_by_posts(self, post_ids: ConcurrentStableList[int]) -> ConcurrentStableList[OrgUserPost]:
        """取一组岗位下的用户关联（部门含子级的用户派生用；单批 IN 查询避免 N+1）。

        Args:
            post_ids: 岗位 id 序列。

        Returns:
            ConcurrentStableList[OrgUserPost]: 关联记录（库返回序）。
        """
        if not post_ids:
            return ConcurrentStableList()
        statement = self._select().where(self._column("post_id").in_(tuple(post_ids)))
        return ConcurrentStableList((await self._session.execute(statement)).scalars().all())

    async def get_active(self, *, user_id: int, post_id: int) -> OrgUserPost | None:
        """取未解绑的用户-岗位关联。

        Args:
            user_id: 用户 id。
            post_id: 岗位 id。

        Returns:
            OrgUserPost | None: 关联记录；不存在返回 None。
        """
        statement = self._select().where(self._column("user_id") == user_id, self._column("post_id") == post_id)
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def count_by_user(self, user_id: int) -> int:
        """取用户已分配岗位数（上限校验）。

        Args:
            user_id: 用户 id。

        Returns:
            int: 已分配岗位数。
        """
        statement = (
            select(func.count()).select_from(self.model).where(*self._scope_where(), self._column("user_id") == user_id)
        )
        return int((await self._session.execute(statement)).scalar_one())

    async def count_by_post(self, post_id: int) -> int:
        """取岗位关联用户数（岗位删除引用检查）。

        Args:
            post_id: 岗位 id。

        Returns:
            int: 关联用户数。
        """
        statement = (
            select(func.count()).select_from(self.model).where(*self._scope_where(), self._column("post_id") == post_id)
        )
        return int((await self._session.execute(statement)).scalar_one())
