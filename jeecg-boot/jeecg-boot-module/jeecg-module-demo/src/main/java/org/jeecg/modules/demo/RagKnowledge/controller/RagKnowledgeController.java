package org.jeecg.modules.demo.RagKnowledge.controller;

import org.jeecg.common.api.vo.Result;
import org.jeecg.modules.demo.RagKnowledge.service.IRagKnowledgeService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

/**
 * RAG知识库主表 - 前端HTTP入口
 */
@RestController
@RequestMapping("/ragKnowledge")
public class RagKnowledgeController {

    @Autowired
    private IRagKnowledgeService ragKnowledgeService;

    /**
     * 简历上传接口
     */
    @PostMapping("/uploadResume")
    public Result<?> uploadResume(@RequestParam("file") MultipartFile file) {
        try {
            return ragKnowledgeService.uploadResume(file);
        } catch (Exception e) {
            e.printStackTrace();
            return Result.error("处理失败：" + e.getMessage());
        }
    }
}
