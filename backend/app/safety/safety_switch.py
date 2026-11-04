# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-20 小欧 - 新建: 安全配置项唯一读取口。各配置项互相独立, 不做总闸折叠 ——
#   总闸 security.system.enabled 由安全模块入口单独短路判定(见 path_tool_safety_checker)。
#   缺键一律按"开"处理(fail-closed): 缺配置不放松安全等级。
#   无状态, 每次调用即时求值; get_config() 内有 mtime 缓存, 改配置下次调用即生效。
"""
safety_switch · 安全配置项读取(唯一口)

小欧 2026-10-20
"""

from app.config import get_config

#: 总闸键: 由安全模块入口读取并短路, 不在本模块折叠
MASTER_KEY = "security.system.enabled"


def safety_enabled() -> bool:
    """安全模块总闸是否开启(入口短路用)"""
    return bool(get_config().get(MASTER_KEY, True))


def safety_switch(key: str, default: bool = True) -> bool:
    """读取一个安全配置项(独立求值, 不含总闸)

    Args:
        key: 配置键, 如 "security.hitl.delete_confirm"
        default: 缺键时的取值, 默认 True(缺配置不放松安全)
    Returns:
        True = 开启(生效); False = 关闭(该项不生效)
    """
    return bool(get_config().get(key, default))


__all__ = ["MASTER_KEY", "safety_enabled", "safety_switch"]
