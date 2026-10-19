# -*- coding: utf-8 -*-
"""知识库 / RAG 业务服务：入库、语义检索、人才聚合、简历问答。

职责边界：
- 只编排 repositories（SQL）+ embedding_service（向量）+ core.llm（生成）；
- 事务由 db_cursor 统一控制：向量生成失败则不写任何分片，杜绝空向量垃圾数据。
"""
import json
import logging
import os
import uuid
from datetime import datetime

from app.core.llm import ai_call
from app.repositories import chunk_repository, knowledge_repository
from app.services.document_parser import read_local_resume
from app.services.embedding_service import (
    cosine_similarity,
    get_cloud_embedding,
    get_cloud_embeddings_batch,
    text_splitter,
)


# ===================== 知识库主表 =====================
def create_knowledge(knowledge_id: str, knowledge_name: str,
                     description: str = "") -> str:
    """写入 rag_knowledge 主表；已存在返回 "success: existed"，不重复插入。"""
    logging.info("【rag_create_knowledge】开始创建主记录 knowledge_id=%s", knowledge_id)
    try:
        if knowledge_repository.exists_by_id(knowledge_id):
            logging.info("知识库记录已存在，无需新增")
            return "success: existed"
        knowledge_repository.insert_knowledge(knowledge_id, knowledge_name, description)
        logging.info("【rag_create_knowledge】主表插入成功")
        return "success: created"
    except Exception as e:
        logging.error("创建知识库异常：%s", e)
        return f"fail:{str(e)}"


# ===================== 文档入库（分片 + 向量化） =====================
def store_resume(knowledge_id: str, resume_text: str,
                 source_file_name: str = "") -> str:
    """对文档文本分片、批量向量化、写入 rag_doc_chunk。

    knowledge_id 为空时由 Python 兜底生成（正常业务由 Java 传入）。
    """
    logging.info(
        "【rag_knowledge_store_resume入库开始】knowledge_id=%s, text_len=%s, source_file_name=%s",
        knowledge_id, len(resume_text), source_file_name,
    )

    if not knowledge_id:
        knowledge_id = str(uuid.uuid4())
        logging.warning("⚠️ Java未传入knowledge_id，Python兜底生成：%s", knowledge_id)

    if not resume_text or len(resume_text.strip()) < 5:
        logging.warning("【rag_knowledge_store_resume】❌简历文本过短，直接返回")
        return "❌简历文本过短"

    try:
        # 1. 文本分片
        chunks = text_splitter.split_text(resume_text)
        logging.info("分片完成，总分片数量：%s", len(chunks))

        # 2. 一次性批量向量化（失败直接终止，不再写入空向量垃圾数据）
        vectors = get_cloud_embeddings_batch(chunks)
        if len(vectors) != len(chunks):
            raise RuntimeError(
                f"向量数量({len(vectors)})与分片数量({len(chunks)})不一致"
            )
        logging.info("批量向量化完成，向量维度：%s", len(vectors[0]) if vectors else 0)

        now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = [
            (idx, chunk, json.dumps(vec_list))
            for idx, (chunk, vec_list) in enumerate(zip(chunks, vectors))
        ]

        # 3. 批量写库（同一事务，失败整体回滚）
        count = chunk_repository.batch_insert_chunks(
            knowledge_id, rows, source_file_name, now_time
        )
        logging.info("✅ 入库成功，knowledge_id=%s，分片数:%s", knowledge_id, count)
        return f"✅文档入库成功，knowledge_id:{knowledge_id}，分片{count}条"
    except Exception as e:
        logging.error("入库异常：%s", str(e))
        return f"❌入库失败：{str(e)}"


# ===================== 检索 =====================
def search_multi(knowledge_id_list: list[str], query_text: str,
                 top_k: int = 3) -> str:
    """在多个知识库检索分片，返回格式化文本（MCP 工具直出）。"""
    logging.info("【rag_knowledge_search_multi】检索知识库列表=%s, query=%s",
                 knowledge_id_list, query_text)
    if not knowledge_id_list:
        return "知识库列表为空，无法检索"
    try:
        scored = retrieve(knowledge_id_list, query_text, top_k=top_k)
        out = [
            f"【知识库{item['knowledge_id']}｜相似度{item['score']:.3f}】{item['chunk_text']}"
            for item in scored
        ]
        return "\n".join(out) if out else "没有检索到相关分片"
    except Exception as e:
        logging.exception("【多知识库检索异常】")
        return f"❌检索异常：{str(e)}"


def retrieve(knowledge_id_list, query_text: str, top_k: int = 3,
             min_score: float = 0.0) -> list[dict]:
    """内部语义检索：返回结构化结果。

    空列表检索全部知识库（人才搜索用）；非空时按库过滤。
    自动跳过空向量分片，低于 min_score 的不返回。
    """
    q_vec = get_cloud_embedding(query_text)
    rows = chunk_repository.fetch_chunks(knowledge_id_list or None)
    scored = []
    for row in rows:
        emb = json.loads(row["embedding"]) if row["embedding"] else []
        if not emb:
            continue
        sim = cosine_similarity(q_vec, emb)
        if sim >= min_score:
            scored.append({
                "score": sim,
                "knowledge_id": row["knowledge_id"],
                "chunk_text": row["chunk_text"],
            })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


