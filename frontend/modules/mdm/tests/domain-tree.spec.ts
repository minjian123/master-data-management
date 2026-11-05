// kiwi_id: 2348
/**
 * 组织域领域工具用例（mdm 01_05）：部门树展平（含递归缩进）/ 树数据转换（含子节点与叶子两侧）/
 * 标识参数归一（空值返回 `null`、字符串原样透传）。
 *
 * 说明：本文件补齐 `src/domain.ts` 两条未覆盖分支（`flattenDeptTree` 子节点递归、
 * `toDeptTreeData` 是否带 `children` 的三元两侧），服务标识归并后（`mdm` 域段）不得回退。
 */

import { describe, expect, it } from 'vitest'

import { flattenDeptTree, toDeptTreeData, toIdParam, toIdParamList, type DeptTreeNode } from '../src/domain'

/** 两层部门树（根 + 子 + 孙，含叶子）。 */
const TREE: DeptTreeNode[] = [
  {
    id: '1',
    code: 'HQ',
    name: '总部',
    parent_id: null,
    ancestors: '/',
    sort: 0,
    status: 'enabled',
    children: [
      {
        id: '2',
        code: 'RD',
        name: '研发部',
        parent_id: '1',
        ancestors: '/1/',
        sort: 0,
        status: 'enabled',
        children: [
          { id: '3', code: 'RD-A', name: '前端组', parent_id: '2', ancestors: '/1/2/', sort: 0, status: 'enabled' },
        ],
      },
      { id: '4', code: 'MK', name: '市场部', parent_id: '1', ancestors: '/1/', sort: 1, status: 'disabled' },
    ],
  } as DeptTreeNode,
]

describe('mdm 组织域领域工具（01_05 · Kiwi 2348）', () => {
  it('部门树展平：按深度缩进，子节点递归展开（含叶子）', () => {
    const options = flattenDeptTree(TREE)

    expect(options.map((item) => item.value)).toEqual(['1', '2', '3', '4'])
    expect(options[0].label).toBe('总部')
    expect(options[1].label).toBe('　研发部')
    expect(options[2].label).toBe('　　前端组')
    expect(options[3].label).toBe('　市场部')
  })

  it('部门树展平：空树返回空清单（递归终止分支）', () => {
    expect(flattenDeptTree([])).toEqual([])
  })

  it('树数据转换：有子节点的节点带 `children`，叶子不带该键', () => {
    const data = toDeptTreeData(TREE)

    expect(data).toHaveLength(1)
    expect(data[0].id).toBe('1')
    expect(data[0].label).toBe('总部')
    expect(data[0].children).toHaveLength(2)
    expect(data[0].children?.[0].children?.[0]).toEqual({ id: '3', label: '前端组' })
    expect(Object.hasOwn(data[0].children?.[1] ?? {}, 'children')).toBe(false)
  })

  it('标识参数归一：空值返回 `null`，非空原样转数值口径', () => {
    expect(toIdParam('')).toBeNull()
    expect(toIdParam(undefined)).toBeNull()
    expect(toIdParam(null)).toBeNull()
    // 契约声明为数值，但实现按字符串原样透传（雪花 id 超出安全整数范围）
    expect(toIdParam('9007199254740993') as unknown as string).toBe('9007199254740993')
  })

  it('标识集合归一：字符串原样透传（雪花 id 不做数值转换）', () => {
    const ids = ['9007199254740993', '42']
    const passed = toIdParamList(ids)

    expect(passed).toHaveLength(2)
    expect(passed[0]).toBe(ids[0] as unknown as number)
  })
})
