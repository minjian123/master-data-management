// kiwi_id: 2261
/**
 * 契约对齐门禁（mdm 01_04）：**前端调用面 ⊆ 产品契约**。
 *
 * 做法：以请求能力替身驱动**全部**服务方法（真实调用路径 / 参数），把捕获到的
 * 「方法 + 路径 + 查询参数名」与 `deploy/contracts/org.json`（产品契约快照，唯一事实源）逐条比对：
 *   - 路径（补产品域前缀后按模板归一）必须命中契约 `paths`；
 *   - 查询参数名必须命中该操作点声明的 `parameters`；
 *   - 比对为**双向覆盖**：契约中管理面端点（排除出口 / 探针）必须被前端覆盖，避免「端点在契约、前端漏接」。
 *
 * 该用例是「契约零漂移」在前端侧的对称面：`api-types:gen:check` 保证**类型**不漂移，
 * 本用例保证**调用面**不漂移（改路径 / 改名即失败）。
 */

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import type { ModuleApi, ModuleApiScope } from '@bms/core'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { applyHostContext } from '../src/runtime'
import {
  assignRoleDepts,
  assignRolePosts,
  assignUserPosts,
  createDept,
  createPost,
  deleteDept,
  deletePost,
  fetchDept,
  fetchDeptRoleIds,
  fetchDeptTree,
  fetchDeptUserIds,
  fetchPost,
  fetchPostPage,
  fetchPostRoleIds,
  fetchPostUserIds,
  fetchRoleDeptIds,
  fetchRolePostIds,
  fetchUserPostIds,
  moveDept,
  unassignRoleDept,
  unassignRolePost,
  unassignUserPost,
  updateDept,
  updatePost,
} from '../src/services/org-service'

/** 仓根（本测试位于 `modules/org/tests`）。 */
const REPO_ROOT = resolve(import.meta.dirname, '../../../..')
/** 产品契约快照（唯一事实源）。 */
const CONTRACT = JSON.parse(readFileSync(resolve(REPO_ROOT, 'deploy/contracts/org.json'), 'utf8')) as {
  paths: Record<string, Record<string, { parameters?: { name: string; in: string }[] }>>
}

/** 服务调用前缀（产品域前缀；模块侧只写相对路径）。 */
const PRODUCT_PREFIX = '/api/v1/org'

/** 用例中使用的实体标识（归一为路径模板时替换）。 */
const TEST_IDS = ['d-1', 'p-1', 'u-1', 'r-1', 'd-2']

/** 契约操作点（按**双向模板归一**后的路径索引：具体标识与 `{param}` 均归一为 `{}`）。 */
type ContractOps = Record<string, { parameters?: { name: string; in: string }[] }>

/**
 * 路径模板归一（把具体标识段替换为占位，便于与契约模板比对）。
 *
 * @param path 具体或模板路径。
 * @returns 模板路径。
 */
function toTemplate(path: string): string {
  let result = path
  for (const id of TEST_IDS) {
    result = result.split(`/${id}`).join('/{}')
  }
  return result.replace(/\{[^}]*\}/g, '{}')
}

/** 契约操作点（**双方同口径**归一后的索引：前端具体路径与契约 `{param}` 模板可比对）。 */
const NORMALIZED_CONTRACT: Map<string, ContractOps> = new Map(
  Object.entries(CONTRACT.paths).map(([path, ops]) => [toTemplate(path), ops]),
)

/** 捕获到的调用。 */
interface Call {
  /** 请求能力方法名（`del` 等）。 */
  method: string
  /** 资源子路径（不含产品域前缀）。 */
  path: string
  /** 查询参数（`get` / `del`）。 */
  params?: Record<string, unknown>
}

/** 请求能力方法名 → 契约 HTTP 动词。 */
const VERB: Record<string, string> = { get: 'get', post: 'post', put: 'put', patch: 'patch', del: 'delete' }

