"""mdm 管理面权限码种子（07B `02_03` 真实播种）。

- **声明与执行分离**：产品自持清单 `deploy/registry/mdm.toml` 的 `[[seeds]]` 声明
  「模块路径 + 入口名 + 依赖顺序」；平台装载期校验入口可解析，执行由平台**统一种子编排**
  调度（一个 XA 全局事务内串行执行、统一提交或整体回滚）。
- **入口契约**：沿用基座分支处理器范式 `async def entry(session, args) -> None`——
  会话由执行器传入且**已绑定 XA 分支连接**，写入自动并入分支事务，本模块**不自行 commit**。
- **写入内容**：业务码 `mdm`（`sys_business`）+ 4 条权限码（`sys_permission`）。
  这些表归**平台服务库**，故种子声明的 `db_key = platform_platform`（不是 mdm 自己的库）；
  服务身份仍是 `mdm`，体现「产品声明、平台调度、产品执行」。
- **幂等**：按自然键判存——业务码按 `code`、权限码按 `(business_id, action_id)`；
  存在且同值即跳过，存在且异值抛 `ParamError`（由编排器事务前预检提前拦截）。
"""

from bms_core.core.concurrent import ConcurrentStableDict, ConcurrentStableFrozenDict
from bms_core.core.exceptions import ParamError
from bms_core.db.session import DbSession
from bms_core.models.platform.permission_meta import SysAction, SysBusiness, SysPermission
from bms_core.tenant.seed.contract import ExpectedRow
from sqlalchemy import select

__all__ = ["BUSINESS_CODE", "PERMISSION_ACTIONS", "expected_rows", "seed_admin_codes"]

BUSINESS_CODE = "mdm"
"""mdm 管理面业务码（= 产品键）。"""

BUSINESS_NAME = "组织主数据（mdm 产品）"
"""业务码显示名（冲突判定用）。"""

PERMISSION_ACTIONS: tuple[str, ...] = ("query", "create", "update", "delete")
"""mdm 管理面权限码的动作码（部门移动复用 `update`）。"""


def expected_rows() -> list[ExpectedRow]:
    """mdm 管理面权限码的期望行（冲突预检用；07B `02_03` 详设 §3.5）。

    **纯函数**：只读模块常量，不连库、不写库。覆盖业务码（`sys_business` 按 `code`）与
    动作码的存在性（`sys_action`，由平台先行播种，本种子只读不写，故不列入期望行）。

    Returns:
        list[ExpectedRow]: 期望行（业务码 mdm 一条）。
    """
    return [
        ExpectedRow(
            table="sys_business",
            key=ConcurrentStableFrozenDict({"code": BUSINESS_CODE}),
            values=ConcurrentStableFrozenDict({"name": BUSINESS_NAME}),
        )
    ]


async def seed_admin_codes(session: DbSession, args: ConcurrentStableDict[str, object]) -> None:
    """管理面业务码与权限码种子（在 XA 分支事务内执行）。

    Args:
        session: 已绑定 XA 分支连接的会话（写入自动并入分支事务）。
        args: 分支参数（本种子不消费）。

    Raises:
        ParamError: 业务码已存在且名称不同（声明与库中数据不一致）。
    """
    del args
    business = (
        await session.execute(
            select(SysBusiness).where(SysBusiness.code == BUSINESS_CODE, SysBusiness.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if business is None:
        business = SysBusiness(code=BUSINESS_CODE, name=BUSINESS_NAME, status="enabled")
        session.add(business)
        await session.flush()
    elif business.name != BUSINESS_NAME:
        raise ParamError(f"业务码 {BUSINESS_CODE} 已存在且名称不同（现有 {business.name!r} / 期望 {BUSINESS_NAME!r}）")
    business_id = int(business.id)
    for action_code in PERMISSION_ACTIONS:
        action = (
            await session.execute(
                select(SysAction).where(SysAction.code == action_code, SysAction.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        if action is None:
            raise ParamError(f"动作码未登记：{action_code}（须先在平台登记动词）")
        existing = (
            await session.execute(
                select(SysPermission).where(
                    SysPermission.business_id == business_id,
                    SysPermission.action_id == int(action.id),
                    SysPermission.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue
        session.add(SysPermission(business_id=business_id, action_id=int(action.id), status="enabled"))
