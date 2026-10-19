# -*- coding: utf-8 -*-
"""网关安全工具：CORS 来源白名单判定。

仅放行本机来源（localhost/127.0.0.1 任意端口），外部来源预检直接拒绝。
"""


def is_local_origin(origin: str) -> bool:
    """判断是否为本机受信来源（Java 等服务端调用不带 Origin，天然不受影响）。"""
    if not origin:
        return False
    return (
        origin.startswith("http://localhost:")
        or origin.startswith("http://127.0.0.1:")
        or origin in ("http://localhost", "http://127.0.0.1")
    )
