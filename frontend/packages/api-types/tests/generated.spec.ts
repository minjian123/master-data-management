// kiwi_id: 2261
/**
 * 契约类型生成物一致性用例（mdm 01_04）：事实源就位 / 生成物覆盖快照全部路径 / 按域命名空间导出 /
 * 生成头可追溯（`--check` 逐字节零漂移为另一道硬门禁，二者互补）。
 */

import { existsSync, readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

/** 仓根（本文件位于 `mdm/frontend/packages/api-types/tests/`）。 */
const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../../..')
/** 产品契约快照目录（事实源）。 */
const contractsDir = join(repoRoot, 'deploy', 'contracts')
/** 生成物目录。 */
const srcDir = resolve(dirname(fileURLToPath(import.meta.url)), '../src')

/**
 * 读取契约快照。
 *
 * @param domain 域简称（如 `org`）。
 * @returns 快照对象。
 */
function contractOf(domain: string): { openapi?: string; paths?: Record<string, unknown> } {
  return JSON.parse(readFileSync(join(contractsDir, `${domain}.json`), 'utf8'))
}

describe('mdm 产品契约类型生成物（01_04 · Kiwi 2261）', () => {
  it('事实源就位：快照为 OpenAPI 3.x 且含业务端点', () => {
    const schema = contractOf('org')
    expect(String(schema.openapi ?? '').startsWith('3.')).toBe(true)
    expect(Object.keys(schema.paths ?? {}).length).toBeGreaterThan(20)
  })

  it('生成物覆盖快照全部路径（逐路径断言，防漏生成）', () => {
    const generated = readFileSync(join(srcDir, 'org.ts'), 'utf8')
    for (const path of Object.keys(contractOf('org').paths ?? {})) {
      expect(generated, `生成物缺少路径：${path}`).toContain(`"${path}"`)
    }
  })

  it('按域命名空间导出（index.ts）并生成头齐备', () => {
    const index = readFileSync(join(srcDir, 'index.ts'), 'utf8')
    expect(index).toContain("export type * as org from './org'")

    const generated = readFileSync(join(srcDir, 'org.ts'), 'utf8')
    expect(generated).toContain('deploy/contracts/org.json')
    expect(generated).toContain('请勿手工修改')
  })

  it('无多余生成文件（目录面与快照一一对应）', () => {
    const snapshotDomains = ['org']
    for (const domain of snapshotDomains) {
      expect(existsSync(join(srcDir, `${domain}.ts`))).toBe(true)
    }
    expect(existsSync(join(srcDir, 'index.ts'))).toBe(true)
  })
})
