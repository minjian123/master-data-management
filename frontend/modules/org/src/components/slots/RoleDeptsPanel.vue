<script setup lang="ts">
// 插件：部门分配（挂宿主「角色分配」页签 `sys.role.detail.assign`）。
//
// 与「岗位分配」同一上下文通道（**显式上下文注入**，`roleId`）；差别在目标为**部门**，
// 且语义为**精确匹配**（不含子部门）——按该域口径，勾选即选中该部门本身，不级联子树。
import { EmptyState, useModuleSlotField } from '@bms/ui-ep'
import { onMounted, ref, watch } from 'vue'

import { useOrgI18n } from '../../composables/useOrgI18n'
import { toIdParamList } from '../../domain'
import { isApiAbsent } from '../../runtime'
import { assignRoleDepts, fetchDeptTree, fetchRoleDeptIds } from '../../services/org-service'

import AssignPanel, { type AssignTargetOption } from './AssignPanel.vue'

const { t } = useOrgI18n()

/** 角色标识（宿主页显式上下文注入）。 */
const roleId = useModuleSlotField<string>('roleId')

/** 候选部门（树展平；缩进体现层级）。 */
const options = ref<AssignTargetOption[]>([])
/** 已分配部门。 */
const assigned = ref<string[]>([])
const loading = ref(false)
const submitting = ref(false)
/** 降级提示。 */
const degraded = ref('')

/** 当前角色标识（空串表示上下文缺失）。 */
function currentRoleId(): string {
  return roleId.value ?? ''
}

/**
 * 部门树展平（带层级缩进；`check-strictly` 口径＝精确匹配，不级联）。
 *
 * @param nodes 树节点。
 * @param depth 深度。
 * @returns 展平选项。
 */
function flatten(
  nodes: readonly { id: unknown; name: string; children?: readonly unknown[] }[],
  depth = 0,
): AssignTargetOption[] {
  const result: AssignTargetOption[] = []
  for (const node of nodes) {
    result.push({ value: String(node.id), label: `${'　'.repeat(depth)}${node.name}` })
    const children = node.children as readonly { id: unknown; name: string; children?: readonly unknown[] }[] | undefined
    if (children !== undefined && children.length > 0) {
      result.push(...flatten(children, depth + 1))
    }
  }
  return result
}

/** 载入候选部门与当前分配。 */
async function reload(): Promise<void> {
  const id = currentRoleId()
  if (id === '') return
  loading.value = true
  degraded.value = ''
  try {
    const [tree, current] = await Promise.all([fetchDeptTree(), fetchRoleDeptIds(id)])
    options.value = flatten(tree.items ?? [])
    assigned.value = (current.dept_ids ?? []).map((deptId) => String(deptId))
  } catch (caught) {
    degraded.value = isApiAbsent(caught) ? t('mdmOrg.common.apiAbsent') : t('mdmOrg.common.failed')
  } finally {
    loading.value = false
  }
}

/**
 * 提交全量分配（即时提交；精确匹配语义）。
 *
 * @param ids 部门标识集合。
 */
async function submit(ids: string[]): Promise<void> {
  submitting.value = true
  try {
    const result = await assignRoleDepts(currentRoleId(), { dept_ids: toIdParamList(ids) })
    assigned.value = (result.dept_ids ?? []).map((deptId) => String(deptId))
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  void reload()
})

watch(roleId, () => {
  assigned.value = []
  options.value = []
  void reload()
})
</script>

<template>
  <div class="mdm-org-slot" data-test="slot-role-depts">
    <p v-if="degraded !== ''" class="mdm-org-slot__degraded" data-test="slot-role-depts-degraded">{{ degraded }}</p>
    <empty-state
      v-if="currentRoleId() === ''"
      type="data"
      :title="t('mdmOrg.slot.contextAbsent')"
      data-test="slot-role-depts-absent"
    />
    <template v-else>
      <p class="mdm-org-slot__hint">{{ t('mdmOrg.slot.deptExactHint') }}</p>
      <assign-panel
        title-key="mdmOrg.slot.roleDepts.title"
        target-label="部门"
        :context-id="currentRoleId()"
        :options="options"
        :assigned="assigned"
        :loading="loading"
        :submitting="submitting"
        :on-submit="submit"
        @reload="reload"
        @update:assigned="assigned = $event"
      />
    </template>
  </div>
</template>

<style scoped>
.mdm-org-slot__degraded,
.mdm-org-slot__hint {
  margin: 0 0 var(--bms-space-2);
  color: var(--bms-color-text-secondary);
  font-size: var(--bms-font-size-sm);
}
</style>
