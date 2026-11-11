package org.jeecg.modules.demo.resume.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.IService;
import org.jeecg.modules.demo.resume.entity.Resume;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;
import java.util.Map;

public interface IResumeService extends IService<Resume> {

    /**
     * 上传简历：保存文件 + 落库（并触发RAG入库）
     */
    Resume upload(MultipartFile file) throws Exception;

    /**
     * 从源目录同步单个文件到存储目录并落库
     */
    Resume syncSingleFile(String fileName) throws Exception;

    /**
     * 列出源目录中可同步的简历文件
     */
    List<String> listSourceFiles();

    /**
     * 分页查询未删除的简历
     */
    IPage<Resume> pageList(Integer pageNo, Integer pageSize);

    /**
     * 各状态简历数量统计
     */
    Map<String, Long> getStats();

    /**
     * 删除简历：记录 + 本地文件
     */
    void deleteResume(String id);

    /**
     * 批量删除简历：记录 + 本地文件
     */
    void deleteBatchResumes(String ids);
}
