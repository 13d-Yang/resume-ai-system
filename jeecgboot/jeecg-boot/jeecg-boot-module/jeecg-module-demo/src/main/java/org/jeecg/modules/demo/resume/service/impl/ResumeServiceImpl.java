package org.jeecg.modules.demo.resume.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import lombok.extern.slf4j.Slf4j;
import org.jeecg.modules.demo.resume.entity.Resume;
import org.jeecg.modules.demo.resume.mapper.ResumeMapper;
import org.jeecg.modules.demo.resume.service.IResumeService;
import org.jeecg.modules.demo.resume.service.RagClientUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

/**
 * 简历服务实现类
 */
@Slf4j
@Service
public class ResumeServiceImpl extends ServiceImpl<ResumeMapper, Resume> implements IResumeService {

    // 注入RAG调用工具
    @Autowired
    private RagClientUtil ragClientUtil;

    // ======================== 新增自动填充逻辑 开始 ========================
    /**
     * 新增简历时自动填充status_name，并同步RAG入库后回写knowledge_id
     */
    @Override
    public boolean save(Resume entity) {
        fillStatusName(entity); // 调用填充方法
        boolean saveOk = super.save(entity); // 执行原保存逻辑
        // 保存成功同步RAG向量库
        if(saveOk){
            Long resumeId = entity.getId();
            String filePath = entity.getResumePath();
            String fileName = entity.getResumeFile();
            if(filePath != null && !filePath.isBlank()){
                String knowledgeId = ragClientUtil.syncResumeToRag(resumeId, filePath, fileName);
                if(knowledgeId != null && !knowledgeId.isBlank()){
                    // 回写 knowledge_id 到 resume 表
                    Resume update = new Resume();
                    update.setId(resumeId);
                    update.setKnowledgeId(knowledgeId);
                    super.updateById(update);
                    log.info("【RAG回写成功】简历ID:{} knowledge_id:{}", resumeId, knowledgeId);
                } else {
                    log.warn("【RAG回写跳过】简历ID:{} 未获取到有效 knowledge_id", resumeId);
                }
            }
        }
        return saveOk;
    }

    /**
     * 根据ID更新简历时自动填充status_name
     */
    @Override
    public boolean updateById(Resume entity) {
        fillStatusName(entity); // 调用填充方法
        return super.updateById(entity); // 执行原更新逻辑
    }

    /**
     * 核心方法：根据status值自动设置对应的status_name
     * @param resume 简历实体对象
     */
    private void fillStatusName(Resume resume) {
        Integer status = resume.getStatus();
        if (status == null) {
            resume.setStatusName("未知状态"); // 处理空值情况
            return;
        }

        // 根据status值匹配对应的状态名称
        switch (status) {
            case 1:
                resume.setStatusName("面试中");
                break;
            case 2:
                resume.setStatusName("待筛选");
                break;
            case 3:
                resume.setStatusName("已录用");
                break;
            case 4:
                resume.setStatusName("已拒绝");
                break;
            default:
                resume.setStatusName("未知状态");
                break;
        }
    }
    // ======================== 新增自动填充逻辑 结束 ========================

}