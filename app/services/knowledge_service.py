# -*- coding: utf-8 -*-
"""知识库 / RAG 业务服务：入库、语义检索、人才聚合、简历问答。

职责边界：
- 只编排 repositories（SQL）+ embedding_service（向量）+ core.llm（生成）；
- 事务由 db_cursor 统一控制：向量生成失败则不写任何分片，杜绝空向量垃圾数据。
"""
import json
import logging
import os
import re
import uuid
from datetime import datetime

from app.core.llm import ai_call, analyze_resume_text
from app.repositories import chat_history_repository, chunk_repository, knowledge_repository
from app.services.document_parser import read_local_resume
from app.services.embedding_service import (
    cosine_similarity,
    get_cloud_embedding,
    get_cloud_embeddings_batch,
    split_resume_text,
)


# ===================== 知识库主表 =====================
def get_knowledge_names(knowledge_ids: list[str]) -> dict[str, str]:
    """批量取知识库展示名（优先简历真名，回退文件名）"""
    return knowledge_repository.get_display_name_map(knowledge_ids)


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
        # 1. 文本分片（先按章节标题语义切，切不动再退回标点分片）
        chunks = split_resume_text(resume_text)
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
# 全文回退的字数上限：单份简历通常 3000~6000 字，多份拼接时截断防上下文溢出
FULL_TEXT_LIMIT = 12000

# 综合性问题特征：需要通读整份简历才能下结论，靠局部片段必然答不全。
# 除标准评价词外，也覆盖口语化问法（"这份简历是不是很好用""他靠谱吗"）
_COMPREHENSIVE_PATTERN = re.compile(
    r"评分|打分|评个分|打个分|给个分|分数|多少分|几分|评价|评估|整体|全局|综合|总结|概括|"
    r"优缺点|值不值得|推荐|水平如何|怎么样|如何评价|"
    r"好用|好不好|值得|适合|靠谱|竞争力|强不强|优秀|"
    r"能不能|会不会|能否|是否|建议|判断|"
    r"哪些技术|哪些技能|技术栈|技能|会什么|掌握"
)


def _is_comprehensive(question: str) -> bool:
    return bool(_COMPREHENSIVE_PATTERN.search(question or ""))


# 评分类问句：输出形态确定（必须给数字分数），应交给固定流程而非模型判断
_SCORE_PATTERN = re.compile(r"评分|打分|评个分|打个分|给个分|分数|多少分|几分")


def detect_intent(question: str) -> str:
    """确定性意图路由：按"输出形态"分流，不依赖模型自主判断。

    score    → 必须给出数字分数，走雷达图固定流程
    analysis → 需要通读全文判断评价，走全文分析
    fact     → 具体事实，走检索问答
    规则只覆盖形态确定的问法；覆盖不到的照旧交给 Agent 兜底。
    """
    q = question or ""
    if _SCORE_PATTERN.search(q):
        return "score"
    if _is_comprehensive(q):
        return "analysis"
    return "fact"


# 寒暄/对话本身类问句：不需要检索简历，应按对话方式回应
# 纯寒暄用整句锚定（"你好""谢谢"），避免"谢谢，那他会Python吗"这类
# 带寒暄的真实问题被误判成寒暄而跳过检索
_CONVERSATIONAL_PATTERN = re.compile(
    r"^(你好|您好|hi|hello|在吗|在不在|早上好|中午好|下午好|晚上好|谢谢|感谢|辛苦了)"
    r"[！!。.，,？?~～\s]*$"
    r"|你(能|会|可以)做(什么|啥)|你是谁|你叫什么|"
    r"我问(你|了)|我(之前|刚刚|刚才)问|刚才(问|说)|前面(聊|说)|上一?[句轮条]|"
    r"随便聊|聊聊天|还在吗"
)


def is_conversational(question: str) -> bool:
    """判断是否为寒暄或关于对话本身的问题。
    这类问题不应触发简历检索，也不该被全文兜底强行改写成简历分析。"""
    q = (question or "").strip()
    return len(q) <= 25 and bool(_CONVERSATIONAL_PATTERN.search(q))


