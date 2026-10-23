"""组织域 **XA 分支参与方**用例（Kiwi 2274；嵌套子任务 `_03` 第 7 条）。

覆盖：① 分支端点已挂载（5 条，协议动作与 TM 白名单口径）；② 四 `op` 已登记且**只调已有服务层**；
③ `[transaction_manager].provider` 缺省为空 ⇒ 参与方为占位实现，协议动作**明确拒绝**（`10013` / 503，不静默降级）。
"""

import pytest
from bms_core.core.concurrent import ConcurrentStableDict, ConcurrentStableFrozenList
from bms_core.core.exceptions import AuthError, ParamError
from bms_core.oauth.token import TOKEN_AUDIENCE_SERVICE
from bms_core.oauth.verify import BaseTokenVerifier, VerifiedToken, get_token_verifier
from bms_core.transaction.base import BranchHandlerRegistry
from fastapi import FastAPI
from httpx import AsyncClient

from mdm.repositories.dept import DeptRepository
from mdm.repositories.user_dept import UserDeptRepository
from mdm.services.branch_handlers import BRANCH_OPS, ROLE_DEPTS_OP, ROLE_POSTS_OP, USER_DEPTS_OP, USER_POSTS_OP
from mdm.services.user_dept import UserDeptService
from tests_support import org_env

BRANCH_PATHS = (
    "/api/v1/txn/branches",
    "/api/v1/txn/branches/{xid}/commit",
    "/api/v1/txn/branches/{xid}/rollback",
    "/api/v1/txn/branches/{xid}",
)


class _BranchVerifierStub(BaseTokenVerifier):
    """令牌校验替身（**插件名须唯一**，避免与其它模块替身重名）。"""

    plugin_name: str = "branch_participant_stub"

    async def verify(self, token: str, *, audience: str) -> VerifiedToken:
        """服务受众一律放行（协议动作的**白名单**由基座依赖判定，不在此处）。

        Args:
            token: 令牌紧凑串（忽略）。
            audience: 期望受众。

        Returns:
            VerifiedToken: 服务身份声明。

        Raises:
            AuthError: 非服务受众。
        """
        del token
        if audience == TOKEN_AUDIENCE_SERVICE:
            return VerifiedToken(
                subject="gateway", service="platform", audience=ConcurrentStableFrozenList((audience,))
            )
        raise AuthError("用户令牌不可用（替身）")


@pytest.mark.kiwi_id(2274)
async def test_branch_paths_mounted(service_app: FastAPI) -> None:
    """分支端点已挂载（执行 / 提交 / 回滚 / 状态）。"""
    paths = service_app.openapi()["paths"]

    for path in BRANCH_PATHS:
        assert path in paths, f"分支端点未挂载：{path}"
    assert "post" in paths["/api/v1/txn/branches"]
    assert "get" in paths["/api/v1/txn/branches/{xid}"]


