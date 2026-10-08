import { join } from 'node:path'
import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

import { loadModulePackage, moduleVersionDefine } from '../../../../bms/frontend/scripts/module-meta.mjs'

/** 模块工程目录（版本单一来源：`package.json`）。 */
const MODULE_DIR = fileURLToPath(new URL('.', import.meta.url))

// 版本注入与构建配置同源（缺一即测试与构建版本口径不一致）
const MODULE_VERSION = loadModulePackage(MODULE_DIR).version

/** 平台前端目录（工作区 bms 克隆；跨仓脚本与单一来源所在）。 */
const BMS_FRONTEND_DIR = fileURLToPath(new URL('../../../../bms/frontend/', import.meta.url))

export default defineConfig({
  define: moduleVersionDefine(MODULE_VERSION),
  plugins: [vue()],
  resolve: {
    // 跨仓平台脚本经别名引入（相对路径出工作区根时 Vite 解析不稳）
    alias: { '@bms-scripts': join(BMS_FRONTEND_DIR, 'scripts') },
  },
  test: {
    environment: 'jsdom',
    include: ['tests/**/*.spec.ts'],
    server: {
      deps: {
        // element-plus 组件在 jsdom 下需内联转译（同平台 ui-ep 测试口径），否则组件解析失败
        inline: ['element-plus'],
      },
    },
  },
  // 跨仓平台脚本读取（护栏纯函数）以别名引入，允许访问工作区外的 bms 目录
  server: {
    fs: { allow: [fileURLToPath(new URL('.', import.meta.url)), BMS_FRONTEND_DIR] },
  },
})
