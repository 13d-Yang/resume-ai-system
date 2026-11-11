# -*- coding: utf-8 -*-
"""Agent 对话工作流：LLM 决策 -> 调用工具 -> 回到 LLM 汇总。"""
import json
import logging
import re
import uuid
from typing import Annotated

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from app.core.llm import (
    analyze_resume_text,
    compare_text,
    gen_question_text,
    llm,
    optimize_text,
    risk_check_text,
    trim_history,
)
from app.services import knowledge_service
from app.workflows.match_workflow import match_app
from app.workflows.radar_workflow import radar_app


class AgentState(TypedDict):
    # 必须用 add_messages reducer：节点返回的消息会追加到历史，而不是整体覆盖
    messages: Annotated[list, add_messages]


@tool
def radar_generate(resume_text: str) -> str:
    """简历综合评分/能力评估（6维雷达图，含总分）。用户要求给简历打分、评分、
    综合评价、评估候选人水平时使用。返回JSON：scoreArr/totalScore/advantage/risk"""
    ret = radar_app.invoke({"resume_text": resume_text})
    return json.dumps(ret["radar_result"], ensure_ascii=False)


@tool
def jd_match(resume_text: str, jd: str) -> str:
    """简历与岗位JD的匹配评分（四维严格打分）。返回JSON"""
    ret = match_app.invoke({"resume_text": resume_text, "jd": jd})
    return json.dumps(ret["final"], ensure_ascii=False)


@tool
def compare_resumes(knowledge_id_a: str, knowledge_id_b: str) -> str:
    """两份简历横向对比（各自优势、短板、录用优先级）。用户要求对比两份简历、
    谁更合适、选哪个、A和B哪个好时使用。参数必须是简历ID，严禁传入简历正文。"""
    text_a = knowledge_service.get_resume_text(knowledge_id_a)
    text_b = knowledge_service.get_resume_text(knowledge_id_b)
    for text in (text_a, text_b):
        if not text or "未找到" in text[:20]:
            return "简历读取失败：请确认 knowledge_id 是否正确后重试"
    name_map = knowledge_service.get_knowledge_names([knowledge_id_a, knowledge_id_b])
    return compare_text.invoke({
        "text_a": text_a,
        "name_a": name_map.get(knowledge_id_a, knowledge_id_a),
        "text_b": text_b,
        "name_b": name_map.get(knowledge_id_b, knowledge_id_b),
    })


@tool
def talent_search(jd_text: str, top_n: int = 5) -> str:
    """人才库语义搜索：用JD在全库简历中向量召回并按简历聚合排名。返回JSON：candidates[...]"""
    return knowledge_service.search_candidates(jd_text, top_n=top_n)


@tool
def resume_qa(question: str, knowledge_id: str = "") -> str:
    """基于简历内容回答具体事实问题（会不会某项技术、几年经验、学历、英语水平、
    某个项目细节等）。不适合评分、综合评价、整体分析、总结推荐这类需要通读全文的
    问题，那类问题应改用 get_resume_text 加对应分析工具。返回JSON：answer/sources/hit"""
    ids = [knowledge_id] if knowledge_id else None
    # 确定性路由：评分问题直接走雷达图固定流程，不依赖模型选工具
    if knowledge_id and knowledge_service.detect_intent(question) == "score":
        text = knowledge_service.get_resume_text(knowledge_id)
        if text and "未找到" not in text[:20]:
            return radar_generate.invoke({"resume_text": text})
    ret = knowledge_service.resume_chat(question, ids, top_k=5)
    return json.dumps(ret, ensure_ascii=False)


@tool
def get_resume_text(knowledge_id: str) -> str:
    """根据简历ID（knowledge_id）读取简历全文。
    当任务需要简历全文而用户只提供了ID时，必须先调用本工具获取文本，
    严禁把ID字符串当作简历文本传给其他工具。"""
    return knowledge_service.get_resume_text(knowledge_id)


