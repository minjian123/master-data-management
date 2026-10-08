// kiwi_id: 2261
/**
 * 具名插槽插件用例（mdm 01_04）：三条上下文通道、弹窗分配（全量覆盖）与降级口径——
 * ① 路由参数（用户详情页）② 显式上下文注入（角色分配页签）③ 缺失即不请求 / 权限不足只读；
 * ④ 分配经弹窗「保存并提交」、单条解绑入口齐备。
 */

import type { ModuleApi, ModuleApiScope } from '@bms/core'
import { MODULE_SLOT_CONTEXT_KEY } from '@bms/ui-ep'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

import RoleDeptsPanel from '../src/components/slots/RoleDeptsPanel.vue'
import RolePostsPanel from '../src/components/slots/RolePostsPanel.vue'
import UserPostsPanel from '../src/components/slots/UserPostsPanel.vue'
import { applyHostContext } from '../src/runtime'

/** 记录调用的作用域替身。 */
interface ScopeSpy {
  get: ReturnType<typeof vi.fn>
  put: ReturnType<typeof vi.fn>
}

/**
 * 构造按路径分派的请求能力替身（返回最小可用数据；写方法记录调用）。
 *
 * @returns 请求能力与作用域替身。
 */
function hostStub(): { api: ModuleApi; scope: ScopeSpy } {
  const get = vi.fn((path: string) => {
    if (path === '/posts') {
      return Promise.resolve({
        list: [{ id: 'p-1', code: 'ENG', name: '工程师', dept_id: 'd-1', sort: 0, status: 'enabled' }],
        total: 1,
        page: 1,
        size: 200,
      })
    }
    if (path === '/user-posts') return Promise.resolve({ post_ids: ['p-1'] })
    if (path === '/role-posts') return Promise.resolve({ post_ids: ['p-1'] })
    if (path === '/role-depts') return Promise.resolve({ dept_ids: ['d-1'] })
    if (path === '/depts') {
      return Promise.resolve({ items: [{ id: 'd-1', name: '研发部', ancestors: '', sort: 0, status: 'enabled' }] })
    }
    return Promise.resolve({})
  })
  const scope: ScopeSpy = {
    get,
    put: vi.fn().mockResolvedValue({ post_ids: ['p-1'], dept_ids: ['d-1'] }),
  }
  const api = {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    del: vi.fn(),
    request: vi.fn(),
    product: vi.fn(() => scope as unknown as ModuleApiScope),
  } as unknown as ModuleApi
  return { api, scope }
}

/**
 * 以显式上下文通道挂载插件（宿主页提供 `roleId`）。
 *
 * @param component 插件组件。
 * @param roleId 角色标识（缺省不注入，模拟上下文缺失）。
 * @returns 挂载结果。
 */
function mountWithContext(
  component: typeof RoleDeptsPanel | typeof RolePostsPanel,
  roleId?: string,
): ReturnType<typeof mount> {
  return mount(component, {
    global: {
      provide:
        roleId === undefined
          ? {}
          : ({ [MODULE_SLOT_CONTEXT_KEY as unknown as string]: ref({ roleId }) } as unknown as Record<string, unknown>),
    },
  })
}

beforeEach(() => {
  applyHostContext({})
})

describe('mdm 组织域模块 · 具名插槽插件（01_04 · Kiwi 2261）', () => {
  it('路由参数通道缺失（无宿主路由）：上下文缺失即提示，不发起请求', async () => {
    const { api, scope } = hostStub()
    applyHostContext({ api })
    const wrapper = mount(UserPostsPanel)
    await flushPromises()

    expect(wrapper.find('[data-test="assign-context-absent"]').exists()).toBe(true)
    expect(scope.get).not.toHaveBeenCalled()
  })

  it('路由参数通道可用：已分配列表按名称回显（产品域寻址）', async () => {
    const { api } = hostStub()
    applyHostContext({ api, router: { currentRoute: { value: { params: { id: 'u-1' } } } } })
    const wrapper = mount(UserPostsPanel)
    await flushPromises()

    expect(wrapper.find('[data-test="assign-context-absent"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="assigned-table"]').text()).toContain('工程师')
    expect(wrapper.find('[data-test="assign-open"]').exists()).toBe(true)
  })

  it('弹窗分配：打开弹窗勾选候选并「保存并提交」按全量覆盖写回', async () => {
    const { api, scope } = hostStub()
    applyHostContext({ api, router: { currentRoute: { value: { params: { id: 'u-1' } } } } })
    const wrapper = mount(UserPostsPanel)
    await flushPromises()

    await wrapper.find('[data-test="assign-open"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-test="slot-user-posts-candidates"]').text()).toContain('工程师')

    await wrapper.find('[data-test="assign-dialog-submit"]').trigger('click')
    await flushPromises()

    expect(scope.put).toHaveBeenCalledWith('/user-posts/u-1', { post_ids: ['p-1'] })
  })

  it('单条解绑入口齐备（写侧经服务层，二次确认后立即生效）', async () => {
    const { api } = hostStub()
    applyHostContext({ api, router: { currentRoute: { value: { params: { id: 'u-1' } } } } })
    const wrapper = mount(UserPostsPanel)
    await flushPromises()

    expect(wrapper.find('[data-test="assign-unbind-p-1"]').exists()).toBe(true)
  })

  it('显式上下文通道（角色分配页签）：注入 roleId 后载入已分配岗位', async () => {
    const { api } = hostStub()
    applyHostContext({ api })
    const wrapper = mountWithContext(RolePostsPanel, 'r-1')
    await flushPromises()

    expect(wrapper.find('[data-test="assign-context-absent"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="assigned-table"]').text()).toContain('工程师')
  })

  it('部门分配：弹窗内为部门树多选并提示精确匹配（不含下级）', async () => {
    const { api } = hostStub()
    applyHostContext({ api })
    const wrapper = mountWithContext(RoleDeptsPanel, 'r-1')
    await flushPromises()

    expect(wrapper.find('[data-test="assigned-table"]').text()).toContain('研发部')

    await wrapper.find('[data-test="assign-open"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-test="slot-role-depts-hint"]').text()).toContain('精确匹配')
    expect(wrapper.find('[data-test="slot-role-depts-tree"]').exists()).toBe(true)
  })

  it('显式上下文缺失：给出上下文缺失提示且不请求（插件自行降级）', async () => {
    const { api, scope } = hostStub()
    applyHostContext({ api })
    const wrapper = mountWithRoleDeptsWithoutContext()
    await flushPromises()

    expect(wrapper.find('[data-test="assign-context-absent"]').exists()).toBe(true)
    expect(scope.get).not.toHaveBeenCalled()
  })

  it('权限不足：可写入口不渲染（显隐只是体验，后端强制校验）', async () => {
    const { api } = hostStub()
    applyHostContext({ api, user: ['other:perm'], router: { currentRoute: { value: { params: { id: 'u-1' } } } } })
    const wrapper = mount(UserPostsPanel)
    await flushPromises()

    expect(wrapper.find('[data-test="assign-no-permission"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="assign-open"]').exists()).toBe(false)
  })

  it('请求能力未注入：给出「未接入」降级提示且不报错', async () => {
    const wrapper = mountWithContext(RolePostsPanel, 'r-1')
    await flushPromises()

    expect(wrapper.find('[data-test="assign-error"]').text()).toContain('未接入')
  })
})

/** 挂载部门分配插件且不注入上下文（验证上下文缺失降级）。 */
function mountWithRoleDeptsWithoutContext(): ReturnType<typeof mount> {
  return mount(RoleDeptsPanel, { global: { provide: {} } })
}
