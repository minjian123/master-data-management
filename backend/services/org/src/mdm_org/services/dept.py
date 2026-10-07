"""部门服务：组织架构树维护（新建 / 修改 / 移动级联 / 删除引用检查）与树查询。"""

from typing import cast

from bms_core.config.base import BaseConfigSource
from bms_core.core.concurrent import ConcurrentStableDict, ConcurrentStableList
from bms_core.core.exceptions import ConcurrentConflictError
from bms_core.core.objects import BaseFrameworkObject
from bms_core.db.session import DbSession
from bms_core.db.tenant import current_tenant_id_str
from bms_core.db.unit_of_work import UnitOfWork
from bms_core.events.base import EventEnvelope
from bms_core.outbox.base import BaseOutboxStore

from mdm_org import config as org_config
from mdm_org.errors import (
    OrgDeptChildrenLimitError,
    OrgDeptCycleError,
    OrgDeptDepthExceededError,
    OrgDeptHasChildrenError,
    OrgDeptHasRolesError,
    OrgDeptNameExistsError,
    OrgDeptNotFoundError,
    OrgDeptParentUnavailableError,
    OrgDeptReferencedError,
)
from mdm_org.events import DEPT_CHANGED_EVENT
from mdm_org.models.dept import ROOT_ANCESTORS, STATUS_ENABLED, OrgDept
from mdm_org.repositories.dept import DeptRepository
from mdm_org.repositories.post import PostRepository
from mdm_org.repositories.role_dept import RoleDeptRepository
from mdm_org.repositories.user_post import UserPostRepository
from mdm_org.schemas.dept import DeptTreeNode

CHANGE_CREATED = "created"
"""变更类型：新建。"""

CHANGE_UPDATED = "updated"
"""变更类型：修改。"""

CHANGE_MOVED = "moved"
"""变更类型：移动。"""

CHANGE_DELETED = "deleted"
"""变更类型：删除。"""


