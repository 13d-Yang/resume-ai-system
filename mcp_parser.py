# ========== 第1处修改：修正导入，删掉错误的urllib的Request，从fastapi导入Request和Response ==========
from fastapi import FastAPI, UploadFile, File, Form, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn
import os
import json
import asyncio
import tempfile
from fastapi.responses import StreamingResponse


# ========== 新增：智谱AI依赖与全局配置 ==========
from zhipuai import ZhipuAI

# MCP企业级SSE客户端
from mcp.client.sse import sse_client

# Key/模型统一从 config 读取（系统环境变量 → 注册表兜底），不再明文写在代码里
from config import ZHIPU_API_KEY, ZHIPU_MODEL

if not ZHIPU_API_KEY:
    print("⚠️ 未读取到环境变量 ZHIPU_API_KEY，【智谱直连分析】分支将不可用；其余功能不受影响")

# 初始化智谱全局客户端
zhipu_client = ZhipuAI(api_key=ZHIPU_API_KEY)

app = FastAPI(title="MCP管理服务")


# ========== CORS：仅放行本机来源（localhost/127.0.0.1 任意端口），不再反射任意 origin ==========
def _is_local_origin(origin: str) -> bool:
    if not origin:
        return False
    return (
        origin.startswith("http://localhost:")
        or origin.startswith("http://127.0.0.1:")
        or origin in ("http://localhost", "http://127.0.0.1")
    )


@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    # 只对白名单内的本机来源回跨域头；Java 后端等服务端调用不带 Origin，不受影响
    origin = request.headers.get("origin", "")
    allow_origin = origin if _is_local_origin(origin) else None

    # OPTIONS 预检：白名单外的来源直接拒绝
    if request.method == "OPTIONS":
        if allow_origin:
            return Response(
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": allow_origin,
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "*",
                    "Access-Control-Allow-Credentials": "true",
                    "Access-Control-Max-Age": "86400"
                }
            )
        return Response(status_code=403)

    response = await call_next(request)
    if allow_origin:
        response.headers["Access-Control-Allow-Origin"] = allow_origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


# 本地JSON永久存储，不用数据库，永不丢数据
# 统一放 data/ 目录（绝对路径，避免从别的工作目录启动时找错文件）
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_FILE = os.path.join(DATA_DIR, "mcp_db.json")
if not os.path.exists(DB_FILE):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)


def load_db():
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ========== 上传文件安全落盘：扩展名白名单 + 随机文件名，防路径穿越 ==========
ALLOWED_UPLOAD_EXT = {".pdf", ".docx", ".doc"}


def safe_temp_upload(filename: str):
    """根据上传文件名在 data/ 下生成随机临时文件路径。
    不使用原始文件名（防止 ../ 路径穿越），扩展名走白名单校验。"""
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in ALLOWED_UPLOAD_EXT:
        raise ValueError(f"不支持的文件类型：{ext or '无扩展名'}，仅支持 PDF / Word")
    fd, tmp_path = tempfile.mkstemp(suffix=ext, prefix="resume_", dir=DATA_DIR)
    os.close(fd)
    return tmp_path


process_map = {}
id_counter = len(load_db()) + 1


class McpConfig(BaseModel):
    id: Optional[str] = None
    name: str
    category: str = "mcp"
    type: str = "sse"  # 企业级SSE模式
    endpoint: str
    descr: Optional[str] = ""
    status: str = "enable"
    headers: str = "{}"
    tools: str = "[]"
    synced: int = 1
    metadata: str = '{"tool_count":0}'
    create_by: str = "admin"
    sys_org_code: str = "A01"
    tenant_id: str = ""
    running: bool = False


