# -*- coding: utf-8 -*-
"""网关作为 MCP 客户端调用 8604 服务的公共方法。

链路：SSE 建连 -> initialize 握手 -> call_tool -> 提取文本结果。
endpoint 固定读 config.MCP_SSE_ENDPOINT（http://127.0.0.1:8604/sse）。
"""
import asyncio
import logging

from mcp import ClientSession
from mcp.client.sse import sse_client

from app.config import MCP_SSE_ENDPOINT


async def call_mcp_tool_common(tool_name: str, params: dict, timeout: int = 120) -> str:
    """调用 8604 上的 MCP 工具，返回文本结果。失败抛异常，由调用方兜底。"""
    logging.info("【MCP客户端调用】tool=%s, endpoint=%s", tool_name, MCP_SSE_ENDPOINT)

    async def _call() -> str:
        async with sse_client(MCP_SSE_ENDPOINT) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, params)
                # FastMCP 返回 content 列表，拼接所有 text 块
                parts = [c.text for c in result.content if getattr(c, "text", None)]
                return "\n".join(parts) if parts else str(result.content)

    return await asyncio.wait_for(_call(), timeout=timeout)
