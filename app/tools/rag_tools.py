# -*- coding: utf-8 -*-
"""RAG 相关 MCP 工具：知识库创建、入库、检索、人才搜索、简历问答、读简历。

工具名即对外注册名，必须与 Java 网关 callTool 的名字严格一致，禁止改名。
本层只做参数透传与日志，业务逻辑全部在 services.knowledge_service。
"""
import logging

from app.services import knowledge_service
from app.tools.mcp_instance import mcp


@mcp.tool()
def rag_create_knowledge(knowledge_id: str, knowledge_name: str, description: str = "") -> str:
    """创建知识库主记录，写入rag_knowledge表"""
    return knowledge_service.create_knowledge(knowledge_id, knowledge_name, description)


@mcp.tool()
def rag_knowledge_store_resume(knowledge_id: str, resume_text: str, source_file_name: str = "") -> str:
    """对传入的文档文本做分片、向量化，写入rag_doc_chunk表。
    knowledge_id 由 Java 传入，优先使用 Java 传过来的 ID。"""
    return knowledge_service.store_resume(knowledge_id, resume_text, source_file_name)


@mcp.tool()
def rag_knowledge_search_multi(knowledge_id_list: list[str], query_text: str, top_k: int = 3) -> str:
    """批量在多个知识库检索简历分片"""
    return knowledge_service.search_multi(knowledge_id_list, query_text, top_k=top_k)


@mcp.tool()
def rag_search_candidates(jd_text: str, top_n: int = 5) -> str:
    """人才库语义搜索：用JD在全库简历中向量召回，按简历聚合评分并排名。
    返回JSON：{"candidates":[{"rank","knowledge_id","knowledge_name","score",
    "match_level","matched_snippets"}]}"""
    return knowledge_service.search_candidates(jd_text, top_n=top_n)


@mcp.tool()
def rag_resume_chat(question: str, knowledge_id_list: list[str] | None = None,
                    top_k: int = 3) -> dict:
    """基于简历知识库的RAG问答（检索+大模型生成）。
    返回 {"answer","sources":[...],"hit":bool}，只依据简历内容回答，不编造。"""
    return knowledge_service.resume_chat(question, knowledge_id_list, top_k=top_k)


@mcp.tool()
def read_resume(path: str, knowledge_id: str | None = None) -> str:
    """读取简历文件。
    传入 knowledge_id：读完自动分片存入 rag_doc_chunk；
    不传：Python 自动生成全新 UUID 入库。
    ⚠️ 每个新简历必须使用全新 knowledge_id，禁止使用 resume_001。"""
    return knowledge_service.read_and_store(path, knowledge_id)



