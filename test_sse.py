# -*- coding: utf-8 -*-
"""
测试 MCP SSE 连接是否可用
"""
import requests
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

url = "http://127.0.0.1:8604/sse"
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
