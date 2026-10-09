/**
 * 分配面板状态组合式（四个具名插槽插件共用：用户侧岗位 / 部门、角色侧岗位 / 部门）。
 *
 * 统一「已分配列表载入 / **草稿编辑** / 主要项 / 降级文案」四件事；候选（岗位列表 / 部门树）由各插件自行渲染，
 * 因为四者的候选形态与筛选方式不同（岗位＝部门筛选 + 多选列表；部门＝树多选）。
 *
 * **提交口径（2026-10-09 定稿：跟随宿主保存）**：
 * - 宿主经插槽上下文提供 `registerSubmitter`（表单框架记录页签保存时回调插件）⇒ 改动**只进草稿**，
 *   由宿主工具栏「保存」统一提交（`isDirty()` 供宿主做脏标记 / 离开拦截）；
 * - 宿主**未提供**该通道（如已交付的角色管理页）⇒ 保持**自提交兜底**（弹窗「确定」即立即覆盖），不回归可用性；
 * - 主要项：契约只回标识集合，置位走**独立端点**（提交器内两步：先全量覆盖、再置位 / 清除；两步均幂等）。
 */

import { computed, ref, watch, type ComputedRef, type Ref } from 'vue'

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

/** 宿主提交器登记入参（表单框架记录页签：宿主保存时回调插件提交 / 取脏标记）。 */
export interface HostSubmitterEntry {
  /** 提交草稿（幂等；宿主工具栏保存时调用）。 */
  submit: () => Promise<void>
  /** 是否含未提交改动（宿主脏标记 / 离开拦截）。 */
  isDirty: () => boolean
}

/** 宿主提交器注册通道（经插槽上下文字段 `registerSubmitter` 注入；缺失即无通道）。 */
export interface HostSubmitterRegistrar {
  /**
   * 登记插件提交器。
   *
   * @param entry 提交器（提交回调 + 脏标记）。
   */
  registerSubmitter: (entry: HostSubmitterEntry) => void
}

/** 分配数据面（插件按自身端点注入）。 */
export interface AssignmentPorts {
  /**
   * 载入已分配（返回标识集合、名称回填信息与已保存的主要项）。
   *
   * @param contextId 作用实体标识（用户 / 角色）。
   */
  loadAssigned: (contextId: string) => Promise<{ ids: string[]; labels: AssignedLabel[]; primary?: string }>
  /**
   * 全量提交（覆盖语义；幂等）。
   *
   * @param contextId 作用实体标识。
   * @param ids 目标标识集合。
   */
  submit: (contextId: string, ids: string[]) => Promise<void>
  /**
   * 置位 / 清除主要项（独立端点；`null` 清除；幂等。未提供即该面板无主要项语义）。
   *
   * @param contextId 作用实体标识。
   * @param primaryId 主要项标识（`null` 清除）。
   */
  submitPrimary?: (contextId: string, primaryId: string | null) => Promise<void>
}

/** 分配面板状态面。 */
export interface UseAssignmentResult {
  /** 已分配项（服务端已保存口径；列表展示）。 */
  assignedRows: Ref<AssignedRow[]>
  /** 草稿勾选集合（`v-model:picked`；含未提交改动）。 */
  picked: Ref<string[]>
  /** 草稿主要项标识（空串＝未设；无主要项语义时恒为空串）。 */
  primary: Ref<string>
  /** 是否含未提交改动（集合差异或主要项差异）。 */
  dirty: ComputedRef<boolean>
  /** 宿主是否提供提交器通道（False ⇒ 弹窗确定即自提交兜底）。 */
  hostBound: ComputedRef<boolean>
  /** 载入中。 */
  loading: Ref<boolean>
  /** 提交中。 */
  submitting: Ref<boolean>
  /** 失败文案（空串不显示）。 */
  errorText: Ref<string>
  /** 降级中（上下文缺失或请求能力未注入）。 */
  degraded: ComputedRef<boolean>
  /** 重新载入已分配列表（同时重置草稿）。 */
  reload: () => Promise<void>
  /** 提交草稿（宿主调用或自提交兜底；无改动即短路）。 */
  applyDraft: () => Promise<void>
}

