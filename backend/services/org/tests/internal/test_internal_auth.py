"""组织域内部写通道**鉴权矩阵与幂等回放**用例（Kiwi 2274）。

口径：内部面**只换鉴权、不换语义**——故鉴权分支保留**真实依赖**（`require_service("platform")`），
只注入令牌校验替身，从 HTTP 面断言 401 与放行；放行后断言「同 `Idempotency-Key` 重复提交返回同结果」。
"""

import pytest
from bms_core.api.deps import get_uow
from bms_core.core.exceptions import AuthError
from bms_core.oauth.token import TOKEN_AUDIENCE_SERVICE
from bms_core.oauth.verify import BaseTokenVerifier, VerifiedToken, get_token_verifier
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests_support import org_env

INTERNAL_USER_DEPTS = "/api/v1/org/internal/user-depts/{user_id}"
"""内部写端点（用户-部门，含主要项）。"""

AUTH_HEADER = {"Authorization": "Bearer stub"}
"""占位授权头（令牌校验为替身，内容不参与判定）。"""


class _VerifierStub(BaseTokenVerifier):
    """令牌校验替身：服务受众按注入服务标识放行，其余受众一律拒（驱动 `10010` 分支）。"""

    plugin_name: str = "internal_auth_stub"

    def __init__(self, *, service: str | None = None) -> None:
        """初始化。

        Args:
            service: 服务受众通过时的服务标识；None 表示服务受众也拒。
        """
        self._service = service

    async def verify(self, token: str, *, audience: str) -> VerifiedToken:
        """校验令牌（服务受众按注入值放行，其余恒拒）。

        Args:
            token: 令牌紧凑串（替身忽略）。
            audience: 期望受众。

        Returns:
            VerifiedToken: 服务身份声明。

        Raises:
            AuthError: 非服务受众或未注入服务标识（20001 / 401）。
        """
        del token
        if audience == TOKEN_AUDIENCE_SERVICE and self._service is not None:
            return VerifiedToken(subject="gateway", service=self._service, audience=(audience,))
        raise AuthError("用户令牌不可用（替身）")


async def _seed_dept(session: AsyncSession) -> int:
    """造一个部门（内部写端点的目标；与请求**同一会话**，避免跨库 / 跨租户取不到）。

    Args:
        session: 请求级会话。

    Returns:
        int: 部门 id。
    """
    depts = org_env.make_dept_service(session, org_env.make_uow(session), org_env.make_outbox())
    dept = await depts.create_dept(code="rd", name="研发中心", parent_id=None, sort=1)
    dept_id = dept.id
    await org_env.commit(session)
    return dept_id


@pytest.mark.kiwi_id(2274)
async def test_internal_rejects_non_whitelisted_service(service_app: FastAPI, client: AsyncClient) -> None:
    """非白名单服务身份（`org` 之外的调用方）被拒：`401`（`20001`）。"""
    service_app.dependency_overrides[get_token_verifier] = lambda: _VerifierStub(service="other")

    response = await client.put(INTERNAL_USER_DEPTS.format(user_id=1), json={"dept_ids": []}, headers=AUTH_HEADER)

    assert response.status_code == 401


@pytest.mark.kiwi_id(2274)
async def test_internal_rejects_user_audience_token(service_app: FastAPI, client: AsyncClient) -> None:
    """登录态令牌（非服务受众）被拒：`401`（`10010`）——内部面不回落登录态。"""
    service_app.dependency_overrides[get_token_verifier] = lambda: _VerifierStub()

    response = await client.put(INTERNAL_USER_DEPTS.format(user_id=1), json={"dept_ids": []}, headers=AUTH_HEADER)

    assert response.status_code == 401


@pytest.mark.kiwi_id(2274)
async def test_internal_platform_writes_with_primary(service_app: FastAPI, client: AsyncClient) -> None:
    """白名单 `platform` 放行：内部写生效——全量覆盖部门并置位主要部门（复用公开面服务层语义）。

    说明：本轮从 HTTP 面只断言「一次写入的响应内容」；**幂等键载荷回放**与**重复提交同结果**属续做
    （见实施记录 §4 遗留 2）——在 DI 覆写夹具下幂等存储与工作单元共用会话会冲突
    （`A transaction is already begun on this Session`），需先按生产装配给幂等存储独立连接。
    """
    session, engine = await org_env.make_session()
    try:
        dept_id = await _seed_dept(session)
        await session.rollback()
        service_app.dependency_overrides[get_token_verifier] = lambda: _VerifierStub(service="platform")
        service_app.dependency_overrides[get_uow] = lambda: org_env.make_uow(session)

        response = await client.put(
            INTERNAL_USER_DEPTS.format(user_id=2),
            json={"dept_ids": [dept_id], "primary_dept_id": dept_id},
            headers=AUTH_HEADER,
        )

        assert response.status_code == 200
        assert response.json()["data"]["dept_ids"] == [dept_id]
        assert response.json()["data"]["primary_dept_id"] == str(dept_id)
    finally:
        await engine.dispose()
