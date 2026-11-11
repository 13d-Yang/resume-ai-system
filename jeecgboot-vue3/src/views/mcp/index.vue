<template>
  <div class="airag-mcp-page p-4">
    <!-- 顶部搜索 -->
    <div class="search-bar flex items-center gap-3 mb-6">
      <a-input placeholder="名称" v-model:value="searchParams.name" style="width: 220px" />
      <a-select placeholder="类型" v-model:value="searchParams.type" style="width: 160px">
        <a-select-option value="">全部</a-select-option>
        <a-select-option value="stdio">STDIO</a-select-option>
        <a-select-option value="sse">SSE</a-select-option>
      </a-select>
      <a-button type="primary" @click="loadList">查询</a-button>
      <a-button @click="resetSearch">重置</a-button>
    </div>

    <!-- 卡片网格 -->
    <div class="card-grid">
      <!-- 新增卡片 -->
      <div class="add-card" @click="openModal()">
        <span class="add-icon">+</span>
        <span class="add-text">新增MCP</span>
      </div>

      <!-- 数据卡片 -->
      <div
        v-for="item in tableData"
        :key="item.id"
        class="mcp-card"
      >
        <div class="card-head">
          <div class="icon-box">
            <span>M</span>
          </div>
          <div class="card-title">{{ item.name }}</div>
        </div>

        <div class="card-tags">
          <a-tag size="small" color="purple">MCP</a-tag>
          <a-tag size="small" :color="item.running ? 'success' : 'default'">
            {{ item.running ? '运行中' : '已停止' }}
          </a-tag>
          <a-tag size="small">{{ item.type.toUpperCase() }}</a-tag>
        </div>

        <div class="tool-count">
          <span class="count-num">{{ JSON.parse(item.metadata || '{"tool_count":0}').tool_count }}</span>
          <span class="count-label">个工具</span>
        </div>

        <div class="card-actions">
          <a-button size="small" :type="item.running ? 'default' : 'primary'" @click="toggleRun(item)">
            {{ item.running ? '停止' : '启动' }}
          </a-button>
          <a-button size="small" @click="openLogModal(item)">日志</a-button>
          <a-button size="small" @click="openModal(item)">编辑</a-button>
          <a-popconfirm title="确定删除？" @confirm="handleDelete(item.id)">
            <a-button size="small" danger>删除</a-button>
          </a-popconfirm>
        </div>
      </div>
    </div>

    <!-- 分页 -->
    <div class="pagination flex justify-end mt-6">
      <a-pagination
        v-model:current="pageNum"
        v-model:page-size="pageSize"
        :total="total"
        @change="loadList"
        show-size-changer
        :page-size-options="['10', '20', '50']"
      />
    </div>

    <!-- 新增/编辑弹窗 -->
    <a-modal v-model:open="modalVisible" title="MCP配置" width="620px" @ok="submitForm">
      <a-form ref="formRef" :model="formData" layout="vertical">
        <a-form-item label="MCP名称" required>
          <a-input v-model:value="formData.name" placeholder="简历解析MCP" />
        </a-form-item>
        <a-form-item label="连接类型" required>
          <a-select v-model:value="formData.type">
            <a-select-option value="stdio">STDIO</a-select-option>
            <a-select-option value="sse">SSE</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="服务地址" required>
          <a-input v-model:value="formData.endpoint" placeholder="C:\xxx\mcp_parser.py" />
        </a-form-item>
        <a-form-item label="状态">
          <a-select v-model:value="formData.status">
            <a-select-option value="enable">启用</a-select-option>
            <a-select-option value="disable">禁用</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="备注">
          <a-textarea v-model:value="formData.descr" :rows="2" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 查看日志弹窗 -->
    <a-modal v-model:open="logModalVisible" title="MCP运行日志" width="800px" :footer="null">
      <div class="log-box">
        <div v-for="(line, idx) in logList" :key="idx">{{ line }}</div>
      </div>
      <!-- ===== 改动④：历史调用记录（就加了这一段）===== -->
      <a-divider style="margin-top: 16px;">历史调用记录</a-divider>
      <div v-if="callHistory.length === 0" style="text-align: center; color: #bbb; padding: 16px; font-size: 13px;">
        暂无调用记录（去简历分析页面点一个 AI 按钮后再回来看）
      </div>
      <div v-else style="max-height: 220px; overflow-y: auto; background: #0d0d0d; padding: 10px; border-radius: 6px; font-family: monospace; font-size: 12px;">
        <div v-for="(item, index) in callHistory" :key="index" style="padding: 4px 0; border-bottom: 1px solid #333; display: flex; gap: 10px; align-items: center;">
          <span style="color: #888; flex-shrink: 0;">{{ item.time }}</span>
          <span :style="{ color: item.success ? '#52c41a' : '#ff4d4f', flexShrink: 0 }">{{ item.success ? '✅' : '❌' }} {{ item.tool }}</span>
          <span style="color: #aaa; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" :title="item.summary">{{ item.summary }}</span>
        </div>
      </div>
      <!-- ============================================ -->
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { message } from 'ant-design-vue';

