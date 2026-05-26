# -*- coding: utf-8 -*-
"""
Agent 配置注册表 — 声明式定义

改造前：9个Agent子类（每个category一个类）
改造后：2个类（UniversalReactAgent + DesktopReactAgent）+ 声明式配置

Author: 小强 - 2026-05-23
"""
from dataclasses import dataclass, field
from typing import Type, List, Dict, Optional

from app.services.tools.registry import ToolCategory
from app.services.prompts.BasePromptTemplate import BasePrompts


@dataclass
class AgentConfig:
    """Agent 配置项"""
    intent_type: str
    category: ToolCategory
    prompt_module: str
    prompt_class_name: str
    category_display_name: str
    rollback_enabled: bool = False
    max_steps: int = 100
    aliases: List[str] = field(default_factory=list)
    
    _prompt_class: Optional[Type[BasePrompts]] = field(default=None, repr=False)
    
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
        rollback_enabled=True,
        aliases=[],
    ),
    "system": AgentConfig(
        intent_type="system",
        category=ToolCategory.SYSTEM,
        prompt_module="app.services.prompts.system.system_prompts",
        prompt_class_name="SystemPrompts",
        category_display_name="系统操作",
        aliases=["shell", "meta", "time", "environment", "env", "code_execution"],
    ),
    "network": AgentConfig(
        intent_type="network",
        category=ToolCategory.NETWORK,
        prompt_module="app.services.prompts.network.network_prompts",
        prompt_class_name="NetworkPrompts",
        category_display_name="网络通信",
        aliases=[],
    ),
    "document": AgentConfig(
        intent_type="document",
        category=ToolCategory.DOCUMENT,
        prompt_module="app.services.prompts.document.document_prompts",
        prompt_class_name="DocumentPrompts",
        category_display_name="文档读写",
        aliases=["database"],
    ),
    "desktop": AgentConfig(
        intent_type="desktop",
        category=ToolCategory.DESKTOP,
        prompt_module="app.services.prompts.desktop.desktop_prompts",
        prompt_class_name="DesktopPrompts",
        category_display_name="桌面操作",
        aliases=[],
    ),
}


def resolve_agent_config(intent_type: str) -> AgentConfig:
    """根据 intent_type 解析 Agent 配置（支持别名）"""
    for config in AGENT_REGISTRY.values():
        if config.intent_type == intent_type:
            return config
        if intent_type in config.aliases:
            return config
    raise ValueError(f"Unknown intent_type: {intent_type}")


def get_all_intent_types() -> List[str]:
    """获取所有 intent_type（含别名）"""
    result = []
    for config in AGENT_REGISTRY.values():
        result.append(config.intent_type)
        result.extend(config.aliases)
    return result