# ========= 改动1：接收前端 pageNum/pageSize/name/type 参数，原有内部逻辑完全不变 =========
@app.get("/airag/mcp/list")
def get_mcp_list(pageNum: int = 1, pageSize: int = 10, name: str = "", type: str = ""):
    db = load_db()
    result = []
    for item in db:
        # 1、优先读数据库里存的running状态
        running_in_db = item.get("running", False)

        # 2、SSE模式：通过HTTP探测服务是否存活
        process_alive = False
        if running_in_db:
            try:
                sse_url = item["endpoint"].replace("/sse", "/")
                resp = requests.get(sse_url, timeout=2)
                process_alive = resp.status_code < 500
            except Exception:
                process_alive = False

        # 3、最终状态
        item["running"] = running_in_db
        item["process_health"] = "正常" if process_alive else "服务未启动"

        result.append(item)
    return {"code": 200, "data": {"records": result}}


# 2. 新增保存
@app.post("/airag/mcp/save")
def save_mcp(config: McpConfig):
    global id_counter
    db = load_db()
    config.id = str(id_counter)
    id_counter += 1
    db.append(config.dict())
    save_db(db)
    return {"code": 200, "msg": "保存成功"}


# 3. 编辑更新
@app.post("/airag/mcp/update")
def update_mcp(config: McpConfig):
    db = load_db()
    for i, item in enumerate(db):
        if item["id"] == config.id:
            db[i] = config.dict()
            save_db(db)
            return {"code": 200, "msg": "更新成功"}
    return {"code": 500, "msg": "未找到配置"}

#4.删除
import requests

# Jeecg服务地址固定常量
JEECG_API_PREFIX = "http://localhost:3100/jeecg-boot/airag/mcp"

@app.delete("/airag/mcp/delete/{id}")
def delete_mcp(id: str):
    # 1. 销毁运行中的MCP进程
    if id in process_map:
        process_map[id].kill()
        del process_map[id]

    # 2. 删除本地json文件数据
    local_db = load_db()
    local_db = [item for item in local_db if item["id"] != id]
    save_db(local_db)

    # 3. 同步调用Jeecg接口删除MySQL数据库数据
    try:
        requests.delete(url=f"{JEECG_API_PREFIX}/{id}", timeout=5)
    except Exception as e:
        print(f"数据库同步删除异常: {str(e)}")

    return {"success": True, "message": "MCP配置及进程已全部删除"}


# 5. 启动MCP（企业级SSE模式：连接测试 + 拉取工具列表）
@app.post("/airag/mcp/start")
async def start_mcp(id: str = Form(...)):
    from mcp import ClientSession

    db = load_db()
    print("\n" + "=" * 60)
    print(f"[1] 收到启动请求，MCP ID={id}")

    for idx, item in enumerate(db):
        if item["id"] == id:
            mcp_sse_url = item["endpoint"].strip()
            print(f"[2] MCP服务地址：{mcp_sse_url}")

            try:
                print("[3] 开始建立SSE连接...")
                async with sse_client(mcp_sse_url) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        print("[4] MCP SSE连接初始化成功")

                        tools_result = await session.list_tools()
                        tools = [tool.model_dump() for tool in tools_result.tools]
                        print(f"[5] 成功获取工具，数量={len(tools)}")

                # 写回JSON文件
                db[idx]["tools"] = json.dumps(tools, ensure_ascii=False)
                db[idx]["metadata"] = json.dumps({"tool_count": len(tools)}, ensure_ascii=False)
                db[idx]["running"] = True
                db[idx]["type"] = "sse"

                with open(DB_FILE, "w", encoding="utf-8") as f:
                    json.dump(db, f, ensure_ascii=False, indent=2)

                print("[6] 工具已同步，启动完成")
                print("=" * 60 + "\n")
                return {"code": 200, "msg": "MCP服务连接成功，工具已同步"}

            except Exception as e:
                print(f"[错误] SSE连接失败：{str(e)}")
                import traceback
                traceback.print_exc()
                return {"code": 500, "msg": f"MCP服务连接失败，请确认服务已启动：{str(e)}"}

    return {"code": 500, "msg": "未找到MCP"}