# 可用工具表（注册名与调用名必须一致）
tools = [
    analyze_resume_text,
    gen_question_text,
    optimize_text,
    risk_check_text,
    radar_generate,
    jd_match,
    talent_search,
    resume_qa,
    get_resume_text,
    compare_resumes,
]
tool_map = {t.name: t for t in tools}
llm_with_tools = llm.bind_tools(tools)

# Agent 系统提示词：只约束"怎么选工具"和"怎么呈现结果"，具体业务仍由各工具负责。
# 收敛在本文件（Agent 的定义地），tools 层不再各自维护。
AGENT_SYSTEM_PROMPT = (
    "你是HR智能助手，可用工具包括：简历完整分析、面试题生成、简历优化、风险筛查、"
    "能力雷达图、JD匹配评分、人才库检索、简历问答、按ID读取简历全文。"
    "请根据用户任务意图自主选择最合适的工具（可多轮调用）。"
    "\n\n【工具选择指南】\n"
    "- 要求打分/评分/评个分/打个分/给个分数/综合评价/评估水平 → "
    "先用 get_resume_text 取全文，再调 radar_generate（6维评分+总分）\n"
    "- 要求整体分析、详细评价、优缺点、是否值得录用 → analyze_resume_text\n"
    "- 询问具体事实（会不会某技术、几年经验、学历、英语水平、项目细节） → resume_qa\n"
    "- 生成面试题 → gen_question_text；优化建议 → optimize_text；风险 → risk_check_text\n"
    "- 对照岗位JD判断匹配度 → jd_match；找候选人 → talent_search\n"
    "- 对比两份简历、谁更合适、选哪个 → compare_resumes（传两份简历的ID）\n"
    "\n【多份简历】当前对话涉及两份及以上简历时（参考用户消息中列出的简历ID），"
    "说明用户要做对比：必须逐份读取，再调用 compare_resumes，"
    "回答要按候选人分别说明，最后给出明确的录用优先级。\n"
    "\n【关键区分】resume_qa 只适合用简历中的局部片段回答具体事实问题；"
    "凡是需要通读整份简历才能回答的综合性问题（评分、分析、评价、总结、推荐），"
    "绝对不能用 resume_qa，必须先用 get_resume_text 取全文再调用对应分析工具。"
    "如果用 resume_qa 得到\"简历中未提及\"这类结果，且问题本身是综合性/能力判断性的，"
    "请改用 get_resume_text + 相应分析工具重新作答，不要直接把\"未提及\"交给用户。"
    "但如果问题本身与简历内容完全无关（如生活技能、简历中不可能出现的领域），"
    "\"未提及\"就是正确答案，直接如实告知，禁止升级为完整分析报告。"
    "\n\n【开放性问题的处理】用户的问题常常是开放式的、口语化的，没有专门工具覆盖\n"
    "（例如\"这份简历是不是很好用\"\"值不值得约面试\"\"能不能投这个岗位\"\"他靠谱吗\"）。\n"
    "遇到这类问题不要拒答，也不要硬套 resume_qa 拿局部片段应付，正确做法是：\n"
    "先调用 get_resume_text 获取简历全文，再调用 analyze_resume_text 基于全文做完整分析，\n"
    "最后结合用户的具体问题给出结论、理由和建议。\n"
    "只要问题涉及判断、评价、建议、推荐、是否适合，就必须以简历全文为依据，禁止凭空作答。"
    "\n\n【工具都不适用时】先判断现有工具能否组合出答案：能组合，就按上面的指南"
    "多步调用（例如先 get_resume_text 取全文，再 analyze_resume_text 分析）。"
    "如果确实没有任何工具能覆盖该需求（例如查询行业内公司名单、预测薪资行情、"
    "提供法律或医疗意见、检索简历库以外的外部信息），严禁勉强套用不相关的工具，"
    "也严禁凭空编造数据或冒充已有能力。此时应当用一两句话明确说明系统当前不具备"
    "该能力，并指出可以替代的事情（如基于简历给出针对性建议），不要输出看似专业"
    "实则编造的内容。"
    "\n\n【严禁把系统能力当简历内容】只要用户问的是这份简历或这位候选人，"
    "答案必须来自简历数据（先调用工具取内容再回答）。"
    "严禁把你自身或本系统的功能（如LLM分析、RAG向量检索、雷达图、JD匹配、"
    "面试题生成、简历优化等）描述成简历内容或候选人能力。"
    "如果用户的用词含混（例如\"这份简历会哪些功能\"\"这个简历能做什么\"），"
    "应按\"这位候选人具备哪些技能与能力\"来理解并依据简历如实回答，"
    "不要理解成系统功能清单。"
    "\n\n重要规则：如果任务需要简历全文而用户只提供了简历ID（一串UUID或编号），"
    "必须先调用 get_resume_text 获取全文，再把全文传给后续工具；"
    "严禁把ID字符串当作简历文本传给其他工具。"
    "如果工具返回错误信息，请根据错误提示修正参数重试，或换用其他工具，"
    "不要重复同样的错误调用超过两次。"
    "调用工具必须通过系统提供的工具调用机制发起，"
    "严禁把工具名和参数JSON以普通文本形式输出给用户。"
    "如果用户只是日常问候、寒暄、确认能否提问（如\"我问你几个问题？\"\"在吗\"）、"
    "表达感谢，或询问你能做什么，无需调用工具，直接用自然语言回应，"
    "严禁把这类对话性话语当成简历内容去检索，更不得回答\"简历中未提及\"。"
    "如果用户询问与对话本身有关的问题（如\"我刚才问了什么\"\"我问了几个问题\""
    "\"前面聊到哪了\"），请直接依据本次对话历史如实回答（可复述其原话），"
    "严禁调用工具，也不要反过来要求用户重复问题。"
    "当工具返回 JSON（雷达图、JD匹配、人才库检索、简历问答）时，"
    "必须原样输出该 JSON 字符串，不要改写、不要包代码块、不要添加任何解释；"
    "当工具返回文本时，完整呈现结果，不要压缩或省略。"
    "用户输入可能有错别字、口语化或表述不清，请按最可能的真实意图理解并作答，"
    "不要逐字抠字面（例如把明显的错别字当成一个陌生概念来否定）；"
    "若歧义确实影响结论，用一句话说明你的理解后再回答。"
    "严禁在答复中暴露内部机制：不要提到工具、函数名、调用过程、"
    "\"是否需要调用工具\"之类的判断，也不要说\"我的功能是……\"，"
    "一律用面向招聘业务的自然语言直接回答。"
)


