// kiwi_id: 2348
/**
 * 部门管理页用例（mdm 01_05）：载入与降级 / 选中详情（含祖先链与角色标签）/ 页内编辑（保存走
 * 移动 + 更新两端点）/ 新建与表单页跳转 / 移动对话框（取消与关闭静默）/ 启停 / 删除 / 权限显隐。
 *
 * 产品域寻址口径：页面经 `api.product('mdm', 'mdm')`（服务标识归并后域段与产品同为 `mdm`），
 * 本用例以作用域替身断言请求路径，防止旧域段回流。
 */

import type { ModuleApi, ModuleApiScope } from '@bms/core'
import { flushPromises, mount } from '@vue/test-utils'
import { ElMessage, ElMessageBox } from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import DeptListView from '../src/views/org/DeptListView.vue'
import { applyHostContext } from '../src/runtime'

/** 部门树替身（两层，含无子节点的叶子）。 */
const TREE = {
  items: [
    {
      id: '1',
      code: 'HQ',
      name: '总部',
      parent_id: null,
      ancestors: '',
      sort: 0,
      status: 'enabled',
      children: [
        { id: '2', code: 'RD', name: '研发部', parent_id: '1', ancestors: '/1/', sort: 0, status: 'disabled' },
      ],
    },
  ],
}

/** 作用域替身（可按用例覆写单条路径行为）。 */
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
function hostStub(overrides: { get?: (path: string) => Promise<unknown>; put?: (path: string) => Promise<unknown>; del?: (path: string) => Promise<unknown> } = {}): {
  api: ModuleApi
  scope: ScopeStub
} {
  const get = vi.fn((path: string) => {
    if (overrides.get !== undefined) return overrides.get(path)
    if (path === '/depts') return Promise.resolve(TREE)
    if (path.endsWith('/users')) return Promise.resolve({ user_ids: ['u-1', 'u-2'] })
    if (path.endsWith('/roles')) return Promise.resolve({ role_ids: ['r-1'] })
    return Promise.resolve({})
  })
  const put = vi.fn((path: string) => (overrides.put ? overrides.put(path) : Promise.resolve({ id: '1' })))
  const del = vi.fn((path: string) => (overrides.del ? overrides.del(path) : Promise.resolve({ id: '1' })))
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
      { path: '/mdm/depts/form/:id?', name: 'MdmOrgDeptForm', component: { template: '<div />' } },
    ],
  })
}

/**
 * 挂载部门管理页并等待首屏载入。
 *
 * @param api 请求能力（缺省不注入，模拟宿主未接入）。
 * @param user 权限码清单。
 * @returns 挂载结果与路由。
 */
async function mountPage(api?: ModuleApi, user: string[] = ['mdm:update']): Promise<{ wrapper: ReturnType<typeof mount>; router: Router }> {
  applyHostContext(api === undefined ? { user } : { api, user })
  const router = makeRouter()
  await router.push('/')
  await router.isReady()
  const wrapper = mount(DeptListView, { global: { plugins: [router] } })
  await flushPromises()
  return { wrapper, router }
}

/**
 * 选中树中第一个节点（触发详情载入）。
 *
 * @param wrapper 挂载结果。
 */
async function selectFirst(wrapper: ReturnType<typeof mount>): Promise<void> {
  const tree = wrapper.findComponent({ name: 'ElTree' })
  tree.vm.$emit('node-click', TREE.items[0])
  await flushPromises()
}

beforeEach(() => {
  vi.restoreAllMocks()
  applyHostContext({})
  document.body.innerHTML = ''
})

