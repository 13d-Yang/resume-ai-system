package org.jeecg.modules.demo.mcp.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.fasterxml.jackson.databind.JsonNode;
import org.jeecg.modules.demo.mcp.client.McpClient;
import org.jeecg.modules.demo.mcp.entity.Mcp;
import org.jeecg.modules.demo.mcp.mapper.McpMapper;
import org.jeecg.modules.demo.mcp.service.IMcpService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

@Service
public class McpServiceImpl extends ServiceImpl<McpMapper, Mcp> implements IMcpService {

    @Autowired
    private McpClient mcpClient;

    @Override
    public List<Mcp> listEnabled() {
        return lambdaQuery().eq(Mcp::getStatus, "enable").list();
    }

    @Override
    public void addMcp(Mcp mcp) {
        mcp.setCategory("mcp");
        save(mcp);
    }

    @Override
    public void enable(String id) {
        Mcp mcp = getById(id);
        if (mcp == null) {
            throw new IllegalArgumentException("MCP配置不存在");
        }
        mcp.setStatus("enable");
        syncTools(mcp);
        updateById(mcp);
    }

    @Override
    public void disable(String id) {
        Mcp mcp = getById(id);
        if (mcp == null) {
            throw new IllegalArgumentException("MCP配置不存在");
        }
        mcp.setStatus("disable");
        updateById(mcp);
    }

    @Override
    public String callTool(String mcpId, String toolName, Map<String, Object> arguments) {
        Mcp mcp = getById(mcpId);
        if (mcp == null) {
            throw new IllegalArgumentException("MCP不存在");
        }
        if (!"enable".equals(mcp.getStatus())) {
            throw new IllegalArgumentException("MCP未启动");
        }
        String endpoint = mcp.getEndpoint();
        if (endpoint == null || endpoint.isEmpty()) {
            throw new IllegalArgumentException("MCP endpoint 未配置");
        }
        try {
            if (!endpoint.endsWith("/sse")) {
                return mcpClient.callByGateway(endpoint, toolName, arguments);
            }
            return mcpClient.callTool(endpoint, toolName, arguments);
        } catch (Exception e) {
            throw new RuntimeException(e.getMessage(), e);
        }
    }

    /**
     * 同步工具清单，失败只记录到metadata，不阻断启用
     */
    private void syncTools(Mcp mcp) {
        String endpoint = mcp.getEndpoint();
        if (endpoint == null || endpoint.isEmpty()) {
            return;
        }
        try {
            List<JsonNode> tools = mcpClient.listTools(endpoint);
            mcp.setTools(tools.toString());
            mcp.setMetadata("{\"tool_count\":" + tools.size() + "}");
        } catch (Exception e) {
            mcp.setMetadata("{\"error\":\"" + String.valueOf(e.getMessage()).replace("\"", "'") + "\"}");
        }
    }
}