# 拒答特征：模型用这些措辞回避作答
_REFUSAL_PATTERN = re.compile(r"未提及|没有提及|没有检索到|无法据此回答|未涉及")


def _is_refusal(answer: str) -> bool:
    """判断模型是否在拒答。只在短文本上判定，避免把包含"未提及"的长篇分析误杀。"""
    return bool(_REFUSAL_PATTERN.search(answer or "")) and len(answer or "") < 120


def _load_full_text(knowledge_id_list: list[str]) -> str:
    """按知识库ID顺序拼接分片为简历全文，超长截断。供 RAG 无命中时兜底。"""
    parts, total = [], 0
    for kid in knowledge_id_list:
        text = get_resume_text(kid)
        # get_resume_text 找不到分片时返回的是提示文案，不是简历内容，需跳过
        if not text or "未找到 knowledge_id" in text:
            continue
        parts.append(text)
        total += len(text)
        if total >= FULL_TEXT_LIMIT:
            break
    return "\n\n".join(parts)[:FULL_TEXT_LIMIT]


def _answer_resume_question(question: str, context_title: str,
                            context: str, sources: list[dict],
                            strict: bool = True) -> dict:
    """统一的简历问答生成入口，按上下文类型自动切换回答规则：

    - strict=True（片段模式）：只依据检索到的局部片段，无直接依据必须拒答，
      防止把"没检索到"当成"没有"；
    - strict=False（全文模式）：已拿到完整简历，允许基于全文做判断、评价、建议，
      只有全文确实没有线索时才说"未提及"。若沿用片段模式的严苛规则，
      模型即使拿到全文也不敢回答"能否找到好工作"这类判断性问题。
    """
    if strict:
        rules = f"""1. 最高优先级：只依据【{context_title}】中的实际内容作答。如果没有与问题直接相关的
   信息，必须回答"简历中未提及该信息"，此时不要再补充任何解释或推断；
2. 严禁根据标题出现次数、重复频率、格式特征等表面信息做任何推断或联想，
   例如"标题重复出现可推断……"这类结论一律禁止，编造依据比不回答更严重；
3. 当有明确、直接的依据时，才用完整的句子回答：先给出结论，
   再引用原文作支撑；
4. 使用中文回答。"""
        system_prompt = (
            "你是严谨的简历问答助手。你的第一准则是：简历内容里没有的信息"
            "一律回答\"简历中未提及该信息\"，绝不编造、绝不推断。"
            "只有在有直接依据时才展开回答，回答需包含结论和原文依据。"
        )
    else:
        rules = f"""1. 你拿到的是候选人的完整简历【{context_title}】，你的任务是回答问题并给出专业判断，不是做原文检索；
2. 对"能不能/会不会/是否/怎么样/好不好/值不值得"这类问题，即使简历没有逐字写明，
   也必须基于简历中的事实（技能栈、项目经验、工作年限、行业背景）给出明确结论和理由；
3. 严禁用"简历中未提及"敷衍能力、意愿、发展、竞争力、岗位适配类问题；
   该说法只允许用于与候选人职业能力完全无关的问题（例如身高、婚姻状况）；
4. 严格区分事实与分析：引用简历原文的部分作为事实依据，基于事实得出的判断要明确写成
   "分析/推断"，并给出支撑理由；
5. 严禁编造简历中不存在的具体经历、技能、证书或数据；
6. 使用中文回答，把结论与理由融进一段自然流畅的分析里，不要用单独一行的标签式结论；必要时给风险提示或建议；
7. 用户问题可能有错别字或表述不清，按最可能的真实意图理解，不要逐字抠字面；
   若歧义影响结论，先用一句话说明你的理解再作答。"""
        system_prompt = (
            "你是一位资深职业顾问，擅长基于候选人完整简历给出专业判断与建议。"
            "你的职责是分析，而不是复述简历或回避问题：对能力、意愿、发展潜力、"
            "岗位适配类问题，必须给出明确的分析结论，并用简历中的具体事实作为理由。"
            "回答用自然语言直接展开，不要用\"较难\"\"能做\"这类单独一行的标签式结论开头。"
            "只有问题与职业能力完全无关时才回答"
            "\"简历中未提及该信息\"。你可以基于事实做合理推断，但绝不能编造简历中"
            "不存在的经历、技能、证书或数据。"
        )

    prompt = f"""请依据下面提供的简历内容回答用户问题。

【回答要求】
{rules}

【{context_title}】
{context}

【用户问题】
{question}"""

    # 全文模式下把硬性要求放在最后一行：简历全文很长，会把中段的规则推远，
    # 模型对末尾指令更敏感，能显著降低"握着全文仍答未提及"的概率
    if not strict:
        prompt += ("\n\n若问题与候选人的职业能力相关，请直接给出明确结论，"
                   "禁止用\"简历中未提及\"回避；若信息不完整，也要基于事实给出"
                   "最可能的判断与理由。但若问题与简历内容完全无关"
                   "（如询问简历中不可能出现的生活技能），直接一句话说明"
                   "简历中没有该信息即可，不要为此展开分析。"
                   "若用户明确要求打分或评分，必须给出具体的数字分数（百分制），"
                   "再展开评分理由，不能只写文字评价。")

    answer = ai_call(prompt, system_prompt=system_prompt)
    # 兜底一：综合/能力类问题偶发仍拒答时，用极简 prompt 再压一次。
    # 长上下文是拒答的主要诱因，这里去掉冗长规则、只留简历+问题+硬指令。
    # 注意：事实性问题（如"会做锅包肉吗"）查完全文后确认没有，
    # "未提及"本身就是正确答案，严禁触发重试或分析兜底
    if not strict and _is_refusal(answer) and _is_comprehensive(question):
        logging.warning("【简历问答】全文模式下模型仍拒答，启用强指令重试")
        answer = ai_call(
            f"候选人简历如下：\n{context}\n\n"
            f"请回答这个问题：{question}\n"
            f"要求：用自然语言直接回答问题，结论融入正文，不要用\"较难\"\"能做\""
            f"这类单独一行的标签开头；再用简历中的具体事实作为理由。"
            f"严禁回答\"简历中未提及\"。",
            system_prompt=system_prompt,
        )
    # 兜底二：重试仍拒答、且确属需要给出判断的综合类问题时，才改用通用分析工具，
    # 宁可给出通用但专业的分析，也不让用户只收到"未提及"；
    # 事实性问题的"未提及"是正确结论，直接返回，绝不可升级为分析报告
    if not strict and _is_refusal(answer) and _is_comprehensive(question):
        logging.warning("【简历问答】重试仍拒答，改用通用分析工具兜底")
        answer = (f"针对「{question}」，基于这份简历的综合分析如下：\n\n"
                  + analyze_resume_text.invoke(context))
    return {"answer": answer, "sources": sources, "hit": True}


