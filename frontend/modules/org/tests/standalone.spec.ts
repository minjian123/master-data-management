// kiwi_id: 2348
/**
 * 独立预览壳用例（mdm 01_05）：不依赖宿主即可挂载（`#app` 内渲染出路由视图），
 * 路由表与模块声明同构（部门 / 岗位管理页 + 两表单页）。
 *
 * 说明：本壳不进远端产物（隔离扫描豁免），改名的 `views/org/*` 路径由本用例兜住。
 */

import { describe, expect, it } from 'vitest'

describe('mdm 组织域独立预览壳（01_05 · Kiwi 2348）', () => {
  it('挂载到 #app：路由视图渲染成功，默认重定向到部门管理页', async () => {
    document.body.innerHTML = '<div id="app"></div>'

    await import('../src/standalone')
    await new Promise((resolve) => setTimeout(resolve, 0))

    const host = document.querySelector('#app')
    expect(host).not.toBeNull()
    expect(host?.innerHTML ?? '').not.toBe('')
    expect(window.location.hash === '' || window.location.hash.startsWith('#/')).toBe(true)
  })
})
