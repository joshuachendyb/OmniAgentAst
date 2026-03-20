# -*- coding: utf-8 -*-
"""
ReAct Agent Structured Outputs 实现 - Function Calling Schema 生成器

【创建时间】2026-03-20 小沈
【迁移历史】
  - 2026-03-21 小沈 - 从 agent/react_schema.py 迁移到 tools/file/file_react_schema.py
  - 2026-03-21 小沈 - 按设计文档要求迁移到 agent/types/react_schema.py

【参考】Structured-Outputs-实现方案-小沈-2026-03-20.md

功能：
1. 从 tools.py 的 Pydantic 模型生成 OpenAI Function Calling 格式的 Schema
2. 支持 LongCat 等支持 tools 参数的 LLM
3. 通过强制 Schema 约束确保参数名正确

原理：
- Function Calling 强制 LLM 使用 Schema 中定义的参数名
- 无法输出 "directory_path"，只能是 "dir_path"
- 消除了 agent.py 中参数映射容错代码的必要

更新时间: 2026-03-21 07:15:00
"""

import json
from typing import Any, Dict, List, Optional

from app.services.tools.file.file_tools import (
    FileTools,
    get_registered_tools,
    get_tool,
)


def get_tools_schema_for_function_calling() -> List[Dict[str, Any]]:
    """
    获取 OpenAI Function Calling 格式的工具 Schema
    
    从 tools.py 的 Pydantic 模型生成 OpenAI 兼容的 tools 参数
    
    Returns:
        OpenAI 格式的 tools 列表，可以直接用于 API 请求的 tools 参数
    
    示例返回格式:
    [
        {
            "type": "function",
            "function": {
                "name": "list_directory",
                "description": "列出目录内容...",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dir_path": {
                            "type": "string",
                            "description": "目录的完整路径"
                        },
                        ...
                    },
                    "required": ["dir_path"]
                }
            }
        },
        ...
    ]
    """
    tools = get_registered_tools()
    
    openai_tools = []
    for tool in tools:
        name = tool.get("name", "")
        description = tool.get("description", "") or ""
        input_schema = tool.get("input_schema", {})
        examples = tool.get("input_examples", [])
        
        processed_description = _process_description(description)
        
        properties = input_schema.get("properties", {})
        required = input_schema.get("required", [])
        
        cleaned_properties = _clean_properties(properties)
        
        openai_tool = {
            "type": "function",
            "function": {
                "name": name,
                "description": processed_description,
                "parameters": {
                    "type": "object",
                    "properties": cleaned_properties,
                    "required": required if required else []
                }
            }
        }
        
        if examples:
            example_hints = _generate_example_hints(name, examples)
            if example_hints:
                openai_tool["function"]["description"] += f"\n\n{example_hints}"
        
        openai_tools.append(openai_tool)
    
    return openai_tools


def _process_description(description: str) -> str:
    """
    处理工具描述，提取关键信息
    
    移除 FORBIDDEN 规则（LLM 无法看到 Function Calling 的描述），
    但保留参数约束说明
    """
    if not description:
        return ""
    
    lines = description.split("\n")
    processed_lines = []
    
    skip_patterns = [
        "【重要】必须使用",
        "错误示例:",
        "正确示例:",
        "FORBIDDEN",
        "【注意】",
        "【警告】"
    ]
    
    for line in lines:
        if any(pattern in line for pattern in skip_patterns):
            continue
        processed_lines.append(line)
    
    return "\n".join(processed_lines).strip()


def _clean_properties(properties: Dict[str, Any]) -> Dict[str, Any]:
    """
    清理 JSON Schema properties
    
    移除 OpenAI 不需要的字段，只保留：
    - type
    - description
    - enum (如果有)
    - 数值类型的 minimum, maximum (如果有)
    """
    cleaned = {}
    
    for param_name, param_schema in properties.items():
        if not isinstance(param_schema, dict):
            continue
        
        clean_param = {}
        
        param_type = _extract_type(param_schema)
        if param_type:
            clean_param["type"] = param_type
        
        if "description" in param_schema:
            desc = param_schema["description"]
            if "【重要】" in desc:
                important_parts = [p for p in desc.split("\n") if "【重要】" in p]
                if important_parts:
                    clean_param["description"] = important_parts[0].replace("【重要】", "").strip()
                else:
                    clean_param["description"] = desc.split("\n")[0]
            else:
                clean_param["description"] = desc.split("\n")[0].strip()
        
        if "enum" in param_schema:
            clean_param["enum"] = param_schema["enum"]
        
        if "minimum" in param_schema:
            clean_param["minimum"] = param_schema["minimum"]
        if "maximum" in param_schema:
            clean_param["maximum"] = param_schema["maximum"]
        
        if "default" in param_schema:
            clean_param["default"] = param_schema["default"]
        
        cleaned[param_name] = clean_param
    
    return cleaned


