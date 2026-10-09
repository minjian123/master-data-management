"""组织域 **XA 分支处理器**（跨服务强一致参与方；嵌套子任务 `_03` 第 7 条）。

把分支 `op` 映射到本域**已有服务层方法**（**不复制业务逻辑**），由基座分支执行器在
**已开启的两阶段分支事务**的连接上调用：

- 执行器传入的 `session` 是绑定该分支连接的会话（`SyncSession(bind=connection)`，
  `join_transaction_mode="create_savepoint"`）⇒ 服务层 `UnitOfWork.begin()` 收敛为 **SAVEPOINT**，
  外层 XA 分支保持打开、仍可 `prepare`；**不回滚外层分支、也不另开事务**。
- 参数解包失败一律 `ParamError`（`330010`，参数错误）——分支载荷由调用方（编排）生成，非法即拒。
- 强一致启用后**恢复原语＝幂等重放**（TM 重驱动分支）；**禁止手工改数据**。
"""

from typing import TYPE_CHECKING, cast

from bms_core.config.base import BaseConfigSource
from bms_core.core.concurrent import ConcurrentStableDict, ConcurrentStableList
from bms_core.core.config import Settings
from bms_core.core.exceptions import ParamError
from bms_core.core.plugin import resolve_plugin
from bms_core.db.session import DbSession
from bms_core.db.unit_of_work import DbUnitOfWork
from bms_core.outbox.base import BaseOutboxStore
from bms_core.transaction.base import BranchHandlerRegistry

from mdm_org.repositories.dept import DeptRepository
from mdm_org.repositories.post import PostRepository
from mdm_org.repositories.role_dept import RoleDeptRepository
from mdm_org.repositories.role_post import RolePostRepository
from mdm_org.repositories.user_dept import UserDeptRepository
from mdm_org.repositories.user_post import UserPostRepository
from mdm_org.services.role_dept import RoleDeptService
from mdm_org.services.role_post import RolePostService
from mdm_org.services.user_dept import UserDeptService
from mdm_org.services.user_post import UserPostService

if TYPE_CHECKING:
    from fastapi import FastAPI

__all__ = [
    "BRANCH_OPS",
    "ROLE_DEPTS_OP",
    "ROLE_POSTS_OP",
    "USER_DEPTS_OP",
    "USER_POSTS_OP",
    "build_branch_handlers",
]

USER_POSTS_OP = "org.user-posts.assign"
"""分支操作名：用户-岗位全量覆盖 + 主要岗位。"""

USER_DEPTS_OP = "org.user-depts.assign"
"""分支操作名：用户-部门全量覆盖 + 主要部门。"""

ROLE_POSTS_OP = "org.role-posts.assign"
"""分支操作名：角色-岗位全量覆盖。"""

ROLE_DEPTS_OP = "org.role-depts.assign"
"""分支操作名：角色-部门全量覆盖。"""

BRANCH_OPS = (USER_POSTS_OP, USER_DEPTS_OP, ROLE_POSTS_OP, ROLE_DEPTS_OP)
"""本服务登记的全部分支操作名（顺序稳定，供用例断言）。"""


def _int_arg(args: ConcurrentStableDict[str, object], key: str) -> int:
    """解包整数参数（缺失 / 类型非法即拒）。

    Args:
        args: 分支载荷。
        key: 参数名。

    Returns:
        int: 参数值。

    Raises:
        ParamError: 缺失 / 非整数（330010，参数错误）。
    """
    value = args.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ParamError(f"分支参数非法：{key}")
    return int(value)


def _optional_int_arg(args: ConcurrentStableDict[str, object], key: str) -> int | None:
    """解包可选整数参数（缺失 / `None` → `None`；类型非法即拒）。

    Args:
        args: 分支载荷。
        key: 参数名。

    Returns:
        int | None: 参数值（未提供为 `None`）。

    Raises:
        ParamError: 非整数（330010，参数错误）。
    """
    value = args.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ParamError(f"分支参数非法：{key}")
    return int(value)


