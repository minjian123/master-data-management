"""组织域事件契约（5 条 `org.*`）。

事件名 = `{已登记事件域}.{对象}.{动作}`（域 `org` 已在服务目录登记）；契约随「组织主数据域实现」
一并登记（`[event].contract_mode` 缺省 `enforce`，未登记契约拒发 10010）；主版本内字段只增不删、
新增必须可选，破坏性变更升主版本。
"""

from bms_core.core.concurrent import ConcurrentStableDict
from bms_core.events.contracts import (
    EventContract,
    EventContractRegistry,
    EventFieldSpec,
    register_event_contract,
)

DEPT_CHANGED_EVENT = "org.dept.changed"
"""部门变更事件（新建 / 修改 / 移动 / 删除后）。"""

POST_CHANGED_EVENT = "org.post.changed"
"""岗位变更事件。"""

USER_POST_CHANGED_EVENT = "org.user_post.changed"
"""用户-岗位分配变更事件。"""

ROLE_POST_CHANGED_EVENT = "org.role_post.changed"
"""角色-岗位分配变更事件（供权限版本失效）。"""

ROLE_DEPT_CHANGED_EVENT = "org.role_dept.changed"
"""角色-部门分配变更事件（供权限版本失效）。"""

USER_DEPT_CHANGED_EVENT = "org.user_dept.changed"
"""用户-部门分配变更事件（全量覆盖 / 解绑 / 主要部门置位或清除 / 用户删除清理）。"""

_STRING_REQUIRED = EventFieldSpec(type="string", required=True)
"""必填字符串字段（雪花 ID 出参字符串化）。"""

_CHANGED_TYPE = EventFieldSpec(type="string", required=False)
"""变更类型（created / updated / moved / deleted / assigned / unassigned / primary）。"""

ORG_EVENT_CONTRACTS: tuple[EventContract, ...] = (
    EventContract(
        event_type=DEPT_CHANGED_EVENT,
        description="部门变更后（新建 / 修改 / 移动 / 删除）",
        fields=ConcurrentStableDict({"dept_id": _STRING_REQUIRED, "changed_type": _CHANGED_TYPE}),
    ),
    EventContract(
        event_type=POST_CHANGED_EVENT,
        description="岗位变更后（新建 / 修改 / 删除）",
        fields=ConcurrentStableDict({"post_id": _STRING_REQUIRED, "changed_type": _CHANGED_TYPE}),
    ),
    EventContract(
        event_type=USER_POST_CHANGED_EVENT,
        description="用户-岗位分配变更后（全量覆盖 / 解绑 / 用户删除清理）",
        fields=ConcurrentStableDict(
            {"user_id": _STRING_REQUIRED, "post_id": _STRING_REQUIRED, "changed_type": _CHANGED_TYPE}
        ),
    ),
    EventContract(
        event_type=ROLE_POST_CHANGED_EVENT,
        description="角色-岗位分配变更后（供 bms 权限版本失效）",
        fields=ConcurrentStableDict(
            {"role_id": _STRING_REQUIRED, "post_id": _STRING_REQUIRED, "changed_type": _CHANGED_TYPE}
        ),
    ),
    EventContract(
        event_type=ROLE_DEPT_CHANGED_EVENT,
        description="角色-部门分配变更后（供 bms 权限版本失效）",
        fields=ConcurrentStableDict(
            {"role_id": _STRING_REQUIRED, "dept_id": _STRING_REQUIRED, "changed_type": _CHANGED_TYPE}
        ),
    ),
    EventContract(
        event_type=USER_DEPT_CHANGED_EVENT,
        description="用户-部门分配变更后（全量覆盖 / 解绑 / 主要部门置位或清除 / 用户删除清理）",
        fields=ConcurrentStableDict(
            {"user_id": _STRING_REQUIRED, "dept_id": _STRING_REQUIRED, "changed_type": _CHANGED_TYPE}
        ),
    ),
)
"""组织域事件契约清单（插入序）。"""


def register_org_event_contracts(registry: EventContractRegistry | None = None) -> None:
    """登记组织域事件契约（**幂等**：同值重复登记无操作）。

    Args:
        registry: 目标注册表；None 取进程级默认注册表。
    """
    for contract in ORG_EVENT_CONTRACTS:
        register_event_contract(contract, registry=registry)
