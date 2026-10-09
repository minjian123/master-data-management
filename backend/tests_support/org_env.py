"""组织域用例支持：内存 SQLite + 请求级会话 + 仓储 / 服务装配（照 bms platform 测试范式）。

置于 `tests_support`（工作区与工程级两套 pytest 上下文均可导入：两处 `pythonpath` 均含 `backend/`）。
"""

import json
from collections.abc import Iterable
from typing import cast

from bms_core.cache.memory import MemoryCacheRegion
from bms_core.config.base import BaseConfigSource
from bms_core.config.null import NullConfigSource
from bms_core.core.concurrent import ConcurrentStableDict, ConcurrentStableList, ConcurrentStableSet
from bms_core.core.serialization import normalize_collections
from bms_core.db.migration import import_models
from bms_core.db.unit_of_work import DbUnitOfWork
from bms_core.events.contracts import EVENT_CONTRACT_MODE_ENFORCE, default_event_contract_registry
from bms_core.models.base import Base
from bms_core.outbox.store import SqlOutboxStore
from bms_core.schemas.pagination import BasePageResponse
from bms_core.servicecall.base import BaseServiceClient, ServiceRequest, ServiceResponse
from bms_core.services.table_registry import chain_tables
from sqlalchemy import Table
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from mdm_org.errors import OrgSourceUnavailableError
from mdm_org.events import register_product_event_contracts
from mdm_org.org.base import DEFAULT_ORG_PAGE_SIZE, BaseOrgUserSource, OrgUser
from mdm_org.org.default import DbOrgDataSource, DbOrgNameResolver
from mdm_org.repositories.dept import DeptRepository
from mdm_org.repositories.post import PostRepository
from mdm_org.repositories.role_dept import RoleDeptRepository
from mdm_org.repositories.role_post import RolePostRepository
from mdm_org.repositories.user_dept import UserDeptRepository
from mdm_org.repositories.user_post import UserPostRepository
from mdm_org.services.dept import DeptService
from mdm_org.services.open_read import OpenReadService
from mdm_org.services.post import PostService
from mdm_org.services.role_dept import RoleDeptService
from mdm_org.services.role_post import RolePostService
from mdm_org.services.user_dept import UserDeptService
from mdm_org.services.user_post import UserPostService
from services.table_registry import register as register_product_tables

DEPT_TREE_MAX_DEPTH_KEY = "org.dept_tree_max_depth"
"""部门树最大深度参数键。"""

DEPT_MAX_CHILDREN_KEY = "org.dept_max_children"
DEPT_MAX_PER_USER_KEY = "org.dept_max_per_user"
"""同级子部门数上限参数键。"""

POST_CODE_PATTERN_KEY = "org.post_code_pattern"
DEPT_CODE_PATTERN_KEY = "org.dept_code_pattern"
"""岗位码格式参数键。"""

POST_MAX_PER_USER_KEY = "org.post_max_per_user"
"""单用户岗位数上限参数键。"""

DATA_SOURCE_MAX_FILTER_IDS_KEY = "org.data_source_max_filter_ids"
"""组织只读出口部门过滤候选集上限参数键。"""

USER_ROLES_CACHE_TTL_KEY = "org.user_roles_cache_ttl"
"""按用户解析角色结果缓存 TTL 参数键。"""


class ConfigStub(BaseConfigSource):
    """系统参数替身：按给定映射返回（缺失键不出现，调用方回落代码默认值）。"""

    def __init__(self, values: ConcurrentStableDict[str, str] | None = None) -> None:
        """初始化。

        Args:
            values: 参数键 → 值；None 取空映射。
        """
        self._values: ConcurrentStableDict[str, str] = values if values is not None else ConcurrentStableDict()

    async def get_many(self, keys: ConcurrentStableList[str]) -> ConcurrentStableDict[str, str]:
        """批量取参数（只返回存在的键）。

        Args:
            keys: 参数键序列。

        Returns:
            ConcurrentStableDict[str, str]: 命中键 → 值。
        """
        return ConcurrentStableDict({key: self._values[key] for key in keys if key in self._values})


