"""mdm 默认数据种子包（产品自持声明 `[[seeds]]` 的入口实现；07B `02_01`）。

对外暴露 `seed_admin_codes`（平台种子编排按清单声明的 `module` + `entry` 加载，装载期校验可解析）。
"""

from mdm.seeds.permissions import seed_admin_codes

__all__ = ["seed_admin_codes"]
