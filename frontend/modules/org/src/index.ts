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

import { ORG_MESSAGES_EN, ORG_MESSAGES_ZH_CN } from './i18n/messages'
import { applyHostContext } from './runtime'

/** mdm 组织域模块（清单 `name` / `version` 须与平台清单条目严格一致；版本构建期注入）。 */
export const orgModule = defineModule({
  manifest: { name: 'mdm-org', version: __BMS_MODULE_VERSION__, contractVersion: MODULE_CONTRACT_VERSION },
  setup: (context) => {
    // 只经注入上下文访问宿主能力（只读快照）：记录请求能力与只读路由、据权限码派生可写态；缺失项自行降级。
    applyHostContext(context)
    return {
      routes: [
        {
          path: '/org/depts',
          name: 'MdmOrgDeptList',
          component: () => import('./views/org/DeptListView.vue'),
          meta: {
            title: '部门管理',
            icon: 'organization',
            group: '组织主数据',
            groupIcon: 'organization',
            keepAlive: true,
          },
        },
        {
          path: '/org/depts/form/:id?',
          name: 'MdmOrgDeptForm',
          component: () => import('./views/org/DeptFormView.vue'),
          meta: { title: '部门表单', menu: false },
        },
        {
          path: '/org/posts',
          name: 'MdmOrgPostList',
          component: () => import('./views/org/PostListView.vue'),
          meta: { title: '岗位管理', icon: 'briefcase', group: '组织主数据', keepAlive: true },
        },
        {
          path: '/org/posts/form/:id?',
          name: 'MdmOrgPostForm',
          component: () => import('./views/org/PostFormView.vue'),
          meta: { title: '岗位表单', menu: false },
        },
      ],
      regions: [
        {
          key: 'mdm-org:user-posts',
          area: 'sys.user.detail.tabs',
          component: () => import('./components/slots/UserPostsPanel.vue'),
          order: 20,
          title: '用户分配岗位',
          perm: 'org:update',
        },
        {
          key: 'mdm-org:role-posts',
          area: 'sys.role.detail.assign',
          component: () => import('./components/slots/RolePostsPanel.vue'),
          order: 20,
          title: '岗位分配',
          perm: 'org:update',
        },
        {
          key: 'mdm-org:role-depts',
          area: 'sys.role.detail.assign',
          component: () => import('./components/slots/RoleDeptsPanel.vue'),
          order: 30,
          title: '部门分配',
          perm: 'org:update',
        },
      ],
      i18nPacks: [
        { key: 'mdm-org:zh-cn', messages: ORG_MESSAGES_ZH_CN },
        { key: 'mdm-org:en', messages: ORG_MESSAGES_EN },
      ],
    }
  },
})

export default orgModule
