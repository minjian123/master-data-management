# org_dept（部门）

> mdm · 数据库设计 · 数据表设计

[文档首页](../../../文档首页.md) › [数据库设计总览](../01_数据库设计_总览.md) › [已设计数据表登记](../01_数据库设计_总览.md#tables-registry) › org_dept

## 1. 归属与依据 <a id="meta"></a>

| 项 | 值 |
| --- | --- |
| 归属库 | mdm 租户库 `mdm_org_{code}`（归属服务 `org`） |
| 覆盖模块 | 03-部门管理（组织架构树） |
| 上游依据 | 《[概要设计 · 部门管理](../../概要设计/03_概要设计_部门管理.md)》、《[架构设计 · 总览](../../架构设计/01_架构设计_总览.md)》「域服务划分与数据边界」节 |
| ORM 模型 | `mdm_org/models/dept.py::OrgDept`（继承 `BaseModel`） |
| 状态 | 已落库（需求 `01-2` / 任务 `01_02`，2026-10-07；`code` 列随嵌套子任务 `02-01` 于 2026-10-08 新增） |
| 相关节点 | [数据库设计总览](../01_数据库设计_总览.md)、[org_post](org_post.md)、[org_role_dept](org_role_dept.md) |

## 2. 字段 <a id="fields"></a>

公共字段继承 `BaseModel`（雪花 ID / 审计 / 软删除 / 乐观锁），下表不再重复说明其语义。

| 字段 | 类型 | 可空 | 约束 / 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | BIGINT | 否 | 主键，雪花 ID | 主键 |
| `code` | VARCHAR(64) | 否 | 与 `deleted_at` 复合唯一 | 部门编码（租户内唯一；格式受 `org.dept_code_pattern` 约束；创建后可修改） |
| `parent_id` | BIGINT | 是 | — | 父部门 id（逻辑外键 → 本表 `id`，同库）；根部门为空 |
| `ancestors` | VARCHAR(512) | 否 | 默认 `/` | 祖先 id 路径（如 `/1/5/9/`），供子树查询与 `@dept_subtree` 展开 |
| `name` | VARCHAR(128) | 否 | 与 `parent_id` + `deleted_at` 复合唯一 | 部门名称 |
| `sort` | INT | 否 | 默认 0 | 同级排序 |
| `status` | VARCHAR(16) | 否 | 默认 `enabled` | 状态（`enabled` / `disabled`） |
| `created_at` | DATETIME | 否 | 审计 | 创建时间（UTC） |
| `created_by` | BIGINT | 是 | 审计 | 创建人 |
| `updated_at` | DATETIME | 否 | 审计 | 更新时间（UTC） |
| `updated_by` | BIGINT | 是 | 审计 | 更新人 |
| `deleted_at` | DATETIME | 是 | 软删除（NULL=未删） | 软删除时间 |
| `version` | INT | 否 | 默认 1 | 乐观锁版本 |

## 3. 索引与约束 <a id="index"></a>

| 名称 | 类型 | 列 | 说明 |
| --- | --- | --- | --- |
| `uq_org_dept_code_deleted_at` | 唯一 | `(code, deleted_at)` | 部门编码租户内唯一（软删除后可复用） |
| `uq_org_dept_parent_name_deleted_at` | 唯一 | `(parent_id, name, deleted_at)` | 同父部门名称唯一（软删除后可复用） |
| `idx_org_dept_parent_id` | 普通 | `parent_id` | 父子树遍历 |
| `idx_org_dept_status` | 普通 | `status` | 状态筛选 |
| `idx_org_dept_ancestors` | 普通 | `ancestors` | 子树查询与 `@dept_subtree` 展开（前缀匹配） |

- 无物理外键；`parent_id` 指向本表 `id`（同库逻辑外键）。
- **同父名称唯一**为设计补充（概要设计未显式声明），用于保证同级部门名不重复；如需允许重名，删除该唯一约束并回写本表与概要设计。
- **部门编码**（2026-10-08 新增）：必填、租户内唯一、**创建后可修改**（格式 + 唯一校验，自身同值豁免；内部引用一律 `dept_id`，改码无副作用）；格式受系统参数 `org.dept_code_pattern` 约束（默认 `^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$`）；存量行由迁移 `0003_dept_code` 按 `id` 升序回填 `DEPT` + 定长 4 位序号（超 9999 自动扩位）。

## 4. 分片 / 归档 / 迁移 <a id="storage"></a>

- **分片**：不分片（组织架构树为常驻小型主数据）。
- **归档**：不归档（在用主数据；删除走软删除 / 回收站语义）。
- **迁移**：随 **`org:tenant` 链**迁移落地（实现在任务 `01_02`）。

## 5. 变更记录 <a id="revlog"></a>

| 日期 | 版本 | 变更 | 作者 |
| --- | --- | --- | --- |
| 2026-10-07 | v1 | 新建表结构（mdm 组织域，自 bms 概要设计 05 迁入） | minjian |
| 2026-10-08 | v2 | 增 `code` 部门编码列（必填 / 租户内唯一 / 可改）与唯一约束 `uq_org_dept_code_deleted_at`；存量按 `id` 升序回填 `DEPT` + 定长序号（迁移 `0003_dept_code`） | minjian |

> 数据表设计 · 与 bms《数据库开发规范》「数据表文件规范」节配套
