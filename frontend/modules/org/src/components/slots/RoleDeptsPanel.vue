<script setup lang="ts">
// 插件：部门分配（挂宿主「角色分配」页签 `sys.role.detail.assign`）。
//
// 与「岗位分配」同一上下文通道（**显式上下文注入**，`roleId`）；差别在目标为**部门**，
// 且语义为**精确匹配、不含下级**——弹窗内以部门树多选呈现（`check-strictly` 不级联）。
import { ElTree } from 'element-plus'
import { useModuleSlotField } from '@bms/ui-ep'
import { onMounted, ref, watch } from 'vue'

import { useOrgI18n } from '../../composables/useOrgI18n'
import { useAssignment, type AssignedLabel, type HostSubmitterRegistrar } from '../../composables/useAssignment'
import { flattenDeptTree, toDeptTreeData, toIdParamList, type DeptTreeNode, type DeptTreeOption } from '../../domain'
import { assignRoleDepts, fetchDeptTree, fetchRoleDeptIds } from '../../services/org-service'

import AssignPanel from './AssignPanel.vue'

const { t } = useOrgI18n()

/** 角色标识（宿主页显式上下文注入）。 */
const roleId = useModuleSlotField<string>('roleId')
const registrar = useModuleSlotField<HostSubmitterRegistrar>('registerSubmitter')
const contextId = ref(roleId.value ?? '')

/** 部门名称索引（已分配项回显）。 */
const deptNames = ref(new Map<string, AssignedLabel>())
/** 部门树（弹窗内多选；精确匹配不级联）。 */
const treeData = ref<DeptTreeOption[]>([])
/** 树组件引用（勾选回填与取值）。 */
const treeRef = ref<InstanceType<typeof ElTree>>()

const assignment = useAssignment(
  contextId,
  {
    async loadAssigned(id) {
      const [current, tree] = await Promise.all([fetchRoleDeptIds(id), fetchDeptTree()])
      const flat = flattenDeptTree((tree.items ?? []) as DeptTreeNode[])
      const index = new Map<string, AssignedLabel>()
      for (const item of flat) index.set(item.value, { id: item.value, label: item.label.replace(/\u3000/g, '') })
      deptNames.value = index
      treeData.value = toDeptTreeData((tree.items ?? []) as DeptTreeNode[])
      const ids = (current.dept_ids ?? []).map((deptId) => String(deptId))
      return { ids, labels: [...index.values()] }
    },
    async submit(id, ids) {
      await assignRoleDepts(id, { dept_ids: toIdParamList(ids) })
    },
  },
  { registrar, segment: { key: 'role_depts', idsField: 'dept_ids' } },
)

/**
 * 树勾选变化（精确匹配：只取勾选节点本身，不含半选父级）。
 *
 * @param info 树勾选状态（`checkedKeys` 为可提交的标识集合）。
 */
function onTreeCheck(info: { checkedKeys: (string | number)[] }): void {
  assignment.picked.value = info.checkedKeys.map((item) => String(item))
}

/**
 * 把当前勾选回填到树（弹窗打开时同步）。
 *
 * @param keys 勾选标识集合。
 */
function syncTreeChecked(keys: string[]): void {
  treeRef.value?.setCheckedKeys(keys)
}

/** 重新载入（已分配 + 部门树）。 */
async function reload(): Promise<void> {
  if (contextId.value === '') return
  await assignment.reload()
}

// 宿主记录页签切换角色（上下文变化）→ 重新载入
watch(roleId, (value) => {
  contextId.value = value ?? ''
  deptNames.value = new Map()
  void reload()
})

onMounted(() => {
  void reload()
})

defineExpose({ syncTreeChecked })
</script>

<template>
  <div class="mdm-org-slot" data-test="slot-role-depts">
    <assign-panel
      title-key="mdmOrg.slot.roleDepts.title"
      target-label="部门"
      :context-id="contextId"
      :assigned-rows="assignment.assignedRows.value"
      :picked="assignment.picked.value"
      :loading="assignment.loading.value"
      :submitting="assignment.submitting.value"
      :error-text="assignment.errorText.value"
      :dirty="assignment.dirty.value"
      :host-bound="assignment.hostBound.value"
      @update:picked="assignment.picked.value = $event"
      @submit="assignment.applyDraft()"
      @reload="reload"
    >
      <template #picker>
        <p class="mdm-org-slot__hint" data-test="slot-role-depts-hint">{{ t('mdmOrg.slot.deptExactHint') }}</p>
        <el-tree
          ref="treeRef"
          :data="treeData"
          :props="{ label: 'label', children: 'children' }"
          node-key="id"
          show-checkbox
          check-strictly
          default-expand-all
          data-test="slot-role-depts-tree"
          @check="(_node: unknown, info: { checkedKeys: (string | number)[] }) => onTreeCheck(info)"
        />
      </template>
    </assign-panel>
  </div>
</template>

<style scoped>
.mdm-org-slot__hint {
  margin: 0 0 var(--bms-space-2);
  color: var(--bms-color-text-secondary);
  font-size: var(--bms-font-size-sm);
}
</style>
