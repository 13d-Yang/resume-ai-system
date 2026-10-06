import json
import logging
import sys
import os
import requests
import numpy as np
import pymysql
import uuid
from logging.handlers import RotatingFileHandler
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import ToolMessage, BaseMessage, HumanMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter
from mcp.server.fastmcp import FastMCP
from config import (
    HOST, PORT_MCP_ALL, ZHIPU_API_KEY, ZHIPU_MODEL, MYSQL_CONFIG,
    SILICONFLOW_API_KEY, SILICONFLOW_BASE_URL, EMBED_MODEL
)
from utils import read_local_resume
from zhipuai import ZhipuAI

# ========== 全局智谱客户端初始化（负责聊天/分析） ==========
zhipu_client = ZhipuAI(api_key=ZHIPU_API_KEY)
ZHIPU_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"

# ========== 全局日志配置 ==========
# 日志统一放 logs/ 目录，与代码分离（目录不存在则自动创建）
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "mcp_run.log")
stream_handler = logging.StreamHandler(sys.stderr)
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=2, encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logging.basicConfig(
    level=logging.INFO,
    handlers=[stream_handler, file_handler]
)
logging.getLogger("mcp.server.lowlevel.server").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

# ========== MCP实例 ==========
mcp = FastMCP("简历综合MCP", host=HOST, port=PORT_MCP_ALL)

# ========== 中文简历专用分片器 ==========
# bge-large-zh-v1.5 单条最大 512 token（中文约400字），分片过大尾部会被截断丢内容
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=400,
    chunk_overlap=60,
    separators=[
        "\n\n", "\n", "。", "！", "？", "；",
        ". ", "! ", "? ",
        " "
    ]
)


def ai_call(prompt: str, system_prompt: str = None) -> str:
    logging.info(f"【智谱LLM调用】文本长度：{len(prompt)}，模型：{ZHIPU_MODEL}")

    # 默认 system prompt：禁止复读，强制输出结论
    if system_prompt is None:
        system_prompt = (
            "你是一位资深HR专家。严格按用户指令执行任务，"
            "绝对不要复述用户提供的原始文本，只输出你的分析结论和建议。"
        )

    try:
        resp = zhipu_client.chat.completions.create(
            model=ZHIPU_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            timeout=120
        )
        result = resp.choices[0].message.content
        logging.info(f"【智谱LLM完成】返回长度：{len(result)}")
        return result
    except Exception as e:
        logging.exception("【智谱LLM调用失败】")
        return f"❌LLM调用异常：{str(e)}"

# 新增：消息裁剪工具，只保留最近N条消息，防止上下文溢出
def trim_messages(messages: list[BaseMessage], keep_last:int=4) -> list[BaseMessage]:
    if len(messages) <= keep_last:
        return messages
    return messages[-keep_last:]


# ========== 内部工具 ==========
# ========== 内部工具 ==========
@tool
def analyze_resume_text(text:str)->str:
    """分析简历文本，输出HR专业分析报告"""
    return ai_call(
        f"简历全文如下：\n{text}",
        system_prompt=(
            "你是一位拥有15年经验的资深HR专家。"
            "请对这份简历输出结构化的分析报告，必须包含四部分："
            "1. 综合评分（0-100） 2. 核心优势 3. 明显短板 4. 改进建议。"
            "严禁复述简历原文，只输出分析结论。使用中文。"
        )
    )

@tool
def gen_question_text(text:str)->str:
    """基于简历内容生成面试问题"""
    return ai_call(
        f"简历全文如下：\n{text}",
        system_prompt=(
            "你是一位资深面试官。请基于候选人简历，输出8-10个专业的面试问题，"
            "按'技术能力'、'项目经验'、'软技能'三个分类。"
            "只输出问题列表，不要复述简历原文，不要输出分析。使用中文。"
        )
    )

