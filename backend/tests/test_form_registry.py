"""产品 `form_key` 清单（Kiwi 2340）：跨表全局唯一 / `data_source_key` 同名闭合 / 模型双向一致 / 注入应用级视图。"""

import runpy
import sys

import pytest
from bms_core.core.concurrent import ConcurrentStableList
from bms_core.registry.forms import FormRecord, FormRegistry, merge_form_records
from fastapi import FastAPI
from sqlalchemy import BigInteger, Column, MetaData, String, Table, UniqueConstraint

import ops.check_forms as check_forms
from mdm_org.main import ApplicationFactory
from ops.check_forms import diff_models, diff_records, load_models
from services.form_registry import MDM_FORM_RECORDS, form_keys, form_record, form_records


@pytest.mark.kiwi_id(2340)
def test_records_registered_with_same_name_closure() -> None:
    """清单：`org_dept` / `org_post` 两条、字典类型、启用态、`data_source_key` 同名闭合、跨表唯一。"""
    assert form_keys() == ("org_dept", "org_post")
    assert form_records() == ConcurrentStableList(MDM_FORM_RECORDS)
    for record in MDM_FORM_RECORDS:
        assert record.kind == "dict"
        assert record.status == "enabled"
        assert record.data_source_key == record.form_key
    assert form_record("org_dept") is MDM_FORM_RECORDS[0]
    assert form_record("org_user_post") is None
    assert diff_records(MDM_FORM_RECORDS) == []


@pytest.mark.kiwi_id(2340)
def test_duplicate_or_mismatched_records_rejected() -> None:
    """反例：`form_key` 重复 / 表名重复 / `data_source_key` 未同名闭合 → 校验逐项报错。"""
    duplicated = (
        FormRecord(form_key="org_dept", table="org_dept", name="部门", data_source_key="org_dept"),
        FormRecord(form_key="org_dept", table="org_post", name="岗位", data_source_key="org_dept"),
    )
    issues = diff_records(duplicated)
    assert any("form_key 跨表重复" in issue for issue in issues)

    drifted = (FormRecord(form_key="org_dept", table="org_dept", name="部门", data_source_key="dept"),)
    issues = diff_records(drifted)
    assert any("data_source_key 未同名闭合" in issue for issue in issues)


@pytest.mark.kiwi_id(2340)
def test_models_match_records_bidirectionally() -> None:
    """模型 ↔ 清单双向一致：列 / 缺省值 / 复合唯一齐备，且无「有列未登记」的表；关联表未落字段。"""
    metadata = load_models()
    assert diff_models(MDM_FORM_RECORDS, metadata) == []
    assert {"org_dept", "org_post"} <= set(metadata.tables)


@pytest.mark.kiwi_id(2340)
def test_factory_hook_returns_product_records() -> None:
    """应用工厂钩子 `form_records()` 返回产品清单（基座据此拼应用级视图）。"""
    assert ApplicationFactory().form_records() == ConcurrentStableList(MDM_FORM_RECORDS)
    merged = merge_form_records(injected=ConcurrentStableList(MDM_FORM_RECORDS))
    assert FormRegistry(merged).get("org_post") == MDM_FORM_RECORDS[1]


@pytest.mark.kiwi_id(2340)
async def test_application_view_contains_product_records(service_app: FastAPI) -> None:
    """装配：`app.state.form_registry` 为「平台清单 + 注入记录」视图，含 `org_dept` / `org_post`。"""
    registry = service_app.state.form_registry
    assert isinstance(registry, FormRegistry)
    assert registry.get("org_dept") == MDM_FORM_RECORDS[0]
    assert registry.get("org_post") == MDM_FORM_RECORDS[1]
    assert service_app.state.form_injected_records == ConcurrentStableList(MDM_FORM_RECORDS)


def _define_table(
    metadata: MetaData,
    name: str,
    *,
    form_key: str | None = "org_dept",
    nullable: bool = False,
    with_unique: bool = True,
    with_parent_id: bool = True,
) -> Table:
    """构造探针表（校验脚本反例用）。

    Args:
        metadata: 目标元数据。
        name: 物理表名。
        form_key: `form_key` 列缺省值（None 表示不建该列）。
        nullable: `form_key` 列是否可空。
        with_unique: 是否建 `(form_key, deleted_at)` 复合唯一。
        with_parent_id: 是否建 `parent_id` 列。

    Returns:
        Table: 已注册到元数据的表。
    """
    columns = [Column("id", BigInteger, primary_key=True), Column("deleted_at", String(32))]
    if form_key is not None:
        columns.append(Column("form_key", String(64), nullable=nullable, default=form_key))
    if with_parent_id:
        columns.append(Column("parent_id", BigInteger, nullable=True))
    constraints = []
    if with_unique and form_key is not None:
        constraints.append(UniqueConstraint("form_key", "deleted_at", name=f"uq_{name}_form_key_deleted_at"))
    return Table(name, metadata, *columns, *constraints)


