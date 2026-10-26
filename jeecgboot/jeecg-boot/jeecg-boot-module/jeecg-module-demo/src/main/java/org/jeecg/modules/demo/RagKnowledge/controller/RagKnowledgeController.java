package org.jeecg.modules.demo.RagKnowledge.controller;
import org.jeecg.common.api.vo.Result;
import org.jeecg.modules.demo.RagDocChunk.controller.RagDocChunk;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;
import java.io.File;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import lombok.extern.slf4j.Slf4j;

@Slf4j
@RestController
@RequestMapping("/ragKnowledge")
public class RagKnowledgeController {
    @Autowired
    private RagDocChunk mcpClient; //SSE MCP客户端

    /**
     * 简历上传接口：生成新UUID，调用MCP
     */
    @PostMapping("/uploadResume")
    public Result<?> uploadResume(@RequestParam("file") MultipartFile file) {
        try {
            //1. 生成32位无横线UUID，作为knowledge_id
            String knowledgeId = UUID.randomUUID().toString().replace("-", "");
            log.info("✅本次简历生成knowledge_id：{}", knowledgeId);

            //2. 保存上传文件到本地
            String savePath = "C:\\Users\\简历测试数据\\存储\\" + knowledgeId + ".pdf";
            File saveFile = new File(savePath);
            file.transferTo(saveFile);

            //====================【新增代码开始】====================
            //第一步：调用MCP创建知识库主表记录 rag_knowledge
            Map<String, Object> createParams = new HashMap<>();
            createParams.put("knowledge_id", knowledgeId);
            createParams.put("knowledge_name", file.getOriginalFilename());
            createParams.put("description", "简历文档");
            String createResult = mcpClient.callTool("rag_create_knowledge", createParams);
            log.info("创建知识库主表返回结果：{}", createResult);
            //====================【新增代码结束】====================

            //3. 【原有代码完全不变】调用read_resume做解析、分片、写入rag_doc_chunk
            Map<String, Object> params = new HashMap<>();
            params.put("path", savePath);
            params.put("knowledge_id", knowledgeId);
            log.info("【Controller组装完成params】:{}", params);
            String mcpResult = mcpClient.callTool("read_resume", params);

            return Result.OK("简历上传&入库成功，知识库ID："+knowledgeId, mcpResult);
        } catch (Exception e) {
            e.printStackTrace();
            return Result.error("处理失败：" + e.getMessage());
        }
    }
}
