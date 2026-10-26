"""mdm 默认数据种子入口（07B `02_01` 落位；真实播种与幂等 / 冲突语义归 `02_03`）。

断言面：清单声明的入口 `mdm.seeds.permissions:seed_admin_codes` 可导入、可调用、占位阶段无副作用
（装载期「入口可解析」校验与实际调用口径一致）。新建用例的 Kiwi 编号由 07B `05_01` 统一登记后回填。
"""

from mdm.seeds import seed_admin_codes


async def test_seed_admin_codes_is_callable_placeholder() -> None:
    """种子入口可调用且占位阶段不写库（返回 None）。"""
    assert await seed_admin_codes(None) is None