@tool
def optimize_text(text:str)->str:
    """对简历文本进行优化润色"""
    return ai_call(
        f"原简历如下：\n{text}",
        system_prompt=(
            "你是一位简历优化专家。请对这份简历进行润色，"
            "输出优化后对简历的修改意见，以及修改好之后的简历。"
            "输出优化后的简历"
        )
    )

@tool
def risk_check_text(text:str)->str:
    """检测简历存在的风险点"""
    return ai_call(
        f"简历全文如下：\n{text}",
        system_prompt=(
            "你是一位资深背景调查专家。请从这份简历中识别潜在风险点，"
            "包括：时间线断层、夸大表述、逻辑矛盾、合规风险等。"
            "只输出风险点清单和简要说明，严禁复述简历原文，不要输出分析报告。使用中文。"
        )
    )

#========== Agent工作流【全部注释，规避智谱tool‑call 400报错】 ==========
llm = ChatOpenAI(
    model=ZHIPU_MODEL,
    api_key=ZHIPU_API_KEY,
    base_url=ZHIPU_BASE_URL,
    temperature=0.3,
    timeout=120,
    max_retries=2
)
tools = [analyze_resume_text, gen_question_text, optimize_text, risk_check_text]
tool_map = {t.name: t for t in tools}
llm_with_tools = llm.bind_tools(tools)

class AgentState(TypedDict):
    messages: list

def agent_node(state: AgentState):
    logging.info("【Agent执行节点】")
    # 关键：每次进入agent节点裁剪消息，避免消息无限累积
    trimmed = trim_messages(state["messages"], keep_last=4)
    result = llm_with_tools.invoke(trimmed)
    return {"messages": [result]}

def tool_call_node(state: AgentState):
    last_msg = state["messages"][-1]
    outputs = []
    for call in last_msg.tool_calls:
        tool_func = tool_map[call["name"]]
        res = tool_func.invoke(call["args"])
        outputs.append(ToolMessage(content=str(res), tool_call_id=call["id"]))
    return {"messages": outputs}

def should_continue(state: AgentState):
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tool"
    return END

agent_graph = StateGraph(AgentState)
agent_graph.add_node("agent", agent_node)
agent_graph.add_node("tool", tool_call_node)
agent_graph.add_conditional_edges("agent", should_continue)
agent_graph.add_edge("tool", "agent")
agent_graph.set_entry_point("agent")
agent_app = agent_graph.compile()

# ========== 雷达图工作流 ==========
class RadarState(TypedDict):
    resume_text: str
    radar_result: dict

def radar_node(state: RadarState):
    prompt = """
只输出纯JSON，不要多余文字！
6个维度0-100分：工作经验、学历背景、专业技能、项目含金量、沟通协作、稳定性
必须同时输出这4个字段：scoreArr、totalScore、advantage、risk
示例：{"scoreArr":[80,70,85,75,60,72],"totalScore":74,"advantage":"xxx","risk":"xxx"}
简历：
""" + state["resume_text"]
    out = ai_call(
        prompt,
        system_prompt="你是资深HR，严格按JSON格式输出，不要多余文字。"
    )
    out = out.replace("```json","").replace("```","").strip()
    try:
        data = json.loads(out)
        # ✅ Python自己兜底再算一遍平均分，防止模型乱给
        if "scoreArr" in data and len(data["scoreArr"]) > 0:
            nums = [float(x) for x in data["scoreArr"] if str(x).replace('.','').isdigit()]
            if nums:
                data["totalScore"] = round(sum(nums) / len(nums), 1)
        logging.info(f"【雷达图解析成功】{data}")
    except Exception as e:
        logging.error(f"【雷达图JSON解析失败】raw={out}, err={str(e)}")
        data = {"scoreArr":[50,50,50,50,50,50],"totalScore":50,"advantage":"解析失败","risk":"解析失败"}
    return {"radar_result": data}

radar_graph = StateGraph(RadarState)
radar_graph.add_node("radar_gen", radar_node)
radar_graph.set_entry_point("radar_gen")
radar_graph.add_edge("radar_gen", END)
radar_app = radar_graph.compile()

