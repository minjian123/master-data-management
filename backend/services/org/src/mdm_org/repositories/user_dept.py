"""用户-部门关联仓储（`org_user_dept`）。"""

from bms_core.core.concurrent import ConcurrentStableList, ConcurrentStableSet
from bms_core.repositories.base_db_repository import BaseDbRepository
from sqlalchemy import func, select, update

from mdm_org.models.user_dept import OrgUserDept


class UserDeptRepository(BaseDbRepository[OrgUserDept]):
    """用户-部门关联仓储（按用户 / 部门双向查询 + 主要项互斥置位）。"""

    model = OrgUserDept
    sortable_fields = ConcurrentStableSet({"id", "user_id", "dept_id", "created_at"})

    async def flush(self) -> None:
        """刷新会话（服务层同事务内改 ORM 属性后调用）。"""
        await self._session.flush()

    async def list_by_user(self, user_id: int) -> ConcurrentStableList[OrgUserDept]:
        """取用户已分配部门关联。

        Args:
            user_id: 用户 id。

        Returns:
            ConcurrentStableList[OrgUserDept]: 关联记录（插入序）。
        """
        statement = self._select().where(self._column("user_id") == user_id)
        return ConcurrentStableList((await self._session.execute(statement)).scalars().all())

    async def list_by_dept(self, dept_id: int) -> ConcurrentStableList[OrgUserDept]:
        """取部门下用户关联。

        Args:
            dept_id: 部门 id。

        Returns:
            ConcurrentStableList[OrgUserDept]: 关联记录（插入序）。
        """
        statement = self._select().where(self._column("dept_id") == dept_id)
        return ConcurrentStableList((await self._session.execute(statement)).scalars().all())

    async def list_by_depts(self, dept_ids: ConcurrentStableList[int]) -> ConcurrentStableList[OrgUserDept]:
        """取一组部门下的用户关联（单批 IN 查询避免 N+1）。

        Args:
            dept_ids: 部门 id 序列。

        Returns:
            ConcurrentStableList[OrgUserDept]: 关联记录（库返回序）。
        """
        if not dept_ids:
            return ConcurrentStableList()
        statement = self._select().where(self._column("dept_id").in_(tuple(dept_ids)))
        return ConcurrentStableList((await self._session.execute(statement)).scalars().all())

    async def get_active(self, *, user_id: int, dept_id: int) -> OrgUserDept | None:
        """取未解绑的用户-部门关联。

        Args:
            user_id: 用户 id。
            dept_id: 部门 id。

        Returns:
            OrgUserDept | None: 关联记录；不存在返回 None。
        """
        statement = self._select().where(self._column("user_id") == user_id, self._column("dept_id") == dept_id)
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def count_by_user(self, user_id: int) -> int:
        """取用户已分配部门数（上限校验）。

        Args:
            user_id: 用户 id。

        Returns:
            int: 已分配部门数。
        """
        statement = (
            select(func.count()).select_from(self.model).where(*self._scope_where(), self._column("user_id") == user_id)
        )
        return int((await self._session.execute(statement)).scalar_one())

    async def count_by_dept(self, dept_id: int) -> int:
        """取部门关联用户数（部门删除引用检查）。

        Args:
            dept_id: 部门 id。

        Returns:
            int: 关联用户数。
        """
        statement = (
            select(func.count()).select_from(self.model).where(*self._scope_where(), self._column("dept_id") == dept_id)
        )
        return int((await self._session.execute(statement)).scalar_one())

    async def clear_primary(self, user_id: int) -> None:
        """清空该用户的主要部门标记（置位前调用；未标记行无操作）。

        Args:
            user_id: 用户 id。
        """
        statement = (
            update(self.model)
            .where(*self._scope_where(), self._column("user_id") == user_id, self._column("is_primary").is_(True))
            .values(is_primary=False)
        )
        await self._session.execute(statement)
