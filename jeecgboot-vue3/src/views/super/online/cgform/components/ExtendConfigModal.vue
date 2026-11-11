<template>
  <ConfigProvider :theme="{ token: { fontSize: 13 } }">
    <BasicModal @register="registerModal" title="表单扩展配置项" :width="1000" @ok="handleOk" @cancel="handleCancel">
      <BasicForm @register="registerForm" />
    </BasicModal>
  </ConfigProvider>
</template>

<script lang="ts">
  import { ConfigProvider } from 'ant-design-vue';
  import { nextTick, defineComponent } from 'vue';
  import { BasicModal, useModalInner } from '/@/components/Modal';
  import { BasicForm, useForm } from '/@/components/Form';
  import { useMessage } from '/@/hooks/web/useMessage';
  import { useExtendConfigFormSchemas } from '../hooks/useSchemas';

  export default defineComponent({
    name: 'CgformExtConfigModel',
    components: { BasicModal, BasicForm, ConfigProvider },
    props: {
      parentForm: {
        type: Object,
        required: true,
      },
    },
    emits: ['register', 'ok'],
    setup(props, { emit }) {
      const { createMessage: $message } = useMessage();

      const { formSchemas } = useExtendConfigFormSchemas(props, {
        onIsDesformChange,
        onJoinQueryChange,
        onReportPrintShowChange,
        onFormLabelLengthShow,
      });

      // 表单配置
      const [registerForm, { resetFields, setFieldsValue, getFieldsValue, clearValidate, validate }] = useForm({
        schemas: formSchemas,
        showActionButtonGroup: false,
        labelAlign: 'right',
      });

      const [registerModal, { closeModal }] = useModalInner(async (data) => {
        await resetFields();
        await setFieldsValue(data.extConfigJson);
      });

      async function handleOk() {
        await clearValidate();
        await nextTick();
        try {
          const values = await validate();
          emit('ok', values);
          closeModal();
        } catch (e) {}
      }

      function handleCancel() {
        closeModal();
      }

      // 对接表单设计更改事件
      function onIsDesformChange(value) {
        if (value === 'Y') {
          let { themeTemplate } = props.parentForm.getFieldsValue(['themeTemplate']);
          if ('erp' === themeTemplate) {
            props.parentForm.setFieldsValue({ themeTemplate: 'normal' });
            $message.warning('请注意：erp风格不支持对接表单设计，已自动改为默认风格！');
          }
        } else {
          clearValidate('desFormCode');
        }
      }

      // 默认提示积木报表地址
      const defaultReportPrintUrl = `{{ window._CONFIG['domianURL'] }}/jmreport/view/{积木报表ID}`;

      // 集成积木报表更改事件
      async function onReportPrintShowChange(value) {
        let reportPrintUrl = getFieldsValue()['reportPrintUrl'];
        // 0 = 关闭时，清空默认提示地址
        if (value === 0) {
          if (reportPrintUrl === defaultReportPrintUrl) {
            await setFieldsValue({ reportPrintUrl: '' });
          }
        } else if (value === 1) {
          if (reportPrintUrl === '') {
            await setFieldsValue({ reportPrintUrl: defaultReportPrintUrl });
          }
        }
        clearValidate('reportPrintUrl');
      }
      /**
       * 2024-03-29
       * liaozhiyang
       * 表单统一label长度关闭时,formLabelLength置空
       */
      async function onFormLabelLengthShow(value) {
        if (value == 0) {
          await setFieldsValue({ formLabelLength: null });
        }
        await clearValidate('formLabelLength');
      }

      // 联合查询更改事件
      function onJoinQueryChange(value) {
        if (value === 1) {
          let { themeTemplate, isTree, tableType } = props.parentForm.getFieldsValue(['themeTemplate', 'isTree', 'tableType']);
          if ('erp' === themeTemplate) {
            $message.warning('请注意：erp风格不支持联合查询，配置无效!');
            setFieldsValue({ joinQuery: 0 });
          }
          if ('innerTable' === themeTemplate) {
            $message.warning('请注意：内嵌风格不支持联合查询，配置无效!');
            setFieldsValue({ joinQuery: 0 });
          }
          if (1 === tableType) {
            $message.warning('请注意：单表不支持联合查询，配置无效!');
            setFieldsValue({ joinQuery: 0 });
          } else if (3 === tableType) {
            $message.warning('请注意：当前表为附表，请在对应主表配置!');
            setFieldsValue({ joinQuery: 0 });
          } else if ('Y' === isTree) {
            $message.warning('请注意：树形列表不支持联合查询，配置无效!');
            setFieldsValue({ joinQuery: 0 });
          }
        }
      }

      return {
        handleOk,
        handleCancel,
        registerModal,
        registerForm,
      };
    },
  });
</script>

<style scoped lang="less">
  .onl-cgform-ext-config-form.ant-form-inline {
    :deep(.ant-form-item) {
      margin-bottom: 8px;
    }
  }
</style>
