# -*- coding: utf-8 -*-
"""
工具4部分一致性全面检查测试 - 小健 2026-05-19

检查范围：7分类 x 59个LLM可见工具
检查内容：
  1. tool函数的参数签名 vs schema的properties字段
  2. schema的required字段 vs 函数参数的默认值（必填/可选一致性）
  3. register的description完整性
  4. schema每个字段的description完整性

特殊处理：
  - FILE分类的implementation是 lambda **kw: _get_ft().xxx(**kw)
    需要去底层FileTools类方法检查参数签名

每个tool逐一检查，不遗漏。
"""

import sys
import os
import inspect
import pytest
from typing import Dict, List, Any, Optional, Set, Tuple
from pydantic import BaseModel
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.tools.registry import (
    ToolRegistry,
    ToolCategory,
    ToolMetadata,
    tool_registry,
    register_tool,
)
from app.services.tools import ensure_tools_registered
from app.services.tools.lazy_loader import reset_registered_state


# ============================================================================
# FILE分类特殊处理：获取FileTools类方法的真实参数签名
# ============================================================================

_FILE_TOOLS_CLASS = None

def _get_file_tools_class():
    global _FILE_TOOLS_CLASS
    if _FILE_TOOLS_CLASS is None:
        from app.services.tools.file.file_tools import FileTools
        _FILE_TOOLS_CLASS = FileTools
    return _FILE_TOOLS_CLASS


# FILE分类 tool_name → FileTools类方法名 的映射
_FILE_TOOL_METHOD_MAP = {
    "read_file": "read_file",
    "write_text_file": "write_text_file",
    "read_media_file": "read_media_file",
    "edit_file": "edit_file",
    "list_directory": "list_directory",
    "search_files": "search_files",
    "grep_file_content": "grep_file_content",
    "rename_file": "rename_file",
    "archive_tool": "archive_tool",
    "file_operation": "file_operation",
    "data_file_format": "data_file_format",
}


# ============================================================================
# 辅助函数
# ============================================================================

def _get_func_params(func: callable) -> Dict[str, Any]:
    """提取函数参数信息：名称、类型、是否有默认值"""
    sig = inspect.signature(func)
    params = {}
    for name, param in sig.parameters.items():
        if name in ("self", "cls", "args", "kwargs"):
            continue
        params[name] = {
            "name": name,
            "has_default": param.default is not inspect.Parameter.empty,
            "default_value": param.default if param.default is not inspect.Parameter.empty else None,
            "annotation": str(param.annotation) if param.annotation is not inspect.Parameter.empty else None,
        }
    return params


def _get_real_func_params(tool_name: str, impl: callable) -> Dict[str, Any]:
    """获取tool的真实函数参数（处理lambda **kw包装）"""
    if tool_name in _FILE_TOOL_METHOD_MAP:
        cls = _get_file_tools_class()
        method_name = _FILE_TOOL_METHOD_MAP[tool_name]
        method = getattr(cls, method_name, None)
        if method:
            return _get_func_params(method)
    return _get_func_params(impl)


def _get_real_docstring(tool_name: str, impl: callable) -> str:
    """获取tool的真实docstring（处理lambda **kw包装）"""
    if tool_name in _FILE_TOOL_METHOD_MAP:
        cls = _get_file_tools_class()
        method_name = _FILE_TOOL_METHOD_MAP[tool_name]
        method = getattr(cls, method_name, None)
        if method and method.__doc__:
            return method.__doc__.strip()
    if impl.__doc__:
        return impl.__doc__.strip()
    return ""


def _get_schema_fields(schema: Dict) -> Dict[str, Any]:
    """从Pydantic JSON Schema中提取字段信息"""
    if not schema or "properties" not in schema:
        return {}
    required = set(schema.get("required", []))
    fields = {}
    for name, info in schema["properties"].items():
        field_type = info.get("type", "unknown")
        if "anyOf" in info and field_type == "unknown":
            types = [item.get("type") for item in info["anyOf"] if isinstance(item, dict) and "type" in item]
            non_null = [t for t in types if t != "null"]
            field_type = non_null[0] if len(non_null) == 1 else f"union({','.join(non_null)})"
        fields[name] = {
            "name": name,
            "type": field_type,
            "required": name in required,
            "description": info.get("description", ""),
        }
    return fields


