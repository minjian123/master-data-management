"""组织域运行期配置读取（经基座系统参数取数；缺失 / 非法回落代码默认值，不硬编码在逻辑里）。"""

from bms_core.config.base import BaseConfigSource

DEPT_TREE_MAX_DEPTH_KEY = "org.dept_tree_max_depth"
"""部门树最大深度（默认 10）。"""

DEPT_MAX_CHILDREN_KEY = "org.dept_max_children"
"""单部门直接子部门数上限（默认 500）。"""

POST_CODE_PATTERN_KEY = "org.post_code_pattern"
"""岗位码格式（正则；默认 `^[A-Za-z][A-Za-z0-9_]{0,31}$`）。"""

DEPT_CODE_PATTERN_KEY = "org.dept_code_pattern"
"""部门编码格式（正则；默认 `^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$`）。"""

POST_MAX_PER_USER_KEY = "org.post_max_per_user"
"""单用户可分配岗位数上限（默认 10）。"""

DEPT_MAX_PER_USER_KEY = "org.dept_max_per_user"
"""单用户可分配部门数上限（默认 10）。"""

DATA_SOURCE_MAX_FILTER_IDS_KEY = "org.data_source_max_filter_ids"
"""组织只读出口「部门过滤候选集」规模上限（默认 1000）。"""

USER_ROLES_CACHE_TTL_KEY = "org.user_roles_cache_ttl"
"""按用户解析角色结果缓存 TTL（秒；默认 30；≤0 表示不缓存）。"""

DEFAULT_DEPT_TREE_MAX_DEPTH = 10
DEFAULT_DEPT_MAX_CHILDREN = 500
DEFAULT_POST_CODE_PATTERN = r"^[A-Za-z][A-Za-z0-9_]{0,31}$"
DEFAULT_DEPT_CODE_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$"
DEFAULT_POST_MAX_PER_USER = 10
DEFAULT_DEPT_MAX_PER_USER = 10
DEFAULT_DATA_SOURCE_MAX_FILTER_IDS = 1000
DEFAULT_USER_ROLES_CACHE_TTL = 30


async def read_int(source: BaseConfigSource, key: str, default: int) -> int:
    """读整数型系统参数（缺失 / 不可解析回落默认值）。

    Args:
        source: 系统参数取数契约。
        key: 参数键。
        default: 默认值。

    Returns:
        int: 参数值或默认值。
    """
    raw = await source.get(key, "")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


async def read_str(source: BaseConfigSource, key: str, default: str) -> str:
    """读字符串型系统参数（缺失回落默认值）。

    Args:
        source: 系统参数取数契约。
        key: 参数键。
        default: 默认值。

    Returns:
        str: 参数值或默认值。
    """
    raw = await source.get(key, "")
    return raw or default
