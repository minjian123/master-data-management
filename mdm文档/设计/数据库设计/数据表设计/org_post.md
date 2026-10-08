# org_post（岗位）

> mdm · 数据库设计 · 数据表设计

[文档首页](../../../文档首页.md) › [数据库设计总览](../01_数据库设计_总览.md) › [已设计数据表登记](../01_数据库设计_总览.md#tables-registry) › org_post

## 1. 归属与依据 <a id="meta"></a>

| 项 | 值 |
| --- | --- |
| 归属库 | mdm 租户库 `mdm_org_{code}`（归属服务 `org`） |
| 覆盖模块 | 02-岗位管理（岗位定义） |
| 上游依据 | 《[概要设计 · 岗位管理](../../概要设计/02_概要设计_岗位管理.md)》、《[架构设计 · 总览](../../架构设计/01_架构设计_总览.md)》「域服务划分与数据边界」节 |
| ORM 模型 | `mdm_org/models/post.py::OrgPost`（继承 `BaseModel`） |
| 状态 | 已落库（需求 `01-2` / 任务 `01_02`，2026-10-07；岗位码「创建后不可改」于 2026-10-08 放开） |
| 相关节点 | [数据库设计总览](../01_数据库设计_总览.md)、[org_dept](org_dept.md)、[org_user_post](org_user_post.md)、[org_role_post](org_role_post.md) |

## 2. 字段 <a id="fields"></a>

公共字段继承 `BaseModel`（雪花 ID / 审计 / 软删除 / 乐观锁），下表不再重复说明其语义。

| 字段 | 类型 | 可空 | 约束 / 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | BIGINT | 否 | 主键，雪花 ID | 主键 |
| `code` | VARCHAR(64) | 否 | 与 `deleted_at` 复合唯一 | 岗位码（租户内唯一；格式受 `org.post_code_pattern` 约束；**创建后可修改**） |
| `name` | VARCHAR(128) | 否 | — | 岗位名称 |
| `dept_id` | BIGINT | 否 | — | 归属部门 id（逻辑外键 → `org_dept.id`，同库） |
| `sort` | INT | 否 | 默认 0 | 排序 |
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
| `uq_org_post_code_deleted_at` | 唯一 | `(code, deleted_at)` | 岗位码租户内唯一（软删除后可复用） |
| `idx_org_post_dept_id` | 普通 | `dept_id` | 按部门筛选、归属部门引用检查 |
| `idx_org_post_status` | 普通 | `status` | 状态筛选 |
| `idx_org_post_sort` | 普通 | `sort` | 排序白名单字段 |

- 无物理外键；`dept_id` 指向 `org_dept.id`（同库逻辑外键）。
- **岗位码创建后可修改**（2026-10-08 放开）：接口接受 `code` 更新（格式与租户内唯一校验、自身同值豁免；内部引用一律 `post_id`，改码无副作用）。

## 4. 分片 / 归档 / 迁移 <a id="storage"></a>

- **分片**：不分片（岗位为常驻小型主数据）。
- **归档**：不归档（在用主数据；删除走软删除 / 回收站语义）。
- **迁移**：随 **`org:tenant` 链**迁移落地（实现在任务 `01_02`）。

## 5. 变更记录 <a id="revlog"></a>

| 日期 | 版本 | 变更 | 作者 |
| --- | --- | --- | --- |
| 2026-10-07 | v1 | 新建表结构（mdm 组织域，自 bms 概要设计 08 迁入） | minjian |
| 2026-10-08 | v2 | 岗位码由「创建后不可改」放开为可改（仅应用层行为，无结构变更） | minjian |

> 数据表设计 · 与 bms《数据库开发规范》「数据表文件规范」节配套
