# 06 实施记录 · 前端模块键 snake 化与重发

> mdm 产品奠基 · 01_组织主数据承接 · 子任务 06 · 实施记录 01

[文档首页](../../../../../../文档首页.md) › [01 组织主数据承接](../../01_组织主数据承接.md) › [06 前端模块键 snake 化与重发](../01_组织主数据承接_06_前端模块键snake化与重发.md) › 实施　|　[← 详细设计](../设计/01_详细设计_06_前端模块键snake化与重发.md)

## 1. 信息 <a id="info"></a>

- 任务：`01_06` 前端模块键 snake 化与重发；对应需求 [01-7](../../../../需求/01_需求_组织主数据承接.md#r01-7)。
- 详细设计：[01_详细设计_06_前端模块键snake化与重发](../设计/01_详细设计_06_前端模块键snake化与重发.md)（2026-10-25 定稿，§9 四项拍板）。
- 交付日期：2026-10-25；Kiwi 用例 **2358**。
- 范围：**mdm 仓**（模块名 / MF 容器名 / 插件与区域项键 / i18n 包键 / 包名 / CSS 前缀 / 测试 / 现行文档）＋ **bms 仓**（发布登记 `modules.json` 与 `release-log`，跨仓发布由平台侧执行）。历史实施 / 测试记录保留原文，仅加修订注。

## 2. 过程与交付物 <a id="process"></a>

```mermaid
flowchart LR
    A["前置：对齐 bms 包名下划线收口（a045f91）"] --> B["S1 代码：index.ts / vite / package / CSS 前缀"]
    B --> C["S2 测试：既有断言改 mdm_org + module-key 用例（Kiwi 2358）"]
    C --> D["S3 文档：现行文档回写 + 01_05 修订注"]
    D --> E["S4 安装 / lint / typecheck / 118 例 / 构建 / 预算 / 隔离"]
    E --> F["S5 发布：dry-run → 正式发布 → 清单核对"]
    F --> G["S6 实施 / 测试记录 + 计划回写 + 提交"]
```

### 2.1 前置修复（跨仓，独立提交 `a045f91`） <a id="prereq"></a>

bms `c42f5f5ad`（2026-10-25「命名收口——前端包名统一下划线」）把平台前端包改为 `@bms/api_types` / `@bms/ui_ep`（目录同步 snake），mdm 前端仍引旧名（`file:` 路径已不存在），`pnpm install` 报锁文件过期、构建链断。本任务实施前先单独提交对齐（不改需求 / 任务范围）：

| 面 | 变更 |
| --- | --- |
| 依赖声明 | `@bms/api-types` → `@bms/api_types`、`@bms/ui-ep` → `@bms/ui_ep`（`file:` 路径同步 `packages/api_types` / `packages/ui_ep`） |
| 源码 / 用例 import | 10 个 `.vue` / `.ts` 文件与 2 个用例文件同步改包名 |
| 锁文件 | `pnpm-lock.yaml` 重生成（含工作区成员路径与 peer 解析归一） |
| 现行文档 | `.gitlab-ci.yml` 构建前提注释、联调清单、依赖外置说明、类型包 README |

### 2.2 S1 代码改造 <a id="code"></a>

| 文件 | 变更 |
| --- | --- |
| `frontend/modules/org/src/index.ts` | `manifest.name` → `mdm_org`；四个插件 / 区域项键 → `mdm_org:user-posts` / `user-depts` / `role-posts` / `role-depts`；两个 i18n 包键 → `mdm_org:zh-cn` / `mdm_org:en` |
| `frontend/modules/org/vite.config.ts` | `MODULE_NAME = 'mdm_org'`（同时作用于 MF 容器名与产物元数据插件） |
| `frontend/modules/org/package.json` | 包名 `@mdm/module-org` → `@mdm/module_org` |
| `frontend/package.json` | `org:*` 七个脚本的 `--filter` 同步 `@mdm/module_org` |
| `.gitlab-ci.yml` | 前端测试作业 `--filter @mdm/module_org` |
| `src/components/slots/*.vue`、`src/views/org/*.vue` | 自有 CSS 类名与 `scoped` 选择器 `.mdm-org-*` → `.mdm_org-*`（**7 个文件 / 59 处**；设计记为 6 个文件，实测含 `DeptListView` 与 `PostListView` 两个视图页） |
| `frontend/packages/api-types/README.md` | 消费方包名同步 |

**未改**：`data-test` 属性值、组件名 / Vue 文件名、路由名、根脚本名 `org:*`、服务标识 `mdm`、真实请求路径；不保留 `mdm-org` 兼容别名。

### 2.3 S2 测试 <a id="test-code"></a>

- `tests/module-definition.spec.ts`：清单身份改 `mdm_org`，补 `MODULE_NAME_PATTERN` 断言；区域项键 / i18n 包键改新键。
- `tests/module-registration.spec.ts`：默认导出与文案包键位改 `mdm_org`。
- 新增 `tests/module-key.spec.ts`（`kiwi_id: 2358`，4 例）：模块名合宿主模式、四区域项键 / 两 i18n 包键同源前缀、注册面无第二种前缀形态。

### 2.4 S3 文档回写 <a id="docs"></a>

| 文档 | 处置 |
| --- | --- |
| `mdm文档/设计/架构设计/01_架构设计_总览.md` | 前端形态行改 `@mdm/module_org` / MF 容器名 `mdm_org`（标注 2026-10-25 模块键改 snake） |
| `mdm文档/资料/知识档案/主数据管理/16_…跨仓部署联调清单.md` | 模块名、发布命令 `--module mdm_org`、清单核对口径同步 |
| `需求/01_需求_组织主数据承接.md` | 01-4 内容行模块名改 `mdm_org` 并注明变更来源 |
| `01_04` 任务文档 | 运行时模块名改 `mdm_org` 并加日期注记 |
| `01_05` 详细设计 §2 决策 12 / 12.1、任务文档 | 加「2026-10-25 修订」注：模块名保留结论作废（历史正文保留） |
| `01_01` / `01_02` / `01_04` 详细设计与各实施 / 测试记录 | 不改（历史事实） |
| 计划 / 本条任务文档 | 阶段计划回写交付结论；任务文档补记录链接 |

### 2.5 S4 校验 <a id="verify"></a>

在 `mdm/frontend` 执行 `pnpm install`（锁文件稳定）后：`pnpm run org:check`（lint + typecheck + 13 文件 / 118 例）、变更源文件覆盖率门禁（`src/index.ts` 行 + 分支 100%）、`pnpm run org:build`（产物元数据 `name=mdm_org`）、`pnpm run org:budget`（入口 12.2 KB / 6 块）、`pnpm run org:guard`（产物面隔离零违规）、`pnpm run org:build:standalone`（独立预览构建）。产物 CSS 仅含 `.mdm_org-*`，`dist/` 无 `mdm-org` 残留。

### 2.6 S5 发布与登记 <a id="release"></a>

1. `node frontend/scripts/release-module.mjs publish --module mdm_org --module-dir D:/Develop/bizs/mdm/frontend/modules/org --dry-run` → 通过（四关强校验）。
2. 正式发布 → 归档 `bms frontend/releases/mdm_org/0.1.0/`（`remoteEntry.js` + `module.meta.json` + sourcemap + `@mf-types`），清单条目 `{name: mdm_org, entry: http://localhost:5002/mdm_org/0.1.0/remoteEntry.js, version: 0.1.0, mode: remote}`，留痕 `source: external`。
3. `node scripts/check-module-manifest.mjs` → 在册模块「仓内 3 项 / 跨仓 1 项（mdm_org）」；`modules.json` 无 `mdm-org` 条目（改前本就没有，故无需删除旧条目）。
4. 版本保持 `0.1.0`：新模块名即新命名空间，内容等价于旧归档，按设计 §9 第 4 项执行。

## 3. 关键结论与偏差 <a id="notes"></a>

| # | 事项 | 结论 |
| --- | --- | --- |
| 1 | CSS 前缀文件数 | 设计记 6 个 `.vue` / 59 处；实测 7 个文件 / 59 处（含 `DeptListView.vue`、`PostListView.vue`），替换范围按实测执行 |
| 2 | 包名变更对锁文件 | 工作区包名不进 `importers` 键，`pnpm-lock.yaml` 变化来自 bms 包名对齐与 peer 解析归一，非模块改名单独引入 |
| 3 | 旧产物下线 | 本克隆发布存储无 `mdm-org` 归档与清单条目；「下线」落实为不登记旧键、不改历史归档，运行时不存在双形态 |
| 4 | 宿主加载验证 | 已完成构建产物 / 元数据 / 入口路径 / 清单格式核对；真机宿主加载随部署窗口（见 §5） |
| 5 | 跨仓前置 | bms 包名下划线收口需产品仓同步；本次已对齐并单独提交，后续 bms 包名再变须同步 mdm 前端 |

## 4. 交付物 <a id="deliver"></a>

```
mdm/
├─ frontend/
│  ├─ package.json                                  # org:* 过滤改 @mdm/module_org
│  ├─ pnpm-lock.yaml                                # 包名对齐后重生成
│  └─ modules/org/
│     ├─ package.json                               # 包名 @mdm/module_org
│     ├─ vite.config.ts                             # MF 容器名 mdm_org
│     ├─ src/index.ts                               # 清单名 + 四插件键 + 两 i18n 键
│     ├─ src/components/slots/*.vue                 # CSS 前缀 .mdm_org-
│     ├─ src/views/org/*.vue                        # CSS 前缀 .mdm_org-
│     └─ tests/
│        ├─ module-definition.spec.ts               # 身份 / 键位断言
│        ├─ module-registration.spec.ts             # 注册面断言
│        └─ module-key.spec.ts                      # Kiwi 2358（新增）
├─ .gitlab-ci.yml                                   # CI 过滤包名同步
└─ mdm文档/…                                        # 现行文档回写 + 实施 / 测试记录
```

**bms 仓**：`frontend/apps/desktop/public/modules.json`、`frontend/releases/release-log.{json,md}`（发布登记，独立提交）；归档目录 `frontend/releases/mdm_org/0.1.0/`（gitignore，不入库）。

## 5. 遗留 <a id="leftover"></a>

| # | 事项 | 归口 |
| --- | --- | --- |
| 1 | bms 桌面端真机加载 `mdm_org` 并验证路由 / 区域项 / i18n（真实网关与令牌） | 部署联调窗口（随 bms `11_02` 联合验收） |
| 2 | 生产托管基址替换（`localhost:5002` → 部署基址）与清单下发 | 部署阶段 |
| 3 | 发布存储历史 `mdm-org` 归档（若生产存储存在）保留不登记 | 平台发布存储历史，不进入运行时登记面 |

## 6. 回滚 <a id="rollback"></a>

Git revert 本任务提交后重新发布旧构建产物（历史 `releases/mdm-org/0.1.0` 归档仍可取）；宿主侧不保留双键，回滚即整体回到 kebab 形态（仅适用于宿主约束回退的假设场景）。
