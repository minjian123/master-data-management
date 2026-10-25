# 01 详细设计 · 前端模块键 snake 化与重发

> mdm 产品奠基 · 01_组织主数据承接 · 06 前端模块键 snake 化与重发 · 详细设计（开发核心文档）

[文档首页](../../../../../../文档首页.md) › [06 前端模块键 snake 化与重发](../01_组织主数据承接_06_前端模块键snake化与重发.md) › 设计

## 1. 目标与边界 <a id="scope"></a>

**目标**：把 mdm 组织域运行时模块的标识及其派生面从 kebab（`mdm-org`）一次收口为 snake（`mdm_org`），使 bms 宿主按 `MODULE_NAME_PATTERN = ^[a-z][a-z0-9_]*$` 正常加载，并完成重发与旧产物下线。

**范围内**：

1. 模块标识：`manifest.name`、Module Federation 容器名；
2. 派生键：四个插件 / 区域项键、两个 i18n 文案包键；
3. 包名：`@mdm/module-org` → `@mdm/module_org`（工作区脚本与依赖引用）；
4. 样式前缀：模块自有 CSS 类 `.mdm-org-*` → `.mdm_org-*`；
5. 模块定义 / 注册 / 构建断言与现行文档口径；
6. 重建产物、跨仓发布（新键）与旧 `mdm-org` 产物下线。

**范围外**：

| 项 | 理由 |
| --- | --- |
| 服务标识 / 表前缀 / 路径 / 事件域 / 包名 `mdm` | 已由 `01_05` 收口，本任务不动 |
| 组件名（`MdmOrgDeptList` 等 PascalCase）与 Vue 文件名 | 非运行时登记标识 |
| `data-test` 属性值（`slot-user-posts` 等） | 测试选择器，非登记面；避免无意义 churn |
| 根脚本名 `org:*` | 指「组织域」而非模块标识，且为开发者习惯入口 |
| 历史实施 / 测试记录中的 `mdm-org` 原文 | 记录当时事实，不回改；以现行文档与新增记录说明变更 |
| 旧产物归档文件本身 | 发布存储中的历史归档保留（仅从清单 / 登记面下线） |

## 2. 现状核对 <a id="current"></a>

| 面 | 现状 | 落点 |
| --- | --- | --- |
| 模块名 | `manifest.name: 'mdm-org'` | `frontend/modules/org/src/index.ts` |
| MF 容器名 | `MODULE_NAME = 'mdm-org'` | `frontend/modules/org/vite.config.ts` |
| 插件 / 区域项键 | `mdm-org:user-posts` / `user-depts` / `role-posts` / `role-depts` | `src/index.ts` |
| i18n 包键 | `mdm-org:zh-cn` / `mdm-org:en` | `src/index.ts` |
| 包名 | `@mdm/module-org` | `frontend/modules/org/package.json`、根 `frontend/package.json` 的 `org:*` 过滤 |
| CSS 前缀 | `.mdm-org-*`（6 个 `.vue`、59 处） | `src/components/slots/*.vue`、`src/views/org/*.vue` |
| 测试断言 | `manifest.name` / 插件键 / i18n 键 / 类名 | `tests/module-definition.spec.ts`、`tests/module-registration.spec.ts` 等 |
| 宿主约束 | `MODULE_NAME_PATTERN = ^[a-z][a-z0-9_]*$`，kebab 直接拒载 | bms `frontend/packages/core/src/module/define.ts` |

**事实**：`mdm-org` 当前在 bms `apps/desktop/public/modules.json` 中**没有条目**（历史发布只落 `releases/release-log`），因此「下线」指不新增旧键条目、不改历史归档；新键发布由平台侧 `release-module.mjs publish --module mdm_org --module-dir <mdm>/frontend/modules/org` 写入清单。

## 3. 设计 <a id="design"></a>

### 3.1 命名映射 <a id="mapping"></a>

| 对象 | 旧值 | 新值 |
| --- | --- | --- |
| 模块名 / MF 容器 | `mdm-org` | `mdm_org` |
| 插件 / 区域项键 | `mdm-org:user-posts` 等 4 个 | `mdm_org:user-posts` 等 4 个 |
| i18n 文案包键 | `mdm-org:zh-cn` / `mdm-org:en` | `mdm_org:zh-cn` / `mdm_org:en` |
| pnpm 包名 | `@mdm/module-org` | `@mdm/module_org` |
| CSS 前缀 | `.mdm-org-` | `.mdm_org-` |
| `data-test` / 组件名 / 路由名 / 根脚本 | 不变 | 不变（非登记标识） |

