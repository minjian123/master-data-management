"""mdm 管理面权限码种子入口（占位实现；07B `02_01` 落位、`02_03` 接通）。

- **声明与执行分离**：产品自持清单 `deploy/registry/mdm.toml` 的 `[[seeds]]` 声明
  「模块路径 + 入口名 + 依赖顺序」；平台装载期校验入口可解析（`ops.check_modules` / 装配期），
  执行由平台**统一种子编排**调度（幂等 / 冲突报错 / 失败隔离只有一套实现，红线三）。
- **本任务边界**（`02_01`）：只落**可调用入口**，不写库、不产生业务数据——真实播种内容
  （业务码 `mdm` 与 `mdm:query` / `mdm:create` / `mdm:update` / `mdm:delete` 权限码，按自然键 upsert）
  与返回结构（`SeedResult`）归 `02_03`；平台种子里的产品码移除（去产品化）归 `03_03`。
- **调用契约**：平台按 `async def seed_admin_codes(ctx: SeedContext) -> SeedResult` 调用
  （`SeedContext` / `SeedResult` 由 `02_03` 定义）；本入口签名即按该契约预留，落地时只补实现、
  不改签名，避免平台侧再改调用点。
"""


async def seed_admin_codes(ctx: object) -> None:
    """管理面业务码与权限码种子入口（占位：不写库）。

    Args:
        ctx: 种子上下文（`02_03` 定义 `SeedContext`；占位阶段不消费）。

    Returns:
        None: 占位返回；`02_03` 接通后改为返回 `SeedResult`（本签名保持不变）。
    """
    del ctx
