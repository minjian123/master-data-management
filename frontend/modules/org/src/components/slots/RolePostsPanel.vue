<script setup lang="ts">
// 插件：岗位分配（挂宿主「角色分配」页签 `sys.role.detail.assign`）。
//
// **上下文通道＝显式上下文注入**：该页签非路由承载（表单框架记录页签、无 `:id` 路由参数），
// 宿主页经插槽件 `context` 注入角色标识，插件经 `useModuleSlotField('roleId')` **只读取得**；
// 缺失即降级（不请求），不阻塞宿主页其余部分。
import { useModuleSlotField } from '@bms/ui-ep'
import { onMounted, ref, watch } from 'vue'

import { useOrgI18n } from '../../composables/useOrgI18n'
import { toIdParamList } from '../../domain'
import { isApiAbsent } from '../../runtime'
import { assignRolePosts, fetchPostPage, fetchRolePostIds } from '../../services/org-service'

import AssignPanel, { type AssignTargetOption } from './AssignPanel.vue'

const { t } = useOrgI18n()

/** 角色标识（宿主页显式上下文注入；未注入为 `undefined` → 降级）。 */
const roleId = useModuleSlotField<string>('roleId')

/** 候选岗位。 */
const options = ref<AssignTargetOption[]>([])
/** 已分配岗位。 */
const assigned = ref<string[]>([])
const loading = ref(false)
const submitting = ref(false)
/** 降级提示。 */
const degraded = ref('')

/** 当前角色标识（空串表示上下文缺失）。 */
function currentRoleId(): string {
  return roleId.value ?? ''
}

/** 载入候选岗位与当前分配。 */
async function reload(): Promise<void> {
  const id = currentRoleId()
  if (id === '') return
  loading.value = true
  degraded.value = ''
  try {
    const [page, current] = await Promise.all([fetchPostPage({ page: 1, size: 200 }), fetchRolePostIds(id)])
    options.value = page.list.map((item) => ({ value: String(item.id), label: item.name, description: item.code }))
    assigned.value = (current.post_ids ?? []).map((postId) => String(postId))
  } catch (caught) {
    degraded.value = isApiAbsent(caught) ? t('mdmOrg.common.apiAbsent') : t('mdmOrg.common.failed')
  } finally {
    loading.value = false
  }
}

/**
 * 提交全量分配（即时提交）。
 *
 * @param ids 岗位标识集合。
 */
async function submit(ids: string[]): Promise<void> {
  submitting.value = true
  try {
    const result = await assignRolePosts(currentRoleId(), { post_ids: toIdParamList(ids) })
    assigned.value = (result.post_ids ?? []).map((postId) => String(postId))
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  void reload()
})

// 宿主记录页签切换角色（上下文变化）时重新载入
watch(roleId, () => {
  assigned.value = []
  options.value = []
  void reload()
})
</script>

<template>
  <div class="mdm-org-slot" data-test="slot-role-posts">
    <p v-if="degraded !== ''" class="mdm-org-slot__degraded" data-test="slot-role-posts-degraded">{{ degraded }}</p>
    <assign-panel
      title-key="mdmOrg.slot.rolePosts.title"
      target-label="岗位"
      :context-id="currentRoleId()"
      :options="options"
      :assigned="assigned"
      :loading="loading"
      :submitting="submitting"
      :on-submit="submit"
      @reload="reload"
      @update:assigned="assigned = $event"
    />
  </div>
</template>

<style scoped>
.mdm-org-slot__degraded {
  margin: 0 0 var(--bms-space-2);
  color: var(--bms-color-text-secondary);
  font-size: var(--bms-font-size-sm);
}
</style>
