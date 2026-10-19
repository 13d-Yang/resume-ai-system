# -*- coding: utf-8 -*-
"""FastMCP 全局单例。所有工具模块共享同一个实例，禁止重复创建。"""
from mcp.server.fastmcp import FastMCP

from app.config import HOST, PORT_MCP_ALL

mcp = FastMCP("简历综合MCP", host=HOST, port=PORT_MCP_ALL)
