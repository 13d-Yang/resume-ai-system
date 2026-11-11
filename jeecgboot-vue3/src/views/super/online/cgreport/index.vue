<template>
  <div>
    <BasicTable @register="registerTable" :rowSelection="rowSelection" v-bind="$attrs">
      <template #tableTitle>
        <a-button preIcon="ant-design:plus-outlined" type="primary" @click="handleAdd" style="margin-right: 5px">录入</a-button>
        <a-button preIcon="bxs:bot" type="primary" style="margin-right: 5px" @click="onCreateByAi">AI生成报表</a-button>
        <a-dropdown v-if="selectedRowKeys.length > 0">
          <template #overlay>
            <a-menu>
              <a-menu-item key="1" @click="batchHandleDelete">
                <Icon icon="ant-design:delete-outlined"></Icon>
                删除
              </a-menu-item>
            </a-menu>
          </template>
          <a-button
            >批量操作
            <Icon icon="mdi:chevron-down"></Icon>
          </a-button>
        </a-dropdown>
      </template>
      <template #action="{ record }">
        <TableAction :actions="getAction(record)" :dropDownActions="getDropDownAction(record)" />
      </template>
    </BasicTable>
    <!-- 表单区域 -->
    <CgreportModal @register="registerModal" @success="handleSuccess"></CgreportModal>
    <!-- 通过Ai生成报表 -->
    <CgreportAigcModal @register="registerCgreportAigcModal" @generate="onAigcGenerate" />
  </div>
</template>

