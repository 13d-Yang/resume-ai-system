<template>
  <BasicDrawer
    v-bind="$attrs"
    @register="registerDrawer"
    :title="title"
    width="90%"
    destroyOnClose
    @ok="handleSubmit"
    :showFooter="showFooter"
  >
    <!-- 上部：基本信息表单 -->
    <BasicForm @register="registerForm" ref="formRef">
      <template #whiteListSlot="{ model, field }">
        <a-textarea
          v-model:value="model[field]"
          :rows="5"
          placeholder="示例：&#10;192.168.1.100&#10;10.0.0.0/8&#10;172.16.*.*"
          :disabled="formDisabled"
        />
        <!-- 标签预览 -->
        <div v-if="model[field]" style="margin-top: 8px">
          <a-tag
            v-for="item in parseWhiteList(model[field])"
            :key="item"
            color="green"
            style="margin-bottom: 4px"
          >
            {{ item }}
          </a-tag>
        </div>
        <!-- 整理按钮 -->
        <div v-if="model[field] && !formDisabled" style="margin-top: 4px; text-align: right">
          <a-button size="small" @click="formatWhiteList(model, field)">整 理</a-button>
        </div>
      </template>
    </BasicForm>

    <!-- 下部：Tabs -->
    <a-tabs v-model:activeKey="activeTab" style="margin-top: 16px">
      <a-tab-pane key="headers" tab="请求头">
        <JVxeTable
          keep-source
          ref="openApiHeader"
          :loading="openApiHeaderTable.loading"
          :columns="openApiHeaderTable.columns"
          :dataSource="openApiHeaderTable.dataSource"
          :height="240"
          :disabled="formDisabled"
          :rowNumber="true"
          :rowSelection="true"
          :toolbar="true"
        />
      </a-tab-pane>

      <a-tab-pane key="params" tab="请求参数">
        <JVxeTable
          keep-source
          ref="openApiParam"
          :loading="openApiParamTable.loading"
          :columns="openApiParamTable.columns"
          :dataSource="openApiParamTable.dataSource"
          :height="240"
          :disabled="formDisabled"
          :rowNumber="true"
          :rowSelection="true"
          :toolbar="true"
        />
      </a-tab-pane>

      <a-tab-pane key="body" tab="请求体">
        <div style="border: 1px solid #d9d9d9; border-radius: 4px; min-height: 300px">
          <CodeEditor v-model:value="bodyContent" mode="application/json" :readonly="formDisabled" />
        </div>
      </a-tab-pane>

      <a-tab-pane key="response" tab="响应配置">
        <div style="margin-bottom: 16px">
          <h4 style="margin-bottom: 8px">响应示例</h4>
          <div style="border: 1px solid #d9d9d9; border-radius: 4px; min-height: 200px">
            <CodeEditor v-model:value="responseExample" mode="application/json" :readonly="formDisabled" />
          </div>
        </div>
        <div>
          <h4 style="margin-bottom: 8px">响应字段说明</h4>
          <JVxeTable
            keep-source
            ref="responseField"
            :loading="responseFieldTable.loading"
            :columns="responseFieldTable.columns"
            :dataSource="responseFieldTable.dataSource"
            :height="240"
            :disabled="formDisabled"
            :rowNumber="true"
            :rowSelection="true"
            :toolbar="true"
          />
        </div>
      </a-tab-pane>
    </a-tabs>
  </BasicDrawer>
</template>

