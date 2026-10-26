package org.jeecg.modules.demo.mcp.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.jeecg.common.api.vo.Result;
import org.jeecg.modules.demo.mcp.entity.Mcp;
import org.jeecg.modules.demo.mcp.service.IMcpService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

@RestController
@CrossOrigin("*")
public class McpController {

    private static final ObjectMapper om = new ObjectMapper();

    @Autowired
    private IMcpService mcpService;

    // ========== 新增：返回启用中的 MCP 列表（前端用来动态拿 ID）==========
    @GetMapping("/sys/mcp/enabled")
    public Result<?> getEnabled() {
        return Result.OK(mcpService.lambdaQuery().eq(Mcp::getStatus, "enable").list());
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
        mcp.setCategory("mcp");
        mcpService.save(mcp);
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
        Mcp mcp = mcpService.getById(id);
        if (mcp == null) return Result.error("MCP配置不存在");
        mcp.setStatus("enable");
        readTools(mcp);
        mcpService.updateById(mcp);
        return Result.OK("启动成功");
    }

    @PostMapping("/sys/mcp/stop")
    public Result<?> stop(@RequestParam("id") String id) {
        Mcp mcp = mcpService.getById(id);
        if (mcp == null) return Result.error("MCP配置不存在");
        mcp.setStatus("disable");
        mcpService.updateById(mcp);
        return Result.OK("停止成功");
    }

    // ===== 读工具数（修复：用 Map 构造 JSON + UTF-8 编码）=====
    private void readTools(Mcp mcp) {
        try {
            String endpoint = mcp.getEndpoint();
            if (endpoint == null || endpoint.isEmpty()) return;

            String baseUrl = endpoint.replace("/sse", "");
            HttpClient client = HttpClient.newBuilder()
                    .connectTimeout(Duration.ofSeconds(10)).build();

            HttpRequest sseReq = HttpRequest.newBuilder(URI.create(endpoint))
                    .timeout(Duration.ofSeconds(15))
                    .header("Accept", "text/event-stream").build();

            HttpResponse<InputStream> sseResp = client.send(
                    sseReq, HttpResponse.BodyHandlers.ofInputStream());

            BufferedReader sseReader = new BufferedReader(
                    new InputStreamReader(sseResp.body(), StandardCharsets.UTF_8));

            String sessionPath = null;
            String line;
            while ((line = sseReader.readLine()) != null) {
                String trimmed = line.trim();
                if (trimmed.startsWith("data: /")) {
                    sessionPath = trimmed.substring(5).trim();
                    break;
                }
            }
            if (sessionPath == null) {
                sseReader.close();
                mcp.setMetadata("{\"error\":\"无法建立SSE连接\"}");
                return;
            }

            String msgUrl = baseUrl + sessionPath;

            Map<String, Object> initMap = new LinkedHashMap<>();
            initMap.put("jsonrpc", "2.0");
            initMap.put("id", 1);
            initMap.put("method", "initialize");
            Map<String, Object> initParams = new LinkedHashMap<>();
            initParams.put("protocolVersion", "2024-11-05");
            initParams.put("capabilities", new LinkedHashMap<>());
            Map<String, Object> clientInfo = new LinkedHashMap<>();
            clientInfo.put("name", "jeecg");
            clientInfo.put("version", "1.0");
            initParams.put("clientInfo", clientInfo);
            initMap.put("params", initParams);
            client.send(post(msgUrl, om.writeValueAsString(initMap)), HttpResponse.BodyHandlers.ofString());

            Map<String, Object> notifMap = new LinkedHashMap<>();
            notifMap.put("jsonrpc", "2.0");
            notifMap.put("method", "notifications/initialized");
            client.send(post(msgUrl, om.writeValueAsString(notifMap)), HttpResponse.BodyHandlers.ofString());

            Map<String, Object> listMap = new LinkedHashMap<>();
            listMap.put("jsonrpc", "2.0");
            listMap.put("id", 2);
            listMap.put("method", "tools/list");
            listMap.put("params", new LinkedHashMap<>());
            client.send(post(msgUrl, om.writeValueAsString(listMap)), HttpResponse.BodyHandlers.ofString());

            while ((line = sseReader.readLine()) != null) {
                String trimmed = line.trim();
                if (trimmed.startsWith("data: {")) {
                    String json = trimmed.substring(6).trim();
                    JsonNode node = om.readTree(json);
                    if (node.has("id") && node.get("id").asInt() == 2) {
                        JsonNode tools = node.path("result").path("tools");
                        int count = tools.isArray() ? tools.size() : 0;
                        mcp.setMetadata("{\"tool_count\":" + count + "}");
                        mcp.setTools(tools.isArray() ? tools.toString() : "[]");
                        break;
                    }
                }
            }
            sseReader.close();
        } catch (Exception e) {
            e.printStackTrace();
            try {
                mcp.setMetadata("{\"error\":\"" + e.getMessage().replace("\"", "'") + "\"}");
            } catch (Exception ignored) {}
        }
    }

