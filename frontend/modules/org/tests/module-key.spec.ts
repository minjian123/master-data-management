// kiwi_id: 2358
/**
 * 模块键 snake 化（mdm 01_06）：模块名 / 插件与区域项键 / i18n 包键统一取 `mdm_org` 前缀，
 * 与 bms 宿主 `MODULE_NAME_PATTERN`（登记型标识一律 snake_case）同口径，不保留旧键形态。
 *
 * 说明：模块清单身份与挂接位断言见 `module-definition.spec.ts`；本文件只锁「键位派生面」，
 * 变更时须同步模块定义、宿主清单与发布条目（详见任务 01_06 详细设计 §3.1）。
 */

import { MODULE_NAME_PATTERN } from '@bms/core'
import { describe, expect, it } from 'vitest'

import orgModule from '../src/index'

/** 模块名（= 清单 `name` = MF 容器名）。 */
const MODULE_NAME = 'mdm_org'

const registration = await orgModule.setup({})

describe('mdm 组织域模块键 snake 化（01_06 · Kiwi 2358）', () => {
  it('模块名取 `mdm_org`，且可被宿主按 `MODULE_NAME_PATTERN` 接受', () => {
    expect(orgModule.manifest.name).toBe(MODULE_NAME)
    expect(MODULE_NAME_PATTERN.test(MODULE_NAME)).toBe(true)
  })

  it('四个插件 / 区域项键均以模块名为前缀', () => {
    expect((registration.regions ?? []).map((region) => region.key)).toEqual([
      `${MODULE_NAME}:user-posts`,
      `${MODULE_NAME}:user-depts`,
      `${MODULE_NAME}:role-posts`,
      `${MODULE_NAME}:role-depts`,
    ])
  })

  it('两个 i18n 文案包键均以模块名为前缀', () => {
    expect((registration.i18nPacks ?? []).map((pack) => pack.key)).toEqual([
      `${MODULE_NAME}:zh-cn`,
      `${MODULE_NAME}:en`,
    ])
  })

  it('注册面所有派生键同源（无第二种前缀形态）', () => {
    const keys = [
      ...(registration.regions ?? []).map((region) => region.key),
      ...(registration.i18nPacks ?? []).map((pack) => pack.key),
    ]
    expect(keys).toHaveLength(6)
    for (const key of keys) {
      expect(key.split(':', 1)[0]).toBe(MODULE_NAME)
    }
  })
})
