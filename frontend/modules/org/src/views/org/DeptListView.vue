<script setup lang="ts">
// 部门管理页：组织架构树 + 选中部门详情（**页内编辑**：修改 / 保存 / 取消，只读态↔编辑态）+
// 工具栏（新建子部门 / 移动 / 启停 / 刷新）+ 只读的直属用户与角色 + `ancestors` 链展示。
// 数据经**产品域寻址** `api.product('mdm', 'org')`（见 services/org-service）；模块不自建 HTTP、不自拼前缀。
import { EmptyState, PageContainer, SectionContainer } from '@bms/ui-ep'
import { ElButton, ElInput, ElInputNumber, ElMessage, ElMessageBox, ElOption, ElSelect, ElTag, ElTree } from 'element-plus'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useOrgI18n } from '../../composables/useOrgI18n'
import {
  ENTITY_STATUS,
  STATUS_OPTIONS,
  flattenDeptTree,
  toIdParam,
  type DeptTreeNode,
  type DomainOption,
} from '../../domain'
import { isApiAbsent, orgRuntime } from '../../runtime'
import {
  deleteDept,
  fetchDeptRoleIds,
  fetchDeptTree,
  fetchDeptUserIds,
  moveDept,
  updateDept,
} from '../../services/org-service'

defineOptions({ name: 'MdmOrgDeptList' })

const router = useRouter()
const { t } = useOrgI18n()
const runtime = orgRuntime()

/** 部门树。 */
const tree = ref<DeptTreeNode[]>([])
/** 选中部门。 */
const selected = ref<DeptTreeNode | null>(null)
/** 选中部门下用户 / 角色标识（只读）。 */
const userIds = ref<string[]>([])
const roleIds = ref<string[]>([])
const loading = ref(false)
/** 降级 / 错误提示。 */
const notice = ref('')