    private HttpRequest post(String url, String body) {
        return HttpRequest.newBuilder(URI.create(url))
                .timeout(Duration.ofSeconds(8))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body)).build();
    }

    // ===== callTool：加了 3 行调试日志，其余完全没动 =====
    @PostMapping("/sys/mcp/call_tool")
    public Result<?> callTool(
            @RequestParam("mcp_id") String mcpId,
            @RequestParam("tool_name") String toolName,
            @RequestBody Map<String, Object> arguments) {
        // ===== 新增的 3 行调试日志（看完后删掉就行）=====
        System.out.println("【DEBUG】前端传来的 mcp_id = [" + mcpId + "]");
        System.out.println("【DEBUG】tool_name = [" + toolName + "]");
        // ==============================================
        try {
            Mcp mcp = mcpService.getById(mcpId);
            System.out.println("【DEBUG】查到的 mcp 对象 = " + mcp); // 这行也是新增
            if (mcp == null) return Result.error("MCP不存在");
            if (!"enable".equals(mcp.getStatus())) return Result.error("MCP未启动");

            String endpoint = mcp.getEndpoint();
            String baseUrl = endpoint.replace("/sse", "");

            HttpClient client = HttpClient.newBuilder()
                    .connectTimeout(Duration.ofSeconds(15)).build();

            HttpRequest sseReq = HttpRequest.newBuilder(URI.create(endpoint))
                    .timeout(Duration.ofSeconds(15))
                    .header("Accept", "text/event-stream").build();

            HttpResponse<InputStream> sseResp = client.send(
                    sseReq, HttpResponse.BodyHandlers.ofInputStream());

            BufferedReader sseReader = new BufferedReader(
                    new InputStreamReader(sseResp.body(), StandardCharsets.UTF_8));

            String sessionPath = null;
            String line;
            while ((line = sseReader.readLine()) != null) {
                String trimmed = line.trim();
                if (trimmed.startsWith("data: /")) {
                    sessionPath = trimmed.substring(5).trim();
                    break;
                }
            }
            if (sessionPath == null) {
                sseReader.close();
                return Result.error("无法连接MCP服务，请检查Python是否启动");
            }

            String msgUrl = baseUrl + sessionPath;
            String callId = UUID.randomUUID().toString().substring(0, 8);

            Map<String, Object> initMap = new LinkedHashMap<>();
            initMap.put("jsonrpc", "2.0");
            initMap.put("id", 1);
            initMap.put("method", "initialize");
            Map<String, Object> initParams = new LinkedHashMap<>();
            initParams.put("protocolVersion", "2024-11-05");
            initParams.put("capabilities", new LinkedHashMap<>());
            Map<String, Object> clientInfo = new LinkedHashMap<>();
            clientInfo.put("name", "jeecg");
            clientInfo.put("version", "1.0");
            initParams.put("clientInfo", clientInfo);
            initMap.put("params", initParams);
            client.send(post(msgUrl, om.writeValueAsString(initMap)), HttpResponse.BodyHandlers.ofString());

            Map<String, Object> notifMap = new LinkedHashMap<>();
            notifMap.put("jsonrpc", "2.0");
            notifMap.put("method", "notifications/initialized");
            client.send(post(msgUrl, om.writeValueAsString(notifMap)), HttpResponse.BodyHandlers.ofString());

            Map<String, Object> callPayload = new LinkedHashMap<>();
            callPayload.put("jsonrpc", "2.0");
            callPayload.put("id", callId);
            callPayload.put("method", "tools/call");
            Map<String, Object> params = new LinkedHashMap<>();
            params.put("name", toolName);
            params.put("arguments", arguments);
            callPayload.put("params", params);

            client.send(post(msgUrl, om.writeValueAsString(callPayload)), HttpResponse.BodyHandlers.ofString());

            String result = null;
            while ((line = sseReader.readLine()) != null) {
                String trimmed = line.trim();
                if (trimmed.startsWith("data: {")) {
                    String json = trimmed.substring(6).trim();
                    JsonNode node = om.readTree(json);
                    if (node.has("id") && callId.equals(node.get("id").asText())) {
                        JsonNode content = node.path("result").path("content");
                        if (content.isArray() && content.size() > 0) {
                            result = content.get(0).path("text").asText();
                        } else {
                            result = node.path("result").toString();
                        }
                        break;
                    }
                }
            }
            sseReader.close();

            if (result == null) return Result.error("MCP工具调用超时或无响应");
            return Result.OK(result);
        } catch (Exception e) {
            e.printStackTrace();
            return Result.error("调用失败: " + e.getMessage());
        }
    }
}