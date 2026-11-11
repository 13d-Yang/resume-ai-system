<!-- 字典下拉单选 -->
<template>
  <a-select
    :value="innerValue"
    :disabled="disabled"
    :placeholder="placeholder"
    :filter-option="filterOptionComputed"
    :showSearch="showSearch"
    :getPopupContainer="getPopupContainer"
    :notFoundContent="loading ? undefined : null"
    allowClear
    @change="handleChange"
    @search="handleSearch"
    @popupScroll="handlePopupScroll"
    @dropdownVisibleChange="handleDropdownVisibleChange"
    v-bind="$attrs"
  >
    <template #notFoundContent>
      <a-spin v-if="loading" size="small" />
    </template>
    <template v-for="item in selectOptions" :key="item.key">
      <a-select-option :value="item.value" :getPopupContainer="getPopupContainer">
        <span :class="item.class" :style="item.style">{{ item.text }}</span>
      </a-select-option>
    </template>
  </a-select>
</template>

<script setup lang="ts">
  import { computed, ref, watch, unref } from 'vue';
  import { debounce } from 'lodash-es';
  import { initDictOptions } from '/@/utils/dict/index';
  import { setPopContainer } from '/@/utils';
  import { defHttp } from '/@/utils/http/axios';

  defineOptions({ name: 'JSelectSingle' });

  // --- Props & Emits ---
  interface DictOption {
    value: string | number;
    label?: string;
    text?: string;
    color?: string;
  }

  interface SelectOptionItem {
    key: string;
    text: string;
    value: string | number;
    class: string[];
    style: { backgroundColor: string };
  }

  /** 下拉单选组件的值类型（可被 change / update:value / input 等复用） */
  export type SelectSingleValue = string | number | undefined;

  const props = withDefaults(
    defineProps<{
      value?: SelectSingleValue;
      placeholder?: string;
      readOnly?: boolean;
      options?: DictOption[];
      triggerChange?: boolean;
      popContainer?: string;
      dictCode?: string;
      disabled?: boolean;
      useDicColor?: boolean;
      pageSize?: number;
      scrollLoad?: boolean;
    }>(),
    {
      placeholder: '请选择',
      readOnly: false,
      options: () => [],
      triggerChange: true,
      popContainer: '',
      disabled: false,
      useDicColor: false,
      pageSize: 10,
      scrollLoad: false,
    }
  );
  const emit = defineEmits<{
    (e: 'change', value: SelectSingleValue): void;
    (e: 'update:value', value: SelectSingleValue): void;
    (e: 'input', value: SelectSingleValue): void;
    (e: 'options-change'): void;
  }>();

  // --- 选项数据 ---
  const innerValue = ref<SelectSingleValue>(props.value ?? undefined);
  const dictOptions = ref<DictOption[]>([]);
  const loading = ref(false);
  const searchKeyword = ref('');

  // --- 字典加载（分页滚动） ---
  const scrollState = {
    pageNo: 1,
    hasMore: true,
    loading: false,
  };

  const isDictTable = computed(() => {
    if (!props.dictCode) return false;
    return props.dictCode.split(',').length >= 2;
  });

  const useLoadDict = computed(() => props.scrollLoad && isDictTable.value);

  const selectOptions = computed<SelectOptionItem[]>(() => {
    if (!Array.isArray(dictOptions.value)) return [];
    return dictOptions.value.map((item, index) => {
      const text = item.text ?? item.label ?? '';
      return {
        key: `${item.value}_${text}_${index}`,
        text,
        value: item.value,
        class: [props.useDicColor && item.color ? 'colorText' : ''],
        style: { backgroundColor: props.useDicColor && item.color ? String(item.color) : '' },
      };
    });
  });

  function fetchDictPage(pageNo: number, append: boolean) {
    return defHttp
      .get({
        url: `/sys/dict/loadDict/${props.dictCode}`,
        params: { pageNo, pageSize: props.pageSize, keyword: searchKeyword.value, order: 'asc' },
      })
      .then((res: any[]) => {
        const items: DictOption[] = (res ?? []).map((it) => ({
          value: it.value,
          label: it.text ?? it.label,
        }));
        if (items.length === 0) {
          if (!append) dictOptions.value = [];
          scrollState.hasMore = false;
          return;
        }
        if (append) {
          const existValues = new Set(dictOptions.value.map((o) => String(o.value)));
          const newItems = items.filter((it) => !existValues.has(String(it.value)));
          if (newItems.length > 0) {
            dictOptions.value = [...dictOptions.value, ...newItems];
          }
        } else {
          // 有选中的值且optinos中存在时，需要把选中的值在options中存在且不在新数据中的项保留（防止多次请求）
          if (unref(innerValue) && unref(dictOptions).length) {
            const existItem = unref(dictOptions).find((item) => String(item.value) === String(unref(innerValue)));
            if (existItem && !items.some((item) => String(item.value) === String(existItem.value))) {
              items.push(existItem);
            }
          }
          dictOptions.value = items;
        }
        scrollState.pageNo = pageNo + 1;
      });
  }

  async function loadDictOptions() {
    if (useLoadDict.value) {
      scrollState.pageNo = 1;
      scrollState.hasMore = true;
      loading.value = true;
      fetchDictPage(1, false)
        .catch(() => {
          dictOptions.value = [];
        })
        .finally(() => {
          loading.value = false;
          ensureValueInOptions();
        });
    } else {
      let code = props.dictCode ?? '';
      try {
        const dictData = await initDictOptions(code);
        dictOptions.value = dictData;
      } catch (error) {
        console.error('initDictOptions error:', error);
        dictOptions.value = [];
      }
    }
  }

  /** 根据 value 拉取单条字典项用于回显（编辑时当前值不在已加载选项中时） */
  function fetchDictItemByValue(val: SelectSingleValue): Promise<DictOption | null> {
    if (val == null) return Promise.resolve(null);
    return defHttp
      .get({ url: `/sys/dict/loadDictItem/${props.dictCode}`, params: { key: val } })
      .then((res: any) => {
        if (Array.isArray(res)) {
          return { value: val, label: res[0] };
        }
        return null;
      })
      .catch(() => null);
  }

  /** 确保当前 value 在选项中（仅 useLoadDict 时：编辑时当前值不在已加载列表中则拉取单条并插入） */
  function ensureValueInOptions() {
    if (!useLoadDict.value) return;
    const val = innerValue.value;
    if (val == null) return;
    const exists = dictOptions.value.some((o) => String(o.value) === String(val));
    if (exists) return;
    fetchDictItemByValue(val).then((item) => {
      if (item) dictOptions.value = [item].concat(dictOptions.value);
    });
  }

  const handleSearch = debounce((keyword: string) => {
    if (!useLoadDict.value) return;
    searchKeyword.value = keyword ?? '';
    scrollState.pageNo = 1;
    scrollState.hasMore = true;
    loading.value = true;
    fetchDictPage(1, false)
      .catch(() => {
        dictOptions.value = [];
      })
      .finally(() => {
        loading.value = false;
        ensureValueInOptions();
      });
  }, 300);

  function handleDropdownVisibleChange(open: boolean) {
    if (!open || !useLoadDict.value) return;
    scrollState.pageNo = 1;
    scrollState.hasMore = true;
    searchKeyword.value = '';
    loading.value = true;
    fetchDictPage(1, false)
      .finally(() => {
        loading.value = false;
        ensureValueInOptions();
      });
  }

  function handlePopupScroll(e: Event) {
    if (!useLoadDict.value || scrollState.loading || !scrollState.hasMore) return;
    const target = e.target as HTMLElement;
    const { scrollTop, scrollHeight, clientHeight } = target;
    if (scrollTop + clientHeight < scrollHeight - 10) return;
    scrollState.loading = true;
    fetchDictPage(scrollState.pageNo, true)
      .finally(() => {
        scrollState.loading = false;
      })
      .catch(() => {
        if (scrollState.pageNo > 1) {
          scrollState.pageNo--;
        }
      });
  }

  // --- 弹层挂载 & 搜索过滤 ---
  const showSearch = computed(() => useLoadDict.value);
  function getPopupContainer(node: HTMLElement) {
    return props.popContainer ? setPopContainer(node, props.popContainer) : node?.parentNode;
  }

  function filterOption(input: string, option: any) {
    const node = option.children?.();
    const text = (node?.[0]?.children ?? '').toString().toLowerCase();
    return text.indexOf(input.toLowerCase()) >= 0;
  }
  const filterOptionComputed = computed(() => (input: string, option: any) => {
    if (useLoadDict.value) return true;
    return filterOption(input, option);
  });

  // --- 选择变更 ---
  function handleChange(value: SelectSingleValue) {
    const val = value ?? undefined;
    if (props.triggerChange) {
      emit('change', val);
    } else {
      emit('input', val);
    }
    emit('update:value', val);
  }

  // --- 初始化与监听 ---
  function syncOptionsFromProps() {
    if (props.dictCode) {
      loadDictOptions();
    } else {
      dictOptions.value = props.options ?? [];
    }
  }
  watch(() => props.dictCode, syncOptionsFromProps);

  watch(
    () => props.value,
    (val) => {
      innerValue.value = val ?? undefined;
      if (useLoadDict.value) ensureValueInOptions();
    }
  );

  watch(
    () => props.options,
    () => {
      if (!props.dictCode) dictOptions.value = props.options ?? [];
    }
  );

  syncOptionsFromProps();
</script>

<style scoped lang="less">
  .colorText {
    display: inline-block;
    height: 20px;
    line-height: 20px;
    padding: 0 6px;
    border-radius: 8px;
    background-color: red;
    color: #fff;
    font-size: 12px;
  }
</style>
