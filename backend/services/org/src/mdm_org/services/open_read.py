"""组织只读出口服务：出口编排（数据源 / 名称回显 / 按用户解析角色）+ 结果缓存与失效代。

- 数据源与回显**只做编排**：真实取数在 `mdm_org/org/default.py`（数据范围由装配侧注入 `dept_scope`）；
- **按用户解析角色**：岗位链（`org_user_post` → `org_role_post`，本域库）∪ 部门链（**用户已分配部门**
  的全部（`org_user_dept`，**不按主要项过滤**）→ `org_role_dept` 精确匹配，**不含子树**）；并集去重、
  插入序稳定；**不返回用户直接角色**（`sys_user_role` 归 platform，由消费方合并）；
- **缓存**：结果按租户 + 用户短时缓存（TTL 经 `org.user_roles_cache_ttl`，≤0 即不缓存），缓存键内嵌
  **租户级失效代**；写侧（角色-岗位 / 角色-部门 / 用户-岗位 分配或解绑）经
  `bump_user_roles_generation` 推进失效代 → 旧键立即不可达、由 TTL 自然回收；
- **降级口径（2026-10-09 修订）**：部门链改取本域 `org_user_dept`（**不再经平台用户来源**），故按用户解析
  角色不再受平台可达性影响；出口其余面（数据源 `users` / 名称回显 `user`）在用户来源不可达时仍**整体
  fail-closed**（330101），不接受「少了数据」的部分结果。
"""

from collections.abc import Iterable, Mapping
from typing import cast

from bms_core.cache.base import CacheRegion
from bms_core.config.base import BaseConfigSource
from bms_core.core.concurrent import ConcurrentStableList
from bms_core.core.objects import BaseFrameworkObject
from bms_core.core.serialization import normalize_collections
from bms_core.db.tenant import current_tenant_id_str
from bms_core.schemas.pagination import BasePageResponse

from mdm_org import config as org_config
from mdm_org.org.base import (
    DEFAULT_ORG_PAGE_SIZE,
    BaseOrgDataSource,
    BaseOrgNameResolver,
    OrgDept,
    OrgNameRef,
    OrgPost,
    OrgUser,
)
from mdm_org.repositories.role_dept import RoleDeptRepository
from mdm_org.repositories.role_post import RolePostRepository
from mdm_org.repositories.user_dept import UserDeptRepository
from mdm_org.repositories.user_post import UserPostRepository

USER_ROLES_GEN_KEY = "org:user_roles:gen"
"""按用户解析角色缓存的**失效代**业务键（租户经 `CacheRegion.build_key` 拼入）。"""

USER_ROLES_KEY_PREFIX = "org:user_roles"
"""按用户解析角色缓存业务键前缀（其后接失效代与用户 id）。"""

ROLE_IDS_FIELD = "role_ids"
"""缓存载荷中的角色 id 字段名。"""


