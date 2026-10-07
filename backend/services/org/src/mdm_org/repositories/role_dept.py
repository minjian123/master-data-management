"""角色-部门分配仓储（`org_role_dept`）。"""

from bms_core.core.concurrent import ConcurrentStableList, ConcurrentStableSet
from bms_core.repositories.base_db_repository import BaseDbRepository
from sqlalchemy import func, select

from mdm_org.models.role_dept import OrgRoleDept


class RoleDeptRepository(BaseDbRepository[OrgRoleDept]):
    """角色-部门分配仓储（按角色 / 部门双向查询）。"""

    model = OrgRoleDept
    sortable_fields = ConcurrentStableSet({"id", "role_id", "dept_id", "created_at"})

    async def flush(self) -> None:
        """刷新会话（服务层同事务内改 ORM 属性后调用）。"""
        await self._session.flush()

    async def list_by_role(self, role_id: int) -> ConcurrentStableList[OrgRoleDept]:
        """取角色已分配部门关联。

        Args:
            role_id: 角色 id。

        Returns:
            ConcurrentStableList[OrgRoleDept]: 关联记录（插入序）。
        """
        statement = self._select().where(self._column("role_id") == role_id)
        return ConcurrentStableList((await self._session.execute(statement)).scalars().all())

    async def list_by_dept(self, dept_id: int) -> ConcurrentStableList[OrgRoleDept]:
        """取部门的已分配角色关联。

        Args:
            dept_id: 部门 id。

        Returns:
            ConcurrentStableList[OrgRoleDept]: 关联记录（插入序）。
        """
        statement = self._select().where(self._column("dept_id") == dept_id)
        return ConcurrentStableList((await self._session.execute(statement)).scalars().all())

    async def get_active(self, *, role_id: int, dept_id: int) -> OrgRoleDept | None:
        """取未解绑的角色-部门分配。

        Args:
            role_id: 角色 id。
            dept_id: 部门 id。

        Returns:
            OrgRoleDept | None: 关联记录；不存在返回 None。
        """
        statement = self._select().where(self._column("role_id") == role_id, self._column("dept_id") == dept_id)
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def count_by_dept(self, dept_id: int) -> int:
        """取部门绑定角色数（部门删除引用检查）。

        Args:
            dept_id: 部门 id。

        Returns:
            int: 绑定角色数。
        """
        statement = (
            select(func.count()).select_from(self.model).where(*self._scope_where(), self._column("dept_id") == dept_id)
        )
        return int((await self._session.execute(statement)).scalar_one())