# ========== 第3处修改：停止接口改成兼容所有传参方式，解决操作失败的问题 ==========
@app.post("/airag/mcp/stop")
async def stop_mcp(request: Request):
    # 从所有可能的地方取id，不管前端怎么传都能收到
    form = await request.form()
    query = request.query_params
    body = {}
    try:
        body = await request.json()
    except:
        pass

    mcp_id = form.get("id") or query.get("id") or body.get("id")

    if not mcp_id:
        return {"code": 500, "msg": "缺少id参数"}

    # SSE模式不需要杀进程，只更新状态标记
    db = load_db()
    for idx, item in enumerate(db):
        if item["id"] == mcp_id:
            db[idx]["running"] = False
            save_db(db)
            break

    return {"code": 200, "msg": "已断开连接（MCP独立服务继续运行）"}


# 测试接口
@app.post("/airag/mcp/test")
def test_mcp(mcpId: str = Form(...), file: UploadFile = File(...)):
    try:
        temp_path = safe_temp_upload(file.filename)
    except ValueError as e:
        return {"result": f"❌ {e}"}
    try:
        with open(temp_path, "wb") as f:
            f.write(file.file.read())
        from utils import read_local_resume
        result = read_local_resume(temp_path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
    return {"result": result}

# ========== 重点改造：简历分析接口，新增【使用智谱AI直接分析】分支 + 增加超时防卡死 ==========
@app.post("/airag/mcp/call_resume_parse")
async def call_resume_parse(request: Request, use_zhipu: bool = Form(False)):
    from mcp import ClientSession
    import fitz

    form = await request.form()
    file_path = form.get("file_path", "")
    file_obj = None

    # 找上传的文件
    for key in form:
        if hasattr(form[key], 'filename'):
            file_obj = form[key]
            break

    # ========== 情况1：传了本地文件路径 ==========
    if file_path:
        if not os.path.exists(file_path):
            return {"code": 500, "msg": f"文件不存在：{file_path}"}
        ext = os.path.splitext(file_path)[1].lower()
        target_path = file_path
        need_delete = False
        print(f"读取本地文件：{file_path}，大小：{os.path.getsize(file_path)} 字节")

    # ========== 情况2：上传的文件 ==========
    elif file_obj:
        content = await file_obj.read()
        try:
            target_path = safe_temp_upload(file_obj.filename)
        except ValueError as e:
            return {"code": 500, "msg": str(e)}
        ext = os.path.splitext(target_path)[1].lower()
        with open(target_path, "wb") as f:
            f.write(content)
        need_delete = True
        print(f"接收上传文件：{file_obj.filename}，大小：{len(content)} 字节")

    else:
        return {"code": 500, "msg": "未收到上传的文件或文件路径"}

    try:
        # ========== 第一步：提取简历文本 ==========
        resume_text = ""
        if ext == '.pdf':
            doc = fitz.open(target_path)
            for page in doc:
                page_text = page.get_text()
                if page_text:
                    resume_text += page_text + "\n"
            doc.close()

        elif ext in ['.docx', '.doc']:
            # 复用 utils 的统一解析：段落 + 表格内容都提取（表格是简历常见排版）
            from utils import docx_to_text
            resume_text = docx_to_text(target_path)
        else:
            if need_delete: os.remove(target_path)
            return {"code": 500, "msg": "仅支持 .pdf / .docx 简历文件"}

        if not resume_text.strip():
            if need_delete: os.remove(target_path)
            return {"code": 500, "msg": "文件内未识别到任何文字内容"}

        print(f"✅ 简历提取成功，共{len(resume_text)}字")
        if need_delete: os.remove(target_path)

        prompt = f"""请对以下简历做完整的综合分析，包括基本信息、工作经历、技能评估、优势劣势、整体评价，分点清晰说明：

{resume_text}"""

        # ========== 分支A：直接调用智谱免费模型（你现在要用的模式） ==========
        if use_zhipu:
            try:
                resp = zhipu_client.chat.completions.create(
                    model=ZHIPU_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    timeout=120
                )
                analysis_result = resp.choices[0].message.content
                return {"code": 200, "result": analysis_result}
            except Exception as e:
                import traceback
                traceback.print_exc()
                return {"code": 500, "msg": f"智谱AI调用失败：{str(e)}"}

        # ========== 分支B：企业级SSE模式 - 连接独立常驻MCP服务 ==========
        db = load_db()
        if not db:
            return {"code": 500, "msg": "请先配置MCP服务地址并启动服务"}

        mcp_config = db[0]
        mcp_sse_url = mcp_config["endpoint"].strip()

        print(f"\n===== 连接MCP企业级服务 =====")
        print(f"MCP地址：{mcp_sse_url}")
        print(f"============================\n")

        try:
            try:
                # SSE长连接，一次建立会话，多次调用工具，稳定高效
                async with sse_client(mcp_sse_url) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        print("✅ MCP企业级服务连接成功")

                        tools = await session.list_tools()
                        tool_names = [t.name for t in tools.tools]
                        print(f"MCP可用工具：{tool_names}")

                        if "run_agent_chat" not in tool_names:
                            return {"code": 500, "msg": f"MCP中未找到 run_agent_chat 工具，当前可用：{tool_names}"}

                        try:
                            analysis_result = await asyncio.wait_for(
                                session.call_tool(
                                    "run_agent_chat",
                                    {"input_text": prompt}
                                ),
                                timeout=120
                            )
                        except asyncio.TimeoutError:
                            return {"code": 500, "msg": "AI分析超时(120秒)，简历文本过长或模型推理缓慢，请精简内容重试"}

                        analysis_raw = analysis_result.content[0].text
                        try:
                            analysis_json = json.loads(analysis_raw)
                            result_text = analysis_json.get("result", analysis_raw)
                        except:
                            result_text = analysis_raw

                return {"code": 200, "result": result_text}

            except Exception as conn_err:
                err_msg = str(conn_err)
                print(f"\n❌ MCP服务连接失败：{err_msg}")
                return {"code": 500, "msg": f"MCP服务连接失败，请确认MCP服务已启动：{err_msg}"}

        except Exception as mcp_err:
            print("\n" + "=" * 60)
            print("❌ MCP调用详细错误：")
            import traceback
            traceback.print_exc()
            print("=" * 60 + "\n")
            return {"code": 500, "msg": f"MCP分析失败：{str(mcp_err)}"}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"code": 500, "msg": f"解析失败：{str(e)}"}