def _compare_params_schema(
    tool_name: str,
    func_params: Dict,
    schema_fields: Dict,
) -> List[str]:
    """比较函数参数与schema字段的一致性"""
    issues = []
    func_param_names = set(func_params.keys())
    schema_field_names = set(schema_fields.keys())

    extra_in_schema = schema_field_names - func_param_names
    if extra_in_schema:
        issues.append(f"  ❌ schema有但函数参数缺少: {sorted(extra_in_schema)}")

    extra_in_func = func_param_names - schema_field_names
    if extra_in_func:
        issues.append(f"  ❌ 函数参数有但schema缺少: {sorted(extra_in_func)}")

    common = func_param_names & schema_field_names
    for name in sorted(common):
        func_param = func_params[name]
        schema_field = schema_fields[name]
        func_is_required = not func_param["has_default"]
        schema_is_required = schema_field["required"]
        if func_is_required != schema_is_required:
            func_str = "必填" if func_is_required else "可选"
            schema_str = "必填" if schema_is_required else "可选"
            issues.append(f"  ❌ 参数'{name}'必填/可选不一致: 函数={func_str}, schema={schema_str}")

    return issues


# ============================================================================
# Fixture
# ============================================================================

@pytest.fixture(autouse=True, scope="module")
def register_all_tools():
    reset_registered_state()
    ensure_tools_registered()
    yield
    reset_registered_state()


# ============================================================================
# 获取所有已注册工具
# ============================================================================

def _get_all_llm_tools() -> List[Tuple[str, ToolMetadata, callable]]:
    tools = []
    for name, metadata in tool_registry._tools.items():
        if not metadata.expose_to_llm:
            continue
        impl = tool_registry.get_implementation(name)
        tools.append((name, metadata, impl))
    return sorted(tools, key=lambda x: (x[1].category.value, x[0]))


# ============================================================================
# 核心检查函数
# ============================================================================

def _check_tool_four_parts(tool_name: str) -> List[str]:
    """检查单个tool的4部分一致性，返回问题列表"""
    issues = []
    metadata = tool_registry.get_tool(tool_name)
    impl = tool_registry.get_implementation(tool_name)

    if metadata is None:
        return [f"  ❌ 工具'{tool_name}'未在registry中注册"]

    if impl is None:
        issues.append(f"  ❌ 工具'{tool_name}'没有实现函数")
        return issues

    # === 第1部分：函数参数（处理lambda **kw包装） ===
    func_params = _get_real_func_params(tool_name, impl)

    # === 第2部分：Schema字段 ===
    schema = metadata.input_schema
    schema_fields = _get_schema_fields(schema)

    # === 检查1：函数参数 vs Schema字段 ===
    param_schema_issues = _compare_params_schema(tool_name, func_params, schema_fields)
    issues.extend(param_schema_issues)

    # === 第3部分：register的description ===
    reg_description = metadata.description
    if not reg_description:
        issues.append(f"  ❌ register description为空")

    # === 第4部分：函数docstring（处理lambda **kw包装） ===
    func_docstring = _get_real_docstring(tool_name, impl)
    if not func_docstring:
        issues.append(f"  ⚠️ 函数docstring为空（建议补充）")

    # === 检查：input_schema结构完整性 ===
    if not schema:
        issues.append(f"  ❌ input_schema为空")
    else:
        if "properties" not in schema:
            issues.append(f"  ❌ input_schema缺少properties")
        if "type" not in schema:
            issues.append(f"  ⚠️ input_schema缺少type字段")

    # === 检查：schema每个字段是否有description ===
    for field_name, field_info in schema_fields.items():
        if not field_info["description"]:
            issues.append(f"  ⚠️ schema字段'{field_name}'缺少description说明")

    # === 检查：implementation可调用 ===
    if not callable(impl):
        issues.append(f"  ❌ implementation不可调用")

    return issues


def _check_schema_depth(tool_name: str) -> List[str]:
    """深度检查schema结构"""
    issues = []
    metadata = tool_registry.get_tool(tool_name)
    if not metadata:
        return ["  ❌ 未注册"]

    schema = metadata.input_schema
    if not schema:
        issues.append("  ❌ input_schema为空")
        return issues

    if "type" not in schema:
        issues.append("  ⚠️ schema缺少顶级type字段")
    elif schema["type"] != "object":
        issues.append(f"  ⚠️ schema顶级type不是object: {schema['type']}")

    if "properties" not in schema:
        issues.append("  ❌ schema缺少properties")
        return issues

    for prop_name, prop_info in schema["properties"].items():
        if not isinstance(prop_info, dict):
            issues.append(f"  ❌ 字段'{prop_name}'不是dict")
            continue

        has_type = "type" in prop_info
        has_any_of = "anyOf" in prop_info
        has_one_of = "oneOf" in prop_info
        has_ref = "$ref" in prop_info
        has_all_of = "allOf" in prop_info

        if not any([has_type, has_any_of, has_one_of, has_ref, has_all_of]):
            issues.append(f"  ❌ 字段'{prop_name}'缺少type/anyOf/oneOf/$ref/allOf")

        if "enum" in prop_info:
            if not isinstance(prop_info["enum"], list):
                issues.append(f"  ❌ 字段'{prop_name}'的enum不是list")

    required = schema.get("required", [])
    if not isinstance(required, list):
        issues.append(f"  ❌ required不是list: {type(required)}")
    else:
        prop_names = set(schema["properties"].keys())
        for r in required:
            if r not in prop_names:
                issues.append(f"  ❌ required中的'{r}'不在properties中")

    return issues


