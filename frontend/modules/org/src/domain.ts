/**
 * 组织域领域类型与选项常量。
 *
 * **类型不手写**：一律自产品契约生成类型 `@mdm/api-types`（`org` 命名空间）取别名——
 * 后端契约变更后重生成即同步（`pnpm run api-types:gen`，漂移由 `gen:check` 阻断）。
 */

import type { org as orgContract } from '@mdm/api-types'

/** 契约 schema 集合别名。 */
type Schemas = orgContract.components['schemas']

/** 部门行（响应面）。 */
export type DeptItem = Schemas['DeptItem']
/** 部门树节点（响应面；`children` 嵌套，一次性返回不分页）。 */
export type DeptTreeNode = Schemas['DeptTreeNode']
/** 部门树（响应面：`{ items: [...] }` 包装）。 */
export type DeptTree = Schemas['DeptTree']
/** 新建部门请求体。 */
export type DeptCreateRequest = Schemas['DeptCreateRequest']
/** 更新部门请求体。 */
export type DeptUpdateRequest = Schemas['DeptUpdateRequest']
/** 移动部门请求体。 */
export type DeptMoveRequest = Schemas['DeptMoveRequest']
/** 部门下用户标识集合（只读）。 */
export type DeptUserIds = Schemas['DeptUserIds']
/** 部门下角色标识集合（只读）。 */
export type DeptRoleIds = Schemas['DeptRoleIds']

/** 岗位行（响应面）。 */
export type PostItem = Schemas['PostItem']
/** 岗位分页响应（`{ list, total, page, size }`）。 */
export type PostPage = Schemas['BasePageResponse_PostItem_']
/** 新建岗位请求体。 */
export type PostCreateRequest = Schemas['PostCreateRequest']
/** 更新岗位请求体。 */
export type PostUpdateRequest = Schemas['PostUpdateRequest']
/** 岗位下用户标识集合（只读）。 */
export type PostUserIds = Schemas['PostUserIds']
/** 岗位下角色标识集合（只读）。 */
export type PostRoleIds = Schemas['PostRoleIds']

/** 用户-岗位（按用户）标识集合。 */
export type UserPostIds = Schemas['UserPostIds']
/** 用户-岗位全量分配请求体。 */
export type UserPostAssignRequest = Schemas['UserPostAssignRequest']
/** 角色-岗位（按角色）标识集合。 */
export type RolePostIds = Schemas['RolePostIds']
/** 角色-岗位全量分配请求体。 */
export type RolePostAssignRequest = Schemas['RolePostAssignRequest']
/** 角色-部门（按角色）标识集合。 */
export type RoleDeptIds = Schemas['RoleDeptIds']
/** 角色-部门全量分配请求体。 */
export type RoleDeptAssignRequest = Schemas['RoleDeptAssignRequest']

/** 岗位列表查询（管理面）。 */
export interface PostQuery {
  /** 所属部门（含子级）。 */
  dept_id?: string
  /** 状态。 */
  status?: string
  /** 关键字（编码 / 名称）。 */
  keyword?: string
  /** 页码。 */
  page?: number
  /** 每页条数。 */
  size?: number
}

/** 启用 / 停用状态取值。 */
export const ENTITY_STATUS = {
  /** 启用。 */
  enabled: 'enabled',
  /** 停用。 */
  disabled: 'disabled',
} as const

/** 状态选项（界面用）。 */
export const STATUS_OPTIONS: readonly { value: string; labelKey: string }[] = [
  { value: ENTITY_STATUS.enabled, labelKey: 'mdmOrg.common.enabled' },
  { value: ENTITY_STATUS.disabled, labelKey: 'mdmOrg.common.disabled' },
]

/**
 * 标识参数归一（**契约请求面口径差异**）。
 *
 * 契约响应面把雪花标识声明为**字符串**（避免精度丢失），但部分请求体（如 `DeptCreateRequest.parent_id`、
 * `PostCreateRequest.dept_id`）在契约中被声明为整数型。此处**按字符串原样透传**并由后端宽松解析，
 * 不做 `Number()` 转换（雪花 id 超出 JS 安全整数范围，转换会丢精度）。
 * 差异已登记为契约口径遗留（见任务 01_04 实施记录 §6）。
 *
 * @param id 标识（字符串或空）。
 * @returns 透传值（`null` 表示无父级）。
 */
export function toIdParam(id: string | null | undefined): number | null {
  if (id === undefined || id === null || id === '') {
    return null
  }
  return id as unknown as number
}

/** 选项项（下拉 / 勾选列表 / 树通用）。 */
export interface DomainOption {
  /** 标识（字符串口径）。 */
  value: string
  /** 展示名（层级项带缩进）。 */
  label: string
}

/** 树节点（`el-tree` 数据面）。 */
export interface DeptTreeOption {
  /** 标识。 */
  id: string
  /** 展示名。 */
  label: string
  /** 子节点。 */
  children?: DeptTreeOption[]
}

/**
 * 部门树展平（带层级缩进；用于下拉筛选与勾选列表）。
 *
 * @param nodes 树节点。
 * @param depth 深度（递归用）。
 * @returns 展平选项。
 */
export function flattenDeptTree(nodes: readonly DeptTreeNode[], depth = 0): DomainOption[] {
  const result: DomainOption[] = []
  for (const node of nodes) {
    result.push({ value: String(node.id), label: `${'　'.repeat(depth)}${node.name}` })
    const children = (node.children ?? []) as DeptTreeNode[]
    if (children.length > 0) result.push(...flattenDeptTree(children, depth + 1))
  }
  return result
}

/**
 * 部门树转 `el-tree` 数据（**精确匹配**勾选口径下不级联，故仅作结构展示）。
 *
 * @param nodes 树节点。
 * @returns 树数据。
 */
export function toDeptTreeData(nodes: readonly DeptTreeNode[]): DeptTreeOption[] {
  return nodes.map((node) => {
    const children = (node.children ?? []) as DeptTreeNode[]
    return {
      id: String(node.id),
      label: node.name,
      ...(children.length > 0 ? { children: toDeptTreeData(children) } : {}),
    }
  })
}

/**
 * 标识集合参数归一（同上口径）。
 *
 * 契约的分配请求体（`UserPostAssignRequest.post_ids` / `RolePostAssignRequest.post_ids` /
 * `RoleDeptAssignRequest.dept_ids`）声明为整数数组，而标识在响应面为字符串；
 * 此处**按字符串原样透传**由后端宽松解析，不做数值转换（雪花 id 超出安全整数范围）。
 *
 * @param ids 标识集合（字符串口径）。
 * @returns 透传值（契约声明为数值数组）。
 */
export function toIdParamList(ids: readonly string[]): number[] {
  return ids as unknown as number[]
}
