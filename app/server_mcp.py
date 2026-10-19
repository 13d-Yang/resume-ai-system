# -*- coding: utf-8 -*-
"""MCP SSE 服务入口（端口 8604）。

启动方式（项目根目录执行）：
    python -m app.server_mcp

导入 tools 子模块即触发 @mcp.tool() 注册，随后启动 SSE 传输。
"""
import sys

from app.config import HOST, PORT_MCP_ALL
from app.core.logging_setup import configure_logging

configure_logging()

# 顺序很重要：先导入工具模块完成注册，再取 mcp 单例
from app.tools import analysis_tools, rag_tools  # noqa: F401,E402
from app.tools.mcp_instance import mcp  # noqa: E402


def main() -> None:
    sys.stderr.write("\n" + "=" * 60 + "\n")
    sys.stderr.write(f"✅ MCP SSE服务启动 http://{HOST}:{PORT_MCP_ALL}/sse\n")
    sys.stderr.write("⚠️  read_resume传入knowledge_id参数才会自动分片入库rag_doc_chunk\n")
    sys.stderr.write("=" * 60 + "\n\n")
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()
