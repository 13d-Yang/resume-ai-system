package org.jeecg.modules.demo.resume.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.jeecg.modules.demo.resume.entity.Resume;

@Mapper
public interface ResumeMapper extends BaseMapper<Resume> {
    // 继承 BaseMapper 后，基础的增删改查都已经有了
}