"""组织只读出口真实取数实现：承接本域仓储（部门 / 岗位 / 用户-岗位）+ 用户来源端口。

- `DbOrgDataSource`：`posts` / `dept_tree` 取**本域库**（`org_post` / `org_dept`）；`users` 取**用户来源
  端口**（平台用户只读出口）。部门过滤（`dept_id` / `include_children`）按部门祖先链展开子树；
  **`users` 的部门过滤为过渡口径**——映射为「该部门（含子树）下的岗位、且用户已分配该岗位」的候选
  用户集合，再交由用户来源在集合内筛选（`sys_user.dept_id` 落地后切换为平台字段过滤）。
- `DbOrgNameResolver`：`post` / `dept` 取本域库、`user` 取用户来源；单批 IN 查询，避免 N+1；
  未命中 id 在结果中占位（`exists=False` / `status=disabled`）。
- **数据范围强制接入**：`dept_scope` 由装配侧（依赖提供者）读取基座 `DataScope.read_predicate()` 后注入，
  本实现按之限定部门范围（`None` = 不限）；调用方无法绕过（本类是唯一实现入口）。
"""

from bms_core.config.base import BaseConfigSource
from bms_core.core.concurrent import ConcurrentStableDict, ConcurrentStableList, ConcurrentStableSet
from bms_core.core.exceptions import ParamError
from bms_core.schemas.pagination import BasePageQuery, BasePageResponse

from mdm_org import config as org_config
from mdm_org.models.dept import OrgDept as OrgDeptModel
from mdm_org.models.post import OrgPost as OrgPostModel
from mdm_org.org.base import (
    DEFAULT_ORG_PAGE_SIZE,
    ORG_TARGETS,
    BaseOrgDataSource,
    BaseOrgNameResolver,
    BaseOrgUserSource,
    OrgDept,
    OrgNameRef,
    OrgPost,
    OrgUser,
)
from mdm_org.repositories.dept import DeptRepository
from mdm_org.repositories.post import PostRepository
from mdm_org.repositories.user_post import UserPostRepository

SUBTREE_SUFFIX = "/"
"""子树前缀尾字符（`ancestors` 链以 `/` 连接）。"""


