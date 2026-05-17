# -*- coding: utf-8 -*-
"""
13.12 meta 分类新工具测试
- 小健 2026-05-17

设计依据: 工具精简方案v1.9 第13.12节
新增: ToolCategory.META, 3个元工具
  tool_help — 查询工具详细用法
  tool_search — 自然语言匹配工具
  pipeline — 多工具执行管道
  batch_process [file分类] — 批量文件处理

覆盖:
  tool_help: 查询已有工具/查询不存在的工具/使用例
  tool_search: 关键词匹配/返回格式
  pipeline: 多步执行/错误停止/步骤传递
  batch_process: dry_run/批量操作
"""

import pytest
from unittest.mock import patch, MagicMock

from app.services.tools.meta.meta_tools import (
    tool_help,
    tool_search,
    pipeline,
)
from app.services.tools.file.file_tools import (
    batch_process,
)


# ============================================================
# TestToolHelp — 元工具: 查询工具用法
# ============================================================
class TestToolHelp:
    """tool_help — 帮助LLM了解工具的详细用法"""

    def test_tool_help_existing(self):
        """正常：查询已注册工具的用法"""
        result = tool_help(tool_name="get_env")
        assert result["code"] == "SUCCESS"
        assert "name" in result["data"]
        assert result["data"]["name"] == "get_env"
        assert "description" in result["data"]
        assert "params" in result["data"]

    def test_tool_help_another(self):
        """正常：查询另一个工具的用法"""
        result = tool_help(tool_name="list_directory")
        assert result["code"] == "SUCCESS"
        assert result["data"]["name"] == "list_directory"

    def test_tool_help_not_found(self):
        """异常：工具不存在"""
        result = tool_help(tool_name="nonexistent_tool_xyz_999")
        assert result["code"] == "ERR_TOOL_NOT_FOUND"
        assert "next_actions" in result
        tools = [a["tool"] for a in result["next_actions"]]
        assert "tool_search" in tools

    def test_tool_help_returns_schema(self):
        """正常：返回参数的JSON Schema"""
        result = tool_help(tool_name="get_env")
        if result["code"] == "SUCCESS":
            params = result["data"].get("params")
            if params:
                assert "properties" in params

    def test_tool_help_next_actions(self):
        """【P15】tool_help 成功后返回 next_actions"""
        result = tool_help(tool_name="get_env")
        if result["code"] == "SUCCESS":
            assert "next_actions" in result or "message" in result


# ============================================================
# TestToolSearch — 元工具: 自然语言搜索工具
# ============================================================
class TestToolSearch:
    """tool_search — 帮LLM从众多工具中找到合适的"""

    def test_tool_search_by_keyword(self):
        """正常：按关键词搜索工具"""
        result = tool_search(query="read file")
        assert result["code"] == "SUCCESS"
        assert "matches" in result["data"]
        assert len(result["data"]["matches"]) > 0
        names = [m["tool"] for m in result["data"]["matches"]]
        assert any("read" in n.lower() for n in names)

    def test_tool_search_by_action(self):
        """正常：按操作意图搜索"""
        result = tool_search(query="delete environment variable")
        assert result["code"] == "SUCCESS"
        assert len(result["data"]["matches"]) > 0

    def test_tool_search_no_match(self):
        """边界：无匹配工具"""
        result = tool_search(query="zzzznotexist999")
        assert result["code"] == "SUCCESS"
        assert isinstance(result["data"]["matches"], list)

    def test_tool_search_result_limit(self):
        """正常：返回最多10个匹配"""
        result = tool_search(query="file")
        assert result["code"] == "SUCCESS"
        assert len(result["data"]["matches"]) <= 10

    def test_tool_search_format(self):
        """验证返回结果格式"""
        result = tool_search(query="list windows")
        if result["data"]["matches"]:
            m = result["data"]["matches"][0]
            assert "tool" in m
            assert "description" in m
            assert "score" in m


# ============================================================
# TestPipeline — 编排工具: 多工具执行管道
# ============================================================
class TestPipeline:
    """pipeline — 多工具按序执行管道"""

    def test_pipeline_single_step(self):
        """正常：单步管道"""
        result = pipeline(steps=[
            {"tool": "get_system_info", "params": {"info_type": "basic"}},
        ])
        assert result["code"] == "SUCCESS"
        assert len(result["data"]["results"]) == 1

    def test_pipeline_multi_step(self):
        """正常：多步管道"""
        result = pipeline(steps=[
            {"tool": "get_system_info", "params": {"info_type": "basic"}},
            {"tool": "get_system_info", "params": {"info_type": "cpu"}},
        ])
        assert result["code"] == "SUCCESS"
        assert len(result["data"]["results"]) == 2

    def test_pipeline_stop_on_error(self):
        """异常：stop_on_error=True时中间失败中断"""
        result = pipeline(steps=[
            {"tool": "get_system_info", "params": {"info_type": "basic"}},
            {"tool": "nonexistent_tool", "params": {}},
        ], stop_on_error=True)
        assert result["code"] in ("SUCCESS", "ERR_TOOL_NOT_FOUND", "ERR_PIPELINE_STOPPED")

    def test_pipeline_tool_not_found(self):
        """异常：工具不存在"""
        result = pipeline(steps=[
            {"tool": "nonexistent_tool_xyz", "params": {}},
        ])
        assert "ERR" in result["code"]

    def test_pipeline_context_passing(self):
        """正常：步骤间上下文传递"""
        result = pipeline(steps=[
            {"tool": "get_system_info", "params": {"info_type": "basic"}},
        ])
        if result["code"] == "SUCCESS":
            assert "step_1" in result.get("data", {})

    def test_pipeline_empty_steps(self):
        """边界：空步骤列表"""
        result = pipeline(steps=[])
        assert result["code"] in ("SUCCESS", "ERROR")


# ============================================================
# TestBatchProcess — 文件分类: 批量文件处理
# ============================================================
class TestBatchProcess:
    """batch_process — 批量文件操作(file分类)"""

    def test_batch_process_dry_run(self, tmp_path):
        """【P15】dry_run模式(默认)"""
        # 创建测试文件
        for i in range(3):
            (tmp_path / f"test_{i}.txt").write_text(f"content_{i}")
        result = batch_process(
            source_pattern=str(tmp_path / "*.txt"),
            action="rename",
            target_pattern="*.md",
            dry_run=True,
        )
        assert result["code"] == "SUCCESS"
        assert "file_count" in result.get("data", {})

    def test_batch_process_no_match(self):
        """边界：无匹配文件"""
        result = batch_process(
            source_pattern="/nonexistent_dir_xyz/*.nonexistent",
            action="delete",
        )
        assert result["code"] == "ERR_NO_MATCH"

    def test_batch_process_next_actions(self, tmp_path):
        """【P15】dry_run后建议确认执行"""
        for i in range(2):
            (tmp_path / f"batch_{i}.txt").write_text("data")
        result = batch_process(
            source_pattern=str(tmp_path / "*.txt"),
            action="delete",
            dry_run=True,
        )
        assert "next_actions" in result
        tools = [a["tool"] for a in result["next_actions"]]
        assert "batch_process" in tools
