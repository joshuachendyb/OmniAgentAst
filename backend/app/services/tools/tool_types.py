# -*- coding: utf-8 -*-
"""
工具类型&意图类型定义 — 单一定义源(OCP:新增分类/意图只需在此文件添加)
- ToolCategory + IntentType 枚举
- INTENT_TO_CATEGORY / CATEGORY_ORDER / CATEGORY_NAMES / INTENT_MAPPING / CRSS_TYPE_KEYWORDS 全部从此自动派生

拆分自 registry.py — 小沈 2026-05-29
OCP统一改造 — 小健 2026-05-31
"""

from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import re


# ====================================================================
# 一、意图类型枚举(name 必须与 ToolCategory 成员一一对应)
# ====================================================================

class IntentType(str, Enum):
    """统一的意图类型枚举"""
    FILE = "file"
    SYSTEM = "system"
    NETWORK = "network"
    DOCUMENT = "document"
    DESKTOP = "desktop"

    @property
    def category(self) -> "ToolCategory":
        return INTENT_TO_CATEGORY.get(self.value, ToolCategory.FUND_RUNTIME)


# ====================================================================
# 二、工具分类枚举(单一定义源)
# ====================================================================

class ToolCategory(Enum):
    """
    工具分类枚举

    每个成员携带 (value, intent_keys, order, name_cn):
    - intent_keys: 可映射到该分类的意图名称列表(小写)
    - order: 显示排序
    - name_cn: 中文名称

    INTENT_TO_CATEGORY / CATEGORY_ORDER / CATEGORY_NAMES 从此自动派生。
    新增分类只需添加一个枚举成员 —— 小健 2026-05-31
    """
    FILE = ("file", ["file"], 0, "文件操作工具")
    FUND_RUNTIME = ("fund_runtime", ["shell", "system", "time", "meta", "env", "environment", "code_execution"], 1, "基础运行时工具")
    NET_PROCESS = ("net_process", ["network", "process", "service", "registry"], 2, "网络与进程工具")
    SCREEN = ("screen", ["desktop", "screen", "window"], 3, "屏幕交互工具")
    DOC_CONTENT = ("doc_content", ["document", "database", "data_analysis", "content"], 4, "文档内容工具")

    def __new__(cls, value, intent_keys, order, name_cn):
        member = object.__new__(cls)
        member._value_ = value
        member._intent_keys = intent_keys
        member._order = order
        member._name_cn = name_cn
        return member

    @property
    def intent_keys(self) -> List[str]:
        return self._intent_keys

    @property
    def order(self) -> int:
        return self._order

    @property
    def name_cn(self) -> str:
        return self._name_cn


INTENT_TO_CATEGORY: Dict[str, ToolCategory] = {
    k: cat for cat in ToolCategory for k in cat.intent_keys
}

CATEGORY_ORDER: List[ToolCategory] = sorted(ToolCategory, key=lambda c: c.order)

CATEGORY_NAMES: Dict[ToolCategory, str] = {cat: cat.name_cn for cat in ToolCategory}


# ====================================================================
# 四、工具安全级别（Layer 2）— 小沈 2026-06-09
# ====================================================================

class ToolSafetyLevel(Enum):
    """
    工具安全级别五级分级
    
    v3.4修复：区分沙箱内危险和系统级危险
    """
    READ_ONLY = "read_only"              # 纯读取，无副作用
    SAFE = "safe"                        # 有副作用但可逆或无害
    DESTRUCTIVE = "destructive"          # 破坏性操作，不可逆
    DANGEROUS_SANDBOX = "dangerous_sandbox"  # 沙箱内危险(execute_python/execute_js)
    DANGEROUS = "dangerous"              # 系统级危险(execute_shell_command/kill_process)


# SAFETY_POLICY默认值（配置驱动，支持运行时调整）
DEFAULT_SAFETY_POLICY = {
    ToolSafetyLevel.READ_ONLY:          {"needs_confirmation": False, "needs_safety_check": False},
    ToolSafetyLevel.SAFE:               {"needs_confirmation": False, "needs_safety_check": False},
    ToolSafetyLevel.DESTRUCTIVE:        {"needs_confirmation": True,  "needs_safety_check": True},
    ToolSafetyLevel.DANGEROUS_SANDBOX:  {"needs_confirmation": True,  "needs_safety_check": True},
    ToolSafetyLevel.DANGEROUS:          {"needs_confirmation": True,  "needs_safety_check": True},
}


# ====================================================================
# 五、CRSS 意图注册 — CRSS名称 → (IntentType成员名, 关键词数据)
# 新增/删除 CRSS 意图只需在此编辑,INTENT_MAPPING/CRSS_TYPE_KEYWORDS 自动派生
# ====================================================================