class DeptService(BaseFrameworkObject):
    """部门服务（事务边界：写方法经工作单元单事务；移动为级联单事务）。"""

    def __init__(
        self,
        depts: DeptRepository,
        posts: PostRepository,
        user_posts: UserPostRepository,
        role_depts: RoleDeptRepository,
        uow: UnitOfWork,
        config: BaseConfigSource,
        outbox: BaseOutboxStore,
    ) -> None:
        """初始化。

        Args:
            depts: 部门仓储。
            posts: 岗位仓储（引用检查 / 部门用户聚合）。
            user_posts: 用户-岗位关联仓储（部门用户聚合）。
            role_depts: 角色-部门分配仓储（引用检查）。
            uow: 工作单元（事务边界）。
            config: 系统参数取数。
            outbox: 事务性发件箱（事件发布）。
        """
        self._depts = depts
        self._posts = posts
        self._user_posts = user_posts
        self._role_depts = role_depts
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

    async def require_dept(self, dept_id: int) -> OrgDept:
        """取部门（不存在抛 `OrgDeptNotFoundError`）。

        Args:
            dept_id: 部门 id。

        Returns:
            OrgDept: 部门记录。

        Raises:
            OrgDeptNotFoundError: 部门不存在（330051）。
        """
        dept = await self._depts.get(dept_id)
        if dept is None:
            raise OrgDeptNotFoundError(f"部门不存在：{dept_id}")
        return dept

    async def list_tree(self, *, status: str | None = None) -> ConcurrentStableList[DeptTreeNode]:
        """取部门树（一次性返回、不分页；按 `status` 过滤）。

        Args:
            status: 状态过滤；None 取全部。

        Returns:
            ConcurrentStableList[DeptTreeNode]: 根节点列表（子节点嵌套，插入序 = sort / id 序）。
        """
        rows = await self._depts.list_all(status=status)
        return _build_tree(rows)

    async def dept_detail(self, dept_id: int) -> OrgDept:
        """取部门详情。

        Args:
            dept_id: 部门 id。

        Returns:
            OrgDept: 部门记录。
        """
        return await self.require_dept(dept_id)

    async def list_subtree_users(self, dept_id: int) -> ConcurrentStableList[int]:
        """取部门（含子树）归属用户 id 列表（按子树岗位经 `org_user_post` 聚合）。

        Args:
            dept_id: 部门 id。

        Returns:
            ConcurrentStableList[int]: 去重后的用户 id（插入序）。
        """
        dept = await self.require_dept(dept_id)
        dept_ids = _subtree_ids(dept, await self._depts.list_subtree(prefix=_subtree_prefix(dept)))
        user_ids: ConcurrentStableList[int] = ConcurrentStableList()
        for current in dept_ids:
            for post in await self._posts.list_by_dept(current):
                for link in await self._user_posts.list_by_post(post.id):
                    if link.user_id not in user_ids:
                        user_ids.add(link.user_id)
        return user_ids

    async def list_dept_roles(self, dept_id: int) -> ConcurrentStableList[int]:
        """取部门已分配角色 id 列表。

        Args:
            dept_id: 部门 id。

        Returns:
            ConcurrentStableList[int]: 角色 id（插入序）。
        """
        await self.require_dept(dept_id)
        return ConcurrentStableList(link.role_id for link in await self._role_depts.list_by_dept(dept_id))

    async def create_dept(
        self,
        *,
        name: str,
        parent_id: int | None,
        sort: int,
        actor: int | None = None,
    ) -> OrgDept:
        """新建部门（校验父部门、深度与同父名称唯一）。

        Args:
            name: 部门名称。
            parent_id: 父部门 id；None 表示根部门。
            sort: 同级排序。
            actor: 操作者（审计占位用）。

        Returns:
            OrgDept: 新建部门。

        Raises:
            OrgDeptParentUnavailableError: 父部门不存在或已停用（330052）。
            OrgDeptChildrenLimitError: 同级子部门数超上限（330058）。
            OrgDeptDepthExceededError: 部门树深度超上限（330057）。
        """
        del actor
        # 校验读与写同事务（SQLAlchemy 2.0：先读后 begin 会因自动开启事务而失败）
        async with self._uow.begin():
            parent: OrgDept | None = None
            ancestors = ROOT_ANCESTORS
            if parent_id is not None:
                parent = await self._depts.get(parent_id)
                if parent is None or parent.status != STATUS_ENABLED:
                    raise OrgDeptParentUnavailableError(f"父部门不存在或已停用：{parent_id}")
                ancestors = _subtree_prefix(parent)
            # 同父名称唯一（先于上限校验，报错更具体；DB 复合唯一兜底）
            if await self._depts.get_by_parent_name(parent_id=parent_id, name=name) is not None:
                raise OrgDeptNameExistsError(f"同父部门名称已存在：{name}")
            if parent is not None:
                max_children = await org_config.read_int(
                    self._config, org_config.DEPT_MAX_CHILDREN_KEY, org_config.DEFAULT_DEPT_MAX_CHILDREN
                )
                if await self._depts.count_children(parent.id) >= max_children:
                    raise OrgDeptChildrenLimitError(f"同级子部门数超上限：{parent.id}")
                max_depth = await org_config.read_int(
                    self._config, org_config.DEPT_TREE_MAX_DEPTH_KEY, org_config.DEFAULT_DEPT_TREE_MAX_DEPTH
                )
                if parent.ancestors.count("/") + 1 > max_depth:
                    raise OrgDeptDepthExceededError(f"部门树深度超上限：{max_depth}")
            dept = await self._depts.create(
                name=name, parent_id=parent_id, ancestors=ancestors, sort=sort, status=STATUS_ENABLED
            )
            await self._publish(dept.id, CHANGE_CREATED)
        return dept

    async def update_dept(
        self,
        *,
        dept_id: int,
        name: str | None = None,
        sort: int | None = None,
        status: str | None = None,
        version: int | None = None,
        actor: int | None = None,
    ) -> OrgDept:
        """修改部门（名称 / 排序 / 状态；`version` 乐观锁比对）。

        Args:
            dept_id: 部门 id。
            name: 新名称；None 不改。
            sort: 新排序；None 不改。
            status: 新状态；None 不改。
            version: 客户端版本（提供时比对，冲突抛统一并发冲突）。
            actor: 操作者（审计占位用）。

        Returns:
            OrgDept: 更新后的部门。

        Raises:
            OrgDeptNotFoundError: 部门不存在（330051）。
            ConcurrentConflictError: 乐观锁冲突。
        """
        del actor
        async with self._uow.begin():
            dept = await self.require_dept(dept_id)
            _guard_version(dept.version, version)
            if name is not None and name != dept.name:
                duplicate = await self._depts.get_by_parent_name(parent_id=dept.parent_id, name=name)
                if duplicate is not None and duplicate.id != dept.id:
                    raise OrgDeptNameExistsError(f"同父部门名称已存在：{name}")
                dept.name = name
            if sort is not None:
                dept.sort = sort
            if status is not None:
                dept.status = status
            await self._depts.flush()
            await self._publish(dept.id, CHANGE_UPDATED)
        return dept

    async def move_dept(self, *, dept_id: int, new_parent_id: int | None, actor: int | None = None) -> OrgDept:
        """移动部门（防环 + 同事务级联更新子树 `ancestors`）。

        Args:
            dept_id: 部门 id。
            new_parent_id: 新父部门 id；None 表示移至根层级。
            actor: 操作者（审计占位用）。

        Returns:
            OrgDept: 移动后的部门。

        Raises:
            OrgDeptNotFoundError: 部门或新父部门不存在（330051）。
            OrgDeptParentUnavailableError: 新父部门已停用（330052）。
            OrgDeptCycleError: 新父为自身或其后代（330053）。
            OrgDeptDepthExceededError: 移动后子树深度超上限（330057）。
        """
        del actor
        async with self._uow.begin():
            dept = await self.require_dept(dept_id)
            new_parent_ancestors = ROOT_ANCESTORS
            if new_parent_id is not None:
                if new_parent_id == dept_id:
                    raise OrgDeptCycleError("移动形成环：父部门不能是自身")
                parent = await self._depts.get(new_parent_id)
                if parent is None:
                    raise OrgDeptNotFoundError(f"部门不存在：{new_parent_id}")
                if parent.status != STATUS_ENABLED:
                    raise OrgDeptParentUnavailableError(f"父部门已停用：{new_parent_id}")
                # 新父的 ancestors 若以自身子树前缀开头，则该父是自身后代 → 成环
                if parent.ancestors.startswith(_subtree_prefix(dept)):
                    raise OrgDeptCycleError("移动形成环：父部门不能是自身或其后代")
                new_parent_ancestors = _subtree_prefix(parent)

            old_prefix = _subtree_prefix(dept)
            new_prefix = f"{new_parent_ancestors}{dept.id}/"
            descendants = await self._depts.list_subtree(prefix=old_prefix)
            max_depth = await org_config.read_int(
                self._config, org_config.DEPT_TREE_MAX_DEPTH_KEY, org_config.DEFAULT_DEPT_TREE_MAX_DEPTH
            )
            deepest = max(
                (child.ancestors.count("/") - old_prefix.count("/") for child in descendants),
                default=0,
            )
            if new_parent_ancestors.count("/") + deepest + 1 > max_depth:
                raise OrgDeptDepthExceededError(f"移动后子树深度超上限：{max_depth}")

            dept.parent_id = new_parent_id
            dept.ancestors = new_parent_ancestors
            await self._depts.flush()
            for child in descendants:
                child.ancestors = new_prefix + child.ancestors[len(old_prefix) :]
            await self._depts.flush()
            await self._publish(dept.id, CHANGE_MOVED)
        return dept

    async def delete_dept(self, *, dept_id: int, actor: int | None = None) -> None:
        """删除部门（引用检查通过后软删除；同事务校验 + 删除）。

        Args:
            dept_id: 部门 id。
            actor: 操作者（审计占位用）。

        Raises:
            OrgDeptNotFoundError: 部门不存在（330051）。
            OrgDeptHasChildrenError: 仍存在子部门（330054）。
            OrgDeptReferencedError: 仍被岗位 / 用户引用（330055）。
            OrgDeptHasRolesError: 仍存在角色分配（330056）。
        """
        del actor
        async with self._uow.begin():
            dept = await self.require_dept(dept_id)
            if await self._depts.count_children(dept_id) > 0:
                raise OrgDeptHasChildrenError(f"部门仍存在子部门，禁止删除：{dept_id}")
            if await self._posts.count_by_dept(dept_id) > 0:
                raise OrgDeptReferencedError(f"部门仍被岗位引用，禁止删除：{dept_id}")
            if await self._role_depts.count_by_dept(dept_id) > 0:
                raise OrgDeptHasRolesError(f"部门仍存在角色分配，禁止删除：{dept_id}")
            await self._depts.soft_delete(dept_id)
            await self._publish(dept.id, CHANGE_DELETED)

    async def _publish(self, dept_id: int, changed_type: str) -> None:
        """发布部门变更事件（同事务写发件箱）。

        Args:
            dept_id: 部门 id。
            changed_type: 变更类型。
        """
        await self._outbox.enqueue(
            self._session,
            EventEnvelope(
                event_type=DEPT_CHANGED_EVENT,
                payload=ConcurrentStableDict({"dept_id": str(dept_id), "changed_type": changed_type}),
                tenant_id=current_tenant_id_str(),
                aggregate_key=f"org.dept:{dept_id}",
            ),
        )


