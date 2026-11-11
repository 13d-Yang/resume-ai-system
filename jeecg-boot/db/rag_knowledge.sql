-- RAG知识库主表
-- 对应实体: org/jeecg/modules/demo/RagKnowledge/entity/RagKnowledge.java
-- 说明: Controller 中生成的 32 位无横线 UUID (knowledge_id) 即本表主键 id,
--       rag_doc_chunk.knowledge_id 通过该 id 关联本表
--       del_flag 取值: 0-正常, 1-已删除
CREATE TABLE IF NOT EXISTS `rag_knowledge` (
  `id` varchar(32) NOT NULL COMMENT '主键ID(32位无横线UUID,即knowledge_id)',
  `knowledge_name` varchar(200) NOT NULL COMMENT '知识库名称(简历文件名)',
  `description` varchar(500) DEFAULT NULL COMMENT '描述',
  `create_by` varchar(32) DEFAULT NULL COMMENT '创建人',
  `create_time` datetime DEFAULT NULL COMMENT '创建时间',
  `update_by` varchar(32) DEFAULT NULL COMMENT '更新人',
  `update_time` datetime DEFAULT NULL COMMENT '更新时间',
  `del_flag` int DEFAULT 0 COMMENT '删除标记 0正常 1删除',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='RAG-自定义知识库';
