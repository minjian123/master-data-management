"""组织域用例支持：内存 SQLite + 请求级会话 + 仓储 / 服务装配（照 bms platform 测试范式）。

置于 `tests_support`（工作区与工程级两套 pytest 上下文均可导入：两处 `pythonpath` 均含 `backend/`）。
"""

from typing import cast

from bms_core.config.base import BaseConfigSource
from bms_core.config.null import NullConfigSource
from bms_core.core.concurrent import ConcurrentStableDict, ConcurrentStableList
from bms_core.db.migration import import_models
from bms_core.db.unit_of_work import DbUnitOfWork
from bms_core.events.contracts import EVENT_CONTRACT_MODE_ENFORCE, default_event_contract_registry
from bms_core.models.base import Base
from bms_core.outbox.store import SqlOutboxStore
from bms_core.services.table_registry import chain_tables
from sqlalchemy import Table
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from mdm_org.events import register_product_event_contracts
from mdm_org.repositories.dept import DeptRepository
from mdm_org.repositories.post import PostRepository
from mdm_org.repositories.role_dept import RoleDeptRepository
from mdm_org.repositories.role_post import RolePostRepository
from mdm_org.repositories.user_post import UserPostRepository
from mdm_org.services.dept import DeptService
from mdm_org.services.post import PostService
from mdm_org.services.role_dept import RoleDeptService
from mdm_org.services.role_post import RolePostService
from mdm_org.services.user_post import UserPostService
from services.table_registry import register as register_product_tables

DEPT_TREE_MAX_DEPTH_KEY = "org.dept_tree_max_depth"
"""部门树最大深度参数键。"""

DEPT_MAX_CHILDREN_KEY = "org.dept_max_children"
"""同级子部门数上限参数键。"""

POST_CODE_PATTERN_KEY = "org.post_code_pattern"
"""岗位码格式参数键。"""

POST_MAX_PER_USER_KEY = "org.post_max_per_user"
"""单用户岗位数上限参数键。"""


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
    max_per_user: int | None = None,
) -> BaseConfigSource:
    """构造系统参数替身（未给项走代码默认值）。

    Args:
        max_depth: 部门树最大深度。
        max_children: 同级子部门数上限。
        post_pattern: 岗位码格式。
        max_per_user: 单用户岗位数上限。

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
    if max_per_user is not None:
        values.set(POST_MAX_PER_USER_KEY, str(max_per_user))
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


def ids(*values: int) -> ConcurrentStableList[int]:
    """构造整数 id 清单（契约集合形态）。

    Args:
        *values: id 值。

    Returns:
        ConcurrentStableList[int]: id 清单。
    """
    return ConcurrentStableList(values)
