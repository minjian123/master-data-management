# org_user_post（用户-岗位关联）

> mdm · 数据库设计 · 数据表设计

[文档首页](../../../文档首页.md) › [数据库设计总览](../01_数据库设计_总览.md) › [已设计数据表登记](../01_数据库设计_总览.md#tables-registry) › org_user_post

## 1. 归属与依据 <a id="meta"></a>

| 项 | 值 |
| --- | --- |
| 归属库 | mdm 租户库 `mdm_org_{code}`（归属服务 `org`） |
| 覆盖模块 | 02-岗位管理（用户-岗位多对多关联） |
| 上游依据 | 《[概要设计 · 岗位管理](../../概要设计/02_概要设计_岗位管理.md)》、《[架构设计 · 总览](../../架构设计/01_架构设计_总览.md)》「域服务划分与数据边界」节 |
| ORM 模型 | `mdm_org/models/user_post.py::OrgUserPost` |
| 状态 | 已落库（需求 `01-2` / 任务 `01_02`，2026-10-07；原 bms `sys_user_post`，2026-10-03 归 mdm） |
| 相关节点 | [数据库设计总览](../01_数据库设计_总览.md)、[org_post](org_post.md) |

## 2. 字段 <a id="fields"></a>

**关联表**：以雪花 `id` 为主键（基座 `BaseModel`），业务列复合唯一防重（见 bms《数据库设计 · 数据规范》「公共字段」节关联表口径——2026-10-07 修订）。

| 字段 | 类型 | 可空 | 约束 / 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | BIGINT | 否 | 主键，雪花 ID | 主键 |
| `user_id` | BIGINT | 否 | 与 `post_id` + `deleted_at` 复合唯一 | 用户 id（逻辑外键 → bms `sys_user.id`，**跨服务**） |
| `post_id` | BIGINT | 否 | 与 `user_id` + `deleted_at` 复合唯一 | 岗位 id（逻辑外键 → `org_post.id`，同库） |
| `is_primary` | BOOLEAN | 否 | 默认假 | **主要岗位**标记（该用户所属岗位以主要项为准；同用户至多一个） |
| `created_at` | DATETIME | 否 | 审计 | 创建时间（UTC） |
| `created_by` | BIGINT | 是 | 审计 | 创建人 |
| `updated_at` | DATETIME | 否 | 审计 | 更新时间（UTC） |
| `updated_by` | BIGINT | 是 | 审计 | 更新人 |
| `deleted_at` | DATETIME | 是 | 软删除（NULL=未删） | 软删除时间 |
| `version` | INT | 否 | 默认 1 | 乐观锁版本 |

> **解绑语义**：解绑走**软删除**（`deleted_at` 置位，留痕），复合唯一含 `deleted_at` 使解绑后可重新绑定；`version` 由 `BaseModel` 提供（乐观锁）。
>
> **主要项语义（2026-10-09）**：同用户**至多一个**主要岗位（可为空）；**唯一性由服务侧在同一写事务内保证**（置位时先清该用户既有主要项再置位），**不使用部分唯一索引**（四库方言差异）；置位目标必须已在该用户分配集合内；解除该条分配时同事务清空主要项标记。主要岗位**不参与**「按用户解析角色」的岗位链（解析按全部已分配岗位）。

## 3. 索引与约束 <a id="index"></a>

| 名称 | 类型 | 列 | 说明 |
| --- | --- | --- | --- |
| `uq_org_user_post_user_post_deleted_at` | 唯一 | `(user_id, post_id, deleted_at)` | 多对多防重（软删除后可重绑） |
| `idx_org_user_post_post_id` | 普通 | `post_id` | 岗位下用户反查（`user_id` 为唯一索引先导列，不再单列） |

- 无物理外键；`user_id` 指向 bms `sys_user.id`（**跨服务逻辑外键**），`post_id` 指向 `org_post.id`（同库）。
- **用户删除补偿**：bms 用户删除经 `sys.user.deleted` 事件驱动本域清理其关联行（不跨库强约束）。

## 4. 分片 / 归档 / 迁移 <a id="storage"></a>

- **分片**：不分片（关联关系随主数据常驻）。
- **归档**：不归档。
- **迁移**：随 **`org:tenant` 链**迁移落地（实现在任务 `01_02`）。

## 5. 变更记录 <a id="revlog"></a>

| 日期 | 版本 | 变更 | 作者 |
| --- | --- | --- | --- |
| 2026-10-07 | v1 | 新建表结构（mdm 组织域，原 bms `sys_user_post` 迁入） | minjian |
| 2026-10-07 | v2 | 主键口径修订：联合主键 → 雪花 `id` 主键 + `(user_id, post_id, deleted_at)` 复合唯一；补软删除与 `version`（对齐基座 `BaseModel` 与 bms 现役实现） | minjian |
| 2026-10-09 | v3 | 增 `is_primary` 主要岗位标记（同用户至多一个，服务侧事务保证；跨仓来源 bms 阶段七需求 `07-11`）；补主要项语义说明；**不新增索引**（查询走 `user_id` 先导的唯一索引） | minjian |

> 数据表设计 · 与 bms《数据库开发规范》「数据表文件规范」节配套
