package org.jeecg.modules.demo.mcp.client;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * MCP协议客户端：只负责HTTP/SSE通信，不含业务判断
 */
@Component
public class McpClient {

    private static final ObjectMapper OM = new ObjectMapper();

    /**
     * 连接MCP服务并读取工具清单
     */
    public List<JsonNode> listTools(String endpoint) throws Exception {
        String baseUrl = endpoint.replace("/sse", "");
        HttpClient client = newClient();

        HttpRequest sseReq = HttpRequest.newBuilder(URI.create(endpoint))
                .timeout(Duration.ofSeconds(15))
                .header("Accept", "text/event-stream").build();
        HttpResponse<InputStream> sseResp = client.send(sseReq, HttpResponse.BodyHandlers.ofInputStream());

        try (BufferedReader sseReader = new BufferedReader(
                new InputStreamReader(sseResp.body(), StandardCharsets.UTF_8))) {

            String sessionPath = readSessionPath(sseReader);
            if (sessionPath == null) {
                throw new IllegalStateException("无法建立SSE连接");
            }
            String msgUrl = baseUrl + sessionPath;

            initialize(client, msgUrl);

            Map<String, Object> listMap = new LinkedHashMap<>();
            listMap.put("jsonrpc", "2.0");
            listMap.put("id", 2);
            listMap.put("method", "tools/list");
            listMap.put("params", new LinkedHashMap<>());
            client.send(post(msgUrl, OM.writeValueAsString(listMap)), HttpResponse.BodyHandlers.ofString());

            String line;
            while ((line = sseReader.readLine()) != null) {
                String trimmed = line.trim();
                if (trimmed.startsWith("data: {")) {
                    JsonNode node = OM.readTree(trimmed.substring(6).trim());
                    if (node.has("id") && node.get("id").asInt() == 2) {
                        JsonNode tools = node.path("result").path("tools");
                        List<JsonNode> result = new ArrayList<>();
                        if (tools.isArray()) {
                            tools.forEach(result::add);
                        }
                        return result;
                    }
                }
            }
            return new ArrayList<>();
        }
    }

    /**
     * 调用MCP工具：SSE直连（短连接模式）
     */
    public String callTool(String endpoint, String toolName, Map<String, Object> arguments) throws Exception {
        String baseUrl = endpoint.replace("/sse", "");
        HttpClient client = newClient();

        HttpRequest sseReq = HttpRequest.newBuilder(URI.create(endpoint))
                .timeout(Duration.ofSeconds(15))
                .header("Accept", "text/event-stream").build();
        HttpResponse<InputStream> sseResp = client.send(sseReq, HttpResponse.BodyHandlers.ofInputStream());

        try (BufferedReader sseReader = new BufferedReader(
                new InputStreamReader(sseResp.body(), StandardCharsets.UTF_8))) {

            String sessionPath = readSessionPath(sseReader);
            if (sessionPath == null) {
                throw new IllegalStateException("无法连接MCP服务，请检查Python是否启动");
            }
            String msgUrl = baseUrl + sessionPath;
            String callId = UUID.randomUUID().toString().substring(0, 8);

            initialize(client, msgUrl);

            Map<String, Object> callPayload = new LinkedHashMap<>();
            callPayload.put("jsonrpc", "2.0");
            callPayload.put("id", callId);
            callPayload.put("method", "tools/call");
            Map<String, Object> params = new LinkedHashMap<>();
            params.put("name", toolName);
            params.put("arguments", arguments);
            callPayload.put("params", params);

            client.send(post(msgUrl, OM.writeValueAsString(callPayload)), HttpResponse.BodyHandlers.ofString());

            String line;
            while ((line = sseReader.readLine()) != null) {
                String trimmed = line.trim();
                if (trimmed.startsWith("data: {")) {
                    JsonNode node = OM.readTree(trimmed.substring(6).trim());
                    if (node.has("id") && callId.equals(node.get("id").asText())) {
                        JsonNode content = node.path("result").path("content");
                        if (content.isArray() && content.size() > 0) {
                            return content.get(0).path("text").asText();
                        }
                        return node.path("result").toString();
                    }
                }
            }
            throw new IllegalStateException("MCP工具调用超时或无响应");
        }
    }

    /**
     * 调用MCP工具：通过8501网关转发（普通HTTP，不含MCP协议）
     */
    public String callByGateway(String gatewayUrl, String toolName, Map<String, Object> arguments) throws Exception {
        try {
            Map<String, Object> payload = new LinkedHashMap<>();
            payload.put("tool_name", toolName);
            payload.put("params", arguments);

            HttpRequest request = HttpRequest.newBuilder(URI.create(gatewayUrl))
                    .timeout(Duration.ofSeconds(300))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(
                            OM.writeValueAsString(payload), StandardCharsets.UTF_8))
                    .build();

            HttpResponse<String> resp = newClient().send(request,
                    HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            if (resp.statusCode() != 200) {
                throw new IllegalStateException("网关调用失败：HTTP " + resp.statusCode());
            }
            JsonNode node = OM.readTree(resp.body());
            if (node.path("code").asInt() != 200) {
                throw new IllegalStateException(node.path("message").asText("网关调用失败"));
            }
            JsonNode resultNode = node.path("result");
            return resultNode.isTextual() ? resultNode.asText() : resultNode.toString();
        } catch (IllegalStateException e) {
            throw e;
        } catch (Exception e) {
            throw new IllegalStateException("网关调用失败: " + e.getMessage(), e);
        }
    }

    private HttpClient newClient() {
        return HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(15)).build();
    }

    /**
     * 从SSE流中读取 messages 端点路径
     */
    private String readSessionPath(BufferedReader reader) throws Exception {
        String line;
        while ((line = reader.readLine()) != null) {
            String trimmed = line.trim();
            if (trimmed.startsWith("data: /")) {
                return trimmed.substring(5).trim();
            }
        }
        return null;
    }

    /**
     * MCP初始化握手：initialize请求 + initialized通知
     */
    private void initialize(HttpClient client, String msgUrl) throws Exception {
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
        client.send(post(msgUrl, OM.writeValueAsString(initMap)), HttpResponse.BodyHandlers.ofString());

        Map<String, Object> notifMap = new LinkedHashMap<>();
        notifMap.put("jsonrpc", "2.0");
        notifMap.put("method", "notifications/initialized");
        client.send(post(msgUrl, OM.writeValueAsString(notifMap)), HttpResponse.BodyHandlers.ofString());
    }

    private HttpRequest post(String url, String body) {
        return HttpRequest.newBuilder(URI.create(url))
                .timeout(Duration.ofSeconds(8))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body)).build();
    }
}
