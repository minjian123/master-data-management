"""ASGI 入口：模块级应用实例（`uvicorn mdm_org.asgi:app`，工作目录为 `backend/`）。"""

from mdm_org.main import ApplicationFactory

app = ApplicationFactory().create(None)