def _subtree_prefix(dept: OrgDept) -> str:
    """取子树前缀（`{ancestors}{id}/`）。

    Args:
        dept: 部门记录。

    Returns:
        str: 子树前缀。
    """
    return f"{dept.ancestors}{dept.id}/"


def _subtree_ids(root: OrgDept, descendants: ConcurrentStableList[OrgDept]) -> ConcurrentStableList[int]:
    """取「自身 + 后代」部门 id 列表（插入序）。

    Args:
        root: 根部门。
        descendants: 后代部门。

    Returns:
        ConcurrentStableList[int]: 部门 id（自身在前）。
    """
    ids: ConcurrentStableList[int] = ConcurrentStableList([root.id])
    ids.update(child.id for child in descendants)
    return ids


def _guard_version(current: int, expected: int | None) -> None:
    """乐观锁比对（`expected` 提供且不等即抛统一并发冲突）。

    Args:
        current: 当前版本。
        expected: 客户端版本；None 跳过比对。

    Raises:
        ConcurrentConflictError: 版本不一致（可重试）。
    """
    if expected is not None and expected != current:
        raise ConcurrentConflictError(f"乐观锁冲突：期望版本 {expected}，当前版本 {current}")


def _build_tree(rows: ConcurrentStableList[OrgDept]) -> ConcurrentStableList[DeptTreeNode]:
    """由扁平部门列表构建树（父不在集合内者视为根节点）。

    Args:
        rows: 部门列表（已按 sort / id 排序）。

    Returns:
        ConcurrentStableList[DeptTreeNode]: 根节点列表。
    """
    nodes: ConcurrentStableDict[int, DeptTreeNode] = ConcurrentStableDict()
    order: ConcurrentStableList[int] = ConcurrentStableList()
    for row in rows:
        nodes.set(
            row.id,
            DeptTreeNode(
                id=row.id,
                parent_id=row.parent_id,
                name=row.name,
                ancestors=row.ancestors,
                sort=row.sort,
                status=row.status,
            ),
        )
        order.add(row.id)
    roots: ConcurrentStableList[DeptTreeNode] = ConcurrentStableList()
    for dept_id in order:
        node = nodes.get(dept_id)
        if node is None:
            continue
        parent = nodes.get(node.parent_id) if node.parent_id is not None else None
        if parent is None:
            roots.add(node)
        else:
            parent.children.add(node)
    return roots
