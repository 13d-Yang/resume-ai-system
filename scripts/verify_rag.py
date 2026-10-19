# -*- coding: utf-8 -*-
"""
RAG 简历分片 / 语义检索 验证脚本（只读，不写库、不入库）

用法（项目根目录执行）：
    .\\venv310\\Scripts\\python.exe scripts\\verify_rag.py
    .\\venv310\\Scripts\\python.exe scripts\\verify_rag.py <knowledge_id>
    .\\venv310\\Scripts\\python.exe scripts\\verify_rag.py <id1> <id2>

验证三件事：
  探针A：分片是否切对（数量、向量维度=1024、无空向量）
  探针B：语义检索是否真的懂"意思相近"——同义改写也该命中，负样本分数应明显更低
  探针C：知识库隔离——只查某个 knowledge_id 时，返回分片不得串到别的库
"""
import argparse
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from app.config import EMBED_MODEL  # noqa: E402
from app.repositories import chunk_repository  # noqa: E402
from app.services.embedding_service import (  # noqa: E402
    cosine_similarity,
    get_cloud_embedding,
)

DEFAULT_IDS = [
    "7345497a-c775-43e9-8434-f39073add090",
    "b32ce579-4097-4286-b3ec-1b13c4655edb",
]
EXPECTED_DIM = 1024

BASELINE_QUERIES = ["Python 开发经验", "RAG 向量检索"]
PARAPHRASE_QUERIES = [
    "这个人能不能做服务端程序设计和接口开发",
    "会不会做数据清洗和报表可视化",
    "有没有人力资源信息化系统的实施经历",
]
NEGATIVE_QUERIES = [
    "红烧肉的家常做法",
    "挖掘机液压系统维修手册",
    "小学生二年级乘法口诀",
]

POS_MIN = 0.40
MARGIN = 0.12


def fetch_chunks(knowledge_id: str):
    """只读查询某知识库的全部分片"""
    return chunk_repository.fetch_chunks_by_knowledge_id(knowledge_id)


def search(rows, query: str, top_k: int = 3):
    """对给定分片做一次向量检索，返回 [(score, chunk_text), ...]"""
    q_vec = get_cloud_embedding(query)
    scored = []
    for r in rows:
        emb = json.loads(r["embedding"]) if r["embedding"] else []
        if not emb:
            continue
        scored.append((cosine_similarity(q_vec, emb), r["chunk_text"]))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]


def probe_a(rows):
    print("\n" + "=" * 64)
    print("探针 A：分片入库检查（切分粒度 / 向量维度 / 空向量）")
    print("=" * 64)
    ok = True
    n = len(rows)
    print(f"分片总数：{n}（该简历约 3000 字，400 字/片，预期 8~9 片）")
    if n == 0:
        print("❌ FAIL：该知识库没有任何分片，无法继续后续验证")
        return False
    if not (5 <= n <= 15):
        print(f"⚠️  WARN：分片数 {n} 偏离预期区间 5~15，检查分片大小是否改动过")
    else:
        print("✅ 分片数量在合理区间")

    dims, empty, lens = set(), 0, []
    for r in rows:
        emb = json.loads(r["embedding"]) if r["embedding"] else []
        if not emb:
            empty += 1
        else:
            dims.add(len(emb))
        lens.append(len(r["chunk_text"] or ""))
    print(f"向量维度：{sorted(dims)}（预期 {{{EXPECTED_DIM}}}，模型 {EMBED_MODEL}）")
    print(f"空向量分片：{empty} 个")
    print(f"分片字数：最短 {min(lens)} / 最长 {max(lens)} / 平均 {sum(lens)//len(lens)}")

    if dims == {EXPECTED_DIM}:
        print("✅ 所有分片向量维度正确")
    else:
        print("❌ FAIL：存在非 1024 维向量")
        ok = False
    if empty == 0:
        print("✅ 没有空向量分片")
    else:
        print(f"❌ FAIL：{empty} 个空向量（向量化失败未回滚）")
        ok = False
    return ok