# ========== 简历匹配工作流 ==========
class MatchState(TypedDict):
    resume_text: str
    jd: str
    extract_info: str
    score_result: dict
    final: dict

def extract_node(state: MatchState):
    ret = ai_call(f"提取简历关键信息：\n简历：{state['resume_text']}\nJD：{state['jd']}")
    return {"extract_info": ret}

def score_node(state: MatchState):
    prompt = f"""你是一位极其严格的HR评分专家。请对照【JD岗位要求】给候选人评分。

【评分维度说明】
- major（专业匹配度）：专业、学历、行业背景是否与JD要求匹配
- exp（工作经验）：工作年限、项目经验是否达到JD要求
- skill（技能匹配）：JD要求的技能，候选人简历里真正具备多少
- quality（综合素养）：沟通、协作、稳定性等，需有简历证据支撑

【严格评分规则】
1. 必须以JD为唯一标尺！JD没要求的技能，即使简历写了一大堆，也不能加分
2. 简历里与JD完全无关的内容（如"会做饭"、"会唱歌"），一律不计入任何维度
3. 如果核心技能与JD差距大，skill维度必须给低分（30分以下）
4. 严禁"老好人式"打分。不匹配就给低分，60分是及格线，80分以上才是优秀
5. 每个维度0-100分

【输出格式】
只输出纯JSON，不要多余文字！
示例：{{"major":75,"exp":60,"skill":45,"quality":70}}

【简历信息】
{state['extract_info']}

【JD岗位要求】
{state['jd']}
"""
    raw = ai_call(
        prompt,
        system_prompt="你是极其严格的HR评分专家。严格按JD评分，绝不给'人情分'。只输出纯JSON。"
    ).replace("```json","").replace("```","").strip()
    try:
        d = json.loads(raw)
        logging.info(f"【match评分】{d}")
    except Exception as e:
        logging.error(f"【match解析失败】{raw} {e}")
        d = {"major":0,"exp":0,"skill":0,"quality":0}
    return {"score_result": d}
def final_node(state: MatchState):
    s = state["score_result"]
    # 模型若返回非对象JSON（如数组），统一按空处理，避免 .get 抛 AttributeError
    if not isinstance(s, dict):
        s = {}

    # 模型可能漏返回字段或返回字符串，统一做安全取值：缺失/非法按0分，并限制在0-100
    def _safe_score(key: str) -> int:
        try:
            v = float(s.get(key, 0))
        except (TypeError, ValueError):
            return 0
        return max(0, min(100, round(v)))

    major = _safe_score("major")
    exp = _safe_score("exp")
    skill = _safe_score("skill")
    quality = _safe_score("quality")
    total = major + exp + skill + quality
    # ✅ 换算成百分制
    avg_total = round(total / 4, 1)
    level, tip = ("推荐录用",1) if total>=280 else ("待定观察",2) if total>=200 else ("不匹配",0)
    return {"final": {
        "totalScore": avg_total,
        "subScore": {
            "major": major,
            "exp": exp,
            "skill": skill,
            "quality": quality
        },
        "advice": level,
        "level_code": tip
    }}

match_graph = StateGraph(MatchState)
match_graph.add_node("extract", extract_node)
match_graph.add_node("score", score_node)
match_graph.add_node("final", final_node)
match_graph.set_entry_point("extract")
match_graph.add_edge("extract","score")
match_graph.add_edge("score","final")
match_graph.add_edge("final", END)
match_app = match_graph.compile()

# ========== 向量工具（硅基流动 bge-large-zh-v1.5，免费） ==========
def _call_siliconflow_embeddings(inputs: list[str]) -> list[list[float]]:
    """
    统一的向量请求：inputs 为文本列表，返回按 index 排序的向量列表。
    失败时抛出异常，由调用方决定回滚，绝不静默返回空向量。
    """
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


def get_cloud_embedding(input_text: str):
    """单条文本向量化（检索时用）"""
    return _call_siliconflow_embeddings([input_text])[0]


