<script setup lang="ts">
// 分配面板骨架（三个具名插槽插件共用）：载入当前分配 → 勾选目标 → **即时提交**（全量覆盖语义）。
//
// 降级口径（插件在宿主页中必须可缺省存在）：上下文缺失 / 权限不足 / 请求能力未注入 → 不请求、给出明确提示；
// 提交失败给出可读错误（业务失败多为 HTTP 200 + 统一响应码，由宿主请求层解包为错误）。
import { EmptyState, SectionContainer } from '@bms/ui-ep'
import { ElButton, ElCheckbox, ElMessage } from 'element-plus'
import { onMounted, ref, watch } from 'vue'

import { useOrgI18n } from '../../composables/useOrgI18n'
import { orgRuntime } from '../../runtime'

/** 目标选项（扁平项；部门树亦展平后使用）。 */
export interface AssignTargetOption {
  /** 标识（字符串口径，避免雪花 id 精度丢失）。 */
  value: string
  /** 展示名。 */
  label: string
  /** 次级说明（如所属部门）。 */
  description?: string
}

const props = defineProps<{
  /** 面板标题文案键。 */
  titleKey: string
  /** 作用实体标识（宿主页提供：路由参数或显式上下文）。 */
  contextId: string
  /** 上下文缺失提示文案键。 */
  contextAbsentKey?: string
  /** 目标选项清单（父组件载入后传入；空数组表示无候选）。 */
  options: AssignTargetOption[]
  /** 已分配标识（父组件载入后传入）。 */
  assigned: string[]
  /** 目标类型文案（如「岗位」「部门」）。 */
  targetLabel: string
  /** 候选载入中。 */
  loading?: boolean
  /** 提交中。 */
  submitting?: boolean
  /** 提交回调（全量覆盖）。 */
  onSubmit: (ids: string[]) => Promise<void>
}>()

const emit = defineEmits<{
  /** 勾选变化（供父组件维护状态）。 */
  'update:assigned': [ids: string[]]
  /** 请求重新载入（父组件实现）。 */
  reload: []
}>()

const { t } = useOrgI18n()
const runtime = orgRuntime()

/** 勾选集合（本地态；点「提交变更」才落库——即时提交指不随宿主工具栏保存）。 */
const picked = ref<string[]>([...props.assigned])
/** 上次提交成功后的基线（用于判断是否有未提交变更）。 */
const baseline = ref<string[]>([...props.assigned])
/** 错误文案。 */
const errorText = ref('')

watch(
  () => props.assigned,
  (value) => {
    picked.value = [...value]
    baseline.value = [...value]
  },
)

/** 是否有未提交变更。 */
function dirty(): boolean {
  const left = [...picked.value].sort()
  const right = [...baseline.value].sort()
  return left.length !== right.length || left.some((item, index) => item !== right[index])
}

/**
 * 勾选切换。
 *
 * @param value 目标标识。
 * @param checked 是否勾选。
 */
function toggle(value: string, checked: boolean): void {
  const next = new Set(picked.value)
  if (checked) next.add(value)
  else next.delete(value)
  picked.value = [...next]
  emit('update:assigned', picked.value)
}

/** 提交变更。 */
async function submit(): Promise<void> {
  errorText.value = ''
  try {
    await props.onSubmit([...picked.value])
    baseline.value = [...picked.value]
    ElMessage.success(t('mdmOrg.slot.submitted'))
  } catch (caught) {
    errorText.value = caught instanceof Error ? caught.message : t('mdmOrg.common.failed')
  }
}

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
      <p class="mdm-org-assign__summary" data-test="assign-summary">
        {{ t('mdmOrg.slot.assigned', { count: assigned.length }) }}
      </p>

      <div v-if="loading" class="mdm-org-assign__hint" data-test="assign-loading">{{ t('mdmOrg.common.loading') }}</div>

      <empty-state
        v-else-if="options.length === 0"
        type="data"
        :title="t('mdmOrg.common.empty')"
        data-test="assign-empty-options"
      />

      <template v-else>
        <ul class="mdm-org-assign__list" data-test="assign-options">
          <li v-for="option in options" :key="option.value" class="mdm-org-assign__item">
            <el-checkbox
              :model-value="picked.includes(option.value)"
              :data-test="`assign-option-${option.value}`"
              @update:model-value="(checked: string | number | boolean) => toggle(option.value, checked === true)"
            >
              {{ option.label }}
            </el-checkbox>
            <span v-if="option.description !== undefined" class="mdm-org-assign__desc">{{ option.description }}</span>
          </li>
        </ul>

        <div class="mdm-org-assign__actions">
          <el-button
            v-if="runtime.canUpdate"
            type="primary"
            :disabled="!dirty() || submitting === true"
            data-test="assign-submit"
            @click="submit"
          >
            {{ t('mdmOrg.slot.submit') }}
          </el-button>
          <span v-if="!runtime.canUpdate" class="mdm-org-assign__hint" data-test="assign-no-permission">
            {{ t('mdmOrg.slot.noPermission') }}
          </span>
          <span v-else-if="!dirty()" class="mdm-org-assign__hint" data-test="assign-no-change">
            {{ t('mdmOrg.slot.noChange') }}
          </span>
          <el-button data-test="assign-reload" @click="emit('reload')">{{ t('mdmOrg.common.refresh') }}</el-button>
        </div>

        <p v-if="errorText !== ''" class="mdm-org-assign__error" data-test="assign-error">{{ errorText }}</p>
      </template>
    </template>
  </section-container>
</template>

<style scoped>
.mdm-org-assign__summary {
  margin: 0 0 var(--bms-space-2);
  color: var(--bms-color-text-secondary);
  font-size: var(--bms-font-size-sm);
}

.mdm-org-assign__list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--bms-space-1);
}

.mdm-org-assign__item {
  display: flex;
  align-items: center;
  gap: var(--bms-space-2);
}

.mdm-org-assign__desc {
  color: var(--bms-color-text-secondary);
  font-size: var(--bms-font-size-sm);
}

.mdm-org-assign__actions {
  display: flex;
  align-items: center;
  gap: var(--bms-space-2);
  margin-top: var(--bms-space-3);
}

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