### 3.2 代码改造 <a id="code"></a>

| 文件 | 改法 |
| --- | --- |
| `src/index.ts` | `manifest.name`、四个键、两个 i18n 包键改 `mdm_org` 前缀 |
| `vite.config.ts` | `MODULE_NAME = 'mdm_org'`（同时作用于 MF 容器名与产物元数据插件） |
| `package.json`（模块） | `name` 改 `@mdm/module_org` |
| `frontend/package.json`（工作区） | `org:*` 脚本的 `--filter @mdm/module_org` 同步 |
| `src/components/slots/*.vue`、`src/views/org/*.vue` | CSS 类名与 `scoped` 选择器统一 `.mdm_org-*` |
| `tests/module-definition.spec.ts`、`tests/module-registration.spec.ts` | 断言改 `mdm_org`；补 `manifest.name` 合 `MODULE_NAME_PATTERN` 的断言 |
| `frontend/pnpm-lock.yaml` | 如需刷新，以 `pnpm install --lockfile-only` 生成，不手改 |

**不做**：不保留 `mdm-org` 双形态别名（与 bms「一次改齐」口径一致）；不改 `mtime` / 组件内部逻辑。

### 3.3 文档回写 <a id="docs"></a>

| 文档 | 处置 |
| --- | --- |
| `mdm文档/设计/架构设计/01_架构设计_总览.md` | 前端形态行模块名 / 容器名改 `mdm_org` |
| `mdm文档/资料/知识档案/主数据管理/16_…跨仓部署联调清单.md` | 模块名、发布命令 `--module mdm_org`、清单核对口径同步 |
| `01_04` 任务文档「运行时模块（模块名 `mdm-org`）」 | 改新口径并加日期注记 |
| `01_05` 详细设计 §2 第 12.1 项 / 任务文档 | 加「2026-10-25 修订」注：模块名保留结论作废，按 `01-7` 改 `mdm_org`（历史正文保留） |
| `01_01` / `01_02` 设计 / 实施 / 测试记录 | 不改（历史事实） |

### 3.4 重发与宿主登记 <a id="release"></a>

1. `pnpm install`（工作区名变更后刷新）→ `pnpm run org:check` → `pnpm run org:build`。
2. 平台侧发布：`node frontend/scripts/release-module.mjs publish --module mdm_org --module-dir D:/Develop/bizs/mdm/frontend/modules/org`（在 bms 仓根；`--dry-run` 先验）。
3. 校验 `apps/desktop/public/modules.json` 仅有 `mdm_org` 条目（无 `mdm-org`），入口指向 `mdm_org/0.1.0/remoteEntry.js`。
4. 宿主实跑：bms 桌面端启动后模块加载成功、路由 / 区域项 / i18n 正常（至少完成构建产物 + 清单 + 加载路径核对；真机联调随部署窗口）。

### 3.5 兼容与回滚 <a id="rollback"></a>

- 模块键变更**不兼容**旧清单：旧 `mdm-org` 条目若存在会被宿主拒载，发布时明确不下发旧键。
- 回滚以 Git revert + 重新发布旧构建产物（`releases/mdm-org/0.1.0` 归档仍可取）；不在宿主保留双键。
- 旧键仅在发布存储历史归档与历史文档中保留，不进入运行时登记面。

## 4. 影响面 <a id="impact"></a>

| 类别 | 对象 | 变更 |
| --- | --- | --- |
| 修改 | `frontend/modules/org/src/index.ts`、`vite.config.ts`、`package.json` | 模块标识、键前缀、容器名、包名 |
| 修改 | `frontend/modules/org/src/{components,views}/**/*.vue` | CSS 前缀（59 处） |
| 修改 | `frontend/modules/org/tests/*.spec.ts` | 断言与新增形态断言 |
| 修改 | `frontend/package.json`、`frontend/pnpm-lock.yaml` | 工作区过滤与锁文件 |
| 修改 | 现行文档 3 份 + 历史记录加修订注 | 口径 |
| 重发 | `releases/mdm_org/0.1.0/`、`apps/desktop/public/modules.json` | 新键产物与清单条目 |

## 5. 测试设计 <a id="test"></a>

**Kiwi 用例 2358**（2026-10-25 登记，先登记后编码）。

