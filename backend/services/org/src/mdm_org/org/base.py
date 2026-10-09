"""组织只读出口端口契约与数据契约（自 bms `bms_core/org` 迁入 mdm 组织域，2026-10-07）。

- 常量：组织状态 `ORG_STATUSES`（enabled / disabled）、回显目标 `ORG_TARGETS`（user / post / dept）、
  默认每页条数 `DEFAULT_ORG_PAGE_SIZE`。
- 数据契约：`OrgUser`（手机号 / 邮箱为敏感字段）/ `OrgPost` / `OrgDept`（嵌套部门树）/ `OrgNameRef`。
- `BaseOrgDataSource`（`key = "org_data_source"`）：`users` / `posts`（关键字 / 部门 / 含子级 / 状态 /
  分页）+ `dept_tree`（不分页一次性返回）。
- `BaseOrgNameResolver`（`key = "org_name_resolver"`）：`resolve_names(target, ids)` 按 id 批量回显名称。
- `BaseOrgUserSource`（`key = "org_user_source"`）：用户明细**跨服务取数**端口——组织主数据归 mdm、
  用户（账号）归 platform，mdm **不跨库读** `sys_user`，只经平台用户只读出口契约取数。

口径：**租户隔离与动作级数据范围由实现侧经 `DataScope` 注入、字段脱敏经基座 `BaseMasker`
统一接入，契约方法不显式传租户 / 数据范围参数，调用方不可绕过**；`OrgUser.masked_fields` 声明手机号 /
邮箱为敏感字段（序列化自动掩码，持 `data:plain` 权限方可看明文）。部门树一次性返回、不分页；已删除 /
停用对象不抛错，由 `OrgNameRef.exists` / `status` 标记（前端回退展示 id）。业务与前端只经本出口取数，
**不直连组织域表**。
"""

from abc import ABC, abstractmethod
from typing import Annotated

from bms_core.core.concurrent import ConcurrentStableList, ConcurrentStableSet
from bms_core.core.plugin import DEFAULT_CONTRACT_VERSION, NULL_PLUGIN_NAME, BasePluggable
from bms_core.schemas.base import CONTRACT_COLLECTION, CONTRACT_STABLE_LIST, BaseSchema
from bms_core.schemas.pagination import BasePageResponse
from pydantic import Field

__all__ = [
    "DEFAULT_ORG_PAGE_SIZE",
    "ORG_STATUSES",
    "ORG_TARGETS",
    "BaseOrgDataSource",
    "BaseOrgNameResolver",
    "BaseOrgUserSource",
    "OrgDept",
    "OrgNameRef",
    "OrgPost",
    "OrgUser",
]

ORG_STATUSES: tuple[str, ...] = ("enabled", "disabled")
"""组织对象状态（用户 / 岗位 / 部门共用；`enabled` 启用 / `disabled` 停用）。"""

ORG_TARGETS: tuple[str, ...] = ("user", "post", "dept")
"""批量回显目标类型（用户 / 岗位 / 部门）。"""

DEFAULT_ORG_PAGE_SIZE = 20
"""组织列表默认每页条数（对齐前端组织选择字段下拉限制条数）。"""


class OrgUser(BaseSchema):
    """组织用户（展示所需最小字段；手机号 / 邮箱默认脱敏）。"""

    masked_fields = ConcurrentStableSet({"phone", "email"})
    """敏感字段（经基座掩码器序列化自动掩码；持 `data:plain` 权限方可看明文）。"""

    id: int = Field(description="用户 ID")
    username: str = Field(description="用户名")
    nickname: str = Field(default="", description="昵称")
    status: str = Field(default="enabled", description="状态（enabled / disabled）")
    avatar: str | None = Field(default=None, description="头像地址")
    phone: str | None = Field(default=None, description="手机号（默认脱敏）")
    email: str | None = Field(default=None, description="邮箱（默认脱敏）")


class OrgPost(BaseSchema):
    """组织岗位（展示所需最小字段）。"""

    id: int = Field(description="岗位 ID")
    code: str = Field(description="岗位编码")
    name: str = Field(description="岗位名称")
    dept_id: int | None = Field(default=None, description="归属部门 ID")
    status: str = Field(default="enabled", description="状态（enabled / disabled）")
    sort: int = Field(default=0, description="排序值")


class OrgDept(BaseSchema):
    """组织部门（嵌套树节点；部门树一次性返回、不分页）。"""

    id: int = Field(description="部门 ID")
    parent_id: int | None = Field(default=None, description="父部门 ID（None＝根）")
    code: str = Field(description="部门编码（租户内唯一）")
    name: str = Field(description="部门名称")
    sort: int = Field(default=0, description="排序值")
    status: str = Field(default="enabled", description="状态（enabled / disabled）")
    children: Annotated[ConcurrentStableList[OrgDept], CONTRACT_COLLECTION] = Field(
        default_factory=CONTRACT_STABLE_LIST, description="子部门（嵌套树）"
    )


class OrgNameRef(BaseSchema):
    """批量回显项（按 id 回显名称；已删除 / 停用不抛错，以字段标记）。"""

    id: int = Field(description="对象 ID")
    name: str = Field(description="对象名称（不存在时为占位名）")
    target: str = Field(default="user", description="目标类型（user / post / dept）")
    exists: bool = Field(default=True, description="对象是否存在")
    status: str = Field(default="enabled", description="状态（enabled / disabled）")


