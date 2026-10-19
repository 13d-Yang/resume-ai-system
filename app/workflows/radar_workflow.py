# -*- coding: utf-8 -*-
"""能力雷达图工作流：LLM 输出 6 维评分 JSON，Python 兜底复算平均分。"""
import json
import logging

from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict

from app.core.llm import ai_call


class RadarState(TypedDict):
    resume_text: str
    radar_result: dict


def radar_node(state: RadarState):
    prompt = """
只输出纯JSON，不要多余文字！
6个维度0-100分：工作经验、学历背景、专业技能、项目含金量、沟通协作、稳定性
必须同时输出这4个字段：scoreArr、totalScore、advantage、risk
示例：{"scoreArr":[80,70,85,75,60,72],"totalScore":74,"advantage":"xxx","risk":"xxx"}
简历：
""" + state["resume_text"]
    out = ai_call(
        prompt,
        system_prompt="你是资深HR，严格按JSON格式输出，不要多余文字。"
    )
    out = out.replace("```json", "").replace("```", "").strip()
    try:
        data = json.loads(out)
        # Python 兜底再算一遍平均分，防止模型乱给
        if "scoreArr" in data and len(data["scoreArr"]) > 0:
            nums = [float(x) for x in data["scoreArr"] if str(x).replace(".", "").isdigit()]
            if nums:
                data["totalScore"] = round(sum(nums) / len(nums), 1)
        logging.info(f"【雷达图解析成功】{data}")
    except Exception as e:
        logging.error(f"【雷达图JSON解析失败】raw={out}, err={str(e)}")
        data = {"scoreArr": [50, 50, 50, 50, 50, 50],
                "totalScore": 50, "advantage": "解析失败", "risk": "解析失败"}
    return {"radar_result": data}


radar_graph = StateGraph(RadarState)
radar_graph.add_node("radar_gen", radar_node)
radar_graph.set_entry_point("radar_gen")
radar_graph.add_edge("radar_gen", END)
radar_app = radar_graph.compile()
