"""角色-岗位分配仓储（`org_role_post`）。"""

from bms_core.core.concurrent import ConcurrentStableList, ConcurrentStableSet
from bms_core.repositories.base_db_repository import BaseDbRepository
from sqlalchemy import func, select

from mdm_org.models.role_post import OrgRolePost


class RolePostRepository(BaseDbRepository[OrgRolePost]):
    """角色-岗位分配仓储（按角色 / 岗位双向查询）。"""

    model = OrgRolePost
    sortable_fields = ConcurrentStableSet({"id", "role_id", "post_id", "created_at"})

    async def flush(self) -> None:
        """刷新会话（服务层同事务内改 ORM 属性后调用）。"""
        await self._session.flush()

    async def list_by_role(self, role_id: int) -> ConcurrentStableList[OrgRolePost]:
        """取角色已分配岗位关联。

        Args:
            role_id: 角色 id。

        Returns:
            ConcurrentStableList[OrgRolePost]: 关联记录（插入序）。
        """
        statement = self._select().where(self._column("role_id") == role_id)
        return ConcurrentStableList((await self._session.execute(statement)).scalars().all())

    async def list_by_post(self, post_id: int) -> ConcurrentStableList[OrgRolePost]:
        """取岗位的已分配角色关联。

        Args:
            post_id: 岗位 id。

        Returns:
            ConcurrentStableList[OrgRolePost]: 关联记录（插入序）。
        """
        statement = self._select().where(self._column("post_id") == post_id)
        return ConcurrentStableList((await self._session.execute(statement)).scalars().all())

    async def list_by_posts(self, post_ids: ConcurrentStableList[int]) -> ConcurrentStableList[OrgRolePost]:
        """取一组岗位的已分配角色关联（按用户解析角色的岗位链用；单批 IN 查询避免 N+1）。

        Args:
            post_ids: 岗位 id 序列。

        Returns:
            ConcurrentStableList[OrgRolePost]: 关联记录（库返回序）。
        """
        if not post_ids:
            return ConcurrentStableList()
        statement = self._select().where(self._column("post_id").in_(tuple(post_ids)))
        return ConcurrentStableList((await self._session.execute(statement)).scalars().all())

    async def get_active(self, *, role_id: int, post_id: int) -> OrgRolePost | None:
        """取未解绑的角色-岗位分配。

        Args:
            role_id: 角色 id。
            post_id: 岗位 id。

        Returns:
            OrgRolePost | None: 关联记录；不存在返回 None。
        """
        statement = self._select().where(self._column("role_id") == role_id, self._column("post_id") == post_id)
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def count_by_post(self, post_id: int) -> int:
        """取岗位绑定角色数（岗位删除引用检查）。

        Args:
            post_id: 岗位 id。

        Returns:
            int: 绑定角色数。
        """
        statement = (
            select(func.count()).select_from(self.model).where(*self._scope_where(), self._column("post_id") == post_id)
        )
        return int((await self._session.execute(statement)).scalar_one())
