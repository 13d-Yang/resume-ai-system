# -*- coding: utf-8 -*-
"""FastAPI 应用工厂：装配 CORS 安全中间件与简历 AI 路由。"""
from fastapi import FastAPI, Request, Response

from app.gateway.routes import resume_ai
from app.gateway.security import is_local_origin


def create_app() -> FastAPI:
    app = FastAPI(title="MCP管理服务")

    @app.middleware("http")
    async def add_cors_headers(request: Request, call_next):
        # 仅对白名单内的本机来源回跨域头；Java 等服务端调用不带 Origin，不受影响
        origin = request.headers.get("origin", "")
        allow_origin = origin if is_local_origin(origin) else None

        # OPTIONS 预检：白名单外来源直接拒绝
        if request.method == "OPTIONS":
            if allow_origin:
                return Response(
                    status_code=200,
                    headers={
                        "Access-Control-Allow-Origin": allow_origin,
                        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                        "Access-Control-Allow-Headers": "*",
                        "Access-Control-Allow-Credentials": "true",
                        "Access-Control-Max-Age": "86400",
                    },
                )
            return Response(status_code=403)

        response = await call_next(request)
        if allow_origin:
            response.headers["Access-Control-Allow-Origin"] = allow_origin
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "*"
            response.headers["Access-Control-Allow-Credentials"] = "true"
        return response

    app.include_router(resume_ai.router)
    return app
