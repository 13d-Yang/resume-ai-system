<template>
  <a-spin :spinning="loading">
    <template v-if="treeData && treeData.length > 0">
      <BasicTree
        :expandedKeys="expandedKeys"
        :fieldNames="{ children: 'children', title: 'title', key: 'value' }"
        ref="basicTree"
        :treeData="treeData"
        :checkStrictly="true"
        @select="onSelectDepart"
        style="height: calc(100vh - 390px); min-height: 150px; overflow: auto"
      ></BasicTree>
    </template>
    <a-empty v-else description="无岗位信息" />
  </a-spin>
</template>

<script lang="ts" setup>
  import { ref, watchEffect } from 'vue';
  import { BasicTree } from '/@/components/Tree/index';

  const props = defineProps({
    treeData: { type: Array, default: () => ([]) },
  });
  const emit = defineEmits(['select']);
  const basicTree = ref();
  const loading = ref<boolean>(false);
  //选中的key
  const expandedKeys = ref<any[]>([]);
  //所有的部门id
  const departIds = ref<any[]>([]);
  /**
   * 折叠全部
   *
   * @param expandAll
   */
  async function expandAll(expandAll) {
    if (!expandAll) {
      expandedKeys.value = [];
    } else {
      expandedKeys.value = departIds.value;
    }
  }

  watchEffect(() => {
    props.treeData && (departIds.value = getParentDepartmentIds(props.treeData));
  });

  /**
   * 
   * @param data
   * @param node
   */
  function onSelectDepart(data, { node }) {
    emit('select', data);
  }
  /**
   * 获取存在子级的部门id
   * @param departments
   */
  function getParentDepartmentIds(departments) {
    const ids: any = [];
    departments.forEach((dept) => {
      // 检查是否有 children 数组且不为空
      if (dept.children && Array.isArray(dept.children) && dept.children.length > 0) {
        ids.push(dept.id);
        // 递归检查子部门是否也有子级
        ids.push(...getParentDepartmentIds(dept.children));
      }
    });
    return ids;
  }
</script>

<style lang="less" scoped>
  .depart-rule-tree :deep(.scrollbar__bar) {
    pointer-events: none;
  }
</style>