def _extract_type(param_schema: Dict[str, Any]) -> Optional[str]:
    """
    从 JSON Schema 中提取类型信息
    
    处理以下情况：
    1. 直接的 type 字段: {"type": "string"}
    2. anyOf 格式: {"anyOf": [{"type": "string"}, {"type": "null"}]}
    3. oneOf 格式: {"oneOf": [{"type": "string"}, {"type": "null"}]}
    """
    if "type" in param_schema:
        return param_schema["type"]
    
    if "anyOf" in param_schema:
        types = set()
        for item in param_schema["anyOf"]:
            if isinstance(item, dict) and "type" in item:
                types.add(item["type"])
        
        if "string" in types:
            return "string"
        if "boolean" in types:
            return "boolean"
        if "integer" in types:
            return "integer"
        if "number" in types:
            return "number"
        if "object" in types:
            return "object"
        if "array" in types:
            return "array"
    
    if "oneOf" in param_schema:
        types = set()
        for item in param_schema["oneOf"]:
            if isinstance(item, dict) and "type" in item:
                types.add(item["type"])
        
        if "string" in types:
            return "string"
        if "boolean" in types:
            return "boolean"
        if "integer" in types:
            return "integer"
        if "number" in types:
            return "number"
    
    return None


def _generate_example_hints(tool_name: str, examples: List[Dict[str, Any]]) -> str:
    """
    生成示例提示，帮助 LLM 理解正确的参数格式
    """
    if not examples:
        return ""
    
    hints = ["使用示例:"]
    
    for i, example in enumerate(examples[:2], 1):
        hint_lines = []
        for key, value in example.items():
            hint_lines.append(f"  {key}: {value}")
        hints.append(f"示例{i}:")
        hints.extend(hint_lines)
    
    return "\n".join(hints)


def get_tool_schema(tool_name: str) -> Optional[Dict[str, Any]]:
    """
    获取单个工具的 Function Calling Schema
    
    Args:
        tool_name: 工具名称
        
    Returns:
        工具的 OpenAI Function Calling Schema，如果不存在返回 None
    """
    tools = get_tools_schema_for_function_calling()
    for tool in tools:
        if tool.get("function", {}).get("name") == tool_name:
            return tool
    return None


def validate_tool_call(tool_call: Dict[str, Any]) -> Dict[str, Any]:
    """
    验证和解析 Function Calling 返回的工具调用
    
    Args:
        tool_call: LLM 返回的 tool_call 对象
        
    Returns:
        解析后的工具调用信息，包含:
        - tool_name: 工具名称
        - arguments: 解析后的参数字典
        - raw_arguments: 原始参数字符串
        - error: 如果解析失败，错误信息
    """
    result = {
        "tool_name": None,
        "arguments": {},
        "raw_arguments": "",
        "error": None
    }
    
    func = tool_call.get("function", {})
    tool_name = func.get("name")
    if not tool_name:
        result["error"] = "Missing tool name in function call"
        return result
    
    result["tool_name"] = tool_name
    
    arguments_str = func.get("arguments", "{}")
    result["raw_arguments"] = arguments_str
    
    try:
        if isinstance(arguments_str, str):
            result["arguments"] = json.loads(arguments_str)
        elif isinstance(arguments_str, dict):
            result["arguments"] = arguments_str
        else:
            result["arguments"] = {}
    except json.JSONDecodeError as e:
        result["error"] = f"Failed to parse arguments: {e}"
        return result
    
    tool_schema = get_tool_schema(tool_name)
    if tool_schema:
        params_schema = tool_schema.get("function", {}).get("parameters", {})
        required = params_schema.get("required", [])
        
        missing_params = [p for p in required if p not in result["arguments"]]
        if missing_params:
            result["error"] = f"Missing required parameters: {missing_params}"
    
    return result


def get_available_tools() -> List[str]:
    """
    获取所有可用工具的名称列表
    
    Returns:
        工具名称列表
    """
    tools = get_registered_tools()
    return [tool.get("name", "") for tool in tools if tool.get("name")]


def get_finish_tool_schema() -> Dict[str, Any]:
    """
    获取 finish 工具的 Schema
    
    finish 不是真正的工具调用，而是用于结束 ReAct 循环
    """
    return {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "结束任务，返回最终结果。当用户请求已经满足时使用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "result": {
                        "type": "string",
                        "description": "任务完成的结果或总结"
                    },
                    "success": {
                        "type": "boolean",
                        "description": "任务是否成功完成",
                        "default": True
                    }
                },
                "required": ["result"]
            }
        }
    }


__all__ = [
    "get_tools_schema_for_function_calling",
    "get_tool_schema",
    "validate_tool_call",
    "get_available_tools",
    "get_finish_tool_schema",
    "_process_description",
    "_clean_properties",
    "_extract_type",
    "_generate_example_hints",
]
