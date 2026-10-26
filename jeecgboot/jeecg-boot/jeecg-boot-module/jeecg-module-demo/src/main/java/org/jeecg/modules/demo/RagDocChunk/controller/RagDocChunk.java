package org.jeecg.modules.demo.RagDocChunk.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import org.springframework.stereotype.Component;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/**
 * MCP SSE客户端
 * Python MCP服务地址：http://127.0.0.1:8000/sse
 */
@Component
public class RagDocChunk {

    private static final String MCP_SSE_URL = "http://127.0.0.1:8604/sse";
    private volatile String sessionId;
    private volatile String initializedSession = null; // 已完成initialize握手的session
    private final Object initLock = new Object();
    private final ConcurrentHashMap<String, CountDownLatch> latchMap = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<String, String> resultMap = new ConcurrentHashMap<>();
    private Thread sseThread;
    private volatile boolean running = false;

    private final ObjectMapper objectMapper = new ObjectMapper();


    @PostConstruct
    public void init() {
        running = true;
        sseThread = new Thread(this::sseListenThread, "mcp-sse-listener");
        sseThread.setDaemon(true);
        sseThread.start();
    }


    @PreDestroy
    public void destroy() {
        running = false;
        if(sseThread != null){
            sseThread.interrupt();
        }
    }


    /**
     * Controller原样调用，上层代码不需要改动
     */
    public String callTool(String toolName, Map<String,Object> args) throws Exception {
        // SSE是异步连接，启动后需要等待sessionId就绪，最多等10秒
        int waitCount = 0;
        while(sessionId == null && waitCount < 20){
            try {
                TimeUnit.MILLISECONDS.sleep(500);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new RuntimeException("等待MCP sessionId被中断", e);
            }
            waitCount++;
        }
        if(sessionId == null){
            throw new RuntimeException("MCP SSE尚未建立session，请确认Python MCP服务已启动");
        }
        // MCP协议要求先完成initialize握手，才能调用工具
        ensureInitialized();
        String reqId = UUID.randomUUID().toString();
        CountDownLatch latch = new CountDownLatch(1);
        latchMap.put(reqId, latch);
        ObjectNode payload = objectMapper.createObjectNode();
        payload.put("jsonrpc","2.0");
        payload.put("id", reqId);
        payload.put("method","tools/call");
        ObjectNode params = objectMapper.createObjectNode();
        params.put("name", toolName);
        params.set("arguments", objectMapper.valueToTree(args));
        payload.set("params", params);
        String jsonBody = objectMapper.writeValueAsString(payload);

        // ============新增调试打印！重点看这个JSON===========
        System.out.println("【MCP客户端发送完整JSON报文】：" + jsonBody);
        System.out.println("【传入args原始map】：" + args);
        // ==================================================

        sendPost(sessionId, jsonBody);
        boolean ok = latch.await(30, TimeUnit.SECONDS);
        latchMap.remove(reqId);
        if(!ok){
            resultMap.remove(reqId);
            throw new RuntimeException("调用MCP工具超时30s");
        }
        String res = resultMap.remove(reqId);
        return res;
    }


    /**
     * MCP初始化握手：initialize请求 + initialized通知，每个session只做一次
     */
    private void ensureInitialized() throws Exception {
        if(sessionId.equals(initializedSession)){
            return;
        }
        synchronized (initLock){
            if(sessionId.equals(initializedSession)){
                return;
            }
            String sid = sessionId;
            // 1. 发送 initialize 请求
            String initId = UUID.randomUUID().toString();
            CountDownLatch latch = new CountDownLatch(1);
            latchMap.put(initId, latch);
            ObjectNode payload = objectMapper.createObjectNode();
            payload.put("jsonrpc","2.0");
            payload.put("id", initId);
            payload.put("method","initialize");
            ObjectNode params = objectMapper.createObjectNode();
            params.put("protocolVersion","2024-11-05");
            params.set("capabilities", objectMapper.createObjectNode());
            ObjectNode clientInfo = objectMapper.createObjectNode();
            clientInfo.put("name","jeecg-java-client");
            clientInfo.put("version","1.0");
            params.set("clientInfo", clientInfo);
            payload.set("params", params);
            sendPost(sid, objectMapper.writeValueAsString(payload));
            boolean ok = latch.await(15, TimeUnit.SECONDS);
            latchMap.remove(initId);
            if(!ok){
                resultMap.remove(initId);
                throw new RuntimeException("MCP initialize握手超时");
            }
            String initResp = resultMap.remove(initId);
            System.out.println("【MCP初始化】initialize返回: " + initResp);

            // 2. 发送 notifications/initialized 通知（无id，无需等待响应）
            ObjectNode notice = objectMapper.createObjectNode();
            notice.put("jsonrpc","2.0");
            notice.put("method","notifications/initialized");
            notice.set("params", objectMapper.createObjectNode());
            sendPost(sid, objectMapper.writeValueAsString(notice));
            initializedSession = sid;
            System.out.println("【MCP初始化】握手完成 session=" + sid);
        }
    }


    private void sseListenThread(){
        while (running){
            HttpURLConnection conn = null;
            try{
                URL url = new URL(MCP_SSE_URL);
                conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("GET");
                conn.setConnectTimeout(5000);
                conn.setReadTimeout(0);
                conn.setRequestProperty("Accept","text/event-stream");

                try(BufferedReader br = new BufferedReader(new InputStreamReader(conn.getInputStream(), StandardCharsets.UTF_8))){
                    String line;
                    String currentEvent = null;
                    while(running && (line = br.readLine()) != null){
                        if(line.startsWith("event:")){
                            currentEvent = line.substring(6).trim();
                        }else if(line.startsWith("data:")){
                            String data = line.substring(5).trim();
                            // FastMCP协议：event=endpoint时，data是 /messages/?session_id=xxx
                            if("endpoint".equals(currentEvent)){
                                // 从URL参数中提取session_id
                                int idx = data.indexOf("session_id=");
                                if(idx >= 0){
                                    sessionId = data.substring(idx + "session_id=".length());
                                    System.out.println("【MCP SSE】获取到sessionId: " + sessionId);
                                }
                            }else{
                                // 其他事件按JSON解析
                                try {
                                    var jsonNode = objectMapper.readTree(data);
                                    if(jsonNode.has("id")){
                                        String rid = jsonNode.get("id").asText();
                                        resultMap.put(rid, jsonNode.toString());
                                        CountDownLatch latch = latchMap.get(rid);
                                        if(latch != null){
                                            latch.countDown();
                                        }
                                    }
                                } catch (Exception e) {
                                    // 非JSON数据忽略
                                }
                            }
                        }
                    }
                }
            }catch (Exception e){
                try { TimeUnit.SECONDS.sleep(3); } catch (InterruptedException ignored) {}
            }finally {
                if(conn != null) conn.disconnect();
            }
        }
    }


    private void sendPost(String sid, String body) throws IOException {
        // FastMCP协议：POST端点为 /messages/?session_id=xxx
        URL url = new URL(MCP_SSE_URL.replace("/sse","/messages/?session_id="+sid));
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod("POST");
        conn.setDoOutput(true);
        conn.setRequestProperty("Content-Type","application/json");
        try(OutputStream os = conn.getOutputStream()){
            os.write(body.getBytes(StandardCharsets.UTF_8));
        }
        int code = conn.getResponseCode();
        conn.disconnect();
        if(code <200 || code >=300){
            throw new IOException("MCP message接口返回异常code:"+code);
        }
    }
}