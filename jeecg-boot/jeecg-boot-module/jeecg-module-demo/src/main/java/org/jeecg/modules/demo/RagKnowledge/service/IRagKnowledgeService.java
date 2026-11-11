package org.jeecg.modules.demo.RagKnowledge.service;

import com.baomidou.mybatisplus.extension.service.IService;
import org.jeecg.common.api.vo.Result;
import org.jeecg.modules.demo.RagKnowledge.entity.RagKnowledge;
import org.springframework.web.multipart.MultipartFile;

/**
 * @Description: RAG知识库主表
 */
public interface IRagKnowledgeService extends IService<RagKnowledge> {

    /**
     * 上传简历：保存文件到本地 → 调MCP创建知识库主表 → 调MCP解析分片
     * @return 成功返回 knowledgeId，失败抛异常
     */
    Result<?> uploadResume(MultipartFile file) throws Exception;

}