<script lang="ts" setup>
  import { ref, computed, unref, reactive } from 'vue';
  import { BasicDrawer, useDrawerInner } from '/@/components/Drawer';
  import { BasicForm, useForm } from '/@/components/Form/index';
  import { CodeEditor } from '/@/components/CodeEditor';
  import {
    formSchema,
    openApiHeaderJVxeColumns,
    openApiParamJVxeColumns,
    responseFieldJVxeColumns,
  } from '../OpenApi.data';
  import { saveOrUpdate, getGenPath } from '../OpenApi.api';
  import { useMessage } from '/@/hooks/web/useMessage';

  const emit = defineEmits(['register', 'success']);
  const $message = useMessage();
  const isUpdate = ref(true);
  const formDisabled = ref(false);
  const showFooter = ref(true);
  const activeTab = ref('headers');
  const bodyContent = ref('');
  const responseExample = ref('');

  const openApiHeader = ref();
  const openApiParam = ref();
  const responseField = ref();

  const openApiHeaderTable = reactive({
    loading: false,
    dataSource: [] as any[],
    columns: openApiHeaderJVxeColumns,
  });
  const openApiParamTable = reactive({
    loading: false,
    dataSource: [] as any[],
    columns: openApiParamJVxeColumns,
  });
  const responseFieldTable = reactive({
    loading: false,
    dataSource: [] as any[],
    columns: responseFieldJVxeColumns,
  });

  const [registerForm, { setProps, resetFields, setFieldsValue, validate }] = useForm({
    labelWidth: 100,
    schemas: formSchema,
    showActionButtonGroup: false,
    baseColProps: { span: 12 },
  });

  const [registerDrawer, { setDrawerProps, closeDrawer }] = useDrawerInner(async (data) => {
    await reset();
    showFooter.value = !!data?.showFooter;
    setDrawerProps({ confirmLoading: false, showFooter: showFooter.value });
    isUpdate.value = !!data?.isUpdate;
    formDisabled.value = !data?.showFooter;

    if (unref(isUpdate)) {
      await setFieldsValue({
        ...data.record,
      });
      openApiHeaderTable.dataSource = data.record.headersJson ? JSON.parse(data.record.headersJson) : [];
      openApiParamTable.dataSource = data.record.paramsJson ? JSON.parse(data.record.paramsJson) : [];
      bodyContent.value = data.record.body || '';
      responseExample.value = data.record.responseExample || '';
      responseFieldTable.dataSource = data.record.responseFieldsJson ? JSON.parse(data.record.responseFieldsJson) : [];
    } else {
      const requestUrlObj = await getGenPath({});
      await setFieldsValue({
        requestUrl: requestUrlObj.result,
      });
    }
    setProps({ disabled: !data?.showFooter });
  });

  const title = computed(() => (!unref(isUpdate) ? '新增' : !unref(formDisabled) ? '编辑' : '详情'));

  /** 解析白名单文本为条目数组 */
  function parseWhiteList(text: string): string[] {
    if (!text) return [];
    return text
      .split(/[,\n]/)
      .map((s) => s.trim())
      .filter(Boolean);
  }

  /** 整理白名单：去空行、去重、每行一个 */
  function formatWhiteList(model: any, field: string) {
    const items = parseWhiteList(model[field]);
    const unique = [...new Set(items)];
    model[field] = unique.join('\n');
  }

  async function reset() {
    await resetFields();
    activeTab.value = 'headers';
    openApiHeaderTable.dataSource = [];
    openApiParamTable.dataSource = [];
    responseFieldTable.dataSource = [];
    bodyContent.value = '';
    responseExample.value = '';
  }

  async function handleSubmit() {
    try {
      const values = await validate();
      setDrawerProps({ confirmLoading: true });

      // Collect JVxeTable data
      const headerData = await openApiHeader.value?.getTableData();
      const paramData = await openApiParam.value?.getTableData();
      const responseFieldData = await responseField.value?.getTableData();

      const headersJson = headerData?.tableData?.length ? JSON.stringify(headerData.tableData) : null;
      const paramsJson = paramData?.tableData?.length ? JSON.stringify(paramData.tableData) : null;
      const responseFieldsJson = responseFieldData?.tableData?.length ? JSON.stringify(responseFieldData.tableData) : null;

      // Validate body JSON
      if (bodyContent.value) {
        try {
          if (typeof JSON.parse(bodyContent.value) != 'object') {
            $message.createMessage.error('JSON格式化错误,请检查输入数据');
            return;
          }
        } catch (e) {
          $message.createMessage.error('JSON格式化错误,请检查输入数据');
          return;
        }
      }

      // Validate response example JSON
      if (responseExample.value) {
        try {
          JSON.parse(responseExample.value);
        } catch (e) {
          $message.createMessage.error('响应示例JSON格式错误,请检查输入数据');
          return;
        }
      }

      const submitValues = {
        ...values,
        headersJson,
        paramsJson,
        body: bodyContent.value || null,
        responseExample: responseExample.value || null,
        responseFieldsJson,
      };

      await saveOrUpdate(submitValues, isUpdate.value);
      closeDrawer();
      emit('success');
    } finally {
      setDrawerProps({ confirmLoading: false });
    }
  }
</script>

<style lang="less" scoped>
  :deep(.ant-input-number) {
    width: 100%;
  }

  :deep(.ant-calendar-picker) {
    width: 100%;
  }
</style>
