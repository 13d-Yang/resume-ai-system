# -*- coding: utf-8 -*-
"""rag_knowledge（知识库主表）数据访问。"""
import logging

from app.core.db import db_cursor


def exists_by_id(knowledge_id: str) -> bool:
    """知识库主记录是否已存在。"""
    with db_cursor() as cur:
        cur.execute("SELECT id FROM rag_knowledge WHERE id = %s", (knowledge_id,))
        return cur.fetchone() is not None


def insert_knowledge(knowledge_id: str, knowledge_name: str,
                     description: str = "", create_by: str = "mcp-service") -> None:
    """插入知识库主记录（调用方应先用 exists_by_id 判重）。"""
    with db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO rag_knowledge
                (id, knowledge_name, description, create_by, del_flag)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (knowledge_id, knowledge_name, description, create_by, 0),
        )
    logging.info("【rag_knowledge】主表插入成功 knowledge_id=%s", knowledge_id)


def get_display_name_map(knowledge_ids: list[str]) -> dict[str, str]:
    """批量查知识库展示名。

    优先关联 resume 表取真名 resume_name；关联不上时回退到文件名 knowledge_name。
    """
    if not knowledge_ids:
        return {}
    with db_cursor() as cur:
        placeholders = ",".join(["%s"] * len(knowledge_ids))
        cur.execute(
            f"""
            SELECT k.id AS kid, k.knowledge_name, r.resume_name
            FROM rag_knowledge k
            LEFT JOIN resume r
              ON r.knowledge_id = k.id AND r.del_flag = 0
            WHERE k.id IN ({placeholders}) AND k.del_flag = 0
            """,
            knowledge_ids,
        )
        name_map = {}
        for row in cur.fetchall():
            name_map[row["kid"]] = row["resume_name"] or row["knowledge_name"]
        return name_map


def list_all_knowledge() -> list[dict]:
    """列出全部知识库（运维脚本补数据用）。"""
    with db_cursor() as cur:
        cur.execute("SELECT id, knowledge_name, description FROM rag_knowledge")
        return cur.fetchall()
