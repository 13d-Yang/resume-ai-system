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

from app.core.llm import ai_call
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
    """简历完整分析。use_zhipu=true 走智谱直连，否则转发 8604 的 run_agent_chat。"""
    text, tmp_path = await _resolve_resume_text(path, file)
    try:
        if use_zhipu:
            result = await asyncio.to_thread(ai_call, f"简历全文如下：\n{text}")
        else:
            result = await call_mcp_tool_common("run_agent_chat", {"text": text}, timeout=120)
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
        result = await call_mcp_tool_common(tool_name, {"text": text}, timeout=120)
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
