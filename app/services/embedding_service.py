# -*- coding: utf-8 -*-
"""向量化服务：硅基流动 bge-large-zh-v1.5 + 中文分片器 + 余弦相似度。"""
import logging
import re

import numpy as np
import requests
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import (
    EMBED_MODEL,
    SILICONFLOW_API_KEY,
    SILICONFLOW_BASE_URL,
)

# ========== 中文简历专用分片器 ==========
# bge-large-zh-v1.5 单条最大 512 token（中文约400字），分片过大尾部会被截断丢内容
CHUNK_SIZE = 400

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=60,
    separators=[
        "\n\n", "\n", "。", "！", "？", "；",
        ". ", "! ", "? ",
        " ",
    ],
)


# ========== 语义分片：先按章节标题切，切不动再退回上面的标点分片器 ==========
# 章节核心词根：只认词根不认完整标题，"教育背景/教育经历/学历信息"都能命中
_SECTION_ROOT_RE = re.compile(
    r"(?:教育|学习|学历|工作|职业|任职|实习|项目|技能|技术栈|能力|"
    r"自我|个人|荣誉|获奖|奖项|证书|资质|培训)"
)

# 编号式标题：一、 / 1. / (1) / 【标题】
_NUMBERED_RE = re.compile(
    r"^(?:[一二三四五六七八九十]+[、.]|\d+[、.）)]|[（(]\d+[）)]|【[^】]{2,12}】)"
)

# 以这些字符结尾的是正文句子，不是标题
_SENTENCE_END = "，。；：、,.;:"


def is_section_heading(line: str, next_line: str = "") -> bool:
    """判断一行是否像章节标题（启发式：宁可多切一刀，也不漏掉章节边界）。"""
    s = line.strip()
    if not s or len(s) > 15:
        return False
    if s[-1] in _SENTENCE_END:
        return False
    # ① 语义命中：含章节核心词根
    if _SECTION_ROOT_RE.search(s):
        return True
    # ② 结构命中：编号 / 【】包裹的标题
    if _NUMBERED_RE.match(s):
        return True
    # ③ 结构兜底：短、无数字、下一行明显更长（典型"标题 + 内容"排版）
    return (
        4 <= len(s) <= 15
        and not any(ch.isdigit() for ch in s)
        and len(next_line.strip()) > 30
    )


def split_resume_text(text: str) -> list[str]:
    """简历语义分片：先按章节标题切成大块，超长块再交给标点分片器二次切。

    识别不到任何标题时，完全退回 text_splitter 的原行为，不会让现有效果变差。
    """
    lines = text.split("\n")
    idxs = [
        i for i, line in enumerate(lines)
        if is_section_heading(line, lines[i + 1] if i + 1 < len(lines) else "")
    ]
    if not idxs:
        logging.info("【语义分片】未识别到章节标题，退回标点分片")
        return text_splitter.split_text(text)

    logging.info(
        "【语义分片】识别到 %d 个章节标题：%s",
        len(idxs), [lines[i].strip() for i in idxs],
    )

    # 按标题位置把行聚成章节块（第一个标题之前的内容单独成块）
    blocks, start = [], 0
    for pos in idxs + [len(lines)]:
        block = "\n".join(lines[start:pos]).strip()
        if block:
            blocks.append(block)
        start = pos

    # 超长章节再切，保证单块不超过 chunk_size
    chunks = []
    for block in blocks:
        if len(block) <= CHUNK_SIZE:
            chunks.append(block)
        else:
            chunks.extend(text_splitter.split_text(block))
    logging.info("【语义分片】章节块 %d 个 → 最终分片 %d 个", len(blocks), len(chunks))
    return chunks


def _call_siliconflow_embeddings(inputs: list[str]) -> list[list[float]]:
    """统一的向量请求：inputs 为文本列表，返回按 index 排序的向量列表。
    失败时抛异常，由调用方决定回滚，绝不静默返回空向量。"""
    if not SILICONFLOW_API_KEY:
        raise RuntimeError(
            "未读到环境变量 SILICONFLOW_API_KEY，请先在 "
            "https://cloud.siliconflow.cn/account/ak 创建密钥并设置环境变量"
        )
    resp = requests.post(
        f"{SILICONFLOW_BASE_URL}/embeddings",
        headers={
            "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"model": EMBED_MODEL, "input": inputs, "encoding_format": "float"},
        timeout=60,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"向量接口HTTP {resp.status_code}: {resp.text[:300]}")
    data = resp.json()["data"]
    data.sort(key=lambda d: d["index"])
    return [d["embedding"] for d in data]


def get_cloud_embedding(input_text: str) -> list[float]:
    """单条文本向量化（检索时用）。"""
    return _call_siliconflow_embeddings([input_text])[0]


def get_cloud_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """批量向量化：一次请求处理多个分片，比逐片调用快得多、网络开销小。"""
    if not texts:
        return []
    return _call_siliconflow_embeddings(texts)


def cosine_similarity(a, b) -> float:
    """余弦相似度；空向量/维度不一致时返回 0 分，避免除零崩溃。"""
    arr_a = np.array(a, dtype=np.float32)
    arr_b = np.array(b, dtype=np.float32)
    norm_a = np.linalg.norm(arr_a)
    norm_b = np.linalg.norm(arr_b)
    if norm_a == 0 or norm_b == 0 or arr_a.shape != arr_b.shape:
        return 0.0
    return float(np.dot(arr_a, arr_b) / (norm_a * norm_b))