class StubUserSource(BaseOrgUserSource):
    """用户来源替身：内存用户表（关键字 / 状态 / 限定集合筛选 + 分页）；记录调用次数。"""

    def __init__(self, users: ConcurrentStableList[OrgUser] | None = None) -> None:
        """初始化。

        Args:
            users: 内存用户表；None 取空。
        """
        self.users: ConcurrentStableList[OrgUser] = users if users is not None else ConcurrentStableList()
        self.query_calls = 0
        self.by_ids_calls = 0

    async def query(
        self,
        keyword: str | None = None,
        *,
        status: str | None = None,
        ids: ConcurrentStableList[int] | None = None,
        page: int = 1,
        size: int = DEFAULT_ORG_PAGE_SIZE,
    ) -> BasePageResponse[OrgUser]:
        """查询用户（内存筛选 + 切片分页）。

        Args:
            keyword: 关键字；None 不过滤。
            status: 状态过滤；None 不过滤。
            ids: 限定集合；None 不限定。
            page: 页码。
            size: 每页条数。

        Returns:
            BasePageResponse[OrgUser]: 分页用户。
        """
        self.query_calls += 1
        rows = ConcurrentStableList(
            item for item in self.users if _match_user(item, keyword=keyword, status=status, ids=_id_set(ids))
        )
        start = (page - 1) * size
        window: ConcurrentStableList[OrgUser] = ConcurrentStableList()
        for index, item in enumerate(rows):
            if start <= index < start + size:
                window.add(item)
        return BasePageResponse[OrgUser](list=window, total=len(rows), page=page, size=size)

    async def by_ids(self, ids: ConcurrentStableList[int]) -> ConcurrentStableList[OrgUser]:
        """按主键集合批量取用户（保持内存表顺序）。

        Args:
            ids: 用户主键序列。

        Returns:
            ConcurrentStableList[OrgUser]: 用户序列。
        """
        self.by_ids_calls += 1
        wanted = ConcurrentStableSet(ids)
        return ConcurrentStableList(item for item in self.users if item.id in wanted)


class UnavailableUserSource(BaseOrgUserSource):
    """用户来源替身：任何取数即抛 330101（模拟平台用户只读出口不可达 / 未装配）。"""

    async def query(
        self,
        keyword: str | None = None,
        *,
        status: str | None = None,
        ids: ConcurrentStableList[int] | None = None,
        page: int = 1,
        size: int = DEFAULT_ORG_PAGE_SIZE,
    ) -> BasePageResponse[OrgUser]:
        """查询用户（恒失败）。

        Args:
            keyword: 关键字（忽略）。
            status: 状态过滤（忽略）。
            ids: 限定集合（忽略）。
            page: 页码（忽略）。
            size: 每页条数（忽略）。

        Raises:
            OrgSourceUnavailableError: 恒抛（330101）。
        """
        del keyword, status, ids, page, size
        raise OrgSourceUnavailableError("用户来源不可用（替身）")

    async def by_ids(self, ids: ConcurrentStableList[int]) -> ConcurrentStableList[OrgUser]:
        """按主键集合批量取用户（恒失败）。

        Args:
            ids: 用户主键序列（忽略）。

        Raises:
            OrgSourceUnavailableError: 恒抛（330101）。
        """
        del ids
        raise OrgSourceUnavailableError("用户来源不可用（替身）")


