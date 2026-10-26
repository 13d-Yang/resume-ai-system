package org.jeecg.modules.demo.resume.service;

import lombok.extern.slf4j.Slf4j;
import org.jeecg.modules.demo.RagDocChunk.controller.RagDocChunk;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

@Slf4j
@Component
public class RagClientUtil {

    @Autowired
    private RagDocChunk mcpClient; // SSE MCP客户端

    /**
     * 上传简历后同步向量入库
     * @param resumeId 简历主键ID
     * @param realFilePath 简历本地物理存储路径
     * @param originalFileName 原始文件名（用于知识库名称）
     * @return knowledgeId 入库成功返回，失败返回 null
     */
    public String syncResumeToRag(Long resumeId, String realFilePath, String originalFileName){
        String knowledgeId = null;
        try {
            // 1. 生成32位无横线UUID作为 knowledge_id
            knowledgeId = UUID.randomUUID().toString().replace("-", "");
            log.info("【RAG同步开始】简历ID:{} knowledge_id:{}", resumeId, knowledgeId);

            // 2. 调用 MCP 创建知识库主表记录
            Map<String, Object> createParams = new HashMap<>();
            createParams.put("knowledge_id", knowledgeId);
            createParams.put("knowledge_name", originalFileName != null ? originalFileName : "未知简历");
            createParams.put("description", "简历文档");
            String createResult = mcpClient.callTool("rag_create_knowledge", createParams);
            log.info("【RAG创建知识库主表返回】简历ID:{} 结果:{}", resumeId, createResult);

            // 3. 调用 MCP read_resume 完成解析、分片、写入 rag_doc_chunk
            Map<String, Object> readParams = new HashMap<>();
            readParams.put("path", realFilePath);
            readParams.put("knowledge_id", knowledgeId);
            String readResult = mcpClient.callTool("read_resume", readParams);
            log.info("【RAG同步成功】简历ID:{} knowledge_id:{} 结果:{}", resumeId, knowledgeId, readResult);
            return knowledgeId;
        } catch (Exception e) {
            log.error("【RAG同步失败】简历ID:{} knowledge_id:{} 异常:", resumeId, knowledgeId, e);
            return null;
        }
    }
}