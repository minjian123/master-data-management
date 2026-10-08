<script setup lang="ts">
// 部门管理页：组织架构树 + 选中部门详情（只读的用户 / 角色）+ 新建 / 编辑 / 移动 / 删除。
// 数据经**产品域寻址** `api.product('mdm', 'org')`（见 services/org-service）；模块不自建 HTTP、不自拼前缀。
import { EmptyState, PageContainer, SectionContainer } from '@bms/ui-ep'
import { ElButton, ElMessage, ElMessageBox, ElTag, ElTree } from 'element-plus'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useOrgI18n } from '../../composables/useOrgI18n'
import { toIdParam, type DeptTreeNode } from '../../domain'
import { isApiAbsent, orgRuntime } from '../../runtime'
import {
  deleteDept,
  fetchDeptRoleIds,
  fetchDeptTree,
  fetchDeptUserIds,
  moveDept,
} from '../../services/org-service'

defineOptions({ name: 'MdmOrgDeptList' })

const router = useRouter()
const { t } = useOrgI18n()
const runtime = orgRuntime()

/** 部门树。 */
const tree = ref<DeptTreeNode[]>([])
/** 选中部门（详情区）。 */
const selected = ref<DeptTreeNode | null>(null)
/** 选中部门下用户 / 角色标识（只读）。 */
const userIds = ref<string[]>([])
const roleIds = ref<string[]>([])
const loading = ref(false)
/** 降级 / 错误提示。 */
const notice = ref('')

/** 树组件 props（`children` 字段与契约一致）。 */
const treeProps = { label: 'name', children: 'children' }

/** 是否有写权限（显隐只是体验，后端强制校验）。 */
const canUpdate = computed(() => runtime.canUpdate)

/** 载入部门树。 */
async function load(): Promise<void> {
  loading.value = true
  notice.value = ''
  try {
    const result = await fetchDeptTree()
    tree.value = (result.items ?? []) as DeptTreeNode[]
    if (selected.value !== null) {
      const hit = findNode(tree.value, String(selected.value.id))
      selected.value = hit ?? null
    }
  } catch (caught) {
    notice.value = isApiAbsent(caught) ? t('mdmOrg.common.apiAbsent') : t('mdmOrg.common.failed')
  } finally {
    loading.value = false
  }
}

/**
 * 树内查找节点。
 *
 * @param nodes 树节点。
 * @param id 部门标识。
 * @returns 命中节点（未命中为 `null`）。
 */
function findNode(nodes: readonly DeptTreeNode[], id: string): DeptTreeNode | null {
  for (const node of nodes) {
    if (String(node.id) === id) return node
    const hit = findNode((node.children ?? []) as DeptTreeNode[], id)
    if (hit !== null) return hit
  }
  return null
}

/**
 * 选中部门（载入只读的用户 / 角色）。
 *
 * @param node 树节点。
 */
async function onSelect(node: DeptTreeNode): Promise<void> {
  selected.value = node
  userIds.value = []
  roleIds.value = []
  try {
    const [users, roles] = await Promise.all([fetchDeptUserIds(String(node.id)), fetchDeptRoleIds(String(node.id))])
    userIds.value = (users.user_ids ?? []).map((id) => String(id))
    roleIds.value = (roles.role_ids ?? []).map((id) => String(id))
  } catch {
    // 只读区失败不阻塞主流程（详情区给出空态）
  }
}

/** 新建（无选中时为根部门）。 */
function openCreate(): void {
  void router.push({ name: 'MdmOrgDeptForm', query: { parent: selected.value === null ? '' : String(selected.value.id) } })
}

/** 编辑选中部门。 */
function openEdit(): void {
  if (selected.value === null) return
  void router.push({ name: 'MdmOrgDeptForm', params: { id: String(selected.value.id) } })
}

/** 移动选中部门（对话框选目标）。 */
async function onMove(): Promise<void> {
  if (selected.value === null) return
  const target = await ElMessageBox.prompt(t('mdmOrg.dept.move.target'), t('mdmOrg.dept.move.title'), {
    inputPlaceholder: t('mdmOrg.dept.form.root'),
    confirmButtonText: t('mdmOrg.common.confirm'),
    cancelButtonText: t('mdmOrg.common.cancel'),
  })
  try {
    await moveDept(String(selected.value.id), { parent_id: toIdParam(target.value.trim()) })
    ElMessage.success(t('mdmOrg.common.save'))
    await load()
  } catch (caught) {
    ElMessage.error(isApiAbsent(caught) ? t('mdmOrg.common.apiAbsent') : t('mdmOrg.common.failed'))
  }
}