class StubPlatformClient(BaseServiceClient):
    """服务间调用替身：按平台用户只读出口契约生成统一响应（供 `PlatformOrgUserSource` 解析链路覆盖）。

    `status_code` / `code` 可注入以覆盖「非 2xx」「业务失败」「返回契约非法」等降级分支。
    """

    plugin_name: str = "stub"

    def __init__(
        self,
        users: ConcurrentStableList[OrgUser] | None = None,
        *,
        status_code: int = 200,
        code: int = 0,
        payload: object | None = None,
    ) -> None:
        """初始化。

        Args:
            users: 内存用户表（按请求体筛选页）。
            status_code: 响应状态码。
            code: 统一响应业务码。
            payload: 直接给定的响应体（None 时按用户表生成）。
        """
        self.users: ConcurrentStableList[OrgUser] = users if users is not None else ConcurrentStableList()
        self.status_code = status_code
        self.code = code
        self.payload = payload
        self.requests: ConcurrentStableList[ServiceRequest] = ConcurrentStableList()

    async def call(self, request: ServiceRequest) -> ServiceResponse:
        """生成统一响应（不真联）。

        Args:
            request: 调用请求（读其 `json_body` 的关键字 / 状态 / 限定集合 / 分页）。

        Returns:
            ServiceResponse: 统一响应。
        """
        self.requests.add(request)
        body = cast("ConcurrentStableDict[str, object]", request.json_body)
        keyword = body.get("keyword")
        status = body.get("status")
        page = body.get("page") if isinstance(body.get("page"), int) else 1
        size = body.get("size") if isinstance(body.get("size"), int) else DEFAULT_ORG_PAGE_SIZE
        ids = body.get("ids")
        rows = ConcurrentStableList(
            item for item in self.users if _match_user(item, keyword=keyword, status=status, ids=_id_set(ids))
        )
        start = (page - 1) * size
        window: ConcurrentStableList[OrgUser] = ConcurrentStableList()
        for index, item in enumerate(rows):
            if start <= index < start + size:
                window.add(item)
        content = self.payload
        if content is None:
            content = ConcurrentStableDict(
                {
                    "code": self.code,
                    "message": "",
                    "data": ConcurrentStableDict(
                        {
                            "list": ConcurrentStableList(_internal_row(item) for item in window),
                            "total": len(rows),
                            "page": page,
                            "size": size,
                        }
                    ),
                }
            )
        return ServiceResponse(
            status_code=self.status_code,
            headers=ConcurrentStableDict(),
            content=json.dumps(normalize_collections(content), ensure_ascii=False).encode("utf-8"),
        )


def _internal_row(user: OrgUser) -> ConcurrentStableDict[str, object]:
    """构造平台用户只读行（字段名与平台内部契约一致：`name` 为显示名）。

    Args:
        user: 用户实体。

    Returns:
        ConcurrentStableDict[str, object]: 只读行。
    """
    return ConcurrentStableDict(
        {
            "id": user.id,
            "username": user.username,
            "name": user.nickname,
            "status": user.status,
            "phone": user.phone,
            "email": user.email,
        }
    )


def _id_set(value: object) -> ConcurrentStableSet[int] | None:
    """把请求体 `ids` 值规整为整数集合（None / 非可迭代返回 None）。

    Args:
        value: 原始值（可为基座集合类——`ConcurrentStableList` 是 `Sequence` 而**非** `list` 子类）。

    Returns:
        ConcurrentStableSet[int] | None: 整数集合；不限定返回 None。
    """
    if value is None or isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
        return None
    return ConcurrentStableSet(cast("Iterable[int]", value))


def _match_user(
    user: OrgUser,
    *,
    keyword: object,
    status: object,
    ids: ConcurrentStableSet[int] | None,
) -> bool:
    """用户是否命中筛选条件（限额集合 / 状态 / 关键字）。

    Args:
        user: 用户实体。
        keyword: 关键字（用户名 / 昵称，大小写不敏感）。
        status: 状态。
        ids: 限定集合。

    Returns:
        bool: 命中 True。
    """
    if ids is not None and user.id not in ids:
        return False
    if isinstance(status, str) and status and user.status != status:
        return False
    if isinstance(keyword, str) and keyword:
        needle = keyword.lower()
        if needle not in user.username.lower() and needle not in user.nickname.lower():
            return False
    return True


async def make_session() -> tuple[AsyncSession, AsyncEngine]:
    """建内存 SQLite 会话并创建 `org:tenant` 链表集（org 五表 + 基础设施三表）。

    Returns:
        tuple[AsyncSession, AsyncEngine]: （会话，引擎）。
    """
    # 内存库必须共享同一连接（`StaticPool`），否则每个会话拿到独立的空库
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    # 表归属产品注入（bms 12_04）：链表集派生依赖注入记录，故建表前先注册
    register_product_tables()
    import_models("org")
    names = sorted(chain_tables("org", "tenant"))
    tables = [cast("Table", Base.metadata.tables[name]) for name in names]
    async with engine.begin() as connection:
        await connection.run_sync(lambda conn: Base.metadata.create_all(conn, tables=tables))
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(engine, expire_on_commit=False)
    return factory(), engine


