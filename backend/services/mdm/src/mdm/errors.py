"""组织域错误码与异常（mdm 段位 `33xxxx`；文案由前端按 `error.{code}` 映射）。

错误码与《[mdm 英文简称规范](../../../../mdm文档/规范/英文简称规范.md)》《01_详细设计_02_组织主数据域实现.md》§8 一致；
统一并发冲突沿用基座 `ConcurrentConflictError`（不重复定义）。
"""

from enum import IntEnum
from typing import ClassVar

from bms_core.core.exceptions import BizError


class MdmErrorCode(IntEnum):
    """组织域错误码（段位 `33xxxx`）。"""

    POST_NOT_FOUND = 330031
    """"岗位不存在。"""

    POST_CODE_EXISTS = 330032
    """岗位 code 已存在。"""

    POST_DEPT_UNAVAILABLE = 330033
    """归属部门不存在或已停用。"""

    POST_HAS_USERS = 330034
    """岗位仍关联用户，禁止删除。"""

    POST_HAS_ROLES = 330035
    """岗位仍绑定角色，禁止删除。"""

    POST_CODE_FORMAT = 330036
    """岗位 code 不符合格式约束。"""

    DEPT_NOT_FOUND = 330051
    """部门不存在。"""

    DEPT_PARENT_UNAVAILABLE = 330052
    """父部门不存在或已停用。"""

    DEPT_CYCLE = 330053
    """移动形成环：父部门不能是自身或其后代。"""

    DEPT_HAS_CHILDREN = 330054
    """部门仍存在子部门，禁止删除。"""

    DEPT_REFERENCED = 330055
    """部门仍被岗位 / 用户引用，禁止删除。"""

    DEPT_HAS_ROLES = 330056
    """部门仍存在角色分配，禁止删除。"""

    DEPT_DEPTH_EXCEEDED = 330057
    """部门树深度超出上限。"""

    DEPT_CHILDREN_LIMIT = 330058
    """同级子部门数超出上限。"""

    DEPT_NAME_EXISTS = 330059
    """同父部门名称已存在。"""

    DEPT_CODE_EXISTS = 330060
    """部门编码已存在（租户内唯一）。"""

    DEPT_CODE_FORMAT = 330061
    """部门编码不符合格式约束。"""

    USER_POST_NOT_FOUND = 330071
    """用户-岗位关联不存在。"""

    USER_POST_LIMIT_EXCEEDED = 330072
    """单用户岗位数超出上限。"""

    ROLE_POST_NOT_FOUND = 330081
    """角色-岗位分配不存在。"""

    ROLE_DEPT_NOT_FOUND = 330091
    """角色-部门分配不存在。"""

    MDM_SOURCE_UNAVAILABLE = 330101
    """用户来源不可达 / 未装配（组织只读出口的用户维度取数通道）。"""

    USER_DEPT_NOT_FOUND = 330111
    """用户-部门关联不存在。"""

    USER_DEPT_LIMIT_EXCEEDED = 330112
    """单用户部门数超出上限。"""

    USER_PRIMARY_NOT_ASSIGNED = 330113
    """主要项置位目标不在该用户已分配集合内。"""


class MdmError(BizError):
    """组织域异常基类（段位基；子类预置码位与 HTTP 状态）。"""

    code_: ClassVar[int]
    """错误码（子类预置）。"""

    http_status_: ClassVar[int] = 200
    """HTTP 状态（默认业务失败 200；不存在类取 404）。"""

    def __init__(self, message: str | None = None, *, data: object | None = None) -> None:
        """初始化组织域异常。

        Args:
            message: 提示信息（缺省由前端按 i18n 键映射）。
            data: 随附数据（可选）。
        """
        super().__init__(type(self).code_, message, http_status=type(self).http_status_, data=data)


class MdmPostNotFoundError(MdmError):
    """岗位不存在（330031）。"""

    code_: ClassVar[int] = MdmErrorCode.POST_NOT_FOUND
    http_status_: ClassVar[int] = 404


class MdmPostCodeExistsError(MdmError):
    """岗位 code 已存在（330032）。"""

    code_: ClassVar[int] = MdmErrorCode.POST_CODE_EXISTS


class MdmPostDeptUnavailableError(MdmError):
    """归属部门不存在或已停用（330033）。"""

    code_: ClassVar[int] = MdmErrorCode.POST_DEPT_UNAVAILABLE


class MdmPostHasUsersError(MdmError):
    """岗位仍关联用户，禁止删除（330034）。"""

    code_: ClassVar[int] = MdmErrorCode.POST_HAS_USERS