/** 安装请求能力替身并返回捕获数组。 */
function installSpy(): Call[] {
  const calls: Call[] = []
  const record = (method: string) => (path: string, arg?: unknown) => {
    calls.push({ method, path, params: method === 'get' ? (arg as Record<string, unknown>) : undefined })
    return Promise.resolve({})
  }
  const scope = {
    get: record('get'),
    post: record('post'),
    put: record('put'),
    patch: record('patch'),
    del: record('del'),
    request: vi.fn().mockResolvedValue({}),
  } as unknown as ModuleApiScope
  const api = {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    del: vi.fn(),
    request: vi.fn(),
    product: vi.fn(() => scope),
  } as unknown as ModuleApi
  applyHostContext({ api })
  return calls
}

/** 驱动全部服务方法（覆盖管理面端点）。 */
async function driveAllServices(): Promise<void> {
  await fetchDeptTree('enabled')
  await fetchDept('d-1')
  await createDept({ name: '研发部' })
  await updateDept('d-1', { name: '研发部' })
  await moveDept('d-1', { parent_id: null })
  await deleteDept('d-1')
  await fetchDeptUserIds('d-1')
  await fetchDeptRoleIds('d-1')

  await fetchPostPage({ dept_id: 'd-1', page: 1, size: 10 })
  await fetchPost('p-1')
  await createPost({ code: 'ENG', name: '工程师', dept_id: 1 })
  await updatePost('p-1', { name: '高级工程师' })
  await deletePost('p-1')
  await fetchPostUserIds('p-1')
  await fetchPostRoleIds('p-1')

  await fetchUserPostIds('u-1')
  await assignUserPosts('u-1', { post_ids: [1] })
  await unassignUserPost('u-1', 'p-1')

  await fetchRolePostIds('r-1')
  await assignRolePosts('r-1', { post_ids: [1] })
  await unassignRolePost('r-1', 'p-1')

  await fetchRoleDeptIds('r-1')
  await assignRoleDepts('r-1', { dept_ids: [1] })
  await unassignRoleDept('r-1', 'd-1')
}

beforeEach(() => {
  applyHostContext({})
})

describe('mdm 组织域模块 · 契约对齐（01_04 · Kiwi 2261）', () => {
  it('前端调用面 ⊆ 产品契约（逐条命中 paths）', async () => {
    const calls = installSpy()
    await driveAllServices()

    expect(calls.length).toBeGreaterThanOrEqual(20)
    for (const call of calls) {
      const templated = `${PRODUCT_PREFIX}${toTemplate(call.path)}`
      const ops = NORMALIZED_CONTRACT.get(templated)
      expect(ops, `契约缺少路径：${templated}`).toBeDefined()
      expect(Object.keys(ops ?? {})).toContain(VERB[call.method])
    }
  })

  it('查询参数名 ⊆ 契约声明（改参数名即失败）', async () => {
    const calls = installSpy()
    await driveAllServices()

    for (const call of calls.filter((item) => item.params !== undefined)) {
      const templated = `${PRODUCT_PREFIX}${toTemplate(call.path)}`
      const declared = (NORMALIZED_CONTRACT.get(templated)?.[VERB[call.method] ?? call.method]?.parameters ?? [])
        .filter((param) => param.in === 'query')
        .map((param) => param.name)
      for (const name of Object.keys(call.params ?? {})) {
        expect(declared, `${call.method.toUpperCase()} ${templated} 未声明查询参数：${name}`).toContain(name)
      }
    }
  })

  it('契约管理面端点被前端全部覆盖（防漏接；排除出口 / 探针）', async () => {
    const calls = installSpy()
    await driveAllServices()
    const covered = new Set(calls.map((call) => `${VERB[call.method] ?? call.method} ${toTemplate(call.path)}`))

    const management = Object.entries(CONTRACT.paths).filter(([path]) => {
      const relative = path.slice(PRODUCT_PREFIX.length)
      const excluded = path === '/' || path === '/healthz' || path === '/readyz'
      return !excluded && !relative.startsWith('/data-source') && relative !== '/resolve-names' && relative !== '/user-roles'
    })

    const missing = management
      .flatMap(([path, ops]) => Object.keys(ops).map((method) => `${method} ${toTemplate(path.slice(PRODUCT_PREFIX.length))}`))
      .filter((key) => !covered.has(key))

    expect(missing, `以下契约端点在模块服务层缺失：${missing.join('、')}`).toEqual([])
  })
})