async def commit(session: AsyncSession) -> None:
    """结束当前读事务（服务调用前调用，避免与 `uow.begin()` 冲突）。

    Args:
        session: 请求级会话。
    """
    await session.commit()


def make_uow(session: AsyncSession) -> DbUnitOfWork:
    """构造请求级工作单元。

    Args:
        session: 请求级会话。

    Returns:
        DbUnitOfWork: 工作单元。
    """
    return DbUnitOfWork(session)


def make_outbox() -> SqlOutboxStore:
    """构造发件箱存储（契约校验 `enforce`，与运行期口径一致：未登记契约即拒发）。

    Returns:
        SqlOutboxStore: 发件箱存储。
    """
    register_product_event_contracts(default_event_contract_registry())
    registry = default_event_contract_registry()
    return SqlOutboxStore(contract_mode=EVENT_CONTRACT_MODE_ENFORCE, contract_resolver=registry.contract)


def make_config(
    *,
    max_depth: int | None = None,
    max_children: int | None = None,
    post_pattern: str | None = None,
    dept_pattern: str | None = None,
    max_per_user: int | None = None,
    dept_max_per_user: int | None = None,
    max_filter_ids: int | None = None,
    user_roles_ttl: int | None = None,
) -> BaseConfigSource:
    """构造系统参数替身（未给项走代码默认值）。

    Args:
        max_depth: 部门树最大深度。
        max_children: 同级子部门数上限。
        post_pattern: 岗位码格式。
        dept_pattern: 部门编码格式。
        max_per_user: 单用户岗位数上限。
        dept_max_per_user: 单用户部门数上限。
        max_filter_ids: 出口部门过滤候选集上限。
        user_roles_ttl: 按用户解析角色结果缓存 TTL（秒）。

    Returns:
        BaseConfigSource: 参数替身（无覆盖时返回 Null 实现）。
    """
    values: ConcurrentStableDict[str, str] = ConcurrentStableDict()
    if max_depth is not None:
        values.set(DEPT_TREE_MAX_DEPTH_KEY, str(max_depth))
    if max_children is not None:
        values.set(DEPT_MAX_CHILDREN_KEY, str(max_children))
    if post_pattern is not None:
        values.set(POST_CODE_PATTERN_KEY, post_pattern)
    if dept_pattern is not None:
        values.set(DEPT_CODE_PATTERN_KEY, dept_pattern)
    if max_per_user is not None:
        values.set(POST_MAX_PER_USER_KEY, str(max_per_user))
    if dept_max_per_user is not None:
        values.set(DEPT_MAX_PER_USER_KEY, str(dept_max_per_user))
    if max_filter_ids is not None:
        values.set(DATA_SOURCE_MAX_FILTER_IDS_KEY, str(max_filter_ids))
    if user_roles_ttl is not None:
        values.set(USER_ROLES_CACHE_TTL_KEY, str(user_roles_ttl))
    return ConfigStub(values) if values else NullConfigSource()


def make_dept_service(
    session: AsyncSession,
    uow: DbUnitOfWork,
    outbox: SqlOutboxStore,
    config: BaseConfigSource | None = None,
) -> DeptService:
    """装配部门服务。

    Args:
        session: 请求级会话。
        uow: 工作单元。
        outbox: 发件箱存储。
        config: 系统参数（缺省 Null）。

    Returns:
        DeptService: 服务实例。
    """
    return DeptService(
        DeptRepository(session),
        PostRepository(session),
        UserPostRepository(session),
        RoleDeptRepository(session),
        uow,
        config if config is not None else NullConfigSource(),
        outbox,
    )


def make_post_service(
    session: AsyncSession,
    uow: DbUnitOfWork,
    outbox: SqlOutboxStore,
    config: BaseConfigSource | None = None,
) -> PostService:
    """装配岗位服务。

    Args:
        session: 请求级会话。
        uow: 工作单元。
        outbox: 发件箱存储。
        config: 系统参数（缺省 Null）。

    Returns:
        PostService: 服务实例。
    """
    return PostService(
        PostRepository(session),
        DeptRepository(session),
        UserPostRepository(session),
        RolePostRepository(session),
        uow,
        config if config is not None else NullConfigSource(),
        outbox,
    )


