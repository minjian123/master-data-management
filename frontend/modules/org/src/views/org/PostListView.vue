<script setup lang="ts">
// 岗位管理页：关键字 / 所属部门（含子级）/ 状态筛选 + 列表（多选批量删除 / 行内编辑·启停·删除）+
// 「绑定角色」入口（**只读**：岗位侧角色绑定写端点属角色分配域，见按钮说明）+ 双击行打开岗位表单页。
// 列表与分页复用平台件 `DataTable`（与服务端分页契约 `{ list, total, page, size }` 对齐）。
import { DataTable, PageContainer, SectionContainer } from '@bms/ui-ep'
import type { DataTableColumn } from '@bms/ui-ep'
import { ElButton, ElDialog, ElInput, ElMessage, ElMessageBox, ElOption, ElSelect, ElTag } from 'element-plus'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useOrgI18n } from '../../composables/useOrgI18n'
import {
  ENTITY_STATUS,
  STATUS_OPTIONS,
  flattenDeptTree,
  type DeptTreeNode,
  type DomainOption,
  type PostItem,
  type PostQuery,
} from '../../domain'
import { isApiAbsent, orgRuntime } from '../../runtime'
import { deletePost, fetchDeptTree, fetchPostPage, fetchPostRoleIds, updatePost } from '../../services/org-service'

defineOptions({ name: 'MdmOrgPostList' })

const router = useRouter()
const { t } = useOrgI18n()
const runtime = orgRuntime()

const list = ref<PostItem[]>([])
const total = ref(0)
const loading = ref(false)
const errorText = ref('')
/** 部门选项（树展平，用于筛选与列显示）。 */
const deptOptions = ref<DomainOption[]>([])
/** 已勾选行键（多选批量操作）。 */
const selectedKeys = ref<string[]>([])
/** 关键字输入（点「查询」才生效）。 */
const keywordInput = ref('')
/** 查询条件。 */
const query = ref<PostQuery>({ page: 1, size: 10 })

/** 绑定角色弹窗（只读视图）。 */
const rolesVisible = ref(false)
const rolesTarget = ref<PostItem | null>(null)
const boundRoleIds = ref<string[]>([])

const columns = computed<DataTableColumn[]>(() => [
  { key: 'code', title: t('mdmOrg.post.column.code'), width: 160 },
  { key: 'name', title: t('mdmOrg.post.column.name'), minWidth: 160, sortable: true },
  { key: 'dept_id', title: t('mdmOrg.post.column.dept'), width: 200 },
  { key: 'status', title: t('mdmOrg.post.column.status'), width: 110 },
])

/** 写权限（显隐只是体验，后端强制校验）。 */
const canUpdate = computed(() => runtime.canUpdate)

/** 载入岗位分页。 */
async function load(): Promise<void> {
  loading.value = true
  errorText.value = ''
  try {
    const page = await fetchPostPage(query.value)
    list.value = page.list
    total.value = page.total ?? 0
    selectedKeys.value = []
  } catch (caught) {
    errorText.value = isApiAbsent(caught) ? t('mdmOrg.common.apiAbsent') : t('mdmOrg.common.failed')
  } finally {
    loading.value = false
  }
}

/** 载入部门选项（筛选与显示）。 */
async function loadDepts(): Promise<void> {
  try {
    const tree = await fetchDeptTree()
    deptOptions.value = flattenDeptTree((tree.items ?? []) as DeptTreeNode[])
  } catch {
    // 选项失败不阻塞列表
  }
}

/**
 * 翻页。
 *
 * @param next 页码。
 */
async function onPageChange(next: number): Promise<void> {
  query.value = { ...query.value, page: next }
  await load()
}

/**
 * 改页长。
 *
 * @param next 页长。
 */
async function onPageSizeChange(next: number): Promise<void> {
  query.value = { ...query.value, page: 1, size: next }
  await load()
}

/**
 * 筛选条件变化（回第 1 页）。
 *
 * @param patch 条件增量。
 */
async function onFilter(patch: Partial<PostQuery>): Promise<void> {
  query.value = { ...query.value, ...patch, page: 1 }
  await load()
}

/** 查询（关键字生效）。 */
async function onSearch(): Promise<void> {
  const trimmed = keywordInput.value.trim()
  await onFilter({ keyword: trimmed === '' ? undefined : trimmed })
}

