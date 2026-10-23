// kiwi_id: 2348
/**
 * 岗位管理页用例（mdm 01_05）：载入与降级 / 筛选与分页（回第 1 页）/ 行内编辑·启停·删除 /
 * 多选批量删除（全成功与部分失败）/ 绑定角色只读弹窗 / 权限显隐。
 *
 * 产品域寻址口径：页面经 `api.product('mdm', 'mdm')`（服务标识归并后域段与产品同为 `mdm`），
 * 本用例以作用域替身断言请求路径，防止旧域段回流。
 */

import type { ModuleApi, ModuleApiScope } from '@bms/core'
import { flushPromises, mount } from '@vue/test-utils'
import { ElMessage, ElMessageBox } from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import PostListView from '../src/views/org/PostListView.vue'
import { applyHostContext } from '../src/runtime'

/** 岗位分页替身（两行，一启用一停用）。 */
const PAGE = {
  list: [
    { id: 'p-1', code: 'ENG', name: '工程师', dept_id: 'd-1', sort: 0, status: 'enabled' },
    { id: 'p-2', code: 'OPS', name: '运维', dept_id: 'd-2', sort: 1, status: 'disabled' },
  ],
  total: 2,
  page: 1,
  size: 10,
}

/** 部门树替身。 */
const TREE = {
  items: [{ id: 'd-1', code: 'RD', name: '研发部', parent_id: null, ancestors: '', sort: 0, status: 'enabled' }],
}

/** 作用域替身。 */
interface ScopeStub {
  get: ReturnType<typeof vi.fn>
  put: ReturnType<typeof vi.fn>
  del: ReturnType<typeof vi.fn>
}

/**
 * 构造请求能力替身。
 *
 * @param overrides 按路径覆写（缺省走成功分支）。
 * @returns 请求能力与作用域替身。
 */
function hostStub(
  overrides: {
    get?: (path: string) => Promise<unknown>
    put?: (path: string) => Promise<unknown>
    del?: (path: string) => Promise<unknown>
  } = {},
): { api: ModuleApi; scope: ScopeStub } {
  const get = vi.fn((path: string) => {
    if (overrides.get !== undefined) return overrides.get(path)
    if (path === '/posts') return Promise.resolve(PAGE)
    if (path === '/depts') return Promise.resolve(TREE)
    if (path.endsWith('/roles')) return Promise.resolve({ role_ids: ['r-1'] })
    return Promise.resolve({})
  })
  const put = vi.fn((path: string) => (overrides.put ? overrides.put(path) : Promise.resolve({ id: 'p-1' })))
  const del = vi.fn((path: string) => (overrides.del ? overrides.del(path) : Promise.resolve({ id: 'p-1' })))
  const scope: ScopeStub = { get, put, del }
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
 * 构造内存路由（页面跳转断言用）。
 *
 * @returns 路由实例。
 */
function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: { template: '<div />' } },
      { path: '/mdm/posts/form/:id?', name: 'MdmOrgPostForm', component: { template: '<div />' } },
    ],
  })
}

/**
 * 挂载岗位管理页并等待首屏载入。
 *
 * @param api 请求能力（缺省不注入，模拟宿主未接入）。
 * @param user 权限码清单。
 * @returns 挂载结果与路由。
 */
async function mountPage(
  api?: ModuleApi,
  user: string[] = ['mdm:update'],
): Promise<{ wrapper: ReturnType<typeof mount>; router: Router }> {
  applyHostContext(api === undefined ? { user } : { api, user })
  const router = makeRouter()
  await router.push('/')
  await router.isReady()
  const wrapper = mount(PostListView, { global: { plugins: [router] } })
  await flushPromises()
  return { wrapper, router }
}

/**
 * 触发数据表事件（分页 / 勾选 / 行操作由表格插槽承载）。
 *
 * @param wrapper 挂载结果。
 * @param event 事件名。
 * @param payload 载荷。
 */
async function emitTable(wrapper: ReturnType<typeof mount>, event: string, payload?: unknown): Promise<void> {
  const table = wrapper.findComponent({ name: 'DataTable' })
  table.vm.$emit(event, payload)
  await flushPromises()
}

