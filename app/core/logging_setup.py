# -*- coding: utf-8 -*-
"""日志统一配置：控制台 + 按大小滚动的文件 handler，日志全部落 logs/ 目录。"""
import logging
import sys
from logging.handlers import RotatingFileHandler

from app.config import LOG_DIR


def configure_logging() -> None:
    """初始化全局日志（幂等：重复调用不会叠加 handler）。"""
    import os
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, "mcp_run.log")

    if getattr(configure_logging, "_done", False):
        return

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=2, encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    logging.basicConfig(level=logging.INFO, handlers=[stream_handler, file_handler])
    logging.getLogger("mcp.server.lowlevel.server").setLevel(logging.ERROR)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)

    configure_logging._done = True
