# -*- coding: utf-8 -*-
"""rag_doc_chunk（简历分片 + 向量）数据访问。"""
import uuid

from app.core.db import db_cursor


def batch_insert_chunks(knowledge_id: str, chunks_with_vectors: list[tuple],
                        source_file_name: str, create_time: str,
                        create_by: str = "mcp-service") -> int:
    """批量插入分片。

    :param chunks_with_vectors: [(chunk_index, chunk_text, embedding_json), ...]
    外层 service 已保证向量生成成功；本函数与向量生成处于同一业务流程，
    失败由 db_cursor 自动回滚，绝不写入空向量垃圾数据。
    """
    sql = """
        INSERT INTO rag_doc_chunk
            (id, knowledge_id, chunk_index, chunk_text, source_file_name,
             embedding, create_by, create_time, del_flag)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0)
    """
    with db_cursor() as cur:
        for idx, chunk_text, embedding_json in chunks_with_vectors:
            cur.execute(sql, (
                uuid.uuid4().hex,
                knowledge_id,
                idx,
                chunk_text,
                source_file_name,
                embedding_json,
                create_by,
                create_time,
            ))
    return len(chunks_with_vectors)


def fetch_chunks(knowledge_id_list: list[str] | None = None) -> list[dict]:
    """检索有效分片（del_flag=0）。

    传空/None 时检索全部分片（人才库全库搜索用）；非空时按知识库过滤。
    """
    with db_cursor() as cur:
        if knowledge_id_list:
            placeholders = ",".join(["%s"] * len(knowledge_id_list))
            cur.execute(
                f"SELECT knowledge_id, chunk_text, embedding FROM rag_doc_chunk "
                f"WHERE knowledge_id IN ({placeholders}) AND del_flag=0",
                knowledge_id_list,
            )
        else:
            cur.execute(
                "SELECT knowledge_id, chunk_text, embedding FROM rag_doc_chunk "
                "WHERE del_flag=0"
            )
        return cur.fetchall()


def fetch_chunks_by_knowledge_id(knowledge_id: str) -> list[dict]:
    """只读查询单个知识库的全部分片（验证脚本用）。"""
    with db_cursor() as cur:
        cur.execute(
            "SELECT id, knowledge_id, chunk_text, embedding "
            "FROM rag_doc_chunk WHERE knowledge_id=%s AND del_flag=0",
            (knowledge_id,),
        )
        return cur.fetchall()