# ===================== 人才库语义搜索 =====================
def search_candidates(jd_text: str, top_n: int = 5) -> str:
    """用 JD 在全库简历中向量召回，按简历聚合评分并排名，返回 JSON 字符串。

    综合分 = 该简历 top3 命中分片的平均相似度；同名简历去重保留最高分。
    """
    logging.info("【rag_search_candidates】jd=%s..., top_n=%s", jd_text[:60], top_n)
    try:
        # 1) 全库检索，取足够多的分片用于聚合
        hits = retrieve([], jd_text, top_k=50, min_score=0.30)
        if not hits:
            return json.dumps({"candidates": []}, ensure_ascii=False)

        # 2) 按知识库（简历）聚合
        grouped: dict[str, list] = {}
        for hit in hits:
            grouped.setdefault(hit["knowledge_id"], []).append(hit)

        # 3) 查简历名称：优先 resume.resume_name，回退 rag_knowledge.knowledge_name
        name_map = knowledge_repository.get_display_name_map(list(grouped.keys()))

        # 4) 综合分（top3 平均）+ 同名去重
        candidates = []
        for kid, chunks in grouped.items():
            chunks.sort(key=lambda x: x["score"], reverse=True)
            top3 = chunks[:3]
            score = round(sum(c["score"] for c in top3) / len(top3), 3)
            candidates.append({
                "knowledge_id": kid,
                "knowledge_name": name_map.get(kid, kid),
                "score": score,
                "matched_snippets": [
                    {"score": round(c["score"], 3), "text": c["chunk_text"][:120]}
                    for c in top3
                ],
            })
        best_by_name = {}
        for candidate in candidates:
            name = candidate["knowledge_name"]
            if name not in best_by_name or candidate["score"] > best_by_name[name]["score"]:
                best_by_name[name] = candidate
        candidates = sorted(
            best_by_name.values(), key=lambda x: x["score"], reverse=True
        )[:top_n]

        # 5) 排名 + 等级分档
        for i, candidate in enumerate(candidates):
            candidate["rank"] = i + 1
            if candidate["score"] >= 0.55:
                candidate["match_level"] = "强烈推荐"
            elif candidate["score"] >= 0.45:
                candidate["match_level"] = "可以考虑"
            else:
                candidate["match_level"] = "匹配度低"

        return json.dumps({"candidates": candidates}, ensure_ascii=False)
    except Exception as e:
        logging.exception("【rag_search_candidates执行异常】")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ===================== RAG 简历问答 =====================
def resume_chat(question: str, knowledge_id_list: list[str] | None = None,
                top_k: int = 3) -> dict:
    """基于简历知识库的 RAG 问答（检索 + 大模型生成，完整闭环）。

    只依据检索到的简历片段作答；无依据时明确说"未提及"，杜绝编造。
    """
    logging.info("【rag_resume_chat】question=%s, kb=%s", question, knowledge_id_list)

    relevance_cutoff = 0.35
    hits = retrieve(knowledge_id_list or [], question, top_k=top_k)
    hits = [h for h in hits if h["score"] >= relevance_cutoff]

    if not hits:
        return {
            "answer": "简历库中没有检索到与该问题相关的内容，无法据此回答。",
            "sources": [],
            "hit": False,
        }

    context_blocks = []
    sources = []
    for i, hit in enumerate(hits, 1):
        context_blocks.append(f"[片段{i}] {hit['chunk_text']}")
        sources.append({
            "index": i,
            "knowledge_id": hit["knowledge_id"],
            "score": round(hit["score"], 3),
            "snippet": (hit["chunk_text"] or "")[:80],
            "content": hit["chunk_text"] or "",
        })
    context = "\n\n".join(context_blocks)

    prompt = f"""请严格依据下面提供的简历片段回答用户问题。

【回答要求】
1. 只能使用【简历片段】中出现的信息，禁止使用片段之外的常识或猜测；
2. 如果片段中没有与问题相关的依据，必须直接回答"简历中未提及该信息"，不得编造；
3. 回答简洁明确，关键结论后用[片段x]标注信息来源；
4. 使用中文回答。

【简历片段】
{context}

【用户问题】
{question}"""

    answer = ai_call(
        prompt,
        system_prompt="你是严谨的简历问答助手。只依据给定简历片段作答，"
                      "片段里没有的信息一律回答“简历中未提及该信息”，绝不编造。",
    )
    return {"answer": answer, "sources": sources, "hit": True}


# ===================== read_resume：读文件 + 自动入库 =====================
def read_and_store(path: str, knowledge_id: str | None = None) -> str:
    """读取简历文件；传入 knowledge_id 时自动分片入库。

    ⚠️ 每个新简历必须使用全新 knowledge_id，重复 id 会追加到同一知识库；
    resume_001 为保留 ID，禁止使用。
    """
    if not knowledge_id:
        knowledge_id = str(uuid.uuid4())
        logging.info("【read_resume】未传入knowledge_id，Python自动生成id=%s", knowledge_id)

    if knowledge_id.strip() == "resume_001":
        logging.error("❌拦截！禁止使用resume_001作为知识库ID")
        return "错误：resume_001为保留ID，禁止使用，请传入全新的32位UUID"

    logging.info("【read_resume工具被调用】 path=%s, knowledge_id=%s", path, knowledge_id)

    text = read_local_resume(path)
    logging.info("【read_resume读取文件完成】读取文本长度=%s", len(text))

    if len(text.strip()) > 10:
        logging.info("【read_resume】准备执行分片入库！knowledge_id=%s", knowledge_id)
        # 先写主表（已存在则跳过），避免产生孤儿分片
        kb_result = create_knowledge(
            knowledge_id,
            knowledge_name=os.path.basename(path) or "未命名简历",
            description="由read_resume自动创建",
        )
        logging.info("【read_resume】主表写入结果: %s", kb_result)
        store_result = store_resume(knowledge_id, text, source_file_name=os.path.basename(path))
        logging.info("【read_resume】入库函数返回结果 >>> %s", store_result)
    else:
        logging.warning("【read_resume】文本太短，跳过入库，text长度:%s", len(text.strip()))

    return text