def make_user_post_service(
    session: AsyncSession,
    uow: DbUnitOfWork,
    outbox: SqlOutboxStore,
    config: BaseConfigSource | None = None,
) -> UserPostService:
    """装配用户-岗位分配服务。

    Args:
        session: 请求级会话。
        uow: 工作单元。
        outbox: 发件箱存储。
        config: 系统参数（缺省 Null）。

    Returns:
        UserPostService: 服务实例。
    """
    return UserPostService(
        UserPostRepository(session),
        PostRepository(session),
        uow,
        config if config is not None else NullConfigSource(),
        outbox,
    )


def make_user_dept_service(
    session: AsyncSession,
    uow: DbUnitOfWork,
    outbox: SqlOutboxStore,
    config: BaseConfigSource | None = None,
) -> UserDeptService:
    """装配用户-部门分配服务。

    Args:
        session: 请求级会话。
        uow: 工作单元。
        outbox: 发件箱存储。
        config: 系统参数（缺省 Null）。

    Returns:
        UserDeptService: 服务实例。
    """
    return UserDeptService(
        UserDeptRepository(session),
        DeptRepository(session),
        uow,
        config if config is not None else NullConfigSource(),
        outbox,
    )


def make_role_post_service(session: AsyncSession, uow: DbUnitOfWork, outbox: SqlOutboxStore) -> RolePostService:
    """装配角色-岗位分配服务。

    Args:
        session: 请求级会话。
        uow: 工作单元。
        outbox: 发件箱存储。

    Returns:
        RolePostService: 服务实例。
    """
    return RolePostService(RolePostRepository(session), PostRepository(session), uow, outbox)


def make_role_dept_service(session: AsyncSession, uow: DbUnitOfWork, outbox: SqlOutboxStore) -> RoleDeptService:
    """装配角色-部门分配服务。

    Args:
        session: 请求级会话。
        uow: 工作单元。
        outbox: 发件箱存储。

    Returns:
        RoleDeptService: 服务实例。
    """
    return RoleDeptService(RoleDeptRepository(session), DeptRepository(session), uow, outbox)


async def seed_org_tree(session: AsyncSession) -> ConcurrentStableDict[str, int]:
    """造数：研发中心（含子部门平台组）+ 市场部，各挂岗位，并给三个用户分配岗位。

    用户：2001 → 开发主管（研发中心）；2002 → 开发工程师（平台组）；3001 → 销售（市场部）。

    Args:
        session: 请求级会话。

    Returns:
        ConcurrentStableDict[str, int]: 关键 id（root / child / other / lead / eng / sales）。
    """
    uow = make_uow(session)
    outbox = make_outbox()
    depts = make_dept_service(session, uow, outbox)
    posts = make_post_service(session, uow, outbox)
    user_posts = make_user_post_service(session, uow, outbox)
    root = await depts.create_dept(code="rd", name="研发中心", parent_id=None, sort=1)
    root_id = root.id
    child = await depts.create_dept(code="rd-platform", name="平台组", parent_id=root_id, sort=1)
    child_id = child.id
    other = await depts.create_dept(code="mkt", name="市场部", parent_id=None, sort=2)
    other_id = other.id
    await commit(session)
    lead = await posts.create_post(code="dev_lead", name="开发主管", dept_id=root_id, sort=1)
    lead_id = lead.id
    eng = await posts.create_post(code="dev", name="开发工程师", dept_id=child_id, sort=2)
    eng_id = eng.id
    sales = await posts.create_post(code="sales", name="销售", dept_id=other_id, sort=3)
    sales_id = sales.id
    await commit(session)
    await user_posts.assign_user_posts(user_id=2001, post_ids=ids(lead_id))
    await user_posts.assign_user_posts(user_id=2002, post_ids=ids(eng_id))
    await user_posts.assign_user_posts(user_id=3001, post_ids=ids(sales_id))
    await commit(session)
    return ConcurrentStableDict(
        {
            "root": root_id,
            "child": child_id,
            "other": other_id,
            "lead": lead_id,
            "eng": eng_id,
            "sales": sales_id,
        }
    )


