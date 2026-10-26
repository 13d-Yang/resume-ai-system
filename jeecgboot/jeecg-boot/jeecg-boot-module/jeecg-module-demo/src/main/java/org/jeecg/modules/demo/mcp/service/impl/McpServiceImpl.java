package org.jeecg.modules.demo.mcp.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.jeecg.modules.demo.mcp.entity.Mcp;
import org.jeecg.modules.demo.mcp.mapper.McpMapper;
import org.jeecg.modules.demo.mcp.service.IMcpService;
import org.springframework.stereotype.Service;

@Service
public class McpServiceImpl extends ServiceImpl<McpMapper, Mcp> implements IMcpService {
}