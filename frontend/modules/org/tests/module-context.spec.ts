// kiwi_id: 2261
/**
 * 注入上下文只读消费与降级用例（mdm 01_04）：权限码派生可写态 / 请求能力缺失即哨兵 /
 * 只读路由参数取宿主页作用实体标识。
 */

import type { ModuleApi } from '@bms/core'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  applyHostContext,
  hostApiOf,
  hostRouteParam,
  isApiAbsent,
  MODULE_API_ABSENT,
  orgRuntime,
  requiredHostApi,
} from '../src/runtime'

/** 构造请求能力替身（仅需 `product` 与平台通道方法签名）。 */
function apiStub(): ModuleApi {
  return {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    del: vi.fn(),
    request: vi.fn(),
    product: vi.fn(),
  } as unknown as ModuleApi
}

beforeEach(() => {
  applyHostContext({})
})

describe('mdm 组织域模块 · 注入上下文消费（01_04 · Kiwi 2261）', () => {
  it('空上下文：不假定请求能力存在（取用即抛哨兵错误，调用方降级）', () => {
    expect(hostApiOf()).toBeUndefined()

    let caught: unknown
    try {
      requiredHostApi()
    } catch (error) {
      caught = error
    }
    expect(isApiAbsent(caught)).toBe(true)
    expect((caught as Error).message).toBe(MODULE_API_ABSENT)
  })

  it('权限码派生可写态：含 `org:update` 可写；无权限信息按可写（显隐只是体验）', () => {
    applyHostContext({ user: ['org:update'] })
    expect(orgRuntime().canUpdate).toBe(true)

    applyHostContext({ user: ['other:perm'] })
    expect(orgRuntime().canUpdate).toBe(false)

    applyHostContext({})
    expect(orgRuntime().canUpdate).toBe(true)
  })

  it('请求能力注入后经 `hostApiOf` 可取（服务层据此取数）', () => {
    const api = apiStub()
    applyHostContext({ api })
    expect(hostApiOf()).toBe(api)
  })

  it('只读路由参数通道：取宿主页作用实体标识（缺失返回空串，调用方降级）', () => {
    applyHostContext({ router: { currentRoute: { value: { params: { id: 'u-1' } } } } })
    expect(hostRouteParam()).toBe('u-1')
    expect(hostRouteParam('roleId')).toBe('')

    applyHostContext({})
    expect(hostRouteParam()).toBe('')
  })
})