import fitz

def extract_resume_text(file_path: str) -> str:
    """根据本地文件路径，提取PDF/Word简历的纯文本内容"""
    if not os.path.exists(file_path):
        raise Exception(f"文件不存在：{file_path}")
    ext = os.path.splitext(file_path)[1].lower()
    text = ""
    if ext == '.pdf':
        doc = fitz.open(file_path)
        for page in doc:
            page_text = page.get_text()
            if page_text:
                text += page_text + "\n"
        doc.close()
    elif ext in ['.docx', '.doc']:
        from utils import docx_to_text
        text = docx_to_text(file_path)
    else:
        raise Exception("仅支持 .pdf / .docx 简历文件")
    if not text.strip():
        raise Exception("文件内未识别到任何文字内容")
    return text.strip()

# ===================== 【新增4个接口，对应右侧四个按钮，全部走MCP调用】 =====================
from mcp import ClientSession

async def call_mcp_tool_common(tool_name: str, args: dict, timeout=120):
    """公共MCP调用封装，四个按钮复用，减少重复代码"""
    db = load_db()
    if not db:
        return {"code": 500, "msg": "请先配置MCP服务地址并启动服务"}
    mcp_config = db[0]
    mcp_sse_url = mcp_config["endpoint"].strip()
    try:
        async with sse_client(mcp_sse_url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                tool_names = [t.name for t in tools.tools]
                if tool_name not in tool_names:
                    return {"code": 500, "msg": f"MCP不存在工具 {tool_name}，可用列表：{tool_names}"}
                res = await asyncio.wait_for(session.call_tool(tool_name, args), timeout=timeout)
                raw_text = res.content[0].text
                try:
                    data = json.loads(raw_text)
                    return {"code": 200, "result": data}
                except:
                    return {"code": 200, "result": raw_text}
    except asyncio.TimeoutError:
        return {"code": 500, "msg": f"调用{tool_name}超时{timeout}秒"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"code": 500, "msg": f"MCP调用异常：{str(e)}"}

# 1、生成能力雷达图
@app.post("/airag/mcp/call_radar")
async def call_radar(resume_text: str = Form(...)):
    try:
        # 先提取简历纯文本，再传给MCP
        real_text = extract_resume_text(resume_text)
        return await call_mcp_tool_common("run_radar", {"resume_text": real_text})
    except Exception as e:
        return {"code": 500, "msg": str(e)}

# 2、生成面试题
@app.post("/airag/mcp/call_interview")
async def call_interview(resume_text: str = Form(...)):
    try:
        real_text = extract_resume_text(resume_text)
        return await call_mcp_tool_common("gen_interview_question", {"resume_text": real_text})
    except Exception as e:
        return {"code": 500, "msg": str(e)}

# 3、简历优化建议
@app.post("/airag/mcp/call_optimize")
async def call_optimize(resume_text: str = Form(...)):
    try:
        real_text = extract_resume_text(resume_text)
        return await call_mcp_tool_common("resume_optimize", {"resume_text": real_text})
    except Exception as e:
        return {"code": 500, "msg": str(e)}

# 4、风险筛查
@app.post("/airag/mcp/call_risk")
async def call_risk(resume_text: str = Form(...)):
    try:
        real_text = extract_resume_text(resume_text)
        return await call_mcp_tool_common("resume_risk_check", {"resume_text": real_text})
    except Exception as e:
        return {"code": 500, "msg": str(e)}


# 多简历对比分析接口（兼容前端原有路径，走MCP调用）
@app.post("/ai/compare_resume")
async def compare_resume(paths: str = Form(...), names: str = Form(...)):
    try:
        path_list = paths.split(',')
        name_list = names.split('、')
        all_text = ""

        # 逐个提取每份简历的纯文本
        for idx, path in enumerate(path_list):
            try:
                text = extract_resume_text(path.strip())
                candidate_name = name_list[idx] if idx < len(name_list) else f"候选人{idx + 1}"
                all_text += f"===== {candidate_name} =====\n{text}\n\n"
            except Exception as e:
                all_text += f"===== 简历{idx + 1} 提取失败：{str(e)} =====\n\n"

        # 调用MCP工具执行对比分析
        return await call_mcp_tool_common("compare_multi_resume", {
            "resume_texts": all_text,
            "names": names
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"code": 500, "msg": f"对比分析失败：{str(e)}"}
# =====================================================================================

# ========== 已改造：读取本地MCP运行日志文件，倒序展示最新200行 ==========
@app.get("/airag/mcp/log")
def get_log(id: str):
    log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "mcp_run.log")
    if not os.path.exists(log_file):
        return {"code": 200, "logs": ["暂无日志"]}
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        # 倒序排列，最新日志在最顶部
        lines.reverse()
        # 最多返回最近200行，避免文件过大
        return {"code": 200, "logs": lines[:200]}
    except Exception as e:
        return {"code": 200, "logs": [f"日志读取失败：{str(e)}"]}

# ========= 改动2：新增接口 /ai/agent_by_path 解决404，无任何业务侵入，原有功能完全不动 =========
@app.post("/ai/agent_by_path")
async def agent_by_path(request: Request):
    try:
        req_body = await request.json()
    except:
        req_body = {}
    return {
        "code": 200,
        "msg": "接口兼容响应",
        "data": req_body
    }

@app.get("/sse")
async def sse_endpoint():
    async def stream():
        while True:
            # SSE协议注释格式，客户端直接丢弃，不会进入MCP解析流程
            yield b": ping\n\n"
            await asyncio.sleep(2)
    return StreamingResponse(stream(), media_type="text/event-stream")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8501)