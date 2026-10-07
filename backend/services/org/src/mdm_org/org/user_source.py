"""用户明细来源实现：经服务间调用 bms platform 用户只读出口取数（**不跨库读** `sys_user`）。

- 目标：`POST /api/v1/platform/internal/users/query`（platform 内部端点，`require_service` 白名单为
  本组织服务键；东西向直连不经网关）；
- 出站身份：经基座 `service_client` 调用，出站剥离入站 `Authorization` 并按开关附自签服务 JWT
  （`caller` = 本服务标识）+ `tenant` claim（供 platform 解析租户库）；
- 失败语义：下游不可达 / 非 2xx / 统一响应 `code != 0` / 响应契约非法 → **一律 fail-closed** 转
  `OrgSourceUnavailableError`（330101），**不静默返回空或旧值**（用户维度缺失必须让调用方感知）。
"""

from collections.abc import Iterable
from typing import cast

from bms_core.core.concurrent import ConcurrentStableDict, ConcurrentStableList, ConcurrentStableSet
from bms_core.core.exceptions import ServiceUnavailableError
from bms_core.db.tenant import current_tenant_id_str
from bms_core.schemas.pagination import BasePageResponse
from bms_core.servicecall.base import BaseServiceClient, ServiceCallPolicy, ServiceRequest, ServiceResponse

from mdm_org.errors import OrgSourceUnavailableError
from mdm_org.org.base import DEFAULT_ORG_PAGE_SIZE, BaseOrgUserSource, OrgUser

PLATFORM_SERVICE = "platform"
"""用户（账号）归属服务标识。"""

QUERY_PATH = "/api/v1/platform/internal/users/query"
"""平台用户只读出口路径（内部端点，服务间公开契约面 `/api/v1`）。"""

_INTERFACE = "platform 用户只读出口"
"""错误提示用接口名称。"""

_ITEM_COLUMNS = ConcurrentStableSet({"id", "username", "name", "status"})
"""响应行必备标量列（缺失即视为响应契约非法）。"""


