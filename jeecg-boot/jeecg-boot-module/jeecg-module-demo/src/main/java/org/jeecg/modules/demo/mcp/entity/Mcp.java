package org.jeecg.modules.demo.mcp.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
import java.util.Date;
import java.io.Serializable;

@Data
@TableName("mcp")
public class Mcp implements Serializable {
    private static final long serialVersionUID = 1L;

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;
    private String icon;
    private String name;
    private String descr;
    private String category;
    private String type;
    private String endpoint;
    private String header;
    private String tools;
    private String status;
    private Integer synced;
    private String metadata;
    private String createBy;
    private Date createTime;
    private String updateBy;
    private Date updateTime;
    private String sysOrgCode;
    private String tenantId;
}