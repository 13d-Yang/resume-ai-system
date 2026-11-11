<template>
  <div class="resume-page p-4" style="font-family: 'Microsoft YaHei', sans-serif">
    <!-- 顶部统计卡片 -->
    <!-- 👇 只改了这里的布局，实现均匀分布、间距一致 -->
    <div class="flex flex-wrap gap-4 mb-4">
      <template v-for="(item, index) in resumeCardList" :key="item.title">
        <Card size="small" :title="item.title" class="flex-1 min-w-[200px]">
          <template #extra>
            <Tag :color="item.color">{{ item.tagText }}</Tag>
          </template>
          <div class="py-4 px-4 flex justify-between items-center">
            <CountTo :startVal="0" :endVal="item.value" class="text-2xl font-bold" style="font-family: 'Segoe UI', sans-serif" />
            <Icon :icon="item.icon || 'ion:document-text-outline'" :size="40" />
          </div>
          <div class="p-2 px-4 flex justify-between text-gray-500 text-sm">
            <span>共 {{ item.total }} 份简历</span>
            <span>{{ item.percent }}%</span>
          </div>
        </Card>
      </template>
    </div>
    <!-- 图表 + AI 面板 -->
    <div style="display: flex; gap: 16px; margin-bottom: 16px">
      <div style="flex: 7; background: #fff; padding: 16px; border-radius: 8px">
        <div style="font-size: 16px; font-weight: bold; margin-bottom: 16px">AI 简历能力评估雷达图</div>
        <div ref="radarChartRef" style="width: 100%; height: 260px"></div>
        <div v-if="radarData" style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #eee">
          <p><strong>综合评分：</strong> {{ radarData.totalScore }} / 100</p>
          <p><strong>优势：</strong> {{ radarData.advantage }}</p>
        </div>
        <div v-else style="height: 260px; display: flex; align-items: center; justify-content: center; color: #999">
          点击表格一行简历，自动生成AI能力雷达图
        </div>
      </div>
      <div style="flex: 3; background: #fff; padding: 16px; border-radius: 8px">
        <div style="font-size: 16px; font-weight: bold; margin-bottom: 16px">AI 快捷操作</div>
        <div style="height: 380px; background: #fafafa; padding: 16px; border-radius: 8px; display: flex; flex-direction: column; gap: 12px">
          <div style="font-size: 13px; color: #666">当前文件：{{ currentResumeName || '未选择简历' }}</div>
          <!-- ========== 已删除红圈的a-textarea输入框 ========== -->
          <a-button type="primary" block size="large" @click="handleBatchAnalysis" :loading="aiLoading"> 📄 AI 完整简历分析 </a-button>
          <!-- 新增生成雷达图按钮 -->
          <a-button type="primary" block size="large" @click="generateRadarChart" :loading="radarLoading"> 📊 生成能力雷达图 </a-button>
          <a-button block size="large" @click="aiGenerateQuestions" :loading="qLoading"> 📝 生成面试题 </a-button>
          <a-button block size="large" @click="aiOptimizeResume"> ✨ 简历优化建议 </a-button>
          <a-button block size="large" @click="aiCheckRisk"> ⚠️ 风险筛查 </a-button>
          <a-button type="primary" ghost block size="large" @click="openChatModal"> 💬 简历问答（RAG） </a-button>
        </div>
      </div>
    </div>
    <!-- 🔥 人才库语义搜索：给一段JD，从全部已入库简历中语义检索最匹配的候选人 -->
    <a-card title="🔍 人才库语义搜索（按 JD 全库找人）" :bordered="false" style="margin-bottom: 16px">
      <a-textarea
        v-model:value="talentJD"
        :rows="3"
        placeholder="粘贴岗位要求（JD），例如：AI应用开发工程师，要求熟练Python，有RAG向量检索、大模型LLM应用、LangGraph工作流开发经验"
      />
      <div style="margin-top: 10px; display: flex; align-items: center; gap: 12px">
        <a-button type="primary" size="large" @click="searchCandidates" :loading="talentLoading">
          🔎 全库搜索候选人
        </a-button>
        <span style="color: #999; font-size: 12px">基于向量语义匹配，无需逐份打开简历；返回 Top5 综合匹配排名</span>
      </div>
      <a-empty v-if="talentSearched && talentCandidates.length === 0" description="没有匹配的简历（全部低于相似度阈值）" style="margin-top: 16px" />
      <a-table
        v-if="talentCandidates.length > 0"
        :columns="talentColumns"
        :data-source="talentCandidates"
        :pagination="false"
        size="small"
        row-key="knowledge_id"
        style="margin-top: 16px"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'rank'">
            <span :style="{ fontWeight: 700, color: record.rank <= 3 ? '#fa8c16' : '#999' }">#{{ record.rank }}</span>
          </template>
          <template v-else-if="column.key === 'score'">
            <a-progress
              :percent="Math.round(record.score * 100)"
              size="small"
              :stroke-color="scoreColor(record.score)"
              style="width: 160px"
            />
            <span style="margin-left: 8px; font-weight: 600">{{ record.score }}</span>
          </template>
          <template v-else-if="column.key === 'match_level'">
            <a-tag :color="levelColor(record.match_level)">{{ record.match_level }}</a-tag>
          </template>
        </template>
      </a-table>
    </a-card>
    <!-- 简历列表 -->
    <a-card title="简历列表" :bordered="false" style="margin-bottom: 16px">
      <template #extra>
        <a-button type="primary" danger style="margin-right: 8px" @click="handleBatchDelete" :disabled="selectedRowKeys.length === 0">
          批量删除
        </a-button>
        <a-button type="primary" style="margin-right: 8px" @click="selectSingleResume"> 选择简历测试数据文件 </a-button>
        <a-button type="primary" @click="handleCompareResumes" :disabled="selectedRowKeys.length < 2"> 简历对比（选2份以上） </a-button>
      </template>
      <a-table
        :columns="columns"
        :data-source="resumeList"
        row-key="id"
        :pagination="pagination"
        @change="handleTableChange"
        :row-selection="rowSelection"
        @row-click="handleRowClick"
      >
        <template #bodyCell="{ column, record, index }">
          <template v-if="column.key === 'rowIndex'">
            {{ (pagination.current - 1) * pagination.pageSize + index + 1 }}
          </template>
          <template v-if="column.key === 'action'">
            <div style="display: flex; justify-content: flex-start; gap: 12px; padding-left: 4px">
              <a-button type="link" size="small" @click="openResume(record)">下载</a-button>
              <a-button type="link" size="small" @click="openEdit(record)">编辑</a-button>
              <a-button type="link" size="small" @click="openMatchModal(record)">简历匹配度查看</a-button>
            </div>
          </template>
        </template>
      </a-table>
    </a-card>
    <!-- 编辑状态弹窗 -->
    <a-modal v-model:open="editVisible" title="修改简历状态" width="500px" @ok="handleSaveEdit" @cancel="editVisible = false">
      <a-form layout="vertical" class="mt-4">
        <a-form-item label="简历名称">
          <a-input v-model:value="editForm.resumeName" disabled />
        </a-form-item>
        <a-form-item label="选择状态">
          <a-select v-model:value="editForm.status" placeholder="请选择简历状态" style="width: 100%">
            <a-select-option :value="1">面试中</a-select-option>
            <a-select-option :value="2">待筛选</a-select-option>
            <a-select-option :value="3">已录用</a-select-option>
            <a-select-option :value="4">已拒绝</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>
    <!-- 🔥 简历匹配度弹窗（输入岗位要求） -->
    <a-modal v-model:open="matchVisible" title="简历匹配度分析" width="600px" @cancel="matchVisible = false">
      <a-form layout="vertical">
        <a-form-item label="当前简历">
          <a-input :value="matchResumeName" disabled />
        </a-form-item>
        <a-form-item label="请输入岗位要求（JD）">
          <a-textarea v-model:value="matchJD" :rows="5" placeholder="例如：3年Python开发经验、本科及以上学历、熟悉FastAPI/LangChain、有AI项目经验" />
        </a-form-item>
      </a-form>
      <template #footer>
        <a-button @click="matchVisible = false">取消</a-button>
        <a-button type="primary" @click="getResumeMatchScore" :loading="matchLoading"> 开始AI匹配分析 </a-button>
      </template>
    </a-modal>
    <!-- 🔥 简历 RAG 问答弹窗：基于向量检索 + GLM 生成，答案带引用来源 -->
    <a-modal
      v-model:open="chatVisible"
      :footer="null"
      :maskClosable="false"
      :keyboard="false"
      width="720px"
      wrapClassName="resume-chat-modal"
      :bodyStyle="{ padding: '0' }"
      @cancel="chatVisible = false"
    >
      <template #title>
        <div class="rc-title">
          <div class="rc-title-icon">✦</div>
          <div>
            <div class="rc-title-main">简历智能问答</div>
            <div class="rc-title-sub">Resume Intelligence · 基于简历全文的 AI 分析</div>
          </div>
        </div>
      </template>
      <!-- 当前简历信息条 -->
      <div class="rc-context">
        <span class="rc-context-label">当前简历</span>
        <span class="rc-context-name">{{ chatResumeName }}</span>
        <span class="rc-context-hint">仅依据该简历作答，不编造未提及信息</span>
      </div>
      <!-- 对话记录 -->
      <div class="rc-body">
        <div v-if="chatMessages.length === 0" class="rc-empty">
          <div class="rc-empty-icon">💬</div>
          <div class="rc-empty-title">和 AI 聊聊这份简历</div>
          <div class="rc-empty-sub">试试这些问题</div>
          <div class="rc-empty-chips">
            <span v-for="q in chatSuggestions" :key="q" class="rc-chip" @click="quickAsk(q)">{{ q }}</span>
          </div>
        </div>
        <!-- 一问一答合并为同一张卡片，不左右分开 -->
        <div v-for="(msg, i) in chatMessages" :key="i" class="rc-card">
          <div class="rc-card-q">
            <span class="rc-q-badge">问</span>
            <div class="rc-q-main">
              <div class="rc-q-text">{{ msg.question }}</div>
              <div v-if="msg.resumeName" class="rc-msg-tag">{{ msg.resumeName }}</div>
            </div>
          </div>
          <div class="rc-card-a">
            <span class="rc-a-badge">AI</span>
            <div class="rc-a-text">{{ msg.answer }}</div>
          </div>
        </div>
        <!-- 生成中：三点跳动 -->
        <div v-if="chatLoading" class="rc-card">
          <div class="rc-card-a">
            <span class="rc-a-badge">AI</span>
            <div class="rc-dots"><span></span><span></span><span></span></div>
          </div>
        </div>
      </div>
      <!-- 输入区 -->
      <div class="rc-inputbar">
        <a-textarea
          v-model:value="chatInput"
          :rows="2"
          :bordered="false"
          placeholder="输入关于这份简历的问题，Enter 发送 / Shift+Enter 换行"
          @keydown.enter.exact.prevent="askResumeChat"
        />
        <div class="rc-actions">
          <a-button type="primary" shape="round" :disabled="chatLoading" @click="askResumeChat">发送</a-button>
          <a-button type="primary" danger shape="round" :disabled="!chatLoading" @click="stopResumeChat">停止</a-button>
        </div>
      </div>
    </a-modal>
    <!-- AI 分析报告 -->
    <a-card title="AI分析报告" style="margin-top: 16px">
      <template #extra>
        <a-button v-if="aiResult" size="small" @click="aiResult = ''">清空结果</a-button>
      </template>
      <div
        v-if="aiResult"
        style="white-space: pre-wrap; font-size: 15px; line-height: 1.9; color: #2c3e50; padding: 12px 16px; background: #f9fafb; border-radius: 8px"
      >
        {{ cleanAiResult }}
      </div>
      <div v-else style="color: #999; text-align: center; padding: 20px">上传简历后显示分析结果</div>
    </a-card>
    <!-- 🔥 简历匹配度结果展示 -->
    <a-card v-if="matchResult" title="简历匹配度评分" style="margin-top: 16px">
      <template #extra>
        <a-button size="small" @click="matchResult = null">清空结果</a-button>
      </template>
      <div style="padding: 16px; line-height: 2">
        <h3 style="margin: 0 0 12px 0">🎯 匹配总分：{{ matchResult.totalScore }} / 100</h3>
        <p>📊 专业匹配度：{{ matchResult.subScore.major }} 分</p>
        <p>🧰 工作经验：{{ matchResult.subScore.exp }} 分</p>
        <p>🔧 技能匹配：{{ matchResult.subScore.skill }} 分</p>
        <p>🌟 综合素养：{{ matchResult.subScore.quality }} 分</p>
        <p :style="{ color: matchResult.suggestStatus === 1 ? '#00b42a' : '#ff4d4f', fontWeight: 600, marginTop: '12px' }">
          最终建议：{{ matchResult.advice }}
        </p>
      </div>
    </a-card>
  </div>