def probe_b(rows):
    print("\n" + "=" * 64)
    print("探针 B：语义检索检查（字面不同 ≠ 找不到，这是向量检索的核心证据）")
    print("=" * 64)

    def run_group(name, queries):
        print(f"\n—— {name} ——")
        group_best = -1.0
        for q in queries:
            s, txt = search(rows, q, top_k=1)[0]
            group_best = max(group_best, s)
            preview = (txt or "").replace("\n", " ")[:46]
            print(f"  查询：{q}")
            print(f"    top1 相似度={s:.3f}｜命中片段：{preview}…")
        return group_best

    base = run_group("B1 原词基线（本该命中）", BASELINE_QUERIES)
    para = run_group("B2 同义改写（简历里没有这些词，仍应命中）", PARAPHRASE_QUERIES)
    neg = run_group("B3 负样本（无关问题，应明显更低）", NEGATIVE_QUERIES)

    print("\n—— 判定 ——")
    ok = True
    pos_best = max(base, para)
    print(f"正样本最高分：{pos_best:.3f}（阈值 {POS_MIN}）")
    print(f"负样本最高分：{neg:.3f}")
    print(f"语义区分间隔：{pos_best - neg:.3f}（要求 ≥ {MARGIN}）")
    if base >= POS_MIN:
        print("✅ B1 原词查询稳定命中")
    else:
        print("❌ B1 FAIL：原词都没命中，检查 embedding/检索链路")
        ok = False
    if para >= POS_MIN:
        print("✅ B2 同义改写也能命中 → 检索靠的是【语义】而非字面匹配")
    else:
        print("⚠️  B2 WARN：同义改写分数偏低，可观察命中片段是否仍相关")
    if pos_best - neg >= MARGIN:
        print("✅ B3 无关问题被有效拉开 → 系统不是无脑返回")
    else:
        print("❌ B3 FAIL：正负样本拉不开差距，检索区分度不足")
        ok = False
    return ok


def probe_c(all_chunks: dict):
    print("\n" + "=" * 64)
    print("探针 C：知识库隔离检查（只查 A 库，不得返回 B 库分片）")
    print("=" * 64)
    ok = True
    for kid, rows in all_chunks.items():
        if not rows:
            print(f"⚠️  知识库 {kid} 无分片，跳过")
            continue
        top = search(rows, "Python 开发经验", top_k=3)
        leaked = [t for _, t in top if t not in {r["chunk_text"] for r in rows}]
        if not leaked:
            print(f"✅ {kid[:8]}… ：top3 全部来自本库，无串库")
        else:
            print(f"❌ {kid[:8]}… ：发现 {len(leaked)} 条其他库分片")
            ok = False
    return ok


def main():
    parser = argparse.ArgumentParser(description="RAG 简历分片验证（只读）")
    parser.add_argument("ids", nargs="*", help="knowledge_id，可传多个；不传用脚本内默认值")
    args = parser.parse_args()
    ids = args.ids or DEFAULT_IDS

    print(f"向量模型：{EMBED_MODEL}")
    print(f"待验证知识库：{ids}")

    all_chunks = {}
    for kid in ids:
        rows = fetch_chunks(kid)
        all_chunks[kid] = rows
        print(f"  {kid} → {len(rows)} 个分片")

    if not any(all_chunks.values()):
        print("\n❌ 所有知识库都没有分片，请先通过 read_resume 入库后再验证")
        sys.exit(1)

    first_kid = next(k for k, v in all_chunks.items() if v)
    results = {
        "A 分片质量": probe_a(all_chunks[first_kid]),
        "B 语义检索": probe_b(all_chunks[first_kid]),
        "C 库间隔离": probe_c(all_chunks),
    }

    print("\n" + "=" * 64)
    print("验证总结")
    print("=" * 64)
    for name, passed in results.items():
        print(f"  {'✅ PASS' if passed else '❌ FAIL'}  {name}")
    print("=" * 64)
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
