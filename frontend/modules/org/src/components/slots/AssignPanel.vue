<script setup lang="ts">
// 分配面板骨架（三个具名插槽插件共用）：**已分配列表 + 单条解绑 + 弹窗分配（全量覆盖）+ 即时提交**。
//
// 交互口径（承组织域插件原型）：① 分配经**弹窗**（候选由父组件在 `#picker` 插槽内渲染，支持部门筛选 / 树多选）；
// ② 点「保存并提交」按勾选结果**整体覆盖**该对象现有分配并**立即生效**（不随宿主页工具栏保存）；
// ③ 单条**解绑**带二次确认、立即生效；④ 降级：上下文缺失 / 无权限 / 请求能力未注入 → 不请求、给出明确提示。
import { EmptyState, SectionContainer } from '@bms/ui-ep'
import { ElButton, ElDialog, ElMessage, ElMessageBox, ElTable, ElTableColumn } from 'element-plus'
import { onMounted, ref, watch } from 'vue'

import { useOrgI18n } from '../../composables/useOrgI18n'
import { orgRuntime } from '../../runtime'

/** 已分配项（列表展示与解绑对象）。 */
export interface AssignedRow {
  /** 标识（字符串口径，避免雪花 id 精度丢失）。 */
  id: string
  /** 名称。 */
  label: string
  /** 次级说明（编码 / 所属部门等）。 */
  description?: string
}

const props = defineProps<{
  /** 面板标题文案键。 */
  titleKey: string
  /** 作用实体标识（宿主页提供：路由参数或显式上下文）。 */
  contextId: string
  /** 上下文缺失提示文案键。 */
  contextAbsentKey?: string
  /** 目标类型文案（如「岗位」「部门」）。 */
  targetLabel: string
  /** 已分配项（父组件载入后传入）。 */
  assignedRows: AssignedRow[]
  /** 弹窗内已勾选标识（`v-model:picked`）。 */
  picked: string[]
  /** 候选载入中。 */
  loading?: boolean
  /** 提交中。 */
  submitting?: boolean
  /** 载入 / 提交失败文案（父组件传入；空串不显示）。 */
  errorText?: string
}>()

const emit = defineEmits<{
  /** 勾选集合变化。 */
  'update:picked': [ids: string[]]
  /** 提交全量分配（父组件执行写操作）。 */
  submit: [ids: string[]]
  /** 单条解绑（父组件执行写操作）。 */
  unassign: [id: string]
  /** 重新载入（父组件实现）。 */
  reload: []
}>()

const { t } = useOrgI18n()
const runtime = orgRuntime()

/** 分配弹窗可见性。 */
const pickerVisible = ref(false)
/** 解绑中标识（行内 loading）。 */
const unassigning = ref('')

/** 打开分配弹窗（勾选初值＝当前已分配）。 */
function openPicker(): void {
  emit('update:picked', props.assignedRows.map((row) => row.id))
  pickerVisible.value = true
}

/** 取消分配弹窗。 */
function closePicker(): void {
  pickerVisible.value = false
}

/** 保存并提交（全量覆盖；立即生效，不随宿主页工具栏保存）。 */
function submit(): void {
  emit('submit', [...props.picked])
  pickerVisible.value = false
  ElMessage.success(t('mdmOrg.slot.submitted'))
}

/**
 * 单条解绑（二次确认；立即生效）。
 *
 * @param row 已分配项。
 */
async function unassign(row: AssignedRow): Promise<void> {
  await ElMessageBox.confirm(
    t('mdmOrg.slot.unassignConfirm', { name: row.label }),
    t('mdmOrg.common.confirm'),
    {
      confirmButtonText: t('mdmOrg.common.confirm'),
      cancelButtonText: t('mdmOrg.common.cancel'),
      type: 'warning',
    },
  )
  unassigning.value = row.id
  try {
    emit('unassign', row.id)
  } finally {
    unassigning.value = ''
  }
}

