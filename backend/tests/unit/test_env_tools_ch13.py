# -*- coding: utf-8 -*-
"""
13.2 environment(env) 优化测试 - 5→3
- 小健 2026-05-17

设计依据: 工具精简方案v1.9 第13.2节
变更: delete_env→合入set_env(action="delete"); exists_env→消除(get_env已返回exists)
新增: P15 next_actions (含跨分类); P16 幂等性+action统一

覆盖:
  set_env (含 action="delete")
  get_env (含 exists 字段)
  list_env
  P15 next_actions 输出格式
  P16 幂等性
"""

import os
from unittest.mock import patch, MagicMock

import pytest

from app.services.tools.environment.env_tools import (
    get_env,
    set_env,
    list_env,
)


# ============================================================
# TestSetEnv — 13.2 set_env: action统一 (合并delete_env)
# ============================================================
class TestSetEnv:
    """set_env 优化后测试 — 含 action="delete" 统一入口"""

    def test_set_env_create(self):
        """P13.2.2: 创建新环境变量"""
        result = set_env("__TEST_CH13_CREATE__", "new_val", scope="process")
        assert result["code"] == "SUCCESS"
        assert os.environ.get("__TEST_CH13_CREATE__") == "new_val"
        os.environ.pop("__TEST_CH13_CREATE__", None)

    def test_set_env_update(self):
        """P13.2.2: 更新已存在的变量"""
        os.environ["__TEST_CH13_UPDATE__"] = "old"
        result = set_env("__TEST_CH13_UPDATE__", "new", scope="process")
        assert result["code"] == "SUCCESS"
        assert os.environ.get("__TEST_CH13_UPDATE__") == "new"
        os.environ.pop("__TEST_CH13_UPDATE__", None)

    def test_set_env_action_delete(self):
        """【合并delete_env】set_env(action="delete") 删除环境变量"""
        os.environ["__TEST_CH13_DEL__"] = "to_delete"
        result = set_env("__TEST_CH13_DEL__", scope="process", action="delete")
        assert result["code"] == "SUCCESS"
        assert "__TEST_CH13_DEL__" not in os.environ

    def test_set_env_action_delete_not_exists(self):
        """【P16幂等】删除不存在的变量应返回成功而非报错"""
        result = set_env("__TEST_CH13_NONEXIST__", scope="process", action="delete")
        assert result["code"] == "SUCCESS"

    def test_set_env_append_mode(self):
        """【P16幂等】append_mode防重复"""
        os.environ["__TEST_CH13_APPEND__"] = "base"
        result = set_env("__TEST_CH13_APPEND__", ";new", scope="process", append_mode=True)
        assert result["code"] == "SUCCESS"
        val = os.environ.get("__TEST_CH13_APPEND__", "")
        # append_mode防重复: ";new;new" 不应出现
        assert val.count("new") == 1
        os.environ.pop("__TEST_CH13_APPEND__", None)

    def test_set_env_next_actions(self):
        """【P15】set_env 成功后应返回 next_actions"""
        result = set_env("__TEST_CH13_NA__", "val", scope="process")
        os.environ.pop("__TEST_CH13_NA__", None)
        assert "next_actions" in result
        assert isinstance(result["next_actions"], list)
        assert len(result["next_actions"]) >= 1
        # 应包含 get_env 验证建议
        tool_names = [a["tool"] for a in result["next_actions"]]
        assert "get_env" in tool_names


# ============================================================
# TestGetEnv — 13.2 get_env: exists字段已覆盖exists_env功能
# ============================================================
class TestGetEnv:
    """get_env 优化后测试 — exists字段消除exists_env需求"""

    def test_get_existing_env(self):
        """正常：获取已存在的变量，exists=True"""
        os.environ["__TEST_CH13_GET__"] = "val"
        result = get_env("__TEST_CH13_GET__")
        os.environ.pop("__TEST_CH13_GET__", None)
        assert result["code"] == "SUCCESS"
        assert result["data"]["exists"] is True
        assert result["data"]["value"] == "val"

    def test_get_nonexistent_env(self):
        """【消除exists_env】get_env 获取不存在变量，exists=False"""
        result = get_env("__TEST_CH13_NONEXIST__")
        assert result["code"] == "SUCCESS"
        assert result["data"]["exists"] is False

    def test_get_env_with_default(self):
        """正常：不存在时返回默认值"""
        result = get_env("__TEST_CH13_NONEXIST__", default="fallback")
        assert result["code"] == "SUCCESS"
        assert result["data"]["value"] == "fallback"

    def test_get_env_process_scope(self):
        """正常：process作用域"""
        os.environ["__TEST_CH13_SCOPE__"] = "val"
        result = get_env("__TEST_CH13_SCOPE__", scope="process")
        os.environ.pop("__TEST_CH13_SCOPE__", None)
        assert result["code"] == "SUCCESS"
        assert result["data"]["scope"] == "process"

    def test_get_env_next_actions_exists(self):
        """【P15】get_env 存在时 next_actions 应包含 set_env/list_env"""
        os.environ["__TEST_CH13_NA2__"] = "val"
        result = get_env("__TEST_CH13_NA2__")
        os.environ.pop("__TEST_CH13_NA2__", None)
        assert "next_actions" in result
        tool_names = [a["tool"] for a in result["next_actions"]]
        assert "set_env" in tool_names
        assert "list_env" in tool_names

    def test_get_env_next_actions_not_exists(self):
        """【P15】get_env 不存在时 next_actions 建议创建"""
        result = get_env("__TEST_CH13_NONEXIST_NA__")
        assert "next_actions" in result
        tool_names = [a["tool"] for a in result["next_actions"]]
        assert "set_env" in tool_names


# ============================================================
# TestListEnv — 13.2 list_env: 保留, 新增 next_actions
# ============================================================
class TestListEnv:
    """list_env 优化后测试"""

    def test_list_env_basic(self):
        """正常：列出全部环境变量"""
        result = list_env()
        assert result["code"] == "SUCCESS"
        assert isinstance(result["data"]["env_vars"], list)

    def test_list_env_llm_data(self):
        """正常：llm_data 精简输出"""
        result = list_env()
        assert result["code"] == "SUCCESS"
        if "llm_data" in result:
            for item in result["llm_data"]:
                assert "name" in item
                assert "value" in item

    def test_list_env_next_actions(self):
        """【P15】list_env 成功后应返回 next_actions"""
        result = list_env()
        if result["code"] == "SUCCESS":
            assert "next_actions" in result
            tool_names = [a["tool"] for a in result["next_actions"]]
            assert "get_env" in tool_names


# ============================================================
# TestEliminated — 13.2 验证已消除的工具
# ============================================================
class TestEliminated:
    """验证 delete_env 和 exists_env 已被消除（不暴露为LLM工具）"""

    def test_delete_env_not_importable(self):
        """【消除】delete_env 不应再作为独立LLM工具存在"""
        with pytest.raises(ImportError):
            from app.services.tools.environment.env_tools import delete_env  # noqa

    def test_exists_env_not_importable(self):
        """【消除】exists_env 不应再作为独立LLM工具存在"""
        with pytest.raises(ImportError):
            from app.services.tools.environment.env_tools import exists_env  # noqa
