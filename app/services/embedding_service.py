# -*- coding: utf-8 -*-
"""向量化服务：硅基流动 bge-large-zh-v1.5 + 中文分片器 + 余弦相似度。"""
import logging

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
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=400,
    chunk_overlap=60,
    separators=[
        "\n\n", "\n", "。", "！", "？", "；",
        ". ", "! ", "? ",
        " ",
    ],
)


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
