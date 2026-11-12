# -*- coding: utf-8 -*-
"""AI 简历分析系统应用包。

分层结构：
    core/          基础设施（配置消费、数据库连接池、日志、LLM 客户端）
    repositories/  数据访问层（只放 SQL，不写业务逻辑）
    services/      业务服务层（文档解析、向量化、知识库、RAG 问答）
    workflows/     LangGraph 工作流（Agent / 雷达图 / JD 匹配）
    tools/         MCP 工具注册层（FastMCP 单例 + 对外暴露的工具）
    gateway/       FastAPI HTTP 网关（对接 JeecgBoot 前端）
"""

__version__ = "1.0.0"
