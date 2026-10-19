# -*- coding: utf-8 -*-
"""
历史数据补全脚本（运维脚本，业务逻辑在 app.services.resume_link_service）：
把 resume 表和 rag_knowledge 表按文件名关联，回写 knowledge_id。

用法（项目根目录执行）：
    # 1. 先干跑（DRY RUN），只打印匹配计划，不改数据库
    .\\venv310\\Scripts\\python.exe scripts\\fix_knowledge_id.py

    # 2. 确认无误后，真正执行 UPDATE
    .\\venv310\\Scripts\\python.exe scripts\\fix_knowledge_id.py --execute
"""
import argparse
import os
import sys

# Windows 控制台中文输出
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 把项目根目录加入 sys.path，使脚本可独立运行
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from app.services import resume_link_service  # noqa: E402


def print_plan(plan: dict) -> None:
    print("=" * 80)
    print("【DRY RUN】历史数据补全预览")
    print("=" * 80)

    print(f"\n[1] resume 表中缺 knowledge_id 的记录数：{len(plan['resumes'])}")
    for r in plan["resumes"]:
        print(f"    id={r['id']}, resume_name={r['resume_name']}, "
              f"resume_file={r['resume_file']}")

    print(f"\n[2] rag_knowledge 表现有知识库数：{len(plan['knowledges'])}")
    for k in plan["knowledges"]:
        print(f"    id={k['id']}, knowledge_name={k['knowledge_name']}")

    print("\n[3] 匹配计划（按 resume_file = knowledge_name 关联）：")
    for item in plan["matched"]:
        r, k = item["resume"], item["knowledge"]
        print(f"    ✅ resume.id={r['id']} ({r['resume_file']})"
              f"  -->  knowledge_id={k['id']}")
    for r in plan["unmatched"]:
        print(f"    ❌ resume.id={r['id']} ({r['resume_file']})"
              f"  -->  rag_knowledge 中无同名记录，无法自动关联")

    print("\n" + "=" * 80)
    print(f"统计：可自动关联 {len(plan['matched'])} 条，"
          f"无法关联 {len(plan['unmatched'])} 条")
    if plan["unmatched"]:
        print("\n无法关联的简历，说明它们从未入库到 RAG，需要重新上传或手动入库：")
        for r in plan["unmatched"]:
            print(f"    - id={r['id']}, file={r['resume_file']}")
    print("=" * 80)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true",
                        help="真正执行UPDATE，不加此参数则为DRY RUN")
    args = parser.parse_args()

    plan = resume_link_service.plan_links()
    print_plan(plan)

    if args.execute:
        print("\n【开始执行 UPDATE】")
        count = resume_link_service.apply_links(plan)
        print(f"\n✅ 共更新 {count} 条记录，事务已提交。")
    else:
        print("\n当前为 DRY RUN，未修改数据库。")
        print("确认匹配无误后，加 --execute 参数重新运行：")
        print(r"    .\venv310\Scripts\python.exe scripts\fix_knowledge_id.py --execute")


if __name__ == "__main__":
    main()
