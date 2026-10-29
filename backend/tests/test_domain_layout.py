"""域布局生成物（07B `04_02` 重开）：清单第九类 `[[domains]]` 渲染与漂移比对。

口径：`domain_layout.json` 是**生成物**（清单是唯一来源）——本用例既守「渲染结果与仓库内生成物一致」
（手改生成物 / 改清单未重渲染即红），也守渲染器的去重与字段省略规则。
"""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from ops import check_modules

_LAYOUT = Path("deploy/boundaries/domain_layout.json")


def _manifest(domains: list[Any], shared: list[str]) -> Any:
    """构造装载结果替身（渲染器只读 `domains` 与 `domain_shared_paths` 两个属性）。

    Args:
        domains: 域条目列表。
        shared: 域外共享路径列表。

    Returns:
        Any: 清单替身。
    """
    return SimpleNamespace(domains=domains, domain_shared_paths=shared)


def _entry(domain_key: str, *, name: str = "", service_key: str = "mdm") -> Any:
    """构造域条目替身（渲染器只读五个字段 + 可选 `name`）。

    Args:
        domain_key: 域键。
        name: 域中文名（空串表示不输出该字段）。
        service_key: 承载服务键。

    Returns:
        Any: 域条目替身。
    """
    return SimpleNamespace(
        domain_key=domain_key,
        name=name,
        service_key=service_key,
        status="placement",
        paths=["backend/services/org/src/mdm/org/"],
        public_api=["mdm.org"],
    )


def test_render_matches_committed_layout() -> None:
    """渲染结果与仓库内生成物逐字段一致（清单为唯一来源，生成物不得手改）。"""
    document = check_modules.render_domain_layout()
    committed = json.loads((check_modules._REPO_ROOT / _LAYOUT).read_text(encoding="utf-8"))

    assert document == committed
    assert document["version"] == 1
    assert any(item["domain_key"] == "org" and item["service_key"] == "mdm" for item in document["domains"])


def test_render_dedupes_and_omits_empty_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """多仓同名域 / 同名域外路径只取首次；无 `name` 的域不输出该字段。

    Args:
        monkeypatch: pytest monkeypatch 夹具。
    """
    manifests = [
        _manifest([_entry("org", name="组织主数据")], ["bms文档/"]),
        _manifest([_entry("org", service_key="other"), _entry("user")], ["bms文档/", "engkit文档/"]),
    ]
    monkeypatch.setattr("bms_core.registry.products.load_product_manifests", lambda paths: manifests)

    document = check_modules.render_domain_layout()

    assert [item["domain_key"] for item in document["domains"]] == ["org", "user"]
    assert document["domains"][0]["name"] == "组织主数据"
    assert "name" not in document["domains"][1]
    assert document["domains"][0]["service_key"] == "mdm"
    assert document["shared_paths"] == ["bms文档/", "engkit文档/"]


def test_cli_render_check_and_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI：渲染 → 一致 → 漂移 / 非法 JSON / 缺失 四种结果（退出码 0 / 1）。

    Args:
        tmp_path: 临时目录（充当仓根）。
        monkeypatch: pytest monkeypatch 夹具。
    """
    monkeypatch.setattr(check_modules, "_REPO_ROOT", tmp_path)
    target = tmp_path / _LAYOUT

    assert check_modules.main(["--check-domain-layout"]) == 1  # 生成物缺失
    assert check_modules.main(["--render-domain-layout"]) == 0
    assert target.is_file()
    assert check_modules.main(["--check-domain-layout"]) == 0

    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["domains"] = []
    target.write_text(json.dumps(payload), encoding="utf-8")
    assert check_modules.main(["--check-domain-layout"]) == 1  # 与清单不一致

    target.write_text("{", encoding="utf-8")
    assert check_modules.main(["--check-domain-layout"]) == 1  # 生成物 JSON 非法
