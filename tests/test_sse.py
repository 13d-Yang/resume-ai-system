# -*- coding: utf-8 -*-
"""MCP SSE 连通性冒烟测试（需要 8604 服务已启动，非单元测试，不进 CI）。

用法（项目根目录）：
    python tests/test_sse.py
"""
import os
import sys

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from app.config import HOST, PORT_MCP_ALL  # noqa: E402

url = f"http://{HOST}:{PORT_MCP_ALL}/sse"
print(f"测试连接: {url}")

try:
    resp = requests.get(url, stream=True, timeout=5)
    print(f"状态码: {resp.status_code}")
    print(f"响应头: {dict(resp.headers)}")
    print("\n前5行数据:")
    for i, line in enumerate(resp.iter_lines()):
        if i >= 5:
            break
        if line:
            print(f"  {line.decode('utf-8')}")
except Exception as e:
    print(f"连接失败: {e}")
