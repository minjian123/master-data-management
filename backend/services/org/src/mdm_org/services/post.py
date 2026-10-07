"""岗位服务：CRUD、岗位码唯一与格式校验、归属部门校验、删除引用检查与事件发布。"""

import re
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
from bms_core.schemas.pagination import BasePageQuery

from mdm_org import config as org_config
from mdm_org.errors import (
    OrgPostCodeExistsError,
    OrgPostCodeFormatError,
    OrgPostDeptUnavailableError,
    OrgPostHasRolesError,
    OrgPostHasUsersError,
    OrgPostNotFoundError,
)
from mdm_org.events import POST_CHANGED_EVENT
from mdm_org.models.dept import STATUS_ENABLED
from mdm_org.models.post import OrgPost
from mdm_org.repositories.dept import DeptRepository
from mdm_org.repositories.post import PostRepository
from mdm_org.repositories.role_post import RolePostRepository
from mdm_org.repositories.user_post import UserPostRepository

CHANGE_CREATED = "created"
"""变更类型：新建。"""

CHANGE_UPDATED = "updated"
"""变更类型：修改。"""

CHANGE_DELETED = "deleted"
"""变更类型：删除。"""


class PostService(BaseFrameworkObject):
    """岗位服务（事务边界：写方法经工作单元单事务）。"""

    def __init__(
        self,
        posts: PostRepository,
        depts: DeptRepository,
        user_posts: UserPostRepository,
        role_posts: RolePostRepository,
        uow: UnitOfWork,
        config: BaseConfigSource,
        outbox: BaseOutboxStore,
    ) -> None:
        """初始化。

        Args:
            posts: 岗位仓储。
            depts: 部门仓储（归属部门校验）。
            user_posts: 用户-岗位关联仓储（删除引用检查 / 岗位用户聚合）。
            role_posts: 角色-岗位分配仓储（删除引用检查 / 岗位角色聚合）。
            uow: 工作单元（事务边界）。
            config: 系统参数取数。
            outbox: 事务性发件箱。
        """
        self._posts = posts
        self._depts = depts
        self._user_posts = user_posts
        self._role_posts = role_posts
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

    async def require_post(self, post_id: int) -> OrgPost:
        """取岗位（不存在抛 `OrgPostNotFoundError`）。

        Args:
            post_id: 岗位 id。

        Returns:
            OrgPost: 岗位记录。

        Raises:
            OrgPostNotFoundError: 岗位不存在（330031）。
        """
        post = await self._posts.get(post_id)
        if post is None:
            raise OrgPostNotFoundError(f"岗位不存在：{post_id}")
        return post

    async def list_posts(
        self,
        query: BasePageQuery,
        *,
        dept_id: int | None = None,
        status: str | None = None,
        keyword: str | None = None,
    ) -> tuple[ConcurrentStableList[OrgPost], int]:
        """分页查询岗位（当前页 + 总数）。

        Args:
            query: 分页查询契约。
            dept_id: 归属部门过滤。
            status: 状态过滤。
            keyword: 关键字（岗位码 / 名称）。

        Returns:
            tuple[ConcurrentStableList[OrgPost], int]: （当前页记录，总数）。
        """
        rows = await self._posts.list_filtered(query, dept_id=dept_id, status=status, keyword=keyword)
        total = await self._posts.count_filtered(dept_id=dept_id, status=status, keyword=keyword)
        return rows, total

    async def list_post_users(self, post_id: int) -> ConcurrentStableList[int]:
        """取岗位下用户 id 列表。

        Args:
            post_id: 岗位 id。

        Returns:
            ConcurrentStableList[int]: 用户 id（插入序）。
        """
        await self.require_post(post_id)
        return ConcurrentStableList(link.user_id for link in await self._user_posts.list_by_post(post_id))

    async def list_post_roles(self, post_id: int) -> ConcurrentStableList[int]:
        """取岗位已分配角色 id 列表。

        Args:
            post_id: 岗位 id。

        Returns:
            ConcurrentStableList[int]: 角色 id（插入序）。
        """
        await self.require_post(post_id)
        return ConcurrentStableList(link.role_id for link in await self._role_posts.list_by_post(post_id))

    async def create_post(self, *, code: str, name: str, dept_id: int, sort: int = 0) -> OrgPost:
        """新建岗位（岗位码格式 + 唯一校验、归属部门存在且启用）。

        Args:
            code: 岗位码（创建后不可改）。
            name: 岗位名称。
            dept_id: 归属部门 id。
            sort: 排序。

        Returns:
            OrgPost: 新建岗位。

        Raises:
            OrgPostCodeFormatError: 岗位码不符合格式约束（330036）。
            OrgPostCodeExistsError: 岗位码已存在（330032）。
            OrgPostDeptUnavailableError: 归属部门不存在或已停用（330033）。
        """
        # 校验读与写同事务（SQLAlchemy 2.0：先读后 begin 会因自动开启事务而失败）
        async with self._uow.begin():
            await self._assert_code_format(code)
            dept = await self._depts.get(dept_id)
            if dept is None or dept.status != STATUS_ENABLED:
                raise OrgPostDeptUnavailableError(f"归属部门不存在或已停用：{dept_id}")
            if await self._posts.get_by_code(code) is not None:
                raise OrgPostCodeExistsError(f"岗位 code 已存在：{code}")
            post = await self._posts.create(code=code, name=name, dept_id=dept_id, sort=sort, status=STATUS_ENABLED)
            await self._publish(post.id, CHANGE_CREATED)
        return post

    async def update_post(
        self,
        *,
        post_id: int,
        name: str | None = None,
        dept_id: int | None = None,
        sort: int | None = None,
        status: str | None = None,
        version: int | None = None,
    ) -> OrgPost:
        """修改岗位（`code` 不可改；`version` 乐观锁比对）。

        Args:
            post_id: 岗位 id。
            name: 新名称；None 不改。
            dept_id: 新归属部门；None 不改。
            sort: 新排序；None 不改。
            status: 新状态；None 不改。
            version: 客户端版本（提供时比对）。

        Returns:
            OrgPost: 更新后的岗位。

        Raises:
            OrgPostNotFoundError: 岗位不存在（330031）。
            OrgPostDeptUnavailableError: 归属部门不存在或已停用（330033）。
            ConcurrentConflictError: 乐观锁冲突。
        """
        async with self._uow.begin():
            post = await self.require_post(post_id)
            if version is not None and version != post.version:
                raise ConcurrentConflictError(f"乐观锁冲突：期望版本 {version}，当前版本 {post.version}")
            if dept_id is not None and dept_id != post.dept_id:
                dept = await self._depts.get(dept_id)
                if dept is None or dept.status != STATUS_ENABLED:
                    raise OrgPostDeptUnavailableError(f"归属部门不存在或已停用：{dept_id}")
                post.dept_id = dept_id
            if name is not None:
                post.name = name
            if sort is not None:
                post.sort = sort
            if status is not None:
                post.status = status
            await self._posts.flush()
            await self._publish(post.id, CHANGE_UPDATED)
        return post

    async def delete_post(self, *, post_id: int) -> None:
        """删除岗位（有关联用户 / 角色分配则拒绝；通过后软删除）。

        Args:
            post_id: 岗位 id。

        Raises:
            OrgPostNotFoundError: 岗位不存在（330031）。
            OrgPostHasUsersError: 岗位仍关联用户（330034）。
            OrgPostHasRolesError: 岗位仍绑定角色（330035）。
        """
        async with self._uow.begin():
            post = await self.require_post(post_id)
            if await self._user_posts.count_by_post(post_id) > 0:
                raise OrgPostHasUsersError(f"岗位仍关联用户，禁止删除：{post_id}")
            if await self._role_posts.count_by_post(post_id) > 0:
                raise OrgPostHasRolesError(f"岗位仍绑定角色，禁止删除：{post_id}")
            await self._posts.soft_delete(post_id)
            await self._publish(post.id, CHANGE_DELETED)

    async def _assert_code_format(self, code: str) -> None:
        """校验岗位码格式（受 `org.post_code_pattern` 约束；配置非法回落默认）。

        Args:
            code: 岗位码。

        Raises:
            OrgPostCodeFormatError: 不符合格式（330036）。
        """
        pattern = await org_config.read_str(
            self._config, org_config.POST_CODE_PATTERN_KEY, org_config.DEFAULT_POST_CODE_PATTERN
        )
        try:
            matched = re.fullmatch(pattern, code) is not None
        except re.error:
            matched = re.fullmatch(org_config.DEFAULT_POST_CODE_PATTERN, code) is not None
        if not matched:
            raise OrgPostCodeFormatError(f"岗位 code 不符合格式约束：{code}")

    async def _publish(self, post_id: int, changed_type: str) -> None:
        """发布岗位变更事件（同事务写发件箱）。

        Args:
            post_id: 岗位 id。
            changed_type: 变更类型。
        """
        await self._outbox.enqueue(
            self._session,
            EventEnvelope(
                event_type=POST_CHANGED_EVENT,
                payload=ConcurrentStableDict({"post_id": str(post_id), "changed_type": changed_type}),
                tenant_id=current_tenant_id_str(),
                aggregate_key=f"org.post:{post_id}",
            ),
        )
