"""角色-部门分配服务：按角色查部门 / 全量覆盖（diff 后增删单事务）/ 解绑。"""

from typing import cast

from bms_core.core.concurrent import ConcurrentStableDict, ConcurrentStableList, ConcurrentStableSet
from bms_core.core.objects import BaseFrameworkObject
from bms_core.db.session import DbSession
from bms_core.db.tenant import current_tenant_id_str
from bms_core.db.unit_of_work import UnitOfWork
from bms_core.events.base import EventEnvelope
from bms_core.outbox.base import BaseOutboxStore

from mdm_org.errors import OrgDeptNotFoundError, OrgRoleDeptNotFoundError
from mdm_org.events import ROLE_DEPT_CHANGED_EVENT
from mdm_org.repositories.dept import DeptRepository
from mdm_org.repositories.role_dept import RoleDeptRepository

CHANGE_ASSIGNED = "assigned"
"""变更类型：分配。"""

CHANGE_UNASSIGNED = "unassigned"
"""变更类型：解绑。"""


class RoleDeptService(BaseFrameworkObject):
    """角色-部门分配服务（全量覆盖为「diff 后增删」单事务）。"""

    def __init__(
        self,
        role_depts: RoleDeptRepository,
        depts: DeptRepository,
        uow: UnitOfWork,
        outbox: BaseOutboxStore,
    ) -> None:
        """初始化。

        Args:
            role_depts: 角色-部门分配仓储。
            depts: 部门仓储（部门存在性校验）。
            uow: 工作单元（事务边界）。
            outbox: 事务性发件箱。
        """
        self._role_depts = role_depts
        self._depts = depts
        self._uow = uow
        self._outbox = outbox

    @property
    def _session(self) -> DbSession:
        """当前事务会话。

        Returns:
            DbSession: 请求级会话。
        """
        return cast("DbSession", self._uow.session)

    async def list_role_depts(self, role_id: int) -> ConcurrentStableList[int]:
        """按角色取已分配部门 id。

        Args:
            role_id: 角色 id。

        Returns:
            ConcurrentStableList[int]: 部门 id（插入序）。
        """
        return ConcurrentStableList(link.dept_id for link in await self._role_depts.list_by_role(role_id))

    async def assign_role_depts(
        self, *, role_id: int, dept_ids: ConcurrentStableList[int]
    ) -> ConcurrentStableList[int]:
        """全量覆盖分配角色部门（diff 后增删，单事务）。

        Args:
            role_id: 角色 id。
            dept_ids: 目标部门 id 清单（全量）。

        Returns:
            ConcurrentStableList[int]: 分配后的部门 id（插入序）。

        Raises:
            OrgDeptNotFoundError: 目标部门不存在（330051）。
        """
        target = _dedupe(dept_ids)
        async with self._uow.begin():
            for dept_id in target:
                if await self._depts.get(dept_id) is None:
                    raise OrgDeptNotFoundError(f"部门不存在：{dept_id}")
            existing = await self._role_depts.list_by_role(role_id)
            target_set = ConcurrentStableSet(target)
            for link in existing:
                if link.dept_id not in target_set:
                    await self._role_depts.soft_delete(link.id)
                    await self._publish(role_id, link.dept_id, CHANGE_UNASSIGNED)
            existing_ids = ConcurrentStableSet(link.dept_id for link in existing)
            for dept_id in target:
                if dept_id not in existing_ids:
                    await self._role_depts.create(role_id=role_id, dept_id=dept_id)
                    await self._publish(role_id, dept_id, CHANGE_ASSIGNED)
        return target

    async def unassign_role_dept(self, *, role_id: int, dept_id: int) -> None:
        """解绑单个角色-部门（软删除）。

        Args:
            role_id: 角色 id。
            dept_id: 部门 id。

        Raises:
            OrgRoleDeptNotFoundError: 分配不存在（330091）。
        """
        async with self._uow.begin():
            link = await self._role_depts.get_active(role_id=role_id, dept_id=dept_id)
            if link is None:
                raise OrgRoleDeptNotFoundError(f"角色-部门分配不存在：role={role_id}, dept={dept_id}")
            await self._role_depts.soft_delete(link.id)
            await self._publish(role_id, dept_id, CHANGE_UNASSIGNED)

    async def _publish(self, role_id: int, dept_id: int, changed_type: str) -> None:
        """发布角色-部门变更事件（同事务写发件箱）。

        Args:
            role_id: 角色 id。
            dept_id: 部门 id。
            changed_type: 变更类型。
        """
        await self._outbox.enqueue(
            self._session,
            EventEnvelope(
                event_type=ROLE_DEPT_CHANGED_EVENT,
                payload=ConcurrentStableDict(
                    {"role_id": str(role_id), "dept_id": str(dept_id), "changed_type": changed_type}
                ),
                tenant_id=current_tenant_id_str(),
                aggregate_key=f"org.role_dept:{role_id}",
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
