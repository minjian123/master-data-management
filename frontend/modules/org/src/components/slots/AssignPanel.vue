<script setup lang="ts">
// 分配面板骨架（四个具名插槽插件共用）：**已分配列表 + 主要项单选 + 弹窗分配（全量覆盖）+ 跟随宿主保存**。
//
// 交互口径（2026-10-09 定稿）：
// ① 分配经**弹窗**（候选由父组件在 `#picker` 插槽内渲染，支持部门筛选 / 树多选）；
// ② 弹窗内勾选与主要项选择**只改进草稿**（不立即请求）；**确定**仅关闭弹窗；
// ③ 宿主提供提交器通道（`hostBound`）⇒ 由宿主记录页签「保存」统一提交，面板显示**未保存标记**；
//    宿主未提供 ⇒ 旧口径兜底：**确定即自提交**（全量覆盖、立即生效），不回归可用性；
// ④ 移除「解绑」列：移除分配＝在弹窗内取消勾选后提交（草稿语义天然覆盖）；
// ⑤ 降级：上下文缺失 / 无权限 / 请求能力未注入 → 不请求、给出明确提示。
import { EmptyState, SectionContainer } from '@bms/ui-ep'
import { ElButton, ElDialog, ElRadio, ElTable, ElTableColumn } from 'element-plus'
import { ref, watch } from 'vue'

import { useOrgI18n } from '../../composables/useOrgI18n'
import { orgRuntime } from '../../runtime'

/** 已分配项（列表展示对象）。 */
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
  /** 作用实体标识（宿主页提供：显式上下文优先、路由参数兜底）。 */
  contextId: string
  /** 上下文缺失提示文案键。 */
  contextAbsentKey?: string
  /** 目标类型文案（如「岗位」「部门」）。 */
  targetLabel: string
  /** 已分配项（父组件载入后传入；服务端已保存口径）。 */
  assignedRows: AssignedRow[]
  /** 弹窗内草稿勾选标识（`v-model:picked`）。 */
  picked: string[]
  /** 草稿主要项标识（空串＝未设；`showPrimary` 为真时生效）。 */
  primary?: string
  /** 是否含未提交改动（草稿差异；父组件传入）。 */
  dirty?: boolean
  /** 宿主是否提供提交器通道（真 ⇒ 跟随宿主保存；假 ⇒ 确定即自提交兜底）。 */
  hostBound?: boolean
  /** 是否呈现主要项单选列（该面板具备主要项语义时为真）。 */
  showPrimary?: boolean
  /** 候选载入中。 */
  loading?: boolean
  /** 提交中。 */
  submitting?: boolean
  /** 载入 / 提交失败文案（父组件传入；空串不显示）。 */
  errorText?: string
}>()

const emit = defineEmits<{
  /** 草稿勾选集合变化。 */
  'update:picked': [ids: string[]]
  /** 草稿主要项变化。 */
  'update:primary': [id: string]
  /** 自提交兜底（宿主无通道时点「确定」触发；父组件执行写操作）。 */
  submit: [ids: string[]]
  /** 重新载入（父组件实现）。 */
  reload: []
}>()

const { t } = useOrgI18n()
const runtime = orgRuntime()

/** 分配弹窗可见性。 */
const pickerVisible = ref(false)

/** 打开分配弹窗（勾选初值＝当前草稿；未设主要项且已分配非空时默认首项）。 */
function openPicker(): void {
  emit('update:picked', [...props.picked])
  if (props.showPrimary === true && (props.primary ?? '') === '' && props.assignedRows.length > 0) {
    emit('update:primary', props.assignedRows[0]!.id)
  }
  pickerVisible.value = true
}

/** 关闭分配弹窗（不改草稿）。 */
function closePicker(): void {
  pickerVisible.value = false
}

/**
 * 确定（关闭弹窗）。
 *
 * 宿主有提交器通道 ⇒ 改动留在草稿，由宿主工具栏保存统一提交；
 * 无通道 ⇒ 自提交兜底（全量覆盖、立即生效）。
 */
function confirm(): void {
  pickerVisible.value = false
  if (props.hostBound !== true) emit('submit', [...props.picked])
}

// 上下文切换（宿主记录页签换实体）：关闭弹窗、清空本地态
watch(
  () => props.contextId,
  () => {
    pickerVisible.value = false
  },
)
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
        <span v-if="dirty === true" class="mdm-org-assign__dirty" data-test="assign-dirty">
          {{ t('mdmOrg.slot.dirty') }}
        </span>
        <span v-if="!runtime.canUpdate" class="mdm-org-assign__hint" data-test="assign-no-permission">
          {{ t('mdmOrg.slot.noPermission') }}
        </span>
      </div>

      <p v-if="hostBound !== true" class="mdm-org-assign__hint" data-test="assign-self-submit">
        {{ t('mdmOrg.slot.selfSubmitHint') }}
      </p>

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
        <el-table-column
          v-if="showPrimary === true"
          :label="t('mdmOrg.slot.column.primary')"
          width="100"
          align="center"
        >
          <template #default="{ row }">
            <el-radio
              :model-value="primary ?? ''"
              :value="(row as AssignedRow).id"
              :disabled="!runtime.canUpdate"
              :label="(row as AssignedRow).id"
              :data-test="`assign-primary-${(row as AssignedRow).id}`"
              @change="emit('update:primary', (row as AssignedRow).id)"
            >
              <span />
            </el-radio>
          </template>
        </el-table-column>
        <el-table-column prop="label" :label="targetLabel" min-width="160" />
        <el-table-column prop="description" :label="t('mdmOrg.slot.column.note')" min-width="160" />
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
            data-test="assign-dialog-confirm"
            @click="confirm"
          >
            {{ hostBound === true ? t('mdmOrg.common.confirm') : t('mdmOrg.slot.saveAndSubmit') }}
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

.mdm-org-assign__dirty {
  color: var(--bms-color-warning);
  font-size: var(--bms-font-size-sm);
}

.mdm-org-assign__error {
  margin: var(--bms-space-2) 0 0;
  color: var(--bms-color-danger);
  font-size: var(--bms-font-size-sm);
}
</style>
