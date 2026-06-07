# -*- coding: utf-8 -*-
"""
agent_config.py 测试 — 声明式配置注册表

Author: 小资 - 2026-05-23
"""
import pytest

from app.services.agent.agent_config import (
    AgentConfig,
    AGENT_REGISTRY,
    resolve_agent_config,
    get_all_intent_types,
)
from app.services.tools.registry import ToolCategory


class TestResolveAgentConfig:
    """resolve_agent_config 核心逻辑"""

    @pytest.mark.parametrize("intent_type", [
        "file", "system", "network", "document", "desktop",
    ])
    def test_resolve_agent_config_primary(self, intent_type):
        """所有5个主 intent_type 都能正确解析"""
        config = resolve_agent_config(intent_type)
        assert isinstance(config, AgentConfig)
        assert config.intent_type == intent_type

    @pytest.mark.parametrize("alias,primary", [
        ("shell", "system"),
        ("meta", "system"),
        ("time", "system"),
        ("environment", "system"),
        ("env", "system"),
        ("code_execution", "system"),
        ("database", "document"),
    ])
    def test_resolve_agent_config_aliases(self, alias, primary):
        """所有7个别名都能解析到对应主 intent"""
        config = resolve_agent_config(alias)
        assert config.intent_type == primary

    def test_resolve_agent_config_unknown(self):
        """未知 intent_type 抛出 ValueError"""
        with pytest.raises(ValueError, match="Unknown intent_type"):
            resolve_agent_config("nonexistent_intent")


class TestGetAllIntentTypes:
    """get_all_intent_types 汇总"""

    def test_get_all_intent_types(self):
        """返回所有12个 intent_type（5主+7别名）"""
        all_types = get_all_intent_types()
        primaries = {"file", "system", "network", "document", "desktop"}
        aliases = {"shell", "meta", "time", "environment", "env", "code_execution", "database"}
        expected = primaries | aliases
        assert set(all_types) == expected
        assert len(all_types) == 12


class TestAgentConfigFields:
    """AgentConfig 字段值正确性"""

    def test_file_config_fields(self):
        c = AGENT_REGISTRY["file"]
        assert c.category == ToolCategory.FILE
        assert c.rollback_enabled is True
        assert c.prompt_class_name == "FileOperationPrompts"
        assert c.category_display_name == "文件操作"

    def test_system_config_fields(self):
        c = AGENT_REGISTRY["system"]
        assert c.category == ToolCategory.SYSTEM
        assert c.rollback_enabled is False
        assert c.prompt_class_name == "SystemPrompts"
        assert c.category_display_name == "系统操作"

    def test_network_config_fields(self):
        c = AGENT_REGISTRY["network"]
        assert c.category == ToolCategory.NETWORK
        assert c.rollback_enabled is False
        assert c.prompt_class_name == "NetworkPrompts"
        assert c.category_display_name == "网络通信"

    def test_document_config_fields(self):
        c = AGENT_REGISTRY["document"]
        assert c.category == ToolCategory.DOCUMENT
        assert c.rollback_enabled is False
        assert c.prompt_class_name == "DocumentPrompts"
        assert c.category_display_name == "文档读写"

    def test_desktop_config_fields(self):
        c = AGENT_REGISTRY["desktop"]
        assert c.category == ToolCategory.DESKTOP
        assert c.rollback_enabled is False
        assert c.prompt_class_name == "DesktopPrompts"
        assert c.category_display_name == "桌面操作"

    def test_file_config_rollback_enabled(self):
        """确认 file 的 rollback_enabled=True"""
        assert AGENT_REGISTRY["file"].rollback_enabled is True

    def test_system_config_aliases(self):
        """确认 system 的 aliases 包含 shell/meta/time 等"""
        aliases = AGENT_REGISTRY["system"].aliases
        for a in ["shell", "meta", "time", "environment", "env", "code_execution"]:
            assert a in aliases


class TestPromptClassLazyLoad:
    """prompt_class 属性懒加载"""

    def test_prompt_class_lazy_load(self):
        """测试 prompt_class 属性懒加载正确"""
        c = AGENT_REGISTRY["file"]
        prompt_cls = c.prompt_class
        assert prompt_cls is not None
        assert prompt_cls.__name__ == "FileOperationPrompts"

    def test_prompt_class_cached(self):
        """prompt_class 第二次访问不再重新导入"""
        c = AGENT_REGISTRY["system"]
        cls1 = c.prompt_class
        cls2 = c.prompt_class
        assert cls1 is cls2
