# -*- coding: utf-8 -*-
"""rag_chat_history（简历问答历史表）数据访问。"""
import logging

from app.core.db import db_cursor


def insert_record(session_id: str, question: str, answer: str,
                  knowledge_id: str = "", create_by: str = "mcp-service") -> None:
    """写入一条问答记录。失败不抛异常，避免影响主流程作答。"""
    try:
        with db_cursor() as cur:
            cur.execute(
                """
                INSERT INTO rag_chat_history
                    (session_id, knowledge_id, question, answer, create_by, del_flag)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (session_id, knowledge_id or None, question, answer, create_by, 0),
            )
    except Exception:
        logging.exception("【rag_chat_history】写入失败 session=%s", session_id)


def list_by_session(session_id: str, limit: int = 30,
                    knowledge_id: str = "") -> list[dict]:
    """按会话倒序取最近的问答记录，返回时按时间正序排列。

    knowledge_id 非空时只取该简历的记录：会话（上下文记忆）是 Agent 级的，
    但页面回显需要按当前简历过滤，避免看到别的简历的问答。
    """
    sql = ("SELECT question, answer, knowledge_id, create_time "
           "FROM rag_chat_history "
           "WHERE session_id = %s AND del_flag = 0")
    params: list = [session_id]
    if knowledge_id:
        sql += " AND knowledge_id = %s"
        params.append(knowledge_id)
    sql += " ORDER BY id DESC LIMIT %s"
    params.append(limit)
    with db_cursor() as cur:
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
    return list(reversed(rows))
