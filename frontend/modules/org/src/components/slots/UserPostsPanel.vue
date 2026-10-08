<script setup lang="ts">
// 插件：用户分配岗位（挂宿主「用户详情」页签 `sys.user.detail.tabs`）。
//
// **上下文通道＝路由参数**：宿主页把作用实体标识放路由参数（`/sys/users/:id`），
// 插件经模块持有的宿主注入 `router`（只读）读取——宿主页不感知插件、插件不 import 宿主页。
import { onMounted, ref } from 'vue'

import { useOrgI18n } from '../../composables/useOrgI18n'
import { toIdParamList } from '../../domain'
import { hostRouteParam, isApiAbsent } from '../../runtime'
import { assignUserPosts, fetchPostPage, fetchUserPostIds } from '../../services/org-service'

import AssignPanel, { type AssignTargetOption } from './AssignPanel.vue'

const { t } = useOrgI18n()

/** 作用实体标识（用户 id）。 */
const userId = ref('')
/** 候选岗位。 */
const options = ref<AssignTargetOption[]>([])
/** 已分配岗位。 */
const assigned = ref<string[]>([])
const loading = ref(false)
const submitting = ref(false)
/** 降级提示（请求能力未注入 / 载入失败）。 */
const degraded = ref('')

/** 载入候选岗位与当前分配。 */
async function reload(): Promise<void> {
  if (userId.value === '') return
  loading.value = true
  degraded.value = ''
  try {
    const [page, current] = await Promise.all([fetchPostPage({ page: 1, size: 200 }), fetchUserPostIds(userId.value)])
    options.value = page.list.map((item) => ({ value: String(item.id), label: item.name, description: item.code }))
    assigned.value = (current.post_ids ?? []).map((id) => String(id))
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
    const result = await assignUserPosts(userId.value, { post_ids: toIdParamList(ids) })
    assigned.value = (result.post_ids ?? []).map((id) => String(id))
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  userId.value = hostRouteParam('id')
  void reload()
})
</script>

<template>
  <div class="mdm-org-slot" data-test="slot-user-posts">
    <p v-if="degraded !== ''" class="mdm-org-slot__degraded" data-test="slot-user-posts-degraded">{{ degraded }}</p>
    <assign-panel
      title-key="mdmOrg.slot.userPosts.title"
      target-label="岗位"
      :context-id="userId"
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
