"""组织只读出口的契约护栏用例：下级返回畸形载荷时**明确失败**（不静默降级、不返回半成品）。

覆盖：用户来源响应 `list` 非序列 / 行非对象、角色缓存载荷形状非法、`ids` 过滤参数透传。
"""

import pytest
from bms_core.core.concurrent import ConcurrentStableDict, ConcurrentStableList

from mdm.errors import OrgSourceUnavailableError
from mdm.org import user_source
from mdm.org.user_source import PlatformOrgUserSource
from mdm.services import open_read
from tests_support import org_env


@pytest.mark.kiwi_id(2256)
async def test_user_source_rejects_malformed_rows() -> None:
    """用户来源：`list` 非序列 → 330101；行非对象 → 330101（契约非法即失败）。"""
    # 解析函数为同模块私有：直测契约判定口径（端到端由下方 query 用例覆盖）
    with pytest.raises(OrgSourceUnavailableError):
        user_source._rows(ConcurrentStableDict({"list": "not-a-sequence"}))  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(OrgSourceUnavailableError):
        user_source._to_user("not-a-row")  # pyright: ignore[reportPrivateUsage]


@pytest.mark.kiwi_id(2256)
async def test_user_source_rejects_malformed_downstream_payload() -> None:
    """下游返回畸形载荷：`list` 非序列 / 行非对象 → 出口明确失败（330101），不静默降级。"""
    bad_list = org_env.StubPlatformClient(
        payload={"code": 0, "message": "ok", "data": {"list": "not-a-sequence", "total": 0, "page": 1, "size": 10}}
    )
    with pytest.raises(OrgSourceUnavailableError):
        await PlatformOrgUserSource(bad_list).query()

    bad_row = org_env.StubPlatformClient(
        payload={"code": 0, "message": "ok", "data": {"list": ["not-a-row"], "total": 1, "page": 1, "size": 10}}
    )
    with pytest.raises(OrgSourceUnavailableError):
        await PlatformOrgUserSource(bad_row).query()


@pytest.mark.kiwi_id(2256)
async def test_ids_filter_and_bad_role_cache_payload() -> None:
    """`ids` 过滤随请求下发；角色缓存载荷形状非法时按「无缓存」处理（回落重算）。"""
    client = org_env.StubPlatformClient(ConcurrentStableList([org_env.user(7), org_env.user(8)]))
    page = await PlatformOrgUserSource(client).query(page=1, size=10, ids=ConcurrentStableList([7, 8]))
    assert page.total == 2

    # 缓存载荷解析为同模块私有：直测形状判定口径（非法即按「无缓存」回落重算）
    assert open_read._from_payload("not-a-mapping") is None  # pyright: ignore[reportPrivateUsage]
    assert open_read._from_payload(ConcurrentStableDict({open_read.ROLE_IDS_FIELD: "bad"})) is None  # pyright: ignore[reportPrivateUsage]
    assert open_read._from_payload(ConcurrentStableDict({open_read.ROLE_IDS_FIELD: ["bad"]})) is None  # pyright: ignore[reportPrivateUsage]
    parsed = open_read._from_payload(ConcurrentStableDict({open_read.ROLE_IDS_FIELD: [1, 1]}))  # pyright: ignore[reportPrivateUsage]
    assert parsed is not None and list(parsed) == [1]


@pytest.mark.kiwi_id(2256)
async def test_user_source_query_and_by_ids_use_stub_client() -> None:
    """正常载荷：`query` 与 `by_ids` 均走通（替身客户端契约校验，空集合短路）。"""
    client = org_env.StubPlatformClient(ConcurrentStableList([org_env.user(2001, nickname="张三")]))
    source = PlatformOrgUserSource(client)
    assert (await source.query(page=1, size=10)).total == 1
    assert [item.id for item in await source.by_ids(ConcurrentStableList([2001]))] == [2001]
    assert list(await source.by_ids(ConcurrentStableList())) == []
