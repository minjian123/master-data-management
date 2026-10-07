"""组织主数据服务启动冒烟与产品服务装配（Kiwi 用例 2253）。"""

import pytest
from bms_core.services.module_registry import SERVICE_CATALOG
from bms_core.services.service_contract import service_route_sets
from fastapi import FastAPI
from httpx import AsyncClient

from mdm_org import SERVICE_NAME, SERVICE_TITLE


@pytest.mark.kiwi_id(2253)
async def test_service_boots_and_exposes_probes(service_app: FastAPI, client: AsyncClient) -> None:
    """应用可构造且标题就位；`/healthz` 存活并携带服务身份；`/readyz` 携带身份（依赖状态可 200 / 503）。"""
    assert service_app.title == SERVICE_TITLE
    healthz = await client.get("/healthz")
    readyz = await client.get("/readyz")
    root = await client.get("/")
    assert healthz.status_code == 200
    assert healthz.json()["service"] == SERVICE_NAME
    assert readyz.status_code in (200, 503)
    assert readyz.json()["service"] == SERVICE_NAME
    assert root.status_code == 200
    assert root.json()["data"]["name"] == SERVICE_TITLE


@pytest.mark.kiwi_id(2253)
async def test_assembly_declares_product_service_list(service_app: FastAPI) -> None:
    """装配：产品标识声明就位、注入清单非空且含运行服务行、应用级视图同值去重（不改变平台清单条目数）。"""
    assert service_app.state.service_product_key == "mdm"
    injected = service_app.state.service_injected_records
    assert [record.module_key for record in injected] == ["org"]
    assert injected[0].service_key == SERVICE_NAME
    merged = service_app.state.module_registry.catalog_records()
    # 注入行与平台侧 `org` 行逐字段同值 → 合并去重后条目数与平台清单一致，且顺序以平台清单在前
    assert len(merged) == len(SERVICE_CATALOG)
    assert merged[0].module_key == SERVICE_CATALOG[0].module_key


@pytest.mark.kiwi_id(2253)
async def test_routes_mount_under_service_namespace(service_app: FastAPI) -> None:
    """路由：探针与根路由由基座统一挂载；业务路由经服务级登记表聚合挂 `/api/v1`。

    本任务为工程骨架——**尚无业务端点**（组织主数据端点归 01_02 / 只读出口归 01_03），
    故 `/api/v1` 下暂无模块路由；待业务端点登记后本断言随之扩展。
    取路由经基座 `service_route_sets`（应用路由为惰性结构，直接读 `app.routes` 取不到路径）。
    """
    visible, invisible = service_route_sets(service_app)
    assert {"/", "/healthz", "/readyz"} <= visible
    assert [path for path in sorted(visible) if path.startswith("/api/v1")] == []
    assert "/metrics" in invisible


@pytest.mark.kiwi_id(2253)
def test_asgi_and_models_skeleton() -> None:
    """入口骨架：ASGI 模块级应用可构造；服务包声明空的模型模块清单（本期无业务表）。"""
    from mdm_org import asgi
    from mdm_org.models import MODEL_MODULES

    assert asgi.app.title == SERVICE_TITLE
    assert MODEL_MODULES == ()
