# -*- coding: utf-8 -*-
"""简历 AI 相关 HTTP 路由（网关 8501）。

统一模式：接收简历（路径或上传文件）-> 解析成文本 -> 转发给 8604 MCP 工具。
智谱直连分支仅在显式传 use_zhipu=true 时启用。
"""
import asyncio
import json
import logging
import os

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel

from app.core.llm import analyze_resume_text
from app.gateway.mcp_client import call_mcp_tool_common
from app.gateway.mcp_store import safe_temp_upload
from app.services.document_parser import extract_resume_text

router = APIRouter()

logger = logging.getLogger(__name__)


async def _resolve_resume_text(path: str | None, file: UploadFile | None) -> tuple[str, str | None]:
    """解析简历文本。返回 (文本, 临时文件路径)；临时文件需调用方负责删除。"""
    if path:
        return await asyncio.to_thread(extract_resume_text, path), None
    if file:
        tmp_path = await asyncio.to_thread(safe_temp_upload, file)
        try:
            return await asyncio.to_thread(extract_resume_text, tmp_path), tmp_path
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
    raise ValueError("必须提供 path 或上传文件")


@router.post("/airag/mcp/test")
async def test_parse(path: str = Form(None), file: UploadFile = File(None)):
    """仅解析文件为文本，验证上传+解析链路（不调 AI）。"""
    text, tmp_path = await _resolve_resume_text(path, file)
    if tmp_path and os.path.exists(tmp_path):
        os.remove(tmp_path)
    return {"code": 200, "text_length": len(text), "preview": text[:200]}


@router.post("/airag/mcp/call_resume_parse")
async def call_resume_parse(
    path: str = Form(None),
    file: UploadFile = File(None),
    use_zhipu: bool = Form(False),
):
    """简历完整分析（固定流程）。
    use_zhipu=true 走本地直连（绕过 MCP 的降级通道），
    否则转发 8604 的 analyze_resume 工具（固定调 HR 分析，不交给 Agent 自主决策）。
    """
    text, tmp_path = await _resolve_resume_text(path, file)
    try:
        if use_zhipu:
            result = await asyncio.to_thread(
                analyze_resume_text.invoke, {"text": text}
            )
        else:
            result = await call_mcp_tool_common(
                "analyze_resume", {"resume_text": text}, timeout=120
            )
        # 尝试解析 JSON 结果，不是 JSON 则原样返回
        try:
            parsed = json.loads(result)
            return {"code": 200, "result": parsed}
        except (json.JSONDecodeError, TypeError):
            return {"code": 200, "result": result}
    except Exception as e:
        logger.exception("【call_resume_parse 异常】")
        return {"code": 500, "message": str(e)}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


async def _forward_simple(tool_name: str, path: str | None, file: UploadFile | None):
    """四个单分析按钮的公共转发逻辑。"""
    text, tmp_path = await _resolve_resume_text(path, file)
    try:
        result = await call_mcp_tool_common(tool_name, {"resume_text": text}, timeout=120)
        return {"code": 200, "result": result}
    except Exception as e:
        logger.exception("【%s 异常】", tool_name)
        return {"code": 500, "message": str(e)}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.post("/airag/mcp/call_radar")
async def call_radar(path: str = Form(None), file: UploadFile = File(None)):
    """能力雷达图 -> run_radar"""
    return await _forward_simple("run_radar", path, file)


@router.post("/airag/mcp/call_interview")
async def call_interview(path: str = Form(None), file: UploadFile = File(None)):
    """生成面试题 -> gen_interview_question"""
    return await _forward_simple("gen_interview_question", path, file)


@router.post("/airag/mcp/call_optimize")
async def call_optimize(path: str = Form(None), file: UploadFile = File(None)):
    """简历优化建议 -> resume_optimize"""
    return await _forward_simple("resume_optimize", path, file)


@router.post("/airag/mcp/call_risk")
async def call_risk(path: str = Form(None), file: UploadFile = File(None)):
    """风险筛查 -> resume_risk_check"""
    return await _forward_simple("resume_risk_check", path, file)


@router.post("/ai/compare_resume")
async def compare_resume(paths: str = Form(...)):
    """多简历对比。paths 为逗号分隔的简历文件路径。"""
    path_list = [p.strip() for p in paths.split(",") if p.strip()]
    if len(path_list) < 2:
        return {"code": 400, "message": "至少提供2份简历路径"}
    try:
        texts = []
        for p in path_list:
            t = await asyncio.to_thread(extract_resume_text, p)
            texts.append(f"【简历{len(texts)+1}】{t}")
        combined = "\n\n".join(texts)
        result = await call_mcp_tool_common("compare_multi_resume", {"text": combined}, timeout=180)
        return {"code": 200, "result": result}
    except Exception as e:
        logger.exception("【compare_resume 异常】")
        return {"code": 500, "message": str(e)}


@router.post("/ai/agent_by_path")
async def agent_by_path(path: str = Form(None)):
    """兼容占位接口：旧前端如调到此路径，返回提示而非 404。"""
    return {"code": 200, "result": "该接口已迁移，请使用 /airag/mcp/call_resume_parse"}


class McpCallRequest(BaseModel):
    """通用工具转发请求体。"""

    tool_name: str
    params: dict = {}


# Agent 类工具内部是多轮 LLM 调用（决策 + 工具执行 + 汇总），单轮 120 秒不够用
AGENT_TOOLS = {"run_agent_chat", "agent_chat", "rag_resume_chat"}
AGENT_TIMEOUT = 240
NORMAL_TIMEOUT = 120


@router.post("/airag/mcp/call_tool")
async def call_tool_generic(req: McpCallRequest):
    """通用 MCP 工具转发（Java 侧统一入口）。
    body 形如 {"tool_name": "gen_interview_question", "params": {"resume_text": "..."}}。
    """
    timeout = AGENT_TIMEOUT if req.tool_name in AGENT_TOOLS else NORMAL_TIMEOUT
    logger.info("【网关转发】tool_name=%s，参数键=%s，超时=%ss",
                req.tool_name, list(req.params.keys()), timeout)
    try:
        result = await call_mcp_tool_common(req.tool_name, req.params, timeout=timeout)
        return {"code": 200, "result": result}
    except Exception as e:
        logger.exception("【call_tool 异常】tool_name=%s", req.tool_name)
        return {"code": 500, "message": str(e)}
