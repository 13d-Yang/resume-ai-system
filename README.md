# AI 简历分析系统（RAG + MCP）

基于 **MCP 协议 + RAG 检索增强 + LangGraph 工作流** 的 AI 简历分析后端，
通过 JeecgBoot（Java + Vue3）提供前端界面，支持简历入库、语义检索、
RAG 问答、人才库搜索、JD 匹配、能力雷达图、面试题生成、风险筛查等能力。

## 技术栈

| 层 | 技术 |
|----|------|
| MCP 服务 | Python 3.10 · FastMCP（SSE，端口 8604） |
| HTTP 网关 | FastAPI · Uvicorn（端口 8501） |
| 大模型 | 智谱 GLM-4-Flash（分析/问答） |
| 向量化 | 硅基流动 bge-large-zh-v1.5（1024 维） |
| 工作流 | LangGraph（Agent / 雷达图 / JD 匹配） |
| 存储 | MySQL（业务表 + 向量分片）· DBUtils 连接池 |
| 文档解析 | PyMuPDF（PDF）· python-docx（Word，含表格/嵌套表格） |

## 目录结构

```
resume/
├── app/                        # 应用主代码（分层架构）
│   ├── config.py               # 全局配置（密钥/数据库/端口/路径）
│   ├── server_mcp.py           # MCP SSE 服务入口（8604）
│   ├── server_gateway.py       # FastAPI 网关入口（8501）
│   ├── core/                   # 基础设施：连接池、日志、LLM 客户端
│   ├── repositories/           # 数据访问层：所有 SQL 收敛于此
│   ├── services/               # 业务服务层：文档解析/向量化/RAG/关联修复
│   ├── workflows/              # LangGraph 工作流（agent/radar/match）
│   ├── tools/                  # MCP 工具注册层（FastMCP 单例）
│   └── gateway/                # 网关：安全中间件、JSON存储、SSE客户端、路由
├── scripts/                    # 运维脚本（历史数据补全、RAG 验证）
├── tests/                      # 单元测试 + SSE 冒烟测试
├── docs/                       # 设计文档
├── data/                       # 运行时数据（mcp_db.json，不提交）
├── logs/                       # 运行日志（不提交）
├── start_mcp.bat / .ps1        # 一键启动 MCP（8604）
├── start_parser.bat / .ps1     # 一键启动网关（8501）
├── requirements.txt
├── .env.example                # 环境变量模板
└── .gitignore
```

## 快速开始

### 1. 环境准备

```powershell
python -m venv venv310
.\venv310\Scripts\pip install -r requirements.txt
```

### 2. 配置密钥

复制 `.env.example` 为 `.env` 并填写，或在 Windows 设置用户环境变量：

- `ZHIPU_API_KEY`：智谱大模型密钥
- `SILICONFLOW_API_KEY`：硅基流动向量接口密钥
- `MYSQL_PASSWORD`：MySQL 密码（默认 root）

### 3. 启动服务（按顺序）

```powershell
# 终端1：MCP SSE 服务（8604）
.\start_mcp.bat

# 终端2：HTTP 网关（8501）
.\start_parser.bat
```

也可手动启动：

```powershell
.\venv310\Scripts\python.exe -m app.server_mcp
.\venv310\Scripts\python.exe -m app.server_gateway
```

## 测试

```powershell
# 离线单元测试（无需数据库/网络）
.\venv310\Scripts\python.exe -m pytest tests/test_units.py -v

# RAG 链路验证（需数据库 + 向量服务，只读）
.\venv310\Scripts\python.exe scripts\verify_rag.py

# MCP SSE 连通性（需先启动 8604）
.\venv310\Scripts\python.exe tests\test_sse.py
```

## 运维脚本

```powershell
# 历史简历的 knowledge_id 补全（先干跑预览）
.\venv310\Scripts\python.exe scripts\fix_knowledge_id.py
# 确认后真正执行
.\venv310\Scripts\python.exe scripts\fix_knowledge_id.py --execute
```

## MCP 工具清单

| 工具 | 说明 |
|------|------|
| `read_resume` | 读取简历并自动分片入库 |
| `rag_create_knowledge` | 创建知识库主记录 |
| `rag_knowledge_store_resume` | 文档分片 + 向量化入库 |
| `rag_knowledge_search_multi` | 多知识库语义检索 |
| `rag_resume_chat` | 单份简历 RAG 问答（带来源引用） |
| `rag_search_candidates` | 人才库全量语义搜索 + 排名 |
| `run_match` | 简历 JD 四维严格评分 |
| `run_radar` | 六维能力雷达图 |
| `gen_interview_question` | 面试题生成 |
| `resume_optimize` | 简历优化建议 |
| `resume_risk_check` | 风险点筛查 |
| `compare_multi_resume` | 多简历对比 |
| `run_agent_chat` | Agent 自由对话分析 |

## 安全约定

- API 密钥只从环境变量读取，禁止硬编码；
- 简历文件访问限制在白名单目录，上传使用随机临时文件名 + 扩展名白名单；
- CORS 仅放行 localhost / 127.0.0.1，外部来源预检返回 403；
- 向量检索与入库只处理 `del_flag=0` 的有效数据；
- 向量生成失败整体回滚，绝不写入空向量。
