package org.jeecg.modules.demo.mcp.service;

import com.baomidou.mybatisplus.extension.service.IService;
import org.jeecg.modules.demo.mcp.entity.Mcp;

import java.util.List;
import java.util.Map;

public interface IMcpService extends IService<Mcp> {

    /**
     * 查询已启用的MCP服务
     */
    List<Mcp> listEnabled();

    /**
     * 新增MCP配置（自动归类为mcp）
     */
    void addMcp(Mcp mcp);

    /**
     * 启用MCP，并同步工具清单
     */
    void enable(String id);

    /**
     * 停用MCP
     */
    void disable(String id);

    /**
     * 调用MCP工具：按endpoint类型分流（/sse直连，其余走网关）
     */
    String callTool(String mcpId, String toolName, Map<String, Object> arguments);
}
