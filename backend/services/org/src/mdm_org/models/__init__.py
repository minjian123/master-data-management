"""组织主数据服务模型包。

`MODEL_MODULES` 是服务包自声明的模型模块清单（基座迁移链据此注册 `Base.metadata`）；
包名前缀经 `[app].package_prefix = "mdm"` → 基座按 `mdm_org.models` 解析（bms 12_04）。
"""

MODEL_MODULES: tuple[str, ...] = (
    "mdm_org.models.dept",
    "mdm_org.models.post",
    "mdm_org.models.user_post",
    "mdm_org.models.user_dept",
    "mdm_org.models.role_post",
    "mdm_org.models.role_dept",
)
