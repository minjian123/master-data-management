/**
 * 分配面板状态组合式（三个具名插槽插件共用）。
 *
 * 统一「已分配列表载入 / 全量提交 / 单条解绑 / 降级文案」四件事；候选（岗位列表 / 部门树）由各插件自行渲染，
 * 因为三者的候选形态与筛选方式不同（岗位＝部门筛选 + 多选列表；部门＝树多选）。
 */

import { computed, ref, type ComputedRef, type Ref } from 'vue'

import { useOrgI18n } from './useOrgI18n'
import { isApiAbsent } from '../runtime'

import type { AssignedRow } from '../components/slots/AssignPanel.vue'

/** 已分配项标签（插件解析名称后回填）。 */
export interface AssignedLabel {
  /** 标识（字符串口径）。 */
  id: string
  /** 名称。 */
  label: string
  /** 次级说明（编码 / 所属部门等）。 */
  description?: string
}

/** 分配数据面（插件按自身端点注入）。 */
export interface AssignmentPorts {
  /**
   * 载入已分配（返回标识集合与名称回填信息）。
   *
   * @param contextId 作用实体标识（用户 / 角色）。
   */
  loadAssigned: (contextId: string) => Promise<{ ids: string[]; labels: AssignedLabel[] }>
  /**
   * 全量提交（覆盖语义）。
   *
   * @param contextId 作用实体标识。
   * @param ids 目标标识集合。
   */
  submit: (contextId: string, ids: string[]) => Promise<void>
  /**
   * 单条解绑。
   *
   * @param contextId 作用实体标识。
   * @param targetId 目标标识。
   */
  unassign: (contextId: string, targetId: string) => Promise<void>
}

/** 分配面板状态面。 */
export interface UseAssignmentResult {
  /** 已分配项（列表展示）。 */
  assignedRows: Ref<AssignedRow[]>
  /** 弹窗内勾选集合（`v-model:picked`）。 */
  picked: Ref<string[]>
  /** 载入中。 */
  loading: Ref<boolean>
  /** 提交中。 */
  submitting: Ref<boolean>
  /** 失败文案（空串不显示）。 */
  errorText: Ref<string>
  /** 降级中（上下文缺失或请求能力未注入）。 */
  degraded: ComputedRef<boolean>
  /** 重新载入已分配列表。 */
  reload: () => Promise<void>
  /**
   * 全量提交。
   *
   * @param ids 目标标识集合。
   */
  save: (ids: string[]) => Promise<void>
  /**
   * 单条解绑。
   *
   * @param targetId 目标标识。
   */
  unbind: (targetId: string) => Promise<void>
}

/**
 * 构造分配面板状态。
 *
 * @param contextId 作用实体标识（响应式；缺失即降级，不请求）。
 * @param ports 数据面（插件注入）。
 * @returns 状态面。
 */
export function useAssignment(contextId: Ref<string>, ports: AssignmentPorts): UseAssignmentResult {
  const { t } = useOrgI18n()
  const assignedRows = ref<AssignedRow[]>([])
  const picked = ref<string[]>([])
  const loading = ref(false)
  const submitting = ref(false)
  const errorText = ref('')

  /**
   * 失败文案（请求能力未注入 → 「未接入」；其余 → 通用失败）。
   *
   * @param caught 捕获的错误。
   */
  function describe(caught: unknown): string {
    return isApiAbsent(caught) ? t('mdmOrg.common.apiAbsent') : t('mdmOrg.common.failed')
  }

  /** 重新载入已分配列表（上下文缺失即短路）。 */
  async function reload(): Promise<void> {
    const id = contextId.value
    if (id === '') return
    loading.value = true
    errorText.value = ''
    try {
      const { ids, labels } = await ports.loadAssigned(id)
      const index = new Map(labels.map((item) => [item.id, item]))
      picked.value = [...ids]
      assignedRows.value = ids.map((item) => {
        const hit = index.get(item)
        return { id: item, label: hit?.label ?? item, description: hit?.description }
      })
    } catch (caught) {
      assignedRows.value = []
      errorText.value = describe(caught)
    } finally {
      loading.value = false
    }
  }

  /**
   * 全量提交（覆盖语义；立即生效）。
   *
   * @param ids 目标标识集合。
   */
  async function save(ids: string[]): Promise<void> {
    const id = contextId.value
    if (id === '') return
    submitting.value = true
    errorText.value = ''
    try {
      await ports.submit(id, ids)
      await reload()
    } catch (caught) {
      errorText.value = describe(caught)
    } finally {
      submitting.value = false
    }
  }

  /**
   * 单条解绑（立即生效）。
   *
   * @param targetId 目标标识。
   */
  async function unbind(targetId: string): Promise<void> {
    const id = contextId.value
    if (id === '') return
    errorText.value = ''
    try {
      await ports.unassign(id, targetId)
      await reload()
    } catch (caught) {
      errorText.value = describe(caught)
    }
  }

  return {
    assignedRows,
    picked,
    loading,
    submitting,
    errorText,
    degraded: computed(() => contextId.value === ''),
    reload,
    save,
    unbind,
  }
}
