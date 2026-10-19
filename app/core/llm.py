# -*- coding: utf-8 -*-
"""大模型客户端统一封装：智谱 GLM 客户端、通用 ai_call、LangChain 工具模型。

所有需要调大模型的地方都从这里取，禁止各模块自己 new 客户端。
"""
import logging

from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage
from zhipuai import ZhipuAI

from app.config import ZHIPU_API_KEY, ZHIPU_MODEL, ZHIPU_BASE_URL

# ========== 全局智谱客户端（负责聊天/分析） ==========
zhipu_client = ZhipuAI(api_key=ZHIPU_API_KEY)


def ai_call(prompt: str, system_prompt: str = None) -> str:
    """统一的智谱对话调用。失败不抛异常，返回错误文案，保证 MCP 工具不崩。"""
    logging.info(f"【智谱LLM调用】文本长度：{len(prompt)}，模型：{ZHIPU_MODEL}")

    if system_prompt is None:
        system_prompt = (
            "你是一位资深HR专家。严格按用户指令执行任务，"
            "绝对不要复述用户提供的原始文本，只输出你的分析结论和建议。"
        )

    try:
        resp = zhipu_client.chat.completions.create(
            model=ZHIPU_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            timeout=120,
        )
        result = resp.choices[0].message.content
        logging.info(f"【智谱LLM完成】返回长度：{len(result)}")
        return result
    except Exception as e:
        logging.exception("【智谱LLM调用失败】")
        return f"❌LLM调用异常：{str(e)}"


# ========== 消息裁剪：只保留最近N条，防止上下文溢出 ==========
def trim_messages(messages: list[BaseMessage], keep_last: int = 4) -> list[BaseMessage]:
    if len(messages) <= keep_last:
        return messages
    return messages[-keep_last:]


# ========== Agent 工作流用到的 LangChain 工具 ==========
@tool
def analyze_resume_text(text: str) -> str:
    """分析简历文本，输出HR专业分析报告"""
    return ai_call(
        f"简历全文如下：\n{text}",
        system_prompt=(
            "你是一位拥有15年经验的资深HR专家。"
            "请对这份简历输出结构化的分析报告，必须包含四部分："
            "1. 综合评分（0-100） 2. 核心优势 3. 明显短板 4. 改进建议。"
            "严禁复述简历原文，只输出分析结论。使用中文。"
        ),
    )


@tool
def gen_question_text(text: str) -> str:
    """基于简历内容生成面试问题"""
    return ai_call(
        f"简历全文如下：\n{text}",
        system_prompt=(
            "你是一位资深面试官。请基于候选人简历，输出8-10个专业的面试问题，"
            "按'技术能力'、'项目经验'、'软技能'三个分类。"
            "只输出问题列表，不要复述简历原文，不要输出分析。使用中文。"
        ),
    )


@tool
def optimize_text(text: str) -> str:
    """对简历文本进行优化润色"""
    return ai_call(
        f"原简历如下：\n{text}",
        system_prompt=(
            "你是一位简历优化专家。请对这份简历进行润色，"
            "输出优化后对简历的修改意见，以及修改好之后的简历。"
            "输出优化后的简历"
        ),
    )


@tool
def risk_check_text(text: str) -> str:
    """检测简历存在的风险点"""
    return ai_call(
        f"简历全文如下：\n{text}",
        system_prompt=(
            "你是一位资深背景调查专家。请从这份简历中识别潜在风险点，"
            "包括：时间线断层、夸大表述、逻辑矛盾、合规风险等。"
            "只输出风险点清单和简要说明，严禁复述简历原文，不要输出分析报告。使用中文。"
        ),
    )


# Agent 工作流使用的 tool-calling 模型
llm = ChatOpenAI(
    model=ZHIPU_MODEL,
    api_key=ZHIPU_API_KEY,
    base_url=ZHIPU_BASE_URL,
    temperature=0.3,
    timeout=120,
    max_retries=2,
)