@pytest.mark.kiwi_id(2274)
async def test_branch_handlers_registered_and_delegate_to_service(service_app: FastAPI) -> None:
    """四 `op` 已登记；处理器**只调已有服务层**（用真实会话调用即写生效）。"""
    handlers = service_app.state.branch_handlers
    assert isinstance(handlers, BranchHandlerRegistry)
    assert handlers.ops() == BRANCH_OPS

    session, engine = await org_env.make_session()
    try:
        depts = org_env.make_dept_service(session, org_env.make_uow(session), org_env.make_outbox())
        dept = await depts.create_dept(code="rd", name="研发中心", parent_id=None, sort=1)
        dept_id = dept.id
        await org_env.commit(session)

        handler = handlers.resolve(USER_DEPTS_OP)
        assert handler is not None
        await handler(
            session,
            ConcurrentStableDict[str, object]({"user_id": 3101, "dept_ids": [dept_id], "primary_dept_id": dept_id}),
        )
        await org_env.commit(session)

        service = UserDeptService(
            UserDeptRepository(session),
            DeptRepository(session),
            org_env.make_uow(session),
            org_env.make_config(),
            org_env.make_outbox(),
        )
        assert await service.list_user_depts(3101) == [dept_id]
        await org_env.commit(session)
        assert await service.primary_dept_id(3101) == dept_id
        await org_env.commit(session)
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2274)
async def test_branch_handlers_cover_all_ops_and_reject_invalid_params(service_app: FastAPI) -> None:
    """四 `op` 处理器全走通（用户-岗位带主要项 / 角色-岗位 / 角色-部门），非法载荷一律 `ParamError`。"""
    handlers = service_app.state.branch_handlers
    session, engine = await org_env.make_session()
    try:
        key = await org_env.seed_org_tree(session)

        user_posts = handlers.resolve(USER_POSTS_OP)
        role_posts = handlers.resolve(ROLE_POSTS_OP)
        role_depts = handlers.resolve(ROLE_DEPTS_OP)
        assert user_posts is not None and role_posts is not None and role_depts is not None

        await user_posts(
            session,
            ConcurrentStableDict[str, object](
                {"user_id": 3102, "post_ids": [key["eng"]], "primary_post_id": key["eng"]}
            ),
        )
        await org_env.commit(session)
        await role_posts(session, ConcurrentStableDict[str, object]({"role_id": 9101, "post_ids": [key["eng"]]}))
        await org_env.commit(session)
        await role_depts(session, ConcurrentStableDict[str, object]({"role_id": 9101, "dept_ids": [key["root"]]}))
        await org_env.commit(session)
        # 不带主要项 / 不带集合键：分别覆盖「跳过主要项置位」与「缺省空集合」两条分支
        await user_posts(session, ConcurrentStableDict[str, object]({"user_id": 3103, "post_ids": []}))
        await org_env.commit(session)
        await role_depts(session, ConcurrentStableDict[str, object]({"role_id": 9102}))
        await org_env.commit(session)
        await handlers.resolve(USER_DEPTS_OP)(
            session, ConcurrentStableDict[str, object]({"user_id": 3104, "dept_ids": []})
        )
        await org_env.commit(session)

        with pytest.raises(ParamError):
            await user_posts(session, ConcurrentStableDict[str, object]({"user_id": True, "post_ids": []}))
        with pytest.raises(ParamError):
            await user_posts(
                session,
                ConcurrentStableDict[str, object]({"user_id": 1, "post_ids": [], "primary_post_id": True}),
            )
        with pytest.raises(ParamError):
            await user_posts(session, ConcurrentStableDict[str, object]({"user_id": 1, "post_ids": "bad"}))
        with pytest.raises(ParamError):
            await user_posts(session, ConcurrentStableDict[str, object]({"user_id": 1, "post_ids": [True]}))
    finally:
        await engine.dispose()


@pytest.mark.kiwi_id(2274)
async def test_branch_verifier_stub_rejects_user_audience() -> None:
    """令牌替身自身：非服务受众一律拒（替身行为与真实校验器口径一致）。"""
    with pytest.raises(AuthError):
        await _BranchVerifierStub().verify("token", audience="api")


@pytest.mark.kiwi_id(2274)
async def test_branch_execute_rejected_when_provider_disabled(service_app: FastAPI, client: AsyncClient) -> None:
    """`[transaction_manager].provider` 缺省为空 ⇒ 参与方为占位实现：执行分支**明确拒绝**（`10013` / 503）。"""
    service_app.dependency_overrides[get_token_verifier] = lambda: _BranchVerifierStub()

    payload: dict[str, object] = {
        "xid": "1|b1",
        "db_key": "tenant_demo",
        "ops": [{"op": USER_DEPTS_OP, "args": {}}],
    }
    response = await client.post("/api/v1/txn/branches", json=payload, headers={"Authorization": "Bearer stub"})

    assert response.status_code == 503
    assert response.json()["code"] == 10013
