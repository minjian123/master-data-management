<script setup lang="ts">
// 插件：部门分配（用户侧；挂宿主「用户分配」页签内的 `sys.user.detail.tabs`）。
//
// 与「岗位分配（用户侧）」同一上下文通道（**显式上下文注入优先、路由参数兜底**，`userId`）；语义为
// **部门多分配 + 主要部门标记**（角色解析按**全部已分配部门**，主要部门不参与解析）；弹窗内以部门树多选呈现
// （`check-strictly` 不级联，精确匹配不含下级）。改动**进草稿**：宿主提供提交器通道时随宿主保存，
// 无通道时弹窗「确定」即自提交（见 AssignPanel / useAssignment）。
import { ElTree } from 'element-plus'
import { useModuleSlotField } from '@bms/ui-ep'
import { onMounted, ref, watch } from 'vue'

import { useOrgI18n } from '../../composables/useOrgI18n'
import { useAssignment, type AssignedLabel, type HostSubmitterRegistrar } from '../../composables/useAssignment'
import { flattenDeptTree, toDeptTreeData, toIdParamList, type DeptTreeNode, type DeptTreeOption } from '../../domain'
import { hostRouteParam } from '../../runtime'
import { assignUserDepts, fetchDeptTree, fetchUserDeptIds, setPrimaryUserDept } from '../../services/org-service'

import AssignPanel from './AssignPanel.vue'

const { t } = useOrgI18n()

/** 作用实体标识（用户 id；显式上下文优先、路由参数兜底）。 */
const userIdField = useModuleSlotField<string>('userId')
const registrar = useModuleSlotField<HostSubmitterRegistrar>('registerSubmitter')
const userId = ref(userIdField.value ?? hostRouteParam('id'))

/** 部门名称索引（已分配项回显）。 */
const deptNames = ref(new Map<string, AssignedLabel>())
/** 部门树（弹窗内多选；精确匹配不级联）。 */
const treeData = ref<DeptTreeOption[]>([])
/** 树组件引用（勾选回填与取值）。 */
const treeRef = ref<InstanceType<typeof ElTree>>()

const assignment = useAssignment(
  userId,
  {
    async loadAssigned(id) {
      const [current, tree] = await Promise.all([fetchUserDeptIds(id), fetchDeptTree()])
      const flat = flattenDeptTree((tree.items ?? []) as DeptTreeNode[])
      const index = new Map<string, AssignedLabel>()
      for (const item of flat) index.set(item.value, { id: item.value, label: item.label.replace(/\u3000/g, '') })
      deptNames.value = index
      treeData.value = toDeptTreeData((tree.items ?? []) as DeptTreeNode[])
      const ids = (current.dept_ids ?? []).map((deptId) => String(deptId))
      return { ids, labels: [...index.values()], primary: current.primary_dept_id ?? '' }
    },
    async submit(id, ids) {
      await assignUserDepts(id, { dept_ids: toIdParamList(ids) })
    },
    async submitPrimary(id, primaryId) {
      await setPrimaryUserDept(id, primaryId ?? '')
    },
  },
  {
    registrar,
    segment: { key: 'user_depts', idsField: 'dept_ids', primaryField: 'primary_dept_id' },
  },
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

/** 重新载入（已分配 + 部门树）；上下文缺失即短路（**不请求**）。 */
async function reload(): Promise<void> {
  if (userId.value === '') return
  await assignment.reload()
}

// 宿主记录页签切换用户（上下文变化）→ 重新载入
watch(userIdField, (value) => {
  userId.value = value ?? hostRouteParam('id')
  deptNames.value = new Map()
  void reload()
})

onMounted(() => {
  userId.value = userIdField.value ?? hostRouteParam('id')
  void reload()
})

defineExpose({ syncTreeChecked })
</script>

<template>
  <div class="mdm-org-slot" data-test="slot-user-depts">
    <assign-panel
      title-key="mdmOrg.slot.userDepts.title"
      target-label="部门"
      :context-id="userId"
      :assigned-rows="assignment.assignedRows.value"
      :picked="assignment.picked.value"
      :primary="assignment.primary.value"
      :show-primary="true"
      :dirty="assignment.dirty.value"
      :host-bound="assignment.hostBound.value"
      :loading="assignment.loading.value"
      :submitting="assignment.submitting.value"
      :error-text="assignment.errorText.value"
      @update:picked="assignment.picked.value = $event"
      @update:primary="assignment.primary.value = $event"
      @submit="assignment.applyDraft()"
      @reload="reload"
    >
      <template #picker>
        <p class="mdm-org-slot__hint" data-test="slot-user-depts-hint">{{ t('mdmOrg.slot.deptExactHint') }}</p>
        <el-tree
          ref="treeRef"
          :data="treeData"
          :props="{ label: 'label', children: 'children' }"
          node-key="id"
          show-checkbox
          check-strictly
          default-expand-all
          :default-checked-keys="assignment.picked.value"
          data-test="slot-user-depts-tree"
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
