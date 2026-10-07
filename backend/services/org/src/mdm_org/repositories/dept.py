"""部门仓储（`org_dept`）：全量树取数、父子 / 子树查询与引用检查计数。"""

from bms_core.core.concurrent import ConcurrentStableList, ConcurrentStableSet
from bms_core.repositories.base_db_repository import BaseDbRepository
from sqlalchemy import ColumnElement, func, select

from mdm_org.models.dept import OrgDept


class DeptRepository(BaseDbRepository[OrgDept]):
    """部门仓储（树为主：树取数不分页）。"""

    model = OrgDept
    sortable_fields = ConcurrentStableSet({"id", "name", "sort", "status"})

    async def flush(self) -> None:
        """刷新会话（服务层同事务内改 ORM 属性后调用）。"""
        await self._session.flush()

    async def list_all(self, *, status: str | None = None) -> ConcurrentStableList[OrgDept]:
        """取部门全量（树构建用；按 `sort` 与 `id` 排序）。

        Args:
            status: 状态过滤；None 取全部。

        Returns:
            ConcurrentStableList[OrgDept]: 部门列表（插入序）。
        """
        statement = self._select().order_by(self._column("sort"), self._column("id"))
        if status is not None:
            statement = statement.where(self._column("status") == status)
        return ConcurrentStableList((await self._session.execute(statement)).scalars().all())

    async def get_by_parent_name(self, *, parent_id: int | None, name: str) -> OrgDept | None:
        """按「父部门 + 名称」取部门（同父名称唯一检查）。

        Args:
            parent_id: 父部门 id（None 表示根层级）。
            name: 部门名称。

        Returns:
            OrgDept | None: 部门；不存在返回 None。
        """
        parent_column = self._column("parent_id")
        parent_condition: ColumnElement[bool] = (
            parent_column.is_(None) if parent_id is None else parent_column == parent_id
        )
        statement = self._select().where(parent_condition, self._column("name") == name)
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def count_children(self, parent_id: int) -> int:
        """取直接子部门数（删除引用检查 / 子节点数上限）。

        Args:
            parent_id: 父部门 id。

        Returns:
            int: 子部门数。
        """
        statement = (
            select(func.count())
            .select_from(self.model)
            .where(*self._scope_where(), self._column("parent_id") == parent_id)
        )
        return int((await self._session.execute(statement)).scalar_one())

    async def list_subtree(self, *, prefix: str) -> ConcurrentStableList[OrgDept]:
        """取子树（`ancestors` 前缀匹配；不含自身）。

        Args:
            prefix: 子树前缀（`{自身 ancestors}{自身 id}/`）。

        Returns:
            ConcurrentStableList[OrgDept]: 后代部门列表（插入序）。
        """
        statement = self._select().where(self._column("ancestors").like(f"{prefix}%"))
        return ConcurrentStableList((await self._session.execute(statement)).scalars().all())

    async def count_referenced(self, dept_id: int) -> int:
        """取部门子树内的部门数（含自身；删除前后一致性核对用）。

        Args:
            dept_id: 部门 id。

        Returns:
            int: 计数（不存在返回 0）。
        """
        dept = await self.get(dept_id)
        if dept is None:
            return 0
        statement = (
            select(func.count())
            .select_from(self.model)
            .where(*self._scope_where(), self._column("ancestors").like(f"{dept.ancestors}{dept_id}/%"))
        )
        return 1 + int((await self._session.execute(statement)).scalar_one())
