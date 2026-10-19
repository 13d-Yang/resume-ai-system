# -*- coding: utf-8 -*-
"""JD 匹配评分工作流：关键信息提取 -> 严格四维评分 -> 汇总分档。"""
import json
import logging

from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict

from app.core.llm import ai_call


class MatchState(TypedDict):
    resume_text: str
    jd: str
    extract_info: str
    score_result: dict
    final: dict


def extract_node(state: MatchState):
    ret = ai_call(f"提取简历关键信息：\n简历：{state['resume_text']}\nJD：{state['jd']}")
    return {"extract_info": ret}


def score_node(state: MatchState):
    prompt = f"""你是一位极其严格的HR评分专家。请对照【JD岗位要求】给候选人评分。

【评分维度说明】
- major（专业匹配度）：专业、学历、行业背景是否与JD要求匹配
- exp（工作经验）：工作年限、项目经验是否达到JD要求
- skill（技能匹配）：JD要求的技能，候选人简历里真正具备多少
- quality（综合素养）：沟通、协作、稳定性等，需有简历证据支撑

【严格评分规则】
1. 必须以JD为唯一标尺！JD没要求的技能，即使简历写了一大堆，也不能加分
2. 简历里与JD完全无关的内容（如"会做饭"、"会唱歌"），一律不计入任何维度
3. 如果核心技能与JD差距大，skill维度必须给低分（30分以下）
4. 严禁"老好人式"打分。不匹配就给低分，60分是及格线，80分以上才是优秀
5. 每个维度0-100分

【输出格式】
只输出纯JSON，不要多余文字！
示例：{{"major":75,"exp":60,"skill":45,"quality":70}}

【简历信息】
{state['extract_info']}

【JD岗位要求】
{state['jd']}
"""
    raw = ai_call(
        prompt,
        system_prompt="你是极其严格的HR评分专家。严格按JD评分，绝不给'人情分'。只输出纯JSON。"
    ).replace("```json", "").replace("```", "").strip()
    try:
        d = json.loads(raw)
        logging.info(f"【match评分】{d}")
    except Exception as e:
        logging.error(f"【match解析失败】{raw} {e}")
        d = {"major": 0, "exp": 0, "skill": 0, "quality": 0}
    return {"score_result": d}


def final_node(state: MatchState):
    s = state["score_result"]
    # 模型若返回非对象JSON（如数组），统一按空处理，避免 .get 抛 AttributeError
    if not isinstance(s, dict):
        s = {}

    # 安全取值：缺失/非法按0分，并限制在0-100
    def _safe_score(key: str) -> int:
        try:
            v = float(s.get(key, 0))
        except (TypeError, ValueError):
            return 0
        return max(0, min(100, round(v)))

    major = _safe_score("major")
    exp = _safe_score("exp")
    skill = _safe_score("skill")
    quality = _safe_score("quality")
    total = major + exp + skill + quality
    avg_total = round(total / 4, 1)  # 换算成百分制
    level, tip = ("推荐录用", 1) if total >= 280 else ("待定观察", 2) if total >= 200 else ("不匹配", 0)
    return {"final": {
        "totalScore": avg_total,
        "subScore": {
            "major": major,
            "exp": exp,
            "skill": skill,
            "quality": quality,
        },
        "advice": level,
        "level_code": tip,
    }}


match_graph = StateGraph(MatchState)
match_graph.add_node("extract", extract_node)
match_graph.add_node("score", score_node)
match_graph.add_node("final", final_node)
match_graph.set_entry_point("extract")
match_graph.add_edge("extract", "score")
match_graph.add_edge("score", "final")
match_graph.add_edge("final", END)
match_app = match_graph.compile()