def resume_chat(question: str, knowledge_id_list: list[str] | None = None,
                top_k: int = 3) -> dict:
    """基于简历知识库的问答（检索 + 大模型生成，完整闭环）。

    只依据简历内容作答；无依据时明确说"未提及"，杜绝编造。
    语义检索对短问句（"会做电商吗""英语水平如何"）区分度低，0.45 阈值下
    容易被判无命中；因此检索无命中时回退为"读全文作答"——一份简历的全文
    完全在上下文预算内，比直接拒答更有价值。
    """
    logging.info("【rag_resume_chat】question=%s, kb=%s", question, knowledge_id_list)

    # 综合性问题（评分/评价/总结/水平如何）需要通读全文才能下结论。
    # 局部片段命中再准也不够，直接用全文，避免出现"只取到学历片段就答未提及"的错误
    if knowledge_id_list and _is_comprehensive(question):
        full_text = _load_full_text(knowledge_id_list)
        if full_text:
            logging.info("【rag_resume_chat】综合性问题，改用全文作答，全文长度=%d",
                         len(full_text))
            sources = [{
                "index": 1,
                "knowledge_id": knowledge_id_list[0],
                "score": 1.0,
                "snippet": full_text[:80],
                "content": full_text,
            }]
            return _answer_resume_question(question, "简历全文", full_text, sources,
                                           strict=False)

    relevance_cutoff = 0.45
    hits = retrieve(knowledge_id_list or [], question, top_k=top_k)
    hits = [h for h in hits if h["score"] >= relevance_cutoff]

    if hits:
        context_blocks, sources = [], []
        for i, hit in enumerate(hits, 1):
            context_blocks.append(f"[片段{i}] {hit['chunk_text']}")
            sources.append({
                "index": i,
                "knowledge_id": hit["knowledge_id"],
                "score": round(hit["score"], 3),
                "snippet": (hit["chunk_text"] or "")[:80],
                "content": hit["chunk_text"] or "",
            })
        result = _answer_resume_question(
            question, "简历片段", "\n\n".join(context_blocks), sources)
        # 片段命中了，但命中片段本身不含答案（例如问"会哪些技术"，捞到的却是
        # 教育背景片段），严格模式就会答"未提及"。这种"命中≠答得出"必须回退全文，
        # 否则会出现检索分数过线反而答不出来的假拒答
        if _is_refusal(result.get("answer", "")) and knowledge_id_list:
            full_text = _load_full_text(knowledge_id_list)
            if full_text:
                logging.info("【rag_resume_chat】片段命中但未答出，回退全文重答，"
                             "全文长度=%d", len(full_text))
                full_sources = [{
                    "index": 1,
                    "knowledge_id": knowledge_id_list[0],
                    "score": 1.0,
                    "snippet": full_text[:80],
                    "content": full_text,
                }]
                return _answer_resume_question(question, "简历全文", full_text,
                                               full_sources, strict=False)
        return result

    # RAG 无命中：指定了简历ID时回退全文模式，避免"检索不到就拒答"
    full_text = _load_full_text(knowledge_id_list) if knowledge_id_list else ""
    if full_text:
        logging.info("【rag_resume_chat】RAG无命中，回退全文模式，全文长度=%d",
                     len(full_text))
        sources = [{
            "index": 1,
            "knowledge_id": knowledge_id_list[0],
            "score": 1.0,
            "snippet": full_text[:80],
            "content": full_text,
        }]
        return _answer_resume_question(question, "简历全文", full_text, sources,
                                       strict=False)

    return {
        "answer": "简历库中没有检索到与该问题相关的内容，无法据此回答。",
        "sources": [],
        "hit": False,
    }


