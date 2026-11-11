<template>
  <div>
    <BasicTable @register="registerTable" :loading="loading">
      <template #tableTitle>
        <a-button @click="onAdd" type="primary" preIcon="ant-design:plus">新增</a-button>
      </template>

      <template #switch="{ text, record }">
        <a-switch size="small" :checked="record.status === 1" @click="() => onUpdateStatus(record)" />
      </template>

      <!--操作栏-->
      <template #action="{ record }">
        <TableAction :actions="getTableAction(record)" :dropDownActions="getDropDownAction(record)" />
      </template>
    </BasicTable>
    <!-- 子表单 -->
    <BasicModal v-bind="formModalProps" @openChange="handleOpenChange">
      <a-spin :spinning="formModalProps.confirmLoading">
        <BasicForm @register="registerForm" />
      </a-spin>
    </BasicModal>
  </div>
</template>

<script lang="ts">
  import { watch, defineComponent, ref, reactive, nextTick } from 'vue';
  import { BasicTable, TableAction, ActionItem, useTable } from '/@/components/Table';
  import { BasicModal, useModal } from '/@/components/Modal';
  import { BasicForm, useForm } from '/@/components/Form';
  import { authDataDelete, authDataLoadData, authDataSaveOrUpdate, authDataUpdateStatus } from '../auth.api';
  import { authDataColumns, useAuthDataFormSchemas, USE_SQL_RULES } from '../auth.data';

  export default defineComponent({
    name: 'AuthDataConfig',
    components: { BasicTable, TableAction, BasicModal, BasicForm },
    props: {
      cgformId: { type: String, required: true },
      authFields: { type: Array, required: true },
    },
    setup(props) {
      const loading = ref(false);
      const [registerTable, { reload, setLoading }] = useTable({
        api: (params) => authDataLoadData(props.cgformId, params),
        rowKey: 'id',
        bordered: true,
        columns: authDataColumns,
        showIndexColumn: false,
        // 操作列
        actionColumn: {
          width: 120,
          title: '操作',
          fixed: false,
          dataIndex: 'action',
          slots: { customRender: 'action' },
        },
      });
      watch(loading, (l) => setLoading(l));
      const [registerModal, { openModal, closeModal }] = useModal();
      const formModalProps = reactive({
        title: '',
        width: 800,
        confirmLoading: false,
        onOk: onSubmit,
        onCancel: closeModal,
        onRegister: registerModal,
      });
      let isUpdate = false;
      let formRecord = {};
      let isManualEnter = false;
      const { formSchemas } = useAuthDataFormSchemas(props, {
        onRuleOperatorChange,
        onRuleColumnChange,
        onRuleNameChange,
      });
      // 表单配置
      const [registerForm, { validate, resetFields, setFieldsValue, getFieldsValue, clearValidate, updateSchema }] = useForm({
        schemas: formSchemas,
        showActionButtonGroup: false,
        labelAlign: 'right',
      });

      watch(
        () => props.cgformId,
        () => {
          reload().catch(() => null);
        },
        { immediate: true }
      );

      async function openFormModal(data) {
        isUpdate = data.isUpdate ?? false;
        formModalProps.title = data.title;
        openModal();
        await nextTick();
        await resetFields();
        formRecord = Object.assign({}, data.record);
        await setFieldsValue(formRecord);
      }

      function onAdd() {
        openFormModal({ title: '新增' });
      }

      function onEdit(record) {
        openFormModal({ title: '编辑', record, isUpdate: true });
      }

      function onDelete(id) {
        loading.value = true;
        authDataDelete(id)
          .then(reload)
          .finally(() => (loading.value = false));
      }

      async function onSubmit() {
        try {
          formModalProps.confirmLoading = true;
          let formData = await validate();
          formData = Object.assign({}, formRecord, formData);
          if (formData.ruleOperator == USE_SQL_RULES) {
            formData.ruleColumn = '';
          }
          formData.cgformId = props.cgformId;
          await authDataSaveOrUpdate(formData, isUpdate);
          reload();
          closeModal();
        } finally {
          formModalProps.confirmLoading = false;
        }
      }

      function onUpdateStatus(record) {
        loading.value = true;
        let status = Math.abs(record.status - 1);
        authDataUpdateStatus({ ...record, status })
          .then(() => {
            record.status = status;
          })
          .finally(() => {
            loading.value = false;
          });
      }

      function onRuleOperatorChange(val) {
        if (val == USE_SQL_RULES) {
          setFieldsValue({
            ruleColumn: '',
            ruleValue: '',
          });
          updateSchema({
            field: 'ruleValue',
            component: 'InputTextArea',
          });
          clearValidate(['ruleValue']);
        } else {
          updateSchema({
            field: 'ruleValue',
            component: 'JInputSelect',
          });
        }
      }
      // -update-begin--author:liaozhiyang---date:20240607---for：【TV360X-536】数据权限配置配置优化及新增JInputSelect组件
      function onRuleColumnChange(val) {
        const values = getFieldsValue();
        if (!values.ruleName || (values.ruleName && !isManualEnter)) {
          const findItem: any = props.authFields.find((item: any) => item.value === val);
          const text = findItem ? findItem.text : val;
          setFieldsValue({
            ruleName: text,
          });
        }
      }
      function onRuleNameChange(e) {
        if (e.target.value.length) {
          isManualEnter = true;
        } else {
          isManualEnter = false;
        }
      }
      function handleOpenChange(visible) {
        if (visible) {
          isManualEnter = false;
        }
      }
      // -update-end--author:liaozhiyang---date:20240607---for：【TV360X-536】数据权限配置配置优化及新增JInputSelect组件
      /**
       * 操作栏
       */
      function getTableAction(record) {
        return [
          {
            label: '编辑',
            onClick: () => onEdit(record),
          },
        ];
      }

      /**
       * 下拉操作栏
       */
      function getDropDownAction(record): ActionItem[] {
        return [
          {
            label: '删除',
            popConfirm: {
              title: '确定删除吗？',
              placement: 'left',
              confirm: () => onDelete(record.id),
            },
          },
        ];
      }

      return {
        loading,
        formModalProps,
        onAdd,
        onUpdateStatus,
        getTableAction,
        getDropDownAction,
        registerTable,
        registerModal,
        registerForm,
        handleOpenChange,
      };
    },
  });
</script>
