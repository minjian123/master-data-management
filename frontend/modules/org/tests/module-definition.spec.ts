// kiwi_id: 2261
/**
 * 模块专属断言（mdm 01_04）：清单身份与版本注入 / 路由与菜单 meta / 区域项（四个具名插槽插件）/
 * 文案包键位 / 契约版本与平台同源。
 */

import { MODULE_CONTRACT_VERSION } from '@bms/core'
import { describe, expect, it } from 'vitest'

import orgModule from '../src/index'

/** 模块注册声明（`setup` 在空上下文下也应可用——缺失项自行降级）。 */
const registration = await orgModule.setup({})

describe('mdm 组织域模块定义（01_04 · Kiwi 2261）', () => {
  it('清单身份：名称 / 版本 / 契约版本', () => {
    expect(orgModule.manifest.name).toBe('mdm-org')
    expect(orgModule.manifest.version).toBe(__BMS_MODULE_VERSION__)
    expect(orgModule.manifest.contractVersion).toBe(MODULE_CONTRACT_VERSION)
  })

  it('路由：部门 / 岗位管理页进菜单（分组「组织主数据」），表单页不进菜单', () => {
    const routes = registration.routes ?? []
    expect(routes.map((route) => route.path)).toEqual([
      '/org/depts',
      '/org/depts/form/:id?',
      '/org/posts',
      '/org/posts/form/:id?',
    ])

    const deptList = routes.find((route) => route.path === '/org/depts')
    expect(deptList?.meta?.title).toBe('部门管理')
    expect(deptList?.meta?.group).toBe('组织主数据')

    const postList = routes.find((route) => route.path === '/org/posts')
    expect(postList?.meta?.title).toBe('岗位管理')

    for (const route of routes.filter((item) => item.path.includes('form'))) {
      expect(route.meta?.menu).toBe(false)
    }
  })

  it('区域项：四个具名插槽插件（用户分配岗位 / 用户分配部门 / 岗位分配 / 部门分配）键位与挂接位正确', () => {
    const regions = registration.regions ?? []
    expect(regions.map((region) => region.key)).toEqual([
      'mdm-org:user-posts',
      'mdm-org:user-depts',
      'mdm-org:role-posts',
      'mdm-org:role-depts',
    ])
    expect(regions.map((region) => region.area)).toEqual([
      'sys.user.detail.tabs',
      'sys.user.detail.tabs',
      'sys.role.detail.assign',
      'sys.role.detail.assign',
    ])
    // 次序：用户详情页签下岗位 20 / 部门 30；角色分配页签下岗位 20 / 部门 30；权限码同源 `org:update`
    expect(regions[0]?.order).toBe(20)
    expect(regions[1]?.order).toBe(30)
    expect(regions[2]?.order).toBe(20)
    expect(regions[3]?.order).toBe(30)
    for (const region of regions) {
      expect(region.perm).toBe('org:update')
      expect(region.component).toBeDefined()
    }
  })

  it('文案包：中文与英文各一份（键位 `<模块名>:<语言标识>`）', () => {
    const packs = registration.i18nPacks ?? []
    expect(packs.map((pack) => pack.key)).toEqual(['mdm-org:zh-cn', 'mdm-org:en'])
    expect(Object.keys(packs[0]?.messages ?? {}).length).toBeGreaterThan(20)
  })

  it('只声明三类注册通道（无组件 / 字段渲染器 / 图标 / 卡片 / 令牌）', () => {
    expect(registration.components ?? {}).toEqual({})
    expect(registration.fieldRenderers ?? []).toEqual([])
    expect(registration.icons ?? {}).toEqual({})
    expect(registration.cards ?? []).toEqual([])
    expect(registration.themeTokens ?? []).toEqual([])
  })
})
