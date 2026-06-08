# -*- coding: utf-8 -*-
"""
Agent 配置注册表 — 声明式定义

Author: 小沈 - 2026-06-07
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


AGENT_REGISTRY: Dict[str, AgentConfig] = {
    "file": AgentConfig(
        intent_type="file",
        category=ToolCategory.FILE,
        prompt_module="app.services.prompts.file.file_prompts",
        prompt_class_name="FileOperationPrompts",
        category_display_name="文件操作",
        agent_module="app.services.agent.universal_agent",
        agent_class_name="UniversalAgent",
        rollback_enabled=True,
    ),
    "system": AgentConfig(
        intent_type="system",
        category=ToolCategory.SYSTEM,
        prompt_module="app.services.prompts.system.system_prompts",
        prompt_class_name="SystemPrompts",
        category_display_name="系统操作",
        agent_module="app.services.agent.universal_agent",
        agent_class_name="UniversalAgent",
    ),
    "network": AgentConfig(
        intent_type="network",
        category=ToolCategory.NETWORK,
        prompt_module="app.services.prompts.network.network_prompts",
        prompt_class_name="NetworkPrompts",
        category_display_name="网络通信",
        agent_module="app.services.agent.universal_agent",
        agent_class_name="UniversalAgent",
    ),
    "document": AgentConfig(
        intent_type="document",
        category=ToolCategory.DOCUMENT,
        prompt_module="app.services.prompts.document.document_prompts",
        prompt_class_name="DocumentPrompts",
        category_display_name="文档读写",
        agent_module="app.services.agent.universal_agent",
        agent_class_name="UniversalAgent",
    ),
    "desktop": AgentConfig(
        intent_type="desktop",
        category=ToolCategory.DESKTOP,
        prompt_module="app.services.prompts.desktop.desktop_prompts",
        prompt_class_name="DesktopPrompts",
        category_display_name="桌面操作",
        agent_module="app.services.agent.universal_agent",  # 【修复P0-3 2026-06-08 小沈】改为UniversalAgent，删除DesktopAgent
        agent_class_name="UniversalAgent",  # 遵守DRY、复用优先原则
    ),
}


def resolve_agent_config(intent_type: str) -> AgentConfig:
    """根据 intent_type 解析 Agent 配置(精确匹配,无别名)"""
    from app.services.intents.intent_mapper import normalize_intent
    normalized_intent = normalize_intent(intent_type)
    config = AGENT_REGISTRY.get(normalized_intent)
    if config is not None:
        return config
    raise ValueError(f"Unknown intent_type: {intent_type}")


def get_all_intent_types() -> list:
    """返回所有注册的 intent_type 列表
    小健 - 2026-06-08 修复缺失函数
    """
    return list(AGENT_REGISTRY.keys())

