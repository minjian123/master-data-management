<script setup lang="ts">
// 插件：岗位分配（挂宿主「角色分配」页签 `sys.role.detail.assign`）。
//
// **上下文通道＝显式上下文注入**：该页签非路由承载（表单框架记录页签、无 `:id` 路由参数），
// 宿主页经插槽件 `context` 注入角色标识，插件经 `useModuleSlotField('roleId')` **只读取得**；
// 缺失即降级（不请求），不阻塞宿主页其余部分。分配经弹窗（部门筛选 + 岗位多选）、全量覆盖、即时提交。
import { ElCheckbox, ElOption, ElSelect } from 'element-plus'
import { useModuleSlotField } from '@bms/ui-ep'
import { onMounted, ref, watch } from 'vue'

import { useOrgI18n } from '../../composables/useOrgI18n'
import { useAssignment, type AssignedLabel } from '../../composables/useAssignment'
import { flattenDeptTree, toIdParamList, type DeptTreeNode, type DomainOption } from '../../domain'
import { isApiAbsent } from '../../runtime'
import {
  assignRolePosts,
  fetchDeptTree,
  fetchPostPage,
  fetchRolePostIds,
  unassignRolePost,
} from '../../services/org-service'

import AssignPanel from './AssignPanel.vue'

const { t } = useOrgI18n()

/** 角色标识（宿主页显式上下文注入；缺失为空串 → 降级）。 */
const roleId = useModuleSlotField<string>('roleId')
const contextId = ref(roleId.value ?? '')

/** 岗位名称索引（已分配项回显）。 */
const postNames = ref(new Map<string, AssignedLabel>())
/** 候选岗位（弹窗内；按部门筛选）。 */
const options = ref<DomainOption[]>([])
/** 部门筛选项。 */
const deptOptions = ref<DomainOption[]>([])
/** 当前部门筛选（空串＝全部）。 */
const deptFilter = ref('')

const assignment = useAssignment(contextId, {
  async loadAssigned(id) {
    const [current, page] = await Promise.all([fetchRolePostIds(id), fetchPostPage({ page: 1, size: 200 })])
    const index = new Map(postNames.value)
    for (const post of page.list) {
      index.set(String(post.id), { id: String(post.id), label: post.name, description: post.code })
    }
    postNames.value = index
    return { ids: (current.post_ids ?? []).map((postId) => String(postId)), labels: [...index.values()] }
  },
  async submit(id, ids) {
    await assignRolePosts(id, { post_ids: toIdParamList(ids) })
  },
  async unassign(id, postId) {
    await unassignRolePost(id, postId)
  },
})

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

/** 重新载入（已分配 + 候选）。 */
async function reload(): Promise<void> {
  if (contextId.value === '') return
  await Promise.all([assignment.reload(), loadOptions(), loadDeptOptions()])
}

watch(deptFilter, () => {
  void loadOptions()
})

// 宿主记录页签切换角色（上下文变化）→ 重新载入
watch(roleId, (value) => {
  contextId.value = value ?? ''
  postNames.value = new Map()
  options.value = []
  void reload()
})

onMounted(() => {
  void reload()
})
</script>

<template>
  <div class="mdm-org-slot" data-test="slot-role-posts">
    <assign-panel
      title-key="mdmOrg.slot.rolePosts.title"
      target-label="岗位"
      :context-id="contextId"
      :assigned-rows="assignment.assignedRows.value"
      :picked="assignment.picked.value"
      :loading="assignment.loading.value"
      :submitting="assignment.submitting.value"
      :error-text="assignment.errorText.value"
      @update:picked="assignment.picked.value = $event"
      @submit="assignment.save($event)"
      @unassign="assignment.unbind($event)"
      @reload="reload"
    >
      <template #picker>
        <div class="mdm-org-slot__filter">
          <el-select
            v-model="deptFilter"
            clearable
            :placeholder="t('mdmOrg.slot.filterDept')"
            data-test="slot-role-posts-dept-filter"
          >
            <el-option v-for="item in deptOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </div>
        <div class="mdm-org-slot__candidates" data-test="slot-role-posts-candidates">
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

.mdm-org-slot__candidates {
  display: flex;
  flex-direction: column;
  gap: var(--bms-space-1);
  max-height: 320px;
  overflow: auto;
}
</style>