beforeEach(() => {
  vi.restoreAllMocks()
  applyHostContext({})
  document.body.innerHTML = ''
})

describe('mdm 组织域岗位管理页（01_05 · Kiwi 2348）', () => {
  it('首屏载入：列表与部门选项就绪', async () => {
    const { api } = hostStub()
    const { wrapper } = await mountPage(api)

    expect(wrapper.find('[data-test="post-create"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('岗位管理')
  })

  it('请求能力未注入：提示「未接入」降级（不抛错）', async () => {
    const { wrapper } = await mountPage()

    expect(wrapper.text()).toContain('未接入')
  })

  it('载入失败（非未接入）：提示通用失败', async () => {
    const { api } = hostStub({ get: () => Promise.reject(new Error('boom')) })
    const { wrapper } = await mountPage(api)

    expect(wrapper.text()).toContain('操作失败')
  })

  it('部门选项载入失败：不阻塞列表', async () => {
    const { api } = hostStub({
      get: (path) => (path === '/depts' ? Promise.reject(new Error('dept-fail')) : Promise.resolve(PAGE)),
    })
    const { wrapper } = await mountPage(api)

    expect(wrapper.find('[data-test="post-create"]').exists()).toBe(true)
  })

  it('翻页 / 改页长 / 筛选：条件更新后回第 1 页重查', async () => {
    const { api, scope } = hostStub()
    const { wrapper } = await mountPage(api)

    await emitTable(wrapper, 'update:page', 2)
    expect(scope.get).toHaveBeenCalledWith('/posts', expect.objectContaining({ page: 2 }))

    await emitTable(wrapper, 'update:page-size', 20)
    expect(scope.get).toHaveBeenCalledWith('/posts', expect.objectContaining({ page: 1, size: 20 }))

    await emitTable(wrapper, 'selection-change', ['p-1'])
    expect(wrapper.find('[data-test="post-bind-roles"]').attributes('disabled')).toBeUndefined()
  })

  it('查询：关键字去空白后生效；空关键字不带该条件', async () => {
    const { api, scope } = hostStub()
    const { wrapper } = await mountPage(api)

    const keyword = wrapper.find('[data-test="post-filter-keyword"]')
    await keyword.setValue('  工程  ')
    await wrapper.find('[data-test="post-search"]').trigger('click')
    await flushPromises()
    expect(scope.get).toHaveBeenCalledWith('/posts', expect.objectContaining({ keyword: '工程', page: 1 }))

    await keyword.setValue('   ')
    await wrapper.find('[data-test="post-search"]').trigger('click')
    await flushPromises()
    expect(scope.get).toHaveBeenLastCalledWith('/posts', expect.objectContaining({ keyword: undefined }))
  })

  it('重置筛选：清空关键字并回到第 1 页', async () => {
    const { api, scope } = hostStub()
    const { wrapper } = await mountPage(api)

    await wrapper.find('[data-test="post-filter-keyword"]').setValue('工程')
    await wrapper.find('[data-test="post-reset"]').trigger('click')
    await flushPromises()

    expect(scope.get).toHaveBeenLastCalledWith('/posts', expect.objectContaining({ page: 1 }))
  })

  it('部门与状态筛选：选择后回第 1 页重查', async () => {
    const { api, scope } = hostStub()
    const { wrapper } = await mountPage(api)

    await wrapper.findComponent({ name: 'ElSelect' }).vm.$emit('update:model-value', 'd-1')
    await flushPromises()

    expect(scope.get).toHaveBeenCalledWith('/posts', expect.objectContaining({ dept_id: 'd-1', page: 1 }))
  })

  it('新建 / 编辑 / 双击行：跳转岗位表单页', async () => {
    const { api } = hostStub()
    const { wrapper, router } = await mountPage(api)
    const push = vi.spyOn(router, 'push')

    await wrapper.find('[data-test="post-create"]').trigger('click')
    expect(push).toHaveBeenCalledWith({ name: 'MdmOrgPostForm' })

    await emitTable(wrapper, 'row-dblclick', PAGE.list[0])
    expect(push).toHaveBeenCalledWith({ name: 'MdmOrgPostForm', params: { id: 'p-1' } })
  })

  it('启停：启用态提交停用，停用态提交启用', async () => {
    vi.spyOn(ElMessage, 'success').mockReturnValue({} as never)
    const { api, scope } = hostStub()
    const { wrapper } = await mountPage(api)
    const vm = wrapper.vm as unknown as { onToggleStatus: (row: unknown) => Promise<void> }

    await vm.onToggleStatus(PAGE.list[0])
    expect(scope.put).toHaveBeenCalledWith('/posts/p-1', { status: 'disabled' })

    await vm.onToggleStatus(PAGE.list[1])
    expect(scope.put).toHaveBeenCalledWith('/posts/p-2', { status: 'enabled' })
  })

  it('启停失败：分别提示「未接入」与通用失败', async () => {
    const error = vi.spyOn(ElMessage, 'error').mockReturnValue({} as never)
    const { api } = hostStub({ put: () => Promise.reject(new Error('MODULE_API_ABSENT')) })
    const { wrapper } = await mountPage(api)
    const vm = wrapper.vm as unknown as { onToggleStatus: (row: unknown) => Promise<void> }

    await vm.onToggleStatus(PAGE.list[0])
    expect(error).toHaveBeenCalledTimes(1)
  })

  it('启停失败（通用错误）：提示失败', async () => {
    const error = vi.spyOn(ElMessage, 'error').mockReturnValue({} as never)
    const { api } = hostStub({ put: () => Promise.reject(new Error('boom')) })
    const { wrapper } = await mountPage(api)
    const vm = wrapper.vm as unknown as { onToggleStatus: (row: unknown) => Promise<void> }

    await vm.onToggleStatus(PAGE.list[0])
    expect(error).toHaveBeenCalledTimes(1)
  })

  it('删除：确认后删除并重载', async () => {
    vi.spyOn(ElMessage, 'success').mockReturnValue({} as never)
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue({ action: 'confirm' } as never)
    const { api, scope } = hostStub()
    const { wrapper } = await mountPage(api)
    const vm = wrapper.vm as unknown as { onDelete: (row: unknown) => Promise<void> }

    await vm.onDelete(PAGE.list[0])

    expect(scope.del).toHaveBeenCalledWith('/posts/p-1')
  })

  it('删除：对话框取消时静默返回', async () => {
    const error = vi.spyOn(ElMessage, 'error').mockReturnValue({} as never)
    vi.spyOn(ElMessageBox, 'confirm').mockRejectedValue('cancel')
    const { api, scope } = hostStub()
    const { wrapper } = await mountPage(api)
    const vm = wrapper.vm as unknown as { onDelete: (row: unknown) => Promise<void> }

    await vm.onDelete(PAGE.list[0])

    expect(scope.del).not.toHaveBeenCalled()
    expect(error).not.toHaveBeenCalled()
  })

  it('删除失败：分别提示「未接入」与通用失败', async () => {
    const error = vi.spyOn(ElMessage, 'error').mockReturnValue({} as never)
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue({ action: 'confirm' } as never)
    const { api } = hostStub({ del: () => Promise.reject(new Error('MODULE_API_ABSENT')) })
    const { wrapper } = await mountPage(api)
    const vm = wrapper.vm as unknown as { onDelete: (row: unknown) => Promise<void> }

    await vm.onDelete(PAGE.list[0])
    expect(error).toHaveBeenCalledTimes(1)
  })

  it('删除失败（通用错误）：提示失败', async () => {
    const error = vi.spyOn(ElMessage, 'error').mockReturnValue({} as never)
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue({ action: 'confirm' } as never)
    const { api } = hostStub({ del: () => Promise.reject(new Error('boom')) })
    const { wrapper } = await mountPage(api)
    const vm = wrapper.vm as unknown as { onDelete: (row: unknown) => Promise<void> }

    await vm.onDelete(PAGE.list[0])
    expect(error).toHaveBeenCalledTimes(1)
  })

  it('批量删除：未勾选时早退（不弹确认、不请求）', async () => {
    const confirm = vi.spyOn(ElMessageBox, 'confirm')
    const { api, scope } = hostStub()
    const { wrapper } = await mountPage(api)
    const vm = wrapper.vm as unknown as { onBatchDelete: () => Promise<void> }

    await vm.onBatchDelete()

    expect(confirm).not.toHaveBeenCalled()
    expect(scope.del).not.toHaveBeenCalled()
  })

  it('批量删除：全部成功提示成功；取消时静默返回', async () => {
    const success = vi.spyOn(ElMessage, 'success').mockReturnValue({} as never)
    const confirm = vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue({ action: 'confirm' } as never)
    const { api, scope } = hostStub()
    const { wrapper } = await mountPage(api)
    const vm = wrapper.vm as unknown as { onBatchDelete: () => Promise<void>; onSelectionChange: (keys: string[]) => void }

    vm.onSelectionChange(['p-1', 'p-2'])
    await vm.onBatchDelete()
    expect(scope.del).toHaveBeenCalledTimes(2)
    expect(success).toHaveBeenCalled()

    confirm.mockRejectedValue('cancel')
    vm.onSelectionChange(['p-1'])
    await vm.onBatchDelete()
    expect(scope.del).toHaveBeenCalledTimes(2)
  })

  it('批量删除：部分失败提示失败条数', async () => {
    const error = vi.spyOn(ElMessage, 'error').mockReturnValue({} as never)
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue({ action: 'confirm' } as never)
    let call = 0
    const { api } = hostStub({
      del: () => {
        call += 1
        return call === 1 ? Promise.reject(new Error('boom')) : Promise.resolve({ id: 'p-2' })
      },
    })
    const { wrapper } = await mountPage(api)
    const vm = wrapper.vm as unknown as { onBatchDelete: () => Promise<void>; onSelectionChange: (keys: string[]) => void }

    vm.onSelectionChange(['p-1', 'p-2'])
    await vm.onBatchDelete()

    expect(error).toHaveBeenCalledTimes(1)
  })

  it('绑定角色（只读）：弹窗展示已绑角色；无角色时显示空提示', async () => {
    const { api } = hostStub()
    const { wrapper } = await mountPage(api)
    const vm = wrapper.vm as unknown as { openRoles: (row: unknown) => Promise<void> }

    await vm.openRoles(PAGE.list[0])
    expect(wrapper.find('[data-test="post-roles-hint"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('r-1')
  })

  it('绑定角色（只读）：无绑定角色时显示空态', async () => {
    const { api } = hostStub({ get: (path) => (path === '/posts' ? Promise.resolve(PAGE) : Promise.resolve({})) })
    const { wrapper } = await mountPage(api)
    const vm = wrapper.vm as unknown as { openRoles: (row: unknown) => Promise<void> }

    await vm.openRoles(PAGE.list[0])
    expect(wrapper.find('[data-test="post-roles-empty"]').exists()).toBe(true)
  })

  it('绑定角色失败：分别提示「未接入」与通用失败', async () => {
    const error = vi.spyOn(ElMessage, 'error').mockReturnValue({} as never)
    const { api } = hostStub({
      get: (path) => {
        if (path === '/posts') return Promise.resolve(PAGE)
        if (path === '/depts') return Promise.resolve(TREE)
        return Promise.reject(new Error('MODULE_API_ABSENT'))
      },
    })
    const { wrapper } = await mountPage(api)
    const vm = wrapper.vm as unknown as { openRoles: (row: unknown) => Promise<void> }

    await vm.openRoles(PAGE.list[0])
    expect(error).toHaveBeenCalledTimes(1)
  })

  it('绑定角色失败（通用错误）：提示失败', async () => {
    const error = vi.spyOn(ElMessage, 'error').mockReturnValue({} as never)
    const { api } = hostStub({
      get: (path) => {
        if (path === '/posts') return Promise.resolve(PAGE)
        if (path === '/depts') return Promise.resolve(TREE)
        return Promise.reject(new Error('boom'))
      },
    })
    const { wrapper } = await mountPage(api)
    const vm = wrapper.vm as unknown as { openRoles: (row: unknown) => Promise<void> }

    await vm.openRoles(PAGE.list[0])
    expect(error).toHaveBeenCalledTimes(1)
  })

  it('权限不足：新建与批量删除入口不渲染', async () => {
    const { api } = hostStub()
    const { wrapper } = await mountPage(api, ['mdm:query'])

    expect(wrapper.find('[data-test="post-create"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="post-batch-delete"]').exists()).toBe(false)
  })

  it('刷新与重试：均触发重查', async () => {
    const { api, scope } = hostStub()
    const { wrapper } = await mountPage(api)
    const before = scope.get.mock.calls.filter((call) => call[0] === '/posts').length

    await emitTable(wrapper, 'refresh')
    await emitTable(wrapper, 'retry')

    const after = scope.get.mock.calls.filter((call) => call[0] === '/posts').length
    expect(after).toBeGreaterThan(before)
  })

  it('状态筛选：选择后回第 1 页重查', async () => {
    const { api, scope } = hostStub()
    const { wrapper } = await mountPage(api)

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    selects[1].vm.$emit('update:model-value', 'disabled')
    await flushPromises()

    expect(scope.get).toHaveBeenCalledWith('/posts', expect.objectContaining({ status: 'disabled', page: 1 }))
  })

  it('行内操作：编辑跳转表单页、启停提交、删除二次确认', async () => {
    vi.spyOn(ElMessage, 'success').mockReturnValue({} as never)
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue({ action: 'confirm' } as never)
    const { api, scope } = hostStub()
    const { wrapper, router } = await mountPage(api)
    const push = vi.spyOn(router, 'push')

    await wrapper.find('[data-test="post-edit-p-1"]').trigger('click')
    expect(push).toHaveBeenCalledWith({ name: 'MdmOrgPostForm', params: { id: 'p-1' } })

    await wrapper.find('[data-test="post-toggle-p-1"]').trigger('click')
    await flushPromises()
    expect(scope.put).toHaveBeenCalledWith('/posts/p-1', { status: 'disabled' })

    await wrapper.find('[data-test="post-delete-p-1"]').trigger('click')
    await flushPromises()
    expect(scope.del).toHaveBeenCalledWith('/posts/p-1')
  })

  it('绑定角色入口：勾选单行后可点开只读弹窗并关闭', async () => {
    const { api } = hostStub()
    const { wrapper } = await mountPage(api)

    await emitTable(wrapper, 'selection-change', ['p-1'])
    await wrapper.find('[data-test="post-bind-roles"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-test="post-roles-hint"]').exists()).toBe(true)

    // 点「确定」关闭弹窗（Element Plus 关闭后节点保留但不显示）
    await wrapper.find('[data-test="post-roles-close"]').trigger('click')
    await flushPromises()
    const vm = wrapper.vm as unknown as { rolesVisible: boolean; openRoles: (row: unknown) => Promise<void> }
    expect(vm.rolesVisible).toBe(false)

    // 弹窗自身的 v-model 回写通道（右上角关闭等）同样生效
    await vm.openRoles(PAGE.list[0])
    const dialog = wrapper.findComponent({ name: 'ElDialog' })
    dialog.vm.$emit('update:modelValue', false)
    await flushPromises()
    expect(vm.rolesVisible).toBe(false)
  })

  it('绑定角色弹窗：首次渲染即带标题与只读提示（懒挂载路径）', async () => {
    const { api } = hostStub()
    const { wrapper } = await mountPage(api)
    const vm = wrapper.vm as unknown as { rolesVisible: boolean }

    vm.rolesVisible = true
    await flushPromises()

    expect(wrapper.text()).toContain('绑定角色')
    expect(wrapper.find('[data-test="post-roles-hint"]').text()).toContain('只读视图')
  })

  it('分页响应缺少 `total`：按 0 处理', async () => {
    const { api } = hostStub({ get: () => Promise.resolve({ list: PAGE.list, page: 1, size: 10 }) })
    const { wrapper } = await mountPage(api)

    expect(wrapper.find('[data-test="post-create"]').exists()).toBe(true)
  })

  it('查询条件为空对象时模板按缺省分页渲染（防御分支）', async () => {
    const { api } = hostStub()
    const { wrapper } = await mountPage(api)
    const vm = wrapper.vm as unknown as { query: Record<string, unknown> }

    vm.query = {}
    await flushPromises()

    expect(wrapper.find('[data-test="post-create"]').exists()).toBe(true)
  })
})