/** 编辑态（只读态点击「修改」进入）。 */
const editing = ref(false)
/** 编辑表单（页内）。 */
const form = ref<{ code: string; name: string; parentId: string; sort: number; status: string }>({
  code: '',
  name: '',
  parentId: '',
  sort: 0,
  status: ENTITY_STATUS.enabled,
})
/** 上级部门候选（树展平；编辑态用）。 */
const parentOptions = ref<DomainOption[]>([])

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
    parentOptions.value = flattenDeptTree(tree.value)
    if (selected.value !== null) {
      selected.value = findNode(tree.value, String(selected.value.id))
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
 * 选中部门（载入只读的用户 / 角色；退出编辑态）。
 *
 * @param node 树节点。
 */
async function onSelect(node: DeptTreeNode): Promise<void> {
  selected.value = node
  editing.value = false
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

/** 进入编辑态（表单初值＝当前值）。 */
function startEdit(): void {
  if (selected.value === null) return
  form.value = {
    code: selected.value.code,
    name: selected.value.name,
    parentId: selected.value.parent_id === null || selected.value.parent_id === undefined ? '' : String(selected.value.parent_id),
    sort: selected.value.sort,
    status: selected.value.status,
  }
  editing.value = true
}

/** 取消编辑。 */
function cancelEdit(): void {
  editing.value = false
}

/** 保存编辑（上级部门变更走移动端点；名称 / 排序 / 状态走更新端点）。 */
async function saveEdit(): Promise<void> {
  if (selected.value === null) return
  const id = String(selected.value.id)
  try {
    const originalParent = selected.value.parent_id === null || selected.value.parent_id === undefined ? '' : String(selected.value.parent_id)
    if (form.value.parentId !== originalParent) {
      await moveDept(id, { parent_id: toIdParam(form.value.parentId) })
    }
    await updateDept(id, {
      code: form.value.code,
      name: form.value.name,
      sort: form.value.sort,
      status: form.value.status,
    })
    ElMessage.success(t('mdmOrg.common.save'))
    editing.value = false
    await load()
    const hit = findNode(tree.value, id)
    if (hit !== null) await onSelect(hit)
  } catch (caught) {
    ElMessage.error(isApiAbsent(caught) ? t('mdmOrg.common.apiAbsent') : t('mdmOrg.common.failed'))
  }
}

/** 新建子部门（父级＝当前选中）。 */
function openCreate(): void {
  void router.push({
    name: 'MdmOrgDeptForm',
    query: { parent: selected.value === null ? '' : String(selected.value.id) },
  })
}

/** 打开部门表单页（原型入口：独立表单页）。 */
function openFormPage(): void {
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
    if (caught === 'cancel' || caught === 'close') return
    ElMessage.error(isApiAbsent(caught) ? t('mdmOrg.common.apiAbsent') : t('mdmOrg.common.failed'))
  }
}

/** 启停选中部门（立即生效）。 */
async function onToggleStatus(): Promise<void> {
  if (selected.value === null) return
  const next = selected.value.status === ENTITY_STATUS.enabled ? ENTITY_STATUS.disabled : ENTITY_STATUS.enabled
  try {
    await updateDept(String(selected.value.id), { status: next })
    ElMessage.success(t('mdmOrg.common.save'))
    await load()
    const hit = findNode(tree.value, String(selected.value.id))
    if (hit !== null) await onSelect(hit)
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
        <el-button :disabled="selected === null || !canUpdate" data-test="dept-move" @click="onMove">
          {{ t('mdmOrg.dept.action.move') }}
        </el-button>
        <el-button :disabled="selected === null || !canUpdate" data-test="dept-toggle" @click="onToggleStatus">
          {{ selected?.status === 'enabled' ? t('mdmOrg.common.disabled') : t('mdmOrg.common.enabled') }}
        </el-button>
        <el-button data-test="dept-refresh" @click="load">{{ t('mdmOrg.common.refresh') }}</el-button>
        <span v-if="selected !== null" class="mdm-org-dept__current" data-test="dept-current">
          {{ t('mdmOrg.dept.current', { name: selected.name }) }}
        </span>
      </div>
      <p v-if="notice !== ''" class="mdm-org-dept__notice" data-test="dept-notice">{{ notice }}</p>
    </section-container>

    <section-container>
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
            <div class="mdm-org-dept__actions">
              <el-button v-if="canUpdate && !editing" data-test="dept-edit" @click="startEdit">
                {{ t('mdmOrg.common.edit') }}
              </el-button>
              <el-button v-if="canUpdate && !editing" type="danger" data-test="dept-delete" @click="onDelete">
                {{ t('mdmOrg.common.delete') }}
              </el-button>
              <el-button data-test="dept-form-page" @click="openFormPage">{{ t('mdmOrg.dept.form.open') }}</el-button>
              <el-button v-if="editing" class="mdm-org-dept__spacer" @click="cancelEdit">
                {{ t('mdmOrg.common.cancel') }}
              </el-button>
              <el-button v-if="editing" type="primary" data-test="dept-save" @click="saveEdit">
                {{ t('mdmOrg.common.save') }}
              </el-button>
              <span class="mdm-org-dept__mode" data-test="dept-mode">
                {{ editing ? t('mdmOrg.dept.mode.editing') : t('mdmOrg.dept.mode.readonly') }}
              </span>
            </div>

            <el-form label-width="120px" class="mdm-org-dept__form" data-test="dept-inline-form">
              <el-form-item :label="t('mdmOrg.dept.form.parent')">
                <el-select v-model="form.parentId" :disabled="!editing" clearable :placeholder="t('mdmOrg.dept.form.root')">
                  <el-option v-for="item in parentOptions" :key="item.value" :label="item.label" :value="item.value" />
                </el-select>
              </el-form-item>
              <el-form-item :label="t('mdmOrg.dept.form.code')">
                <el-input v-model="form.code" :disabled="!editing" data-test="dept-inline-code" />
              </el-form-item>
              <el-form-item :label="t('mdmOrg.dept.form.name')">
                <el-input v-model="form.name" :disabled="!editing" data-test="dept-inline-name" />
              </el-form-item>
              <el-form-item :label="t('mdmOrg.dept.form.sort')">
                <el-input-number v-model="form.sort" :min="0" :disabled="!editing" />
              </el-form-item>
              <el-form-item :label="t('mdmOrg.dept.form.status')">
                <el-select v-model="form.status" :disabled="!editing">
                  <el-option
                    v-for="item in STATUS_OPTIONS"
                    :key="item.value"
                    :label="t(item.labelKey)"
                    :value="item.value"
                  />
                </el-select>
              </el-form-item>
              <el-form-item :label="t('mdmOrg.dept.column.ancestors')">
                <span data-test="dept-ancestors">{{ selected.ancestors === '' ? '—' : selected.ancestors }}</span>
              </el-form-item>
              <el-form-item :label="t('mdmOrg.dept.users.title')">
                <span data-test="dept-detail-users">{{ userIds.length }}</span>
              </el-form-item>
              <el-form-item :label="t('mdmOrg.dept.roles.title')">
                <el-tag v-for="role in roleIds" :key="role" class="mdm-org-dept__role" size="small">{{ role }}</el-tag>
                <span v-if="roleIds.length === 0" data-test="dept-detail-roles">0</span>
                <span class="mdm-org-dept__hint">{{ t('mdmOrg.dept.roles.hint') }}</span>
              </el-form-item>
            </el-form>
          </template>
        </div>
      </div>
    </section-container>
  </page-container>
</template>

<style scoped>
.mdm-org-dept__toolbar {
  display: flex;
  align-items: center;
  gap: var(--bms-space-2);
}

.mdm-org-dept__current,
.mdm-org-dept__notice,
.mdm-org-dept__mode,
.mdm-org-dept__hint {
  color: var(--bms-color-text-secondary);
  font-size: var(--bms-font-size-sm);
}

.mdm-org-dept__notice {
  margin: var(--bms-space-2) 0 0;
}

.mdm-org-dept__body {
  display: flex;
  gap: var(--bms-space-4);
}

.mdm-org-dept__detail {
  flex: 1;
  min-width: 0;
}

.mdm-org-dept__actions {
  display: flex;
  align-items: center;
  gap: var(--bms-space-2);
  margin-bottom: var(--bms-space-3);
}

.mdm-org-dept__spacer {
  margin-left: auto;
}

.mdm-org-dept__role {
  margin-right: var(--bms-space-1);
}

.mdm-org-dept__form :deep(.el-form-item) {
  margin-bottom: var(--bms-space-2);
}
</style>
