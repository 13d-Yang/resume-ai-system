# -*- coding: utf-8 -*-
"""FastAPI HTTP 网关入口（端口 8501，对接 JeecgBoot 前端）。

启动方式（项目根目录执行）：
    python -m app.server_gateway
请先启动 app.server_mcp（8604），再启动本网关。
"""
import uvicorn

from app.config import HOST, PORT_FASTAPI
from app.core.logging_setup import configure_logging
from app.gateway.app_factory import create_app

configure_logging()

app = create_app()


def main() -> None:
    uvicorn.run(app, host=HOST, port=PORT_FASTAPI)


if __name__ == "__main__":
    main()
