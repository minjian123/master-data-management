"""组织域事件包：契约声明 + 产品侧注入入口。

对外暴露 `register_product_event_contracts(registry)`（基座 `ops.event_contracts --product-contracts
mdm_org.events` 按该名加载产品侧契约，缺件即拒、不静默降级）；应用装配亦经本入口把契约登记进
进程级默认注册表（启动期事件契约校验与快照共用）。
"""

from bms_core.events.contracts import EventContractRegistry

from mdm_org.events.contracts import (
    DEPT_CHANGED_EVENT,
    ORG_EVENT_CONTRACTS,
    POST_CHANGED_EVENT,
    ROLE_DEPT_CHANGED_EVENT,
    ROLE_POST_CHANGED_EVENT,
    USER_DEPT_CHANGED_EVENT,
    USER_POST_CHANGED_EVENT,
    register_org_event_contracts,
)

__all__ = [
    "DEPT_CHANGED_EVENT",
    "ORG_EVENT_CONTRACTS",
    "POST_CHANGED_EVENT",
    "ROLE_DEPT_CHANGED_EVENT",
    "ROLE_POST_CHANGED_EVENT",
    "USER_DEPT_CHANGED_EVENT",
    "USER_POST_CHANGED_EVENT",
    "register_org_event_contracts",
    "register_product_event_contracts",
]


def register_product_event_contracts(registry: EventContractRegistry | None = None) -> None:
    """产品侧事件契约注入入口（基座 CLI / 应用装配调用；幂等）。

    Args:
        registry: 目标注册表；None 取进程级默认注册表。
    """
    register_org_event_contracts(registry)
