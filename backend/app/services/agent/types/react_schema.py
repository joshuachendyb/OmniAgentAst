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
from typing import Any, Dict, List, Optional, Callable

from app.services.tools.registry import tool_registry
from app.utils.logger import logger


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
    tools = tool_registry.list_tools(expose_to_llm_only=True)
    
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
    
    # ===== 添加 finish 工具（2026-04-23 小沈修复）=====
    # finish 不是真正的工具调用，而是用于结束 ReAct 循环
    openai_tools.append(get_finish_tool_schema())
    
    return openai_tools


def _process_description(description: str) -> str:
    """
    处理工具描述，提取关键信息
    
    【G3修复】2026-05-09 小沈
    只移除 FORBIDDEN 规则和示例行，保留【重要】【注意】【警告】等关键提示。
    原逻辑无差别跳过所有带【重要】【注意】【警告】的行，导致重要约束丢失。
    """
    if not description:
        return ""
    
    lines = description.split("\n")
    processed_lines = []
    
    for line in lines:
        if "FORBIDDEN" in line:
            continue
        if line.strip().startswith("错误示例:") or line.strip().startswith("正确示例:"):
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
            if desc:
                clean_param["description"] = desc.replace("\n", " ").replace("\r", "").strip()
        
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


_TYPE_ORDER = ["string", "integer", "number", "boolean", "object", "array", "null"]


def _extract_type(param_schema: Dict[str, Any]) -> Optional[str]:
    """
    从 JSON Schema 中提取类型信息
    
    处理以下情况：
    1. 直接的 type 字段: {"type": "string"}
    2. anyOf 格式: {"anyOf": [{"type": "string"}, {"type": "null"}]}
    3. oneOf 格式: {"oneOf": [{"type": "string"}, {"type": "null"}]}
    
    【G1修复】2026-05-09 小沈
    Union类型不再简化为单一类型，用逗号拼接保留所有类型信息。
    例: anyOf:[integer,number,string,null] → "integer,number,string"
    与registry.py的_fix_schema_types()保持一致。
    """
    if "type" in param_schema:
        return param_schema["type"]
    
    if "anyOf" in param_schema:
        types = set()
        for item in param_schema["anyOf"]:
            if isinstance(item, dict) and "type" in item:
                t = item["type"]
                if t != "null":
                    types.add(t)
        if types:
            sorted_types = sorted(types, key=lambda x: _TYPE_ORDER.index(x) if x in _TYPE_ORDER else 99)
            return ",".join(sorted_types)
        return "string"
    
    if "oneOf" in param_schema:
        types = set()
        for item in param_schema["oneOf"]:
            if isinstance(item, dict) and "type" in item:
                t = item["type"]
                if t != "null":
                    types.add(t)
        if types:
            sorted_types = sorted(types, key=lambda x: _TYPE_ORDER.index(x) if x in _TYPE_ORDER else 99)
            return ",".join(sorted_types)
        return "string"
    
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
    tools = tool_registry.list_tools(expose_to_llm_only=True)
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
    "get_tools_schema_for_intent_distribution",
    "get_tools_schema_for_categories",
    "_process_description",
    "_clean_properties",
    "_extract_type",
    "_generate_example_hints",
]


def get_tools_schema_for_categories(categories: List[Any]) -> List[Dict[str, Any]]:
    """
    根据分类列表获取工具Schema
    
    【步骤9】用于动态加载工具时的Schema生成
    
    Args:
        categories: ToolCategory分类列表
        
    Returns:
        OpenAI格式的tools Schema列表
    """
    from app.services.tools.registry import get_tools_from_registry_by_category
    
    openai_tools = []
    
    for category in categories:
        # get_tools_from_registry_by_category返回 Dict[str, Callable]
        tools_dict: Dict[str, Callable] = get_tools_from_registry_by_category(category)
        
        # 从metadata获取详细信息（registry存储了工具元数据）
        tool_list = tool_registry.list_tools(category=category, include_metadata=True)
        tool_metadata = {t["name"]: t for t in tool_list if isinstance(t, dict)}
        
        for name, func in tools_dict.items():
            # 获取metadata
            meta = tool_metadata.get(name, {})
            description = meta.get("description", "") or ""
            input_schema = meta.get("input_schema", {})
            examples = meta.get("input_examples", [])
            
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
    
    # 添加 finish 工具
    openai_tools.append(get_finish_tool_schema())
    
    return openai_tools