def get_cloud_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """
    批量向量化：一次请求处理多个分片，比逐片调用快得多、网络开销小。
    """
    if not texts:
        return []
    return _call_siliconflow_embeddings(texts)

def rag_get_db_conn():
    return pymysql.connect(**MYSQL_CONFIG)

def cosine_similarity(a, b):
    arr_a = np.array(a, dtype=np.float32)
    arr_b = np.array(b, dtype=np.float32)
    norm_a = np.linalg.norm(arr_a)
    norm_b = np.linalg.norm(arr_b)
    # 空向量（向量化失败兜底为[]）时范数为0，直接返回0分，避免除零崩溃
    if norm_a == 0 or norm_b == 0 or arr_a.shape != arr_b.shape:
        return 0.0
    return float(np.dot(arr_a, arr_b) / (norm_a * norm_b))

@mcp.tool()
def rag_create_knowledge(knowledge_id: str, knowledge_name: str, description: str = "") -> str:
    """
    创建知识库主记录，写入rag_knowledge表
    """
    return _rag_create_knowledge_internal(knowledge_id, knowledge_name, description)


def _rag_create_knowledge_internal(knowledge_id: str, knowledge_name: str, description: str = "") -> str:
    """
    【内部函数】写入rag_knowledge主表。
    已存在则返回 "existed"，避免重复插入。MCP工具和read_resume都复用此函数，
    保证入库分片前主表一定有对应记录。
    """
    logging.info(f"【rag_create_knowledge】开始创建主记录 knowledge_id={knowledge_id}")
    db = None
    cur = None
    try:
        db = pymysql.connect(**MYSQL_CONFIG)
        cur = db.cursor()
        # 先判断是否已经存在，避免重复插入
        cur.execute("SELECT id FROM rag_knowledge WHERE id = %s", (knowledge_id,))
        row = cur.fetchone()
        if row is not None:
            logging.info("知识库记录已存在，无需新增")
            return "success: existed"

        sql = """
        INSERT INTO rag_knowledge
        (id, knowledge_name, description, create_by, del_flag)
        VALUES (%s, %s, %s, %s, %s)
        """
        cur.execute(sql, (knowledge_id, knowledge_name, description, "mcp-service", 0))
        db.commit()
        logging.info("【rag_create_knowledge】主表插入成功")
        return "success: created"
    except Exception as e:
        if db:
            db.rollback()
        logging.error(f"创建知识库异常：{e}")
        return f"fail:{str(e)}"
    finally:
        if cur:
            cur.close()
        if db:
            db.close()

# ========== 核心修复：RAG入库工具【完整日志版本】 ==========
from datetime import datetime

@mcp.tool()
def rag_knowledge_store_resume(knowledge_id: str, resume_text: str, source_file_name: str = "") -> str:
    """
    MCP工具：对传入的文档文本做分片、向量化，写入rag_doc_chunk表
    knowledge_id：由Java传入，优先使用Java传过来的ID
    """
    logging.info(
        f"【rag_knowledge_store_resume入库开始】knowledge_id={knowledge_id}, text_len={len(resume_text)}, source_file_name={source_file_name}")

    # 兜底逻辑：只有Java没传的时候，Python才生成ID（正常业务不走这个分支）
    if not knowledge_id:
        knowledge_id = str(uuid.uuid4())
        logging.warning(f"⚠️ Java未传入knowledge_id，Python兜底生成：{knowledge_id}")

    if not resume_text or len(resume_text.strip()) < 5:
        logging.warning(f"【rag_knowledge_store_resume】❌简历文本过短，直接返回")
        return "❌简历文本过短"
    db = None
    cur = None
    try:
        # ==========【重点！先连接数据库，拿到游标！】==========
        db = rag_get_db_conn()
        cur = db.cursor()

        # 1. 文本分片
        chunks = text_splitter.split_text(resume_text)
        logging.info(f"分片完成，总分片数量：{len(chunks)}")

        # 2. 一次性批量向量化（失败直接终止并回滚，不再写入空向量垃圾数据）
        vectors = get_cloud_embeddings_batch(chunks)
        if len(vectors) != len(chunks):
            raise RuntimeError(f"向量数量({len(vectors)})与分片数量({len(chunks)})不一致")
        logging.info(f"批量向量化完成，向量维度：{len(vectors[0]) if vectors else 0}")

        now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        create_by_user = "mcp-service"

        # 3. 循环插入，每条chunk生成独立uuid，带上真实向量
        insert_sql = """
        INSERT INTO rag_doc_chunk
        (id, knowledge_id, chunk_index, chunk_text, source_file_name, embedding, create_by, create_time, del_flag)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0)
        """
        for idx, (chunk, vec_list) in enumerate(zip(chunks, vectors)):
            chunk_id = str(uuid.uuid4()).replace("-", "")
            cur.execute(insert_sql, (
                chunk_id,
                knowledge_id,
                idx,
                chunk,
                source_file_name,
                json.dumps(vec_list),
                create_by_user,
                now_time
            ))

        db.commit()
        logging.info(f"✅ 入库成功，knowledge_id={knowledge_id}，分片数:{len(chunks)}")
        return f"✅文档入库成功，knowledge_id:{knowledge_id}，分片{len(chunks)}条"
    except Exception as e:
        if db:
            db.rollback()
        logging.error(f"入库异常：{str(e)}")
        return f"❌入库失败：{str(e)}"
    finally:
        if cur:
            cur.close()
        if db:
            db.close()



