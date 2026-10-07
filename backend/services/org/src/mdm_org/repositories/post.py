"""岗位仓储（`org_post`）：分页筛选、岗位码查询与部门维度计数。"""

from bms_core.core.concurrent import ConcurrentStableList, ConcurrentStableSet
from bms_core.repositories.base_db_repository import BaseDbRepository
from bms_core.schemas.pagination import BasePageQuery
from sqlalchemy import ColumnElement, func, or_, select

from mdm_org.models.post import OrgPost


class PostRepository(BaseDbRepository[OrgPost]):
    """岗位仓储（分页列表 + 筛选 / 排序）。"""

    model = OrgPost
    sortable_fields = ConcurrentStableSet({"id", "code", "name", "sort", "status"})

    async def flush(self) -> None:
        """刷新会话（服务层同事务内改 ORM 属性后调用）。"""
        await self._session.flush()

    async def get_by_code(self, code: str) -> OrgPost | None:
        """按岗位码取岗位（租户内唯一检查）。

        Args:
            code: 岗位码。

        Returns:
            OrgPost | None: 岗位；不存在返回 None。
        """
        statement = self._select().where(self._column("code") == code)
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def list_filtered(
        self,
        query: BasePageQuery,
        *,
        dept_id: int | None = None,
        status: str | None = None,
        keyword: str | None = None,
    ) -> ConcurrentStableList[OrgPost]:
        """分页查询岗位（按部门 / 状态 / 关键字筛选）。

        Args:
            query: 分页查询契约（`page` / `size` / 排序）。
            dept_id: 归属部门过滤；None 不过滤。
            status: 状态过滤；None 不过滤。
            keyword: 关键字（岗位码 / 名称模糊）；None 不过滤。

        Returns:
            ConcurrentStableList[OrgPost]: 当前页记录。
        """
        statement = (
            self._apply_sort(self._select(), self._resolve_sort(query))
            .where(*self._conditions(dept_id=dept_id, status=status, keyword=keyword))
            .limit(query.size)
            .offset((query.page - 1) * query.size)
        )
        return ConcurrentStableList((await self._session.execute(statement)).scalars().all())

    async def count_filtered(
        self,
        *,
        dept_id: int | None = None,
        status: str | None = None,
        keyword: str | None = None,
    ) -> int:
        """统计岗位总数（与 `list_filtered` 同口径）。

        Args:
            dept_id: 归属部门过滤；None 不过滤。
            status: 状态过滤；None 不过滤。
            keyword: 关键字过滤；None 不过滤。

        Returns:
            int: 记录条数。
        """
        statement = (
            select(func.count())
            .select_from(self.model)
            .where(*self._scope_where(), *self._conditions(dept_id=dept_id, status=status, keyword=keyword))
        )
        return int((await self._session.execute(statement)).scalar_one())

    async def list_by_dept(self, dept_id: int) -> ConcurrentStableList[OrgPost]:
        """取部门下岗位（部门用户聚合 / 子树维护用）。

        Args:
            dept_id: 部门 id。

        Returns:
            ConcurrentStableList[OrgPost]: 岗位列表（插入序）。
        """
        statement = self._select().where(self._column("dept_id") == dept_id)
        return ConcurrentStableList((await self._session.execute(statement)).scalars().all())

    async def count_by_dept(self, dept_id: int) -> int:
        """取部门下岗位数（部门删除引用检查）。

        Args:
            dept_id: 部门 id。

        Returns:
            int: 岗位数。
        """
        statement = (
            select(func.count()).select_from(self.model).where(*self._scope_where(), self._column("dept_id") == dept_id)
        )
        return int((await self._session.execute(statement)).scalar_one())

    def _conditions(
        self,
        *,
        dept_id: int | None,
        status: str | None,
        keyword: str | None,
    ) -> ConcurrentStableList[ColumnElement[bool]]:
        """构造筛选条件（列表与计数同口径）。

        Args:
            dept_id: 归属部门过滤。
            status: 状态过滤。
            keyword: 关键字。

        Returns:
            ConcurrentStableList[ColumnElement[bool]]: 条件列表（插入序）。
        """
        conditions: ConcurrentStableList[ColumnElement[bool]] = ConcurrentStableList()
        if dept_id is not None:
            conditions.add(self._column("dept_id") == dept_id)
        if status is not None:
            conditions.add(self._column("status") == status)
        if keyword:
            pattern = f"%{keyword.lower()}%"
            conditions.add(
                or_(
                    func.lower(self._column("code")).like(pattern),
                    func.lower(self._column("name")).like(pattern),
                )
            )
        return conditions