def ids(*values: int) -> ConcurrentStableList[int]:
    """构造整数 id 清单（契约集合形态）。

    Args:
        *values: id 值。

    Returns:
        ConcurrentStableList[int]: id 清单。
    """
    return ConcurrentStableList(values)


def user(
    user_id: int,
    *,
    username: str | None = None,
    nickname: str = "",
    dept_id: int | None = None,
    status: str = "enabled",
    phone: str | None = None,
    email: str | None = None,
) -> OrgUser:
    """构造用户实体（出口契约形态；用户名缺省取 `u{id}`）。

    Args:
        user_id: 用户 id。
        username: 用户名；None 取 `u{id}`。
        nickname: 昵称。
        dept_id: 归属部门 id。
        status: 状态。
        phone: 手机号。
        email: 邮箱。

    Returns:
        OrgUser: 用户实体。
    """
    return OrgUser(
        id=user_id,
        username=username if username is not None else f"u{user_id}",
        nickname=nickname,
        dept_id=dept_id,
        status=status,
        phone=phone,
        email=email,
    )


def make_user_source(users: ConcurrentStableList[OrgUser] | None = None) -> StubUserSource:
    """装配用户来源替身。

    Args:
        users: 内存用户表；None 取空。

    Returns:
        StubUserSource: 替身实例。
    """
    return StubUserSource(users)


def make_cache(domain: str = "mdm_org") -> MemoryCacheRegion:
    """构造内存缓存域（用例级独立实例，避免跨用例串味）。

    Args:
        domain: 业务域简称。

    Returns:
        MemoryCacheRegion: 内存缓存域。
    """
    return MemoryCacheRegion(domain=domain)


def make_data_source(
    session: AsyncSession,
    *,
    user_source: BaseOrgUserSource | None = None,
    config: BaseConfigSource | None = None,
    dept_scope: ConcurrentStableList[int] | None = None,
) -> DbOrgDataSource:
    """装配组织数据源实现。

    Args:
        session: 请求级会话。
        user_source: 用户来源（缺省空表替身）。
        config: 系统参数（缺省 Null）。
        dept_scope: 数据范围限定部门 id（None = 不限定）。

    Returns:
        DbOrgDataSource: 数据源实现。
    """
    return DbOrgDataSource(
        depts=DeptRepository(session),
        posts=PostRepository(session),
        user_posts=UserPostRepository(session),
        users=user_source if user_source is not None else StubUserSource(),
        config=config if config is not None else NullConfigSource(),
        dept_scope=dept_scope,
    )


def make_resolver(session: AsyncSession, *, user_source: BaseOrgUserSource | None = None) -> DbOrgNameResolver:
    """装配名称回显实现。

    Args:
        session: 请求级会话。
        user_source: 用户来源（缺省空表替身）。

    Returns:
        DbOrgNameResolver: 回显实现。
    """
    return DbOrgNameResolver(
        depts=DeptRepository(session),
        posts=PostRepository(session),
        users=user_source if user_source is not None else StubUserSource(),
    )


def make_open_read_service(
    session: AsyncSession,
    *,
    user_source: BaseOrgUserSource | None = None,
    cache: MemoryCacheRegion | None = None,
    config: BaseConfigSource | None = None,
    dept_scope: ConcurrentStableList[int] | None = None,
) -> OpenReadService:
    """装配组织只读出口服务（数据源 / 回显 / 按用户解析角色）。

    Args:
        session: 请求级会话。
        user_source: 用户来源（缺省空表替身）。
        cache: 缓存域（缺省新建内存域）。
        config: 系统参数（缺省 Null）。
        dept_scope: 数据范围限定部门 id（None = 不限定）。

    Returns:
        OpenReadService: 出口服务实例。
    """
    source = user_source if user_source is not None else StubUserSource()
    return OpenReadService(
        data_source=make_data_source(session, user_source=source, config=config, dept_scope=dept_scope),
        resolver=make_resolver(session, user_source=source),
        user_depts=UserDeptRepository(session),
        user_posts=UserPostRepository(session),
        role_posts=RolePostRepository(session),
        role_depts=RoleDeptRepository(session),
        cache=cache if cache is not None else make_cache(),
        config=config if config is not None else NullConfigSource(),
    )
