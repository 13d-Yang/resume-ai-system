# -*- coding: utf-8 -*-
"""Agent 对话工作流：LLM 决策 -> 调用分析工具 -> 回到 LLM 汇总。"""
import logging

from langchain_core.messages import ToolMessage
from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict

from app.core.llm import (
    analyze_resume_text,
    gen_question_text,
    llm,
    optimize_text,
    risk_check_text,
    trim_messages,
)


class AgentState(TypedDict):
    messages: list


# 可用工具表（注册名与调用名必须一致）
tools = [analyze_resume_text, gen_question_text, optimize_text, risk_check_text]
tool_map = {t.name: t for t in tools}
llm_with_tools = llm.bind_tools(tools)


def agent_node(state: AgentState):
    logging.info("【Agent执行节点】")
    # 每次进入裁剪消息，避免消息无限累积导致上下文溢出
    trimmed = trim_messages(state["messages"], keep_last=4)
    result = llm_with_tools.invoke(trimmed)
    return {"messages": [result]}


def tool_call_node(state: AgentState):
    last_msg = state["messages"][-1]
    outputs = []
    for call in last_msg.tool_calls:
        tool_func = tool_map[call["name"]]
        res = tool_func.invoke(call["args"])
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
agent_app = agent_graph.compile()
