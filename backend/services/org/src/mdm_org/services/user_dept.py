"""用户-部门分配服务：按用户查部门 / 全量覆盖（diff 后增删单事务）/ 解绑 / 主要部门置位 / 用户删除清理。"""

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
    OrgDeptNotFoundError,
    OrgUserDeptLimitExceededError,
    OrgUserDeptNotFoundError,
    OrgUserPrimaryNotAssignedError,
)
from mdm_org.events import USER_DEPT_CHANGED_EVENT
from mdm_org.repositories.dept import DeptRepository
from mdm_org.repositories.user_dept import UserDeptRepository

CHANGE_ASSIGNED = "assigned"
"""变更类型：分配。"""

CHANGE_UNASSIGNED = "unassigned"
"""变更类型：解绑。"""

CHANGE_PRIMARY = "primary"
"""变更类型：主要部门置位 / 清除。"""


class UserDeptService(BaseFrameworkObject):
    """用户-部门分配服务（全量覆盖为「diff 后增删」单事务；主要部门互斥置位同事务完成）。"""

    def __init__(
        self,
        user_depts: UserDeptRepository,
        depts: DeptRepository,
        uow: UnitOfWork,
        config: BaseConfigSource,
        outbox: BaseOutboxStore,
    ) -> None:
        """初始化。

        Args:
            user_depts: 用户-部门关联仓储。
            depts: 部门仓储（部门存在性校验）。
            uow: 工作单元（事务边界）。
            config: 系统参数取数。
            outbox: 事务性发件箱。
        """
        self._user_depts = user_depts
        self._depts = depts
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

    async def list_user_depts(self, user_id: int) -> ConcurrentStableList[int]:
        """按用户取已分配部门 id。

        Args:
            user_id: 用户 id。

        Returns:
            ConcurrentStableList[int]: 部门 id（插入序）。
        """
        return ConcurrentStableList(link.dept_id for link in await self._user_depts.list_by_user(user_id))

    async def primary_dept_id(self, user_id: int) -> int | None:
        """取该用户的主要部门 id（未置位返回 None）。

        Args:
            user_id: 用户 id。

        Returns:
            int | None: 主要部门 id。
        """
        for link in await self._user_depts.list_by_user(user_id):
            if link.is_primary:
                return link.dept_id
        return None

    async def assign_user_depts(
        self, *, user_id: int, dept_ids: ConcurrentStableList[int]
    ) -> ConcurrentStableList[int]:
        """全量覆盖分配用户部门（diff 后增删，单事务；受单用户部门数上限约束）。

        被移除项若为**主要部门**，同事务清空其标记（不留悬空主要项）。

        Args:
            user_id: 用户 id。
            dept_ids: 目标部门 id 清单（全量）。

        Returns:
            ConcurrentStableList[int]: 分配后的部门 id（插入序）。

        Raises:
            OrgDeptNotFoundError: 目标部门不存在（330051）。
            OrgUserDeptLimitExceededError: 单用户部门数超上限（330112）。
        """
        target = _dedupe(dept_ids)
        limit = await org_config.read_int(
            self._config, org_config.DEPT_MAX_PER_USER_KEY, org_config.DEFAULT_DEPT_MAX_PER_USER
        )
        if len(target) > limit:
            raise OrgUserDeptLimitExceededError(f"单用户部门数超上限：{limit}")
        async with self._uow.begin():
            for dept_id in target:
                if await self._depts.get(dept_id) is None:
                    raise OrgDeptNotFoundError(f"部门不存在：{dept_id}")
            existing = await self._user_depts.list_by_user(user_id)
            target_set = ConcurrentStableSet(target)
            for link in existing:
                if link.dept_id not in target_set:
                    link.is_primary = False
                    await self._user_depts.soft_delete(link.id)
                    await self._publish(user_id, link.dept_id, CHANGE_UNASSIGNED)
            existing_ids = ConcurrentStableSet(link.dept_id for link in existing)
            for dept_id in target:
                if dept_id not in existing_ids:
                    await self._user_depts.create(user_id=user_id, dept_id=dept_id, is_primary=False)
                    await self._publish(user_id, dept_id, CHANGE_ASSIGNED)
            await self._user_depts.flush()
        return target

    async def unassign_user_dept(self, *, user_id: int, dept_id: int) -> None:
        """解绑单个用户-部门（软删除；若为主要部门同时清空标记）。

        Args:
            user_id: 用户 id。
            dept_id: 部门 id。

        Raises:
            OrgUserDeptNotFoundError: 关联不存在（330111）。
        """
        async with self._uow.begin():
            link = await self._user_depts.get_active(user_id=user_id, dept_id=dept_id)
            if link is None:
                raise OrgUserDeptNotFoundError(f"用户-部门关联不存在：user={user_id}, dept={dept_id}")
            link.is_primary = False
            await self._user_depts.soft_delete(link.id)
            await self._user_depts.flush()
            await self._publish(user_id, dept_id, CHANGE_UNASSIGNED)

    async def set_primary_dept(self, *, user_id: int, dept_id: int | None) -> None:
        """置位 / 清除主要部门（同事务互斥置位：先清该用户既有主要项，再置位目标项）。

        Args:
            user_id: 用户 id。
            dept_id: 目标部门 id；None 表示清除主要标记。

        Raises:
            OrgUserPrimaryNotAssignedError: 置位目标不在该用户已分配集合内（330113）。
        """
        async with self._uow.begin():
            if dept_id is None:
                current = await self._user_depts.list_by_user(user_id)
                primary = next((link for link in current if link.is_primary), None)
                if primary is None:
                    return
                target_dept = primary.dept_id
                await self._user_depts.clear_primary(user_id)
                await self._user_depts.flush()
                await self._publish(user_id, target_dept, CHANGE_PRIMARY)
                return
            link = await self._user_depts.get_active(user_id=user_id, dept_id=dept_id)
            if link is None:
                raise OrgUserPrimaryNotAssignedError(f"主要部门置位目标未分配：user={user_id}, dept={dept_id}")
            await self._user_depts.clear_primary(user_id)
            link.is_primary = True
            await self._user_depts.flush()
            await self._publish(user_id, dept_id, CHANGE_PRIMARY)

    async def purge_user(self, user_id: int) -> int:
        """清理某用户的全部部门关联（消费 `sys.user.deleted`；**幂等**）。

        Args:
            user_id: 用户 id。

        Returns:
            int: 本次清理的关联条数（重复消费为 0）。
        """
        async with self._uow.begin():
            links = await self._user_depts.list_by_user(user_id)
            for link in links:
                link.is_primary = False
                await self._user_depts.soft_delete(link.id)
                await self._publish(user_id, link.dept_id, CHANGE_UNASSIGNED)
            await self._user_depts.flush()
        return len(links)

    async def _publish(self, user_id: int, dept_id: int, changed_type: str) -> None:
        """发布用户-部门变更事件（同事务写发件箱）。

        Args:
            user_id: 用户 id。
            dept_id: 部门 id。
            changed_type: 变更类型。
        """
        await self._outbox.enqueue(
            self._session,
            EventEnvelope(
                event_type=USER_DEPT_CHANGED_EVENT,
                payload=ConcurrentStableDict(
                    {"user_id": str(user_id), "dept_id": str(dept_id), "changed_type": changed_type}
                ),
                tenant_id=current_tenant_id_str(),
                aggregate_key=f"org.user_dept:{user_id}",
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
