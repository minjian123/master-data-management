"""组织主数据服务模型包。

`MODEL_MODULES` 是服务包自声明的模型模块清单（基座迁移链据此注册 `Base.metadata`）；
包名前缀经 `[app].package_prefix = "mdm"` → 基座按 `mdm.models` 解析（bms 12_04）。
"""

MODEL_MODULES: tuple[str, ...] = (
    "mdm.models.dept",
    "mdm.models.post",
    "mdm.models.user_post",
    "mdm.models.user_dept",
    "mdm.models.role_post",
    "mdm.models.role_dept",
)
