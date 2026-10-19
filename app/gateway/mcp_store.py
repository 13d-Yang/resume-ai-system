# -*- coding: utf-8 -*-
"""上传文件安全落盘。

上传文件使用随机临时文件名 + 扩展名白名单，防路径穿越。
"""
import os
import tempfile

from app.config import DATA_DIR

os.makedirs(DATA_DIR, exist_ok=True)

# 上传文件扩展名白名单
ALLOWED_UPLOAD_EXT = {".pdf", ".docx", ".doc"}


def safe_temp_upload(filename: str) -> str:
    """在 data/ 下生成随机临时文件路径。

    不使用原始文件名（防止 ../ 路径穿越），扩展名走白名单校验。
    """
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in ALLOWED_UPLOAD_EXT:
        raise ValueError(f"不支持的文件类型：{ext or '无扩展名'}，仅支持 PDF / Word")
    fd, tmp_path = tempfile.mkstemp(suffix=ext, prefix="resume_", dir=DATA_DIR)
    os.close(fd)
    return tmp_path
