import { computed, Ref } from 'vue';
import { BasicColumn, FormSchema } from '/@/components/Table';
import { onlineDefaultButton } from '../../cgform.data';

export function useJavaColumns(btnList: Ref<any[]>) {
  let columns: BasicColumn[] = [
    {
      title: '页面按钮',
      align: 'center',
      dataIndex: 'buttonCode',
      customRender: ({ text }) => renderButtonText(text, btnList.value),
    },
    {
      title: '事件状态',
      align: 'center',
      dataIndex: 'event',
      customRender: ({ text }) => (text == 'start' ? '开始' : '结束'),
    },
    {
      title: '类型',
      align: 'center',
      dataIndex: 'cgJavaType',
      customRender: ({ text }) => {
        if (text == 'spring') {
          return 'spring-key';
        } else if (text === 'class') {
          return 'java-class';
        } else if (text === 'http') {
          return 'http-api';
        } else {
          return text;
        }
      },
    },
    {
      title: '内容',
      align: 'center',
      dataIndex: 'cgJavaValue',
    },
    {
      title: '是否生效',
      align: 'center',
      dataIndex: 'activeStatus',
      customRender: ({ text }) => {
        if (text == '1') {
          return '有效';
        } else {
          return '无效';
        }
      },
    },
  ];
  return { columns };
}

export function useJavaFormSchemas(btnList: Ref<any[]>) {
  const formSchemas = computed<FormSchema[]>(() => {
    return [
      {
        label: '页面按钮',
        field: 'buttonCode',
        component: 'Select',
        componentProps: {
          options: [
            { label: '新增', value: 'add' },
            { label: '编辑', value: 'edit' },
            { label: '删除', value: 'delete' },
            { label: '导入', value: 'import' },
            { label: '导出', value: 'export' },
            { label: '查询', value: 'query' },
            ...btnList.value.map((item) => ({ label: item.buttonName, value: item.buttonCode })),
          ],
        },
        defaultValue: 'add',
      },
      {
        label: '事件状态',
        field: 'event',
        component: 'RadioButtonGroup',
        componentProps: {
          options: [
            { label: '开始', value: 'start' },
            { label: '结束', value: 'end' },
          ],
        },
        defaultValue: 'end',
      },
      {
        label: '类型',
        field: 'cgJavaType',
        component: 'RadioButtonGroup',
        componentProps: {
          options: [
            { label: 'spring-key', value: 'spring' },
            { label: 'java-class', value: 'class' },
            { label: 'http-api', value: 'http' },
          ],
        },
        defaultValue: 'spring',
      },
      {
        label: '内容',
        field: 'cgJavaValue',
        component: 'Input',
        required: true,
      },
      {
        label: '是否生效',
        field: 'activeStatus',
        component: 'RadioButtonGroup',
        componentProps: {
          options: [
            { label: '有效', value: '1' },
            { label: '无效', value: '0' },
          ],
        },
        defaultValue: '1',
      },
    ];
  });

  return { formSchemas };
}

export function useSqlColumns(btnList: Ref<any[]>) {
  let columns: BasicColumn[] = [
    {
      title: '页面按钮',
      align: 'center',
      dataIndex: 'buttonCode',
      customRender: ({ text }) => renderButtonText(text, btnList.value),
    },
    {
      title: '增强SQL',
      align: 'center',
      dataIndex: 'cgbSql',
      ellipsis: true,
    },
  ];
  return { columns };
}

export function useSqlFormSchemas(btnList: Ref<any[]>) {
  const formSchemas = computed<FormSchema[]>(() => {
    return [
      {
        label: '页面按钮',
        field: 'buttonCode',
        component: 'Select',
        componentProps: {
          allowClear: false,
          options: [
            { label: '新增', value: 'add' },
            { label: '编辑', value: 'edit' },
            { label: '删除', value: 'delete' },
            ...btnList.value.map((item) => ({ label: item.buttonName, value: item.buttonCode })),
          ],
        },
        defaultValue: 'add',
      },
      {
        label: '增强SQL',
        field: 'cgbSql',
        component: 'JCodeEditor',
        componentProps: {
          language: 'sql',
          placeholder: '请输入SQL语句',
          languageChange: false,
          lineNumbers: false,
          fullScreen: true,
          height: '320px',
        },
        defaultValue: '',
      },
      {
        label: '描述',
        field: 'content',
        component: 'InputTextArea',
        defaultValue: '',
      },
    ];
  });

  return { formSchemas };
}

function renderButtonText(text: string, btnList: any[]) {
  let str = '';
  for (let item of onlineDefaultButton) {
    if (item.code === text) {
      str = item.title;
      break;
    }
  }
  if (!str) {
    for (let item of btnList) {
      if (item.buttonCode === text) {
        str = item.buttonName;
        break;
      }
    }
  }
  return str || text;
}