_CRSS_REGISTRY: Dict[str, tuple[str, dict]] = {
    # FILE → IntentType.FILE
    "FILE":   ("FILE",   {"keywords": [r'\bls\b', r'\bdir\b', r'\bcd\b', r'\bpwd\b',
                                        r'\bcat\b', r'\bgrep\b', r'\bfind\b', r'\btree\b',
                                        r'\bcp\b', r'\bmv\b', r'\brm\b', r'\bmkdir\b', r'\btouch\b'],
                           "chinese_keywords": ['文件', '目录', '文件夹', '路径', '磁盘', 'c盘', 'd盘', 'e盘']}),

    # SYSTEM 相关 → IntentType.SYSTEM(多个CRSS名映射到同一意图)
    "SHELL":          ("SYSTEM", {"keywords": [r'\bnpm\b', r'\bpip\b', r'\bnode\b', r'\bgcc\b', r'\bpython\b',
                                                r'\bgit\b', r'\bdocker\b', r'\bgradle\b'],
                                   "chinese_keywords": ['终端', '命令', '脚本']}),
    "TIME":           ("SYSTEM", {"keywords": [r'\bdate\b', r'\btime\b', r'\bnow\b', r'\bclock\b',
                                                r'\bcalendar\b', r'\bschedule\b'],
                                   "chinese_keywords": ['时间', '日期', '今天星期', '几月几号', '现在几点']}),
    "ENV":            ("SYSTEM", {"keywords": [r'\bPATH\b', r'\bHOME\b', r'\bTEMP\b'],
                                   "chinese_keywords": ['环境变量', '系统变量']}),
    "ENVIRONMENT":    ("SYSTEM", {"keywords": [r'\benvironment\b', r'\benv\b'],
                                   "chinese_keywords": ['环境', '环境变量']}),
    "SYSTEM":         ("SYSTEM", {"keywords": [r'\bcpu\b', r'\bmemory\b', r'\bram\b', r'\bdisk\b',
                                                r'\bprocess\b', r'\bservice\b'],
                                   "chinese_keywords": ['系统信息', 'CPU', '内存', '进程', '服务', '磁盘']}),
    "CODE_EXECUTION": ("SYSTEM", {"keywords": [r'\bcompile\b', r'\bg\+\+\b'],
                                   "chinese_keywords": ['编译', '执行程序']}),
    "META":           ("SYSTEM", {"keywords": [r'\bversion\b', r'\bconfig\b', r'\binfo\b'],
                                   "chinese_keywords": ['版本', '配置', '信息', '状态']}),

    # NETWORK → IntentType.NETWORK
    "NETWORK": ("NETWORK", {"keywords": [r'\bping\b', r'\bcurl\b', r'\bwget\b', r'\bssh\b',
                                          r'\bhttp\b', r'\bhttps\b', r'\bftp\b', r'\bsocket\b'],
                              "chinese_keywords": ['网络', '端口', '下载', '请求', 'API',
                                                    'IP', 'IP地址', 'DNS', '公网IP', '网关', 'WIFI', 'WiFi']}),

    # DOCUMENT 相关 → IntentType.DOCUMENT
    "DOCUMENT": ("DOCUMENT", {"keywords": [r'\bdocx\b', r'\bpdf\b', r'\btxt\b', r'\bmd\b', r'\bcsv\b', r'\bjson\b'],
                                "chinese_keywords": ['文档', '报告', '笔记', '文本', '文章']}),
    "DATABASE": ("DOCUMENT", {"keywords": [r'\bsql\b', r'\bdb\b', r'\bdatabase\b',
                                            r'\bselect\b', r'\binsert\b', r'\bupdate\b', r'\bdelete\b'],
                                "chinese_keywords": ['数据库', '表', '数据', 'SQL']}),

    # DESKTOP → IntentType.DESKTOP
    "DESKTOP": ("DESKTOP", {"keywords": [r'\bscreenshot\b', r'\bcapture\b',
                                          r'\bclick\b', r'\btype\b', r'\bpress\b', r'\bkey\b'],
                              "chinese_keywords": ['截图', '录屏', '点击', '按键', '键盘', '鼠标', '窗口', '桌面', '浏览器']}),
}

INTENT_MAPPING: Dict[str, IntentType] = {
    name: IntentType[type_name] for name, (type_name, _) in _CRSS_REGISTRY.items()
}

CRSS_TYPE_KEYWORDS: Dict[str, Dict] = {
    name: kw for name, (_, kw) in _CRSS_REGISTRY.items()
}


# ====================================================================
# 四、工具元数据
# ====================================================================

@dataclass
class ToolMetadata:
    """工具元数据"""
    name: str
    description: str
    category: ToolCategory
    version: str = "1.0.0"
    author: str = ""
    dependencies: List[str] = field(default_factory=list)
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    examples: List[Dict[str, Any]] = field(default_factory=list)
    expose_to_llm: bool = True
    next_actions: Dict[str, Any] = field(default_factory=dict)
    failure_hint_fn: Optional[Callable] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # 【v3.4新增】Layer 2安全级别字段 — 小沈 2026-06-09
    safety_level: ToolSafetyLevel = ToolSafetyLevel.SAFE
    action_safety_map: Optional[Dict[str, ToolSafetyLevel]] = None
    # 【借鉴OpenCode】工具使用注意事项 — 小沈 2026-06-11
    critical_notes: str = ""      # 关键注意事项（LLM必须知道的风险/限制）
    usage_hint: str = ""          # 使用提示（最佳实践）
    forbidden: str = ""           # 禁止用法（什么情况下不能使用此工具）

    def get_failure_hint(self, tool_params: Optional[dict] = None) -> str:
        """获取工具失败时的替代建议 — 小健 2026-05-24"""
        if self.failure_hint_fn:
            try:
                return self.failure_hint_fn(tool_params)
            except Exception:
                pass
        return ""


__all__ = [
    "IntentType",
    "ToolCategory",
    "INTENT_TO_CATEGORY",
    "CATEGORY_ORDER",
    "CATEGORY_NAMES",
    "INTENT_MAPPING",
    "CRSS_TYPE_KEYWORDS",
    "ToolMetadata",
    "ToolSafetyLevel",  # 【v3.4新增】
    "DEFAULT_SAFETY_POLICY",  # 【v3.4新增】
]
