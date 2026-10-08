/**
 * 模块独立预览壳：不依赖宿主，供模块工程自身 `dev` / `preview` 验证页面与样式
 * （`index.html` 内联了最小 `--bms-*` 令牌兜底）。
 *
 * 注意：本文件为**独立预览壳**，非模块契约部分、不进远端产物（隔离扫描豁免）。
 * 独立预览下宿主请求能力未注入 → 页面按降级提示（不发起请求）。
 */

import 'element-plus/dist/index.css'

import { createApp, h } from 'vue'
import { createRouter, createWebHashHistory, RouterView, type RouteRecordRaw } from 'vue-router'

import DeptFormView from './views/org/DeptFormView.vue'
import DeptListView from './views/org/DeptListView.vue'
import PostFormView from './views/org/PostFormView.vue'
import PostListView from './views/org/PostListView.vue'

/** 独立预览路由（与模块声明的路径 / 路由名同构，便于脱离宿主验证页面跳转）。 */
const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/org/depts' },
  { path: '/org/depts', name: 'MdmOrgDeptList', component: DeptListView },
  { path: '/org/depts/form/:id?', name: 'MdmOrgDeptForm', component: DeptFormView },
  { path: '/org/posts', name: 'MdmOrgPostList', component: PostListView },
  { path: '/org/posts/form/:id?', name: 'MdmOrgPostForm', component: PostFormView },
]

const router = createRouter({ history: createWebHashHistory(), routes })

createApp({ render: () => h(RouterView) })
  .use(router)
  .mount('#app')