def agent_node(state: AgentState):
    logging.info("【Agent执行节点】当前消息条数=%d", len(state["messages"]))
    # 按轮保留最近50轮，较早的工具结果压缩为占位符（避免历史全文撑爆上下文）
    trimmed = trim_history(state["messages"], keep_rounds=50)
    # SystemMessage 不入历史、每轮动态前置：
    # 既避免被 trim 切掉导致 Agent 忘记规则，也让提示词修改对旧会话立即生效
    result = llm_with_tools.invoke(
        [SystemMessage(content=AGENT_SYSTEM_PROMPT)] + trimmed
    )
    # GLM 兼容修复：模型偶尔把工具调用写成纯文本，需改写为真正的 tool_call
    result = repair_textual_tool_call(result)
    # 打印模型本轮的工具决策，便于观察 Agent 到底调了哪些工具
    if getattr(result, "tool_calls", None):
        logging.info("【Agent决策】决定调用工具：%s",
                     [c["name"] for c in result.tool_calls])
    else:
        logging.info("【Agent决策】无工具调用，输出最终答复")
    return {"messages": [result]}


# 文本型工具调用的识别模式：开头是工具名，换行后紧跟参数JSON
_TEXT_CALL_RE = re.compile(r"^\s*([A-Za-z_]\w*)\s*\n\s*(\{.*)", re.DOTALL)


