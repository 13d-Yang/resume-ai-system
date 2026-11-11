# -*- coding: utf-8 -*-
"""简历分析类 MCP 工具：雷达图、JD匹配、面试题、优化、风险筛查、多简历对比。

工具名与 Java/前端调用严格一致；本层只做透传，逻辑在 workflows 与 core.llm。
"""
import json
import logging
import uuid

from langchain_core.messages import HumanMessage, ToolMessage

from app.core.llm import (
    ai_call,
    analyze_resume_text,
    gen_question_text,
    optimize_text,
    risk_check_text,
)
from app.tools.mcp_instance import mcp
from app.workflows.agent_workflow import agent_app, extract_trace, strip_textual_tool_call
from app.workflows.match_workflow import match_app
from app.workflows.radar_workflow import radar_app


@mcp.tool()
def run_radar(resume_text: str) -> dict:
    """生成简历AI能力雷达图（6维评分）"""
    logging.info("【MCP调用】run_radar 生成雷达图")
    res = radar_app.invoke({"resume_text": resume_text})
    return res["radar_result"]


@mcp.tool()
def run_match(resume_text: str, jd: str) -> dict:
    """简历与JD的严格四维匹配评分"""
    logging.info("【MCP调用】run_match 简历JD匹配")
    ret = match_app.invoke({"resume_text": resume_text, "jd": jd})
    return ret["final"]


@mcp.tool()
def analyze_resume(resume_text: str) -> str:
    """简历完整分析（固定流程）：评分 + 核心优势 + 明显短板 + 改进建议"""
    logging.info("【MCP调用】analyze_resume 简历完整分析（固定流程）")
    return analyze_resume_text.invoke({"text": resume_text})


@mcp.tool()
def run_agent_chat(input_text: str, session_id: str = "") -> str:
    """Agent 对话：LangGraph ReAct 循环，模型自主选择工具、自主决定是否继续。
    session_id 用于多轮会话记忆：同一会话传相同 ID，Agent 可记住上文；
    不传则为单次对话。Java 侧会按「用户名_工具名」自动兜底注入。"""
    logging.info(f"【MCP调用】run_agent_chat（Agent循环模式）input={input_text[:80]} session={session_id}")
    try:
        # 有 checkpointer 后必须提供 thread_id；无 session_id 时用随机ID，退化为单次对话
        thread_id = session_id or f"once_{uuid.uuid4().hex}"
        # recursion_limit 是硬性循环上限：防止模型陷入无限调工具把额度烧穿
        result = agent_app.invoke(
            {"messages": [HumanMessage(content=input_text)]},
            config={"configurable": {"thread_id": thread_id},
                    "recursion_limit": 15},
        )
        last_msg = result["messages"][-1]
        # 最后一条就是模型最终答复（条件边判断无 tool_calls 时才会走到 END）
        answer = getattr(last_msg, "content", None) or str(last_msg)
        # 兜底：剔除残留的文本型工具调用，防止函数名+参数JSON裸露给用户
        answer = strip_textual_tool_call(answer)
        # 模型把工具调用写成文本导致答复被清空时，用历史中最近一次工具输出
        # 作为上下文走固定流程重答，保证用户始终能拿到有效回答，
        # 而不是看到"模型输出格式错误"这类技术提示
        if not answer.strip():
            logging.warning("【Agent】最终答复为空，启用固定流程兜底重答")
            context = ""
            for msg in reversed(result["messages"]):
                if isinstance(msg, ToolMessage) and msg.content:
                    context = str(msg.content)
                    break
            fallback_prompt = (f"以下是候选人简历信息：\n{context}\n\n"
                               f"请回答问题：{input_text}" if context else input_text)
            answer = ai_call(fallback_prompt)
        logging.info(
            "【Agent循环完成】总消息条数=%d, 最终答案长度=%d",
            len(result["messages"]),
            len(answer),
        )
        # 执行轨迹以文本页脚透传：前端纯文本展示即可见，不破坏现有解析逻辑
        trace = extract_trace(result["messages"])
        if trace:
            answer += "\n\n---\n🔧 Agent 执行轨迹：\n" + "\n".join(
                f"{i}. {t}" for i, t in enumerate(trace, 1))
        return answer
    except Exception as e:
        logging.exception("【run_agent_chat执行异常】")
        return f"❌Agent执行异常：{str(e)}"


@mcp.tool()
def gen_interview_question(resume_text: str) -> str:
    """基于简历生成8-10个分类面试题"""
    logging.info("【MCP调用】gen_interview_question")
    return gen_question_text.invoke({"text": resume_text})


@mcp.tool()
def resume_optimize(resume_text: str) -> str:
    """简历优化润色建议"""
    logging.info("【MCP调用】resume_optimize")
    return optimize_text.invoke({"text": resume_text})


@mcp.tool()
def resume_risk_check(resume_text: str) -> str:
    """简历风险点筛查"""
    logging.info("【MCP调用】resume_risk_check")
    return risk_check_text.invoke({"text": resume_text})


@mcp.tool()
def compare_multi_resume(resume_texts: str, names: str) -> str:
    """多份简历对比：输出优势劣势与录用优先级"""
    logging.info("【MCP调用】compare_multi_resume 多简历对比")
    prompt = f"""对比多份简历：
简历列表：{resume_texts}
简历名字：{names}
输出对比分析，优势劣势，录用优先级。
"""
    return ai_call(prompt)
