// kiwi_id: 2261
/**
 * 数据通路用例（mdm 01_04）：组织域经**产品域寻址**（`api.product('mdm','org')`）访问管理面端点、
 * 平台用户经**平台服务通道**（`api.get('platform','/users')`）——模块不自拼前缀、不自建 HTTP。
 */

import type { ModuleApi, ModuleApiScope } from '@bms/core'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { applyHostContext } from '../src/runtime'
import {
  assignRoleDepts,
  assignRolePosts,
  assignUserPosts,
  createDept,
  fetchDeptTree,
  fetchPostPage,
  fetchRoleDeptIds,
  fetchRolePostIds,
  fetchUserPostIds,
  moveDept,
  unassignUserPost,
} from '../src/services/org-service'
import { fetchPlatformUsers } from '../src/services/platform-user'

/** 记录调用的作用域替身。 */
interface ScopeSpy {
  get: ReturnType<typeof vi.fn>
  post: ReturnType<typeof vi.fn>
  put: ReturnType<typeof vi.fn>
  patch: ReturnType<typeof vi.fn>
  del: ReturnType<typeof vi.fn>
  request: ReturnType<typeof vi.fn>
}

/** 平台通道记录。 */
interface HostSpy {
  api: ModuleApi
  scope: ScopeSpy
  product: ReturnType<typeof vi.fn>
  get: ReturnType<typeof vi.fn>
}

/** 构造宿主请求能力替身（记录产品域寻址与平台通道调用）。 */
function hostSpy(): HostSpy {
  const scope: ScopeSpy = {
    get: vi.fn().mockResolvedValue({}),
    post: vi.fn().mockResolvedValue({}),
    put: vi.fn().mockResolvedValue({}),
    patch: vi.fn().mockResolvedValue({}),
    del: vi.fn().mockResolvedValue({}),
    request: vi.fn().mockResolvedValue({}),
  }
  const product = vi.fn(() => scope as unknown as ModuleApiScope)
  const get = vi.fn().mockResolvedValue({ list: [], total: 0, page: 1, size: 20 })
  const api = { get, post: vi.fn(), put: vi.fn(), del: vi.fn(), request: vi.fn(), product } as unknown as ModuleApi
  return { api, scope, product, get }
}

beforeEach(() => {
  applyHostContext({})
})

describe('mdm 组织域模块 · 数据通路（01_04 · Kiwi 2261）', () => {
  it('组织域一律经产品域寻址（产品键 mdm / 域 org），不自拼前缀', async () => {
    const spy = hostSpy()
    applyHostContext({ api: spy.api })

    await fetchDeptTree()
    await fetchPostPage({ dept_id: 'd-1', page: 1, size: 10 })

    expect(spy.product).toHaveBeenCalledWith('mdm', 'org')
    expect(spy.scope.get).toHaveBeenNthCalledWith(1, '/depts', undefined)
    expect(spy.scope.get).toHaveBeenNthCalledWith(2, '/posts', { dept_id: 'd-1', page: 1, size: 10 })
  })

  it('部门：树 / 移动 / 新建走管理面端点（含请求体形态）', async () => {
    const spy = hostSpy()
    applyHostContext({ api: spy.api })

    await fetchDeptTree('enabled')
    await moveDept('d-1', { parent_id: null })
    await createDept({ name: '研发部', parent_id: null, sort: 10 })

    expect(spy.scope.get).toHaveBeenCalledWith('/depts', { status: 'enabled' })
    expect(spy.scope.put).toHaveBeenCalledWith('/depts/d-1/move', { parent_id: null })
    expect(spy.scope.post).toHaveBeenCalledWith('/depts', { name: '研发部', parent_id: null, sort: 10 })
  })

  it('分配三通道：用户-岗位 / 角色-岗位 / 角色-部门（查询带实体标识、提交为全量覆盖）', async () => {
    const spy = hostSpy()
    applyHostContext({ api: spy.api })

    await fetchUserPostIds('u-1')
    await assignUserPosts('u-1', { post_ids: [1, 2] })
    await unassignUserPost('u-1', 'p-1')

    await fetchRolePostIds('r-1')
    await assignRolePosts('r-1', { post_ids: [1] })

    await fetchRoleDeptIds('r-1')
    await assignRoleDepts('r-1', { dept_ids: [3] })

    expect(spy.scope.get).toHaveBeenCalledWith('/user-posts', { user_id: 'u-1' })
    expect(spy.scope.put).toHaveBeenCalledWith('/user-posts/u-1', { post_ids: [1, 2] })
    expect(spy.scope.del).toHaveBeenCalledWith('/user-posts/u-1/p-1')

    expect(spy.scope.get).toHaveBeenCalledWith('/role-posts', { role_id: 'r-1' })
    expect(spy.scope.put).toHaveBeenCalledWith('/role-posts/r-1', { post_ids: [1] })

    expect(spy.scope.get).toHaveBeenCalledWith('/role-depts', { role_id: 'r-1' })
    expect(spy.scope.put).toHaveBeenCalledWith('/role-depts/r-1', { dept_ids: [3] })
  })

  it('平台用户经平台服务通道取数（不并入产品域作用域）', async () => {
    const spy = hostSpy()
    applyHostContext({ api: spy.api })

    await fetchPlatformUsers({ kw: 'zhang', page: 1, size: 20 })

    expect(spy.get).toHaveBeenCalledWith('platform', '/users', { kw: 'zhang', page: 1, size: 20 })
    expect(spy.product).not.toHaveBeenCalled()
  })

  it('请求能力未注入：服务抛哨兵错误（调用方降级为「未接入」提示）', () => {
    // 取用即抛（同步早失败）：作用域取用时校验请求能力存在性
    expect(() => fetchDeptTree()).toThrowError('MODULE_API_ABSENT')
  })
})
