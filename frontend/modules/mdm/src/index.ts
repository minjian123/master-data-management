/* eslint-disable @typescript-eslint/triple-slash-reference -- Module Federation 类型声明生成以 plain tsc 编译，需引用 env.d.ts 载入环境声明（版本常量与 .vue shim） */
/// <reference path="./env.d.ts" />
/**
 * mdm 组织域运行时模块定义（Module Federation remote 入口：**默认导出**模块定义）。
 *
 * 独立工程、独立构建、独立产物（`dist/remoteEntry.js` + 页面异步分包 + `module.meta.json`）；
 * 平台宿主按模块清单运行期加载本容器暴露的 `./module`（模块定义），经统一装配器倒入扩展点注册表。
 *
 * 八类注册声明**只用三类**：`routes`（部门 / 岗位管理页，菜单经路由 `meta` 由宿主自动装配）、
 * `regions`（三个具名插槽插件）、`i18nPacks`（模块文案包）——无 `components` / `fieldRenderers` /
 * `icons` / `cards` / `themeTokens`。
 */

import { MODULE_CONTRACT_VERSION, defineModule } from '@bms/core'

import { MDM_MESSAGES_EN, MDM_MESSAGES_ZH_CN } from './i18n/messages'
import { applyHostContext } from './runtime'

/** mdm 组织域模块（清单 `name` / `version` 须与平台清单条目严格一致；版本构建期注入）。 */
export const mdmModule = defineModule({
  manifest: { name: 'mdm', version: __BMS_MODULE_VERSION__, contractVersion: MODULE_CONTRACT_VERSION },
  setup: (context) => {
    // 只经注入上下文访问宿主能力（只读快照）：记录请求能力与只读路由、据权限码派生可写态；缺失项自行降级。
    applyHostContext(context)
    return {
      routes: [
        {
          path: '/mdm/depts',
          name: 'MdmMdmDeptList',
          component: () => import('./views/mdm/DeptListView.vue'),
          meta: {
            title: '部门管理',
            icon: 'mdmanization',
            group: '组织主数据',
            groupIcon: 'mdmanization',
            keepAlive: true,
          },
        },
        {
          path: '/mdm/depts/form/:id?',
          name: 'MdmMdmDeptForm',
          component: () => import('./views/mdm/DeptFormView.vue'),
          meta: { title: '部门表单', menu: false },
        },
        {
          path: '/mdm/posts',
          name: 'MdmMdmPostList',
          component: () => import('./views/mdm/PostListView.vue'),
          meta: { title: '岗位管理', icon: 'briefcase', group: '组织主数据', keepAlive: true },
        },
        {
          path: '/mdm/posts/form/:id?',
          name: 'MdmMdmPostForm',
          component: () => import('./views/mdm/PostFormView.vue'),
          meta: { title: '岗位表单', menu: false },
        },
      ],
      regions: [
        {
          key: 'mdm:user-posts',
          area: 'sys.user.detail.tabs',
          component: () => import('./components/slots/UserPostsPanel.vue'),
          order: 20,
          title: '岗位分配',
          perm: 'mdm:update',
        },
        {
          key: 'mdm:user-depts',
          area: 'sys.user.detail.tabs',
          component: () => import('./components/slots/UserDeptsPanel.vue'),
          order: 30,
          title: '部门分配',
          perm: 'mdm:update',
        },
        {
          key: 'mdm:role-posts',
          area: 'sys.role.detail.assign',
          component: () => import('./components/slots/RolePostsPanel.vue'),
          order: 20,
          title: '岗位分配',
          perm: 'mdm:update',
        },
        {
          key: 'mdm:role-depts',
          area: 'sys.role.detail.assign',
          component: () => import('./components/slots/RoleDeptsPanel.vue'),
          order: 30,
          title: '部门分配',
          perm: 'mdm:update',
        },
      ],
      i18nPacks: [
        { key: 'mdm:zh-cn', messages: MDM_MESSAGES_ZH_CN },
        { key: 'mdm:en', messages: MDM_MESSAGES_EN },
      ],
    }
  },
})

export default mdmModule