# ========== 知识库检索工具 ==========
@mcp.tool()
def rag_knowledge_search_multi(knowledge_id_list:list[str], query_text: str, top_k:int=3) -> str:
    """批量在多个知识库检索简历分片"""
    logging.info(f"【rag_knowledge_search_multi】检索知识库列表={knowledge_id_list}, query={query_text}")
    # 空列表会拼出非法SQL "IN ()"，提前拦截
    if not knowledge_id_list:
        return "知识库列表为空，无法检索"
    db = None
    cur = None
    try:
        q_vec = get_cloud_embedding(query_text)
        db = rag_get_db_conn()
        cur = db.cursor(pymysql.cursors.DictCursor)
        placeholders = ",".join(["%s"]*len(knowledge_id_list))
        sql = f"SELECT knowledge_id,chunk_text, embedding FROM rag_doc_chunk WHERE knowledge_id IN ({placeholders}) AND del_flag=0"
        cur.execute(sql, knowledge_id_list)
        rows = cur.fetchall()
        score_list = []
        for r in rows:
            emb = json.loads(r["embedding"])
            # 跳过向量化失败产生的空向量分片，避免无意义的0分结果
            if not emb:
                continue
            sim = cosine_similarity(q_vec, emb)
            score_list.append((sim, r["knowledge_id"], r["chunk_text"]))
        score_list.sort(key=lambda x:x[0], reverse=True)
        top = score_list[:top_k]
        out = []
        for s,kid,txt in top:
            out.append(f"【知识库{kid}｜相似度{s:.3f}】{txt}")
        return "\n".join(out) if out else "没有检索到相关分片"
    except Exception as e:
        logging.exception("【多知识库检索异常】")
        return f"❌检索异常：{str(e)}"
    finally:
        if cur: cur.close()
        if db: db.close()


def _rag_retrieve(knowledge_id_list, query_text: str, top_k: int = 3,
                  min_score: float = 0.0):
    """内部检索：返回结构化结果 [{"score","knowledge_id","chunk_text"}]。
    knowledge_id_list 为空时检索全部知识库（用于问答）；非空时按库过滤。"""
    db = None
    cur = None
    try:
        q_vec = get_cloud_embedding(query_text)
        db = rag_get_db_conn()
        cur = db.cursor(pymysql.cursors.DictCursor)
        if knowledge_id_list:
            placeholders = ",".join(["%s"] * len(knowledge_id_list))
            sql = (f"SELECT knowledge_id, chunk_text, embedding FROM rag_doc_chunk "
                   f"WHERE knowledge_id IN ({placeholders}) AND del_flag=0")
            cur.execute(sql, knowledge_id_list)
        else:
            cur.execute(
                "SELECT knowledge_id, chunk_text, embedding FROM rag_doc_chunk "
                "WHERE del_flag=0")
        rows = cur.fetchall()
        scored = []
        for r in rows:
            emb = json.loads(r["embedding"]) if r["embedding"] else []
            if not emb:
                continue
            sim = cosine_similarity(q_vec, emb)
            if sim >= min_score:
                scored.append({
                    "score": sim,
                    "knowledge_id": r["knowledge_id"],
                    "chunk_text": r["chunk_text"],
                })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]
    finally:
        if cur:
            cur.close()
        if db:
            db.close()


