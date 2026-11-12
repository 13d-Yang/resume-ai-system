# -*- coding: utf-8 -*-
"""MCP 工具注册层。

入口模块 app.server_mcp 导入 rag_tools / analysis_tools 即完成工具注册，
随后调用 mcp_instance.mcp.run(transport="sse") 启动服务。
"""
