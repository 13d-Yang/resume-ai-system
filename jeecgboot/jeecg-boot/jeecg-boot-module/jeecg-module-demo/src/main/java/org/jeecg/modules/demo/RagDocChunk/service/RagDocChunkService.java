package org.jeecg.modules.demo.RagDocChunk.service;


import cn.hutool.core.collection.CollUtil;
import com.alibaba.fastjson.JSON;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import lombok.Data;
import lombok.extern.slf4j.Slf4j;
import org.jeecg.common.api.vo.Result;
import org.jeecg.modules.demo.RagDocChunk.entity.RagDocChunk;
import org.jeecg.modules.demo.RagDocChunk.mapper.RagDocChunkMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.util.*;
import java.util.stream.Collectors;


@Service
@Slf4j
// 补上 implements IRagDocChunkService
public class RagDocChunkService extends ServiceImpl<RagDocChunkMapper, RagDocChunk> implements IRagDocChunkService {

    @Autowired
    private RagDocChunkMapper ragDocChunkMapper;


    // 静态内部类，保存分片+分数
    @Data
    static class ChunkScore {
        private RagDocChunk chunk;
        private double score;
    }


    /**
     * mock向量生成，绕开ollama，仅调试用
     */
    private List<Double> getEmbedding(String text) {
        List<Double> vec = new ArrayList<>();
        Random random = new Random(text.hashCode());
        for (int i = 0; i < 128; i++) {
            vec.add(random.nextDouble());
        }
        return vec;
    }


    /**
     * 余弦相似度
     */
    private double cosineSimilarity(List<Double> vecA, List<Double> vecB) {
        double dotProduct = 0.0;
        double normA = 0.0;
        double normB = 0.0;
        for (int i = 0; i < vecA.size(); i++) {
            dotProduct += vecA.get(i) * vecB.get(i);
            normA += Math.pow(vecA.get(i), 2);
            normB += Math.pow(vecB.get(i), 2);
        }
        return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
    }


    /**
     * 关键词检索
     */
    private List<ChunkScore> keywordSearch(String question, String knowledgeId) {
        List<ChunkScore> resultList = new ArrayList<>();
        String[] keywords = question.split(" ");

        LambdaQueryWrapper<RagDocChunk> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(RagDocChunk::getKnowledgeId, knowledgeId);
        wrapper.eq(RagDocChunk::getDelFlag, 0);
        for (String kw : keywords) {
            if (kw.length() > 0) {
                wrapper.or().like(RagDocChunk::getChunkText, kw);
            }
        }
        List<RagDocChunk> hitChunks = this.list(wrapper);
        for (RagDocChunk chunk : hitChunks) {
            ChunkScore cs = new ChunkScore();
            cs.setChunk(chunk);
            cs.setScore(0.7);
            resultList.add(cs);
        }
        return resultList;
    }


    /**
     * 文本分片
     */
    private List<String> splitText(String text, int chunkSize, int overlap) {
        List<String> res = new ArrayList<>();
        int start = 0;
        while (start < text.length()) {
            int end = Math.min(start + chunkSize, text.length());
            res.add(text.substring(start, end));
            start = start + chunkSize - overlap;
        }
        return res;
    }


    /**
     * 测试：把简历文本切分入库，执行一次即可，之后注释调用
     */
    public void testInsertResumeChunk() {
        String resumeText = "会计税务交易类别变更，梳理9类变更场景，定义允许变更、终止变更判定条件。开发申请交易登录模块，避免部分登录造成异常状态，保障财务数据链完整性。设计自动化覆盖逻辑与场景化规则，开发月次数据结转批处理流程，支撑财务月结。利用PowerQuery做财务多源数据清洗，DAX函数统一日期口径，PowerBI搭建财务可视化报表。项目优化成果：用户人均失误从5次降到3次，失误率下降30%，运维响应效率提升10%。";

        List<String> chunkTexts = splitText(resumeText, 220, 30);
        for (String text : chunkTexts) {
            RagDocChunk chunk = new RagDocChunk();
            chunk.setKnowledgeId("K001");
            chunk.setChunkText(text);
            List<Double> vec = getEmbedding(text);
            chunk.setEmbedding(JSON.toJSONString(vec));
            chunk.setDelFlag(0);
            this.save(chunk);
        }
    }


