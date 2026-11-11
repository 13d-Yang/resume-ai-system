package org.jeecg.modules.demo.RagDocChunk.mapper;


import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.jeecg.modules.demo.RagDocChunk.entity.RagDocChunk;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import java.util.List;


@Mapper
public interface RagDocChunkMapper extends BaseMapper<RagDocChunk> {

    /**
     * 根据知识库id查询有效分片
     */
    @Select("select * from rag_doc_chunk where knowledge_id=#{knowledgeId} and del_flag=0")
    List<RagDocChunk> selectChunkByKbId(@Param("knowledgeId") String knowledgeId);

    /**
     * 原生手写Insert，绕开mybatis‑plus save异常，不操作embedding字段
     */
    @Insert("INSERT INTO rag_doc_chunk(id,knowledge_id,source_file_name,chunk_text,chunk_index,create_by,create_time,del_flag) " +
            "VALUES(#{e.id},#{e.knowledgeId},#{e.sourceFileName},#{e.chunkText},#{e.chunkIndex},#{e.createBy},#{e.createTime},#{e.delFlag})")
    int insertDirect(@Param("e") RagDocChunk e);
}
