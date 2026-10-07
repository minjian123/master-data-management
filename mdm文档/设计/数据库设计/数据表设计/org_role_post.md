# org_role_post（角色-岗位分配）

> mdm · 数据库设计 · 数据表设计

[文档首页](../../../文档首页.md) › [数据库设计总览](../01_数据库设计_总览.md) › [已设计数据表登记](../01_数据库设计_总览.md#tables-registry) › org_role_post

## 1. 归属与依据 <a id="meta"></a>

| 项 | 值 |
| --- | --- |
| 归属库 | mdm 租户库 `mdm_org_{code}`（归属服务 `org`） |
| 覆盖模块 | 02-岗位管理（角色 × 岗位分配） |
| 上游依据 | 《[概要设计 · 岗位管理](../../概要设计/02_概要设计_岗位管理.md)》、《[架构设计 · 总览](../../架构设计/01_架构设计_总览.md)》「域服务划分与数据边界」节 |
| ORM 模型 | `mdm_org/models/role_post.py::OrgRolePost` |
| 状态 | 已落库（需求 `01-2` / 任务 `01_02`，2026-10-07；2026-10-06 归组织域） |
| 相关节点 | [数据库设计总览](../01_数据库设计_总览.md)、[org_post](org_post.md) |

## 2. 字段 <a id="fields"></a>

**关联表**：以雪花 `id` 为主键（基座 `BaseModel`），业务列复合唯一防重（2026-10-07 口径修订）。

| 字段 | 类型 | 可空 | 约束 / 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | BIGINT | 否 | 主键，雪花 ID | 主键 |
| `role_id` | BIGINT | 否 | 与 `post_id` + `deleted_at` 复合唯一 | 角色 id（逻辑外键 → bms `sys_role.id`，**跨服务**） |
| `post_id` | BIGINT | 否 | 与 `role_id` + `deleted_at` 复合唯一 | 岗位 id（逻辑外键 → `org_post.id`，同库） |
| `created_at` | DATETIME | 否 | 审计 | 创建时间（UTC） |
| `created_by` | BIGINT | 是 | 审计 | 创建人 |
| `updated_at` | DATETIME | 否 | 审计 | 更新时间（UTC） |
| `updated_by` | BIGINT | 是 | 审计 | 更新人 |
| `deleted_at` | DATETIME | 是 | 软删除（NULL=未删） | 软删除时间 |
| `version` | INT | 否 | 默认 1 | 乐观锁版本 |

> **解绑语义**：解绑走**软删除**（留痕），复合唯一含 `deleted_at` 使解绑后可重新分配。

## 3. 索引与约束 <a id="index"></a>

| 名称 | 类型 | 列 | 说明 |
| --- | --- | --- | --- |
| `uq_org_role_post_role_post_deleted_at` | 唯一 | `(role_id, post_id, deleted_at)` | 分配防重（软删除后可重分配） |
| `idx_org_role_post_post_id` | 普通 | `post_id` | 岗位下角色反查（`role_id` 为唯一索引先导列，不再单列） |

- 无物理外键；`role_id` 指向 bms `sys_role.id`（**跨服务逻辑外键**），`post_id` 指向 `org_post.id`（同库）。
- 变更经 `org.role_post.changed` 事件驱动 bms 权限版本失效；「按用户解析角色」只读契约依本表解析岗位角色。

## 4. 分片 / 归档 / 迁移 <a id="storage"></a>

- **分片**：不分片。
- **归档**：不归档。
- **迁移**：随 **`org:tenant` 链**迁移落地（实现在任务 `01_02`）。

## 5. 变更记录 <a id="revlog"></a>

| 日期 | 版本 | 变更 | 作者 |
| --- | --- | --- | --- |
| 2026-10-07 | v1 | 新建表结构（mdm 组织域，2026-10-06 归入组织域） | minjian |
| 2026-10-07 | v2 | 主键口径修订：联合主键 → 雪花 `id` 主键 + `(role_id, post_id, deleted_at)` 复合唯一；补软删除与 `version` | minjian |

> 数据表设计 · 与 bms《数据库开发规范》「数据表文件规范」节配套
