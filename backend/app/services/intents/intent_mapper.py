"""
统一意图映射模块

责任：意图字符串→IntentType/ToolCategory 的运行时映射
数据定义已全部移至 app.services.tools.tool_types（OCP 单一定义源）
本模块仅保留 INTENT_ALIASES（用户输入别名）和映射函数
"""

from typing import Dict, List, Tuple
from app.services.tools.tool_types import ToolCategory, IntentType, INTENT_MAPPING


# 意图别名映射（小写，用于用户输入匹配）
INTENT_ALIASES: Dict[str, IntentType] = {
    # FILE
    "file": IntentType.FILE,
    "files": IntentType.FILE,
    "文件": IntentType.FILE,
    "目录": IntentType.FILE,
    "文件夹": IntentType.FILE,

    # SYSTEM (合并的意图)
    "system": IntentType.SYSTEM,
    "shell": IntentType.SYSTEM,
    "cmd": IntentType.SYSTEM,
    "命令": IntentType.SYSTEM,
    "终端": IntentType.SYSTEM,
    "time": IntentType.SYSTEM,
    "时间": IntentType.SYSTEM,
    "日期": IntentType.SYSTEM,
    "meta": IntentType.SYSTEM,
    "environment": IntentType.SYSTEM,
    "env": IntentType.SYSTEM,
    "环境": IntentType.SYSTEM,
    "code_execution": IntentType.SYSTEM,
    "code": IntentType.SYSTEM,
    "代码": IntentType.SYSTEM,
    "编译": IntentType.SYSTEM,
    "执行": IntentType.SYSTEM,

    # NETWORK
    "network": IntentType.NETWORK,
    "net": IntentType.NETWORK,
    "网络": IntentType.NETWORK,
    "通信": IntentType.NETWORK,

    # DOCUMENT
    "document": IntentType.DOCUMENT,
    "doc": IntentType.DOCUMENT,
    "文档": IntentType.DOCUMENT,
    "database": IntentType.DOCUMENT,
    "db": IntentType.DOCUMENT,
    "数据": IntentType.DOCUMENT,
    "数据库": IntentType.DOCUMENT,

    # DESKTOP
    "desktop": IntentType.DESKTOP,
    "ui": IntentType.DESKTOP,
    "gui": IntentType.DESKTOP,
    "界面": IntentType.DESKTOP,
    "桌面": IntentType.DESKTOP,
    "截图": IntentType.DESKTOP,
    "录屏": IntentType.DESKTOP,
}


def _map_intent_to_agent(intent_str: str) -> Tuple[IntentType, ToolCategory]:
    """
    将意图字符串映射到统一的意图类型和工具分类

    Args:
        intent_str: 意图字符串（来自CRSS或用户输入）

    Returns:
        (intent_type, tool_category) 元组，ToolCategory由IntentType.category派生

    Raises:
        ValueError: 如果意图无法识别
    """
    # 首先尝试精确匹配（大写，来自CRSS）
    if intent_str.upper() in INTENT_MAPPING:
        intent_type = INTENT_MAPPING[intent_str.upper()]
        return (intent_type, intent_type.category)

    # 然后尝试别名匹配（小写，来自用户输入）
    intent_lower = intent_str.lower()
    if intent_lower in INTENT_ALIASES:
        intent_type = INTENT_ALIASES[intent_lower]
        return (intent_type, intent_type.category)

    # 如果都无法匹配，默认为SYSTEM
    return (IntentType.SYSTEM, ToolCategory.SYSTEM)


def get_crss_intent_names() -> List[str]:
    """获取CRSS使用的意图名称列表（大写）"""
    return list(INTENT_MAPPING.keys())


def get_agent_intent_names() -> List[str]:
    """获取Agent配置使用的意图名称列表（小写）"""
    return [intent_type.value for intent_type in IntentType]


def resolve_category(intent_str: str) -> ToolCategory:
    """
    解析意图字符串到ToolCategory（兼容现有接口）

    Args:
        intent_str: 意图字符串

    Returns:
        ToolCategory枚举值
    """
    _, tool_category = _map_intent_to_agent(intent_str)
    return tool_category


def get_aliases_for_intent(intent_type: IntentType) -> List[str]:
    """获取指定意图类型的所有别名"""
    aliases = []
    for alias, mapped_type in INTENT_ALIASES.items():
        if mapped_type == intent_type:
            aliases.append(alias)
    return aliases


def normalize_intent(intent_str: str) -> str:
    """规范化意图字符串（转换为标准的意图类型字符串）"""
    intent_type, _ = _map_intent_to_agent(intent_str)
    return intent_type.value
