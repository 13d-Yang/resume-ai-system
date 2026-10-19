# -*- coding: utf-8 -*-
"""简历与知识库关联补全服务（历史数据修复）。

按 resume.resume_file = rag_knowledge.knowledge_name 关联，
把 rag_knowledge.id 回写到 resume.knowledge_id。
该能力作为 service 方法存在，由 scripts/ 下的运维脚本薄封装调用，
不再以"一次性临时脚本"的形式散落在工程根目录。
"""
import logging

from app.repositories import knowledge_repository, resume_repository


def plan_links() -> dict:
    """生成关联计划（只读，不改库）。

    :return: {
        "resumes": 缺knowledge_id的简历列表,
        "knowledges": 知识库列表,
        "matched": [{"resume": row, "knowledge": row}, ...],
        "unmatched": [resume_row, ...],
    }
    """
    resumes = resume_repository.find_missing_knowledge_id()
    knowledges = knowledge_repository.list_all_knowledge()

    matched = []
    unmatched = []
    for resume in resumes:
        hit = next(
            (k for k in knowledges if resume["resume_file"] == k["knowledge_name"]),
            None,
        )
        if hit:
            matched.append({"resume": resume, "knowledge": hit})
        else:
            unmatched.append(resume)

    return {
        "resumes": resumes,
        "knowledges": knowledges,
        "matched": matched,
        "unmatched": unmatched,
    }


def apply_links(plan: dict) -> int:
    """按关联计划执行回写（单事务，失败整体回滚）。"""
    pairs = [
        (item["knowledge"]["id"], item["resume"]["id"])
        for item in plan["matched"]
    ]
    if not pairs:
        return 0
    try:
        count = resume_repository.bulk_update_knowledge_id(pairs)
        logging.info("【关联补全】共回写 %s 条 resume.knowledge_id", count)
        return count
    except Exception as e:
        logging.error("【关联补全】失败已回滚：%s", e)
        raise
