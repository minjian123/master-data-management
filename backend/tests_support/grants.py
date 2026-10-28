"""授权视图来源替身（07B `03_01` 用例支撑）

本服务入站按**能力分配**判定，判定数据来自授权视图来源。生产态来源是「经平台内部出口拉取」
（`RemoteCapabilityGrantSource`），单测不真实外呼，故用本替身覆盖：

- 在**应用启动之后**登记（覆盖启动钩子登记的远端来源），避免用例真连 platform；
- 用例按需 `grant()` / `revoke()` 增删授权，并让视图快照失效（改动对下一次判定立即生效）；
- `fail=True` 模拟来源不可用（首访 fail-closed 分支）。
"""

from collections.abc import Iterator

import pytest
from bms_core.collaboration.grant import (
    CapabilityGrant,
    invalidate_capability_grants,
    register_capability_grant_source,
    reset_capability_grants,
)
from bms_core.core.concurrent import ConcurrentStableList
from bms_core.core.exceptions import CatalogError
from fastapi import FastAPI

__all__ = ["PLATFORM_CONSUMER", "StaticGrantSource", "grant_source"]

PLATFORM_CONSUMER = "platform"
"""能力授权的缺省消费方（宿主编排方）。"""


class StaticGrantSource:
    """静态授权来源替身：按维度返回用例预置的授权记录（实现 `CapabilityGrantSource` 协议）。"""

    def __init__(self) -> None:
        """初始化（空授权集）。"""
        self._grants: ConcurrentStableList[CapabilityGrant] = ConcurrentStableList()
        self.fail = False

    async def load(
        self, *, provider: str | None = None, consumer: str | None = None
    ) -> ConcurrentStableList[CapabilityGrant]:
        """按维度返回预置授权。

        Args:
            provider: 提供方业务域（本替身不区分，返回全部）。
            consumer: 消费方服务键（给定时只返回该消费方的记录）。

        Returns:
            ConcurrentStableList[CapabilityGrant]: 授权记录。

        Raises:
            CatalogError: `fail` 为真（模拟来源不可用）。
        """
        del provider
        if self.fail:
            raise CatalogError("授权视图来源不可用（用例替身）")
        if consumer is None:
            return ConcurrentStableList(self._grants)
        matched: ConcurrentStableList[CapabilityGrant] = ConcurrentStableList()
        for grant in self._grants:
            if grant.consumer_key == consumer:
                matched.add(grant)
        return matched

    def grant(self, capability: str, consumer: str = PLATFORM_CONSUMER) -> None:
        """授予一项能力（并令视图快照失效，下一次判定即生效）。

        Args:
            capability: 能力名。
            consumer: 消费方服务键。
        """
        self._grants.add(CapabilityGrant(capability_name=capability, consumer_key=consumer))
        invalidate_capability_grants()

    def revoke(self, capability: str, consumer: str = PLATFORM_CONSUMER) -> None:
        """撤销一项能力（用例构造「无有效分配」分支）。

        Args:
            capability: 能力名。
            consumer: 消费方服务键。
        """
        kept: ConcurrentStableList[CapabilityGrant] = ConcurrentStableList()
        for grant in self._grants:
            if (grant.capability_name, grant.consumer_key) != (capability, consumer):
                kept.add(grant)
        self._grants = kept
        invalidate_capability_grants()


@pytest.fixture
def grant_source(service_app: FastAPI) -> Iterator[StaticGrantSource]:
    """授权视图来源替身夹具（在应用启动后登记，覆盖远端来源；用例结束复位进程级视图）。

    Args:
        service_app: 已启动的应用实例（依赖它保证启动钩子先跑完）。

    Yields:
        StaticGrantSource: 可增删授权的来源替身。
    """
    del service_app
    reset_capability_grants()
    source = StaticGrantSource()
    register_capability_grant_source(source)
    yield source
    reset_capability_grants()
