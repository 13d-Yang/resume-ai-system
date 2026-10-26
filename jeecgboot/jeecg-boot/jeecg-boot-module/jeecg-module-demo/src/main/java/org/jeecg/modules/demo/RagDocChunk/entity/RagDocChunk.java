package org.jeecg.modules.demo.RagDocChunk.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.annotation.TableField;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("rag_doc_chunk")
public class RagDocChunk {

    @TableId(type = IdType.ASSIGN_ID)
    private String id;

    @TableField("knowledge_id")
    private String knowledgeId;

    @TableField("source_file_name")
    private String sourceFileName;

    @TableField("chunk_text")
    private String chunkText;

    @TableField("chunk_index")
    private Integer chunkIndex;

    @TableField("embedding")
    private String embedding;

    @TableField("create_by")
    private String createBy;

    @TableField("create_time")
    private LocalDateTime createTime;

    @TableField("del_flag")
    private Integer delFlag;
}