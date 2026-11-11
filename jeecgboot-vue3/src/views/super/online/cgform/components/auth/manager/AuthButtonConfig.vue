<template>
  <div class="auth-field-config">
    <BasicTable @register="registerTable">
      <template #switch="{ text, record }">
        <a-switch size="small" :checked="record.status === 1" @change="(flag) => onUpdateStatus(flag, record)" />
      </template>

      <template #control> 可见 </template>
    </BasicTable>
  </div>
</template>

<script lang="ts">
  import { defineComponent, ref, watch } from 'vue';
  import { cloneDeep } from 'lodash-es';
  import { BasicTable, useTable } from '/@/components/Table';
  import { authButtonLoadData, authButtonEnable, authButtonDisable } from '../auth.api';
  import { authButtonColumns, authButtonFixedList } from '../auth.data';

  export default defineComponent({
    name: 'AuthButtonConfig',
    components: { BasicTable },
    props: {
      headId: {
        type: String,
        default: '',
        required: true,
      },
      // 1单表 2主表 3附表
      tableType: {
        type: Number,
        default: 1,
      },
    },
    setup(props) {
      const cgformId = ref('');
      const pageType = ref(2);
      const pageControlList = ref(3);
      const pageControlForm = ref(5);
      const [registerTable, { reload, getTableRef, setPagination }] = useTable({
        api: loadData,
        rowKey: 'code',
        bordered: true,
        columns: authButtonColumns,
        showIndexColumn: false,
      });

      watch(
        () => props.headId,
        (headId) => {
          cgformId.value = headId.split('?')[0];
          // update-begin--author:liaozhiyang---date:20240520---for：【TV360X-149】点击权限控制进入页面后，分页没有重置
          getTableRef().value && setPagination({ current: 1, pageSize: 10 });
          // update-end--author:liaozhiyang---date:20240520---for：【TV360X-149】点击权限控制进入页面后，分页没有重置
          reload().catch(() => null);
        },
        { immediate: true }
      );

      /**
       * 获取内置按钮
       * liaozhiyang
       * 2024-06-14
       * 【TV360X-1017】子表权限管理按钮权限根据主表主题模版只显示所需按钮
       * */
      const getButtonList = (res) => {
        const buttons = cloneDeep(authButtonFixedList);
        if (res.mainRelationType != null && res.mainThemeTemplate != null && props.tableType == 3) {
          // 子表（一对一、一对多）
          let result: any = [];
          switch (res.mainThemeTemplate) {
            case 'normal':
            case 'innerTable':
            case 'tab':
              if (res.mainRelationType == 1) {
                // 一对一
                result = [];
              } else {
                // 一对多
                result = buttons.filter((item) => ['add', 'update', 'batch_delete'].includes(item.code));
              }
              break;
            case 'erp':
              result = buttons.filter((item) => !['super_query'].includes(item.code));
              break;
          }
          return result;
        } else {
          // 主表\单表（全显示）
          return buttons;
        }
      };

      // 加载数据
      async function loadData(params) {
        let result = await authButtonLoadData(cgformId.value, params);
        let { authList, buttonList } = result;
        let dataSource: Recordable[] = [];
        // concat 固定按钮
        // -update-begin--author:liaozhiyang---date:20240614---for：【TV360X-1017】子表权限管理按钮权限根据主表主题模版只显示所需按钮
        // 获取内置按钮
        const buttons = getButtonList(result);
        // -update-end--author:liaozhiyang---date:20240614---for：【TV360X-1017】子表权限管理按钮权限根据主表主题模版只显示所需按钮
        for (let btn of buttons) {

          // 去除重复数据
          const findBtnIdx = buttonList.findIndex((item) => item.buttonCode === btn.code);
          const findBtn: Recordable = {}
          if (findBtnIdx !== -1) {
            findBtn.title = buttonList[findBtnIdx].buttonName;
            buttonList.splice(findBtnIdx, 1);
          }

          let item = {
            status: 0,
            page: pageControlList.value,
          };
          let auth = authList.find((auth) => auth.code == btn.code);
          Object.assign(btn, item, auth, findBtn);
          dataSource.push(btn);
        }
        // update-begin--author:liaozhiyang---date:20240520---for：【TV360X-187】去掉子表权限管理中按钮权限的高级查询
        if (props.tableType == 3) {
          const findIndex = dataSource.findIndex((item) => item.code === 'super_query');
          if (findIndex != -1) {
            dataSource.splice(findIndex, 1);
          }
        }
        // update-end--author:liaozhiyang---date:20240520---for：【TV360X-187】去掉子表权限管理中按钮权限的高级查询
        // update-begin--author:liaozhiyang---date:20250403---for：【QQYUN-11801】生成测试数据
        if ([2, 3].includes(+props.tableType)) {
          const findIndex = dataSource.findIndex((item) => item.code == 'aigc_mock_data');
          if (findIndex != -1) {
            dataSource.splice(findIndex, 1);
          }
        }
        // update-end--author:liaozhiyang---date:20250403---for：【QQYUN-11801】生成测试数据
        // concat 查询的自定义按钮
        return concatCustomButton(authList, buttonList, dataSource);
      }

      

      function concatCustomButton(authList: any[], buttonList: any[], dataSource: any[]) {
        for (let btn of buttonList) {
          //update-begin-author:taoyan date:2022-5-25 for: VUEN-1103 自定义按钮，开启权限控制后，再打开未保存上
          let auth = authList.find((auth) => auth.code == btn.buttonCode);
          //update-end-author:taoyan date:2022-5-25 for: VUEN-1103 自定义按钮，开启权限控制后，再打开未保存上
          let item = {
            code: btn.buttonCode,
            title: btn.buttonName,
            status: 0,
            page: btn.buttonStyle == 'form' ? pageControlForm.value : pageControlList.value,
          };
          dataSource.push(Object.assign(item, auth));
        }
        return dataSource;
      }

      async function onUpdateStatus(flag, record) {
        flag ? doEnableAuthButton(record) : doDisableAuthButton(record);
      }

      // 启用按钮权限
      async function doEnableAuthButton(record: Recordable) {
        let result = await authButtonEnable({
          id: record.id,
          code: record.code,
          page: record.page,
          cgformId: cgformId.value,
          type: pageType.value,
          control: 5,
          status: 1,
        });
        record.id = result.id;
        record.status = 1;
      }

      // 禁用按钮权限
      async function doDisableAuthButton(record: Recordable) {
        await authButtonDisable(record.id);
        record.status = 0;
      }

      return { registerTable, onUpdateStatus };
    },
  });
</script>

<style lang="less" scoped></style>