class DbOrgDataSource(BaseOrgDataSource):
    """组织数据源真实实现（本域库 + 用户来源端口）。"""

    def __init__(
        self,
        *,
        depts: DeptRepository,
        posts: PostRepository,
        user_posts: UserPostRepository,
        users: BaseOrgUserSource,
        config: BaseConfigSource,
        dept_scope: ConcurrentStableList[int] | None = None,
    ) -> None:
        """初始化。

        Args:
            depts: 部门仓储。
            posts: 岗位仓储。
            user_posts: 用户-岗位关联仓储（部门过滤候选用户派生）。
            users: 用户来源端口（平台用户只读出口）。
            config: 系统参数取数（候选集上限等）。
            dept_scope: 数据范围限定的部门 id（None = 不限定）。
        """
        self._depts = depts
        self._posts = posts
        self._user_posts = user_posts
        self._users = users
        self._config = config
        self._scope = dept_scope
        self._scope_set: ConcurrentStableSet[int] | None = (
            None if dept_scope is None else ConcurrentStableSet(dept_scope)
        )

    async def users(
        self,
        keyword: str | None = None,
        *,
        dept_id: int | None = None,
        include_children: bool = False,
        status: str | None = None,
        page: int = 1,
        size: int = DEFAULT_ORG_PAGE_SIZE,
    ) -> BasePageResponse[OrgUser]:
        """查询用户（经用户来源端口；部门过滤为过渡口径，见模块说明）。

        Args:
            keyword: 关键字；None 不过滤。
            dept_id: 部门 id；None 不过滤。
            include_children: 部门过滤是否含下级。
            status: 状态过滤；None 不过滤。
            page: 页码（从 1 起）。
            size: 每页条数。

        Returns:
            BasePageResponse[OrgUser]: 分页用户。

        Raises:
            OrgSourceUnavailableError: 用户来源不可达 / 未装配（330101）。
            ParamError: 部门过滤命中用户数超上限（10001）。
        """
        candidate = await self._filter_user_ids(dept_id=dept_id, include_children=include_children)
        if candidate is not None:
            await self._guard_filter_size(candidate)
            if not candidate:
                return BasePageResponse[OrgUser](list=ConcurrentStableList(), total=0, page=page, size=size)
        return await self._users.query(keyword, status=status, ids=candidate, page=page, size=size)

    async def posts(
        self,
        keyword: str | None = None,
        *,
        dept_id: int | None = None,
        include_children: bool = False,
        status: str | None = None,
        page: int = 1,
        size: int = DEFAULT_ORG_PAGE_SIZE,
    ) -> BasePageResponse[OrgPost]:
        """查询岗位（本域库；部门过滤含子级与数据范围限定）。

        Args:
            keyword: 关键字（岗位码 / 名称）；None 不过滤。
            dept_id: 部门 id；None 不过滤。
            include_children: 部门过滤是否含下级。
            status: 状态过滤；None 不过滤。
            page: 页码（从 1 起）。
            size: 每页条数。

        Returns:
            BasePageResponse[OrgPost]: 分页岗位。
        """
        dept_ids = await self._filter_dept_ids(dept_id=dept_id, include_children=include_children)
        if dept_ids is not None and not dept_ids:
            return BasePageResponse[OrgPost](list=ConcurrentStableList(), total=0, page=page, size=size)
        query = BasePageQuery(page=page, size=size)
        rows = await self._posts.list_filtered(query, dept_ids=dept_ids, status=status, keyword=keyword)
        total = await self._posts.count_filtered(dept_ids=dept_ids, status=status, keyword=keyword)
        return BasePageResponse[OrgPost](
            list=ConcurrentStableList(_post(row) for row in rows),
            total=total,
            page=page,
            size=size,
        )

    async def dept_tree(self, *, status: str | None = None) -> ConcurrentStableList[OrgDept]:
        """取部门树（一次性返回、不分页；数据范围限定外的部门不入树）。

        Args:
            status: 状态过滤；None 不过滤。

        Returns:
            ConcurrentStableList[OrgDept]: 部门树根节点序列（`children` 嵌套）。
        """
        rows = await self._depts.list_all(status=status)
        scoped = ConcurrentStableList(row for row in rows if self._in_scope(row.id))
        return _build_tree(scoped)

    def _in_scope(self, dept_id: int) -> bool:
        """判断部门是否在数据范围内（未限定恒为真）。

        Args:
            dept_id: 部门 id。

        Returns:
            bool: 在范围内 True。
        """
        return self._scope_set is None or dept_id in self._scope_set

    async def _filter_dept_ids(
        self, *, dept_id: int | None, include_children: bool
    ) -> ConcurrentStableList[int] | None:
        """解析生效的部门 id 集合（部门过滤 ∩ 数据范围）；None 表示不限定。

        Args:
            dept_id: 部门 id；None 表示只按数据范围限定。
            include_children: 是否含子树。

        Returns:
            ConcurrentStableList[int] | None: 生效部门集合；None = 不限定。
        """
        scope = None if self._scope is None else ConcurrentStableList(self._scope)
        if dept_id is None:
            return scope
        ids = await self._dept_subtree_ids(dept_id, include_children=include_children)
        if scope is None:
            return ids
        return ConcurrentStableList(item for item in ids if self._in_scope(item))

    async def _dept_subtree_ids(self, dept_id: int, *, include_children: bool) -> ConcurrentStableList[int]:
        """取部门（按需含子树）id 集合；部门不存在返回空集。

        Args:
            dept_id: 部门 id。
            include_children: 是否含子树。

        Returns:
            ConcurrentStableList[int]: 部门 id 集合（自身在前）。
        """
        dept = await self._depts.get(dept_id)
        if dept is None:
            return ConcurrentStableList()
        ids: ConcurrentStableList[int] = ConcurrentStableList([dept.id])
        if include_children:
            prefix = f"{dept.ancestors}{dept.id}{SUBTREE_SUFFIX}"
            ids.update(child.id for child in await self._depts.list_subtree(prefix=prefix))
        return ids

    async def _filter_user_ids(
        self, *, dept_id: int | None, include_children: bool
    ) -> ConcurrentStableList[int] | None:
        """按「岗位归属部门」派生候选用户集合；None 表示不限定。

        Args:
            dept_id: 部门 id；None 表示只按数据范围限定。
            include_children: 是否含子树。

        Returns:
            ConcurrentStableList[int] | None: 候选用户 id（去重、插入序）；None = 不限定。
        """
        dept_ids = await self._filter_dept_ids(dept_id=dept_id, include_children=include_children)
        if dept_ids is None:
            return None
        post_ids = ConcurrentStableList(post.id for post in await self._posts.list_by_depts(dept_ids))
        user_ids: ConcurrentStableList[int] = ConcurrentStableList()
        for link in await self._user_posts.list_by_posts(post_ids):
            if link.user_id not in user_ids:
                user_ids.add(link.user_id)
        return user_ids

    async def _guard_filter_size(self, user_ids: ConcurrentStableList[int]) -> None:
        """候选用户集规模上限校验（超限提示改用关键字检索）。

        Args:
            user_ids: 候选用户集合。

        Raises:
            ParamError: 命中用户数超上限（10001）。
        """
        limit = await org_config.read_int(
            self._config,
            org_config.DATA_SOURCE_MAX_FILTER_IDS_KEY,
            org_config.DEFAULT_DATA_SOURCE_MAX_FILTER_IDS,
        )
        if len(user_ids) > limit:
            raise ParamError(f"部门过滤命中用户过多（{len(user_ids)} 超出上限 {limit}），请改用关键字检索")


