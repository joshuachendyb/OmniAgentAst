# -*- coding: utf-8 -*-
"""
Agent 配置注册表 — 声明式定义

改造前：9个Agent子类（每个category一个类）
改造后：2个类（UniversalReactAgent + DesktopReactAgent）+ 声明式配置

Author: 小强 - 2026-05-23
"""
from dataclasses import dataclass, field
from typing import Type, List, Dict, Optional, Any

from app.services.tools.tool_types import ToolCategory
from app.services.prompts.base_prompt_template import BasePrompts


@dataclass
class AgentConfig:
    """Agent 配置项"""
    intent_type: str
    category: ToolCategory
    prompt_module: str
    prompt_class_name: str
    category_display_name: str
    agent_module: str = ""
    agent_class_name: str = ""
    rollback_enabled: bool = False
    max_steps: int = 100
    aliases: List[str] = field(default_factory=list)
    
    _prompt_class: Optional[Type[BasePrompts]] = field(default=None, repr=False)
    _agent_class: Optional[Any] = field(default=None, repr=False)
    
    @property
    def prompt_class(self) -> Type[BasePrompts]:
        if self._prompt_class is None:
            import importlib
            module = importlib.import_module(self.prompt_module)
            self._prompt_class = getattr(module, self.prompt_class_name)
        return self._prompt_class
    
    @property
    def agent_class(self) -> Any:
        if self._agent_class is None and self.agent_module:
            import importlib
            module = importlib.import_module(self.agent_module)
            self._agent_class = getattr(module, self.agent_class_name)
        return self._agent_class
    
    @property
    def prompt_class(self) -> Type[BasePrompts]:
        if self._prompt_class is None:
            import importlib
            module = importlib.import_module(self.prompt_module)
            self._prompt_class = getattr(module, self.prompt_class_name)
        return self._prompt_class


AGENT_REGISTRY: Dict[str, AgentConfig] = {
    "file": AgentConfig(
        intent_type="file",
        category=ToolCategory.FILE,
        prompt_module="app.services.prompts.file.file_prompts",
        prompt_class_name="FileOperationPrompts",
        category_display_name="文件操作",
        agent_module="app.services.agent.universal_react",
        agent_class_name="UniversalReactAgent",
        rollback_enabled=True,
        aliases=[],
    ),
    "system": AgentConfig(
        intent_type="system",
        category=ToolCategory.SYSTEM,
        prompt_module="app.services.prompts.system.system_prompts",
        prompt_class_name="SystemPrompts",
        category_display_name="系统操作",
        agent_module="app.services.agent.universal_react",
        agent_class_name="UniversalReactAgent",
        aliases=["shell"],
    ),
    "network": AgentConfig(
        intent_type="network",
        category=ToolCategory.NETWORK,
        prompt_module="app.services.prompts.network.network_prompts",
        prompt_class_name="NetworkPrompts",
        category_display_name="网络通信",
        agent_module="app.services.agent.universal_react",
        agent_class_name="UniversalReactAgent",
        aliases=[],
    ),
    "document": AgentConfig(
        intent_type="document",
        category=ToolCategory.DOCUMENT,
        prompt_module="app.services.prompts.document.document_prompts",
        prompt_class_name="DocumentPrompts",
        category_display_name="文档读写",
        agent_module="app.services.agent.universal_react",
        agent_class_name="UniversalReactAgent",
        aliases=[],
    ),
    "desktop": AgentConfig(
        intent_type="desktop",
        category=ToolCategory.DESKTOP,
        prompt_module="app.services.prompts.desktop.desktop_prompts",
        prompt_class_name="DesktopPrompts",
        category_display_name="桌面操作",
        agent_module="app.services.agent.desktop_react",
        agent_class_name="DesktopReactAgent",
        aliases=[],
    ),
}


def resolve_agent_config(intent_type: str) -> AgentConfig:
    """根据 intent_type 解析 Agent 配置（支持别名）"""
    # 首先规范化意图类型
    from app.services.intents.intent_mapper import normalize_intent
    normalized_intent = normalize_intent(intent_type)
    
    # 使用规范化后的意图查找配置
    for config in AGENT_REGISTRY.values():
        if config.intent_type == normalized_intent:
            return config
        if normalized_intent in config.aliases:
            return config
    
    raise ValueError(f"Unknown intent_type: {intent_type}")


def get_all_intent_types() -> List[str]:
    """获取所有 intent_type（含别名）"""
    from app.services.intents.intent_mapper import get_agent_intent_names, get_aliases_for_intent
    from app.services.tools.tool_types import IntentType
    
    result = []
    # 添加所有标准意图类型
    result.extend(get_agent_intent_names())
    
    # 添加所有别名
    for intent_type in IntentType:
        result.extend(get_aliases_for_intent(intent_type))
    
    return list(set(result))  # 去重
