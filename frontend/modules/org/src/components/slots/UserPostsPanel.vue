<script setup lang="ts">
// 插件：岗位分配（用户侧；挂宿主「用户分配」页签内的 `sys.user.detail.tabs`）。
//
// **上下文通道＝路由参数**：宿主页把作用实体标识放路由参数（`/sys/users/:id`），
// 插件经模块持有的宿主注入 `router`（只读）读取——宿主页不感知插件、插件不 import 宿主页。
// 分配经**弹窗**（部门筛选 + 岗位多选）、**全量覆盖**、**即时提交**；单条解绑带二次确认（见 AssignPanel）。
import { ElCheckbox, ElOption, ElSelect } from 'element-plus'
import { useModuleSlotField } from '@bms/ui-ep'
import { onMounted, ref, watch } from 'vue'

import { useOrgI18n } from '../../composables/useOrgI18n'
import { useAssignment, type AssignedLabel, type HostSubmitterRegistrar } from '../../composables/useAssignment'
import { flattenDeptTree, toIdParamList, type DeptTreeNode, type DomainOption } from '../../domain'
import { hostRouteParam, isApiAbsent } from '../../runtime'
import {
  assignUserPosts,
  fetchDeptTree,
  fetchPostPage,
  fetchUserPostIds,
  setPrimaryUserPost,
} from '../../services/org-service'

import AssignPanel from './AssignPanel.vue'

const { t } = useOrgI18n()

/** 作用实体标识（用户 id；路由参数通道）。 */
const userIdField = useModuleSlotField<string>('userId')
const registrar = useModuleSlotField<HostSubmitterRegistrar>('registerSubmitter')
const userId = ref(userIdField.value ?? hostRouteParam('id'))

/** 岗位名称索引（已分配项回显；与弹窗筛选解耦）。 */
const postNames = ref(new Map<string, AssignedLabel>())
/** 候选岗位（弹窗内；按部门筛选）。 */
const options = ref<DomainOption[]>([])
/** 部门筛选项（树展平）。 */
const deptOptions = ref<DomainOption[]>([])
/** 当前部门筛选（空串＝全部）。 */
const deptFilter = ref('')

const assignment = useAssignment(userId, {
  async loadAssigned(id) {
    const [current, page] = await Promise.all([fetchUserPostIds(id), fetchPostPage({ page: 1, size: 200 })])
    const index = new Map(postNames.value)
    for (const post of page.list) {
      index.set(String(post.id), { id: String(post.id), label: post.name, description: post.code })
    }
    postNames.value = index
    return {
      ids: (current.post_ids ?? []).map((postId) => String(postId)),
      labels: [...index.values()],
      primary: current.primary_post_id ?? '',
    }
  },
  async submit(id, ids) {
    await assignUserPosts(id, { post_ids: toIdParamList(ids) })
  },
  async submitPrimary(id, primaryId) {
    await setPrimaryUserPost(id, primaryId ?? '')
  },
}, { registrar })

/** 载入候选岗位（按部门筛选）；失败即降级提示（不抛出）。 */
async function loadOptions(): Promise<void> {
  try {
    const page = await fetchPostPage({
      page: 1,
      size: 200,
      ...(deptFilter.value === '' ? {} : { dept_id: deptFilter.value }),
    })
    options.value = page.list.map((post) => ({ value: String(post.id), label: post.name }))
  } catch (caught) {
    options.value = []
    assignment.errorText.value = isApiAbsent(caught) ? t('mdmOrg.common.apiAbsent') : t('mdmOrg.common.failed')
  }
}

/** 载入部门筛选候选；失败即降级（不阻塞已分配列表）。 */
async function loadDeptOptions(): Promise<void> {
  try {
    const tree = await fetchDeptTree()
    deptOptions.value = flattenDeptTree((tree.items ?? []) as DeptTreeNode[])
  } catch {
    deptOptions.value = []
  }
}

/** 重新载入（已分配 + 候选）；上下文缺失即短路（**不请求**，插件自行降级）。 */
async function reload(): Promise<void> {
  if (userId.value === '') return
  await Promise.all([assignment.reload(), loadOptions(), loadDeptOptions()])
}

watch(userIdField, (value) => {
  userId.value = value ?? hostRouteParam('id')
  void reload()
})

watch(deptFilter, () => {
  void loadOptions()
})

onMounted(() => {
  userId.value = userIdField.value ?? hostRouteParam('id')
  void reload()
})
</script>

<template>
  <div class="mdm-org-slot" data-test="slot-user-posts">
    <assign-panel
      title-key="mdmOrg.slot.userPosts.title"
      target-label="岗位"
      :context-id="userId"
      :assigned-rows="assignment.assignedRows.value"
      :picked="assignment.picked.value"
      :loading="assignment.loading.value"
      :submitting="assignment.submitting.value"
      :error-text="assignment.errorText.value"
      :primary="assignment.primary.value"
      :show-primary="true"
      :dirty="assignment.dirty.value"
      :host-bound="assignment.hostBound.value"
      @update:picked="assignment.picked.value = $event"
      @update:primary="assignment.primary.value = $event"
      @submit="assignment.applyDraft()"
      @reload="reload"
    >
      <template #picker>
        <div class="mdm-org-slot__filter">
          <el-select
            v-model="deptFilter"
            clearable
            :placeholder="t('mdmOrg.slot.filterDept')"
            data-test="slot-user-posts-dept-filter"
          >
            <el-option v-for="item in deptOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </div>
        <p class="mdm-org-slot__hint" data-test="slot-user-posts-chain">
          {{ t('mdmOrg.slot.userPosts.chain') }}
        </p>
        <div class="mdm-org-slot__candidates" data-test="slot-user-posts-candidates">
          <el-checkbox
            v-for="item in options"
            :key="item.value"
            :model-value="assignment.picked.value.includes(item.value)"
            @update:model-value="
              (checked: string | number | boolean) => {
                const next = new Set(assignment.picked.value)
                if (checked === true) next.add(item.value)
                else next.delete(item.value)
                assignment.picked.value = [...next]
              }
            "
          >
            {{ item.label }}
          </el-checkbox>
        </div>
      </template>
    </assign-panel>
  </div>
</template>

<style scoped>
.mdm-org-slot__filter {
  margin-bottom: var(--bms-space-2);
}

.mdm-org-slot__hint {
  margin: 0 0 var(--bms-space-2);
  color: var(--bms-color-text-secondary);
  font-size: var(--bms-font-size-sm);
}

.mdm-org-slot__candidates {
  display: flex;
  flex-direction: column;
  gap: var(--bms-space-1);
  max-height: 320px;
  overflow: auto;
}
</style>
