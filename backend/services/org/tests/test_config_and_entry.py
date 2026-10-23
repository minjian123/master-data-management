"""服务配置读取与启动入口用例：非法参数值回落默认、`python -m mdm` 入口可启动。"""

import importlib
import runpy
import sys

import pytest
from bms_core.core.concurrent import ConcurrentStableDict
from bms_core.core.config import get_settings

from mdm import config as org_config
from tests_support import org_env

_INT_KEY = "mdm.dept_tree_max_depth"
"""整型参数键（读不到 / 非法时回落代码默认值）。"""

_STR_KEY = "mdm.dept_code_pattern"
"""字符串参数键（读不到时回落默认值）。"""


@pytest.mark.kiwi_id(2255)
async def test_read_int_falls_back_on_invalid_value() -> None:
    """系统参数：合法整数直取；为空 / 非整数回落默认值（不因配置写错而拒绝服务）。"""
    assert await org_config.read_int(org_env.ConfigStub(ConcurrentStableDict({_INT_KEY: "9"})), _INT_KEY, 5) == 9
    invalid = org_env.ConfigStub(ConcurrentStableDict({_INT_KEY: "not-a-number"}))
    assert await org_config.read_int(invalid, _INT_KEY, 5) == 5
    empty = org_env.ConfigStub(ConcurrentStableDict())
    assert await org_config.read_int(empty, _INT_KEY, 7) == 7
    assert await org_config.read_str(empty, _STR_KEY, "fallback") == "fallback"
    assert (
        await org_config.read_str(org_env.ConfigStub(ConcurrentStableDict({_STR_KEY: "abc"})), _STR_KEY, "x") == "abc"
    )


@pytest.mark.kiwi_id(2255)
def test_module_entry_point_runs_service(monkeypatch: pytest.MonkeyPatch) -> None:
    """`python -m mdm`：入口以 `ApplicationFactory` 调基座 `run_service`（替身记录调用）。"""
    import bms_core.core.run as run_module

    calls: list[object] = []

    def _record(factory: object) -> None:
        calls.append(factory)

    monkeypatch.setattr(run_module, "run_service", _record)
    monkeypatch.delitem(sys.modules, "mdm.__main__", raising=False)
    runpy.run_module("mdm.__main__", run_name="__main__")
    importlib.import_module("mdm.__main__")  # 以模块名导入：覆盖「非 __main__」分支
    assert calls, "服务入口未调用 run_service"
    assert get_settings() is not None
