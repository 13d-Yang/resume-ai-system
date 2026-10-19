# -*- coding: utf-8 -*-
"""简历分析类 MCP 工具：雷达图、JD匹配、面试题、优化、风险筛查、多简历对比。

工具名与 Java/前端调用严格一致；本层只做透传，逻辑在 workflows 与 core.llm。
"""
import logging

from app.config import ZHIPU_MODEL
from app.core.llm import (
    ai_call,
    gen_question_text,
    optimize_text,
    risk_check_text,
    zhipu_client,
)
from app.tools.mcp_instance import mcp
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
def run_agent_chat(input_text: str) -> str:
    """Agent 对话：直接调用智谱模型完成简历综合分析"""
    logging.info(f"【MCP调用】run_agent_chat input={input_text[:80]}")
    try:
        resp = zhipu_client.chat.completions.create(
            model=ZHIPU_MODEL,
            messages=[{"role": "user", "content": input_text}],
            temperature=0.3,
            timeout=120,
        )
        return resp.choices[0].message.content
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
