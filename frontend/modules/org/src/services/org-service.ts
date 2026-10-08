/**
 * 组织域数据服务（**产品域寻址**：`api.product('mdm', 'org')` → `/api/mdm/v1/org/...`）。
 *
 * 前缀组装、凭据注入、统一响应解包、401 静默刷新与重放**一律由平台宿主请求层处理**；
 * 模块**不自建 HTTP**（护栏 R3）、**不自拼前缀**（护栏 R4）、无 401 逻辑。
 * 请求能力未注入时抛哨兵错误（`MODULE_API_ABSENT`），调用方降级为「未接入」提示。
 */

import type { ModuleApiScope } from '@bms/core'

import type {
  DeptCreateRequest,
  DeptItem,
  DeptMoveRequest,
  DeptRoleIds,
  DeptTree,
  DeptUpdateRequest,
  DeptUserIds,
  PostCreateRequest,
  PostItem,
  PostPage,
  PostQuery,
  PostRoleIds,
  PostUpdateRequest,
  PostUserIds,
  RoleDeptAssignRequest,
  RoleDeptIds,
  RolePostAssignRequest,
  RolePostIds,
  UserPostAssignRequest,
  UserPostIds,
} from '../domain'
import { requiredHostApi } from '../runtime'

/** 产品键（与平台侧产品登记同源）。 */
export const ORG_PRODUCT = 'mdm'
/** 组织域段（产品自持域）。 */
export const ORG_DOMAIN = 'org'

/**
 * 组织域管理面作用域（每次取用；请求能力未注入即抛哨兵错误）。
 *
 * @returns 产品域请求作用域。
 */
function scope(): ModuleApiScope {
  return requiredHostApi().product(ORG_PRODUCT, ORG_DOMAIN)
}

/* ---------------------------------- 部门 ---------------------------------- */

/**
 * 部门树（一次性返回、`children` 嵌套、不分页）。
 *
 * @param status 状态过滤（缺省全部）。
 * @returns 部门树（`{ items: [...] }`）。
 */
export function fetchDeptTree(status?: string): Promise<DeptTree> {
  return scope().get<DeptTree>('/depts', status === undefined || status === '' ? undefined : { status })
}

/**
 * 部门详情。
 *
 * @param deptId 部门标识。
 * @returns 部门行。
 */
export function fetchDept(deptId: string): Promise<DeptItem> {
  return scope().get<DeptItem>(`/depts/${deptId}`)
}

/**
 * 新建部门。
 *
 * @param body 新建请求体。
 * @returns 新建后的部门行。
 */
export function createDept(body: DeptCreateRequest): Promise<DeptItem> {
  return scope().post<DeptItem>('/depts', body)
}

/**
 * 更新部门。
 *
 * @param deptId 部门标识。
 * @param body 更新请求体。
 * @returns 更新后的部门行。
 */
export function updateDept(deptId: string, body: DeptUpdateRequest): Promise<DeptItem> {
  return scope().put<DeptItem>(`/depts/${deptId}`, body)
}

/**
 * 移动部门（级联维护子树）。
 *
 * @param deptId 部门标识。
 * @param body 移动请求体。
 * @returns 移动后的部门行。
 */
export function moveDept(deptId: string, body: DeptMoveRequest): Promise<DeptItem> {
  return scope().put<DeptItem>(`/depts/${deptId}/move`, body)
}

/**
 * 删除部门（存在子部门 / 岗位 / 角色分配时后端拒绝）。
 *
 * @param deptId 部门标识。
 * @returns 被删除的部门行。
 */
export function deleteDept(deptId: string): Promise<DeptItem> {
  return scope().del<DeptItem>(`/depts/${deptId}`)
}

/**
 * 部门下用户标识（只读）。
 *
 * @param deptId 部门标识。
 * @returns 用户标识集合。
 */
export function fetchDeptUserIds(deptId: string): Promise<DeptUserIds> {
  return scope().get<DeptUserIds>(`/depts/${deptId}/users`)
}

/**
 * 部门下角色标识（只读）。
 *
 * @param deptId 部门标识。
 * @returns 角色标识集合。
 */
export function fetchDeptRoleIds(deptId: string): Promise<DeptRoleIds> {
  return scope().get<DeptRoleIds>(`/depts/${deptId}/roles`)
}

/* ---------------------------------- 岗位 ---------------------------------- */

/**
 * 岗位分页（按部门含子级筛选）。
 *
 * @param query 查询条件。
 * @returns 分页响应（`{ list, total, page, size }`）。
 */
export function fetchPostPage(query: PostQuery = {}): Promise<PostPage> {
  return scope().get<PostPage>('/posts', { ...query })
}

/**
 * 岗位详情。
 *
 * @param postId 岗位标识。
 * @returns 岗位行。
 */
export function fetchPost(postId: string): Promise<PostItem> {
  return scope().get<PostItem>(`/posts/${postId}`)
}

