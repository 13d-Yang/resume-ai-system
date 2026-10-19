# -*- coding: utf-8 -*-
"""全局配置：密钥、数据库、端口、路径统一在此管理，业务代码禁止散落硬编码。

密钥读取顺序：进程环境变量 -> Windows 注册表用户环境变量（兜底）。
路径全部基于本文件位置推导，保证从任意工作目录启动都能定位到 data/、logs/。
"""
import os
import sys

import pymysql


def _get_secret(name, default=""):
    """读取密钥：先查当前进程环境变量；读不到时（旧终端/IDE启动的进程拿不到
    新设的环境变量），Windows 下直接去注册表的【用户环境变量】兜底读取。"""
    val = os.getenv(name)
    if val:
        return val
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                val, _ = winreg.QueryValueEx(key, name)
                if val:
                    return val
        except OSError:
            pass
    return default


# ========== 路径配置（集中管理，禁止业务代码自行拼路径） ==========
# app/config.py -> 上两级即项目根目录 resume/
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")

# ========== 智谱大模型配置 ==========
# Key 不写死在代码里：系统环境变量 ZHIPU_API_KEY，注册表用户变量兜底
ZHIPU_API_KEY = _get_secret("ZHIPU_API_KEY", "")
ZHIPU_MODEL = "glm-4-flash"
ZHIPU_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"

# ========== 向量模型配置（硅基流动，bge-large-zh 免费） ==========
# 注册并创建密钥：https://cloud.siliconflow.cn/account/ak
SILICONFLOW_API_KEY = _get_secret("SILICONFLOW_API_KEY", "")
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
# bge-large-zh-v1.5：中文向量、1024维、免费、单条最大512 token
EMBED_MODEL = "BAAI/bge-large-zh-v1.5"

# ========== MySQL jeecg-boot 库配置 ==========
MYSQL_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": _get_secret("MYSQL_PASSWORD", "root"),
    "database": "jeecg-boot",
    "cursorclass": pymysql.cursors.DictCursor,
}

# ========== 数据库连接池配置（DBUtils PooledDB） ==========
DB_POOL_CONFIG = {
    "mincached": 2,        # 启动时预建连接数
    "maxcached": 10,       # 连接池中空闲连接上限
    "maxconnections": 20,  # 连接总数上限
    "blocking": True,      # 连接耗尽时等待而非报错
}

# ========== 简历文件访问白名单目录 ==========
# 只允许读取该目录下的简历文件，防止任意文件读取/路径穿越
# 默认指向项目根的上一级目录（Resume 文件夹），可用环境变量 RESUME_BASE_DIR 覆盖
RESUME_BASE_DIR = os.getenv(
    "RESUME_BASE_DIR",
    os.path.dirname(PROJECT_ROOT),
)

# ========== 服务端口 ==========
# MCP 服务仅本机访问，HOST 固定 127.0.0.1
HOST = "127.0.0.1"
PORT_FASTAPI = 8501

# 三合一综合 MCP 服务端口
PORT_MCP_ALL = 8604

# MCP SSE 服务完整地址（供网关调用）
MCP_SSE_ENDPOINT = f"http://{HOST}:{PORT_MCP_ALL}/sse"
