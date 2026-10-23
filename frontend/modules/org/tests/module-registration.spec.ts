// kiwi_id: 2348
/**
 * 模块注册面补充用例（mdm 01_05）：动态导入解析（路由页 / 具名插槽插件逐个可达）/
 * 默认导出与命名导出一致 / 文案包键位齐备。
 *
 * 说明：模块清单身份与 meta 断言见 `module-definition.spec.ts`；本文件只补「注册面可达性」——
 * 每个 `component: () => import(...)` 都真实调用一次，保证改名（`views/org/*`、`components/slots/*`）
 * 后路径仍然有效。
 */

import { describe, expect, it } from 'vitest'

import orgModule, { orgModule as namedModule } from '../src/index'
import { ORG_MESSAGES_EN, ORG_MESSAGES_ZH_CN } from '../src/i18n/messages'
import { applyHostContext } from '../src/runtime'

const registration = await orgModule.setup({})

describe('mdm 组织域模块注册面（01_05 · Kiwi 2348）', () => {
  it('默认导出与命名导出为同一模块定义', () => {
    expect(namedModule).toBe(orgModule)
    expect(orgModule.manifest.name).toBe('mdm-org')
  })

  it('路由页动态导入全部可达（部门 / 岗位管理页与两表单页）', async () => {
    for (const route of registration.routes ?? []) {
      const loader = route.component as unknown as () => Promise<{ default: unknown }>
      const loaded = await loader()
      expect(loaded.default, `路由 ${route.path} 未能加载组件`).toBeTruthy()
    }
  })

  it('具名插槽插件动态导入全部可达（四个区域项）', async () => {
    for (const region of registration.regions ?? []) {
      const loader = region.component as unknown as () => Promise<{ default: unknown }>
      const loaded = await loader()
      expect(loaded.default, `区域项 ${region.key} 未能加载组件`).toBeTruthy()
    }
  })

  it('文案包：中英两套，键位跟随模块名（`mdm-org:*`）', () => {
    const packs = registration.i18nPacks ?? []
    expect(packs.map((pack) => pack.key)).toEqual(['mdm-org:zh-cn', 'mdm-org:en'])
    expect(packs[0].messages).toBe(ORG_MESSAGES_ZH_CN)
    expect(packs[1].messages).toBe(ORG_MESSAGES_EN)
  })

  it('setup 可重复调用（幂等注册面）且无权限信息时按「有权限」处理', () => {
    const second = orgModule.setup({ user: ['mdm:query'] })
    expect(second.routes).toHaveLength(4)
    expect(second.regions).toHaveLength(4)
    expect(applyHostContext({}).canUpdate).toBe(true)
  })
})