</template>
<script lang="ts" setup>
  import { ref, onMounted, computed, nextTick } from 'vue';
  import { message, Modal } from 'ant-design-vue';
  import { CountTo } from '/@/components/CountTo/index';
  import { Icon } from '/@/components/Icon';
  import { Card, Tag } from 'ant-design-vue';
  import { defHttp } from '@/utils/http/axios';
  import * as echarts from 'echarts';
  // 新增：带超时封装fetch，防止大模型请求卡住
  function fetchWithTimeout(url: string, options: RequestInit, timeout = 90000) {
    return Promise.race([fetch(url, options), new Promise((_, reject) => setTimeout(() => reject(new Error('请求超时')), timeout))]);
  }
  // ===== 新增：Java 后端地址 =====
  const BASE_API = 'http://localhost:8080/jeecg-boot';
  // ===== 新增：动态获取 MCP ID =====
  const mcpId = ref('');
  const fetchMcpId = async () => {
    try {
      const token = localStorage.getItem('token') || localStorage.getItem('X-Access-Token') || '';
      const res = await fetch(`${BASE_API}/sys/mcp/enabled`, {
        headers: { 'X-Access-Token': token }
      });
      const data = await res.json();
      if (data?.result?.length > 0) {
        mcpId.value = data.result[0].id;
        console.log('✅ 自动获取 MCP ID:', mcpId.value);
      } else {
        message.error('没有已启用的 MCP，请先去管理页面启用');
      }
    } catch (e) {
      console.error('获取 MCP ID 失败:', e);
    }
  };
  // 雷达图（纯新增）
  const radarChartRef = ref(null);
  const radarData = ref(null);
  // 新增雷达加载状态
  const radarLoading = ref(false);
  // 🔥 顶部统计卡片：清空假数据，改为响应式空数组
  const resumeCardList = ref<any[]>([]);
  // 数据状态
  const resumeList = ref([]);
  const selectedFile = ref<File | null>(null);
  const selectedResume = ref(null);
  const aiResult = ref('');
  const aiLoading = ref(false);
  const qLoading = ref(false);
  const selectedResumeList = ref([]);
  // 编辑弹窗相关
  const editVisible = ref(false);
  const editForm = ref({
    id: null,
    resumeName: '',
    status: null,
  });
  // 简历匹配度弹窗变量
  const matchVisible = ref(false);
  const matchLoading = ref(false);
  const matchJD = ref('');
  const matchResult = ref(null);
  const matchResumeName = ref('');
  const matchResumePath = ref('');
  const matchKnowledgeId = ref('');
  // 🔥 人才库语义搜索相关状态
  const talentJD = ref('');
  const talentLoading = ref(false);
  const talentCandidates = ref<any[]>([]);
  const talentSearched = ref(false);
  const talentColumns = [
    { title: '排名', dataIndex: 'rank', key: 'rank', width: 70 },
    { title: '简历名称', dataIndex: 'knowledge_name', key: 'knowledge_name' },
    { title: '综合匹配分', dataIndex: 'score', key: 'score', width: 290 },
    { title: '推荐等级', dataIndex: 'match_level', key: 'match_level', width: 110 },
  ];
  // 分数 -> 进度条颜色
  const scoreColor = (s: number) => (s >= 0.6 ? '#52c41a' : s >= 0.5 ? '#faad14' : '#ff4d4f');
  // 等级 -> Tag 颜色
  const levelColor = (level: string) => (level === '强烈推荐' ? 'green' : level === '可以考虑' ? 'orange' : 'default');
  // 🔥 统一清空历史结果：每次点击新操作前调用，保证界面只显示当前操作自己的结果
  const clearAllResults = () => {
    aiResult.value = '';
    matchResult.value = null;
    talentCandidates.value = [];
    talentSearched.value = false;
    radarData.value = null;
    // 销毁雷达图 ECharts 实例，否则旧图会一直残留在画布上
    const dom = radarChartRef.value;
    if (dom) {
      const chartIns = echarts.getInstanceByDom(dom);
      if (chartIns) chartIns.dispose();
    }
  };
  // 🔥 简历 RAG 问答相关状态
  const chatVisible = ref(false);
  const chatLoading = ref(false);
  const chatInput = ref('');
  const chatMessages = ref<any[]>([]);
  // 停止生成：用 AbortController 取消前端等待，让用户可以立即中止长耗时问答
  let chatAbortController: AbortController | null = null;
  let chatAborted = false;
  const stopResumeChat = () => {
    if (!chatAbortController) return;
    chatAborted = true;
    chatAbortController.abort();
  };
  // 空状态下的快捷提问示例，点一下直接发送
  const chatSuggestions = [
    '他有没有大数据相关经验？',
    '最擅长什么技术？',
    '有几年工作经验？',
    '这份简历适合投什么岗位？',
  ];
  const chatResumeName = ref('');
  // 当前问答会话涉及的简历ID：1份=问答，多份=对比
  const chatResumeIds = ref<string[]>([]);
  // 分页
  const pagination = ref({
    current: 1,
    pageSize: 10,
    total: 0,
    showSizeChanger: true,
    showTotal: (total) => `共 ${total} 条`,
  });
  // 表格多选
  const selectedRowKeys = ref<string[]>([]);
  const rowSelection = {
    selectedRowKeys: selectedRowKeys,
    onChange: (keys, rows) => {
      selectedRowKeys.value = keys;
      selectedResumeList.value = rows;
      if (rows.length > 0) {
        selectedResume.value = rows[0];
      }
    },
  };
  // 表格列
  const columns = ref([
    { title: '序号', dataIndex: 'rowIndex', key: 'rowIndex', width: 70, align: 'center' },
    { title: '简历名', dataIndex: 'resumeName', key: 'resumeName', width: 280 },
    {
      title: '状态',
      dataIndex: 'statusName',
      key: 'statusName',
      width: 110,
      align: 'left',
    },
    { title: '创建时间', dataIndex: 'createTime', key: 'createTime', width: 230 },
    {
      title: '操作',
      key: 'action',
      width: 260,
      align: 'left',
      customHeaderCell: () => {
        return {
          style: {
            paddingLeft: '25px',
          },
        };
      },
    },
  ]);
  // 显示当前选中文件名称
  const currentResumeName = computed(() => {
    if (selectedFile.value) return selectedFile.value.name;
    if (selectedResume.value) return selectedResume.value.resumeName;
    return '未选择简历';
  });
  // 🔥 优化：清洗AI输出多余符号
  const cleanAiResult = computed(() => {
    if (!aiResult.value) return '';
    let text = aiResult.value;
    text = text.replace(/^#{1,6}\s*/gm, '');
    text = text.replace(/\*\*/g, '');
    text = text.replace(/\|/g, '');
    text = text.replace(/---+/g, '');
    text = text.replace(/<br\s*\/?>/gi, '\n');
    text = text.replace(/<\/?(li|ul|ol)\s*\/?>/gi, '');
    text = text.replace(/\n\s*\n+/g, '\n\n').trim();
    return text;
  });
  // 修改：增加入参 knowledgeId
  const getResumeText = async (filePath: string, knowledgeId: string): Promise<string> => {
    if (!mcpId.value) {
      message.error('MCP 未就绪，请刷新页面');
      return '';
    }
    const token = localStorage.getItem('token') || localStorage.getItem('X-Access-Token') || '';
    const res = await fetch(`${BASE_API}/sys/mcp/call_tool?mcp_id=${mcpId.value}&tool_name=read_resume`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Access-Token': token },
      body: JSON.stringify({
        path: filePath,
        knowledge_id: knowledgeId // ✅ 使用传入的ID，不再写死
      }),
    });
    const data = await res.json();
    if (data.success) return data.result;
    throw new Error(data.message || '解析简历失败');
  };
  // 🔥 核心：加载数据库真实统计数据（总简历/待筛选/面试中/已录用）
  const loadResumeStats = async () => {
    try {
      const res = await defHttp.get({ url: '/resume/getResumeStats' });
      const stats = res;
      const total = stats.totalAll || 1;
      const getPercent = (num: number) => Math.round((num / total) * 100);
      resumeCardList.value = [
        {
          title: '总简历数',
          value: stats.totalAll,
          total: stats.totalAll,
          percent: 100,
          color: 'blue',
          tagText: '全部',
          icon: 'ion:document-text-outline',
        },
        {
          title: '待筛选',
          value: stats.waitFilter,
          total: stats.totalAll,
          percent: getPercent(stats.waitFilter),
          color: 'orange',
          tagText: '待处理',
          icon: 'ion:hourglass-outline',
        },
        {
          title: '面试中',
          value: stats.interviewing,
          total: stats.totalAll,
          percent: getPercent(stats.interviewing),
          color: 'cyan',
          tagText: '进行中',
          icon: 'ion:people-outline',
        },
        {
          title: '已录用',
          value: stats.employed,
          total: stats.totalAll,
          percent: getPercent(stats.employed),
          color: 'green',
          tagText: '已完成',
          icon: 'ion:checkmark-circle-outline',
        },
        {
          title: '已拒绝',
          value: stats.rejected,
          total: stats.totalAll,
          percent: getPercent(stats.rejected),
          color: 'red',
          tagText: '已淘汰',
          icon: 'ion:close-circle-outline',
        },
      ];
    } catch (e) {
      console.error('加载统计失败', e);
      message.error('统计数据加载失败');
      resumeCardList.value = [
        { title: '总简历数', value: 0, total: 0, percent: 100, color: 'blue', tagText: '全部', icon: 'ion:document-text-outline' },
        { title: '待筛选', value: 0, total: 0, percent: 0, color: 'orange', tagText: '待处理', icon: 'ion:hourglass-outline' },
        { title: '面试中', value: 0, total: 0, percent: 0, color: 'cyan', tagText: '进行中', icon: 'ion:people-outline' },
        { title: '已录用', value: 0, total: 0, percent: 0, color: 'green', tagText: '已完成', icon: 'ion:checkmark-circle-outline' },
        { title: '已拒绝', value: 0, total: 0, percent: 0, color: 'red', tagText: '已淘汰', icon: 'ion:close-circle-outline' },
      ];
    }
  };
  // 加载数据库简历列表
  const loadResumeList = async () => {
    try {
      const res = await defHttp.get({
        url: '/resume/list',
        params: { pageNo: pagination.value.current, pageSize: pagination.value.pageSize },
      });
      resumeList.value = res.records;
      pagination.value.total = res.total;
    } catch (e) {
      message.error('加载列表失败');
    }
  };
  /// 通用上传
  const beforeUpload = async (file: File) => {
    selectedFile.value = file;
    selectedResume.value = null;
    const loading = message.loading('上传中...', 0);
    try {
      await defHttp.uploadFile({ url: '/resume/upload' }, { file, name: 'file' });
      loading();
      message.success('上传成功');
      await loadResumeList();
      await loadResumeStats();
    } catch (err) {
      loading();
      message.error('上传失败');
      selectedFile.value = null;
    }
    return false;
  };
  // 选择本地文件上传
  const selectSingleResume = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.pdf,.doc,.docx';
    input.onchange = async (e: Event) => {
      const target = e.target as HTMLInputElement;
      const file = target.files?.[0];
      if (!file) return;
      selectedFile.value = file;
      selectedResume.value = null;
      const loading = message.loading('上传中...', 0);
      try {
        await defHttp.uploadFile({ url: '/resume/upload' }, { file, name: 'file' });
        loading();
        message.success(`文件【${file.name}】上传并入库成功`);
        await loadResumeList();
        await loadResumeStats();
      } catch (err) {
        loading();
        message.error('上传入库失败');
        selectedFile.value = null;
      }
    };
    input.click();
  };
  // 获取简历文件
  const getResumeFile = async () => {
    if (selectedFile.value) {
      return selectedFile.value;
    }
    if (selectedResume.value) {
      try {
        const token = localStorage.getItem('token') || '';
        const res = await fetch(`/jeecg-boot/common/download?file=${selectedResume.value.resumePath}`, {
          headers: {
            Authorization: 'Bearer ' + token,
            'Cache-Control': 'no-cache',
            Pragma: 'no-cache',
          },
          cache: 'no-cache',
        });
        if (!res.ok) {
          message.error('文件下载异常');
          return null;
        }
        const blob = await res.blob();
        if (blob.size < 1000) {
          message.error('原简历附件已丢失，请点击【编辑】重新上传文件');
          return null;
        }
        let fileName = selectedResume.value.resumeName;
        const lastDot = fileName.lastIndexOf('.');
        if (lastDot === -1 || lastDot === 0 || lastDot === fileName.length - 1) {
          fileName += '.pdf';
        }
        let type = 'application/octet-stream';
        if (fileName.endsWith('.pdf')) type = 'application/pdf';
        if (fileName.endsWith('.docx')) type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
        if (fileName.endsWith('.doc')) type = 'application/msword';
        return new File([blob], fileName, { type: type });
      } catch (e) {
        message.error('文件读取失败');
        return null;
      }
    }
    message.warning('请选择简历');
    return null;
  };
  // ===== AI完整简历分析（改走动态 mcpId）=====
  const handleBatchAnalysis = async () => {
    if (!mcpId.value) {
      message.error('MCP 未就绪，请刷新页面');
      return;
    }
    if (selectedResume.value && selectedResume.value.resumePath) {
      aiLoading.value = true;
      clearAllResults();
      const loadingMsg = message.loading('AI 分析中...', 0);
      try {
        // ✅ 传入knowledgeId
        const resumeText = await getResumeText(selectedResume.value.resumePath, selectedResume.value.knowledgeId);
        const token = localStorage.getItem('token') || localStorage.getItem('X-Access-Token') || '';
        const response = await fetch(`${BASE_API}/sys/mcp/call_tool?mcp_id=${mcpId.value}&tool_name=run_agent_chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-Access-Token': token },
          body: JSON.stringify({ input_text: resumeText }),
        });
        const data = await response.json();
        if (data.success) {
          aiResult.value = data.result || '暂无分析结果';
          message.success('分析完成');
        } else {
          message.error(data.message || '分析失败');
        }
      } catch (err) {
        message.error('AI请求失败：' + err.message);
        console.error(err);
      } finally {
        loadingMsg();
        aiLoading.value = false;
      }
      return;
    }
    if (selectedFile.value) {
      aiLoading.value = true;
      clearAllResults();
      const loadingMsg = message.loading('AI 分析中...', 0);
      try {
        const formData = new FormData();
        formData.append('file', selectedFile.value);
        const uploadRes = await defHttp.uploadFile({ url: '/resume/upload' }, { file: selectedFile.value, name: 'file' });
        const filePath = uploadRes?.result || uploadRes?.data || selectedFile.value.name;
        // 上传新文件场景，后端上传接口已经生成knowledgeId并返回
        const newKnowledgeId = uploadRes?.knowledgeId;
        const resumeText = await getResumeText(filePath, newKnowledgeId);
        const token = localStorage.getItem('token') || localStorage.getItem('X-Access-Token') || '';
        const response = await fetch(`${BASE_API}/sys/mcp/call_tool?mcp_id=${mcpId.value}&tool_name=run_agent_chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-Access-Token': token },
          body: JSON.stringify({ input_text: resumeText }),
        });
        const data = await response.json();
        if (data.success) {
          aiResult.value = data.result || '暂无分析结果';
          message.success('分析完成');
        } else {
          message.error(data.message || '分析失败');
        }
      } catch (err) {
        message.error('AI请求失败：' + err.message);
        console.error(err);
      } finally {
        loadingMsg();
        aiLoading.value = false;
      }
      return;
    }
    message.warning('请先选择一份简历');
  };
  // ===== 生成面试题（改走动态 mcpId）=====
  const aiGenerateQuestions = async () => {
    if (!mcpId.value) {
      message.error('MCP 未就绪，请刷新页面');
      return;
    }
    if (!selectedResume.value) {
      message.warning('请选择简历');
      return;
    }
    qLoading.value = true;
    clearAllResults();
    const loadingMsg = message.loading('生成面试题中...', 0);
    try {
      // ✅ 传入knowledgeId
      const resumeText = await getResumeText(selectedResume.value.resumePath, selectedResume.value.knowledgeId);
      const token = localStorage.getItem('token') || localStorage.getItem('X-Access-Token') || '';
      const response = await fetch(`${BASE_API}/sys/mcp/call_tool?mcp_id=${mcpId.value}&tool_name=gen_interview_question`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Access-Token': token },
        body: JSON.stringify({ resume_text: resumeText }),
      });
      const data = await response.json();
      if (data.success) {
        aiResult.value = data.result || '暂无内容';
        message.success('面试题生成完成');
      } else {
        message.error(data.message || '调用失败');
      }
    } catch (err) {
      message.error('生成失败');
      console.error(err);
    } finally {
      loadingMsg();
      qLoading.value = false;
    }
  };
  // ===== 简历优化（改走动态 mcpId）=====
  const aiOptimizeResume = async () => {
    if (!mcpId.value) {
      message.error('MCP 未就绪，请刷新页面');
      return;
    }
    if (!selectedResume.value) {
      message.warning('请选择简历');
      return;
    }
    clearAllResults();
    const loadingMsg = message.loading('生成优化建议中...', 0);
    try {
      // ✅ 传入knowledgeId
      const resumeText = await getResumeText(selectedResume.value.resumePath, selectedResume.value.knowledgeId);
      const token = localStorage.getItem('token') || localStorage.getItem('X-Access-Token') || '';
      const response = await fetch(`${BASE_API}/sys/mcp/call_tool?mcp_id=${mcpId.value}&tool_name=resume_optimize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Access-Token': token },
        body: JSON.stringify({ resume_text: resumeText }),
      });
      const data = await response.json();
      if (data.success) {
        aiResult.value = data.result || '暂无内容';
        message.success('优化建议生成完成');
      } else {
        message.error(data.message || '调用失败');
      }
    } catch (err) {
      message.error('请求失败');
      console.error(err);
    } finally {
      loadingMsg();
    }
  };
  // ===== 风险筛查（改走动态 mcpId）=====
  const aiCheckRisk = async () => {
    if (!mcpId.value) {
      message.error('MCP 未就绪，请刷新页面');
      return;
    }
    if (!selectedResume.value) {
      message.warning('请选择简历');
      return;
    }
    clearAllResults();
    const loadingMsg = message.loading('风险筛查中...', 0);
    try {
      // ✅ 传入knowledgeId
      const resumeText = await getResumeText(selectedResume.value.resumePath, selectedResume.value.knowledgeId);
      const token = localStorage.getItem('token') || localStorage.getItem('X-Access-Token') || '';
      const response = await fetch(`${BASE_API}/sys/mcp/call_tool?mcp_id=${mcpId.value}&tool_name=resume_risk_check`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Access-Token': token },
        body: JSON.stringify({ resume_text: resumeText }),
      });
      const data = await response.json();
      if (data.success) {
        aiResult.value = data.result || '暂无内容';
        message.success('风险筛查完成');
      } else {
        message.error(data.message || '调用失败');
      }
    } catch (err) {
      message.error('筛查失败');
      console.error(err);
    } finally {
      loadingMsg();
    }
  };
  // ===== 简历对比（改走动态 mcpId）=====
  const handleCompareResumes = async () => {
    if (!mcpId.value) {
      message.error('MCP 未就绪，请刷新页面');
      return;
    }
    if (selectedRowKeys.value.length < 2) {
      message.warning('请至少选择2份简历进行对比');
      return;
    }
    const invalid = selectedResumeList.value.filter((item) => !item.resumePath);
    if (invalid.length) {
      message.error(`存在${invalid.length}份无附件的简历，无法对比`);
      return;
    }
    aiLoading.value = true;
    clearAllResults();
    const loadingMsg = message.loading('AI多简历对比分析中...', 0);
    try {
      let combinedText = '';
      const names = selectedResumeList.value.map((i) => i.resumeName).join('、');
      for (const item of selectedResumeList.value) {
        // ✅ 传入knowledgeId
        const text = await getResumeText(item.resumePath, item.knowledgeId);
        combinedText += `\n--- ${item.resumeName} ---\n${text}\n`;
      }
      const token = localStorage.getItem('token') || localStorage.getItem('X-Access-Token') || '';
      const res = await fetch(`${BASE_API}/sys/mcp/call_tool?mcp_id=${mcpId.value}&tool_name=run_agent_chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Access-Token': token },
        body: JSON.stringify({ input_text: `请对比分析以下简历：${combinedText}` }),
      });
      const data = await res.json();
      if (data.success) {
        aiResult.value = data.result;
        message.success('对比分析完成');
      } else {
        aiResult.value = `❌ ${data.message || '对比失败'}`;
        message.error('对比失败');
      }
    } catch (err) {
      console.error('对比请求异常', err);
      aiResult.value = '❌ 网络异常，请检查后端服务';
      message.error('对比失败');
    } finally {
      loadingMsg();
      aiLoading.value = false;
    }
  };
  // 打开匹配度弹窗
  const openMatchModal = (record) => {
    matchResumeName.value = record.resumeName;
    matchResumePath.value = record.resumePath;
    matchKnowledgeId.value = record.knowledgeId;
    matchJD.value = '';
    matchVisible.value = true;
    matchResult.value = null;
  };
  // ===== AI匹配打分（改走动态 mcpId）=====
  const getResumeMatchScore = async () => {
    if (!mcpId.value) {
      message.error('MCP 未就绪，请刷新页面');
      return;
    }
    if (!matchJD.value.trim()) {
      message.warning('请输入岗位要求！');
      return;
    }
    matchLoading.value = true;
    clearAllResults();
    const loadingMsg = message.loading('AI匹配分析中...', 0);
    try {
      // ✅ 传入knowledgeId
      const resumeText = await getResumeText(matchResumePath.value, matchKnowledgeId.value);
      const token = localStorage.getItem('token') || localStorage.getItem('X-Access-Token') || '';
      const response = await fetch(`${BASE_API}/sys/mcp/call_tool?mcp_id=${mcpId.value}&tool_name=run_match`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Access-Token': token },
        body: JSON.stringify({ resume_text: resumeText, jd: matchJD.value }),
      });
      const data = await response.json();
      if (data.success) {
        matchResult.value = typeof data.result === 'string' ? JSON.parse(data.result) : data.result;
        message.success('匹配分析完成！');
        matchVisible.value = false;
      } else {
        message.error(data.message || '匹配失败');
      }
    } catch (err) {
      message.error('匹配请求失败，请检查后端服务！');
      console.error(err);
    } finally {
      loadingMsg();
      matchLoading.value = false;
    }
  };
  // ===== 人才库语义搜索：JD -> 全库简历向量召回排名（走 MCP 工具 rag_search_candidates）=====
  const searchCandidates = async () => {
    if (!mcpId.value) {
      message.error('MCP 未就绪，请刷新页面');
      return;
    }
    if (!talentJD.value.trim()) {
      message.warning('请先输入岗位要求（JD）');
      return;
    }
    talentLoading.value = true;
    clearAllResults();
    const loadingMsg = message.loading('正在全库语义检索候选人...', 0);
    try {
      const token = localStorage.getItem('token') || localStorage.getItem('X-Access-Token') || '';
      const response = await fetch(`${BASE_API}/sys/mcp/call_tool?mcp_id=${mcpId.value}&tool_name=rag_search_candidates`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Access-Token': token },
        body: JSON.stringify({ jd_text: talentJD.value, top_n: 5 }),
      });
      const data = await response.json();
      if (data.success) {
        const result = typeof data.result === 'string' ? JSON.parse(data.result) : data.result;
        if (result?.error) {
          message.error('检索失败：' + result.error);
          return;
        }
        talentCandidates.value = result?.candidates || [];
        talentSearched.value = true;
        if (talentCandidates.value.length > 0) {
          message.success(`找到 ${talentCandidates.value.length} 位候选人`);
        }
      } else {
        message.error(data.message || '人才搜索失败');
      }
    } catch (err) {
      console.error('人才搜索请求失败', err);
      message.error('人才搜索失败，请检查 Java/Python 服务是否启动');
    } finally {
      loadingMsg();
      talentLoading.value = false;
    }
  };
  // ===== 简历 RAG 问答：打开弹窗（支持单份问答 + 多份对比，同一个 Agent）=====
  const openChatModal = () => {
    if (!mcpId.value) {
      message.error('MCP 未就绪，请刷新页面');
      return;
    }
    // 勾选了多份简历时走对比；否则用当前选中的单份
    const picked = selectedResumeList.value.length >= 2 ? selectedResumeList.value : [selectedResume.value].filter(Boolean);
    if (!picked.length) {
      message.warning('请先在表格中勾选简历（对比需勾选 2 份以上）');
      return;
    }
    if (picked.some((r) => !r.knowledgeId)) {
      message.warning('所选简历中存在缺少知识库ID的，请重新上传入库后再问答');
      return;
    }
    chatResumeIds.value = picked.map((r) => r.knowledgeId);
    chatResumeName.value = picked.map((r) => r.resumeName || '未命名简历').join(' / ');
    chatMessages.value = [];
    chatInput.value = '';
    chatVisible.value = true;
    loadChatHistory();
  };
  // 会话标识：Agent 级（跨简历共享上下文记忆）；历史回显再按 resume_id 过滤
  const chatSessionId = computed(() => 'agent_chat');
  // 打开弹窗时加载历史问答
  const loadChatHistory = async () => {
    const sid = chatSessionId.value;
    if (!sid) return;
    const token = localStorage.getItem('token') || localStorage.getItem('X-Access-Token') || '';
    try {
      const response = await fetch(`${BASE_API}/sys/mcp/call_tool?mcp_id=${mcpId.value}&tool_name=get_chat_history`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Access-Token': token },
        // 单份简历按简历过滤回显；多份对比时不过滤（同一次对比的问答属于同一批简历）
        body: JSON.stringify({
          session_id: sid,
          limit: 30,
          knowledge_id: chatResumeIds.value.length === 1 ? chatResumeIds.value[0] : '',
        }),
      });
      const data = await response.json();
      if (data.success) {
        const result = typeof data.result === 'string' ? JSON.parse(data.result) : data.result;
        chatMessages.value = (result?.messages || []).map((m: any) => ({
          question: m.question,
          answer: m.answer || '',
          sources: [],
          expandedIndex: null,
          resumeName: chatResumeName.value,
        }));
      }
    } catch (err) {
      console.error('加载问答历史失败', err);
    }
  };
  // ===== 简历 RAG 问答：调 rag_resume_chat（向量检索 + GLM 生成，完整 RAG）=====
  const askResumeChat = async () => {
    const question = chatInput.value.trim();
    if (!question) {
      message.warning('请输入问题');
      return;
    }
    if (chatLoading.value) return;
    chatLoading.value = true;
    chatAborted = false;
    chatAbortController = new AbortController();
    // 先把用户问题放到对话区，清空输入框
    chatMessages.value.push({ question, answer: '', sources: [], expandedIndex: null, resumeName: chatResumeName.value });
    chatInput.value = '';
    const token = localStorage.getItem('token') || localStorage.getItem('X-Access-Token') || '';
    try {
      const response = await fetch(`${BASE_API}/sys/mcp/call_tool?mcp_id=${mcpId.value}&tool_name=rag_resume_chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Access-Token': token },
        body: JSON.stringify({
          question: question,
          knowledge_id_list: chatResumeIds.value,
          top_k: 3,
          session_id: chatSessionId.value,
        }),
        signal: chatAbortController.signal,
      });
      const data = await response.json();
      const last = chatMessages.value[chatMessages.value.length - 1];
      if (data.success) {
        const result = typeof data.result === 'string' ? JSON.parse(data.result) : data.result;
        last.answer = result?.answer || '（没有返回内容）';
        last.sources = result?.sources || [];
        last.hit = result?.hit;
      } else {
        last.answer = `❌ ${data.message || '问答调用失败'}`;
        message.error(data.message || '问答失败');
      }
    } catch (err) {
      const last = chatMessages.value[chatMessages.value.length - 1];
      if (chatAborted) {
        // 用户主动停止：不算错误，明确告知已中止
        last.answer = '⏹ 已停止生成';
        message.info('已停止生成');
      } else {
        last.answer = '❌ 网络异常，请检查 Java / Python(8604) 服务是否启动';
        console.error('简历问答请求失败', err);
        message.error('问答失败，请检查后端服务');
      }
    } finally {
      chatLoading.value = false;
      chatAbortController = null;
    }
  };
  // 点击示例问题：填入并直接提问
  const quickAsk = (q: string) => {
    if (chatLoading.value) return;
    chatInput.value = q;
    askResumeChat();
  };
  // 批量删除
  const handleBatchDelete = () => {
    if (selectedRowKeys.value.length === 0) {
      message.warning('请选择要删除的数据');
      return;
    }
    const ids = selectedRowKeys.value.join(',');
    Modal.confirm({
      title: '批量删除确认',
      content: `确定删除选中的 ${selectedRowKeys.value.length} 条数据？`,
      onOk: async () => {
        try {
          await defHttp.delete({ url: `/resume/deleteBatch?ids=${ids}` }, { successMessageMode: 'none' });
          message.success('批量删除成功');
          await loadResumeList();
          await loadResumeStats();
          selectedRowKeys.value = [];
          selectedResume.value = null;
          selectedResumeList.value = [];
        } catch (e) {
          message.error('删除失败');
        }
      },
    });
  };
  // 下载简历（带token的fetch方式，裸<a>链会被后端鉴权拦截返回401）
  const openResume = async (record) => {
    if (!record.id) {
      message.warning('简历ID不存在');
      return;
    }
    try {
      const token = localStorage.getItem('token') || localStorage.getItem('X-Access-Token') || '';
      const res = await fetch(`/jeecg-boot/resume/download?id=${record.id}`, {
        headers: { Authorization: 'Bearer ' + token },
      });
      if (!res.ok) {
        message.error('文件下载异常');
        return;
      }
      const blob = await res.blob();
      if (blob.size < 1000) {
        message.error('原简历附件已丢失，请点击【编辑】重新上传文件');
        return;
      }
      // 从存储路径取真实后缀，避免 docx 被错误命名为 pdf
      const ext = (record.resumePath || '').split('.').pop() || 'pdf';
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${record.resumeName}.${ext}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      message.success('简历已开始下载');
    } catch (e) {
      message.error('文件下载失败');
    }
  };
  // 打开编辑弹窗
  const openEdit = (record) => {
    editForm.value = { ...record };
    editVisible.value = true;
  };
  // 保存编辑
  const handleSaveEdit = async () => {
    try {
      await defHttp.put({
        url: '/resume/edit',
        data: editForm.value,
      });
      message.success('状态修改成功！');
      editVisible.value = false;
      loadResumeList();
      loadResumeStats();
    } catch (err) {
      message.error('修改失败');
      console.error(err);
    }
  };
  const handleTableChange = (page) => {
    pagination.value.current = page.current;
    pagination.value.pageSize = page.pageSize;
    loadResumeList();
  };
  const handleRowClick = (record) => {
    selectedResume.value = record;
    selectedRowKeys.value = [record.id];
    selectedResumeList.value = [record];
    loadRadarScore(record);
  };
  // ===== 点击按钮手动生成雷达图（改走动态 mcpId）=====
  const generateRadarChart = async () => {
    if (!mcpId.value) {
      message.error('MCP 未就绪，请刷新页面');
      return;
    }
    if (!selectedResume.value) {
      message.warning('请先在表格选择一份简历');
      return;
    }
    radarLoading.value = true;
    clearAllResults();
    const loadingMsg = message.loading('正在生成能力雷达图...', 0);
    try {
      // ✅ 传入knowledgeId
      const resumeText = await getResumeText(selectedResume.value.resumePath, selectedResume.value.knowledgeId);
      const token = localStorage.getItem('token') || localStorage.getItem('X-Access-Token') || '';
      const res = await fetch(`${BASE_API}/sys/mcp/call_tool?mcp_id=${mcpId.value}&tool_name=run_radar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Access-Token': token },
        body: JSON.stringify({ resume_text: resumeText }),
      });
      const data = await res.json();
      if (!data.success) {
        throw new Error(data.message || 'MCP调用失败');
      }
      const result = typeof data.result === 'string' ? JSON.parse(data.result) : data.result;
      const numArr = result.scoreArr.map((item) => {
        const n = Number(item);
        return isNaN(n) ? 0 : n;
      });
      radarData.value = {
        scoreArr: numArr,
        totalScore: result.totalScore,
        advantage: result.advantage,
        risk: result.risk,
      };
      nextTick(() => {
        renderRadarChart();
      });
      message.success('雷达图生成完成');
    } catch (e) {
      console.error('雷达图请求失败', e);
      message.error(`生成失败：${e.message || '请检查Python服务'}`);
    } finally {
      loadingMsg();
      radarLoading.value = false;
    }
  };
  // ===== 点行自动生成雷达图（改走动态 mcpId）=====
  const loadRadarScore = async (record) => {
    if (!mcpId.value) {
      message.error('MCP 未就绪，请刷新页面');
      return;
    }
    try {
      // ✅ 传入knowledgeId
      const resumeText = await getResumeText(record.resumePath, record.knowledgeId);
      const token = localStorage.getItem('token') || localStorage.getItem('X-Access-Token') || '';
      const res = await fetch(`${BASE_API}/sys/mcp/call_tool?mcp_id=${mcpId.value}&tool_name=run_radar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Access-Token': token },
        body: JSON.stringify({ resume_text: resumeText }),
      });
      const data = await res.json();
      if (!data.success) {
        console.error('MCP调用失败', data.message);
        return;
      }
      const result = typeof data.result === 'string' ? JSON.parse(data.result) : data.result;
      const numArr = result.scoreArr.map((item) => {
        const n = Number(item);
        return isNaN(n) ? 0 : n;
      });
      radarData.value = {
        scoreArr: numArr,
        totalScore: result.totalScore,
        advantage: result.advantage,
        risk: result.risk,
      };
      setTimeout(() => {
        renderRadarChart();
      }, 150);
    } catch (e) {
      console.error('雷达图请求失败', e);
    }
  };
  const renderRadarChart = () => {
    const dom = radarChartRef.value;
    if (!dom || !radarData.value || !radarData.value.scoreArr) return;
    let chartIns = echarts.getInstanceByDom(dom);
    if (chartIns) chartIns.dispose();
    chartIns = echarts.init(dom);
    const realData = [radarData.value.scoreArr];
    const option = {
      tooltip: {
        trigger: 'item',
        formatter: function (params) {
          const indicatorNames = ['工作经验', '学历背景', '技能匹配', '职业稳定性', '项目含金量', '薪资适配'];
          const scoreList = params.data;
          let html = '';
          indicatorNames.forEach((name, index) => {
            html += `${name}：${scoreList[index]}分<br/>`;
          });
          return html;
        },
      },
      radar: {
        radius: '75%',
        splitNumber: 3,
        indicator: [
          { name: '工作经验', max: 100 },
          { name: '学历背景', max: 100 },
          { name: '技能匹配', max: 100 },
          { name: '职业稳定性', max: 100 },
          { name: '项目含金量', max: 100 },
          { name: '薪资适配', max: 100 },
        ],
        splitArea: {
          areaStyle: {
            color: ['#ffffff', '#f7f8fa'],
          },
        },
      },
      series: [
        {
          name: '简历能力',
          type: 'radar',
          data: realData,
          lineStyle: {
            color: '#409EFF',
            width: 2.5,
          },
          areaStyle: {
            color: 'rgba(64, 158, 255, 0.35)',
          },
          symbol: 'circle',
          symbolSize: 7,
          itemStyle: {
            color: '#409EFF',
          },
        },
      ],
    };
    chartIns.setOption(option);
    const resizeHandler = () => chartIns.resize();
    window.removeEventListener('resize', resizeHandler);
    window.addEventListener('resize', resizeHandler);
  };
  // 🔥 页面加载：同时加载列表 + 统计数据 + 自动获取 MCP ID
  onMounted(() => {
    loadResumeList();
    loadResumeStats();
    fetchMcpId();
  });
</script>
<style scoped lang="less">
/* 如果你原来有 style 内容，原样保留在这里 */

/* ===== 简历智能问答弹窗（现代 AI 助手风格）===== */
:global(.resume-chat-modal) {
  .ant-modal-content {
    border-radius: 18px;
    overflow: hidden;
    padding: 0;
    box-shadow: 0 24px 64px rgba(15, 23, 42, 0.18);
  }
  .ant-modal-header {
    margin: 0;
    padding: 18px 24px;
    border-bottom: none;
    background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 52%, #7c3aed 100%);
  }
  .ant-modal-title {
    color: #fff;
  }
  .ant-modal-close {
    color: rgba(255, 255, 255, 0.85);
    inset-inline-end: 16px;
    top: 16px;
  }
  .ant-modal-close:hover {
    color: #fff;
    background: rgba(255, 255, 255, 0.16);
  }
  .ant-modal-body {
    padding: 0;
  }
}

.rc-title {
  display: flex;
  align-items: center;
  gap: 12px;
  .rc-title-icon {
    width: 36px;
    height: 36px;
    border-radius: 11px;
    background: rgba(255, 255, 255, 0.18);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    color: #fff;
    flex-shrink: 0;
  }
  .rc-title-main {
    font-size: 16px;
    font-weight: 600;
    letter-spacing: 0.5px;
    line-height: 1.3;
  }
  .rc-title-sub {
    font-size: 11px;
    color: rgba(255, 255, 255, 0.72);
    letter-spacing: 0.3px;
    margin-top: 2px;
  }
}

.rc-context {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 24px;
  background: #f8fafc;
  border-bottom: 1px solid #eef2f7;
  font-size: 12px;
  .rc-context-label {
    color: #94a3b8;
  }
  .rc-context-name {
    color: #1e40af;
    font-weight: 600;
  }
  .rc-context-hint {
    margin-left: auto;
    color: #a8b3c4;
    font-size: 11px;
  }
}

.rc-body {
  height: 380px;
  overflow-y: auto;
  padding: 18px 20px;
  background: #fff;
  &::-webkit-scrollbar {
    width: 6px;
  }
  &::-webkit-scrollbar-thumb {
    background: #dbe3ec;
    border-radius: 3px;
  }
}

.rc-empty {
  text-align: center;
  padding-top: 74px;
  .rc-empty-icon {
    font-size: 34px;
  }
  .rc-empty-title {
    font-size: 15px;
    font-weight: 600;
    color: #334155;
    margin-top: 10px;
  }
  .rc-empty-sub {
    font-size: 12px;
    color: #94a3b8;
    margin-top: 6px;
  }
  .rc-empty-chips {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 8px;
    margin-top: 14px;
    padding: 0 28px;
  }
}

.rc-chip {
  font-size: 12px;
  color: #2563eb;
  background: #eff6ff;
  border: 1px solid #dbeafe;
  border-radius: 14px;
  padding: 6px 12px;
  cursor: pointer;
  transition: all 0.2s;
  &:hover {
    background: #dbeafe;
    border-color: #93c5fd;
  }
}

/* 一问一答合并为一张卡片 */
.rc-card {
  background: #fff;
  border: 1px solid #eef2f7;
  border-radius: 14px;
  padding: 12px 14px;
  margin-bottom: 12px;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
}

.rc-card-q {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding-bottom: 10px;
  border-bottom: 1px dashed #eef2f7;
}

.rc-q-badge,
.rc-a-badge {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 600;
  border-radius: 7px;
  padding: 2px 7px;
  line-height: 1.6;
}
.rc-q-badge {
  background: #eef2ff;
  color: #4338ca;
}
.rc-a-badge {
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  color: #fff;
}

.rc-q-main {
  flex: 1;
  min-width: 0;
}
.rc-q-text {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}
.rc-msg-tag {
  display: inline-block;
  margin-top: 6px;
  font-size: 11px;
  color: #64748b;
  background: #f1f5f9;
  border-radius: 8px;
  padding: 2px 8px;
  line-height: 1.5;
}

.rc-card-a {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding-top: 10px;
}
.rc-a-text {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: #1f2937;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
}

.rc-dots {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 0;
  span {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #93c5fd;
    animation: rc-bounce 1.2s infinite;
  }
  span:nth-child(2) {
    animation-delay: 0.2s;
  }
  span:nth-child(3) {
    animation-delay: 0.4s;
  }
}
@keyframes rc-bounce {
  0%,
  80%,
  100% {
    transform: translateY(0);
    opacity: 0.5;
  }
  40% {
    transform: translateY(-5px);
    opacity: 1;
  }
}

.rc-inputbar {
  padding: 14px 20px 18px;
  border-top: 1px solid #eef2f7;
  background: #fff;
  :deep(.ant-input) {
    background: #f8fafc;
    border-radius: 10px;
    padding: 10px 12px;
    resize: none;
  }
  .rc-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 10px;
  }
}
</style>
