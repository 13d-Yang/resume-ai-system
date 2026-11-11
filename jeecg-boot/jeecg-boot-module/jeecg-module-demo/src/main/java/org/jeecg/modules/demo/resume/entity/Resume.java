package org.jeecg.modules.demo.resume.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.annotation.TableField;  // 新增导入
import lombok.Data;
import org.jeecg.common.aspect.annotation.Dict;
import org.jeecgframework.poi.excel.annotation.Excel;  // 新增导入（可选，用于Excel导出）

import java.util.Date;

@Data
@TableName("resume")
public class Resume {
    @TableId(type = IdType.AUTO)
    private Long id;
    private String empNo;          // 员工号
    private String resumeName;     // 姓名
    private String gender;         // 性别
    private Integer age;           // 年龄
    private String education;      // 学历
    private String school;         // 学校
    private String major;          // 专业
    private String workExp;        // 工作经历a
    private String projectExp;     // 项目经历
    private String skill;          // 技能
    private String resumeFile;     // 文件名
    private String resumePath;     // 文件路径
    private Integer aiScore;       // AI评分
    private Date createTime;       // 创建时间
    private Date updateTime;       // 更新时间
    private Integer delFlag;       // 删除标记
    @Dict(dicCode = "resume_status") // 保留原有字典注解，用于前端自动翻译
    private Integer status;        // 状态：1=面试中，2=待筛选，3=已录用

    // ======================== 新增 status_name 字段 开始 ========================
    /**
     * 状态名称（与status一一对应，自动填充）
     */
    @Excel(name = "状态名称", width = 15)  // 可选，用于Excel导出显示
    @TableField("status_name")  // 映射到数据库表的status_name字段
    private String statusName;  // 驼峰命名，对应数据库字段status_name
    // ======================== 新增 status_name 字段 结束 ========================

    // ======================== 新增 knowledge_id 字段 开始 ========================
    /**
     * RAG知识库ID（与rag_knowledge表主键对应）
     */
    @TableField("knowledge_id")
    private String knowledgeId;
    // ======================== 新增 knowledge_id 字段 结束 ========================

    // 由于使用了@Data注解，getter和setter会自动生成
    // 以下为显式写出，方便确认（IDE自动生成也可）
    public String getStatusName() {
        return statusName;
    }

    public void setStatusName(String statusName) {
        this.statusName = statusName;
    }
}