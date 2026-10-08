/**
 * 平台用户查询服务（**平台服务通道**：`api.get('platform', '/users')`）。
 *
 * 用户主数据归平台（`sys_user` 在 bms 侧），mdm 组织域只持有**用户-岗位关联**；
 * 插件的选择用户弹窗与已分配回显经平台契约取数，类型取平台生成类型 `@bms/api-types`（与 bms 侧同源）。
 */

import type { platform } from '@bms/api-types'

import { requiredHostApi } from '../runtime'

/** 平台契约 schema 集合别名。 */
type Schemas = platform.components['schemas']

/** 用户行（平台契约生成类型）。 */
export type PlatformUserItem = Schemas['UserItem']

/** 用户分页响应（`{ list, total, page, size }`）。 */
export type PlatformUserPage = Schemas['BasePageResponse_UserItem_']

/** 用户查询参数。 */
export interface PlatformUserQuery {
  /** 关键字（账号 / 姓名）。 */
  kw?: string
  /** 账号状态。 */
  status?: string
  /** 页码。 */
  page?: number
  /** 每页条数。 */
  size?: number
}

/**
 * 查询平台用户最小字段列表（选择用户弹窗 / 回显）。
 *
 * @param query 查询参数。
 * @returns 用户分页。
 */
export function fetchPlatformUsers(query: PlatformUserQuery = {}): Promise<PlatformUserPage> {
  return requiredHostApi().get<PlatformUserPage>('platform', '/users', { ...query })
}
