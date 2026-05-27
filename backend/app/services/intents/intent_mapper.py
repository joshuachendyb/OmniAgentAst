"""
统一意图映射模块

责任：统一所有意图定义和映射，消除2套+3表的重复定义
设计原则：单一职责、单一入口、集中管理

目前存在的意图定义分散问题：
1. crss_scorer.py: TYPE_CATEGORY_MAP (意图类型 → ToolCategory)
2. agent_config.py: AGENT_REGISTRY (意图类型 → AgentConfig，包含别名)
3. ToolCategory枚举: 工具分类定义
4. 多个地方的硬编码映射

本模块将所有映射统一到一处，提供单一入口函数。
"""

from enum import Enum
from typing import Dict, List, Optional, Tuple
from app.services.tools.registry import ToolCategory


class IntentType(str, Enum):
    """统一的意图类型枚举"""
    FILE = "file"
    SYSTEM = "system"  # 包含shell, time, meta, environment, code_execution
    NETWORK = "network"
    DOCUMENT = "document"  # 包含database
    DESKTOP = "desktop"


# 统一意图映射表：CRSS意图 → 统一意图类型 → ToolCategory
INTENT_MAPPING: Dict[str, Tuple[IntentType, ToolCategory]] = {
    # FILE相关
    "FILE": (IntentType.FILE, ToolCategory.FILE),
    
    # SYSTEM相关（合并多个子类型）
    "SHELL": (IntentType.SYSTEM, ToolCategory.SYSTEM),
    "TIME": (IntentType.SYSTEM, ToolCategory.SYSTEM),
    "ENV": (IntentType.SYSTEM, ToolCategory.SYSTEM),
    "ENVIRONMENT": (IntentType.SYSTEM, ToolCategory.SYSTEM),
    "SYSTEM": (IntentType.SYSTEM, ToolCategory.SYSTEM),
    "CODE_EXECUTION": (IntentType.SYSTEM, ToolCategory.SYSTEM),
    "META": (IntentType.SYSTEM, ToolCategory.SYSTEM),
    
    # NETWORK相关
    "NETWORK": (IntentType.NETWORK, ToolCategory.NETWORK),
    
    # DOCUMENT相关
    "DOCUMENT": (IntentType.DOCUMENT, ToolCategory.DOCUMENT),
    "DATABASE": (IntentType.DOCUMENT, ToolCategory.DOCUMENT),
    
    # DESKTOP相关
    "DESKTOP": (IntentType.DESKTOP, ToolCategory.DESKTOP),
}


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


def map_intent_to_agent(intent_str: str) -> Tuple[IntentType, ToolCategory]:
    """
    将意图字符串映射到统一的意图类型和工具分类
    
    Args:
        intent_str: 意图字符串（来自CRSS或用户输入）
        
    Returns:
        (intent_type, tool_category) 元组
        
    Raises:
        ValueError: 如果意图无法识别
    """
    # 首先尝试精确匹配（大写，来自CRSS）
    if intent_str.upper() in INTENT_MAPPING:
        return INTENT_MAPPING[intent_str.upper()]
    
    # 然后尝试别名匹配（小写，来自用户输入）
    intent_lower = intent_str.lower()
    if intent_lower in INTENT_ALIASES:
        intent_type = INTENT_ALIASES[intent_lower]
        # 查找对应的ToolCategory
        for crss_intent, (mapped_type, tool_cat) in INTENT_MAPPING.items():
            if mapped_type == intent_type:
                return (intent_type, tool_cat)
    
    # 如果都无法匹配，默认为SYSTEM
    return (IntentType.SYSTEM, ToolCategory.SYSTEM)


def get_all_intent_types() -> List[str]:
    """获取所有支持的意图类型列表（用于CRSS等需要完整列表的地方）"""
    return list(set(intent_type.value for _, (intent_type, _) in INTENT_MAPPING.items()))


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
    _, tool_category = map_intent_to_agent(intent_str)
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
    intent_type, _ = map_intent_to_agent(intent_str)
    return intent_type.value


CRSS_TYPE_KEYWORDS: Dict[str, Dict] = {
    "FILE": {
        "keywords": [r'\bls\b', r'\bdir\b', r'\bcd\b', r'\bpwd\b',
                     r'\bcat\b', r'\bgrep\b', r'\bfind\b', r'\btree\b',
                     r'\bcp\b', r'\bmv\b', r'\brm\b', r'\bmkdir\b', r'\btouch\b'],
        "chinese_keywords": ['文件', '目录', '文件夹', '路径', '磁盘', 'C盘', 'D盘', 'E盘']
    },
    "SHELL": {
        "keywords": [r'\bnpm\b', r'\bpip\b', r'\bnode\b', r'\bgcc\b', r'\bpython\b',
                     r'\bgit\b', r'\bdocker\b', r'\bgradle\b'],
        "chinese_keywords": ['终端', '命令', '脚本']
    },
    "TIME": {
        "keywords": [r'\bdate\b', r'\btime\b', r'\bnow\b', r'\bclock\b',
                     r'\bcalendar\b', r'\bschedule\b'],
        "chinese_keywords": ['时间', '日期', '今天星期', '几月几号', '现在几点']
    },
    "NETWORK": {
        "keywords": [r'\bping\b', r'\bcurl\b', r'\bwget\b', r'\bssh\b',
                     r'\bhttp\b', r'\bhttps\b', r'\bftp\b', r'\bsocket\b'],
        "chinese_keywords": ['网络', '端口', '下载', '请求', 'API',
                             'IP', 'IP地址', 'DNS', '公网IP', '网关', 'WIFI', 'WiFi']
    },
    "DESKTOP": {
        "keywords": [r'\bscreenshot\b', r'\bcapture\b',
                     r'\bclick\b', r'\btype\b', r'\bpress\b', r'\bkey\b'],
        "chinese_keywords": ['截图', '录屏', '点击', '按键', '键盘', '鼠标', '窗口', '桌面', '浏览器']
    },
    "ENV": {
        "keywords": [r'\bPATH\b', r'\bHOME\b', r'\bTEMP\b'],
        "chinese_keywords": ['环境变量', '系统变量']
    },
    "ENVIRONMENT": {
        "keywords": [r'\benvironment\b', r'\benv\b'],
        "chinese_keywords": ['环境', '环境变量']
    },
    "SYSTEM": {
        "keywords": [r'\bcpu\b', r'\bmemory\b', r'\bram\b', r'\bdisk\b',
                     r'\bprocess\b', r'\bservice\b'],
        "chinese_keywords": ['系统信息', 'CPU', '内存', '进程', '服务', '磁盘']
    },
    "META": {
        "keywords": [r'\bversion\b', r'\bconfig\b', r'\binfo\b'],
        "chinese_keywords": ['版本', '配置', '信息', '状态']
    },
    "DATABASE": {
        "keywords": [r'\bsql\b', r'\bdb\b', r'\bdatabase\b',
                     r'\bselect\b', r'\binsert\b', r'\bupdate\b', r'\bdelete\b'],
        "chinese_keywords": ['数据库', '表', '数据', 'SQL']
    },
    "DOCUMENT": {
        "keywords": [r'\bdocx\b', r'\bpdf\b', r'\btxt\b', r'\bmd\b', r'\bcsv\b', r'\bjson\b'],
        "chinese_keywords": ['文档', '报告', '笔记', '文本', '文章']
    },
    "CODE_EXECUTION": {
        "keywords": [r'\bcompile\b', r'\bg\+\+\b'],
        "chinese_keywords": ['编译', '执行程序']
    },
}