@pytest.mark.kiwi_id(2340)
def test_empty_and_malformed_records_reported() -> None:
    """反例：空清单 / `form_key` 与表名格式非法 / 名称与数据源标识缺失 → 逐项报错。"""
    assert diff_records(()) == ["清单为空：MDM_FORM_RECORDS 未登记任何表单标识"]

    issues = diff_records((FormRecord(form_key="Bad-Key", table="1bad", name="", data_source_key=""),))
    for fragment in ("form_key 格式非法", "表名格式非法", "名称缺失", "data_source_key 缺失"):
        assert any(fragment in issue for issue in issues), fragment

    repeated = (
        FormRecord(form_key="org_dept", table="org_dept", name="部门", data_source_key="org_dept"),
        FormRecord(form_key="org_post", table="org_dept", name="岗位", data_source_key="org_post"),
    )
    assert any("表名重复登记" in issue for issue in diff_records(repeated))


@pytest.mark.kiwi_id(2340)
def test_missing_model_and_column_reported() -> None:
    """反例：清单表无模型 / 模型缺 `form_key` 列 → 报错。"""
    assert any("清单表无模型：'org_dept'" in issue for issue in diff_models((MDM_FORM_RECORDS[0],), MetaData()))
    assert check_forms.unique_columns("not_exists", MetaData()) == {}

    metadata = MetaData()
    Table("org_dept", metadata, Column("id", BigInteger, primary_key=True), Column("parent_id", BigInteger))
    assert any("模型缺 form_key 列：org_dept" in issue for issue in diff_models((MDM_FORM_RECORDS[0],), metadata))


@pytest.mark.kiwi_id(2340)
def test_nullable_default_and_unique_mismatch_reported() -> None:
    """反例：`form_key` 可空 / 缺省值与清单不符 / 缺复合唯一 → 逐项报错。"""
    metadata = MetaData()
    _define_table(metadata, "org_dept", form_key="wrong", nullable=True, with_unique=False)
    issues = diff_models((MDM_FORM_RECORDS[0],), metadata)
    assert any("模型 form_key 列可空：org_dept" in issue for issue in issues)
    assert any("模型 form_key 缺省值与清单不符：org_dept" in issue for issue in issues)
    assert any("模型缺复合唯一 uq_org_dept_form_key_deleted_at" in issue for issue in issues)


@pytest.mark.kiwi_id(2340)
def test_reverse_dict_and_association_reported() -> None:
    """反例：产品表有 `form_key` 未登记 / 字典表缺 `parent_id` / 字典表无模型 / 关联表落了系统字段。"""
    metadata = MetaData()
    _define_table(metadata, "org_user_post")
    _define_table(metadata, "org_dept", with_parent_id=False)
    issues = diff_models((MDM_FORM_RECORDS[0],), metadata)
    assert any("模型有 form_key 列但未登记清单：org_user_post" in issue for issue in issues)
    assert any("字典表缺 parent_id 列：org_dept" in issue for issue in issues)
    assert any("字典表无模型：org_post" in issue for issue in issues)
    assert any("关联表不应落 form_key：org_user_post" in issue for issue in issues)
    assert any("关联表不应落 parent_id：org_user_post" in issue for issue in issues)
    assert any("关联表无模型：org_role_dept" in issue for issue in issues)


@pytest.mark.kiwi_id(2340)
def test_check_entrypoint_ok_and_failure(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI：清单一致 → 退出码 0 并打印通过；清单为空 → 退出码 1 并打印明细。"""
    assert check_forms.check() == []
    assert check_forms.main([]) == 0
    assert "校验通过" in capsys.readouterr().out

    monkeypatch.setattr(check_forms, "MDM_FORM_RECORDS", ())
    assert check_forms.main([]) == 1
    output = capsys.readouterr().out
    assert "清单为空" in output
    assert "校验失败" in output


@pytest.mark.kiwi_id(2340)
def test_module_entrypoint_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """模块入口（`python -m ops.check_forms`）：清单一致即以退出码 0 结束。"""
    monkeypatch.setattr(sys, "argv", ["ops.check_forms"])
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("ops.check_forms", run_name="__main__")
    assert excinfo.value.code == 0