@mcp.tool()
def rag_search_candidates(jd_text: str, top_n: int = 5) -> str:
    """
    人才库语义搜索：用 JD 在全库简历中向量召回，按简历聚合评分并排名。
    :param jd_text: 岗位描述文本
    :param top_n: 返回候选人数量
    :return: JSON字符串 {"candidates":[{"rank","knowledge_id","knowledge_name","score","match_level","matched_snippets"}]}
    综合分 = 该简历 top3 命中分片的平均相似度；同名简历去重保留最高分。
    """
    logging.info(f"【rag_search_candidates】jd={jd_text[:60]}..., top_n={top_n}")
    try:
        # 1) 全库检索，取足够多的分片用于聚合
        hits = _rag_retrieve([], jd_text, top_k=50, min_score=0.30)
        if not hits:
            return json.dumps({"candidates": []}, ensure_ascii=False)

        # 2) 按知识库（简历）聚合
        grouped = {}
        for h in hits:
            grouped.setdefault(h["knowledge_id"], []).append(h)

        # 3) 查简历名称：优先关联resume表取真名resume_name，关联不上再回退到文件名
        db = rag_get_db_conn()
        cur = db.cursor(pymysql.cursors.DictCursor)
        ids = list(grouped.keys())
        placeholders = ",".join(["%s"] * len(ids))
        cur.execute(
            f"""SELECT k.id AS kid, k.knowledge_name, r.resume_name
                FROM rag_knowledge k
                LEFT JOIN resume r
                  ON r.knowledge_id = k.id AND r.del_flag = 0
                WHERE k.id IN ({placeholders}) AND k.del_flag = 0""",
            ids)
        name_map = {}
        for r in cur.fetchall():
            # resume_name（真名/友好名）优先，空值时回退到rag_knowledge文件名
            name_map[r["kid"]] = r["resume_name"] or r["knowledge_name"]
        cur.close()
        db.close()

        # 4) 计算综合分（top3 分片平均分）+ 同名去重
        candidates = []
        for kid, chunks in grouped.items():
            chunks.sort(key=lambda x: x["score"], reverse=True)
            top3 = chunks[:3]
            score = round(sum(c["score"] for c in top3) / len(top3), 3)
            candidates.append({
                "knowledge_id": kid,
                "knowledge_name": name_map.get(kid, kid),
                "score": score,
                "matched_snippets": [
                    {"score": round(c["score"], 3), "text": c["chunk_text"][:120]}
                    for c in top3
                ],
            })
        # 同名去重：保留分数最高的一条
        best_by_name = {}
        for c in candidates:
            name = c["knowledge_name"]
            if name not in best_by_name or c["score"] > best_by_name[name]["score"]:
                best_by_name[name] = c
        candidates = sorted(best_by_name.values(), key=lambda x: x["score"], reverse=True)[:top_n]

        # 5) 排名 + 等级分档
        for i, c in enumerate(candidates):
            c["rank"] = i + 1
            if c["score"] >= 0.55:
                c["match_level"] = "强烈推荐"
            elif c["score"] >= 0.45:
                c["match_level"] = "可以考虑"
            else:
                c["match_level"] = "匹配度低"

        return json.dumps({"candidates": candidates}, ensure_ascii=False)
    except Exception as e:
        logging.exception("【rag_search_candidates执行异常】")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def rag_resume_chat(question: str, knowledge_id_list: list[str] | None = None,
                    top_k: int = 3) -> dict:
    """
    基于简历知识库的 RAG 问答（检索 + 大模型生成，完整闭环）。
    :param question: 用户问题，如"这位候选人有没有大数据相关经验？"
    :param knowledge_id_list: 限定检索的知识库ID列表；不传则检索全部简历库
    :param top_k: 检索引用的分片数量
    :return: {"answer","sources":[...],"hit":bool}
    只依据检索到的简历片段作答；简历中没有依据时明确说"未提及"，杜绝编造。
    """
    logging.info(f"【rag_resume_chat】question={question}, kb={knowledge_id_list}")

    # 1) 检索：低于阈值视为库里没有相关内容
    RELEVANCE_CUTOFF = 0.35
    hits = _rag_retrieve(knowledge_id_list or [], question, top_k=top_k)
    hits = [h for h in hits if h["score"] >= RELEVANCE_CUTOFF]

    if not hits:
        return {
            "answer": "简历库中没有检索到与该问题相关的内容，无法据此回答。",
            "sources": [],
            "hit": False,
        }

    # 2) 拼装检索上下文（带来源编号）
    context_blocks = []
    sources = []
    for i, h in enumerate(hits, 1):
        context_blocks.append(f"[片段{i}] {h['chunk_text']}")
        sources.append({
            "index": i,
            "knowledge_id": h["knowledge_id"],
            "score": round(h["score"], 3),
            "snippet": (h["chunk_text"] or "")[:80],
            "content": h["chunk_text"] or "",
        })
    context = "\n\n".join(context_blocks)

    # 3) 增强生成：强约束“只用片段、无依据就说不知道”
    prompt = f"""请严格依据下面提供的简历片段回答用户问题。

【回答要求】
1. 只能使用【简历片段】中出现的信息，禁止使用片段之外的常识或猜测；
2. 如果片段中没有与问题相关的依据，必须直接回答"简历中未提及该信息"，不得编造；
3. 回答简洁明确，关键结论后用[片段x]标注信息来源；
4. 使用中文回答。

【简历片段】
{context}

【用户问题】
{question}"""

    answer = ai_call(
        prompt,
        system_prompt="你是严谨的简历问答助手。只依据给定简历片段作答，"
                      "片段里没有的信息一律回答“简历中未提及该信息”，绝不编造。",
    )
    return {"answer": answer, "sources": sources, "hit": True}


