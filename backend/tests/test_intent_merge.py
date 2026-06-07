# -*- coding: utf-8 -*-
"""
意图分类器合并测试 — shell/time/meta → system

Author: 小资 - 2026-05-23
"""
import pytest

from app.services.agent.agent_config import resolve_agent_config
from app.services.tools.tool_types import ToolCategory, INTENT_TO_CATEGORY


class TestIntentMerge:
    """意图别名路由测试"""

    def test_shell_routes_to_system(self):
        """shell 意图路由到 system"""
        config = resolve_agent_config("shell")
        assert config.intent_type == "system"

    def test_time_routes_to_system(self):
        """time 意图路由到 system"""
        config = resolve_agent_config("time")
        assert config.intent_type == "system"

    def test_meta_routes_to_system(self):
        """meta 意图路由到 system"""
        config = resolve_agent_config("meta")
        assert config.intent_type == "system"

    def test_env_routes_to_system(self):
        """env 意图路由到 system"""
        config = resolve_agent_config("env")
        assert config.intent_type == "system"

    def test_code_execution_routes_to_system(self):
        """code_execution 意图路由到 system"""
        config = resolve_agent_config("code_execution")
        assert config.intent_type == "system"

    def test_database_routes_to_document(self):
        """database 意图路由到 document"""
        config = resolve_agent_config("database")
        assert config.intent_type == "document"

    def test_intent_to_category_mapping_shell(self):
        """INTENT_TO_CATEGORY 映射：shell → SHELL（或 SYSTEM）"""
        cat = INTENT_TO_CATEGORY.get("shell")
        assert cat in (ToolCategory.SHELL, ToolCategory.SYSTEM)

    def test_intent_to_category_mapping_time(self):
        """INTENT_TO_CATEGORY 映射：time → META"""
        cat = INTENT_TO_CATEGORY.get("time")
        assert cat in (ToolCategory.META, ToolCategory.SYSTEM)

    def test_intent_to_category_mapping_database(self):
        """INTENT_TO_CATEGORY 映射：database → DOCUMENT"""
        cat = INTENT_TO_CATEGORY.get("database")
        assert cat == ToolCategory.DOCUMENT
