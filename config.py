import os
import sys

import pymysql


def _get_secret(name, default=""):
    """读取密钥：先查当前进程环境变量；读不到时（旧终端/IDE启动的进程拿不到
    新设的环境变量），Windows 下直接去注册表的【用户环境变量】兜底读取。
    这样无论服务从 bat、IDE 还是旧终端启动，都能拿到最新密钥。"""
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


# ========== 智谱大模型配置 ==========
# Key 不写死在代码里：系统环境变量 ZHIPU_API_KEY，注册表用户变量兜底
ZHIPU_API_KEY = _get_secret("ZHIPU_API_KEY", "")
ZHIPU_MODEL = "glm-4-flash"

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
    "password": _get_secret("MYSQL_PASSWORD", "root"),  # 生产环境请用环境变量 MYSQL_PASSWORD
    "database": "jeecg-boot",
    "cursorclass": pymysql.cursors.DictCursor
}

# ========== 简历文件访问白名单目录 ==========
# 只允许读取该目录下的简历文件，防止任意文件读取/路径穿越
# 默认指向本文件上一级目录（Resume 文件夹），可用环境变量 RESUME_BASE_DIR 覆盖
RESUME_BASE_DIR = os.getenv(
    "RESUME_BASE_DIR",
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

# ========== 服务端口 ==========
# 注意：MCP 服务无需对外暴露时，建议把 HOST 改成 "127.0.0.1"
HOST = "127.0.0.1"
PORT_FASTAPI = 8501
PORT_MCP_PARSER = 8601
PORT_MCP_RAG = 8602
PORT_MCP_LLM = 8603

# 三合一综合 MCP 服务端口
PORT_MCP_ALL = 8604
