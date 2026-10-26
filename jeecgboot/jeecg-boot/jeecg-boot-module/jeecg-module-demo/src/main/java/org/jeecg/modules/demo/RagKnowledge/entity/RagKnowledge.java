package org.jeecg.modules.demo.RagKnowledge.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.annotation.TableField;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("rag_knowledge")
public class RagKnowledge {

    @TableId(type = IdType.ASSIGN_ID)
    private String id;

    @TableField("knowledge_name")
    private String knowledgeName;

    @TableField("description")
    private String description;

    @TableField("create_by")
    private String createBy;

    @TableField("create_time")
    private LocalDateTime createTime;

    @TableField("update_by")
    private String updateBy;

    @TableField("update_time")
    private LocalDateTime updateTime;

    @TableField("del_flag")
    private Integer delFlag;
}