/**
 * 新建岗位。
 *
 * @param body 新建请求体。
 * @returns 新建后的岗位行。
 */
export function createPost(body: PostCreateRequest): Promise<PostItem> {
  return scope().post<PostItem>('/posts', body)
}

/**
 * 更新岗位（含启停）。
 *
 * @param postId 岗位标识。
 * @param body 更新请求体。
 * @returns 更新后的岗位行。
 */
export function updatePost(postId: string, body: PostUpdateRequest): Promise<PostItem> {
  return scope().put<PostItem>(`/posts/${postId}`, body)
}

/**
 * 删除岗位（存在用户 / 角色分配时后端拒绝）。
 *
 * @param postId 岗位标识。
 * @returns 被删除的岗位行。
 */
export function deletePost(postId: string): Promise<PostItem> {
  return scope().del<PostItem>(`/posts/${postId}`)
}

/**
 * 岗位下用户标识（只读）。
 *
 * @param postId 岗位标识。
 * @returns 用户标识集合。
 */
export function fetchPostUserIds(postId: string): Promise<PostUserIds> {
  return scope().get<PostUserIds>(`/posts/${postId}/users`)
}

/**
 * 岗位下角色标识（只读）。
 *
 * @param postId 岗位标识。
 * @returns 角色标识集合。
 */
export function fetchPostRoleIds(postId: string): Promise<PostRoleIds> {
  return scope().get<PostRoleIds>(`/posts/${postId}/roles`)
}

/* ------------------------------ 用户-岗位（分配） ------------------------------ */

/**
 * 按用户查已分配岗位。
 *
 * @param userId 用户标识（宿主页作用实体）。
 * @returns 岗位标识集合。
 */
export function fetchUserPostIds(userId: string): Promise<UserPostIds> {
  return scope().get<UserPostIds>('/user-posts', { user_id: userId })
}

/**
 * 用户-岗位**全量覆盖**分配（即时提交，不随宿主工具栏保存）。
 *
 * @param userId 用户标识。
 * @param body 全量岗位标识。
 * @returns 提交后的岗位标识集合。
 */
export function assignUserPosts(userId: string, body: UserPostAssignRequest): Promise<UserPostIds> {
  return scope().put<UserPostIds>(`/user-posts/${userId}`, body)
}

/**
 * 解绑单个用户-岗位。
 *
 * @param userId 用户标识。
 * @param postId 岗位标识。
 * @returns 解绑后的岗位标识集合。
 */
export function unassignUserPost(userId: string, postId: string): Promise<UserPostIds> {
  return scope().del<UserPostIds>(`/user-posts/${userId}/${postId}`)
}

/* ------------------------------ 角色-岗位（分配） ------------------------------ */

/**
 * 按角色查已分配岗位。
 *
 * @param roleId 角色标识（宿主页显式上下文）。
 * @returns 岗位标识集合。
 */
export function fetchRolePostIds(roleId: string): Promise<RolePostIds> {
  return scope().get<RolePostIds>('/role-posts', { role_id: roleId })
}

/**
 * 角色-岗位**全量覆盖**分配（即时提交）。
 *
 * @param roleId 角色标识。
 * @param body 全量岗位标识。
 * @returns 提交后的岗位标识集合。
 */
export function assignRolePosts(roleId: string, body: RolePostAssignRequest): Promise<RolePostIds> {
  return scope().put<RolePostIds>(`/role-posts/${roleId}`, body)
}

/**
 * 解绑单个角色-岗位。
 *
 * @param roleId 角色标识。
 * @param postId 岗位标识。
 * @returns 解绑后的岗位标识集合。
 */
export function unassignRolePost(roleId: string, postId: string): Promise<RolePostIds> {
  return scope().del<RolePostIds>(`/role-posts/${roleId}/${postId}`)
}

/* ------------------------------ 角色-部门（分配） ------------------------------ */

/**
 * 按角色查已分配部门（**精确匹配，不含子部门**）。
 *
 * @param roleId 角色标识。
 * @returns 部门标识集合。
 */
export function fetchRoleDeptIds(roleId: string): Promise<RoleDeptIds> {
  return scope().get<RoleDeptIds>('/role-depts', { role_id: roleId })
}

/**
 * 角色-部门**全量覆盖**分配（即时提交）。
 *
 * @param roleId 角色标识。
 * @param body 全量部门标识。
 * @returns 提交后的部门标识集合。
 */
export function assignRoleDepts(roleId: string, body: RoleDeptAssignRequest): Promise<RoleDeptIds> {
  return scope().put<RoleDeptIds>(`/role-depts/${roleId}`, body)
}

/**
 * 解绑单个角色-部门。
 *
 * @param roleId 角色标识。
 * @param deptId 部门标识。
 * @returns 解绑后的部门标识集合。
 */
export function unassignRoleDept(roleId: string, deptId: string): Promise<RoleDeptIds> {
  return scope().del<RoleDeptIds>(`/role-depts/${roleId}/${deptId}`)
}
