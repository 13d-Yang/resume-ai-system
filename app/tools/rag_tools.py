# -*- coding: utf-8 -*-
"""RAG 相关 MCP 工具：知识库创建、入库、检索、人才搜索、简历问答、读简历。

工具名即对外注册名，必须与 Java 网关 callTool 的名字严格一致，禁止改名。
本层只做参数透传与日志，业务逻辑全部在 services.knowledge_service。
"""
import json
import logging
import uuid

from langchain_core.messages import HumanMessage

from app.services import knowledge_service
from app.tools.mcp_instance import mcp
from app.workflows.agent_workflow import (
    agent_app,
    compare_resumes,
    extract_trace,
    strip_textual_tool_call,
)
from app.workflows.radar_workflow import radar_app

# 雷达图维度顺序与 radar_workflow 里 prompt 的顺序严格一致
_RADAR_DIMS = ["工作经验", "学历背景", "专业技能", "项目含金量", "沟通协作", "稳定性"]


def _format_radar(data: dict) -> str:
    """把雷达图 JSON 转成可读文本：格式由代码保证，不靠模型排版。"""
    lines = [f"综合评分：{data.get('totalScore', '-')} 分", ""]
    for name, score in zip(_RADAR_DIMS, data.get("scoreArr") or []):
        lines.append(f"- {name}：{score} 分")
    if data.get("advantage"):
        lines.append(f"\n优势：{data['advantage']}")
    if data.get("risk"):
        lines.append(f"风险：{data['risk']}")
    return "\n".join(lines)


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
                    top_k: int = 3, session_id: str = "") -> str:
    """简历问答（Agent模式）：LangGraph Agent 自主选择工具作答。
    事实性问题通常走 resume_qa（RAG检索），分析类任务可联动完整分析/雷达图等工具；
    resume_qa 返回JSON：answer/sources/hit，Agent 会原样输出。
    session_id 用于多轮会话记忆：同一会话传相同 ID，Agent 可记住上文。"""
    logging.info("【MCP调用】rag_resume_chat（Agent模式）question=%s session=%s",
                 question[:80], session_id)
    try:
        # 确定性路由：评分类问题直接走雷达图固定流程，不唤醒 Agent。
        # 模型"要分数却只给文字评价"这种偏差不该靠提示词纠正，
        # 输出形态确定的问法交给代码，语义不确定的才交给 Agent
        # 对比场景涉及多份简历，评分路由只应对单份生效
        if len(knowledge_id_list) == 1 and knowledge_service.detect_intent(question) == "score":
            resume_text = knowledge_service.get_resume_text(knowledge_id_list[0])
            if resume_text and "未找到" not in resume_text[:20]:
                logging.info("【rag_resume_chat】确定性路由→雷达图固定流程，简历长度=%d",
                             len(resume_text))
                radar = radar_app.invoke({"resume_text": resume_text})["radar_result"]
                answer = _format_radar(radar)
                knowledge_service.save_chat_record(
                    session_id, question, answer, knowledge_id_list[0])
                return json.dumps({
                    "answer": answer,
                    "sources": [],
                    "trace": [{"tool": "radar_generate",
                               "args": {"knowledge_id": knowledge_id_list[0]}}],
                }, ensure_ascii=False)
        # top_k 仅为兼容旧签名保留，Agent 模式下检索条数由 Agent 自主决定
        if len(knowledge_id_list) > 1:
            # 多份简历同一个 Agent 会话内对比，不拆成两个入口
            name_map = knowledge_service.get_knowledge_names(knowledge_id_list)
            id_list = "、".join(f"{kid}（{name_map.get(kid, '未命名简历')}）"
                                for kid in knowledge_id_list)
            input_text = (
                f"用户正在简历问答对话框中进行多份简历对比，涉及简历：{id_list}。"
                f"需要逐份调用 get_resume_text 取全文，再调用 compare_resumes 进行横向对比；"
                f"回答必须基于这些简历的真实内容，按候选人分别说明优势与短板，"
                f"并给出录用优先级建议。用户问题：{question}"
            )
        elif knowledge_id_list:
            input_text = (
                f"用户正在简历问答对话框中提问，当前简历ID：{','.join(knowledge_id_list)}。"
                f"注意：若用户这句话只是打招呼、寒暄、确认能否提问、表达感谢、"
                f"询问你能做什么，或与简历内容明显无关的闲聊，"
                f"请勿调用任何工具，直接用自然语言回应即可。"
                f"若用户在问对话本身（如\"我刚才问了什么\"\"我问了几个问题\"），"
                f"请依据对话历史如实回答其原话，不要要求用户重复。"
                f"若用户确实在询问这份简历的内容，请按工具选择指南判断用哪个工具："
                f"事实性问题用 resume_qa（需把该简历ID作为 knowledge_id 传入）；"
                f"评分/分析/评价/开放性主观判断（如\"这份简历是不是很好用\"）类问题，"
                f"必须先 get_resume_text 取全文，再调用 analyze_resume_text 等分析工具作答。"
                f"回答内容必须来自这份简历；不要介绍系统自身功能"
                f"（如RAG检索、LLM分析、雷达图、JD匹配），"
                f"用户问\"这份简历会哪些功能/能做什么\"时应理解为候选人的技能能力。"
                f"用户问题：{question}"
            )
        else:
            input_text = f"用户正在简历问答对话框中提问，请回答问题：{question}"
        # 有 checkpointer 后必须提供 thread_id；无 session_id 时用随机ID，退化为单次对话
        thread_id = session_id or f"once_{uuid.uuid4().hex}"
        # recursion_limit 是硬性循环上限：防止模型陷入无限调工具把额度烧穿
        result = agent_app.invoke(
            {"messages": [HumanMessage(content=input_text)]},
            config={"configurable": {"thread_id": thread_id},
                    "recursion_limit": 15},
        )
        last_msg = result["messages"][-1]
        answer = getattr(last_msg, "content", None) or str(last_msg)
        # 兜底：剔除残留的文本型工具调用，防止函数名+参数JSON裸露给用户
        answer = strip_textual_tool_call(answer)
        logging.info("【Agent循环完成】总消息条数=%d, 最终答案长度=%d",
                     len(result["messages"]), len(answer))

        def _current_round(messages) -> list:
            """只取本轮新增消息（最后一个 HumanMessage 之后）。
            checkpointer 会加载全部历史，若不切分，上一轮的 JSON 会被捞回
            并覆盖本轮新答案，表现为"代码改了但回答一直没变"。"""
            round_msgs = []
            for msg in reversed(messages):
                if isinstance(msg, HumanMessage):
                    break
                round_msgs.append(msg)
            round_msgs.reverse()
            return round_msgs

        def _extract_tool_json(messages) -> dict | None:
            """从本轮消息倒序找 resume_qa 的原始 JSON 输出。
            Agent 汇总时可能把工具返回的 JSON 压缩成一句话（GLM 服从性问题），
            导致 sources/hit 丢失；这里直接捞回工具原始输出，保证结构完整。"""
            for msg in reversed(messages):
                content = getattr(msg, "content", None)
                if not content or content is answer:
                    continue
                try:
                    parsed = json.loads(content)
                except (json.JSONDecodeError, TypeError):
                    continue
                if isinstance(parsed, dict) and "answer" in parsed:
                    return parsed
            return None

        # 执行轨迹透传给前端（只统计本轮，避免历史轨迹混入）
        current = _current_round(result["messages"])
        trace = extract_trace(current)
        # 确定性兜底：前端明确指定了简历ID时，只要模型本轮没有真正查询过简历
        # （零工具调用，且问题不属于寒暄/对话本身类），或给出拒答，
        # 就由后端直接对该简历全文重新作答。
        # 目的：不把"要不要查简历"这个判断交给模型——它可能凭上下文猜一个
        # 看似合理的答案，实际从未读过简历。
        fallback = None
        refusal_hints = ("简历库中没有检索到", "简历中未提及", "无法据此回答")
        no_tool_used = not trace
        if knowledge_id_list and (
                not answer.strip()
                or any(h in answer for h in refusal_hints)
                or (no_tool_used and not knowledge_service.is_conversational(question))):
            if len(knowledge_id_list) > 1:
                # 对比场景：模型没调工具时，直接由后端跑对比固定流程
                logging.info("【rag_resume_chat】多简历对比兜底，转确定性对比流程")
                text = compare_resumes.invoke({
                    "knowledge_id_a": knowledge_id_list[0],
                    "knowledge_id_b": knowledge_id_list[1]})
                fallback = {"answer": text} if not text.startswith("简历读取失败") else None
            else:
                logging.info("【rag_resume_chat】Agent 未查询简历或拒答，转确定性全文作答"
                             "（本轮工具调用数=%d）", len(trace))
                fallback = knowledge_service.resume_chat(question, knowledge_id_list)
            if fallback:
                answer = fallback.get("answer", answer)
        # 兜底结果优先生效：它已包含 answer/sources/hit，且是针对当前简历重新生成的
        if fallback is not None:
            fallback["trace"] = trace
            payload = fallback
        else:
            # 其次透传 resume_qa 的原始 JSON（answer/sources/hit 完整保留）；
            # 没有结构化输出时（Agent 直接作答/走了其他工具）才用最终答复兜底包装。
            # 兜底包装不带 hit 字段：hit=false 是"RAG 检索无命中"的专属语义，
            # 非 RAG 来源的回答带上它会误导前端显示"无命中片段"
            tool_json = _extract_tool_json(current)
            if tool_json is not None:
                tool_json["trace"] = trace
                payload = tool_json
            else:
                payload = {"answer": answer, "trace": trace}
        # 落库保存本轮问答，供前端重新打开弹窗时回显历史
        knowledge_service.save_chat_record(
            session_id, question, payload.get("answer", answer),
            knowledge_id_list[0] if knowledge_id_list else "",
        )
        return json.dumps(payload, ensure_ascii=False)
    except Exception as e:
        logging.exception("【rag_resume_chat执行异常】")
        return json.dumps({"answer": f"❌Agent执行异常：{str(e)}",
                           "trace": []}, ensure_ascii=False)


@mcp.tool()
def get_chat_history(session_id: str, limit: int = 30,
                     knowledge_id: str = "") -> str:
    """读取指定会话的历史问答记录，前端重新打开问答弹窗时回显用。
    session_id 必须与 rag_resume_chat 传入的一致（Agent 级会话，跨简历共享记忆）。
    knowledge_id 非空时只回显该简历的问答，避免跨简历串台。
    返回JSON：{"messages":[{"question","answer","createTime"}]}"""
    return knowledge_service.get_chat_history(
        session_id, limit=limit, knowledge_id=knowledge_id)


@mcp.tool()
def read_resume(path: str, knowledge_id: str | None = None) -> str:
    """读取简历文件。
    传入 knowledge_id：读完自动分片存入 rag_doc_chunk；
    不传：Python 自动生成全新 UUID 入库。
    ⚠️ 每个新简历必须使用全新 knowledge_id，禁止使用 resume_001。"""
    return knowledge_service.read_and_store(path, knowledge_id)