/** 重置筛选。 */
async function onReset(): Promise<void> {
  keywordInput.value = ''
  query.value = { page: 1, size: query.value.size }
  await load()
}

/**
 * 勾选变化。
 *
 * @param keys 勾选行键。
 */
function onSelectionChange(keys: string[]): void {
  selectedKeys.value = keys
}

/** 新建岗位。 */
function openCreate(): void {
  void router.push({ name: 'MdmOrgPostForm' })
}

/**
 * 编辑岗位。
 *
 * @param row 行数据。
 */
function openEdit(row: Record<string, unknown>): void {
  void router.push({ name: 'MdmOrgPostForm', params: { id: String(row.id) } })
}

/**
 * 启停岗位（立即生效）。
 *
 * @param row 行数据。
 */
async function onToggleStatus(row: PostItem): Promise<void> {
  try {
    await updatePost(String(row.id), {
      status: row.status === ENTITY_STATUS.enabled ? ENTITY_STATUS.disabled : ENTITY_STATUS.enabled,
    })
    ElMessage.success(t('mdmOrg.common.save'))
    await load()
  } catch (caught) {
    ElMessage.error(isApiAbsent(caught) ? t('mdmOrg.common.apiAbsent') : t('mdmOrg.common.failed'))
  }
}

/**
 * 删除岗位（二次确认）。
 *
 * @param row 行数据。
 */
async function onDelete(row: PostItem): Promise<void> {
  await ElMessageBox.confirm(t('mdmOrg.post.delete.confirm'), t('mdmOrg.common.delete'), {
    confirmButtonText: t('mdmOrg.common.confirm'),
    cancelButtonText: t('mdmOrg.common.cancel'),
    type: 'warning',
  })
  try {
    await deletePost(String(row.id))
    ElMessage.success(t('mdmOrg.common.delete'))
    await load()
  } catch (caught) {
    ElMessage.error(isApiAbsent(caught) ? t('mdmOrg.common.apiAbsent') : t('mdmOrg.common.failed'))
  }
}

/** 批量删除（按勾选行逐个删除，逐条失败不阻塞其余）。 */
async function onBatchDelete(): Promise<void> {
  if (selectedKeys.value.length === 0) return
  await ElMessageBox.confirm(
    t('mdmOrg.post.batchDelete.confirm', { count: selectedKeys.value.length }),
    t('mdmOrg.common.delete'),
    {
      confirmButtonText: t('mdmOrg.common.confirm'),
      cancelButtonText: t('mdmOrg.common.cancel'),
      type: 'warning',
    },
  )
  let failed = 0
  for (const id of selectedKeys.value) {
    try {
      await deletePost(id)
    } catch {
      failed += 1
    }
  }
  if (failed === 0) ElMessage.success(t('mdmOrg.common.delete'))
  else ElMessage.error(t('mdmOrg.post.batchDelete.partial', { failed }))
  await load()
}

/**
 * 绑定角色（**只读**视图：展示该岗位已绑角色；写侧归角色管理「角色分配」）。
 *
 * @param row 行数据。
 */
async function openRoles(row: PostItem): Promise<void> {
  rolesTarget.value = row
  boundRoleIds.value = []
  rolesVisible.value = true
  try {
    const result = await fetchPostRoleIds(String(row.id))
    boundRoleIds.value = (result.role_ids ?? []).map((roleId) => String(roleId))
  } catch (caught) {
    ElMessage.error(isApiAbsent(caught) ? t('mdmOrg.common.apiAbsent') : t('mdmOrg.common.failed'))
  }
}

onMounted(async () => {
  await Promise.all([load(), loadDepts()])
})
</script>

