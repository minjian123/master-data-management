<div align="center">

![Markdown](https://img.shields.io/badge/Markdown-文档-000000?logo=markdown&logoColor=white)
![BMS 产品服务](https://img.shields.io/badge/BMS产品服务-主数据管理-3B6FB6?logo=database&logoColor=white)
![阶段一 已完成](https://img.shields.io/badge/阶段一-已完成-2F8F4F)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

## 简介

**mdm（主数据管理）** 是 BMS 平台之上的独立产品：专门承载**部门、岗位、供应商、客户、物料**等**跨业务项目公用的基础数据**，以**主数据（Master Data）**统一管理——供采购、销售、仓储等各业务项目一致性引用。独立仓库、独立演进，以 **产品服务（独立服务）** 形态接入 BMS 平台（后端按主数据域拆服务独立部署、每服务独立库，前端以运行时模块接入，经 OIDC 认证 + 开放接口（`/api/open`）+ 事件复用平台能力），自身只做主数据域。

> **边界**：用户、角色、菜单、权限、字典、系统参数等**平台运行必需的基础数据**（登录与权限等）仍属 BMS 基座，保留在 bms 仓库（`sys_` 域），不迁入 mdm。部门、岗位由原平台组织模块迁出为 mdm **组织主数据域（org）**。

## 文档

> 全部文档位于 `mdm文档/` 目录，入口为《[文档首页](mdm文档/文档首页.md)》（全量导航）。正文以 Markdown 为载体，线框图/可交互原型保留 `.html` 资产。

> 工作区模型：本仓库与 `bms` 克隆平级置于工作区（如 `bizs/`）；仓库根以软链 `bms文档 → ../bms/bms文档` 并排引用基座，基座只在 bms 仓库演进、靠 git 同步（见 `bms文档`《平台可扩展性规划》「工作区模型与基座引用」节）。

## 目录结构

```text
mdm/
├── README.md                 # 本文件
├── LICENSE                   # MIT 许可
├── renovate.json             # Renovate 配置（CI 依赖自动升级已停用）
├── engkit.toml               # 跨仓工程化工具包配置（文档根 / 预检步骤 / 覆盖率门禁 / 拦截口径）
├── bms文档/                  # 符号链接 → ../bms/bms文档（基座权威源，并排引用）
├── backend/                  # 后端工程（uv workspace：services/ 各主数据域服务）
├── frontend/                 # 前端工程（pnpm workspace：modules/ 运行时模块 + packages/ 类型包）
├── deploy/                   # 部署配置（Dockerfile / compose / contracts / events）
│   └── .env.example          # 凭据模板
├── ops/                      # 运维脚本
└── mdm文档/                  # 项目文档
    ├── 文档首页.md            # 全量导航
    ├── 规划/                 # 1篇：《mdm 主数据管理规划》
    ├── 规范/                 # 1篇：《英文简称规范（mdm）》（产品专属规范，通用规范为基座）
    ├── 项目/                 # 需求/任务/计划基线
    ├── 设计/                 # 主数据体系设计（总纲+节点）
    │   ├── 架构设计/          # 总体架构（主数据外置与平台接入）
    │   ├── 概要设计/          # 组织/供应商/客户/物料主数据模块设计
    │   └── 原型设计/          # 可交互界面原型
    ├── 资料/                 # 产品专属资料与知识档案
    │   └── 知识档案/          # 知识档案总览 + 主数据管理专题（15 篇）
    └── 用户文档/             # 本地资源（按需本地创建，内容已 gitignore）
```

> 凭据统一存 `deploy/.env`（已 gitignore，模板见 `deploy/.env.example`）。

## 使用指南

| 目的 | 文档 |
| --- | --- |
| 全量文档导航 | [文档首页](mdm文档/文档首页.md) |
| 主数据管理规划（域全景 / 产品服务接入 / 标识符登记） | [规划/mdm主数据管理规划](mdm文档/规划/mdm主数据管理规划.md) |
| 文档格式与检查清单 | [bms文档/规范/文档生成规范](bms文档/规范/文档生成规范.md) |
| 命名约定（代码 / 数据库 / API / 基础设施） | [bms文档/规范/命名规范](bms文档/规范/命名规范.md) |
| mdm 主数据域英文简称（表前缀 / 业务码 / 错误码段等） | [规范/英文简称规范](mdm文档/规范/英文简称规范.md) |
| 主数据管理知识档案（标准做法专题，15 篇） | [资料/知识档案/主数据管理总览](mdm文档/资料/知识档案/主数据管理/01_主数据管理_总览.md) |
| 产品服务接入与能力边界 | bms 仓库《微服务演进规划》《平台可扩展性规划》《项目规划说明》 |
| 开发环境与基础设施 | bms 仓库《开发部署规划》与开发服务器部署说明 |
| 本地预检（链接 / 口径 / 定向用例 + 覆盖率门禁） | 下文「本地预检」节 |

## 本地预检

推送前在 `backend/` 下执行（工具为跨仓工程化工具包 `engkit`，与 CI 门禁同口径）：

```bash
cd backend
uv run engkit links --root ..          # 文档相对链接与锚点
uv run engkit docs-scope --root ..     # 文档口径：进度类字段只允许落在阶段计划
uv run engkit run_once --root .. -- uv run engkit preflight --root ..   # 预检：静态 + 契约门禁 + 定向用例 + 覆盖率
```

- 预检步骤、覆盖率阈值与拦截口径都在仓根 `engkit.toml`——改步骤即改配置，不改工具包代码；
- 分钟级命令一律经 `run_once` 包装（窗口内命中即回放完整输出）；本地裸跑重命令（全量 `pytest`、无参数 `ruff` / `pyright`）会被守卫拦下，`ENGKIT_ALLOW_UNWRAPPED=1` 仅用于排查包装器自身问题；
- 本地确需跑全量 pytest 须显式声明（`pytest --full`），口径见 engkit 仓《工程化工具包说明》§4.4。
