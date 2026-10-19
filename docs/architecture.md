# 系统架构说明

## 1. 总体架构

```
Vue3 前端 (JeecgBoot, :3100)
        │ HTTP
        ▼
Java Spring Boot 业务系统 (JeecgBoot)
        │ MCP over SSE
        ▼
┌──────────────────────────────────────────────┐
│ Python 服务                                                  │
│                                                              │
│  FastAPI 网关 app.server_gateway (:8501)                     │
│    └─ gateway/  安全(CORS) · JSON存储 · SSE客户端 · 路由      │
│                                                              │
│  FastMCP 服务 app.server_mcp (:8604)                         │
│    └─ tools/     MCP 工具注册（对外契约，工具名不可随意改）    │
│       └─ services/  业务编排（RAG / 解析 / 向量化）           │
│          └─ repositories/  SQL 访问（连接池）                 │
│             └─ MySQL（jeecg-boot 库）                         │
│    └─ workflows/ LangGraph（agent / radar / match）           │
│    └─ core/      连接池 · 日志 · LLM 客户端                   │
└──────────────────────────────────────────────┘
        │                          │
        ▼                          ▼
  智谱 GLM-4-Flash          硅基流动 bge-large-zh-v1.5
  （生成/分析）              （文本向量化，1024 维）
```

## 2. 分层职责与依赖方向

依赖只能自上而下，**禁止反向依赖与跨层调用**：

```
tools / gateway.routes   接入层：协议适配、参数校验，不写业务
        ↓
services                 业务层：业务规则、事务边界、外部能力编排
        ↓
repositories             数据层：SQL 与数据库交互
        ↓
core / config             基础设施：连接池、日志、LLM、配置
```

- `tools` 之间不互相调用；公共逻辑下沉到 `services`。
- `services` 不允许出现 SQL；`repositories` 不允许出现业务分支。
- FastMCP 实例由 `app/tools/mcp_instance.py` 统一持有，各工具模块共享单例。

## 3. RAG 全链路

1. **入库**：`read_resume` / `rag_knowledge_store_resume`
   - 中文分片器（400 字/片，重叠 60 字）
   - 批量调用 bge 向量化（失败即整体回滚，不写空向量）
   - 向量以 JSON 存入 `rag_doc_chunk.embedding`，主表写 `rag_knowledge`
2. **检索**：问题向量化 → 拉取有效分片（`del_flag=0`）→ 余弦相似度 → 阈值过滤
3. **生成**：片段拼装为带编号上下文 → GLM 强约束"只用片段、无依据说未提及"
4. **溯源**：回答附带命中片段序号、相似度与完整原文
5. **人才搜索**：全库召回 → 按简历聚合 top3 平均分 → 同名去重 → 分档排名

## 4. 数据库连接池

`app/core/db.py` 基于 DBUtils `PooledDB` 提供进程级单例连接池：

- `mincached=2 / maxcached=10 / maxconnections=20`
- `db_cursor()` 上下文管理器：正常提交、异常回滚、连接自动归还
- 业务代码禁止再直接 `pymysql.connect()`

## 5. 关键设计约束（Hard Constraints）

- 密钥只走环境变量（Windows 注册表用户变量兜底）；
- 简历访问白名单目录 + 上传随机临时文件名 + 扩展名白名单（防路径穿越）；
- CORS 仅本机来源；
- 向量数据只认 `del_flag=0`；向量失败必回滚；
- 运行时数据进 `data/`，日志进 `logs/`，均不提交 Git。