class PlatformOrgUserSource(BaseOrgUserSource):
    """平台用户只读出口实现（服务间调用；租户经服务 JWT `tenant` claim 传递）。"""

    def __init__(self, client: BaseServiceClient) -> None:
        """初始化。

        Args:
            client: 服务间调用客户端（经 mdm 应用装配注入）。
        """
        self._client = client

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
            status: 状态过滤；None 不过滤。
            ids: 限定集合（非空时只在该集合内筛选；空 / None 不限定）。
            page: 页码（从 1 起）。
            size: 每页条数。

        Returns:
            BasePageResponse[OrgUser]: 分页用户。

        Raises:
            OrgSourceUnavailableError: 下游不可达 / 非 2xx / 响应契约非法（330101）。
        """
        body: ConcurrentStableDict[str, object] = ConcurrentStableDict({"page": page, "size": size})
        if keyword:
            body.set("keyword", keyword)
        if status:
            body.set("status", status)
        if ids:
            body.set("ids", tuple(ids))
        data = await self._post(body)
        return _page(data, page=page, size=size)

    async def by_ids(self, ids: ConcurrentStableList[int]) -> ConcurrentStableList[OrgUser]:
        """按主键集合批量取用户（名称回显用）。

        Args:
            ids: 用户主键序列。

        Returns:
            ConcurrentStableList[OrgUser]: 用户序列（不存在的 id 不出现在结果中）。

        Raises:
            OrgSourceUnavailableError: 下游不可达 / 非 2xx / 响应契约非法（330101）。
        """
        if not ids:
            return ConcurrentStableList()
        body: ConcurrentStableDict[str, object] = ConcurrentStableDict({"ids": tuple(ids), "page": 1, "size": len(ids)})
        data = await self._post(body)
        return _rows(data)

    async def _post(self, body: ConcurrentStableDict[str, object]) -> ConcurrentStableDict[str, object]:
        """发起一次用户只读查询调用并取统一响应 `data`。

        Args:
            body: 请求体。

        Returns:
            ConcurrentStableDict[str, object]: 统一响应 `data`。

        Raises:
            OrgSourceUnavailableError: 下游不可达 / 非 2xx / 响应契约非法（330101）。
        """
        try:
            response = await self._client.call(
                ServiceRequest(
                    service=PLATFORM_SERVICE,
                    method="POST",
                    path=QUERY_PATH,
                    tenant_id=current_tenant_id_str(),
                    json_body=body,
                    policy=ServiceCallPolicy(),
                )
            )
        except ServiceUnavailableError as exc:
            raise OrgSourceUnavailableError(f"{_INTERFACE}不可达：{exc}") from exc
        return _payload_data(response)


def _payload_data(response: ServiceResponse) -> ConcurrentStableDict[str, object]:
    """解析服务响应为统一响应 `data`（非 2xx / 非对象 / `code != 0` 即来源不可用）。

    Args:
        response: 服务间调用响应。

    Returns:
        ConcurrentStableDict[str, object]: 统一响应 `data`。

    Raises:
        OrgSourceUnavailableError: 响应非法（330101）。
    """
    payload = response.payload()
    if not isinstance(payload, dict) or response.status_code != 200:
        raise OrgSourceUnavailableError(f"{_INTERFACE}返回非法响应（HTTP {response.status_code}）")
    body = cast("dict[str, object]", payload)
    if body.get("code") != 0:
        raise OrgSourceUnavailableError(f"{_INTERFACE}返回失败：{body.get('code')!r} {body.get('message')!r}")
    data = body.get("data")
    if not isinstance(data, dict):
        raise OrgSourceUnavailableError(f"{_INTERFACE}返回契约非法：缺少 data")
    return ConcurrentStableDict(cast("dict[str, object]", data))


def _rows(data: ConcurrentStableDict[str, object]) -> ConcurrentStableList[OrgUser]:
    """取分页数据的行序列并映射为 `OrgUser`。

    Args:
        data: 统一响应 `data`（分页形态）。

    Returns:
        ConcurrentStableList[OrgUser]: 用户序列。

    Raises:
        OrgSourceUnavailableError: 行契约非法（330101）。
    """
    raw = data.get("list")
    if raw is not None and not isinstance(raw, (list, tuple)):
        raise OrgSourceUnavailableError(f"{_INTERFACE}返回契约非法：list 非序列")
    rows: ConcurrentStableList[OrgUser] = ConcurrentStableList()
    for item in cast("Iterable[object]", raw or ()):
        rows.add(_to_user(item))
    return rows


def _page(data: ConcurrentStableDict[str, object], *, page: int, size: int) -> BasePageResponse[OrgUser]:
    """把分页数据映射为 `BasePageResponse[OrgUser]`（总数缺失时回落为当前页行数）。

    Args:
        data: 统一响应 `data`。
        page: 页码（响应缺失时回显请求值）。
        size: 每页条数（响应缺失时回显请求值）。

    Returns:
        BasePageResponse[OrgUser]: 分页用户。

    Raises:
        OrgSourceUnavailableError: 行契约非法（330101）。
    """
    rows = _rows(data)
    raw_total = data.get("total")
    raw_page = data.get("page")
    raw_size = data.get("size")
    return BasePageResponse[OrgUser](
        list=rows,
        total=raw_total if isinstance(raw_total, int) else len(rows),
        page=raw_page if isinstance(raw_page, int) else page,
        size=raw_size if isinstance(raw_size, int) else size,
    )


def _to_user(item: object) -> OrgUser:
    """把平台用户只读行映射为 `OrgUser`。

    平台只读行字段：`id` / `username` / `name` / `status` / `phone` / `email` / `dept_id`；
    其中 `name` 对映契约的 `nickname`，`avatar` 平台契约暂未提供（恒空，随用户完整域补）。

    Args:
        item: 平台返回的单行。

    Returns:
        OrgUser: 组织用户契约实体。

    Raises:
        OrgSourceUnavailableError: 行契约非法（330101）。
    """
    if not isinstance(item, dict):
        raise OrgSourceUnavailableError(f"{_INTERFACE}返回契约非法：行非对象")
    row = cast("dict[str, object]", item)
    missing = [name for name in _ITEM_COLUMNS if name not in row]
    if missing:
        raise OrgSourceUnavailableError(f"{_INTERFACE}返回契约非法：缺列 {'、'.join(sorted(missing))}")
    user_id = row.get("id")
    if not isinstance(user_id, int):
        raise OrgSourceUnavailableError(f"{_INTERFACE}返回契约非法：id 非整数")
    dept_id = row.get("dept_id")
    if dept_id is not None and not isinstance(dept_id, int):
        raise OrgSourceUnavailableError(f"{_INTERFACE}返回契约非法：dept_id 非整数或空")
    return OrgUser(
        id=user_id,
        username=_text(row.get("username")),
        nickname=_text(row.get("name")),
        dept_id=dept_id,
        status=_text(row.get("status")) or "enabled",
        avatar=None,
        phone=_optional_text(row.get("phone")),
        email=_optional_text(row.get("email")),
    )


def _text(value: object) -> str:
    """取字符串值（非字符串返回空串）。

    Args:
        value: 原始值。

    Returns:
        str: 字符串值或空串。
    """
    return value if isinstance(value, str) else ""


def _optional_text(value: object) -> str | None:
    """取可空字符串值（非字符串一律视为空）。

    Args:
        value: 原始值。

    Returns:
        str | None: 字符串值或 None。
    """
    return value if isinstance(value, str) else None


__all__ = ["PLATFORM_SERVICE", "QUERY_PATH", "PlatformOrgUserSource"]