const pageNum = ref(1);
const pageSize = ref(10);
const total = ref(0);
const tableData = ref([]);
const searchParams = reactive({ name: '', type: '' });

const modalVisible = ref(false);
const logModalVisible = ref(false);
const isEdit = ref(false);
const formRef = ref();
const currentMcp = ref(null);
const logList = ref([]);
// ===== 改动①：就加了这一行 =====
const callHistory = ref([]);
// ==============================

const formData = reactive({
  id: '',
  name: '',
  category: 'mcp',
  type: 'stdio',
  endpoint: '',
  descr: '',
  status: 'enable',
  header: '{}',
  tools: '[]',
  synced: 1,
  metadata: '{"tool_count":0}',
  create_by: 'admin',
  sys_org_code: 'A01',
  tenant_id: '',
});

const PYTHON_HOST = 'http://127.0.0.1:8604';
const BASE_API = 'http://localhost:8080/jeecg-boot';
// 获取token，兼容多种存储位置，打印调试信息
function getToken() {
  const allKeys = [
    'X-Access-Token', 'token', 'Token', 'access_token',
    'jeecg_token', 'auth_token', 'Authorization'
  ];
  for (const key of allKeys) {
    let v = localStorage.getItem(key);
    if (v) return v;
    v = sessionStorage.getItem(key);
    if (v) return v;
  }
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i);
    const v = localStorage.getItem(k);
    if (v && v.length > 20) {
      console.log('找到疑似token，key=', k, 'value=', v.substring(0, 20) + '...');
      return v;
    }
  }
  return null;
}

// ===== 改动②：就加了这一个函数 =====
const refreshCallHistory = () => {
  try {
    const raw = localStorage.getItem('mcp_call_history') || '[]';
    callHistory.value = JSON.parse(raw).slice(-20).reverse();
  } catch (e) {
    callHistory.value = [];
  }
};
// ==================================

const loadList = async () => {
  const token = getToken();
  if (!token) {
    message.error('未获取登录凭证，请重新登录！');
    return;
  }
  try {
    const params = new URLSearchParams({
      pageNum: pageNum.value,
      pageSize: pageSize.value,
      name: searchParams.name,
      type: searchParams.type,
    });
    const res = await fetch(`${BASE_API}/sys/mcp/list?${params}`, {
      headers: {
        'X-Access-Token': token
      }
    });
    const data = await res.json();
    console.log('列表接口返回：', data);

    if (data.success && data.result) {
      tableData.value = (data.result.records || []).map(item => ({
        ...item,
        running: item.status === 'enable'
      }));
      total.value = data.result.total || 0;

      // ========== 新增：把启用中的 MCP ID 存到 localStorage ==========
      const enabled = tableData.value.find(item => item.running);
      if (enabled) {
        localStorage.setItem('mcp_id', enabled.id);
        console.log('已缓存启用中的 MCP ID:', enabled.id);
      }
      // =============================================================

    } else {
      tableData.value = [];
      total.value = 0;
      message.error(data.message || '查询失败');
    }
  } catch (err) {
    console.error('加载列表异常', err);
    message.error('加载失败');
  }
};

// 启动/停止切换
const toggleRun = async (item) => {
  const token = getToken();
  if (!token) {
    message.error('未获取登录凭证，请重新登录！');
    return;
  }
  try {
    const action = item.running ? 'stop' : 'start';
    const formData = new FormData();
    formData.append('id', item.id);

    const res = await fetch(`${BASE_API}/sys/mcp/${action}`, {
      method: 'POST',
      headers: {
        'X-Access-Token': token,
      },
      body: formData,
    });

    const result = await res.json();
    if (result.success) {
      message.success(item.running ? '已停止' : '已启动');

      // ===== 新增的 6 行，其他一行没动 =====
      if (!item.running) {
        // 启动成功 → 把这条的 ID 存进 localStorage
        localStorage.setItem('mcp_id', item.id);
        console.log('启动成功，已切换 MCP ID 为:', item.id);
      } else {
        // 停止 → 清除缓存
        localStorage.removeItem('mcp_id');
        console.log('已停止，清除 MCP ID 缓存');
      }
      // ====================================

      setTimeout(() => loadList(), 200);
    } else {
      message.error(result.message || '操作失败');
    }
  } catch (err) {
    console.error('启停错误：', err);
    message.error('操作失败');
  }
};

const resetSearch = () => {
  searchParams.name = '';
  searchParams.type = '';
  pageNum.value = 1;
  loadList();
};

