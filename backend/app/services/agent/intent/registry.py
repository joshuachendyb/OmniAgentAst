from typing import Dict, List, Optional

from pydantic import BaseModel


class Intent(BaseModel):
    """意图定义"""
    name: str  # 意图名称（如 "file", "network"）
    description: str  # 意图描述
    keywords: List[str]  # 关键词列表（用于分类）
    tools: List[str]  # 关联的工具名称列表
    safety_checker: Optional[str] = None  # 安全检查器名称


class IntentRegistry:
    """意图注册表（通用接口）"""

    def __init__(self):
        self._intents: Dict[str, Intent] = {}

    def register(self, intent: Intent):
        """注册新意图类型"""
        self._intents[intent.name] = intent

    def get(self, name: str) -> Optional[Intent]:
        """获取指定意图"""
        return self._intents.get(name)

    def list_all(self) -> List[Intent]:
        """列出所有已注册的意图"""
        return list(self._intents.values())

    def get_all_names(self) -> List[str]:
        """获取所有意图名称"""
        return list(self._intents.keys())