// 上下文切换（宿主记录页签换实体）：关闭弹窗、清空本地态
watch(
  () => props.contextId,
  () => {
    pickerVisible.value = false
  },
)

onMounted(() => {
  if (props.contextId !== '') emit('reload')
})
</script>

<template>
  <section-container :title="t(props.titleKey)" data-test="assign-panel">
    <!-- 降级：作用实体标识缺失（非路由承载页未注入上下文 / 路由参数缺失） -->
    <empty-state
      v-if="contextId === ''"
      type="data"
      :title="t(props.contextAbsentKey ?? 'mdmOrg.slot.contextAbsent')"
      data-test="assign-context-absent"
    />

    <template v-else>
      <div class="mdm-org-assign__toolbar">
        <el-button v-if="runtime.canUpdate" type="primary" data-test="assign-open" @click="openPicker">
          {{ t('mdmOrg.slot.pickTarget', { target: targetLabel }) }}
        </el-button>
        <el-button data-test="assign-reload" @click="emit('reload')">{{ t('mdmOrg.common.refresh') }}</el-button>
        <span class="mdm-org-assign__summary" data-test="assign-summary">
          {{ t('mdmOrg.slot.assigned', { count: assignedRows.length }) }}
        </span>
        <span v-if="!runtime.canUpdate" class="mdm-org-assign__hint" data-test="assign-no-permission">
          {{ t('mdmOrg.slot.noPermission') }}
        </span>
      </div>

      <p v-if="loading === true" class="mdm-org-assign__hint" data-test="assign-loading">
        {{ t('mdmOrg.common.loading') }}
      </p>

      <empty-state
        v-else-if="assignedRows.length === 0"
        type="data"
        :title="t('mdmOrg.slot.empty')"
        data-test="assign-empty"
      />

      <el-table v-else :data="assignedRows" row-key="id" size="small" data-test="assigned-table">
        <el-table-column prop="label" :label="targetLabel" min-width="160" />
        <el-table-column prop="description" :label="t('mdmOrg.slot.column.note')" min-width="160" />
        <el-table-column :label="t('mdmOrg.slot.column.actions')" width="110" align="right">
          <template #default="{ row }">
            <el-button
              v-if="runtime.canUpdate"
              link
              type="danger"
              :loading="unassigning === (row as AssignedRow).id"
              :data-test="`assign-unbind-${(row as AssignedRow).id}`"
              @click="unassign(row as AssignedRow)"
            >
              {{ t('mdmOrg.common.remove') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <p v-if="(errorText ?? '') !== ''" class="mdm-org-assign__error" data-test="assign-error">{{ errorText }}</p>

      <el-dialog
        v-model="pickerVisible"
        :title="t('mdmOrg.slot.picker.title', { target: targetLabel })"
        width="520"
        align-center
      >
        <!-- 候选区（父组件渲染：岗位＝部门筛选 + 多选列表；部门＝树多选） -->
        <slot name="picker" :picked="picked" />

        <template #footer>
          <el-button data-test="assign-dialog-cancel" @click="closePicker">{{ t('mdmOrg.common.cancel') }}</el-button>
          <el-button
            v-if="runtime.canUpdate"
            type="primary"
            :loading="submitting === true"
            data-test="assign-dialog-submit"
            @click="submit"
          >
            {{ t('mdmOrg.slot.saveAndSubmit') }}
          </el-button>
        </template>
      </el-dialog>
    </template>
  </section-container>
</template>

<style scoped>
.mdm-org-assign__toolbar {
  display: flex;
  align-items: center;
  gap: var(--bms-space-2);
  margin-bottom: var(--bms-space-2);
}

.mdm-org-assign__summary,
.mdm-org-assign__hint {
  color: var(--bms-color-text-secondary);
  font-size: var(--bms-font-size-sm);
}

.mdm-org-assign__error {
  margin: var(--bms-space-2) 0 0;
  color: var(--bms-color-danger);
  font-size: var(--bms-font-size-sm);
}
</style>
