// kiwi_id: 2273
/**
 * 草稿语义与宿主提交器通道用例（mdm 01_02-02）：显式上下文 `userId` 优先、路由参数兜底；
 * 有 `registerSubmitter` 通道时勾选只进草稿（不写库）、宿主保存时才提交；无通道时「确定」即自提交。
 */

import type { ModuleApi, ModuleApiScope } from '@bms/core'
import { MODULE_SLOT_CONTEXT_KEY } from '@bms/ui-ep'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

import UserPostsPanel from '../src/components/slots/UserPostsPanel.vue'
import type { HostSubmitterEntry } from '../src/composables/useAssignment'
import { applyHostContext } from '../src/runtime'

/** 记录调用的作用域替身。 */
interface ScopeSpy {
  get: ReturnType<typeof vi.fn>
  put: ReturnType<typeof vi.fn>
}

/**
 * 构造按路径分派的请求能力替身（写方法记录调用）。
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
    if (path === '/user-posts') return Promise.resolve({ post_ids: ['p-1'], primary_post_id: 'p-1' })
    if (path === '/depts') {
      return Promise.resolve({ items: [{ id: 'd-1', name: '研发部', ancestors: '', sort: 0, status: 'enabled' }] })
    }
    return Promise.resolve({})
  })
  const scope: ScopeSpy = {
    get,
    put: vi.fn().mockResolvedValue({ post_ids: ['p-1'] }),
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
 * 以具名插槽上下文挂载「用户分配岗位」插件。
 *
 * @param context 插槽上下文（`userId` / `registerSubmitter` 等）。
 * @returns 挂载结果。
 */
function mountWithSlot(context: Record<string, unknown>): ReturnType<typeof mount> {
  return mount(UserPostsPanel, {
    global: {
      provide: { [MODULE_SLOT_CONTEXT_KEY as unknown as string]: ref(context) } as unknown as Record<string, unknown>,
    },
  })
}

/**
 * 打开分配弹窗并取消勾选首项（制造草稿差异）。
 *
 * @param wrapper 挂载结果。
 */
async function unpickFirst(wrapper: ReturnType<typeof mount>): Promise<void> {
  await wrapper.find('[data-test="assign-open"]').trigger('click')
  await flushPromises()
  await wrapper.find('[data-test="slot-user-posts-candidates"] input[type="checkbox"]').setValue(false)
  await flushPromises()
}

beforeEach(() => {
  applyHostContext({})
})

describe('mdm 组织域模块 · 草稿与宿主提交器通道（01_02-02 · Kiwi 2273）', () => {
  it('显式上下文通道：注入 userId 后载入已分配并按名称回显，主要项单选列就位', async () => {
    const { api } = hostStub()
    applyHostContext({ api })
    const wrapper = mountWithSlot({ userId: 'u-1' })
    await flushPromises()

    expect(wrapper.find('[data-test="assign-context-absent"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="assigned-table"]').text()).toContain('工程师')
    expect(wrapper.find('[data-test="assign-primary-p-1"]').exists()).toBe(true)
  })

  it('有宿主通道：勾选只进草稿（不写库）、脏标记为真、宿主保存时才提交', async () => {
    const entries: HostSubmitterEntry[] = []
    const registerSubmitter = vi.fn((entry: HostSubmitterEntry) => entries.push(entry))
    const { api, scope } = hostStub()
    applyHostContext({ api })
    const wrapper = mountWithSlot({ userId: 'u-1', registerSubmitter })
    await flushPromises()

    expect(registerSubmitter).toHaveBeenCalledTimes(1)
    expect(entries[0]?.isDirty()).toBe(false)

    await unpickFirst(wrapper)

    expect(entries[0]?.isDirty()).toBe(true)
    expect(scope.put).not.toHaveBeenCalled()
    expect(wrapper.find('[data-test="assign-dirty"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="assign-self-submit"]').exists()).toBe(false)

    await entries[0]?.submit()
    await flushPromises()

    expect(scope.put).toHaveBeenCalledWith('/user-posts/u-1', { post_ids: [] })
  })

  it('无宿主通道：给出自提交提示，「确定」即自提交（全量覆盖）', async () => {
    const { api, scope } = hostStub()
    applyHostContext({ api })
    const wrapper = mountWithSlot({ userId: 'u-1' })
    await flushPromises()

    expect(wrapper.find('[data-test="assign-self-submit"]').exists()).toBe(true)

    await unpickFirst(wrapper)
    expect(scope.put).not.toHaveBeenCalled()

    await wrapper.find('[data-test="assign-dialog-confirm"]').trigger('click')
    await flushPromises()

    expect(scope.put).toHaveBeenCalledWith('/user-posts/u-1', { post_ids: [] })
  })
})
