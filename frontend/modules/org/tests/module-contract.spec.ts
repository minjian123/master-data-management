// kiwi_id: 2261
/**
 * 模块契约用例：经平台 `@bms/core/testing` 契约工厂跑**同一套断言**（注入上下文 / 注册声明 /
 * 样式约束）；隔离事实由平台护栏纯函数（跨仓复用）产出。
 */

import { readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'

import { describeModuleContract } from '@bms/core/testing'

import { scanExternalModuleSources } from '@bms-scripts/check-module-isolation.mjs'

import orgModule from '../src/index'

/** 模块工程目录（`modules/org`）。 */
const MODULE_DIR = resolve(import.meta.dirname, '..')

const pkg = JSON.parse(readFileSync(join(MODULE_DIR, 'package.json'), 'utf8')) as { version: string }

describeModuleContract('mdm 组织域模块契约（Kiwi 2261）', {
  definition: orgModule,
  facts: {
    packageVersion: pkg.version,
    // 样式与运行时约束关：跨仓模块走平台护栏的**外部工程**源码面扫描（与仓内模块同判据）
    isolationViolations: scanExternalModuleSources(MODULE_DIR),
  },
})