<script lang="ts" name="online-cgreport" setup>
  import { BasicTable, TableAction } from '/@/components/Table';
  import { useListPage } from '/@/hooks/system/useListPage';
  import { columns, searchFormSchema } from './cgreport.data';
  import { list, deleteOne, batchDelete, getReportParam } from './cgreport.api';
  import { useModal } from '/@/components/Modal';
  import CgreportModal from './components/CgreportModal.vue';
  import CgreportAigcModal from "./components/CgreportAigcModal.vue";
  import Clipboard from 'clipboard';
  import { useRouter } from 'vue-router';
  import { buildUUID } from '/@/utils/uuid';
  let router = useRouter();
  const [registerModal, { openModal }] = useModal();

  // 列表页面公共参数、方法
  const {
    prefixCls,
    tableContext,
    createMessage: $message,
    createConfirm: $confirm,
  } = useListPage({
    designScope: 'online-cgreport-list',
    pagination: true,
    tableProps: {
      title: 'Online报表',
      api: list,
      rowKey: 'id',
      columns: columns,
      formConfig: {
        autoSubmitOnEnter: true,
        showAdvancedButton: true,
        schemas: searchFormSchema,
      },
    },
  });

  const [registerTable, { reload }, { rowSelection, selectedRowKeys }] = tableContext;

  // 注册Aigc弹窗
  const [registerCgreportAigcModal, cgreportAigcModal] = useModal();
  /**
   * 新增事件
   */
  function handleAdd() {
    openModal(true, {
      isUpdate: false,
      showFooter: true,
    });
  }
  /**
   * 编辑事件 e3e3NcxzbUiGa53YYVXxWc8ADo5ISgQGx/gaZwERF91oAryDlivjqBv3wqRArgChupi+Y/Gg/swwGEyL0PuVFg==
   */
  function handleEdit(record: Recordable) {
    openModal(true, {
      record,
      isUpdate: true,
      showFooter: true,
    });
  }

  function onCreateByAi() {
    cgreportAigcModal.openModal(true, {});
  }

  /**
   * 删除事件
   */
  async function handleDelete(record) {
    await deleteOne({ id: record.id }, reload);
  }
  /**
   * 批量删除事件
   */
  async function batchHandleDelete() {
    await batchDelete({ ids: selectedRowKeys.value }, () => {
      reload();
      selectedRowKeys.value = [];
    });
  }

  /**
   * 成功回调
   */
  function handleSuccess() {
    reload();
  }

  function onAigcGenerate(aigcResult: Recordable) {
    openModal(true, {
      isUpdate: false,
      showFooter: true,
      aigc: aigcResult
    });
  }

  /**
   * 操作栏
   */
  function getAction(record) {
    return [
      {
        label: '编辑',
        onClick: handleEdit.bind(null, record),
      },
    ];
  }
  /**
   * 下拉操作栏
   */
  function getDropDownAction(record) {
    return [
      {
        label: '功能测试',
        class: ['low-app-hide'],
        onClick: () => onShowList(record.id),
      },
      {
        label: '配置地址',
        class: ['low-app-hide'],
        onClick: () => onShowOnlineUrl(record),
      },
      {
        label: '删除',
        popConfirm: {
          title: '是否确认删除',
          confirm: handleDelete.bind(null, record),
        },
      },
    ];
  }

  /**
   * 功能测试
   * @param id
   */
  function onShowList(id) {
    router.push({ path: '/online/cgreport/' + id });
  }

  /**
   * 配置地址
   * @param record
   */
  function onShowOnlineUrl(record) {
    let id = record.id;
    let baseUrl = `/online/cgreport/${id}`;
    // 生成插入菜单sql
    let insertMenuSql = `INSERT INTO sys_permission(id, parent_id, name, url, component, component_name, redirect, menu_type, perms, perms_type, sort_no, always_show, icon, is_route, is_leaf, keep_alive, hidden, hide_tab, description, status, del_flag, rule_flag, create_by, create_time, update_by, update_time, internal_or_external) 
                         VALUES ('${buildUUID()}', NULL, '${record.name}', '${baseUrl}', '1', 'OnlineAutoList', NULL, 0, NULL, '1', 0.00, 0, NULL, 0, 1, 0, 0, 0, NULL, '1', 0, 0, 'admin', null, NULL, NULL, 0)`;
    
    getReportParam(id)
      .then((arr) => {
        // 处理参数
        let urlParam = '';
        if (arr && arr.length > 0) {
          for (let i of arr) {
            urlParam += i.paramName + '=${' + i.paramName + '}&';
          }
        }
        if (urlParam.length > 0) {
          urlParam = urlParam.substring(0, urlParam.length - 1);
          baseUrl += '?' + urlParam;
        }
      })
      .catch(() => {
        $message.warning('获取参数失败!');
      })
      .finally(() => {
        // 无论获取失败与否 都弹框显示跳转地址
        $confirm({
          iconType: 'info',
          width: 500,
          title: `菜单链接【${record.name}】`,
          content: baseUrl,
          closable: true,
          maskClosable: true,
          cancelText: '复制SQL',
          okText: '复制URL',
          cancelButtonProps: {
            class: 'copy-this-sql',
            'data-clipboard-text': insertMenuSql,
          } as any,
          okButtonProps: {
            class: 'copy-this-text',
            'data-clipboard-text': baseUrl,
          } as any,
          onOk() {
            return new Promise((resolve: any) => {
              const clipboard = new Clipboard('.copy-this-text');
              clipboard.on('success', () => {
                clipboard.destroy();
                $message.success('复制URL成功');
                resolve();
              });
              clipboard.on('error', () => {
                $message.error('该浏览器不支持自动复制');
                clipboard.destroy();
                resolve();
              });
            });
          },
          onCancel() {
            return new Promise((resolve: any) => {
              const clipboard = new Clipboard('.copy-this-sql');
              clipboard.on('success', () => {
                clipboard.destroy();
                $message.success('复制插入菜单SQL成功');
                resolve();
              });
              clipboard.on('error', () => {
                $message.error('该浏览器不支持自动复制');
                clipboard.destroy();
                resolve();
              });
            });
          },
        });
      });
  }
  
  // 抛出方法，让外部可以调用
  // 目前【lowApp】页面用到
  defineExpose({
    handleAdd,
  })

</script>