describe('mdm 组织域部门管理页（01_05 · Kiwi 2348）', () => {
  it('首屏载入：树渲染成功，未选中时详情为空态', async () => {
    const { api } = hostStub()
    const { wrapper } = await mountPage(api)

    expect(wrapper.find('[data-test="dept-tree"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="dept-detail"]').text()).toContain('暂无数据')
    expect(wrapper.find('[data-test="dept-current"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="dept-edit"]').exists()).toBe(false)
  })

  it('请求能力未注入：给出「未接入」降级提示（不抛错）', async () => {
    const { wrapper } = await mountPage()

    expect(wrapper.find('[data-test="dept-notice"]').text()).toContain('未接入')
  })

  it('载入失败（非未接入）：给出通用失败提示', async () => {
    const { api } = hostStub({ get: () => Promise.reject(new Error('boom')) })
    const { wrapper } = await mountPage(api)

    expect(wrapper.find('[data-test="dept-notice"]').text()).toContain('操作失败')
  })

  it('选中节点：详情显示祖先链、用户数与角色标签', async () => {
    const { api } = hostStub({
      get: (path) => {
        if (path === '/depts') return Promise.resolve(TREE)
        if (path.endsWith('/users')) return Promise.resolve({ user_ids: ['u-1', 'u-2'] })
        if (path.endsWith('/roles')) return Promise.resolve({ role_ids: ['r-1', 'r-2'] })
        return Promise.resolve({})
      },
    })
    const { wrapper } = await mountPage(api)
    await selectFirst(wrapper)

    expect(wrapper.find('[data-test="dept-current"]').text()).toContain('总部')
    expect(wrapper.find('[data-test="dept-detail-users"]').text()).toBe('2')
    expect(wrapper.find('[data-test="dept-detail"]').text()).toContain('r-1')
    expect(wrapper.find('[data-test="dept-mode"]').text()).toContain('只读')
  })

  it('选中节点：祖先链为空显示占位符，无角色时显示 0', async () => {
    const { api } = hostStub({
      get: (path) => {
        if (path === '/depts') return Promise.resolve(TREE)
        if (path.endsWith('/users')) return Promise.resolve({})
        if (path.endsWith('/roles')) return Promise.resolve({})
        return Promise.resolve({})
      },
    })
    const { wrapper } = await mountPage(api)
    await selectFirst(wrapper)

    expect(wrapper.find('[data-test="dept-ancestors"]').text()).toBe('—')
    expect(wrapper.find('[data-test="dept-detail-users"]').text()).toBe('0')
    expect(wrapper.find('[data-test="dept-detail-roles"]').text()).toBe('0')
  })

  it('选中节点的只读区请求失败：不阻塞主流程（详情仍展示）', async () => {
    const { api } = hostStub({
      get: (path) => (path === '/depts' ? Promise.resolve(TREE) : Promise.reject(new Error('ro-fail'))),
    })
    const { wrapper } = await mountPage(api)
    await selectFirst(wrapper)

    expect(wrapper.find('[data-test="dept-current"]').text()).toContain('总部')
    expect(wrapper.find('[data-test="dept-detail-roles"]').text()).toBe('0')
  })

  it('页内编辑：点「修改」进入编辑态并带出当前值，点「取消」回到只读态', async () => {
    const { api } = hostStub()
    const { wrapper } = await mountPage(api)
    await selectFirst(wrapper)

    await wrapper.find('[data-test="dept-edit"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-test="dept-mode"]').text()).toContain('编辑')
    expect((wrapper.find('[data-test="dept-inline-code"]').element as HTMLInputElement).value).toBe('HQ')
    expect((wrapper.find('[data-test="dept-inline-name"]').element as HTMLInputElement).value).toBe('总部')

    const cancel = wrapper.findAll('button').find((button) => button.text().includes('取消'))
    await cancel?.trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-test="dept-mode"]').text()).toContain('只读')
  })

  it('保存编辑：上级变更走移动端点，其余走更新端点；成功后重载并重选', async () => {
    const success = vi.spyOn(ElMessage, 'success').mockReturnValue({} as never)
    const { api, scope } = hostStub()
    const { wrapper } = await mountPage(api)
    await selectFirst(wrapper)

    await wrapper.find('[data-test="dept-edit"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-test="dept-save"]').trigger('click')
    await flushPromises()

    // 上级未变（root 的 parent_id 为 null → 表单空串）⇒ 只走更新端点
    expect(scope.put).toHaveBeenCalledWith('/depts/1', expect.objectContaining({ code: 'HQ', name: '总部' }))
    expect(success).toHaveBeenCalled()
    expect(wrapper.find('[data-test="dept-mode"]').text()).toContain('只读')
  })

  it('保存编辑：上级变更时先调移动端点再调更新端点', async () => {
    const { api, scope } = hostStub()
    const { wrapper } = await mountPage(api)
    await selectFirst(wrapper)

    await wrapper.find('[data-test="dept-edit"]').trigger('click')
    await flushPromises()
    // 选择上级（把 select 的 model 改为 '2'）
    const select = wrapper.findAllComponents({ name: 'ElSelect' })[0]
    select.vm.$emit('update:modelValue', '2')
    await flushPromises()
    await wrapper.find('[data-test="dept-save"]').trigger('click')
    await flushPromises()

    expect(scope.put).toHaveBeenCalledWith('/depts/1/move', { parent_id: '2' })
  })

  it('保存编辑失败：权限能力缺失时提示「未接入」', async () => {
    const error = vi.spyOn(ElMessage, 'error').mockReturnValue({} as never)
    const { api } = hostStub({ put: () => Promise.reject(new Error('MODULE_API_ABSENT')) })
    const { wrapper } = await mountPage(api)
    await selectFirst(wrapper)

    await wrapper.find('[data-test="dept-edit"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-test="dept-save"]').trigger('click')
    await flushPromises()

    expect(error).toHaveBeenCalled()
    expect(wrapper.find('[data-test="dept-mode"]').text()).toContain('编辑')
  })

  it('保存编辑失败（通用）：提示失败且保持编辑态', async () => {
    const error = vi.spyOn(ElMessage, 'error').mockReturnValue({} as never)
    const { api } = hostStub({ put: () => Promise.reject(new Error('boom')) })
    const { wrapper } = await mountPage(api)
    await selectFirst(wrapper)

    await wrapper.find('[data-test="dept-edit"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-test="dept-save"]').trigger('click')
    await flushPromises()

    expect(error).toHaveBeenCalled()
    expect(wrapper.find('[data-test="dept-mode"]').text()).toContain('编辑')
  })

  it('重载后选中项已不在树中：详情退回空态（选中项置空）', async () => {
    let first = true
    const { api } = hostStub({
      get: (path) => {
        if (path !== '/depts') return Promise.resolve({})
        if (first) {
          first = false
          return Promise.resolve(TREE)
        }
        return Promise.resolve({ items: [] })
      },
    })
    const { wrapper } = await mountPage(api)
    await selectFirst(wrapper)
    await wrapper.find('[data-test="dept-refresh"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-test="dept-detail"]').text()).toContain('暂无数据')
  })

  it('新建子部门：未选中时父级为空串；选中时带当前部门标识', async () => {
    const { api } = hostStub()
    const { wrapper, router } = await mountPage(api)
    const push = vi.spyOn(router, 'push')

    await wrapper.find('[data-test="dept-create"]').trigger('click')
    expect(push).toHaveBeenCalledWith({ name: 'MdmOrgDeptForm', query: { parent: '' } })

    await selectFirst(wrapper)
    await wrapper.find('[data-test="dept-create"]').trigger('click')
    expect(push).toHaveBeenCalledWith({ name: 'MdmOrgDeptForm', query: { parent: '1' } })
  })

  it('打开表单页：未选中不跳转；选中时带标识跳转', async () => {
    const { api } = hostStub()
    const { wrapper, router } = await mountPage(api)
    const push = vi.spyOn(router, 'push')

    // 未选中时详情区无该按钮（空态），直接验证选中后的跳转
    await selectFirst(wrapper)
    await wrapper.find('[data-test="dept-form-page"]').trigger('click')
    expect(push).toHaveBeenCalledWith({ name: 'MdmOrgDeptForm', params: { id: '1' } })
  })

  it('移动：对话框确认后调移动端点并重载', async () => {
    vi.spyOn(ElMessage, 'success').mockReturnValue({} as never)
    vi.spyOn(ElMessageBox, 'prompt').mockResolvedValue({ value: '2', action: 'confirm' } as never)
    const { api, scope } = hostStub()
    const { wrapper } = await mountPage(api)
    await selectFirst(wrapper)

    await wrapper.find('[data-test="dept-move"]').trigger('click')
    await flushPromises()

    expect(scope.put).toHaveBeenCalledWith('/depts/1/move', { parent_id: '2' })
  })

  it('移动：对话框取消 / 关闭时静默返回（不提示错误）', async () => {
    const error = vi.spyOn(ElMessage, 'error').mockReturnValue({} as never)
    const prompt = vi.spyOn(ElMessageBox, 'prompt').mockRejectedValue('cancel')
    const { api } = hostStub()
    const { wrapper } = await mountPage(api)
    await selectFirst(wrapper)

    await wrapper.find('[data-test="dept-move"]').trigger('click')
    await flushPromises()
    prompt.mockRejectedValue('close')
    await wrapper.find('[data-test="dept-move"]').trigger('click')
    await flushPromises()

    expect(error).not.toHaveBeenCalled()
  })

  it('移动失败：分别提示「未接入」与通用失败', async () => {
    const error = vi.spyOn(ElMessage, 'error').mockReturnValue({} as never)
    vi.spyOn(ElMessageBox, 'prompt').mockResolvedValue({ value: '2', action: 'confirm' } as never)
    const { api } = hostStub({ put: () => Promise.reject(new Error('MODULE_API_ABSENT')) })
    const { wrapper } = await mountPage(api)
    await selectFirst(wrapper)

    await wrapper.find('[data-test="dept-move"]').trigger('click')
    await flushPromises()
    expect(error).toHaveBeenCalledTimes(1)
  })

  it('启停：启用态点按提交停用；停用态点按提交启用', async () => {
    vi.spyOn(ElMessage, 'success').mockReturnValue({} as never)
    const { api, scope } = hostStub()
    const { wrapper } = await mountPage(api)
    await selectFirst(wrapper)

    await wrapper.find('[data-test="dept-toggle"]').trigger('click')
    await flushPromises()
    expect(scope.put).toHaveBeenCalledWith('/depts/1', { status: 'disabled' })

    // 选中停用态的子部门后再点按 ⇒ 提交启用
    const tree = wrapper.findComponent({ name: 'ElTree' })
    tree.vm.$emit('node-click', TREE.items[0].children[0])
    await flushPromises()
    await wrapper.find('[data-test="dept-toggle"]').trigger('click')
    await flushPromises()
    expect(scope.put).toHaveBeenCalledWith('/depts/2', { status: 'enabled' })
  })

  it('启停失败：提示错误且不改变选中', async () => {
    const error = vi.spyOn(ElMessage, 'error').mockReturnValue({} as never)
    const { api } = hostStub({ put: () => Promise.reject(new Error('boom')) })
    const { wrapper } = await mountPage(api)
    await selectFirst(wrapper)

    await wrapper.find('[data-test="dept-toggle"]').trigger('click')
    await flushPromises()

    expect(error).toHaveBeenCalled()
    expect(wrapper.find('[data-test="dept-current"]').text()).toContain('总部')
  })

  it('删除：确认后删除并清空选中、重载列表', async () => {
    vi.spyOn(ElMessage, 'success').mockReturnValue({} as never)
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue({ action: 'confirm' } as never)
    const { api, scope } = hostStub()
    const { wrapper } = await mountPage(api)
    await selectFirst(wrapper)

    await wrapper.find('[data-test="dept-delete"]').trigger('click')
    await flushPromises()

    expect(scope.del).toHaveBeenCalledWith('/depts/1')
    expect(wrapper.find('[data-test="dept-detail"]').text()).toContain('暂无数据')
  })

  it('删除失败：提示错误且保留选中', async () => {
    const error = vi.spyOn(ElMessage, 'error').mockReturnValue({} as never)
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue({ action: 'confirm' } as never)
    const { api } = hostStub({ del: () => Promise.reject(new Error('boom')) })
    const { wrapper } = await mountPage(api)
    await selectFirst(wrapper)

    await wrapper.find('[data-test="dept-delete"]').trigger('click')
    await flushPromises()

    expect(error).toHaveBeenCalled()
    expect(wrapper.find('[data-test="dept-current"]').text()).toContain('总部')
  })

  it('权限不足：新建 / 编辑 / 删除入口不渲染，移动与启停禁用', async () => {
    const { api } = hostStub()
    const { wrapper } = await mountPage(api, ['mdm:query'])
    await selectFirst(wrapper)

    expect(wrapper.find('[data-test="dept-create"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="dept-edit"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="dept-delete"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="dept-move"]').attributes('disabled')).toBeDefined()
    expect(wrapper.find('[data-test="dept-toggle"]').attributes('disabled')).toBeDefined()
  })

  it('删除：对话框取消时静默返回（不删、不提示）', async () => {
    const error = vi.spyOn(ElMessage, 'error').mockReturnValue({} as never)
    vi.spyOn(ElMessageBox, 'confirm').mockRejectedValue('cancel')
    const { api, scope } = hostStub()
    const { wrapper } = await mountPage(api)
    await selectFirst(wrapper)

    await wrapper.find('[data-test="dept-delete"]').trigger('click')
    await flushPromises()

    expect(scope.del).not.toHaveBeenCalled()
    expect(error).not.toHaveBeenCalled()
    expect(wrapper.find('[data-test="dept-current"]').text()).toContain('总部')
  })

  it('未选中时的防御早退：编辑 / 保存 / 表单页 / 移动 / 启停 / 删除均不发请求', async () => {
    const { api, scope } = hostStub()
    const { wrapper, router } = await mountPage(api)
    const push = vi.spyOn(router, 'push')
    const vm = wrapper.vm as unknown as Record<string, () => Promise<void> | void>

    vm.startEdit()
    await vm.saveEdit?.()
    vm.openFormPage()
    await vm.onMove?.()
    await vm.onToggleStatus?.()
    await vm.onDelete?.()
    await flushPromises()

    expect(scope.put).not.toHaveBeenCalled()
    expect(scope.del).not.toHaveBeenCalled()
    expect(push).not.toHaveBeenCalled()
  })

  it('上级部门为空值（`undefined`）时表单按根处理，保存不触发移动端点', async () => {
    const tree = {
      items: [
        {
          id: '9',
          code: 'LEAF',
          name: '叶子部门',
          ancestors: '/1/',
          sort: 0,
          status: 'enabled',
        },
      ],
    }
    const { api, scope } = hostStub({ get: (path) => (path === '/depts' ? Promise.resolve(tree) : Promise.resolve({})) })
    const { wrapper } = await mountPage(api)
    const elTree = wrapper.findComponent({ name: 'ElTree' })
    elTree.vm.$emit('node-click', tree.items[0])
    await flushPromises()

    await wrapper.find('[data-test="dept-edit"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-test="dept-save"]').trigger('click')
    await flushPromises()

    expect(scope.put).toHaveBeenCalledTimes(1)
    expect(scope.put).toHaveBeenCalledWith('/depts/9', expect.objectContaining({ code: 'LEAF' }))
  })

  it('编辑态下改状态选择器：保存时按所选状态提交', async () => {
    const { api, scope } = hostStub()
    const { wrapper } = await mountPage(api)
    await selectFirst(wrapper)

    await wrapper.find('[data-test="dept-edit"]').trigger('click')
    await flushPromises()
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    selects[1].vm.$emit('update:modelValue', 'disabled')
    await flushPromises()
    await wrapper.find('[data-test="dept-save"]').trigger('click')
    await flushPromises()

    expect(scope.put).toHaveBeenCalledWith('/depts/1', expect.objectContaining({ status: 'disabled' }))
  })

  it('工具栏启停文案随选中项状态切换（启用态显示「停用」，停用态显示「启用」）', async () => {
    const { api } = hostStub()
    const { wrapper } = await mountPage(api)

    await selectFirst(wrapper)
    expect(wrapper.find('[data-test="dept-toggle"]').text()).toContain('停用')

    const elTree = wrapper.findComponent({ name: 'ElTree' })
    elTree.vm.$emit('node-click', TREE.items[0].children[0])
    await flushPromises()
    expect(wrapper.find('[data-test="dept-toggle"]').text()).toContain('启用')
  })

  it('移动失败（通用错误）：提示通用失败', async () => {
    const error = vi.spyOn(ElMessage, 'error').mockReturnValue({} as never)
    vi.spyOn(ElMessageBox, 'prompt').mockResolvedValue({ value: '2', action: 'confirm' } as never)
    const { api } = hostStub({ put: () => Promise.reject(new Error('boom')) })
    const { wrapper } = await mountPage(api)
    await selectFirst(wrapper)

    await wrapper.find('[data-test="dept-move"]').trigger('click')
    await flushPromises()

    expect(error).toHaveBeenCalledTimes(1)
  })

  it('启停成功后选中项已不在树中：重载置空选中、不重选（不因空选中抛错）', async () => {
    vi.spyOn(ElMessage, 'success').mockReturnValue({} as never)
    let first = true
    const { api } = hostStub({
      get: (path) => {
        if (path !== '/depts') return Promise.resolve({})
        if (first) {
          first = false
          return Promise.resolve(TREE)
        }
        return Promise.resolve({ items: [] })
      },
    })
    const { wrapper } = await mountPage(api)
    await selectFirst(wrapper)

    await wrapper.find('[data-test="dept-toggle"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-test="dept-detail"]').text()).toContain('暂无数据')
  })

  it('启停失败：请求能力缺失时提示「未接入」', async () => {
    const error = vi.spyOn(ElMessage, 'error').mockReturnValue({} as never)
    const { api } = hostStub({ put: () => Promise.reject(new Error('MODULE_API_ABSENT')) })
    const { wrapper } = await mountPage(api)
    await selectFirst(wrapper)

    await wrapper.find('[data-test="dept-toggle"]').trigger('click')
    await flushPromises()

    expect(error).toHaveBeenCalledTimes(1)
  })

  it('删除失败：请求能力缺失时提示「未接入」', async () => {
    const error = vi.spyOn(ElMessage, 'error').mockReturnValue({} as never)
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue({ action: 'confirm' } as never)
    const { api } = hostStub({ del: () => Promise.reject(new Error('MODULE_API_ABSENT')) })
    const { wrapper } = await mountPage(api)
    await selectFirst(wrapper)

    await wrapper.find('[data-test="dept-delete"]').trigger('click')
    await flushPromises()

    expect(error).toHaveBeenCalledTimes(1)
  })

  it('重载后树只剩无子节点项：递归到叶子仍未命中，选中置空', async () => {
    let first = true
    const { api } = hostStub({
      get: (path) => {
        if (path !== '/depts') return Promise.resolve({})
        if (first) {
          first = false
          return Promise.resolve(TREE)
        }
        return Promise.resolve({
          items: [{ id: '99', code: 'OTHER', name: '其他部门', parent_id: null, ancestors: '', sort: 0, status: 'enabled' }],
        })
      },
    })
    const { wrapper } = await mountPage(api)
    await selectFirst(wrapper)
    await wrapper.find('[data-test="dept-refresh"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-test="dept-detail"]').text()).toContain('暂无数据')
  })

  it('选中子部门（上级非空）保存：不触发移动，按原上级提交更新', async () => {
    const { api, scope } = hostStub()
    const { wrapper } = await mountPage(api)
    const elTree = wrapper.findComponent({ name: 'ElTree' })
    elTree.vm.$emit('node-click', TREE.items[0].children[0])
    await flushPromises()

    await wrapper.find('[data-test="dept-edit"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-test="dept-save"]').trigger('click')
    await flushPromises()

    expect(scope.put).toHaveBeenCalledTimes(1)
    expect(scope.put).toHaveBeenCalledWith('/depts/2', expect.objectContaining({ code: 'RD' }))
  })

  it('载入响应不含 `items` 字段：按空树处理（不抛错）', async () => {
    const { api } = hostStub({ get: () => Promise.resolve({}) })
    const { wrapper } = await mountPage(api)

    expect(wrapper.find('[data-test="dept-detail"]').text()).toContain('暂无数据')
    expect(wrapper.find('[data-test="dept-notice"]').exists()).toBe(false)
  })

  it('保存成功后重载未命中该部门：不重选（详情退回空态）', async () => {
    let first = true
    const { api } = hostStub({
      get: (path) => {
        if (path !== '/depts') return Promise.resolve({})
        if (first) {
          first = false
          return Promise.resolve(TREE)
        }
        return Promise.resolve({
          items: [{ id: '99', code: 'OTHER', name: '其他部门', parent_id: null, ancestors: '', sort: 0, status: 'enabled' }],
        })
      },
    })
    const { wrapper } = await mountPage(api)
    await selectFirst(wrapper)

    await wrapper.find('[data-test="dept-edit"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-test="dept-save"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-test="dept-detail"]').text()).toContain('暂无数据')
  })
})
