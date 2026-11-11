import { computed } from 'vue';
import { BasicColumn, FormSchema } from '/@/components/Table';
import { useConditionFilter } from '/@/utils/index';

// 字段权限列配置
export const authFieldColumns: BasicColumn[] = [
  {
    title: '启用',
    dataIndex: 'switch',
    width: 100,
    align: 'center',
    slots: { customRender: 'switch' },
  },
  {
    title: '字段名称',
    width: 200,
    dataIndex: 'code',
  },
  {
    title: '字段描述',
    // width: 200,
    dataIndex: 'title',
  },
  {
    title: '列表控制',
    dataIndex: 'list',
    width: 120,
    slots: { customRender: 'list' },
  },
  {
    title: '表单控制',
    dataIndex: 'form',
    width: 180,
    slots: { customRender: 'form' },
  },
];

// 按钮权限列配置
export const authButtonColumns: BasicColumn[] = [
  {
    title: '启用',
    dataIndex: 'switch',
    width: 80,
    slots: { customRender: 'switch' },
  },
  {
    title: '名称',
    dataIndex: 'title',
  },
  {
    title: '编码',
    dataIndex: 'code',
  },
  {
    title: '权限控制',
    dataIndex: 'control',
    width: 180,
    slots: { customRender: 'control' },
  },
];

export const authButtonFixedList = [
  { code: 'add', title: '新增', status: 0 },
  { code: 'edit', title: '编辑', status: 0 },
  { code: 'detail', title: '详情', status: 0 },
  { code: 'delete', title: '删除', status: 0 },
  { code: 'batch_delete', title: '批量删除', status: 0 },
  { code: 'export', title: '导出', status: 0 },
  { code: 'import', title: '导入', status: 0 },
  { code: 'query', title: '查询', status: 0 },
  { code: 'reset', title: '重置', status: 0 },
  { code: 'aigc_mock_data', title: '生成测试数据', status: 0 },
  { code: 'bpm', title: '提交流程', status: 0 },
  { code: 'super_query', title: '高级查询', status: 0 },
  { code: 'form_confirm', title: '确定', status: 0 },
];

export const USE_SQL_RULES = 'USE_SQL_RULES';
// 数据权限列配置
export const authDataColumns: BasicColumn[] = [
  {
    title: '启用',
    dataIndex: 'switch',
    width: 80,
    slots: { customRender: 'switch' },
  },
  {
    title: '规则名称',
    dataIndex: 'ruleName',
    width: 130,
  },
  {
    title: '规则描述',
    dataIndex: 'description',
    customRender({ record: { ruleOperator, ruleValue, ruleColumn } }) {
      if (ruleOperator == USE_SQL_RULES) {
        return `自定义SQL: ${ruleValue}`;
      } else {
        return `${ruleColumn} ${ruleOperator} ${ruleValue}`;
      }
    },
  },
];

export function useAuthDataFormSchemas(props, methods) {
  const formSchemas = computed<FormSchema[]>(() => [
    {
      label: '规则名称',
      field: 'ruleName',
      required: true,
      component: 'Input',
      componentProps: {
        onChange: methods.onRuleNameChange,
      },
    },
    {
      label: '规则字段',
      field: 'ruleColumn',
      component: 'JSearchSelect',
      componentProps: {
        dictOptions: props.authFields,
        getPopupContainer: () => document.body,
        onChange: methods.onRuleColumnChange,
      },
      dynamicRules({ model }) {
        return [{ required: model.ruleOperator != USE_SQL_RULES, message: '请输入规则字段' }];
      },
      show: ({ model }) => model.ruleOperator != USE_SQL_RULES,
    },
    // -update-begin--author:liaozhiyang---date:20240617---for：【TV360X-201】权限管理条件根据控件过滤
    {
      label: '条件规则',
      field: 'ruleOperator',
      required: true,
      component: 'JDictSelectTag',
      componentProps: {
        options: [],
        onChange: methods.onRuleOperatorChange,
        getPopupContainer: () => document.body,
      },
      dynamicPropskey: 'options',
      dynamicPropsVal: ({ model, field }) => {
        const getFieldType = (type) => {
          if (['BigDecimal', 'double', 'int'].includes(type)) {
            return 'number';
          } else {
            return;
          }
        };
        const { filterCondition } = useConditionFilter();
        if (model.ruleColumn) {
          const findItem = props.authFields.find((item) => item.value === model.ruleColumn) ?? {};
          const result = filterCondition({ view: findItem.view, fieldType: getFieldType(findItem.dbType) }).map((item) => ({
            label: item.title ?? item.label,
            value: item.val ?? item.value,
          }));
          result.push({ value: 'USE_SQL_RULES', label: '自定义SQL' });
          return result;
        } else {
          return [{ value: 'USE_SQL_RULES', label: '自定义SQL' }];
        }
      },
    },
    // {
    //   label: '条件规则',
    //   field: 'ruleOperator',
    //   required: true,
    //   component: 'JDictSelectTag',
    //   componentProps: {
    //     dictCode: 'rule_conditions',
    //     onChange: methods.onRuleOperatorChange,
    //     getPopupContainer: () => document.body,
    //   },
    // },
    // -update-end--author:liaozhiyang---date:20240617---for：【TV360X-201】权限管理条件根据控件过滤
    {
      label: '规则值',
      field: 'ruleValue',
      required: true,
      // -update-begin--author:liaozhiyang---date:20240607---for：【TV360X-536】数据权限配置配置优化及新增JInputSelect组件
      component: 'JInputSelect',
      componentProps: {
        selectPlaceholder: '可选择系统变量',
        inputPlaceholder: '请输入',
        getPopupContainer: () => document.body,
        selectWidth: '200px',
        options: [
          {
            label: '登录用户账号',
            value: '#{sys_user_code}',
          },
          {
            label: '登录用户名称',
            value: '#{sys_user_name}',
          },
          {
            label: '当前日期',
            value: '#{sys_date}',
          },
          {
            label: '当前时间',
            value: '#{sys_time}',
          },
          {
            label: '登录用户部门',
            value: '#{sys_org_code}',
          },
          {
            label: '用户拥有的部门',
            value: '#{sys_multi_org_code}',
          },
          {
            label: '登录用户租户',
            value: '#{tenant_id}',
          },
        ],
      },
      // -update-end--author:liaozhiyang---date:20240607---for：【TV360X-536】数据权限配置配置优化及新增JInputSelect组件
    },
    {
      label: '状态',
      field: 'status',
      required: true,
      component: 'RadioButtonGroup',
      componentProps: {
        options: [
          { label: '有效', value: 1 },
          { label: '无效', value: 0 },
        ],
      },
      defaultValue: 1,
    },
  ]);
  return { formSchemas };
}
