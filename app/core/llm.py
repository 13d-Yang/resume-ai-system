# -*- coding: utf-8 -*-
"""大模型客户端统一封装：智谱 GLM 客户端、通用 ai_call、LangChain 工具模型。

所有需要调大模型的地方都从这里取，禁止各模块自己 new 客户端。
"""
import logging

from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
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


# ========== 消息裁剪：按轮保留 + 历史工具结果压缩，防止上下文溢出 ==========
def trim_history(messages: list[BaseMessage], keep_rounds: int = 50,
                 keep_intact: int = 12) -> list[BaseMessage]:
    """按"轮"保留历史，并把较早的工具结果原地压缩。

    为什么不按条数：一次分析类问答会产生 4~6 条消息，且 get_resume_text
    返回的是上万字全文，按条数限制会被少数几轮撑爆上下文。
    这里以 HumanMessage 为轮起点保留最近 keep_rounds 轮；最近 keep_intact
    条消息保持原文（当前推理需要完整数据），更早的 ToolMessage 只留占位符。
    这样既保住"聊过什么"，又不让历史全文长期占用 token。
    """
    human_idx = [i for i, m in enumerate(messages) if isinstance(m, HumanMessage)]
    if len(human_idx) > keep_rounds:
        # 从 HumanMessage 处截断，天然不会产生开头是孤立 ToolMessage 的非法序列
        messages = messages[human_idx[-keep_rounds]:]
    if len(messages) <= keep_intact:
        return messages
    cutoff = len(messages) - keep_intact
    trimmed = []
    for i, m in enumerate(messages):
        if i < cutoff and isinstance(m, ToolMessage):
            m = m.model_copy(
                update={"content": f"[历史工具结果已省略，原长 {len(str(m.content))} 字]"})
        trimmed.append(m)
    return trimmed


# ========== Agent 工作流用到的 LangChain 工具 ==========
@tool
def analyze_resume_text(text: str) -> str:
    """分析简历文本，输出HR专业分析报告"""
    return ai_call(
        f"简历全文如下：\n{text}",
        system_prompt=(
            "你是一位拥有15年经验的资深HR专家与资深技术面试官，熟悉互联网、咨询、金融行业的招聘标准。"
            "请对这份简历输出一份可直接用于招聘决策的深度分析报告，必须严格按以下七个部分输出，"
            "并用 Markdown 小标题和有序列表排版：\n"
            "1. 综合评分与结论：给出 0-100 的综合评分，并用一句话说明该候选人对应的岗位层级"
            "（初级/中级/高级/资深）与适配方向。\n"
            "2. 分维度评分：按『技术深度(20分)、项目复杂度(20分)、可量化成果(20分)、"
            "工程规范(15分)、表达与结构(15分)、成长潜力(10分)』逐项给分，"
            "每一项后面用一句话说明打分依据（引用简历中的具体事实，如技术栈、项目规模、年限）。\n"
            "3. 核心优势：列出 3-4 条，每条采用『结论 + 简历中的具体证据』格式，"
            "说明这条优势在求职时的价值。\n"
            "4. 主要短板：列出 3-5 条，每条采用『现象 + 为什么是短板 + 对求职的实际影响』格式，"
            "优先指出表述空泛、缺乏量化、技术栈与目标岗位错位等硬伤。\n"
            "5. 改进建议：按优先级 P0（必改）、P1（强烈建议）、P2（可选）分组，"
            "每条必须给出可操作的改法，例如『把××改为××』或『补充××维度的数据』，"
            "不要只说『建议加强』这类空话。\n"
            "6. 面试追问预判：列出 3-5 个面试官最可能追问的问题，并说明为什么会被追问"
            "（对应简历中哪一处薄弱或模糊的地方）。\n"
            "7. 结论与下一步：一句话总结是否推荐进入面试，以及候选人下一步最该做的一件事。\n"
            "硬性要求：严禁复述或大段引用简历原文；所有结论必须能在简历中找到依据，"
            "不得编造简历没有的信息；若某维度信息不足，明确写『简历未体现，无法评估』，"
            "不要凭猜测补全；总篇幅控制在 900-1400 字；使用中文。"
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


@tool
def compare_text(text_a: str, name_a: str, text_b: str, name_b: str) -> str:
    """横向对比两份简历的优劣势与录用优先级"""
    return ai_call(
        f"简历A（{name_a}）：\n{text_a}\n\n简历B（{name_b}）：\n{text_b}",
        system_prompt=(
            "你是一位拥有15年经验的资深HR专家。请横向对比这两份简历，使用中文输出：\n"
            "1. 对比总览：一句话说明两人的定位差异（岗位方向、经验年限、技术栈侧重）。\n"
            "2. 逐维度对比：技术深度、项目复杂度、可量化成果、工程规范、表达结构、成长潜力，"
            "每项分别评价 A 与 B，并明确指出该项谁更强。\n"
            "3. 各自优势与短板：分别列 2-3 条，每条必须有简历中的具体事实支撑。\n"
            "4. 录用优先级：明确给出 A 优先还是 B 优先，并说明适用场景（岗位侧重不同则分别说明）。\n"
            "只依据提供的简历内容，严禁编造未提及的经历、技能或数据。"
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
