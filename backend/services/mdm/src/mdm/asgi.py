"""ASGI 入口：模块级应用实例（`uvicorn mdm.asgi:app`，工作目录为 `backend/`）。"""

from mdm.main import ApplicationFactory

app = ApplicationFactory().create(None)
