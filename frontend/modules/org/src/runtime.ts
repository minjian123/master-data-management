/**
 * 模块运行期派生状态与宿主能力持有（宿主注入上下文的**只读消费**结果）。
 *
 * `setup(context)` 时计算并缓存；模块内视图与插槽件只读消费，不直连宿主 store，
 * 不持久化、不自建 HTTP（隔离约定：平台护栏 R2 / R3 / R4）。上下文缺失项自行降级（不假定存在）。
 */

import type { ModuleApi, ModuleHostContext } from '@bms/core'

/** 组织域写权限码（管理面与插件写操作同权限码，与后端 `require_permission` 同源）。 */
export const ORG_UPDATE_PERMISSION = 'org:update'

/** 组织域查询权限码。 */
export const ORG_QUERY_PERMISSION = 'org:query'

/** 宿主请求能力缺失时的哨兵错误（视图据此降级为「未接入」提示）。 */
export const MODULE_API_ABSENT = 'MODULE_API_ABSENT'

/** 模块运行期状态。 */
export interface OrgRuntimeState {
  /** 宿主注入的权限码清单（只读快照）。 */
  permissionCodes: string[]
  /** 是否具备组织域写权限（无权限信息时按「有」处理——显隐只是体验，真正的鉴权在后端）。 */
  canUpdate: boolean
}

/** 宿主注入路由的最小只读面（仅需当前路由参数；模块不直连宿主 router 实例做导航）。 */
export interface HostRouterLike {
  /** 当前路由（响应式）。 */
  currentRoute?: { value?: { params?: Record<string, unknown> } }
}

/** 当前状态（初始为空上下文口径）。 */
let state: OrgRuntimeState = { permissionCodes: [], canUpdate: true }
/** 宿主注入的请求能力（未注入为 `undefined`）。 */
let hostApi: ModuleApi | undefined
/** 宿主注入的路由（只读；用于**路由参数通道**取宿主页作用实体标识）。 */
let hostRouter: HostRouterLike | undefined

/**
 * 依据宿主上下文计算并缓存运行期状态（同时记录宿主请求能力与只读路由）。
 *
 * @param context 宿主注入上下文（只读快照）。
 * @returns 计算后的状态。
 */
export function applyHostContext(context: ModuleHostContext): OrgRuntimeState {
  const codes = Array.isArray(context.user)
    ? context.user.filter((item): item is string => typeof item === 'string')
    : []
  state = {
    permissionCodes: codes,
    canUpdate: codes.length === 0 || codes.includes(ORG_UPDATE_PERMISSION),
  }
  hostApi = context.api
  hostRouter = context.router as HostRouterLike | undefined
  return state
}

/** 读取当前运行期状态（只读）。 */
export function orgRuntime(): OrgRuntimeState {
  return state
}

/** 宿主请求能力（未注入返回 `undefined`）。 */
export function hostApiOf(): ModuleApi | undefined {
  return hostApi
}

/**
 * 取宿主请求能力（**未注入即抛哨兵错误**，由调用方降级为「未接入」提示）。
 *
 * @returns 请求能力。
 * @throws Error 哨兵错误（`MODULE_API_ABSENT`）。
 */
export function requiredHostApi(): ModuleApi {
  if (hostApi === undefined) {
    throw new Error(MODULE_API_ABSENT)
  }
  return hostApi
}

/**
 * 读取宿主页**作用实体标识**（路由参数通道）。
 *
 * 用户详情页把实体标识放路由参数（`/sys/users/:id`）；角色表单记录页签**非路由承载**，
 * 其上下文经**显式上下文注入通道**（`useModuleSlotField('roleId')`）取得——两条通道并存。
 *
 * @param key 路由参数名（缺省 `id`）。
 * @returns 标识字符串（缺失返回空串，调用方降级）。
 */
export function hostRouteParam(key = 'id'): string {
  const value = hostRouter?.currentRoute?.value?.params?.[key]
  return value === undefined || value === null ? '' : String(value)
}

/** 是否请求能力缺失（哨兵判定）。 */
export function isApiAbsent(error: unknown): boolean {
  return error instanceof Error && error.message === MODULE_API_ABSENT
}
