# 产品契约类型包（frontend/packages/api-types）

> `@mdm/api-types`：由 mdm **产品自持**契约快照生成的前端类型（按域一份，当前 `org`）。

## 定位

- 消费产品契约快照生成前端类型，供 mdm 模块（当前 `@mdm/module-org`）与后续消费方共享同一套接口类型。
- **事实源是产品契约快照**：`mdm/deploy/contracts/<域>.json`（由后端 `ops.contract_snapshot export` 产出）。
  与 bms 侧 `@bms/api-types` 的关系：**并列、互不混用**——平台服务契约类型取 bms 包，产品契约类型取本包。
- **生成物不手改**：`src/*.ts` 由 `scripts/generate.mjs` 产出；后端端点变更后重生成。

## 快速命令

> 在 mdm 前端工作区根（`mdm/frontend/`）执行。

```bash
pnpm run api-types:gen          # 生成（产品契约快照 → src/*.ts）
pnpm run api-types:gen:check    # 零漂移校验（逐字节比对；CI 同口径硬门禁）
pnpm run api-types:check        # gen:check + typecheck + lint + test 聚合
```

## 目录结构

```text
frontend/packages/api-types/
├── src/
│   ├── index.ts    # 包根出口（按域命名空间导出）
│   └── org.ts      # 组织域契约类型（`org_dept` / `org_post` 等 schema 与端点）
├── scripts/        # generate.mjs（契约快照 → 类型；`--check` 零漂移）
└── tests/          # 生成物一致性用例（覆盖快照全部路径 / 导出面 / 生成头）
```

## 关键约定

- **单一来源**：类型只源自产品契约快照；前端不维护手写接口类型。
- **后端改端点后必须重生成**：`pnpm run api-types:gen`，否则 `gen:check` 漂移失败（CI 阻断）。
- **生成物与源码同库提交**：`src/*.ts` 入库，评审看差异而非全量。
- **构建前提**：模块工程的平台基座包（`@bms/*`）经 `file:` 引工作区 bms 克隆，故 `mdm/` 与 `bms/` 须同级克隆。

## 文档导航

- 任务详细设计：《[01 详细设计 · 前端接入与 bms 切换支撑](../../../mdm文档/项目/01_mdm%20产品奠基/任务/01_组织主数据承接/01_组织主数据承接_04_前端接入与bms切换支撑/设计/01_详细设计_04_前端接入与bms切换支撑.md)》§7
- 平台侧参照：bms《[微前端业务模块接入指南](../../../../bms文档/资料/知识档案/微前端/10_微前端_业务模块接入指南.md)》