/** 删除选中部门。 */
async function onDelete(): Promise<void> {
  if (selected.value === null) return
  await ElMessageBox.confirm(t('mdmOrg.dept.delete.confirm'), t('mdmOrg.common.delete'), {
    confirmButtonText: t('mdmOrg.common.confirm'),
    cancelButtonText: t('mdmOrg.common.cancel'),
    type: 'warning',
  })
  try {
    await deleteDept(String(selected.value.id))
    ElMessage.success(t('mdmOrg.common.delete'))
    selected.value = null
    await load()
  } catch (caught) {
    ElMessage.error(isApiAbsent(caught) ? t('mdmOrg.common.apiAbsent') : t('mdmOrg.common.failed'))
  }
}

onMounted(load)
</script>

<template>
  <page-container :title="t('mdmOrg.dept.list.title')" :description="t('mdmOrg.dept.list.description')">
    <section-container>
      <div class="mdm-org-dept__toolbar">
        <el-button v-if="canUpdate" type="primary" data-test="dept-create" @click="openCreate">
          {{ t('mdmOrg.dept.list.create') }}
        </el-button>
        <el-button data-test="dept-refresh" @click="load">{{ t('mdmOrg.common.refresh') }}</el-button>
      </div>
      <p v-if="notice !== ''" class="mdm-org-dept__notice" data-test="dept-notice">{{ notice }}</p>
    </section-container>

    <section-container :title="t('mdmOrg.dept.list.title')">
      <div class="mdm-org-dept__body">
        <el-tree
          :data="tree"
          :props="treeProps"
          node-key="id"
          highlight-current
          :expand-on-click-node="false"
          data-test="dept-tree"
          @node-click="onSelect"
        />
        <div class="mdm-org-dept__detail" data-test="dept-detail">
          <empty-state v-if="selected === null" type="data" :title="t('mdmOrg.common.empty')" />
          <template v-else>
            <dl class="mdm-org-dept__meta">
              <dt>{{ t('mdmOrg.dept.column.name') }}</dt>
              <dd data-test="dept-detail-name">{{ selected.name }}</dd>
              <dt>{{ t('mdmOrg.dept.column.status') }}</dt>
              <dd>
                <el-tag size="small" :type="selected.status === 'enabled' ? 'success' : 'info'">
                  {{ selected.status === 'enabled' ? t('mdmOrg.common.enabled') : t('mdmOrg.common.disabled') }}
                </el-tag>
              </dd>
              <dt>{{ t('mdmOrg.dept.users.title') }}</dt>
              <dd data-test="dept-detail-users">{{ userIds.length }}</dd>
              <dt>{{ t('mdmOrg.dept.roles.title') }}</dt>
              <dd data-test="dept-detail-roles">{{ roleIds.length }}</dd>
            </dl>
            <div v-if="canUpdate" class="mdm-org-dept__actions">
              <el-button data-test="dept-edit" @click="openEdit">{{ t('mdmOrg.common.edit') }}</el-button>
              <el-button data-test="dept-move" @click="onMove">{{ t('mdmOrg.dept.action.move') }}</el-button>
              <el-button type="danger" data-test="dept-delete" @click="onDelete">{{ t('mdmOrg.common.delete') }}</el-button>
            </div>
          </template>
        </div>
      </div>
    </section-container>
  </page-container>
</template>

<style scoped>
.mdm-org-dept__toolbar {
  display: flex;
  gap: var(--bms-space-2);
}

.mdm-org-dept__notice {
  margin: var(--bms-space-2) 0 0;
  color: var(--bms-color-text-secondary);
  font-size: var(--bms-font-size-sm);
}

.mdm-org-dept__body {
  display: flex;
  gap: var(--bms-space-4);
}

.mdm-org-dept__detail {
  flex: 1;
  min-width: 0;
}

.mdm-org-dept__meta {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: var(--bms-space-1) var(--bms-space-2);
  margin: 0 0 var(--bms-space-3);
}

.mdm-org-dept__meta dt {
  color: var(--bms-color-text-secondary);
}

.mdm-org-dept__meta dd {
  margin: 0;
}

.mdm-org-dept__actions {
  display: flex;
  gap: var(--bms-space-2);
}
</style>
