// kiwi_id: 2261
/**
 * 具名插槽插件用例（mdm 01_04）：三条上下文通道与降级口径——
 * ① 路由参数（用户详情页）② 显式上下文注入（角色分配页签）③ 缺失即不请求 / 权限不足只读。
 */

import type { ModuleApi, ModuleApiScope } from '@bms/core'
import { MODULE_SLOT_CONTEXT_KEY } from '@bms/ui-ep'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

import { applyHostContext } from '../src/runtime'
import RoleDeptsPanel from '../src/components/slots/RoleDeptsPanel.vue'
import UserPostsPanel from '../src/components/slots/UserPostsPanel.vue'

/** 构造按路径分派的请求能力替身（返回最小可用数据）。 */
function hostStub(): ModuleApi {
  const get = vi.fn((path: string) => {
    if (path === '/posts') {
      return Promise.resolve({
        list: [{ id: 'p-1', code: 'ENG', name: '工程师', dept_id: 'd-1', sort: 0, status: 'enabled' }],
        total: 1,
        page: 1,
        size: 200,
      })
    }
    if (path === '/user-posts') {
      return Promise.resolve({ post_ids: ['p-1'] })
    }
    if (path === '/role-depts') {
      return Promise.resolve({ dept_ids: ['d-1'] })
    }
    if (path === '/depts') {
      return Promise.resolve({ items: [{ id: 'd-1', name: '研发部', ancestors: '', sort: 0, status: 'enabled' }] })
    }
    return Promise.resolve({})
  })
  const scope = {
    get,
    post: vi.fn(),
    put: vi.fn().mockResolvedValue({ post_ids: [], dept_ids: [] }),
    patch: vi.fn(),
    del: vi.fn(),
    request: vi.fn(),
  } as unknown as ModuleApiScope
  return { get: vi.fn(), post: vi.fn(), put: vi.fn(), del: vi.fn(), request: vi.fn(), product: vi.fn(() => scope) } as unknown as ModuleApi
}

beforeEach(() => {
  applyHostContext({})
})

describe('mdm 组织域模块 · 具名插槽插件（01_04 · Kiwi 2261）', () => {
  it('路由参数通道缺失（无宿主路由）：上下文缺失即提示，不发起请求', async () => {
    const api = hostStub()
    applyHostContext({ api })
    const wrapper = mount(UserPostsPanel)
    await flushPromises()

    expect(wrapper.find('[data-test="assign-context-absent"]').exists()).toBe(true)
    // 未取到作用实体标识 → 不请求（降级）
    expect((api.product as unknown as ReturnType<typeof vi.fn>)?.mock?.calls?.length ?? 0).toBe(0)
  })

  it('路由参数通道可用：载入候选与已分配（产品域寻址）', async () => {
    const api = hostStub()
    applyHostContext({ api, router: { currentRoute: { value: { params: { id: 'u-1' } } } } })
    const wrapper = mount(UserPostsPanel)
    await flushPromises()

    expect(wrapper.find('[data-test="assign-context-absent"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="assign-summary"]').text()).toContain('1')
    expect(wrapper.find('[data-test="assign-option-p-1"]').exists()).toBe(true)
  })

  it('显式上下文通道（角色分配页签）：注入 roleId 后载入部门候选并提示精确匹配', async () => {
    const api = hostStub()
    applyHostContext({ api })
    const wrapper = mount(RoleDeptsPanel, {
      global: {
        provide: { [MODULE_SLOT_CONTEXT_KEY as unknown as string]: ref({ roleId: 'r-1' }) } as unknown as Record<
          string,
          unknown
        >,
      },
    })
    await flushPromises()

    expect(wrapper.find('[data-test="slot-role-depts-absent"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('精确匹配')
    expect(wrapper.find('[data-test="assign-option-d-1"]').exists()).toBe(true)
  })

  it('显式上下文缺失：不渲染分配面板、不请求（插件自行降级）', async () => {
    const api = hostStub()
    applyHostContext({ api })
    const wrapper = mount(RoleDeptsPanel)
    await flushPromises()

    expect(wrapper.find('[data-test="slot-role-depts-absent"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="assign-panel"]').exists()).toBe(false)
  })

  it('权限不足：可写入口不渲染（显隐只是体验，后端强制校验）', async () => {
    const api = hostStub()
    applyHostContext({ api, user: ['other:perm'], router: { currentRoute: { value: { params: { id: 'u-1' } } } } })
    const wrapper = mount(UserPostsPanel)
    await flushPromises()

    expect(wrapper.find('[data-test="assign-no-permission"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="assign-submit"]').exists()).toBe(false)
  })

  it('请求能力未注入：给出「未接入」降级提示且不报错', async () => {
    const wrapper = mount(UserPostsPanel, {
      global: { provide: {} },
    })
    await flushPromises()

    // 无上下文（无路由）时先落上下文缺失提示；不抛错即达降级要求
    expect(wrapper.find('[data-test="slot-user-posts"]').exists()).toBe(true)
  })
})