# ===================== 按 ID 读取简历全文 =====================
def get_resume_text(knowledge_id: str) -> str:
    """按 knowledge_id 读取全部分片并按顺序拼回简历全文（Agent 工具用）。"""
    logging.info("【get_resume_text】knowledge_id=%s", knowledge_id)
    rows = chunk_repository.fetch_chunks_by_knowledge_id(knowledge_id)
    if not rows:
        return (
            f"未找到 knowledge_id={knowledge_id} 对应的简历分片。"
            f"这不是有效的简历ID，请勿再用其他文字尝试本工具；"
            f"如果用户消息中已包含简历全文，直接使用该文本继续任务。"
        )
    return "\n".join(row["chunk_text"] for row in rows)


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


# ===================== 问答历史：持久化记录与回显 =====================
def save_chat_record(session_id: str, question: str, answer: str,
                     knowledge_id: str = "") -> None:
    """保存一条问答记录；无 session_id 时跳过，避免脏数据。"""
    if not session_id or not question.strip():
        return
    chat_history_repository.insert_record(session_id, question, answer, knowledge_id)


def get_chat_history(session_id: str, limit: int = 30,
                     knowledge_id: str = "") -> str:
    """按会话读取历史问答，供前端重新打开弹窗时回显。

    knowledge_id 非空时只回显该简历的问答：上下文记忆是 Agent 级的，
    但页面展示需要按当前简历隔离。
    """
    if not session_id:
        return json.dumps({"messages": []}, ensure_ascii=False)
    rows = chat_history_repository.list_by_session(
        session_id, limit=limit, knowledge_id=knowledge_id)
    messages = [
        {
            "question": row["question"],
            "answer": row["answer"] or "",
            "createTime": row["create_time"].strftime("%Y-%m-%d %H:%M:%S")
            if row["create_time"] else "",
        }
        for row in rows
    ]
    logging.info("【get_chat_history】session=%s 条数=%d", session_id, len(messages))
    return json.dumps({"messages": messages}, ensure_ascii=False)



