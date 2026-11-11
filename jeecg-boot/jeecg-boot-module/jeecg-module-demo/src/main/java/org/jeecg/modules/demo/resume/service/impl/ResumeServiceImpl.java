package org.jeecg.modules.demo.resume.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import lombok.extern.slf4j.Slf4j;
import org.jeecg.modules.demo.resume.entity.Resume;
import org.jeecg.modules.demo.resume.mapper.ResumeMapper;
import org.jeecg.modules.demo.resume.service.IResumeService;
import org.jeecg.modules.demo.resume.service.RagClientUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.File;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * 简历服务实现类
 */
@Slf4j
@Service
public class ResumeServiceImpl extends ServiceImpl<ResumeMapper, Resume> implements IResumeService {

    private static final String SOURCE_DIR = "C:\\Users\\简历测试数据";
    private static final String STORAGE_DIR = "C:\\Users\\简历测试数据\\存储\\";

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

    // ======================== 文件与业务逻辑 开始 ========================
    @Override
    public Resume upload(MultipartFile file) throws Exception {
        String originalFilename = file.getOriginalFilename();
        if (originalFilename == null || originalFilename.lastIndexOf(".") < 0) {
            throw new IllegalArgumentException("文件名不合法：" + originalFilename);
        }
        String suffix = originalFilename.substring(originalFilename.lastIndexOf("."));
        String uuidFileName = UUID.randomUUID() + suffix;

        File dir = new File(STORAGE_DIR);
        if (!dir.exists()) {
            dir.mkdirs();
        }

        File targetFile = new File(STORAGE_DIR + uuidFileName);
        file.transferTo(targetFile);

        Resume resume = new Resume();
        resume.setResumeName(originalFilename.replace(suffix, ""));
        resume.setResumeFile(originalFilename);
        resume.setResumePath(STORAGE_DIR + uuidFileName);
        resume.setCreateTime(new Date());
        resume.setUpdateTime(new Date());
        resume.setDelFlag(0);
        resume.setStatus(2);

        save(resume);
        return resume;
    }

    @Override
    public Resume syncSingleFile(String fileName) throws Exception {
        File sourceFile = new File(SOURCE_DIR, fileName);
        if (!sourceFile.exists()) {
            throw new IllegalArgumentException("文件不存在：" + fileName);
        }

        File storageDir = new File(STORAGE_DIR);
        if (!storageDir.exists()) {
            storageDir.mkdirs();
        }

        String suffix = fileName.substring(fileName.lastIndexOf("."));
        String newFileName = UUID.randomUUID() + suffix;
        File targetFile = new File(storageDir, newFileName);

        Files.copy(sourceFile.toPath(), targetFile.toPath(), StandardCopyOption.REPLACE_EXISTING);

        Resume resume = new Resume();
        resume.setResumeName(fileName.replace(suffix, ""));
        resume.setResumeFile(fileName);
        resume.setResumePath(targetFile.getAbsolutePath());
        resume.setCreateTime(new Date());
        resume.setUpdateTime(new Date());
        resume.setDelFlag(0);
        resume.setStatus(2);

        save(resume);
        return resume;
    }

    @Override
    public List<String> listSourceFiles() {
        File dir = new File(SOURCE_DIR);
        if (!dir.exists()) {
            throw new IllegalStateException("目录不存在");
        }

        File[] files = dir.listFiles();
        if (files == null) {
            throw new IllegalStateException("无文件");
        }

        List<String> list = new ArrayList<>();
        for (File f : files) {
            if (f.isFile()) {
                String name = f.getName().toLowerCase();
                if (name.endsWith(".pdf") || name.endsWith(".doc") || name.endsWith(".docx")) {
                    list.add(f.getName());
                }
            }
        }
        return list;
    }

   @Override
    public IPage<Resume> pageList(Integer pageNo, Integer pageSize) {
        QueryWrapper<Resume> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq("del_flag", 0);
        applyKbReadyFilter(queryWrapper);
        queryWrapper.orderByDesc("create_time");

        Page<Resume> page = new  Page<>(pageNo, pageSize);
        return page(page, queryWrapper);
    }

    /**
     * 只保留已完成 AI 入库的简历：必须有知识库记录且存在分片。
     * 未入库的简历在问答/AI 分析时必然查不到数据，统一从列表和统计中排除。
     */
    private void applyKbReadyFilter(QueryWrapper<Resume> wrapper) {
        wrapper.isNotNull("knowledge_id");
        wrapper.exists("SELECT 1 FROM rag_knowledge k WHERE k.id = resume.knowledge_id AND k.del_flag = 0");
        wrapper.exists("SELECT 1 FROM rag_doc_chunk c WHERE c.knowledge_id = resume.knowledge_id AND c.del_flag = 0");
    }

    @Override
    public Map<String, Long> getStats() {
        QueryWrapper<Resume> allWrapper = new QueryWrapper<>();
        allWrapper.eq("del_flag", 0);
        applyKbReadyFilter(allWrapper);
        Long totalAll = count(allWrapper);

        QueryWrapper<Resume> waitWrapper = new QueryWrapper<>();
        waitWrapper.eq("del_flag", 0).eq("status", 2);
        applyKbReadyFilter(waitWrapper);
        Long waitFilter = count(waitWrapper);

        QueryWrapper<Resume> interviewWrapper = new QueryWrapper<>();
        interviewWrapper.eq("del_flag", 0).eq("status", 1);
        applyKbReadyFilter(interviewWrapper);
        Long interviewing = count(interviewWrapper);

        QueryWrapper<Resume> employWrapper = new QueryWrapper<>();
        employWrapper.eq("del_flag", 0).eq("status", 3);
        applyKbReadyFilter(employWrapper);
        Long employed = count(employWrapper);

        QueryWrapper<Resume> rejectWrapper = new QueryWrapper<>();
        rejectWrapper.eq("del_flag", 0).eq("status", 4);
        applyKbReadyFilter(rejectWrapper);
        Long rejected = count(rejectWrapper);

        Map<String, Long> map = new HashMap<>();
        map.put("totalAll", totalAll);
        map.put("waitFilter", waitFilter);
        map.put("interviewing", interviewing);
        map.put("employed", employed);
        map.put("rejected", rejected);
        return map;
    }

    @Override
    public void deleteResume(String id) {
        Resume resume = getById(id);
        if (resume == null) {
            throw new IllegalArgumentException("数据不存在");
        }
        deleteFileQuietly(resume);
        removeById(id);
    }

    @Override
    public void deleteBatchResumes(String ids) {
        String[] idArr = ids.split(",");
        for (String id : idArr) {
            Resume resume = getById(id);
            if (resume != null) {
                deleteFileQuietly(resume);
            }
        }
        removeByIds(Arrays.asList(idArr));
    }

    /**
     * 删除本地文件失败不影响记录删除
     */
    private void deleteFileQuietly(Resume resume) {
        try {
            File file = new File(resume.getResumePath());
            if (file.exists()) {
                file.delete();
            }
        } catch (Exception e) {
            log.warn("删除简历文件失败，简历ID:{} 路径:{}", resume.getId(), resume.getResumePath(), e);
        }
    }
    // ======================== 文件与业务逻辑 结束 ========================
}