# ========== read_resume【自动生成ID版本】 ==========
@mcp.tool()
def read_resume(path: str, knowledge_id: str | None = None) -> str:
    """
    读取简历文件
    :param path: 文件路径
    :param knowledge_id: 知识库ID。
    👉 如果传入knowledge_id：读完简历自动执行分片存入rag_doc_chunk表；
    👉 如果不传knowledge_id：Python自动生成全新UUID作为knowledge_id，执行入库。
    ⚠️【重要】每个新简历必须使用全新knowledge_id，重复相同id会追加到同一个知识库！禁止使用resume_001！
    """
    # 如果为空，自动生成知识库ID
    if not knowledge_id:
        knowledge_id = str(uuid.uuid4())
        logging.info(f"【read_resume】未传入knowledge_id，Python自动生成id={knowledge_id}")

    # 新增拦截：禁止resume_001
    if knowledge_id.strip() == "resume_001":
        logging.error("❌拦截！禁止使用resume_001作为知识库ID")
        return "错误：resume_001为保留ID，禁止使用，请传入全新的32位UUID"

    logging.info(f"【read_resume工具被调用】 path={path}, knowledge_id={knowledge_id}")

    text = read_local_resume(path)
    logging.info(f"【read_resume读取文件完成】读取文本长度={len(text)}")

    # 现在knowledge_id一定有值，执行入库
    if len(text.strip()) > 10:
        logging.info(f"【read_resume】检测到knowledge_id不为空，准备执行分片入库！knowledge_id={knowledge_id}")
        # 先写rag_knowledge主表（已存在则跳过），避免产生孤儿分片
        kb_result = _rag_create_knowledge_internal(
            knowledge_id,
            knowledge_name=os.path.basename(path) or "未命名简历",
            description="由read_resume自动创建"
        )
        logging.info(f"【read_resume】主表写入结果: {kb_result}")
        logging.info(f"【read_resume】文本长度满足条件，调用入库函数")
        store_result = rag_knowledge_store_resume(knowledge_id, text, source_file_name=os.path.basename(path))
        logging.info(f"【read_resume】入库函数返回结果 >>> {store_result}")
    else:
        logging.warning(f"【read_resume】文本太短，跳过入库，text长度:{len(text.strip())}")

    return text