def _ids_arg(args: ConcurrentStableDict[str, object], key: str) -> ConcurrentStableList[int]:
    """解包标识集合参数（缺失 → 空集合；非集合 / 元素非法即拒）。

    Args:
        args: 分支载荷。
        key: 参数名。

    Returns:
        ConcurrentStableList[int]: 标识集合。

    Raises:
        ParamError: 非集合或元素非法（330010，参数错误）。
    """
    value = args.get(key)
    if value is None:
        return ConcurrentStableList()
    if not isinstance(value, list):
        raise ParamError(f"分支参数非法：{key}")
    items: ConcurrentStableList[int] = ConcurrentStableList()
    for item in cast("list[object]", value):
        if isinstance(item, bool) or not isinstance(item, (int, str)):
            raise ParamError(f"分支参数非法：{key} 元素")
        items.add(int(item))
    return items


def _config_of(app: FastAPI) -> BaseConfigSource:
    """取应用装配的系统参数取数（与 `get_config_source` 同源解析）。

    Args:
        app: 应用实例。

    Returns:
        BaseConfigSource: 参数取数实例。
    """
    settings = cast("Settings", app.state.settings)
    return cast(
        "BaseConfigSource",
        resolve_plugin(
            "config_source", settings.config_source.provider, expected_version=BaseConfigSource.contract_version
        ),
    )


def _outbox_of(app: FastAPI) -> BaseOutboxStore:
    """取应用装配的发件箱存储（与 `get_outbox_store` 同源解析）。

    Args:
        app: 应用实例。

    Returns:
        BaseOutboxStore: 发件箱存储。
    """
    settings = cast("Settings", app.state.settings)
    return cast(
        "BaseOutboxStore",
        resolve_plugin(
            "outbox_store", settings.outbox_store.provider, expected_version=BaseOutboxStore.contract_version
        ),
    )


def build_branch_handlers(app: FastAPI) -> BranchHandlerRegistry:
    """构造并登记四组分配的分支处理器（**只调已有服务层**）。

    Args:
        app: 应用实例（取参数取数与发件箱存储；分支事务由执行器持有）。

    Returns:
        BranchHandlerRegistry: 分支处理器注册表。
    """
    registry = BranchHandlerRegistry()

    async def assign_user_posts(session: DbSession, args: ConcurrentStableDict[str, object]) -> None:
        """用户-岗位：全量覆盖 + 主要岗位（复用 `UserPostService`）。"""
        user_id = _int_arg(args, "user_id")
        service = UserPostService(
            UserPostRepository(session),
            PostRepository(session),
            DbUnitOfWork(session),
            _config_of(app),
            _outbox_of(app),
        )
        await service.assign_user_posts(user_id=user_id, post_ids=_ids_arg(args, "post_ids"))
        primary = _optional_int_arg(args, "primary_post_id")
        if primary is not None:
            await service.set_primary_post(user_id=user_id, post_id=primary)

    async def assign_user_depts(session: DbSession, args: ConcurrentStableDict[str, object]) -> None:
        """用户-部门：全量覆盖 + 主要部门（复用 `UserDeptService`）。"""
        user_id = _int_arg(args, "user_id")
        service = UserDeptService(
            UserDeptRepository(session),
            DeptRepository(session),
            DbUnitOfWork(session),
            _config_of(app),
            _outbox_of(app),
        )
        await service.assign_user_depts(user_id=user_id, dept_ids=_ids_arg(args, "dept_ids"))
        primary = _optional_int_arg(args, "primary_dept_id")
        if primary is not None:
            await service.set_primary_dept(user_id=user_id, dept_id=primary)

    async def assign_role_posts(session: DbSession, args: ConcurrentStableDict[str, object]) -> None:
        """角色-岗位：全量覆盖（复用 `RolePostService`）。"""
        service = RolePostService(
            RolePostRepository(session), PostRepository(session), DbUnitOfWork(session), _outbox_of(app)
        )
        await service.assign_role_posts(role_id=_int_arg(args, "role_id"), post_ids=_ids_arg(args, "post_ids"))

    async def assign_role_depts(session: DbSession, args: ConcurrentStableDict[str, object]) -> None:
        """角色-部门：全量覆盖（复用 `RoleDeptService`）。"""
        service = RoleDeptService(
            RoleDeptRepository(session), DeptRepository(session), DbUnitOfWork(session), _outbox_of(app)
        )
        await service.assign_role_depts(role_id=_int_arg(args, "role_id"), dept_ids=_ids_arg(args, "dept_ids"))

    registry.register(USER_POSTS_OP, assign_user_posts)
    registry.register(USER_DEPTS_OP, assign_user_depts)
    registry.register(ROLE_POSTS_OP, assign_role_posts)
    registry.register(ROLE_DEPTS_OP, assign_role_depts)
    return registry