class BaseOrgDataSource(BasePluggable, ABC):
    """组织主数据查询契约：用户 / 岗位查询与部门树取数（真实取数经 mdm 本地装配注入）。"""

    key: str = "org_data_source"
    plugin_key: str = "org_data_source"
    plugin_name: str = NULL_PLUGIN_NAME
    contract_version: str = DEFAULT_CONTRACT_VERSION

    @abstractmethod
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
        """查询用户（关键字 / 部门 / 含子级 / 状态 / 分页）。

        Args:
            keyword: 关键字（用户名 / 昵称，命中列由实现定义）；None 不过滤。
            dept_id: 归属部门 ID；None 不过滤。
            include_children: 部门过滤是否含下级（实现按部门祖先链展开子树）。
            status: 状态过滤（`ORG_STATUSES` 之一）；None 不过滤。
            page: 页码（从 1 起）。
            size: 每页条数。

        Returns:
            BasePageResponse[OrgUser]: 分页用户（数据范围与脱敏由实现侧强制接入）。
        """

    @abstractmethod
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
        """查询岗位（关键字 / 部门 / 含子级 / 状态 / 分页）。

        Args:
            keyword: 关键字（岗位编码 / 名称，命中列由实现定义）；None 不过滤。
            dept_id: 归属部门 ID；None 不过滤。
            include_children: 部门过滤是否含下级。
            status: 状态过滤（`ORG_STATUSES` 之一）；None 不过滤。
            page: 页码（从 1 起）。
            size: 每页条数。

        Returns:
            BasePageResponse[OrgPost]: 分页岗位（数据范围由实现侧强制接入）。
        """

    @abstractmethod
    async def dept_tree(self, *, status: str | None = None) -> ConcurrentStableList[OrgDept]:
        """取部门树（一次性返回、不分页）。

        Args:
            status: 状态过滤（`ORG_STATUSES` 之一）；None 不过滤。

        Returns:
            ConcurrentStableList[OrgDept]: 部门树根节点序列（`children` 嵌套）。
        """


class BaseOrgNameResolver(BasePluggable, ABC):
    """组织主数据回显契约：按标识批量回显名称（避免 N+1）。"""

    key: str = "org_name_resolver"
    plugin_key: str = "org_name_resolver"
    plugin_name: str = NULL_PLUGIN_NAME
    contract_version: str = DEFAULT_CONTRACT_VERSION

    @abstractmethod
    async def resolve_names(self, target: str, ids: ConcurrentStableList[int]) -> ConcurrentStableList[OrgNameRef]:
        """按 id 批量回显名称。

        Args:
            target: 目标类型（`ORG_TARGETS` 之一：user / post / dept）。
            ids: 对象 ID 序列。

        Returns:
            ConcurrentStableList[OrgNameRef]: 回显项（未命中 id 也在结果中占位，`exists=False`）。
        """


class BaseOrgUserSource(BasePluggable, ABC):
    """用户明细来源端口（跨服务）：组织只读出口的用户维度唯一取数通道。

    组织主数据（部门 / 岗位 / 人员）归 mdm，**用户（账号）归 platform**——用户明细（用户名 / 昵称 /
    状态 / 联系方式 / 归属部门）经**平台用户只读出口契约**取数，mdm **不跨库读** `sys_user`。
    实现：`mdm_org/org/user_source.py::PlatformOrgUserSource`（经服务间调用）。
    """

    key: str = "org_user_source"
    plugin_key: str = "org_user_source"
    plugin_name: str = NULL_PLUGIN_NAME
    contract_version: str = DEFAULT_CONTRACT_VERSION

    @abstractmethod
    async def query(
        self,
        keyword: str | None = None,
        *,
        status: str | None = None,
        ids: ConcurrentStableList[int] | None = None,
        page: int = 1,
        size: int = DEFAULT_ORG_PAGE_SIZE,
    ) -> BasePageResponse[OrgUser]:
        """查询用户（关键字 / 状态 / 限定集合 / 分页）。

        Args:
            keyword: 关键字（用户名 / 昵称，大小写不敏感）；None 不过滤。
            status: 状态过滤（`ORG_STATUSES` 之一）；None 不过滤。
            ids: 限定集合（非空时只在该集合内筛选；空 / None 不限定）。
            page: 页码（从 1 起）。
            size: 每页条数。

        Returns:
            BasePageResponse[OrgUser]: 分页用户。

        Raises:
            OrgSourceUnavailableError: 用户来源不可达 / 未装配 / 响应契约非法（330101）。
        """

    @abstractmethod
    async def by_ids(self, ids: ConcurrentStableList[int]) -> ConcurrentStableList[OrgUser]:
        """按主键集合批量取用户（名称回显用；不存在 / 已删除的 id 不出现在结果中）。

        Args:
            ids: 用户主键序列。

        Returns:
            ConcurrentStableList[OrgUser]: 用户序列。

        Raises:
            OrgSourceUnavailableError: 用户来源不可达 / 未装配 / 响应契约非法（330101）。
        """