def repair_textual_tool_call(msg):
    """检测并修复"文本型工具调用"。
    GLM 偶尔会把工具调用写成纯文本（工具名+参数JSON）输出在 content 里，
    而不是走结构化 tool_calls —— 这会让循环提前结束，原始调用文本直接泄露给用户。
    若能解析出已注册的工具名+合法JSON参数，则改写为真正的 tool_call，让循环正常执行。"""
    if getattr(msg, "tool_calls", None) or not msg.content:
        return msg
    m = _TEXT_CALL_RE.match(msg.content)
    if not m or m.group(1) not in tool_map:
        return msg
    try:
        args = json.loads(m.group(2))
    except json.JSONDecodeError:
        return msg
    logging.warning("【文本型工具调用】%s 被模型写成文本，已修复为结构化 tool_call",
                    m.group(1))
    return AIMessage(
        content="",
        tool_calls=[{"name": m.group(1), "args": args,
                     "id": f"repair_{uuid.uuid4().hex[:8]}"}],
    )


def strip_textual_tool_call(answer: str) -> str:
    """兜底清理：修复失败的文本型工具调用若仍残留在最终答复中，
    则清空答复，交由上层用固定流程兜底重答——既不让函数名+参数JSON
    裸露给用户，也不把技术性错误文案当成回答。"""
    m = _TEXT_CALL_RE.match(answer or "")
    if m and m.group(1) in tool_map:
        logging.warning("【文本型工具调用】最终答复仍残留 %s 的原始调用文本，已清空交由兜底重答",
                        m.group(1))
        return ""
    return answer


def tool_call_node(state: AgentState):
    """工具执行节点。容错原则：任何失败都不让 graph 崩溃，
    而是把错误作为 ToolMessage 喂回模型，由模型自主纠错（重试/换工具），
    这是 Agent『观察-纠错-重试』闭环的关键一环。"""
    last_msg = state["messages"][-1]
    outputs = []
    for call in last_msg.tool_calls:
        tool_func = tool_map.get(call["name"])
        # 模型幻觉出不存在的工具名：不崩溃，把可用工具列表喂回去让它自我纠正
        if tool_func is None:
            logging.warning("【工具幻觉】模型调用了不存在的工具：%s", call["name"])
            outputs.append(ToolMessage(
                content=f"错误：工具'{call['name']}'不存在。"
                        f"可用工具列表：{sorted(tool_map.keys())}。请改用可用工具。",
                tool_call_id=call["id"]))
            continue
        logging.info("【执行工具】name=%s，参数=%s",
                     call["name"], str(call["args"])[:150])
        try:
            res = tool_func.invoke(call["args"])
        except Exception as e:
            # 工具执行失败：错误喂回模型，由模型决定修正参数重试还是换路径
            logging.exception("【工具异常】name=%s", call["name"])
            res = (f"工具'{call['name']}'执行失败：{e}。"
                   f"请修正参数后重试，或换用其他工具完成任务。")
        logging.info("【工具返回】name=%s，结果长度=%d",
                     call["name"], len(str(res)))
        outputs.append(ToolMessage(content=str(res), tool_call_id=call["id"]))
    return {"messages": outputs}


def should_continue(state: AgentState):
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tool"
    return END


agent_graph = StateGraph(AgentState)
agent_graph.add_node("agent", agent_node)
agent_graph.add_node("tool", tool_call_node)
agent_graph.add_conditional_edges("agent", should_continue)
agent_graph.add_edge("tool", "agent")
agent_graph.set_entry_point("agent")
# checkpointer 提供跨轮会话记忆：调用方传入相同 thread_id 即可续上历史。
# MemorySaver 为进程内存实现（重启即失），生产环境可平滑替换为 SqliteSaver/PostgresSaver
agent_app = agent_graph.compile(checkpointer=MemorySaver())


def extract_trace(messages) -> list[str]:
    """从消息历史提取 Agent 执行轨迹（调了哪些工具、什么参数），
    让决策过程对调用方可见，不再是黑盒。参数截断防止简历全文刷屏。"""
    trace = []
    for m in messages:
        for c in getattr(m, "tool_calls", None) or []:
            args = json.dumps(c["args"], ensure_ascii=False)
            if len(args) > 60:
                args = args[:60] + "..."
            trace.append(f"{c['name']}({args})")
    return trace