class MdmPostHasRolesError(MdmError):
    """岗位仍绑定角色，禁止删除（330035）。"""

    code_: ClassVar[int] = MdmErrorCode.POST_HAS_ROLES


class MdmPostCodeFormatError(MdmError):
    """岗位 code 不符合格式约束（330036）。"""

    code_: ClassVar[int] = MdmErrorCode.POST_CODE_FORMAT


class MdmDeptNotFoundError(MdmError):
    """部门不存在（330051）。"""

    code_: ClassVar[int] = MdmErrorCode.DEPT_NOT_FOUND
    http_status_: ClassVar[int] = 404


class MdmDeptParentUnavailableError(MdmError):
    """父部门不存在或已停用（330052）。"""

    code_: ClassVar[int] = MdmErrorCode.DEPT_PARENT_UNAVAILABLE


class MdmDeptCycleError(MdmError):
    """移动形成环（330053）。"""

    code_: ClassVar[int] = MdmErrorCode.DEPT_CYCLE


class MdmDeptHasChildrenError(MdmError):
    """部门仍存在子部门，禁止删除（330054）。"""

    code_: ClassVar[int] = MdmErrorCode.DEPT_HAS_CHILDREN


class MdmDeptReferencedError(MdmError):
    """部门仍被岗位 / 用户引用，禁止删除（330055）。"""

    code_: ClassVar[int] = MdmErrorCode.DEPT_REFERENCED


class MdmDeptHasRolesError(MdmError):
    """部门仍存在角色分配，禁止删除（330056）。"""

    code_: ClassVar[int] = MdmErrorCode.DEPT_HAS_ROLES


class MdmDeptDepthExceededError(MdmError):
    """部门树深度超出上限（330057）。"""

    code_: ClassVar[int] = MdmErrorCode.DEPT_DEPTH_EXCEEDED


class MdmDeptChildrenLimitError(MdmError):
    """同级子部门数超出上限（330058）。"""

    code_: ClassVar[int] = MdmErrorCode.DEPT_CHILDREN_LIMIT


class MdmDeptNameExistsError(MdmError):
    """同父部门名称已存在（330059）。"""

    code_: ClassVar[int] = MdmErrorCode.DEPT_NAME_EXISTS


class MdmDeptCodeExistsError(MdmError):
    """部门编码已存在（330060，租户内唯一）。"""

    code_: ClassVar[int] = MdmErrorCode.DEPT_CODE_EXISTS


class MdmDeptCodeFormatError(MdmError):
    """部门编码不符合格式约束（330061）。"""

    code_: ClassVar[int] = MdmErrorCode.DEPT_CODE_FORMAT


class MdmUserPostNotFoundError(MdmError):
    """用户-岗位关联不存在（330071）。"""

    code_: ClassVar[int] = MdmErrorCode.USER_POST_NOT_FOUND
    http_status_: ClassVar[int] = 404


class MdmUserPostLimitExceededError(MdmError):
    """单用户岗位数超出上限（330072）。"""

    code_: ClassVar[int] = MdmErrorCode.USER_POST_LIMIT_EXCEEDED


class MdmRolePostNotFoundError(MdmError):
    """角色-岗位分配不存在（330081）。"""

    code_: ClassVar[int] = MdmErrorCode.ROLE_POST_NOT_FOUND
    http_status_: ClassVar[int] = 404


class MdmRoleDeptNotFoundError(MdmError):
    """角色-部门分配不存在（330091）。"""

    code_: ClassVar[int] = MdmErrorCode.ROLE_DEPT_NOT_FOUND
    http_status_: ClassVar[int] = 404


class MdmSourceUnavailableError(MdmError):
    """用户来源不可达 / 未装配（330101；用户维度出口明确降级，不静默返回旧值）。"""

    code_: ClassVar[int] = MdmErrorCode.MDM_SOURCE_UNAVAILABLE


class MdmUserDeptNotFoundError(MdmError):
    """用户-部门关联不存在（330111）。"""

    code_: ClassVar[int] = MdmErrorCode.USER_DEPT_NOT_FOUND
    http_status_: ClassVar[int] = 404


class MdmUserDeptLimitExceededError(MdmError):
    """单用户部门数超出上限（330112）。"""

    code_: ClassVar[int] = MdmErrorCode.USER_DEPT_LIMIT_EXCEEDED


class MdmUserPrimaryNotAssignedError(MdmError):
    """主要项置位目标不在该用户已分配集合内（330113）。"""

    code_: ClassVar[int] = MdmErrorCode.USER_PRIMARY_NOT_ASSIGNED
