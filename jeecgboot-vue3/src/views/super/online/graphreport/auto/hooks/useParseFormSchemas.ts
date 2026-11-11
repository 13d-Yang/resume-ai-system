import { nextTick, Ref, h } from 'vue';
import { FormSchema } from '/@/components/Form';
import { InputNumber, Input, DatePicker } from 'ant-design-vue';

type PSchema = Partial<FormSchema>;

export function useParseFormSchemas(chartsData: Ref<any>, showSearchField: Ref<boolean>) {
  // 解析查询条件 FormSchemas
  async function parseFormSchemas() {
    let { head, items, dictOptions } = chartsData.value;
    if (head.dataType === 'sql') {
      let formSchemas: FormSchema[] = [];
      items.forEach((field) => {
        // 判断是否查询
        if (field.searchFlag !== 'Y') return;
        let isRange = field.searchMode === 'group';
        let schema: PSchema = {};
        let schemas: FormSchema[] = [];
        // 判断是否有字典，字典组件不能范围查询
        if (field.dictCode && dictOptions[field.dictCode]) {
          schema.component = 'Select';
          schema.componentProps = {
            options: dictOptions[field.dictCode],
          };
        } else if (['Integer', 'Long'].includes(field.fieldType)) {
          // 数字输入框
          schema.component = 'InputNumber';
          if (isRange) {
            schema.render = getRangeRender(schemas, field, InputNumber);
          }
        } else if (field.fieldType === 'Date') {
          // 日期选择组件
          schema.component = 'DatePicker';
          schema.componentProps = {
            format: 'YYYY-MM-DD',
          };
          if (isRange) {
            schema.render = getRangeRender(schemas, field, DatePicker);
          }
        } else {
          // 普通文本框
          schema.component = 'Input';
          if (isRange) {
            schema.render = getRangeRender(schemas, field, Input);
          }
        }
        formSchemas = formSchemas
          .concat({
            label: field.fieldTxt,
            field: field.fieldName,
            component: 'Input',
            itemProps: {
              class: { 'range-query': isRange },
            } as any,
            ...schema,
          })
          .concat(schemas);
      });
      showSearchField.value = formSchemas.length > 0;
      await nextTick();
      return formSchemas;
    } else {
      showSearchField.value = false;
      return null;
    }
  }

  return { parseFormSchemas };
}

/**
 * 获取范围渲染方法
 *
 * @param schemas 显示名
 * @param fieldItem 字段
 * @param component vue 组件
 */
function getRangeRender(schemas: FormSchema[], fieldItem, component: any) {
  let { fieldTxt: label, fieldName: beginField } = fieldItem;
  let endField = beginField + '_end';
  // 添加占位符
  schemas.push({ label: '', field: endField, component: 'Input', show: false });
  return function ({ model }) {
    return [
      h(component, {
        value: model[beginField],
        'onUpdate:value': (v) => (model[beginField] = v),
        placeholder: '请输入开始' + label,

        format: 'YYYY-MM-DD',
      }),
      h('span', { class: 'range-span' }, '~'),
      h(component, {
        value: model[endField],
        'onUpdate:value': (v) => (model[endField] = v),
        placeholder: '请输入结束' + label,
        format: 'YYYY-MM-DD',
      }),
    ];
  };
}
