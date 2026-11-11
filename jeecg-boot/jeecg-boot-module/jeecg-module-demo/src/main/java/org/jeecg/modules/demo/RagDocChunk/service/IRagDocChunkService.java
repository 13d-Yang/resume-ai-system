package org.jeecg.modules.demo.RagDocChunk.service;

import com.baomidou.mybatisplus.extension.service.IService;
import org.jeecg.common.api.vo.Result;
import org.jeecg.modules.demo.RagDocChunk.entity.RagDocChunk;

/**
 * @Description: 分片表
 */
public interface IRagDocChunkService extends IService<RagDocChunk> {

    Result<?> queryRag(String knowledgeId, String question);

    //新增原生插入方法声明
    void insertDirect(RagDocChunk chunk);

}