def get_tools_schema_for_intent_distribution(
    intent_dist: Dict[str, float],
    top_n: int = 2,
    conf_threshold: float = 0.3,
    brief_threshold: float = 0.1
) -> tuple[List[Dict[str, Any]], str]:
    """
    根据意图置信度分布，返回混合Schema（高置信度详细，其他简要）
    
    【步骤8】实现文档4.14节缺陷2修正：置信度阈值无降级策略
    
    Args:
        intent_dist: 意图置信度分布 {"file": 0.85, "time": 0.60, "shell": 0.15}
        top_n: 前N个高置信度意图给详细Schema（默认2）
        conf_threshold: 置信度阈值，低于此值的不加载详细Schema（默认0.3）
        brief_threshold: 简要清单阈值，高于此值的低置信度意图列入简要清单（默认0.1）
    
    Returns:
        (openai_tools, brief_tools_hint): 详细Schema列表 + 简要清单提示
    
    设计说明：
    1. 高置信度（>=conf_threshold）：完整详细Schema（Pydantic模型）
    2. 低置信度（>=brief_threshold）：只给简要清单，不加载详细Schema
    3. 极低置信度（<brief_threshold）：完全忽略
    4. 所有工具置信度都低于阈值：降级返回通用工具清单
    """
    from app.services.tools.registry import tool_registry
    from app.services.tools.registry import ToolCategory
    
    # 1. 排序意图
    sorted_intents = sorted(intent_dist.items(), key=lambda x: x[1], reverse=True)
    
    openai_tools = []
    loaded_categories = set()
    brief_intents = []
    
    # 2. 高置信度意图：详细Schema（阈值0.3）
    for intent, score in sorted_intents[:top_n]:
        if score < conf_threshold:
            # 低于阈值的跳过详细Schema，加入简要清单（如果>=brief_threshold）
            if score >= brief_threshold:
                brief_intents.append(f"- {intent}类工具（置信度{score:.2f}）")
            continue
        
        try:
            category = ToolCategory(intent)
            tools = tool_registry.get_tools(category)
            for tool in tools:
                schema = _build_detailed_schema(tool)
                openai_tools.append(schema)
            loaded_categories.add(intent)
        except ValueError:
            logger.warning(f"[Schema] 意图'{intent}'无对应工具分类，跳过")
    
    # 3. 低置信度意图：只给简要清单（阈值0.1）
    for intent, score in sorted_intents[top_n:]:
        if score >= brief_threshold:
            brief_intents.append(f"- {intent}类工具（置信度{score:.2f}）")
    
    # 4. 构建简要清单提示
    brief_tools_hint = ""
    if brief_intents:
        brief_tools_hint = "\n【可用但未加载详细说明的工具】\n"
        brief_tools_hint += "\n".join(brief_intents)
        brief_tools_hint += "\n如需使用，请说明需求，我将动态加载。"
    
    # 5. 全部置信度低于阈值：降级返回通用工具清单
    if not openai_tools:
        logger.warning(f"[Schema] 所有意图置信度<{conf_threshold}，降级为通用工具清单")
        return get_tools_schema_for_function_calling()[:10], "【通用工具清单】置信度过低，仅提供基础工具"
    
    return openai_tools, brief_tools_hint


def _build_detailed_schema(tool: Any) -> Dict[str, Any]:
    """构建详细Schema（Pydantic模型）"""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.input_schema
        }
    }



