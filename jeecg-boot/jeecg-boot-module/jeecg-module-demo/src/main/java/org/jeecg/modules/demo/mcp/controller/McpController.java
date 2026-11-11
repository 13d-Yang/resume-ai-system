package org.jeecg.modules.demo.mcp.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import org.apache.shiro.SecurityUtils;
import org.jeecg.common.api.vo.Result;
import org.jeecg.common.system.vo.LoginUser;
import org.jeecg.modules.demo.mcp.entity.Mcp;
import org.jeecg.modules.demo.mcp.service.IMcpService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@CrossOrigin("*")
public class McpController {

    @Autowired
    private IMcpService mcpService;

    @GetMapping("/sys/mcp/enabled")
    public Result<?> getEnabled() {
        return Result.OK(mcpService.listEnabled());
    }

    @GetMapping("/sys/mcp/list")
    public Result<IPage<Mcp>> getList(
            @RequestParam(defaultValue = "1") Long pageNum,
            @RequestParam(defaultValue = "10") Long pageSize) {
        Page<Mcp> page = new Page<>(pageNum, pageSize);
        mcpService.page(page);
        return Result.OK(page);
    }

    @PostMapping("/sys/mcp/add")
    public Result<?> add(@RequestBody Mcp mcp) {
        mcpService.addMcp(mcp);
        return Result.OK("新增成功");
    }

    @PostMapping("/sys/mcp/edit")
    public Result<?> edit(@RequestBody Mcp mcp) {
        mcpService.updateById(mcp);
        return Result.OK("更新成功");
    }

    @DeleteMapping("/sys/mcp/delete/{id}")
    public Result<?> delete(@PathVariable String id) {
        mcpService.removeById(id);
        return Result.OK("删除成功");
    }

    @PostMapping("/sys/mcp/start")
    public Result<?> start(@RequestParam("id") String id) {
        try {
            mcpService.enable(id);
            return Result.OK("启动成功");
        } catch (Exception e) {
            return Result.error(e.getMessage());
        }
    }

    @PostMapping("/sys/mcp/stop")
    public Result<?> stop(@RequestParam("id") String id) {
        try {
            mcpService.disable(id);
            return Result.OK("停止成功");
        } catch (Exception e) {
            return Result.error(e.getMessage());
        }
    }

    @PostMapping("/sys/mcp/call_tool")
    public Result<?> callTool(
            @RequestParam("mcp_id") String mcpId,
            @RequestParam("tool_name") String toolName,
            @RequestBody Map<String, Object> arguments) {
        try {
            injectSessionId(toolName, arguments);
            return Result.OK(mcpService.callTool(mcpId, toolName, arguments));
        } catch (Exception e) {
            return Result.error(e.getMessage());
        }
    }

    /**
     * 给 Agent 类入口工具注入会话ID，支撑 Python 侧 LangGraph 的多轮记忆。
     * 优先使用前端显式传入的 session_id（可实现按对话框隔离记忆）；
     * 未传时按「登录用户名_工具名」兜底：同一用户在同一功能入口内记忆连续，
     * 不同功能入口（对话/问答）之间的记忆互相隔离，且前端无需任何改动。
     */
    private void injectSessionId(String toolName, Map<String, Object> arguments) {
        if (arguments == null) {
            return;
        }
        boolean isAgentEntry = "run_agent_chat".equals(toolName)
                || "rag_resume_chat".equals(toolName);
        if (!isAgentEntry) {
            return;
        }
        Object sid = arguments.get("session_id");
        if (sid != null && !sid.toString().isEmpty()) {
            return;
        }
        String username = "anonymous";
        Object principal = SecurityUtils.getSubject().getPrincipal();
        if (principal instanceof LoginUser
                && ((LoginUser) principal).getUsername() != null) {
            username = ((LoginUser) principal).getUsername();
        }
        arguments.put("session_id", username + "_" + toolName);
    }
}
