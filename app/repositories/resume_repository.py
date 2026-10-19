# -*- coding: utf-8 -*-
"""resume（简历业务表）数据访问：主要用于知识库关联补全。"""
from app.core.db import db_cursor


def find_missing_knowledge_id() -> list[dict]:
    """查询缺 knowledge_id 的有效简历记录。"""
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT id, resume_name, resume_file, resume_path, knowledge_id
            FROM resume
            WHERE del_flag = 0 AND (knowledge_id IS NULL OR knowledge_id = '')
            ORDER BY id
            """
        )
        return cur.fetchall()


def update_knowledge_id(resume_id, knowledge_id: str) -> None:
    """回写某条简历的知识库ID（运维补数据用，调用方控制事务边界时自行循环）。"""
    with db_cursor() as cur:
        cur.execute(
            "UPDATE resume SET knowledge_id = %s WHERE id = %s",
            (knowledge_id, resume_id),
        )


def bulk_update_knowledge_id(pairs: list[tuple[str, int]]) -> int:
    """单事务批量回写 knowledge_id。

    :param pairs: [(knowledge_id, resume_id), ...]
    :return: 更新条数
    """
    with db_cursor() as cur:
        for knowledge_id, resume_id in pairs:
            cur.execute(
                "UPDATE resume SET knowledge_id = %s WHERE id = %s",
                (knowledge_id, resume_id),
            )
    return len(pairs)