# ============================================================================
# 测试1: 工具总数和分类数
# ============================================================================

class TestToolCounts:
    def test_category_count(self):
        assert len(ToolCategory) == 7

    def test_llm_visible_tool_count(self):
        tools = _get_all_llm_tools()
        print(f"\nLLM可见工具总数: {len(tools)}")
        cat_counts = Counter(t[1].category.value for t in tools)
        for cat, count in sorted(cat_counts.items()):
            print(f"  {cat}: {count}")
        assert len(tools) >= 59


# ============================================================================
# 测试2: 每个tool的4部分逐一检查（按分类）
# ============================================================================

class TestToolFourPartConsistency:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.all_tools = _get_all_llm_tools()

    def _run_category_check(self, category: ToolCategory, cat_label: str):
        cat_tools = [t for t in self.all_tools if t[1].category == category]
        all_issues = {}
        for name, metadata, impl in cat_tools:
            issues = _check_tool_four_parts(name)
            if issues:
                all_issues[name] = issues
        if all_issues:
            msg = f"\n{cat_label}分类问题汇总 ({len(all_issues)}/{len(cat_tools)} 个工具有问题):\n"
            for name, issues in all_issues.items():
                msg += f"\n[{name}]\n" + "\n".join(issues) + "\n"
            print(msg)
        assert not all_issues, f"{cat_label}分类有{len(all_issues)}个工具存在一致性问题"

    def test_file_tools(self):
        self._run_category_check(ToolCategory.FILE, "FILE")

    def test_shell_tools(self):
        self._run_category_check(ToolCategory.SHELL, "SHELL")

    def test_network_tools(self):
        self._run_category_check(ToolCategory.NETWORK, "NETWORK")

    def test_system_tools(self):
        self._run_category_check(ToolCategory.SYSTEM, "SYSTEM")

    def test_desktop_tools(self):
        self._run_category_check(ToolCategory.DESKTOP, "DESKTOP")

    def test_document_tools(self):
        self._run_category_check(ToolCategory.DOCUMENT, "DOCUMENT")

    def test_meta_tools(self):
        self._run_category_check(ToolCategory.META, "META")


# ============================================================================
# 测试3: Schema深度检查
# ============================================================================

class TestToolSchemaDepth:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.all_tools = _get_all_llm_tools()

    def test_all_tools_schema_depth(self):
        all_issues = {}
        for name, metadata, impl in self.all_tools:
            issues = _check_schema_depth(name)
            if issues:
                all_issues[name] = issues
        if all_issues:
            msg = f"\nSchema深度问题汇总 ({len(all_issues)} 个工具有问题):\n"
            for name, issues in all_issues.items():
                msg += f"\n[{name}]\n" + "\n".join(issues) + "\n"
            print(msg)
        assert not all_issues, f"有{len(all_issues)}个工具的schema存在问题"


# ============================================================================
# 测试4: 注册信息完整性
# ============================================================================

class TestToolRegisterCompleteness:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.all_tools = _get_all_llm_tools()

    def test_all_tools_register_completeness(self):
        all_issues = {}
        for name, metadata, impl in self.all_tools:
            issues = []
            if not metadata.name:
                issues.append("  ❌ name为空")
            if not metadata.description:
                issues.append("  ❌ description为空")
            if not isinstance(metadata.category, ToolCategory):
                issues.append(f"  ❌ category无效: {metadata.category}")
            if metadata.version:
                parts = metadata.version.split(".")
                if len(parts) != 3:
                    issues.append(f"  ⚠️ version格式不标准: {metadata.version}")
            if not metadata.input_schema:
                issues.append("  ❌ input_schema为空")
            if impl is None:
                issues.append("  ❌ 无实现函数")
            elif not callable(impl):
                issues.append("  ❌ implementation不可调用")
            if issues:
                all_issues[name] = issues
        if all_issues:
            msg = f"\n注册完整性问题汇总 ({len(all_issues)} 个工具有问题):\n"
            for name, issues in all_issues.items():
                msg += f"\n[{name}]\n" + "\n".join(issues) + "\n"
            print(msg)
        assert not all_issues, f"有{len(all_issues)}个工具的注册信息不完整"


# ============================================================================
# 测试5: 分类归属正确性
# ============================================================================