/** 选项。 */
export interface UseAssignmentOptions {
  /** 宿主提交器注册通道（响应式；缺失＝无通道 ⇒ 自提交兜底）。 */
  registrar?: ComputedRef<HostSubmitterRegistrar | undefined>
}

/**
 * 集合是否等价（忽略顺序）。
 *
 * @param left 左集合。
 * @param right 右集合。
 * @returns 等价 True。
 */
function sameSet(left: readonly string[], right: readonly string[]): boolean {
  if (left.length !== right.length) return false
  const set = new Set(right)
  return left.every((item) => set.has(item))
}

/**
 * 构造分配面板状态。
 *
 * @param contextId 作用实体标识（响应式；缺失即降级，不请求）。
 * @param ports 数据面（插件注入）。
 * @param options 选项（宿主提交器通道）。
 * @returns 状态面。
 */
export function useAssignment(
  contextId: Ref<string>,
  ports: AssignmentPorts,
  options: UseAssignmentOptions = {},
): UseAssignmentResult {
  const { t } = useOrgI18n()
  const assignedRows = ref<AssignedRow[]>([])
  const assignedIds = ref<string[]>([])
  const picked = ref<string[]>([])
  const primary = ref('')
  const savedPrimary = ref('')
  const loading = ref(false)
  const submitting = ref(false)
  const errorText = ref('')

  const registrar = options.registrar
  const hostBound = computed(() => registrar?.value !== undefined)
  const dirty = computed(
    () => !sameSet(picked.value, assignedIds.value) || (ports.submitPrimary !== undefined && primary.value !== savedPrimary.value),
  )

  /**
   * 失败文案（请求能力未注入 → 「未接入」；其余 → 通用失败）。
   *
   * @param caught 捕获的错误。
   * @returns 提示文案。
   */
  function describe(caught: unknown): string {
    return isApiAbsent(caught) ? t('mdmOrg.common.apiAbsent') : t('mdmOrg.common.failed')
  }

  /** 重新载入已分配列表与主要项（上下文缺失即短路；载入成功即清空草稿差异）。 */
  async function reload(): Promise<void> {
    const id = contextId.value
    if (id === '') return
    loading.value = true
    errorText.value = ''
    try {
      const { ids, labels, primary: savedPrimaryId } = await ports.loadAssigned(id)
      const index = new Map(labels.map((item) => [item.id, item]))
      assignedIds.value = [...ids]
      picked.value = [...ids]
      savedPrimary.value = savedPrimaryId ?? ''
      primary.value = savedPrimaryId ?? ''
      assignedRows.value = ids.map((item) => {
        const hit = index.get(item)
        return { id: item, label: hit?.label ?? item, description: hit?.description }
      })
    } catch (caught) {
      assignedIds.value = []
      assignedRows.value = []
      picked.value = []
      savedPrimary.value = ''
      primary.value = ''
      errorText.value = describe(caught)
    } finally {
      loading.value = false
    }
  }

  /**
   * 提交草稿：① 全量覆盖（含新增 / 移除）→ ② 主要项置位 / 清除（均幂等；任一失败整单失败并保留草稿）。
   */
  async function applyDraft(): Promise<void> {
    const id = contextId.value
    if (id === '' || !dirty.value) return
    submitting.value = true
    errorText.value = ''
    try {
      await ports.submit(id, [...picked.value])
      if (ports.submitPrimary !== undefined && primary.value !== savedPrimary.value) {
        await ports.submitPrimary(id, primary.value === '' ? null : primary.value)
      }
      await reload()
    } catch (caught) {
      errorText.value = describe(caught)
    } finally {
      submitting.value = false
    }
  }

  // 宿主提供通道 ⇒ 登记提交器（改动随宿主保存）；通道出现 / 消失均重新登记
  watch(
    () => registrar?.value,
    (target) => {
      target?.registerSubmitter({ submit: applyDraft, isDirty: () => dirty.value })
    },
    { immediate: true },
  )

  return {
    assignedRows,
    picked,
    primary,
    dirty,
    hostBound,
    loading,
    submitting,
    errorText,
    degraded: computed(() => contextId.value === ''),
    reload,
    applyDraft,
  }
}