class DbOrgNameResolver(BaseOrgNameResolver):
    """名称回显真实实现（岗位 / 部门取本域库、用户取用户来源端口）。"""

    def __init__(
        self,
        *,
        depts: DeptRepository,
        posts: PostRepository,
        users: BaseOrgUserSource,
    ) -> None:
        """初始化。

        Args:
            depts: 部门仓储。
            posts: 岗位仓储。
            users: 用户来源端口。
        """
        self._depts = depts
        self._posts = posts
        self._users = users

    async def resolve_names(self, target: str, ids: ConcurrentStableList[int]) -> ConcurrentStableList[OrgNameRef]:
        """按 id 批量回显名称（保持请求插入序；未命中占位）。

        Args:
            target: 目标类型（`ORG_TARGETS` 之一）。
            ids: 对象 ID 序列。

        Returns:
            ConcurrentStableList[OrgNameRef]: 回显项。

        Raises:
            ParamError: 目标类型非法（10001）。
            OrgSourceUnavailableError: 用户来源不可达 / 未装配（330101，仅 `user` 目标）。
        """
        _guard_target(target)
        found: ConcurrentStableDict[int, OrgNameRef] = ConcurrentStableDict()
        if target == "user":
            for user in await self._users.by_ids(ids):
                found.set(
                    user.id,
                    OrgNameRef(
                        id=user.id,
                        name=user.nickname or user.username,
                        target=target,
                        exists=True,
                        status=user.status,
                    ),
                )
        elif target == "post":
            for post in await self._posts.list_by_ids(ids):
                found.set(
                    post.id,
                    OrgNameRef(id=post.id, name=post.name, target=target, exists=True, status=post.status),
                )
        else:
            for dept in await self._depts.list_by_ids(ids):
                found.set(
                    dept.id,
                    OrgNameRef(id=dept.id, name=dept.name, target=target, exists=True, status=dept.status),
                )
        return ConcurrentStableList(_ref(item, target, found.get(item)) for item in ids)


def _guard_target(target: str) -> None:
    """回显目标合法性校验。

    Args:
        target: 目标类型。

    Raises:
        ParamError: 不在 `ORG_TARGETS` 内（10001）。
    """
    if target not in ORG_TARGETS:
        raise ParamError(f"回显目标非法：{target!r}")


def _ref(item: int, target: str, found: OrgNameRef | None) -> OrgNameRef:
    """构造单个回显项（未命中占位：不存在 + 不可用状态，前端回退展示 id）。

    Args:
        item: 请求的 id。
        target: 目标类型。
        found: 命中的回显项；None 表示未命中。

    Returns:
        OrgNameRef: 回显项。
    """
    if found is not None:
        return found
    return OrgNameRef(id=item, name="", target=target, exists=False, status="disabled")


def _post(row: OrgPostModel) -> OrgPost:
    """岗位记录 → 出口契约实体。

    Args:
        row: 岗位记录。

    Returns:
        OrgPost: 出口契约实体。
    """
    return OrgPost(
        id=row.id,
        code=row.code,
        name=row.name,
        dept_id=row.dept_id,
        status=row.status,
        sort=row.sort,
    )


def _node(row: OrgDeptModel) -> OrgDept:
    """部门记录 → 出口契约节点（子节点后续装配）。

    Args:
        row: 部门记录。

    Returns:
        OrgDept: 出口契约节点。
    """
    return OrgDept(
        id=row.id,
        parent_id=row.parent_id,
        code=row.code,
        name=row.name,
        sort=row.sort,
        status=row.status,
    )


def _build_tree(rows: ConcurrentStableList[OrgDeptModel]) -> ConcurrentStableList[OrgDept]:
    """由扁平部门列表构建出口部门树（父不在集合内者视为根节点）。

    Args:
        rows: 部门记录（已按 `sort` / `id` 排序）。

    Returns:
        ConcurrentStableList[OrgDept]: 根节点序列（子节点嵌套）。
    """
    nodes: ConcurrentStableDict[int, OrgDept] = ConcurrentStableDict()
    order: ConcurrentStableList[int] = ConcurrentStableList()
    for row in rows:
        nodes.set(row.id, _node(row))
        order.add(row.id)
    roots: ConcurrentStableList[OrgDept] = ConcurrentStableList()
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


__all__ = ["DbOrgDataSource", "DbOrgNameResolver"]
