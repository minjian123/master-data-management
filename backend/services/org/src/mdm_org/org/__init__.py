"""组织主数据查询能力域（mdm 组织域自持）：组织数据源 / 名称回显 / 用户来源三端口。

- 端口契约与数据契约见 `base.py`（自 bms `bms_core/org` 迁入，形态与语义保持一致）；
- 真实取数实现见 `default.py`（承接本域仓储 + 用户来源端口）；
- 用户来源实现见 `user_source.py`（经服务间调用 bms platform 用户只读出口，**不跨库读** `sys_user`）。

装配口径：端口契约保留基座 `BasePluggable` 形态，但**经 mdm 本地装配注入**出口路由
（不依赖平台 `PLUGIN_WIRINGS`——bms 组织服务退役后平台侧不再有本域接线）。
"""

from mdm_org.org.base import (
    DEFAULT_ORG_PAGE_SIZE,
    ORG_STATUSES,
    ORG_TARGETS,
    BaseOrgDataSource,
    BaseOrgNameResolver,
    BaseOrgUserSource,
    OrgDept,
    OrgNameRef,
    OrgPost,
    OrgUser,
)

__all__ = [
    "DEFAULT_ORG_PAGE_SIZE",
    "ORG_STATUSES",
    "ORG_TARGETS",
    "BaseOrgDataSource",
    "BaseOrgNameResolver",
    "BaseOrgUserSource",
    "OrgDept",
    "OrgNameRef",
    "OrgPost",
    "OrgUser",
]
