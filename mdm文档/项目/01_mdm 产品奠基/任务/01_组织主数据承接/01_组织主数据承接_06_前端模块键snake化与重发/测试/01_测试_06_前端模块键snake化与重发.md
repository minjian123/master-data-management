# 06 测试记录 · 前端模块键 snake 化与重发

> mdm 产品奠基 · 01_组织主数据承接 · 子任务 06 · 测试记录 01

[文档首页](../../../../../../文档首页.md) › [01 组织主数据承接](../../01_组织主数据承接.md) › [06 前端模块键 snake 化与重发](../01_组织主数据承接_06_前端模块键snake化与重发.md) › 测试　|　[← 实施记录](../实施/01_实施_06_前端模块键snake化与重发.md)

## 1. 信息 <a id="info"></a>

- 任务：`01_06` 前端模块键 snake 化与重发；对应需求 [01-7](../../../../需求/01_需求_组织主数据承接.md#r01-7)。
- **Kiwi TCMS 用例：2358**（2026-10-25 登记，先登记后编码；自动化用例以 `kiwi_id: 2358` 标注）。
- 测试依据：详细设计 [§5 测试设计](../设计/01_详细设计_06_前端模块键snake化与重发.md#test) + 实施记录 §3。
- 测试日期：2026-10-25；测试人：minjian。
- 测试环境：Windows 开发机；Node `v24.20.0`、pnpm `11.7.0`、Python 3.14（`uv`）；mdm 前端工作区与同级 `bms` 克隆。

## 2. 用例清单 <a id="cases"></a>

| # | 用例（详细设计 §5） | 自动化落点 | 断言 |
| --- | --- | --- | --- |
| 1 | 模块定义形态 | `tests/module-key.spec.ts`（Kiwi 2358）+ `tests/module-definition.spec.ts` | `manifest.name === 'mdm_org'` 且合 `^[a-z][a-z0-9_]*$`；四区域项键 / 两 i18n 包键均 `mdm_org:` 前缀 |
| 2 | 模块注册 | `tests/module-registration.spec.ts` + `tests/module-key.spec.ts` | 注册面模块名 / 键前缀一致；键位集合无第二种前缀形态 |
| 3 | 构建产物 | `pnpm run org:build` + 产物核对 | `dist/module.meta.json` 的 `name` 为 `mdm_org`；`remoteEntry.js` 容器名 / 共享域名为 `mdm_org` |
| 4 | 样式前缀 | 源码与 `dist/` 检索 | `src` 无 `.mdm-org-`；产物 CSS 仅 `.mdm_org-*` |
| 5 | 静态与用例 | `pnpm run org:check` | lint / typecheck / 全量用例全绿 |
| 6 | 发布清单 | `release-module.mjs publish`（先 `--dry-run`） | 清单仅新增 `mdm_org`；无 `mdm-org` 条目；发布日志记录新键 |
| 7 | 文档口径 | `engkit links` / `docs-scope` | 断链 0、失效锚点 0；进度类字段零违规 |

## 3. 执行结果 <a id="result"></a>

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 安装 | `pnpm install` | 通过；锁文件稳定（重复安装无变化） |
| Lint | `pnpm run org:lint`（`--max-warnings 0`） | 通过 |
| 类型 | `pnpm run org:typecheck`（`vue-tsc -b`） | 通过 |
| 全量用例 | `pnpm run org:test`（`vitest run`） | **13 文件 / 118 例全部通过** |
| 变更源文件覆盖率 | `vitest run --coverage --coverage.include=src/index.ts --coverage.thresholds.lines=100 --coverage.thresholds.branches=100` | 100%（语句 11/11、分支 0/0、函数 9/9、行 11/11） |
| 构建（远端） | `pnpm run org:build` | 通过；`module.meta.json` = `{name: mdm_org, version: 0.1.0, contractVersion: 2}` |
| 体积预算 | `pnpm run org:budget` | 通过：入口 12.2 KB（预算 17 KB）/ 最大块 6.3 KB（预算 8 KB）/ 6 块（上限 8）/ 异步块 17（下限 4） |
| 产物面隔离 | `pnpm run org:guard` | 通过：零违规（CSS 7 / 模块自有 JS 块 8） |
| 独立预览构建 | `pnpm run org:build:standalone` | 通过 |
| 源码残留检索 | `src` / `tests` / 构建配置检索 `mdm-org` / `module-org` | 0 处 |
| 产物残留检索 | `dist/` 检索 `mdm-org` | 0 处；CSS 实测 `.mdm_org-*` |
| 发布 dry-run | `release-module.mjs publish --module mdm_org --module-dir <mdm>/frontend/modules/org --dry-run` | 通过（四关强校验；入口 gzip 12.2 KB / 6 块） |
| 正式发布 | 同上去掉 `--dry-run`（bms 仓根） | 通过；归档 `releases/mdm_org/0.1.0/`，清单条目指向 `mdm_org/0.1.0/remoteEntry.js` |
| 清单核对 | `node scripts/check-module-manifest.mjs` | 通过：仓内 3 项 / 跨仓 1 项（`mdm_org`），版本发现一致、sourcemap 就位 |
| 文档链接 | `uv run engkit links` | 断链 0、失效锚点 0 |
| 文档口径 | `uv run engkit docs-scope` | 违规 0 处（60 份文档） |
| 预检（快进档） | `engkit run_once -- engkit preflight --fast` | 全部通过（17.7s，退出码 0） |

## 4. 覆盖率 <a id="coverage"></a>

口径见 bms《[AI开发规范](../../../../../../../bms文档/规范/AI开发规范.md)》「覆盖率要求」节（行 + 分支 100%，按变更源文件门禁）。

本次变更源文件中仅 `src/index.ts` 含逻辑（清单名与键位常量），实测语句 11/11、函数 9/9、行 11/11、分支 0/0（无分支），**100%**。其余变更面为 CSS 类名（7 个 `.vue`）、JSON / 配置与文档，不含逻辑分支。

## 5. 问题与偏差 <a id="issues"></a>

| # | 事项 | 处置 |
| --- | --- | --- |
| 1 | **跨仓阻塞**：bms `c42f5f5ad` 已把前端包名改为 `@bms/api_types` / `@bms/ui_ep`，mdm 仍引旧名，`pnpm install` 报锁文件过期 | 经确认后先单独提交对齐（`a045f91`），再执行本任务；不计入 01_06 范围，已在实施记录 §2.1 留痕 |
| 2 | 设计记 CSS 前缀为 6 个 `.vue` / 59 处，实测 7 个文件 / 59 处 | 按实测替换；文件数偏差在实施记录 §3 登记 |
| 3 | `pnpm-lock.yaml` 重生成伴随 peer 解析归一（`supports-color` 变体） | 与包名对齐同批提交；重复安装稳定，不影响产物 |
| 4 | 宿主真机加载未在本次执行 | 已完成产物 / 元数据 / 入口路径 / 清单核对；真机联调随部署窗口（遗留见实施记录 §5） |

## 6. 结论 <a id="conclusion"></a>

Kiwi **2358** 覆盖的 7 项验收点全部通过：模块名 / 容器名 / 插件与区域项键 / i18n 包键 / 包名 / CSS 前缀均收口为 `mdm_org`，仓内现行面零旧键残留；前端静态检查、118 例全量用例、变更源文件覆盖率、构建与产物门禁全绿；新键产物完成跨仓发布并登记，宿主清单只含 `mdm_org`。真机宿主加载与生产托管基址替换列入部署联调遗留。
