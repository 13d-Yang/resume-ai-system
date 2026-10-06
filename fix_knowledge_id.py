# -*- coding: utf-8 -*-
"""
历史数据补全脚本：把 resume 表和 rag_knowledge 表按文件名关联，回写 knowledge_id

用法：
    # 1. 先干跑（DRY RUN），只打印匹配计划，不改数据库
    .\\venv310\\Scripts\\python.exe fix_knowledge_id.py

    # 2. 确认无误后，真正执行 UPDATE
    .\\venv310\\Scripts\\python.exe fix_knowledge_id.py --execute
"""
import sys
import argparse

import pymysql

# Windows 控制台中文输出
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from config import MYSQL_CONFIG


def get_conn():
    return pymysql.connect(**MYSQL_CONFIG)


def dry_run():
    """只查询，不修改，打印匹配计划"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # 查 resume 表：缺 knowledge_id 的有效记录
            cur.execute("""
                SELECT id, resume_name, resume_file, resume_path, knowledge_id
                FROM resume
                WHERE del_flag = 0 AND (knowledge_id IS NULL OR knowledge_id = '')
                ORDER BY id
            """)
            resumes = cur.fetchall()

            # 查 rag_knowledge 表：所有知识库
            cur.execute("SELECT id, knowledge_name, description FROM rag_knowledge")
            knowledges = cur.fetchall()

        print("=" * 80)
        print("【DRY RUN】历史数据补全预览")
        print("=" * 80)

        print(f"\n[1] resume 表中缺 knowledge_id 的记录数：{len(resumes)}")
        for r in resumes:
            print(f"    id={r['id']}, resume_name={r['resume_name']}, "
                  f"resume_file={r['resume_file']}")

        print(f"\n[2] rag_knowledge 表现有知识库数：{len(knowledges)}")
        for k in knowledges:
            print(f"    id={k['id']}, knowledge_name={k['knowledge_name']}")

        print("\n[3] 匹配计划（按 resume_file = knowledge_name 关联）：")
        matched = []
        unmatched = []
        for r in resumes:
            hit = None
            for k in knowledges:
                if r["resume_file"] == k["knowledge_name"]:
                    hit = k
                    break
            if hit:
                matched.append((r, hit))
                print(f"    ✅ resume.id={r['id']} ({r['resume_file']})"
                      f"  -->  knowledge_id={hit['id']}")
            else:
                unmatched.append(r)
                print(f"    ❌ resume.id={r['id']} ({r['resume_file']})"
                      f"  -->  rag_knowledge 中无同名记录，无法自动关联")

        print("\n" + "=" * 80)
        print(f"统计：可自动关联 {len(matched)} 条，无法关联 {len(unmatched)} 条")
        if unmatched:
            print("\n无法关联的简历，说明它们从未入库到 RAG，需要重新上传或手动入库：")
            for r in unmatched:
                print(f"    - id={r['id']}, file={r['resume_file']}")
        print("=" * 80)

        return matched
    finally:
        conn.close()


def execute(matched):
    """真正执行 UPDATE"""
    if not matched:
        print("\n没有可更新的记录，退出。")
        return

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for r, k in matched:
                sql = "UPDATE resume SET knowledge_id = %s WHERE id = %s"
                cur.execute(sql, (k["id"], r["id"]))
                print(f"已更新 resume.id={r['id']}  knowledge_id={k['id']}")
        conn.commit()
        print(f"\n✅ 共更新 {len(matched)} 条记录，事务已提交。")
    except Exception as e:
        conn.rollback()
        print(f"\n❌ 更新失败，已回滚：{e}")
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true",
                        help="真正执行UPDATE，不加此参数则为DRY RUN")
    args = parser.parse_args()

    matched = dry_run()

    if args.execute:
        print("\n【开始执行 UPDATE】")
        execute(matched)
    else:
        print("\n当前为 DRY RUN，未修改数据库。")
        print("确认匹配无误后，加 --execute 参数重新运行：")
        print("    .\\venv310\\Scripts\\python.exe fix_knowledge_id.py --execute")


if __name__ == "__main__":
    main()