| # | 用例 | 落点 | 断言 |
| --- | --- | --- | --- |
| 1 | 模块定义形态 | `frontend/modules/org/tests/module-definition.spec.ts` | `manifest.name === 'mdm_org'` 且合 `^[a-z][a-z0-9_]*$`；四个插件键 / 两个 i18n 包键均为 `mdm_org:` 前缀 |
| 2 | 模块注册 | `tests/module-registration.spec.ts` | 注册后模块名 / 键前缀一致；无 `mdm-org` 残留 |
| 3 | 构建产物 | `pnpm run org:build` | `dist/meta.json` 的 name 为 `mdm_org`；产物 `remoteEntry.js` 容器名一致 |
| 4 | 样式前缀 | 全仓检索 | `frontend/modules/org/src` 无 `.mdm-org-`；构建 CSS 无旧前缀 |
| 5 | 静态与用例 | `pnpm run lint` / `org:typecheck` / `org:test` | 全绿 |
| 6 | 发布清单 | `release-module.mjs publish`（先 `--dry-run`） | 清单仅 `mdm_org` 条目；旧键不下发；发布日志记录新键 |
| 7 | 文档口径 | `engkit links` / `docs-scope` | 现行文档无旧键；历史记录允许保留 |

## 6. 实施顺序 <a id="order"></a>

```mermaid
flowchart LR
    A["S1 代码：index.ts / vite / package / CSS 前缀"] --> B["S2 测试断言 + 新增形态断言"]
    B --> C["S3 现行文档回写 + 历史记录修订注"]
    C --> D["S4 安装 / 静态 / 用例 / 构建"]
    D --> E["S5 发布 dry-run → 正式发布 + 清单核对"]
    E --> F["S6 记录回写 + 提交"]
```

## 7. 风险与边界 <a id="risk"></a>

| 风险 | 处置 |
| --- | --- |
| 包名变更导致 pnpm 工作区过滤 / 锁文件失败 | 先改模块 `package.json` 与根脚本，再 `pnpm install`（必要时 `--lockfile-only`），最后全量检查 |
| CSS 前缀替换误伤 `data-test` / 组件名 | 只替换 `.mdm-org-` 类名与选择器，`data-test` 值不动；构建后检索核对 |
| 发布同版本被拒（产物不可变） | 新模块名是新命名空间，按 `0.1.0` 首发；若已存在同名版本用 `--force` 并记录 `republish` |
| 宿主清单缓存 / 部署未刷新 | 发布后核对 `modules.json` 与远端入口；真机联调随部署窗口 |
| 历史文档回改破坏留痕 | 历史记录不改，仅在 `01_05` 设计 / 任务加修订注 |

## 8. 交付物与验收映射 <a id="deliver"></a>

| 交付物 | 验收要点（需求 01-7） |
| --- | --- |
| 模块名 / 容器名 / 键前缀 / 包名 / CSS 前缀 | 仓内现行面全 `mdm_org`，无 `mdm-org` 残留 |
| 测试与构建 | lint / typecheck / 全量用例 / 构建通过；产物元数据一致 |
| 宿主登记 | `modules.json` 仅新键；宿主按 `MODULE_NAME_PATTERN` 接受 |
| 文档 | 现行文档口径一致，历史记录有修订注 |

## 9. 开放项与对齐记录 <a id="align"></a>

| # | 事项 | 结论 |
| --- | --- | --- |
| 1 | 是否保留 `mdm-org` 兼容 | 不保留（2026-10-25 拍板） |
| 2 | 包名与 CSS 前缀是否同改 | 同改（全量收口） |
| 3 | `data-test` 是否同改 | 不改（非登记面） |
| 4 | 版本号是否升级 | 保持 `0.1.0`（新键即新命名空间，内容不变） |
| — | 实施回写 | 2026-10-25 实施完成：Kiwi 2358；前端 13 文件 / 118 例、变更源文件覆盖率 100%、构建与预算 / 隔离门禁绿；发布 `mdm_org@0.1.0` 并登记（清单跨仓 1 项）；详见[实施记录](../实施/01_实施_06_前端模块键snake化与重发.md)与[测试记录](../测试/01_测试_06_前端模块键snake化与重发.md) |

> 本文档依 bms《[文档生成规范](../../../../../../../bms文档/规范/文档生成规范.md)》与《[任务文档规范](../../../../../../../bms文档/规范/任务文档规范.md)》编写