@mcp.tool()
def run_radar(resume_text:str)->dict:
    logging.info("【MCP调用】run_radar 生成雷达图")
    res = radar_app.invoke({"resume_text": resume_text})
    return res["radar_result"]

@mcp.tool()
def run_match(resume_text:str, jd:str) -> dict:
    logging.info("【MCP调用】run_match 简历JD匹配")
    ret = match_app.invoke({"resume_text":resume_text, "jd":jd})
    return ret["final"]

@mcp.tool()
def run_agent_chat(input_text:str) -> str:
    logging.info(f"【MCP调用】run_agent_chat input={input_text[:80]}")
    try:
        resp = zhipu_client.chat.completions.create(
            model=ZHIPU_MODEL,
            messages=[{"role":"user","content":input_text}],
            temperature=0.3,
            timeout=120
        )
        return resp.choices[0].message.content
    except Exception as e:
        logging.exception("【run_agent_chat执行异常】")
        return f"❌Agent执行异常：{str(e)}"

@mcp.tool()
def gen_interview_question(resume_text: str) -> str:
    logging.info("【MCP调用】gen_interview_question")
    return gen_question_text.invoke({"text": resume_text})

@mcp.tool()
def resume_optimize(resume_text: str) -> str:
    logging.info("【MCP调用】resume_optimize")
    return optimize_text.invoke({"text": resume_text})

@mcp.tool()
def resume_risk_check(resume_text: str) -> str:
    logging.info("【MCP调用】resume_risk_check")
    return risk_check_text.invoke({"text": resume_text})

@mcp.tool()
def rag_search_resume(query_text:str, top_k:int=4) -> str:
    db=None
    cur=None
    try:
        qv = get_cloud_embedding(query_text)
        db = rag_get_db_conn()
        cur = db.cursor(pymysql.cursors.DictCursor)
        cur.execute("SELECT content,vector FROM resume_vector_chunk")
        rows = cur.fetchall()
        items = []
        for r in rows:
            sim = cosine_similarity(qv, json.loads(r["vector"]))
            items.append((sim, r["content"]))
        items.sort(reverse=True, key=lambda x:x[0])
        out = "\n".join([f"【相似度{s:.3f}】{c}" for s,c in items[:top_k]])
        return out if out else "无结果"
    except Exception as e:
        logging.exception("rag_search_resume异常")
        return f"❌{str(e)}"
    finally:
        if cur: cur.close()
        if db: db.close()

@mcp.tool()
def compare_multi_resume(resume_texts: str, names:str) -> str:
    logging.info("【MCP调用】compare_multi_resume 多简历对比")
    prompt = f"""对比多份简历：
简历列表：{resume_texts}
简历名字：{names}
输出对比分析，优势劣势，录用优先级。
"""
    return ai_call(prompt)

# ========== 程序入口 ==========
if __name__ == "__main__":
    sys.stderr.write("\n" + "="*60 + "\n")
    sys.stderr.write(f"✅ MCP SSE服务启动 http://{HOST}:{PORT_MCP_ALL}/sse\n")
    sys.stderr.write("⚠️  read_resume传入knowledge_id参数才会自动分片入库rag_doc_chunk\n")
    sys.stderr.write("="*60 + "\n\n")
    mcp.run(transport="sse")