    /**
     * RAG混合检索核心方法
     */
    @Override
    public Result<?> queryRag(String knowledgeId, String question) {
        LambdaQueryWrapper<RagDocChunk> allWrapper = new LambdaQueryWrapper<>();
        allWrapper.eq(RagDocChunk::getKnowledgeId, knowledgeId);
        allWrapper.eq(RagDocChunk::getDelFlag, 0);
        List<RagDocChunk> allChunkList = this.list(allWrapper);
        if (CollUtil.isEmpty(allChunkList)) {
            return Result.error("知识库内没有简历分片数据");
        }

        List<Double> queryVector = getEmbedding(question);

        //向量检索打分
        List<ChunkScore> vectorScoreList = new ArrayList<>();
        for (RagDocChunk chunk : allChunkList) {
            List<Double> dbVec = JSON.parseArray(chunk.getEmbedding(), Double.class);
            double score = cosineSimilarity(queryVector, dbVec);
            ChunkScore cs = new ChunkScore();
            cs.setChunk(chunk);
            cs.setScore(score);
            vectorScoreList.add(cs);
        }

        //关键词检索打分
        List<ChunkScore> keywordScoreList = keywordSearch(question, knowledgeId);

        //加权融合 向量0.6 关键词0.4
        Map<String, Double> totalScoreMap = new HashMap<>();
        for (ChunkScore cs : vectorScoreList) {
            totalScoreMap.put(cs.getChunk().getId(), cs.getScore() * 0.6);
        }
        for (ChunkScore cs : keywordScoreList) {
            totalScoreMap.merge(cs.getChunk().getId(), cs.getScore() * 0.4, Double::sum);
        }

        //取top3
        List<RagDocChunk> top3Chunks = totalScoreMap.entrySet().stream()
                .sorted((o1, o2) -> Double.compare(o2.getValue(), o1.getValue()))
                .limit(3)
                .map(entry -> allChunkList.stream()
                        .filter(c -> c.getId().equals(entry.getKey()))
                        .findFirst().orElse(null))
                .filter(Objects::nonNull)
                .collect(Collectors.toList());

        StringBuilder contextBuilder = new StringBuilder();
        for (RagDocChunk chunk : top3Chunks) {
            contextBuilder.append(chunk.getChunkText()).append("\n");
        }

        String promptTemplate = """
你是高级技术面试官，只能使用下面【简历参考材料】回答用户的问题。
硬性规则：
1. 严禁编造简历不存在业务、数字、技术点；
2. 尽量挖掘业务细节：变更场景、校验逻辑、批处理流程、PowerQuery/DAX技术、量化优化成果；
3. 如果材料没有相关信息，如实告知，不要脑补。



【简历参考材料】
%s



【用户提问】
%s
""";
        String finalPrompt = String.format(promptTemplate, contextBuilder, question);

        //占位方法，后续对接真实大模型替换这里
        String answer = callLlm(finalPrompt);
        return Result.OK(answer);
    }


    /**
     * 占位：对接大模型，现在只返回prompt文本
     */
    private String callLlm(String prompt) {
        return "【待接入大模型】\n" + prompt;
    }


    //====================新增：原生Mapper插入实现，增加事务注解解决jeecg隐式回滚====================
    @Override
    @Transactional(propagation = Propagation.NOT_SUPPORTED)
    public void insertDirect(RagDocChunk chunk) {
        int rows = ragDocChunkMapper.insertDirect(chunk);
        log.info("【原生Mapper插入】影响行数：{}", rows);
        if (rows != 1) {
            throw new RuntimeException("原生SQL插入失败，影响行数=" + rows);
        }
    }

}
