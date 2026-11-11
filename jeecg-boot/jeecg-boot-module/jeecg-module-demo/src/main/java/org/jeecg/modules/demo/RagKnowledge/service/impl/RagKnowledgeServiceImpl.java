package org.jeecg.modules.demo.RagKnowledge.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import lombok.extern.slf4j.Slf4j;
import org.jeecg.common.api.vo.Result;
import org.jeecg.modules.demo.RagDocChunk.client.RagSseClient;
import org.jeecg.modules.demo.RagKnowledge.entity.RagKnowledge;
import org.jeecg.modules.demo.RagKnowledge.mapper.RagKnowledgeMapper;
import org.jeecg.modules.demo.RagKnowledge.service.IRagKnowledgeService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.File;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

@Slf4j
@Service
public class RagKnowledgeServiceImpl extends ServiceImpl<RagKnowledgeMapper, RagKnowledge> implements IRagKnowledgeService {

    @Autowired
    private RagSseClient mcpClient;

    private static final String RESUME_STORE_DIR = "C:\\Users\\简历测试数据\\存储\\";

    /**
     * 上传简历完整流程：保存文件 → MCP创建知识库主表 → MCP解析分片入库
     */
    @Override
    public Result<?> uploadResume(MultipartFile file) throws Exception {
        // 1. 生成32位无横线UUID作为 knowledge_id
        String knowledgeId = UUID.randomUUID().toString().replace("-", "");
        log.info("✅本次简历生成knowledge_id：{}", knowledgeId);

        // 2. 保存上传文件到本地
        String savePath = RESUME_STORE_DIR + knowledgeId + ".pdf";
        File saveFile = new File(savePath);
        file.transferTo(saveFile);
        log.info("✅简历文件已保存到：{}", savePath);

        // 3. 调MCP创建知识库主表记录（rag_knowledge）
        Map<String, Object> createParams = new HashMap<>();
        createParams.put("knowledge_id", knowledgeId);
        createParams.put("knowledge_name", file.getOriginalFilename());
        createParams.put("description", "简历文档");
        String createResult = mcpClient.callTool("rag_create_knowledge", createParams);
        log.info("创建知识库主表返回结果：{}", createResult);

        // 4. 调MCP解析简历、分片、写入 rag_doc_chunk
        Map<String, Object> readParams = new HashMap<>();
        readParams.put("path", savePath);
        readParams.put("knowledge_id", knowledgeId);
        String mcpResult = mcpClient.callTool("read_resume", readParams);
        log.info("简历解析分片返回：{}", mcpResult);

        return Result.OK("简历上传&入库成功，知识库ID：" + knowledgeId, mcpResult);
    }

}
