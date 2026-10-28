"""组织域对外能力名（07B `03_01`）

本模块是 mdm 侧入站判定的**唯一取值源**：每条能力名与 `deploy/registry/mdm.toml` 的
`[[collaborations]]` 逐项同值（由 `tests/test_capabilities.py` 断言，防双写漂移）。

口径：

- **声明方即提供方**：mdm 清单是这些能力的声明方，故能力名写在产品源码里不构成「平台源码产品字面量」；
- **入站只按分配判定**：端点用 `require_capability(<能力名>)`，判定以本服务侧授权视图为准
  （经 platform 内部出口拉取，见 `bootstrap_remote_capability_grants`）；
- **端点与能力一一对应**：一个端点只声明一项能力，不复用「读 / 写」粗粒度能力。
"""

__all__ = [
    "CAPABILITY_MDM_USER_ROLES",
    "CAPABILITY_ORG_ROLE_DEPTS_ASSIGN",
    "CAPABILITY_ORG_ROLE_POSTS_ASSIGN",
    "CAPABILITY_ORG_USER_DEPTS_ASSIGN",
    "CAPABILITY_ORG_USER_POSTS_ASSIGN",
    "ORG_CAPABILITIES",
]

CAPABILITY_MDM_USER_ROLES = "mdm.org.user-roles"
"""按用户解析角色（只读出口；消费方 = 平台权限计算）。"""

CAPABILITY_ORG_USER_POSTS_ASSIGN = "mdm.org.user-posts.assign"
"""内部写通道：全量覆盖用户岗位 + 主要岗位（消费方 = 平台宿主编排）。"""

CAPABILITY_ORG_USER_DEPTS_ASSIGN = "mdm.org.user-depts.assign"
"""内部写通道：全量覆盖用户部门 + 主要部门（消费方 = 平台宿主编排）。"""

CAPABILITY_ORG_ROLE_POSTS_ASSIGN = "mdm.org.role-posts.assign"
"""内部写通道：全量覆盖角色岗位（消费方 = 平台宿主编排）。"""

CAPABILITY_ORG_ROLE_DEPTS_ASSIGN = "mdm.org.role-depts.assign"
"""内部写通道：全量覆盖角色部门（消费方 = 平台宿主编排）。"""

ORG_CAPABILITIES: tuple[str, ...] = (
    CAPABILITY_MDM_USER_ROLES,
    CAPABILITY_ORG_USER_POSTS_ASSIGN,
    CAPABILITY_ORG_USER_DEPTS_ASSIGN,
    CAPABILITY_ORG_ROLE_POSTS_ASSIGN,
    CAPABILITY_ORG_ROLE_DEPTS_ASSIGN,
)
"""本服务按能力授权收编的全部端点能力（与清单 `[[collaborations]]` 对齐，供同值断言使用）。"""