<template>
  <page-container :title="t('mdmOrg.post.list.title')" :description="t('mdmOrg.post.list.description')">
    <section-container>
      <div class="mdm-org-post__filters">
        <el-input
          v-model="keywordInput"
          clearable
          :placeholder="t('mdmOrg.post.filter.keyword')"
          data-test="post-filter-keyword"
          @keyup.enter="onSearch"
        />
        <el-select
          :model-value="query.dept_id ?? ''"
          clearable
          :placeholder="t('mdmOrg.post.filter.dept')"
          data-test="post-filter-dept"
          @update:model-value="onFilter({ dept_id: String($event) })"
        >
          <el-option v-for="item in deptOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select
          :model-value="query.status ?? ''"
          clearable
          :placeholder="t('mdmOrg.post.filter.status')"
          data-test="post-filter-status"
          @update:model-value="onFilter({ status: String($event) })"
        >
          <el-option v-for="item in STATUS_OPTIONS" :key="item.value" :label="t(item.labelKey)" :value="item.value" />
        </el-select>
        <el-button type="primary" data-test="post-search" @click="onSearch">{{ t('mdmOrg.post.filter.search') }}</el-button>
        <el-button data-test="post-reset" @click="onReset">{{ t('mdmOrg.post.filter.reset') }}</el-button>
      </div>
    </section-container>

    <section-container>
      <data-table
        :ready="true"
        :columns="columns"
        :data="list"
        :total="total"
        :page="query.page ?? 1"
        :page-size="query.size ?? 10"
        :loading="loading"
        :error="errorText"
        row-key="id"
        selectable
        form-key="mdm_org_post_list"
        :empty-text="t('mdmOrg.post.list.empty')"
        @update:page="onPageChange"
        @update:page-size="onPageSizeChange"
        @selection-change="onSelectionChange"
        @row-dblclick="openEdit"
        @refresh="load"
        @retry="load"
      >
        <template #toolbar>
          <el-button v-if="canUpdate" type="primary" data-test="post-create" @click="openCreate">
            {{ t('mdmOrg.post.list.create') }}
          </el-button>
          <el-button
            v-if="canUpdate"
            type="danger"
            :disabled="selectedKeys.length === 0"
            data-test="post-batch-delete"
            @click="onBatchDelete"
          >
            {{ t('mdmOrg.post.action.batchDelete') }}
          </el-button>
          <el-button
            :disabled="selectedKeys.length !== 1"
            data-test="post-bind-roles"
            @click="openRoles(list.find((item) => String(item.id) === selectedKeys[0]) as PostItem)"
          >
            {{ t('mdmOrg.post.action.bindRoles') }}
          </el-button>
          <el-button data-test="post-refresh" @click="load">{{ t('mdmOrg.common.refresh') }}</el-button>
        </template>
        <template #cell-status="{ row }">
          <el-tag size="small" :type="(row as unknown as PostItem).status === 'enabled' ? 'success' : 'info'">
            {{ (row as unknown as PostItem).status === 'enabled' ? t('mdmOrg.common.enabled') : t('mdmOrg.common.disabled') }}
          </el-tag>
        </template>
        <template #cell-actions="{ row }">
          <template v-if="canUpdate">
            <el-button link type="primary" :data-test="`post-edit-${(row as unknown as PostItem).id}`" @click="openEdit(row)">
              {{ t('mdmOrg.common.edit') }}
            </el-button>
            <el-button link :data-test="`post-toggle-${(row as unknown as PostItem).id}`" @click="onToggleStatus(row as unknown as PostItem)">
              {{
                (row as unknown as PostItem).status === 'enabled'
                  ? t('mdmOrg.common.disabled')
                  : t('mdmOrg.common.enabled')
              }}
            </el-button>
            <el-button link type="danger" :data-test="`post-delete-${(row as unknown as PostItem).id}`" @click="onDelete(row as unknown as PostItem)">
              {{ t('mdmOrg.common.delete') }}
            </el-button>
          </template>
        </template>
      </data-table>
    </section-container>

    <el-dialog v-model="rolesVisible" :title="t('mdmOrg.post.roles.title')" width="480" align-center>
      <p class="mdm-org-post__hint" data-test="post-roles-hint">{{ t('mdmOrg.post.roles.readonlyHint') }}</p>
      <el-tag v-for="role in boundRoleIds" :key="role" class="mdm-org-post__role" size="small">{{ role }}</el-tag>
      <span v-if="boundRoleIds.length === 0" data-test="post-roles-empty">{{ t('mdmOrg.common.empty') }}</span>
      <template #footer>
        <el-button data-test="post-roles-close" @click="rolesVisible = false">{{ t('mdmOrg.common.confirm') }}</el-button>
      </template>
    </el-dialog>
  </page-container>
</template>

<style scoped>
.mdm-org-post__filters {
  display: flex;
  gap: var(--bms-space-2);
}

.mdm-org-post__hint {
  margin: 0 0 var(--bms-space-2);
  color: var(--bms-color-text-secondary);
  font-size: var(--bms-font-size-sm);
}

.mdm-org-post__role {
  margin-right: var(--bms-space-1);
}
</style>