class TestToolCategoryAssignment:
    def test_each_category_has_tools(self):
        for cat in ToolCategory:
            tools = tool_registry.list_tools(category=cat, include_metadata=False)
            assert len(tools) > 0, f"分类'{cat.value}'没有任何工具"

    def test_no_cross_category_duplicates(self):
        all_tool_names = []
        for cat in ToolCategory:
            cat_tools = tool_registry.list_tools(category=cat, include_metadata=False)
            for t in cat_tools:
                all_tool_names.append(t["name"])
        dupes = {name: count for name, count in Counter(all_tool_names).items() if count > 1}
        assert not dupes, f"存在跨分类重复工具: {dupes}"


# ============================================================================
# 测试6: 逐一tool参数详查（每个tool一个测试方法）
# 用parametrize为每个tool生成独立测试
# ============================================================================

def _tool_id_func(val):
    return val


@pytest.fixture(scope="module")
def all_tool_names():
    tools = _get_all_llm_tools()
    return [t[0] for t in tools]


class TestEachToolParamDetail:
    """逐一检查每个tool的参数详情"""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.all_tools = _get_all_llm_tools()
        self.tool_map = {t[0]: t for t in self.all_tools}

    @pytest.mark.parametrize("tool_name", [
        "read_file", "write_text_file", "read_media_file", "edit_file",
        "list_directory", "search_files", "grep_file_content", "rename_file",
        "archive_tool", "file_operation", "data_file_format",
        "execute_shell_command", "find_command", "shell_session",
        "execute_python", "execute_javascript",
        "http_request", "download_file", "fetch_webpage", "search_web", "network_diagnose",
        "get_system_info", "net_connections", "event_log", "list_processes",
        "kill_process", "service_control", "task_control", "get_env", "set_env",
        "registry_control",
        "list_windows", "get_window_info", "window_control", "mouse_control",
        "keyboard_control", "screen_capture", "clipboard_control", "screen_record",
        "ocr", "send_notification",
        "read_document", "write_document", "convert_document", "analyze_data",
        "filter_data", "generate_chart", "query_sql", "execute_sql", "get_db_schema",
        "tool_help", "tool_search", "pipeline", "get_time", "time_add",
        "time_diff", "query_calendar", "timezone_convert", "timer",
    ], ids=_tool_id_func)
    def test_tool_param_consistency(self, tool_name):
        """逐一检查每个tool的参数与schema一致性"""
        issues = _check_tool_four_parts(tool_name)
        if issues:
            msg = f"\n[{tool_name}] 发现{len(issues)}个问题:\n" + "\n".join(issues)
            print(msg)
        assert not issues, f"工具'{tool_name}'存在{len(issues)}个一致性问题"


# ============================================================================
# 测试7: 生成详细报告
# ============================================================================

class TestToolConsistencyReport:
    def test_generate_full_report(self):
        all_tools = _get_all_llm_tools()
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("工具4部分一致性检查完整报告 - 小健 2026-05-19")
        report_lines.append("=" * 80)
        report_lines.append(f"LLM可见工具总数: {len(all_tools)}")
        report_lines.append("")

        total_issues = 0
        tools_with_issues = 0
        issues_by_severity = {"error": 0, "warning": 0}

        for name, metadata, impl in all_tools:
            issues = _check_tool_four_parts(name)
            schema_issues = _check_schema_depth(name)
            all_tool_issues = issues + schema_issues

            if all_tool_issues:
                tools_with_issues += 1
                total_issues += len(all_tool_issues)
                for i in all_tool_issues:
                    if "❌" in i:
                        issues_by_severity["error"] += 1
                    elif "⚠️" in i:
                        issues_by_severity["warning"] += 1
                report_lines.append(f"[{metadata.category.value}] {name} - {len(all_tool_issues)}个问题:")
                for issue in all_tool_issues:
                    report_lines.append(f"  {issue}")
                report_lines.append("")

        report_lines.append("-" * 80)
        report_lines.append(f"总结: {tools_with_issues}/{len(all_tools)} 个工具有问题")
        report_lines.append(f"  ❌ 错误: {issues_by_severity['error']}个")
        report_lines.append(f"  ⚠️ 警告: {issues_by_severity['warning']}个")
        report_lines.append(f"  合计: {total_issues}个")
        report_lines.append("-" * 80)

        # 按分类统计
        cat_counts = Counter(t[1].category.value for t in all_tools)
        report_lines.append("\n各分类工具数:")
        for cat, count in sorted(cat_counts.items()):
            report_lines.append(f"  {cat}: {count}")

        report = "\n".join(report_lines)
        print(report)

        report_path = os.path.join(os.path.dirname(__file__), "tool_consistency_report.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n报告已写入: {report_path}")