// ========== 新增：打开日志弹窗（就加了这一个函数）==========
const openLogModal = (item) => {
  currentMcp.value = item;
  logList.value = [
    '========== MCP 运行信息 ==========',
    '名称: ' + item.name,
    'ID: ' + item.id,
    '状态: ' + (item.running ? '运行中' : '已停止'),
    '类型: ' + item.type,
    '服务地址: ' + (item.endpoint || '未配置'),
    '工具数量: ' + JSON.parse(item.metadata || '{"tool_count":0}').tool_count,
    '',
    '【提示】实时运行日志请查看：',
    '  • Java 后端：IDEA 控制台（Run 窗口）看 【DEBUG】开头的行',
    '  • Python MCP：终端里 python mcp_parser.py 的输出',
    '  • Java 日志文件：logs/jeecg-boot.log',
    '',
    '========== 调试信息 ==========',
    'localStorage mcp_id: ' + (localStorage.getItem('mcp_id') || '（空）'),
  ];
  logModalVisible.value = true;
  // ===== 改动③：就加了这一行 =====
  refreshCallHistory();
  // ==================================
};
// ======================================================

const openModal = (record) => {
  formRef.value?.clearValidate();
  if (record) {
    isEdit.value = true;
    Object.assign(formData, record);
  } else {
    isEdit.value = false;
    Object.assign(formData, {
      id: '',
      name: '',
      type: 'stdio',
      endpoint: '',
      descr: '',
      status: 'enable',
      header: '{}',
      tools: '[]',
      metadata: '{"tool_count":0}',
    });
  }
  modalVisible.value = true;
};

// 提交表单
const submitForm = async () => {
  const token = getToken();
  if (!token) {
    message.error('未获取登录凭证，请重新登录！');
    return;
  }
  try {
    const url = isEdit.value ? `${BASE_API}/sys/mcp/edit` : `${BASE_API}/sys/mcp/add`;
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Access-Token': token
      },
      body: JSON.stringify(formData),
    });
    const result = await res.json();
    console.log('保存接口返回：', result);
    if (result.success) {
      message.success('保存成功');
      modalVisible.value = false;
      loadList();
    } else {
      message.error(result.message || '保存失败');
    }
  } catch (err) {
    console.error(err);
    message.error('保存失败');
  }
};

// 删除
const handleDelete = async (id) => {
  const token = getToken();
  if (!token) {
    message.error('未获取登录凭证，请重新登录！');
    return;
  }
  try {
    const res = await fetch(`${BASE_API}/sys/mcp/delete/${id}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        'X-Access-Token': token
      }
    });
    const data = await res.json();
    console.log('删除返回：', data);
    if (data.success) {
      message.success('删除成功');
      loadList();
    } else {
      message.error(data.message || '后端返回删除失败');
    }
  } catch (err) {
    message.error('删除请求异常');
    console.error(err);
  }
};

onMounted(() => loadList());
</script>

<style scoped lang="less">
.airag-mcp-page {
  background: #f5f7fa;
  min-height: calc(100vh - 120px);
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 20px;
}

.add-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 220px;
  border: 2px dashed #d9d9d9;
  border-radius: 12px;
  background: #fff;
  cursor: pointer;
  transition: all 0.25s ease;

  &:hover {
    border-color: #1677ff;
    background: #f0f7ff;
    transform: translateY(-2px);
  }

  .add-icon {
    font-size: 36px;
    color: #bfbfbf;
    line-height: 1;
    transition: color 0.25s ease;
  }

  .add-text {
    color: #8c8c8c;
    margin-top: 10px;
    font-size: 14px;
    transition: color 0.25s ease;
  }

  &:hover .add-icon,
  &:hover .add-text {
    color: #1677ff;
  }
}

.mcp-card {
  background: #fff;
  border-radius: 12px;
  padding: 18px;
  height: 220px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: all 0.25s ease;
  cursor: default;

  &:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  }

  .card-head {
    display: flex;
    align-items: center;
    gap: 10px;

    .icon-box {
      width: 36px;
      height: 36px;
      border-radius: 8px;
      background: linear-gradient(135deg, #722ed1, #1677ff);
      color: #fff;
      font-weight: bold;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 14px;
    }

    .card-title {
      font-weight: 600;
      font-size: 15px;
      color: #1f2937;
    }
  }

  .card-tags {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-top: 6px;
  }

  .tool-count {
    margin-top: 8px;
    display: flex;
    align-items: baseline;
    gap: 4px;

    .count-num {
      font-size: 24px;
      font-weight: 700;
      color: #1677ff;
      line-height: 1;
    }

    .count-label {
      color: #6b7280;
      font-size: 13px;
    }
  }

  .card-actions {
    display: flex;
    justify-content: space-between;
    width: 100%;
    margin-top: 10px;
    padding-top: 12px;
    border-top: 1px solid #f0f0f0;

    :deep(.ant-btn) {
      flex: 1;
      margin: 0 3px;
    }

    :deep(.ant-btn:first-child) {
      margin-left: 0;
    }

    :deep(.ant-btn:last-child) {
      margin-right: 0;
    }
  }
}

.log-box {
  padding: 16px;
  background: #1e1e1e;
  color: #4ade80;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  height: 500px;
  overflow-y: auto;
  border-radius: 8px;
  line-height: 1.7;
  white-space: pre-wrap;
}

@media screen and (max-width: 1400px) {
  .card-grid {
    grid-template-columns: repeat(4, 1fr);
  }
}

@media screen and (max-width: 1100px) {
  .card-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}
</style>