class OpenReadService(BaseFrameworkObject):
    """组织只读出口服务（数据源 / 回显 / 按用户解析角色）。"""

    def __init__(
        self,
        *,
        data_source: BaseOrgDataSource,
        resolver: BaseOrgNameResolver,
        user_depts: UserDeptRepository,
        user_posts: UserPostRepository,
        role_posts: RolePostRepository,
        role_depts: RoleDeptRepository,
        cache: CacheRegion,
        config: BaseConfigSource,
    ) -> None:
        """初始化。

        Args:
            data_source: 组织数据源（组织数据源三取数）。
            resolver: 名称回显。
            user_depts: 用户-部门关联仓储（部门链起点）。
            user_posts: 用户-岗位关联仓储（岗位链起点）。
            role_posts: 角色-岗位分配仓储（岗位链终点）。
            role_depts: 角色-部门分配仓储（部门链终点）。
            cache: 缓存域（结果缓存与失效代）。
            config: 系统参数取数（缓存 TTL 等）。
        """
        self._data_source = data_source
        self._resolver = resolver
        self._user_depts = user_depts
        self._user_posts = user_posts
        self._role_posts = role_posts
        self._role_depts = role_depts
        self._cache = cache
        self._config = config

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
        """组织数据源 · 用户查询。

        Args:
            keyword: 关键字；None 不过滤。
            dept_id: 部门 id；None 不过滤。
            include_children: 部门过滤是否含下级。
            status: 状态过滤；None 不过滤。
            page: 页码（从 1 起）。
            size: 每页条数。

        Returns:
            BasePageResponse[OrgUser]: 分页用户。
        """
        return await self._data_source.users(
            keyword,
            dept_id=dept_id,
            include_children=include_children,
            status=status,
            page=page,
            size=size,
        )

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
        """组织数据源 · 岗位查询。

        Args:
            keyword: 关键字；None 不过滤。
            dept_id: 部门 id；None 不过滤。
            include_children: 部门过滤是否含下级。
            status: 状态过滤；None 不过滤。
            page: 页码（从 1 起）。
            size: 每页条数。

        Returns:
            BasePageResponse[OrgPost]: 分页岗位。
        """
        return await self._data_source.posts(
            keyword,
            dept_id=dept_id,
            include_children=include_children,
            status=status,
            page=page,
            size=size,
        )

    async def dept_tree(self, *, status: str | None = None) -> ConcurrentStableList[OrgDept]:
        """组织数据源 · 部门树（一次性返回、不分页）。

        Args:
            status: 状态过滤；None 不过滤。

        Returns:
            ConcurrentStableList[OrgDept]: 部门树根节点序列。
        """
        return await self._data_source.dept_tree(status=status)

    async def resolve_names(self, target: str, ids: ConcurrentStableList[int]) -> ConcurrentStableList[OrgNameRef]:
        """名称回显（按 id 批量）。

        Args:
            target: 目标类型（`ORG_TARGETS` 之一）。
            ids: 对象 ID 序列。

        Returns:
            ConcurrentStableList[OrgNameRef]: 回显项。

        Raises:
            ParamError: 目标类型非法（10001）。
            OrgSourceUnavailableError: 用户来源不可达（330101，仅 `user` 目标）。
        """
        return await self._resolver.resolve_names(target, ids)

    async def user_roles(self, user_id: int) -> ConcurrentStableList[int]:
        """按用户解析其经岗位 / 部门获得的角色（并集去重；结果短时缓存）。

        Args:
            user_id: 用户 id。

        Returns:
            ConcurrentStableList[int]: 角色 id 集合（岗位链在前、部门链补入）。

        Raises:
            OrgSourceUnavailableError: 用户来源不可达 / 未装配（330101）。
        """
        ttl = await org_config.read_int(
            self._config,
            org_config.USER_ROLES_CACHE_TTL_KEY,
            org_config.DEFAULT_USER_ROLES_CACHE_TTL,
        )
        tenant = current_tenant_id_str()
        if ttl <= 0:
            return await self._resolve_user_roles(user_id)
        key = await self._cache_key(tenant, user_id)
        cached = _from_payload(await self._cache.aget(key))
        if cached is not None:
            return cached
        role_ids = await self._resolve_user_roles(user_id)
        await self._cache.aset(key, normalize_collections({ROLE_IDS_FIELD: tuple(role_ids)}), ttl)
        return role_ids

    async def _cache_key(self, tenant: str | None, user_id: int) -> str:
        """构造按用户解析角色的缓存键（含当前失效代）。

        Args:
            tenant: 租户主键字符串（可为空）。
            user_id: 用户 id。

        Returns:
            str: 缓存键。
        """
        generation = await self._generation(tenant)
        return self._cache.build_key(f"{USER_ROLES_KEY_PREFIX}:{generation}:{user_id}", tenant=tenant)

    async def _generation(self, tenant: str | None) -> int:
        """取当前失效代（读失败 / 未写入按 0）。

        Args:
            tenant: 租户主键字符串（可为空）。

        Returns:
            int: 失效代。
        """
        raw = await self._cache.aget(self._cache.build_key(USER_ROLES_GEN_KEY, tenant=tenant))
        return raw if isinstance(raw, int) else 0

    async def _resolve_user_roles(self, user_id: int) -> ConcurrentStableList[int]:
        """解析用户角色（岗位链 ∪ 部门链，并集去重）。

        Args:
            user_id: 用户 id。

        Returns:
            ConcurrentStableList[int]: 角色 id 集合。
        """
        role_ids: ConcurrentStableList[int] = ConcurrentStableList()
        post_ids = ConcurrentStableList(link.post_id for link in await self._user_posts.list_by_user(user_id))
        for link in await self._role_posts.list_by_posts(post_ids):
            if link.role_id not in role_ids:
                role_ids.add(link.role_id)
        dept_ids = ConcurrentStableList(link.dept_id for link in await self._user_depts.list_by_user(user_id))
        for dept_id in dept_ids:
            for link in await self._role_depts.list_by_dept(dept_id):
                if link.role_id not in role_ids:
                    role_ids.add(link.role_id)
        return role_ids


async def bump_user_roles_generation(cache: CacheRegion, tenant: str | None) -> None:
    """推进按用户解析角色缓存的失效代（**写侧失效**：同租户全量失效、旧键由 TTL 回收）。

    写侧（角色-岗位 / 角色-部门 / 用户-岗位 / 用户-部门 分配、解绑或主要项变更）成功后调用；粒度粗但正确性最好，
    且多副本经共享缓存（生产 Redis）一致。

    Args:
        cache: 缓存域。
        tenant: 租户主键字符串（可为空）。
    """
    await cache.aincrease(cache.build_key(USER_ROLES_GEN_KEY, tenant=tenant))


def _from_payload(payload: object) -> ConcurrentStableList[int] | None:
    """把缓存载荷还原为角色 id 集合（形态不符即按未命中）。

    Args:
        payload: 缓存载荷。

    Returns:
        ConcurrentStableList[int] | None: 角色 id 集合；无法识别返回 None。
    """
    if not isinstance(payload, Mapping):
        return None
    raw = cast("Mapping[str, object]", payload).get(ROLE_IDS_FIELD)
    if not isinstance(raw, (list, tuple)):
        return None
    role_ids: ConcurrentStableList[int] = ConcurrentStableList()
    for item in cast("Iterable[object]", raw):
        if not isinstance(item, int):
            return None
        role_ids.add(item)
    return role_ids


__all__ = [
    "ROLE_IDS_FIELD",
    "USER_ROLES_GEN_KEY",
    "USER_ROLES_KEY_PREFIX",
    "OpenReadService",
    "bump_user_roles_generation",
]
