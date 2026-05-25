# -*- coding: utf-8 -*-
"""
ReAct输出统一解析器模块

用一个统一的解析器入口处理LLM的所有ReAct输出格式
支持中英文关键词、五级JSON降级、明确type类型区分

Author: 小沈
Date: 2026-04-16
Version: 1.0

设计依据: 附件-React重构0.9.5X的解析步骤设计附件 第14章
"""

import re
import json
from typing import Dict, Any, Optional, Tuple, List

from app.utils.logger import logger


# =============================================================================
# 【改进7 2026-05-01 小沈 小健】reasoning验证辅助函数
# =============================================================================

_REASONING_MIN_LENGTH = 10


def _add_reasoning_warning(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    检查tool call的reasoning字段是否为空或过短，附加parse_warning

    当LLM跳过reasoning（直接输出thought+tool_name），标记warning但不阻塞流程。
    调用方(base_react.py)可根据parse_warning决定是否在Observation中附加警告。

    Args:
        result: 解析结果字典

    Returns:
        可能附加了parse_warning的同一个字典（原地修改后返回）
    """
    if result.get("tool_name") and not result.get("parse_warning"):
        reasoning = result.get("reasoning", "")
        if not reasoning or len(reasoning.strip()) < _REASONING_MIN_LENGTH:
            result["parse_warning"] = (
                "⚠️ reasoning字段为空或过短(<10字符)。"
                "有效的reasoning应包含：为什么选择这个工具、参数如何确定。"
            )
    return result


# =============================================================================
# 【修复A2+A3 2026-05-20 小健】finish result 类型标准化共享函数
# =============================================================================

def _normalize_result_to_str(raw_result) -> str:
    """
    将finish的result字段标准化为字符串类型

    解决旧格式路径和混合文本路径中result字段缺类型标准化的问题(A2+A3)。
    新格式路径(_build_action_from_new_format)已有此逻辑，此函数提取为共享实现。

    标准化规则:
    - int/float → str(value)
    - bool → str(value)  注意: bool检查必须在int/float之前(isinstance(True, int)为True)
    - list/dict → json.dumps(value, ensure_ascii=False)
    - str → 原值返回
    - None/其他 → 空字符串

    作者: 小健 2026-05-20
    """
    if isinstance(raw_result, bool):
        return str(raw_result)
    elif isinstance(raw_result, (int, float)):
        return str(raw_result)
    elif isinstance(raw_result, (list, dict)):
        return json.dumps(raw_result, ensure_ascii=False)
    elif isinstance(raw_result, str):
        return raw_result
    else:
        return ""


# =============================================================================
# 步骤1.1：定义REACT_KEYWORDS中英文关键词映射表
# =============================================================================

# 【基于14.0分析增强】中文关键词模式来源：
# - tool_parser.py action_patterns (行245-261) 中的中文模式提取
# - 支持更灵活的中文动词+工具名匹配
REACT_KEYWORDS = {
    "thought": r"(?:Thought|思考|推理):\s*",
    "action": r"(?:Action|行动|工具调用|(?:调用|使用|执行)\s+|(?:工具|函数)\s*为):\s*",
    "action_input": r"(?:Action Input|工具参数|输入|参数):\s*",
    "answer": r"(?:Answer|回答|最终答案|结论):\s*",
}


def _get_all_tool_names():
    """从tool_registry获取所有已注册工具名 - 小健 2026-05-02"""
    try:
        from app.services.tools.registry import tool_registry
        tools = tool_registry.list_tools(include_metadata=False)
        # 【修复 2026-05-05 小沈】list_tools返回dict列表，提取name字段
        return [t["name"] if isinstance(t, dict) else t for t in tools]
    except Exception:
        return ["list_directory", "read_file", "write_file", "delete_file",
                "move_file", "search_files", "grep_file_content", "generate_report",
                "execute_command", "run_command", "get_current_time", "get_system_info",
                "finish", "finish_with_error"]


# =============================================================================
# 步骤1.1：定义parse_react_response函数签名
# =============================================================================

# =============================================================================
# 解析器链 - 统一入口（重构于 2026-05-19 小沈）
# 设计原则：每个handler独立处理一种输入格式，返回结果或None
# 添加新格式 = 写新handler → 插入_HANDLERS列表
# =============================================================================

def _process_json_result(data: Dict, output: str) -> Optional[Dict[str, Any]]:
    """
    共享逻辑：处理已解析的JSON dict（消除标准JSON和非标准JSON路径的重复代码）
    
    此函数被 _handle_standard_json 和 _handle_non_standard_json 共同使用，
    处理 type=parse_error/answer/chunk、tool_name(新格式)、action(旧格式) 等分支。
    如果data不匹配任何已知模式，返回None交给后续handler。
    
    作者: 小沈 2026-05-19
    """
    # 显式type优先判断（避免被tool_name误判为action）
    explicit_type = data.get("type")
    if explicit_type == "parse_error":
        return _build_parse_error_result(data)
    if explicit_type == "answer":
        return _build_answer_result(data)
    if explicit_type == "chunk":
        return _build_chunk_result(data)
    
    # 新字段格式 (tool_name)
    if "tool_name" in data:
        return _build_action_from_new_format(data, output)
    
    # OpenAI function calling 格式 (name + arguments)
    if "name" in data and ("arguments" in data or "args" in data):
        return _build_action_from_fc_format(data, output)
    
    # 旧字段格式 (action/action_input)
    if "action" in data:
        return _build_action_from_old_format(data, output)
    
    # 无匹配模式 → 交给下一个handler
    return None


def _build_parse_error_result(data: Dict) -> Dict[str, Any]:
    """构造 parse_error 类型结果"""
    return {
        "type": "parse_error",
        "error": data.get("error", "LLM返回解析错误"),
        "thought": data.get("content", data.get("thought", "")),
        "content": data.get("content", ""),
        "reasoning": data.get("reasoning", ""),
        "tool_name": None,
        "tool_params": None,
        "response": data.get("content", "")
    }


def _build_answer_result(data: Dict) -> Dict[str, Any]:
    """构造 answer 类型结果"""
    return {
        "type": "answer",
        "thought": data.get("thought", ""),
        "content": data.get("content", ""),
        "reasoning": data.get("reasoning", ""),
        "tool_name": None,
        "tool_params": None,
        "response": data.get("response", data.get("content", ""))
    }


def _build_chunk_result(data: Dict) -> Dict[str, Any]:
    """构造 chunk 类型结果"""
    return {
        "type": "chunk",
        "thought": data.get("thought", ""),
        "content": data.get("content", ""),
        "reasoning": data.get("reasoning", ""),
        "tool_name": None,
        "tool_params": None,
        "response": data.get("response", data.get("content", "")),
        "error": None
    }


def _process_tool_params(tool_params, tool_name=None, raw_output=None):
    """
    统一工具参数处理管道: normalize → filter → supplement
    
    消除标准JSON、非标准JSON、混合文本JSON、_determine_parse_type 
    四条路径中 tool_params 处理步骤不一致的问题（缺陷2修复）。
    
    作者: 小沈 2026-05-19
    """
    if not isinstance(tool_params, dict):
        return tool_params
    
    tool_params = _normalize_tool_params_content(tool_params)
    tool_params = _filter_tool_params(tool_params)
    
    if tool_name and tool_name != "finish" and tool_params:
        tool_params = _supplement_missing_params(
            tool_name, tool_params,
            raw_output if isinstance(raw_output, str) else None
        )
    
    return tool_params


def _build_action_from_fc_format(data: Dict, output: str) -> Dict[str, Any]:
    """
    从OpenAI function calling格式构造action结果
    
    LLM在text策略下可能幻觉输出FC格式: {"name": "xxx", "arguments": {...}}
    将其转换为标准ReAct action格式。
    
    小健 2026-05-24
    """
    tool_name = data["name"]
    is_finish = tool_name == "finish"
    
    raw_args = data.get("arguments", data.get("args", {}))
    if isinstance(raw_args, str):
        try:
            raw_args = json.loads(raw_args)
        except (json.JSONDecodeError, TypeError):
            raw_args = {}
    if not isinstance(raw_args, dict):
        raw_args = {}
    
    if is_finish and raw_args.get("result"):
        raw_result = raw_args["result"]
        response = _normalize_result_to_str(raw_result)
    else:
        response = ""
    
    processed_params = None if is_finish else _process_tool_params(raw_args, tool_name, output)
    
    result = {
        "type": "answer" if is_finish else "action",
        "thought": data.get("thought", ""),
        "content": data.get("thought", ""),
        "reasoning": data.get("reasoning", ""),
        "tool_name": None if is_finish else tool_name,
        "tool_params": processed_params,
        "response": response,
    }
    
    logger.info(f"[parse_react_response] FC格式转换: name={tool_name} → type={result['type']}")
    return _add_reasoning_warning(result)


def _build_action_from_new_format(data: Dict, output: str) -> Dict[str, Any]:
    """从新格式JSON构造action/answer结果（tool_name/tool_params）"""
    tool_name = data["tool_name"]
    is_finish = tool_name == "finish"
    
    # response处理：finish类型从tool_params.result获取
    # 【修复 2026-05-19 小沈】result字段标准化：数字/布尔/list/dict→字符串
    if is_finish and data.get("tool_params", {}).get("result"):
        raw_result = data["tool_params"]["result"]
        response = _normalize_result_to_str(raw_result)
    else:
        response = data.get("response", "")
    
    raw_params = data.get("tool_params", data.get("args", {}))
    processed_tool_params = None if is_finish else _process_tool_params(
        raw_params, tool_name, output
    )
    
    result = {
        "type": "answer" if is_finish else "action",
        "thought": data.get("content", data.get("thought", "")),
        "content": data.get("content", data.get("thought", "")),
        "reasoning": data.get("reasoning", ""),
        "tool_name": None if is_finish else tool_name,
        "tool_params": processed_tool_params,
        "response": response
    }
    if "_pending_calls" in data:
        result["_pending_calls"] = data["_pending_calls"]
    return result


def _build_action_from_old_format(data: Dict, output: str = "") -> Dict[str, Any]:
    """从旧格式JSON构造action/answer结果（action/action_input）

    【修复A2 2026-05-20 小健】finish result 使用 _normalize_result_to_str 标准化
    【修复A1 2026-05-20 小健】tool_params 使用 _process_tool_params 统一管道
    """
    action_name = data["action"]
    is_finish = action_name == "finish"

    if is_finish and data.get("action_input", {}).get("result"):
        raw_result = data["action_input"]["result"]
        response = _normalize_result_to_str(raw_result)
    else:
        response = ""

    raw_params = data.get("action_input", data.get("args", {}))
    processed_tool_params = None if is_finish else _process_tool_params(
        raw_params, action_name, output
    )
    result = {
        "type": "answer" if is_finish else "action",
        "thought": data.get("thought", ""),
        "content": data.get("thought", ""),
        "reasoning": data.get("reasoning", ""),
        "tool_name": None if is_finish else action_name,
        "tool_params": processed_tool_params,
        "response": response
    }
    if "_pending_calls" in data:
        result["_pending_calls"] = data["_pending_calls"]
    return result


# ---------------------------------------------------------------------------
# Handler #1: dict 输入
# ---------------------------------------------------------------------------
def _handle_dict_input(output) -> Optional[Dict[str, Any]]:
    if isinstance(output, dict):
        logger.info(f"[parse_react_response] 检测到dict输入，直接解析")
        return _create_action_result_from_dict(output)
    return None


# ---------------------------------------------------------------------------
# Handler #2: list 输入
# ---------------------------------------------------------------------------
def _handle_list_input(output) -> Optional[Dict[str, Any]]:
    if isinstance(output, list):
        logger.info(f"[parse_react_response] 检测到list输入，解析数组")
        return _create_action_result_from_list(output)
    return None


# ---------------------------------------------------------------------------
# Handler #3: JSON数组字符串 (以'['开头)
# ---------------------------------------------------------------------------
def _handle_json_array_string(output) -> Optional[Dict[str, Any]]:
    if isinstance(output, str) and output.strip().startswith("["):
        try:
            parsed_list = json.loads(output)
            if isinstance(parsed_list, list):
                logger.info(f"[parse_react_response] 检测到JSON数组字符串，解析为list处理")
                return _create_action_result_from_list(parsed_list)
        except (json.JSONDecodeError, TypeError):
            pass
    return None


# ---------------------------------------------------------------------------
# Handler #4: 空值/非字符串输入
# ---------------------------------------------------------------------------
def _handle_empty_input(output) -> Optional[Dict[str, Any]]:
    if not output or not isinstance(output, str):
        thought = "(Implicit) Empty response"
        return {
            "type": "parse_error",
            "error": "Empty or non-string response from LLM",
            "thought": thought,
            "content": thought,
            "reasoning": thought,
            "tool_name": None,
            "tool_params": None,
            "response": ""
        }
    return None


# ---------------------------------------------------------------------------
# Handler #5: 标准JSON (json.loads)
# ---------------------------------------------------------------------------
def _handle_standard_json(output) -> Optional[Dict[str, Any]]:
    if not isinstance(output, str):
        return None
    try:
        data = json.loads(output)
    except (json.JSONDecodeError, TypeError):
        return None
    
    if not isinstance(data, dict):
        return None
    
    result = _process_json_result(data, output)
    if result is not None:
        return result
    # data是dict但无匹配模式 → 交给后续handler
    return None


# ---------------------------------------------------------------------------
# Handler #6: 非标准JSON (单引号)
# ---------------------------------------------------------------------------
def _handle_non_standard_json(output) -> Optional[Dict[str, Any]]:
    if not isinstance(output, str):
        return None
    non_std_data = _try_parse_non_standard_json(output)
    if not non_std_data or not isinstance(non_std_data, dict):
        return None
    
    # _process_json_result 与标准JSON路径完全相同
    result = _process_json_result(non_std_data, output)
    if result is not None:
        # 补充非标准JSON路径特有的内容字段处理
        if result.get("type") == "parse_error":
            result["error"] = non_std_data.get("error", "非标准JSON解析错误")
        logger.info(f"[parse_react_response] 非标准JSON解析成功")
        return result
    return None


# ---------------------------------------------------------------------------
# Handler #7: 混合文本中提取JSON块 + 不完整JSON检测
# ---------------------------------------------------------------------------

# 【24.4.4 组件1】统一 handler 结果构建(消除 4 个 8 字段 dict 重复)
def _build_handler_result(type_: str, thought: str = "", content: str = "",
                           reasoning: str = "", tool_name: Optional[str] = None,
                           tool_params: Optional[Dict] = None,
                           response: Any = None, error: Optional[str] = None) -> Dict[str, Any]:
    """构建统一 handler 结果 — 小健 2026-05-25"""
    return {
        "type": type_, "thought": thought, "content": content or thought,
        "reasoning": reasoning, "tool_name": tool_name, "tool_params": tool_params or {},
        "response": response or thought, "error": error,
    }


def _handle_mixed_text_json(output) -> Optional[Dict[str, Any]]:
    """
    处理从混合文本中提取JSON的场景，包括不完整JSON检测。
    当前代码 lines 313-437 的逻辑整体迁移。
    作者: 小沈 2026-05-19
    """
    # 【24.4.4 重构后主函数】~70行骨架
    if not isinstance(output, str):
        return None

    json_data = _extract_json_block(output)
    prefix_text = ""
    if json_data:
        json_start = output.find("{")
        prefix_text = output[:json_start].strip() if json_start != -1 else ""

    # 不完整 JSON 检测
    if not json_data:
        if re.match(r'^\s*\{\s*"thought":\s*"', output):
            regex_recovered = _try_regex_tool_call_fallback(output)
            if regex_recovered:
                logger.info("不完整JSON但正则兜底提取到tool调用")
                return _add_reasoning_warning(regex_recovered)
            thought_text = output.strip()
            logger.info("检测到不完整JSON格式，返回chunk")
            return _build_handler_result("chunk", thought=thought_text)
        return None

    if not isinstance(json_data, dict):
        return None

    tool_name = json_data.get("tool_name")
    tool_params = json_data.get("tool_params", {})
    if not isinstance(tool_params, dict):
        tool_params = {}

    # finish
    if tool_name == "finish":
        raw_result = tool_params.get("result") if tool_params else None
        result_text = _normalize_result_to_str(raw_result) if raw_result is not None else ""
        content = result_text or prefix_text
        return _build_handler_result("answer", thought=json_data.get("thought", ""),
            content=content, response=content)

    # action
    if tool_name:
        extracted = json_data.get("content", "") or prefix_text
        params = _process_tool_params(tool_params, tool_name, output)
        return _build_handler_result("action", thought=json_data.get("thought", ""),
            content=extracted, tool_name=tool_name, tool_params=params)

    # implicit
    if "content" in json_data or "reasoning" in json_data:
        if not re.search(r'\bAction\s*:', output, re.IGNORECASE) and \
           not re.search(r'\bAnswer\s*:', output, re.IGNORECASE):
            content = json_data.get("content", "")
            reasoning = json_data.get("reasoning", "")
            # 嵌套 JSON 提取(防御性)
            if isinstance(content, str) and content.startswith("{"):
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict):
                        content = parsed.get("content", content)
                except (json.JSONDecodeError, TypeError):
                    pass
            return _build_handler_result("implicit", thought=prefix_text or content,
                content=content, reasoning=reasoning, response=content)

    return None


# ---------------------------------------------------------------------------
# Handler #8: 正则兜底
# ---------------------------------------------------------------------------
def _handle_regex_fallback(output) -> Optional[Dict[str, Any]]:
    if not isinstance(output, str):
        return None
    regex_recovered = _try_regex_tool_call_fallback(output)
    if regex_recovered:
        logger.info("[parse_react_response] 正则兜底提取到 tool 调用，跳过关键词匹配")
        return _add_reasoning_warning(regex_recovered)
    return None


# ---------------------------------------------------------------------------
# Handler #9: 关键词匹配（最终兜底）
# ---------------------------------------------------------------------------
def _handle_keyword_match(output) -> Optional[Dict[str, Any]]:
    logger.info(f"[parse_react_response] 走关键词匹配流程")
    return _determine_parse_type(output) if isinstance(output, str) else None


# ---------------------------------------------------------------------------
# 解析器链配置：按优先级顺序排列
# ---------------------------------------------------------------------------
_HANDLERS = [
    _handle_dict_input,          # 1: dict → action/implicit
    _handle_list_input,          # 2: list → action
    _handle_json_array_string,   # 3: "[...]" → 解析为list
    _handle_empty_input,         # 4: None/空/非字符串 → parse_error
    _handle_standard_json,       # 5: json.loads → 各种type
    _handle_non_standard_json,   # 6: 单引号JSON → 各种type
    _handle_mixed_text_json,     # 7: 混合文本提取JSON + 不完整JSON
    _handle_regex_fallback,      # 8: 正则兜底提取工具调用
    _handle_keyword_match,       # 9: 关键词匹配(_determine_parse_type)
]


def parse_react_response(output: str) -> Dict[str, Any]:
    """
    统一解析器入口函数 - 解析器链模式（重构于 2026-05-19 小沈）
    
    处理LLM的所有ReAct输出格式，返回统一结构字典。
    通过type字段区分：action/answer/implicit/thought_only/parse_error/chunk
    
    架构：9个handler按优先级顺序尝试，每个返回结果或None（交给下一个）。
    添加新LLM格式 = 写新handler → 插入_HANDLERS列表 → 零风险。
    
    Args:
        output: LLM原始响应文本（可为str/dict/list）
        
    Returns:
        统一格式字典，包含type/thought/tool_name/tool_params/response/content/reasoning字段
        
    设计依据: LlamaIndex ReActOutputParser.parse() + 解析器链(Chain of Responsibility)模式
    """
    # 日志记录（迁移自旧代码 lines 125-126）
    output_length = len(output) if isinstance(output, str) else 0
    logger.info(f"[parse_react_response] 解析器链开始, output长度: {output_length}")
    
    for handler in _HANDLERS:
        result = handler(output)
        if result is not None:
            return result
    
    # 理论上不可达（最后一个handler _handle_keyword_match 总是返回结果）
    logger.error("[parse_react_response] 所有handler返回None，解析器链异常")
    return {
        "type": "parse_error",
        "error": "Parser chain exhausted",
        "thought": "(Implicit) Internal error",
        "content": "",
        "reasoning": "",
        "tool_name": None,
        "tool_params": None,
        "response": ""
    }


# =============================================================================
# 步骤1.2：实现四种情况判断逻辑
# =============================================================================

# 【24.1.4 组件2/3 常量】工具名/参数名降级映射 — 小健 2026-05-25
_TOOL_NAME_FALLBACK_KEYS = ["action", "action_tool", "tool_name"]
_TOOL_PARAMS_FALLBACK_KEYS = ["params", "action_input", "actionInput"]


# 【24.1.4 组件1】统一 action 结果构建(消除 2 个 return dict 的 6 字段重复)
def _build_action_result(type_: str, tool_name: str, tool_params: Dict[str, Any],
                          thought: str, error: Optional[str] = None) -> Dict[str, Any]:
    """构建统一 action 结果 — 小健 2026-05-25"""
    return {
        "type": type_,
        "thought": thought,
        "content": thought,      # 兼容字段，可随版本逐步废弃
        "reasoning": thought,    # 兼容字段，可随版本逐步废弃
        "tool_name": tool_name,
        "tool_params": tool_params,
        "response": None,
        "error": error,
    }


# 【24.1.4 组件2】从 tool_params 兜底提取工具名(消除 M1a 3 个连续 if)
def _fallback_tool_name(tool_params: Dict[str, Any], current: str) -> str:
    """从 tool_params 中按优先级兜底查找工具名 — 小健 2026-05-25"""
    if current:
        return current
    for key in _TOOL_NAME_FALLBACK_KEYS:
        if key in tool_params:
            return tool_params.pop(key)
    return ""


# 【24.1.4 组件3】统一参数名映射(消除 M1b 3 个连续 if)
def _normalize_tool_params(tool_params: Dict[str, Any]) -> Dict[str, Any]:
    """将不同 LLM 输出的参数名统一为 tool_params — 小健 2026-05-25"""
    if "tool_params" in tool_params:
        return tool_params
    for key in _TOOL_PARAMS_FALLBACK_KEYS:
        if key in tool_params:
            tool_params["tool_params"] = tool_params.pop(key)
            break
    return tool_params


# 【小沈重构 2026-05-25】25.2节：提取3个独立解析器，消除SLAP/DRY违反
def _try_codeblock_parse(output: str) -> Optional[Dict[str, Any]]:
    """尝试从 ``` 包裹中提取 JSON - 小沈重构 2026-05-25"""
    if '```' not in output:
        return None
    try:
        json_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', output)
        if json_match and "tool_name" in (jd := json.loads(json_match.group(1).strip())):
            return _create_action_result(jd, output)
    except Exception:
        pass
    return None


# 【小健修复 2026-05-25】提取为独立函数（25.2审计发现：重构时被遗漏，残留在_determine_parse_type内作为死代码）
def _parse_thought_only(output: str, thought_match: re.Match) -> Dict[str, Any]:
    """提取纯思考内容（无Action/Answer的场景）"""
    thought_text = output[thought_match.end():].strip()
    return {
        "type": "thought_only",
        "thought": thought_text,
        "content": thought_text,
        "reasoning": thought_text,
        "tool_name": None,
        "tool_params": None,
        "response": None,
    }


def _try_keyword_parse(output: str) -> Optional[Dict[str, Any]]:
    """尝试关键词匹配（传统 ReAct 格式）- 小沈重构 2026-05-25"""
    try:
        thought_match = re.search(REACT_KEYWORDS["thought"], output, re.IGNORECASE)
        action_match = re.search(REACT_KEYWORDS["action"], output, re.IGNORECASE)
        answer_match = re.search(REACT_KEYWORDS["answer"], output, re.IGNORECASE)

        action_idx = action_match.start() if action_match else float('inf')
        answer_idx = answer_match.start() if answer_match else float('inf')

        if action_match and action_idx < answer_idx:
            return _parse_action(output, thought_match, action_match)
        if answer_match:
            return _parse_answer(output, thought_match, answer_match)
        if thought_match:
            return _parse_thought_only(output, thought_match)
    except Exception:
        pass
    return None


def _make_fallback_result(text: str, is_implicit: bool) -> Dict[str, Any]:
    """构建长度兜底的 implicit 或 parse_error 统一结果 - 小沈重构 2026-05-25"""
    error_msg = None if is_implicit else "无法解析LLM响应，所有解析层（JSON/关键词/工具名）都失败"
    return {
        "type": "implicit" if is_implicit else "parse_error",
        "thought": text, "content": text, "reasoning": text,
        "tool_name": None, "tool_params": None,
        "response": text, "error": error_msg,
    }


# 【小沈重构 2026-05-25】25.2节：骨架~20行，3优先级管道
def _determine_parse_type(output: str) -> Dict[str, Any]:
    """
    【重构 2026-05-25】判断LLM输出类型并调用对应解析函数
    优先级顺序：① ```包裹 ② 关键词匹配 ③ 长度兜底
    """
    if not output or not output.strip():
        return _make_fallback_result("", is_implicit=False)

    output = output.strip()

    # 优先级 ① ```包裹
    result = _try_codeblock_parse(output)
    if result:
        return result

    # 优先级 ② 关键词匹配
    result = _try_keyword_parse(output)
    if result:
        return result

    # 优先级 ③ 长度兜底
    stripped = output.strip()
    is_implicit = len(stripped) >= 5
    text = stripped if is_implicit else stripped[:200]
    return _make_fallback_result(text, is_implicit=is_implicit)


# =============================================================================
# 【2026-04-18 小沈新增】纯JSON块提取函数
# 【2026-05-25 小健重构】拆分为骨架+策略链+字段提取，消除SLAP/DRY违反
# =============================================================================

def _extract_json_string(content: str) -> Optional[str]:
    """从文本中提取JSON字符串

    使用场景: _extract_json_block第一步，复用_extract_json_with_balanced_braces

    使用示例:
        json_str = _extract_json_string(content)

    返回数据说明: 提取的JSON字符串，或None
    """
    if not content:
        return None
    content = content.strip()
    json_str, _ = _extract_json_with_balanced_braces(content)
    return json_str if json_str else None


def _strategy_direct_parse(json_str: str) -> Optional[Dict[str, Any]]:
    """策略1: json.loads直接解析"""
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def _strategy_encoding_fix(json_str: str) -> Optional[Dict[str, Any]]:
    """策略2: errors='replace'编码修复

    使用场景: UTF-8编码异常导致json.loads失败时的降级策略

    返回数据说明: 编码修复后解析的dict，或None
    """
    try:
        json_fixed = json_str.encode('utf-8', errors='replace').decode('utf-8')
        return json.loads(json_fixed)
    except (json.JSONDecodeError, UnicodeError):
        return None


def _strategy_chinese_quotes(json_str: str) -> Optional[Dict[str, Any]]:
    """策略3: 中文引号替换

    使用场景: LLM在thought/reasoning中写中文双引号\u201c\u201d破坏JSON
    从_try_parse_non_standard_json的中文引号逻辑提取(2026-05-25 小健)

    返回数据说明: 中文引号修复后解析的dict，或None
    """
    for fix_fn in [
        lambda s: s.replace('\u201c', '\u300c').replace('\u201d', '\u300d'),
        lambda s: s.replace('\u201c', '').replace('\u201d', ''),
    ]:
        try:
            return json.loads(fix_fn(json_str))
        except json.JSONDecodeError:
            pass
    return None


def _strategy_newline_fix(json_str: str) -> Optional[Dict[str, Any]]:
    """策略4: 换行符转空格

    使用场景: JSON value中含未转义换行符导致解析失败

    返回数据说明: 换行符替换后解析的dict，或None
    """
    try:
        escaped = json_str.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
        return json.loads(escaped)
    except json.JSONDecodeError:
        return None


def _strategy_trailing_comma(json_str: str) -> Optional[Dict[str, Any]]:
    """策略5: 尾随逗号修复

    使用场景: JSON末尾多余的逗号(如 {"a":1,})导致解析失败
    从_try_parse_non_standard_json的尾随逗号逻辑提取(2026-05-25 小健)

    返回数据说明: 尾随逗号修复后解析的dict，或None
    """
    try:
        escaped = json_str.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
        fixed = re.sub(r',(\s*[}\]])', r'\1', escaped)
        return json.loads(fixed)
    except json.JSONDecodeError:
        return None


ParseStrategy = Optional[Dict[str, Any]]

STRATEGIES = [
    _strategy_direct_parse,
    _strategy_encoding_fix,
    _strategy_chinese_quotes,
    _strategy_newline_fix,
    _strategy_trailing_comma,
]


def _try_parse_with_strategies(
    json_str: str, strategies: list,
) -> Optional[Dict[str, Any]]:
    """按策略链顺序尝试解析JSON字符串

    使用场景: _extract_json_block第二步，遍历降级策略直到成功

    使用示例:
        data = _try_parse_with_strategies(json_str, STRATEGIES)

    返回数据说明: 第一个成功策略返回的dict，或None(全部失败)
    """
    for strategy in strategies:
        result = strategy(json_str)
        if result is not None:
            return result
    return None


_FIELD_ALIASES = {
    "thought": ["thought", "content"],
    "content": ["content", "thought"],
}


def _try_extract_single_field(
    json_str: str, field: str, is_nested_object: bool,
) -> Optional[Any]:
    """从JSON字符串中提取单个字段的值

    使用场景: _extract_fields_from_json_str内部调用，逐字段提取

    使用示例:
        value = _try_extract_single_field(json_str, "tool_name", False)

    返回数据说明: 提取的字段值(可能是str/dict)，或None
    """
    if is_nested_object:
        start_pattern = rf'"{field}"\s*:\s*\{{'
    else:
        start_pattern = rf'"{field}"\s*:\s*"'

    start_match = re.search(start_pattern, json_str)
    if not start_match:
        return None

    json_after, _ = _extract_json_with_balanced_braces(json_str[start_match.start():])
    if not json_after:
        return None

    try:
        partial = json.loads(json_after)
        return partial.get(field)
    except (json.JSONDecodeError, ValueError):
        pass

    if is_nested_object:
        inner_start = json_after.find('{', json_after.find(field))
        if inner_start != -1:
            inner_json, _ = _extract_json_with_balanced_braces(json_after[inner_start:])
            if inner_json:
                try:
                    return json.loads(inner_json)
                except (json.JSONDecodeError, ValueError):
                    return _extract_params_by_regex_from_json_str(json_after)
        return None

    if field == "tool_name":
        m = re.search(r'"tool_name":\s*"([^"]+)"', json_str)
        return m.group(1) if m else None

    if field in ("content", "thought"):
        val = _extract_content_value_from_json_str(json_str)
        if val:
            return val
        m = re.search(rf'"{field}"\s*:\s*"(.*?)"\s*,', json_str, re.DOTALL)
        return m.group(1) if m else None

    if field == "reasoning":
        m = re.search(r'"reasoning":\s*"([^"]*)"', json_str)
        return m.group(1) if m else None

    return None


def _extract_fields_from_json_str(
    json_str: str, fields: list,
) -> Dict[str, Any]:
    """从JSON字符串中统一提取多个字段

    使用场景: _extract_json_block第三步，策略链全部失败后的字段级fallback

    使用示例:
        result = _extract_fields_from_json_str(json_str, ["tool_name","tool_params","content","thought","reasoning"])

    返回数据说明: 字段名→值的dict，缺失字段不在结果中
    """
    result = {}
    nested_fields = {"tool_params"}

    for field in fields:
        aliases = _FIELD_ALIASES.get(field, [field])
        is_nested = field in nested_fields

        for alias in aliases:
            value = _try_extract_single_field(json_str, alias, is_nested)
            if value is not None:
                if isinstance(value, str):
                    value = value.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                result[field] = value
                if field in ("content", "thought") and alias != field:
                    cross_field = "thought" if field == "content" else "content"
                    result[cross_field] = value
                break

        if field == "tool_params" and "tool_params" not in result:
            tp = _extract_params_by_regex_from_json_str(json_str)
            if tp:
                result["tool_params"] = tp

    return result


def _extract_json_block(content: str) -> Optional[Dict[str, Any]]:
    """从纯JSON块（无```包裹）中提取数据

    处理以下情况：
    1. 纯JSON：{"tool_name": "xxx", "tool_params": {...}}
    2. 文本+JSON：some text {"tool_name": "xxx"...}
    3. JSON中的实际换行符

    使用场景: LLM响应中提取工具调用或文本回复的JSON

    返回数据说明: 解析后的字典，或None（解析失败）
    """
    json_str = _extract_json_string(content)
    if not json_str:
        return None

    data = _try_parse_with_strategies(json_str, STRATEGIES)
    if data:
        return data

    try:
        fields = ["tool_name", "tool_params", "content", "thought", "reasoning"]
        result = _extract_fields_from_json_str(json_str, fields)
        if result.get("tool_name"):
            if "tool_params" not in result:
                result["tool_params"] = {}
            logger.info(
                f"[_extract_json_block] Fallback成功提取: tool_name={result.get('tool_name')}, "
                f"tool_params_keys={list(result.get('tool_params', {}).keys())}"
            )
            return result
    except Exception as e:
        logger.error(f"[_extract_json_block] Fallback提取失败: {e}")

    return None


def _try_regex_tool_call_fallback(output: str) -> Optional[Dict[str, Any]]:
    """
    整块 JSON 因字符串内未转义引号等无法解析时，从文本中提取最后一次 tool_name / tool_params。
    
    典型场景：混合长文本 + 末尾合法字段名，但 thought 字段内含 ASCII 双引号导致 json.loads 失败，
    原先会落入关键词匹配→implicit→提前 finish，用户任务未完成。
    
    Author: 小沈 - 2026-05-10
    """
    if not output or not isinstance(output, str):
        return None
    matches = list(re.finditer(r'"tool_name"\s*:\s*"([^"]+)"', output))
    if not matches:
        return None
    tool_name = matches[-1].group(1).strip()
    if not tool_name:
        return None
    # 【修复 2026-05-10 小健】finish是合法的退出标志，返回answer类型（不执行工具，直接结束）
    if tool_name == "finish":
        tp: Dict[str, Any] = {}
        tp_mark = re.search(r'"tool_params"\s*:\s*\{', output)
        if tp_mark:
            brace_idx = tp_mark.end() - 1
            substr = output[brace_idx:]
            obj_str, _ = _extract_json_with_balanced_braces(substr)
            if obj_str:
                try:
                    tp = json.loads(obj_str)
                except (json.JSONDecodeError, TypeError):
                    pass
        result_text = tp.get("result", "") if tp else ""
        return {
            "type": "answer",
            "thought": output[:200],
            "content": result_text,
            "reasoning": "",
            "tool_name": None,
            "tool_params": None,
            "response": result_text,
            "error": None
        }
    try:
        from app.services.tools import ensure_tools_registered
        from app.services.tools.registry import tool_registry
        ensure_tools_registered()
        if tool_registry.get_implementation(tool_name) is None:
            return None
    except Exception:
        return None

    tp: Dict[str, Any] = {}
    tp_mark = re.search(r'"tool_params"\s*:\s*\{', output)
    if tp_mark:
        brace_idx = tp_mark.end() - 1
        substr = output[brace_idx:]
        obj_str, _ = _extract_json_with_balanced_braces(substr)
        if obj_str:
            try:
                tp = json.loads(obj_str)
            except json.JSONDecodeError:
                tp = {}

    last_brace = output.rfind("{")
    prefix_text = output[:last_brace].strip() if last_brace != -1 else output.strip()

    if isinstance(tp, dict):
        tp = _normalize_tool_params_content(tp)
        tp = _filter_tool_params(tp)
        if tp:
            tp = _supplement_missing_params(tool_name, tp, output)

    return {
        "type": "action",
        "thought": prefix_text,
        "content": prefix_text,
        "reasoning": "",
        "tool_name": tool_name,
        "tool_params": tp if isinstance(tp, dict) else {},
        "response": None,
        "error": None,
        "parse_warning": "regex_tool_fallback",
    }


def _create_action_result_from_dict(data: Dict) -> Dict[str, Any]:
    """
    【2026-04-28 小沈新增】从 dict 输入创建统一格式的结果
    直接处理已解析的 dict（不是 JSON 字符串），解决长文本 content 丢失问题
    
    Args:
        data: 已经解析好的 dict（来自 LLM 返回的 JSON）
        
    Returns:
        统一格式的结果字典
    """
    if not data or not isinstance(data, dict):
        return {
            "type": "parse_error",
            "error": "Empty or invalid dict input",
            "thought": "",
            "content": "",
            "reasoning": "",
            "tool_name": None,
            "tool_params": None,
            "response": ""
        }
    
    # 显式type优先判断（缺陷4修复 小沈 2026-05-19）
    explicit_type = data.get("type")
    if explicit_type == "parse_error":
        return _build_parse_error_result(data)
    if explicit_type == "answer":
        return _build_answer_result(data)
    if explicit_type == "chunk":
        return _build_chunk_result(data)
    
    # 【修复 2026-05-21 小健】支持旧格式action字段
    # 当dict含action但不含tool_name时，委托给_build_action_from_old_format处理
    # 否则_create_action_result_from_dict会因tool_name为空降级为implicit（bug）
    if "action" in data and "tool_name" not in data:
        output = json.dumps(data, ensure_ascii=False) if isinstance(data, dict) else str(data)
        return _build_action_from_old_format(data, output)

    tool_name = data.get("tool_name")
    # 【2026-04-28 小沈修复】支持args字段（LLM可能返回args而非tool_params）
    raw_params = data.get("tool_params", data.get("args", {}))
    # 【2026-04-28 小沈修复】thought字段独立获取，不被content字段覆盖
    thought = data.get("thought", "")
    content = data.get("content", thought)
    reasoning = data.get("reasoning", "")

    # 【修复A4 2026-05-20 小健】使用 _process_tool_params 统一管道替换 inline 三步
    # 同时修复 raw_output=None 的参数补充能力不足问题
    tool_params = _process_tool_params(raw_params, tool_name, None)

    # finish 类型处理
    # 【修复A4 2026-05-20 小健】finish result 使用 _normalize_result_to_str 标准化
    if tool_name == "finish":
        raw_result = tool_params.get("result") if isinstance(tool_params, dict) else None
        result_text = _normalize_result_to_str(raw_result) if raw_result is not None else ""
        return {
            "type": "answer",
            "thought": content,
            "content": result_text or content,
            "reasoning": reasoning,
            "tool_name": None,
            "tool_params": None,
            "response": result_text or content,
            "error": None
        }
    
    # 【2026-05-14 小沈修复】tool_name为None时不应返回action类型
    # _create_action_result_from_dict是在JSON解析成功后调用的，此时如果LLM返回的
    # JSON中有content/reasoning但tool_name为null，说明LLM"空口说话"（没调用工具）。
    # 应返回implicit（隐式完成），不是action（会导致_execute_tool(None,None)→None.copy()崩溃）
    if not tool_name:
        logger.warning(f"[_create_action_result_from_dict] tool_name为空，降级为implicit")
        result = {
            "type": "implicit",
            "thought": thought,
            "content": content,
            "reasoning": reasoning,
            "tool_name": None,
            "tool_params": None,
            "response": content or thought,
            "error": None
        }
        if "_pending_calls" in data:
            result["_pending_calls"] = data["_pending_calls"]
        return _add_reasoning_warning(result)

    # action 类型
    # 【修复A4 2026-05-20 小健】tool_params 已由 _process_tool_params 完整处理
    # (normalize → filter → supplement)，无需再次 supplement
    # 【改进7 2026-05-01 小沈 小健】添加reasoning验证
    result = {
        "type": "action",
        "thought": thought,
        "content": content,
        "reasoning": reasoning,
        "tool_name": tool_name,
        "tool_params": tool_params,
        "response": None,
        "error": None
    }
    # 【2026-05-14 小沈】透传并行工具调用信息
    if "_pending_calls" in data:
        result["_pending_calls"] = data["_pending_calls"]
    return _add_reasoning_warning(result)


# 【小沈重构 2026-05-25】25.3节：统一构造action结果dict，消除3处字段名重复
def _make_action_result_dict(
    result_type: str, thought: str, content: str, reasoning: str,
    tool_name: Optional[str], tool_params: Optional[Dict],
    response: Optional[str], error: Optional[str] = None,
    pending_calls: Optional[List] = None,
) -> Dict[str, Any]:
    """统一构造 action 结果 dict，消除 3 处的字段名重复 - 小沈重构 2026-05-25"""
    result = {
        "type": result_type, "thought": thought,
        "content": content, "reasoning": reasoning,
        "tool_name": tool_name, "tool_params": tool_params,
        "response": response, "error": error,
    }
    if pending_calls:
        result["_pending_calls"] = pending_calls
    return _add_reasoning_warning(result)


def _resolve_return_type(data: Dict) -> Dict[str, Any]:
    """根据 tool_name 确定返回类型，统一调用 _make_action_result_dict - 小沈重构 2026-05-25"""
    thought, content = data.get("thought", ""), data.get("content", data.get("thought", ""))
    reasoning = data.get("reasoning", "")
    raw_params = data.get("tool_params", data.get("args", {}))
    tool_params = _process_tool_params(raw_params, data.get("tool_name"), None)
    pending = data.get("_pending_calls")
    tool_name = data.get("tool_name")

    # finish → answer
    if tool_name == "finish":
        raw_result = tool_params.get("result") if isinstance(tool_params, dict) else None
        result_text = _normalize_result_to_str(raw_result) if raw_result is not None else ""
        return _make_action_result_dict(
            "answer", content, result_text or content, reasoning,
            None, None, result_text or content, None, pending)

    # tool_name 空 → implicit
    if not tool_name:
        logger.warning(f"[_create_action_result_from_dict] tool_name为空，降级为implicit")
        return _make_action_result_dict(
            "implicit", thought, content, reasoning,
            None, None, content or thought, None, pending)

    # 正常 action
    return _make_action_result_dict(
        "action", thought, content, reasoning,
        tool_name, tool_params, None, None, pending)


# 【小沈重构 2026-05-25】25.3节：骨架~25行，3种返回类型统一分发
def _create_action_result_from_dict(data: Dict) -> Dict[str, Any]:
    """
    【重构 2026-05-25】从 dict 输入创建统一格式的结果
    直接处理已解析的 dict（不是 JSON 字符串），解决长文本 content 丢失问题
    """
    if not data or not isinstance(data, dict):
        return _make_action_result_dict("parse_error", "", "", "", None, None, "", "Empty or invalid dict input")

    explicit_type = data.get("type")
    if explicit_type == "parse_error":
        return _build_parse_error_result(data)
    if explicit_type == "answer":
        return _build_answer_result(data)
    if explicit_type == "chunk":
        return _build_chunk_result(data)

    if "action" in data and "tool_name" not in data:
        output = json.dumps(data, ensure_ascii=False) if isinstance(data, dict) else str(data)
        return _build_action_from_old_format(data, output)

    return _resolve_return_type(data)
    """
    【2026-04-28 小沈新增】从 list 输入创建统一格式的结果
    处理LLM返回的JSON数组场景
    
    Args:
        data: 已经解析好的 list（来自 LLM 返回的 JSON 数组）
        
    Returns:
        统一格式的结果字典
    """
    # 空数组处理
    if not data:
        logger.info(f"[parse_react_response] list为空，返回parse_error")
        return {
            "type": "parse_error",
            "error": "Empty list input from LLM",
            "thought": "",
            "content": "",
            "reasoning": "",
            "tool_name": None,
            "tool_params": None,
            "response": ""
        }
    
    # 遍历list，寻找有效的dict元素
    valid_items = [item for item in data if isinstance(item, dict)]
    
    # 无有效dict元素
    if not valid_items:
        logger.info(f"[parse_react_response] list中无有效dict元素，返回parse_error")
        return {
            "type": "parse_error",
            "error": "No valid dict items in list",
            "thought": "",
            "content": "",
            "reasoning": "",
            "tool_name": None,
            "tool_params": None,
            "response": ""
        }
    
    # 取最后一个有效的dict元素（LLM通常将最终结果放在最后）
    last_item = valid_items[-1]
    
    # 【2026-05-14 小沈】处理Function Calling格式数组
    # 如 [{"index":0,"function":{"name":"search_web","arguments":"{\"query\":\"test\"}"}}]
    # 这种格式的item中没有tool_name字段，需要通过function.name提取
    if len(valid_items) > 0 and "tool_name" not in valid_items[0] and "function" in valid_items[0]:
        # 整个数组都是Function Calling格式 → 全部转换
        converted = []
        for item in valid_items:
            if isinstance(item, dict) and "function" in item:
                func = item["function"]
                fname = func.get("name", "") if isinstance(func, dict) else ""
                fargs_str = func.get("arguments", "{}") if isinstance(func, dict) else "{}"
                try:
                    import json as _json
                    fargs = _json.loads(fargs_str) if isinstance(fargs_str, str) else (fargs_str or {})
                except (_json.JSONDecodeError, TypeError):
                    fargs = {}
                converted.append({"name": fname, "args": fargs})
            else:
                converted.append(item)
        
        last_converted = converted[-1]
        pending_calls = converted[:-1]
        
        logger.info(f"[parse_react_response] list检测到Function Calling格式({len(converted)}个)")
        last_item = {
            "tool_name": last_converted["name"],
            "tool_params": last_converted["args"],
            "content": last_item.get("content", ""),
            "thought": last_item.get("thought", last_item.get("content", "")),
            "reasoning": last_item.get("reasoning", ""),
        }
        if pending_calls:
            last_item["_pending_calls"] = pending_calls
    
    logger.info(f"[parse_react_response] list解析成功，使用最后一个元素")
    return _create_action_result_from_dict(last_item)


def _normalize_tool_params_content(tool_params: Dict) -> Dict:
    """
    【2026-04-28 小沈新增】标准化tool_params中的content和result字段类型
    确保content/result字段始终为字符串，处理数字、布尔值、嵌套dict/list等类型
    
    修复finish时result字段嵌套问题（小沈 2026-05-19）:
    LLM可能返回 {"tool_name": "finish", "tool_params": {"result": {"status": "ok"}}}
    此时result是dict，需要转为JSON字符串，否则下游FinalStep收到dict会出问题。
    
    Args:
        tool_params: 原始tool_params字典
        
    Returns:
        标准化后的tool_params字典
    """
    if not isinstance(tool_params, dict):
        return tool_params
    
    # 复制一份避免修改原始数据
    normalized = dict(tool_params)
    
    # 统一处理字段：content 和 result 做相同的类型标准化
    for field_name in ("content", "result"):
        if field_name in normalized:
            field_value = normalized[field_name]
            
            # 布尔类型必须在int之前检查（bool是int子类）
            if isinstance(field_value, bool):
                normalized[field_name] = str(field_value)
            # 数字类型转换为字符串
            elif isinstance(field_value, (int, float)):
                normalized[field_name] = str(field_value)
            # 列表/字典类型转换为JSON字符串
            elif isinstance(field_value, (list, dict)):
                normalized[field_name] = json.dumps(field_value, ensure_ascii=False)
            # None保留为None，不做转换
            # 字符串保持不变
    
    return normalized


def _filter_tool_params(tool_params: Dict) -> Dict:
    """
    【2026-04-28 小沈新增】过滤tool_params中的非工具参数字段
    
    从tool_params中移除reasoning、thought、extra_field等LLM返回的额外字段，
    只保留工具真正需要的参数（包括content字段）
    
    Args:
        tool_params: 原始参数字典
        
    Returns:
        过滤后的参数字典
    """
    if not tool_params or not isinstance(tool_params, dict):
        return {}
    
    # 已知的非参数字段（LLM可能返回的额外字段，这些不是工具参数）
    NON_PARAM_FIELDS = {
        "reasoning",    # LLM的思考过程（不是工具参数）
        "thought",       # 思考内容（不是工具参数）
        "type",         # 类型字段（不是工具参数）
        "tool_name",    # 工具名（不应在参数中）
        "action",       # 动作字段（不是工具参数）
        "action_input", # 动作输入（不是工具参数）
        "extra_field",  # 额外字段（不是工具参数）
        "metadata",     # 元数据（不是工具参数）
        "context",      # 上下文（不是工具参数）
    }
    
    # 创建新字典，只保留非NON_PARAM_FIELDS的字段
    # 注意：content字段是许多工具的有效参数（如write_file），不应该被过滤
    # 过滤逻辑：只保留看起来像真正参数的字段名（字母/数字/下划线组成）
    # 同时过滤掉以--开头的参数名（[TOOL_CALL]格式的参数）
    param_name_pattern = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
    
    # 【2026-04-28 小沈新增】驼峰转下划线映射表
    CAMEL_TO_SNAKE = {
        "filePath": "file_path",
        "filePath2": "file_path",
        "dirPath": "dir_path",
        "dirPath2": "dir_path",
        "sourcePath": "source_path",
        "sourcePath2": "source_path",
        "destinationPath": "destination_path",
        "destinationPath2": "destination_path",
        "filePattern": "file_pattern",
        "filePattern2": "file_pattern",
        "offset2": "offset",
        "limit2": "limit",
        # 首字母大写映射
        "Content": "content",
        "FilePath": "file_path",
        "DirPath": "dir_path",
        "SourcePath": "source_path",
        "DestinationPath": "destination_path",
        "FilePattern": "file_pattern",
    }
    
    filtered = {}
    for k, v in tool_params.items():
        if k not in NON_PARAM_FIELDS:
            # 字段名必须匹配参数名模式（字母/数字/下划线，不能以数字开头）
            if param_name_pattern.match(k):
                # 驼峰转下划线（如filePath → file_path）
                normalized_k = CAMEL_TO_SNAKE.get(k, k)
                # 如果标准化后的key已存在，保留原始key（避免覆盖）
                if normalized_k not in filtered:
                    filtered[normalized_k] = v
                else:
                    # 标准化key已存在，保留原始key
                    filtered[k] = v
    
    return filtered


# TOOL_REQUIRED_PARAMS 已删除 - 小健 2026-05-02
# 必需参数从Pydantic模型schema动态获取，使用 _get_required_params(tool_name)


def _check_missing_required_params(tool_name: str, tool_params: Dict, original_output: str = None) -> tuple:
    """
    【2026-04-28 小沈新增】检测并补充缺失的必需参数
    
    注意：必需参数校验已删除（小健 2026-05-02）。
    Pydantic模型在执行时自动校验required参数，此处不再重复检查。
    保留此函数作为兼容性占位，统一返回(原参数字典, False)。
    
    Args:
        tool_name: 工具名称
        tool_params: 已解析的参数字典
        original_output: LLM原始输出文本
        
    Returns:
        tuple: (原参数字典, False) 固定返回
    """
    return tool_params, False


def _supplement_missing_params(tool_name: str, tool_params: Dict, original_output: str = None) -> Dict:
    """
    【2026-04-28 小沈新增】补充缺失的必需参数
    
    当LLM返回的参数不完整时，尝试从原始输出或内容中推断缺失的参数。
    这是处理LLM返回参数顺序不固定（如先返回file_path再返回content）的容错机制。
    
    处理逻辑：
    1. 首先调用_check_missing_required_params尝试从原始输出补充
    2. 如果无法补充，根据工具类型使用推断逻辑：
       - write_file: 
         - 缺失content时：从original_output中提取content字段
         - 缺失file_path时：从content第一行提取标题作为文件名
       - read_file:
         - 缺失file_path时：从content中提取路径或使用默认值
    
    Args:
        tool_name: 工具名称（如write_file, read_file等）
        tool_params: 已解析的参数字典（可能不完整）
        original_output: LLM原始输出文本（用于提取缺失参数）
        
    Returns:
        补充后的参数字典
        
    示例:
        # LLM返回 {"file_path": "xxx"} 但缺失content
        >>> _supplement_missing_params("write_file", {"file_path": "xxx"}, '{"tool_name":"write_file","tool_params":{"file_path":"xxx","content":"小说内容"}}')
        {"file_path": "xxx", "content": "小说内容"}
        
        # LLM返回 {"content": "xxx"} 但缺失file_path
        >>> _supplement_missing_params("write_file", {"content": "第一章\n内容..."}, None)
        {"content": "第一章\n内容...", "file_path": "E:/故事/第一章.txt"}
    """
    result, has_missing = _check_missing_required_params(tool_name, tool_params, original_output)
    
    # 如果能补充，直接返回
    if result is not None:
        return result
    
    # 无法补充时，使用推断逻辑
    # 【适用范围】专为「写小说/长文本」场景设计，非小说内容（代码、日志等）推断可能不准确
    # 【回退机制】推断失败时直接返回原参数，让LLM重试
    
    # 对于write_file，如果没有content，从file_path推断
    if tool_name == "write_file" and "content" not in tool_params and "file_path" in tool_params:
        # 已有file_path，content缺失，这通常是LLM返回参数顺序问题
        # 从original_output中提取content：优先JSON解析，失败再用正则
        if original_output:
            # 【改进】优先尝试JSON解析，精确提取tool_params里的content
            extracted_content = None
            try:
                json_data = json.loads(original_output)
                # 标准格式：tool_params.content
                if isinstance(json_data, dict):
                    tool_params_data = json_data.get("tool_params") or json_data.get("action_input") or {}
                    if isinstance(tool_params_data, dict) and "content" in tool_params_data:
                        extracted_content = tool_params_data["content"]
            except (json.JSONDecodeError, TypeError):
                pass
            
            if extracted_content:
                tool_params["content"] = extracted_content
                logger.info(f"[_supplement_missing_params] 从JSON解析补充content参数")
                return tool_params
            
            # 【改进】正则支持转义引号（\" 或 \'）
            patterns = [
                r'"content"\s*:\s*"((?:[^\"\\]|\\.)*)"',  # 支持转义双引号
                r"'content'\s*:\s*'((?:[^'\\]|\\.)*)'",  # 支持转义单引号
            ]
            for pattern in patterns:
                match = re.search(pattern, original_output, re.DOTALL)
                if match:
                    tool_params["content"] = match.group(1)
                    logger.info(f"[_supplement_missing_params] 从正则匹配补充content参数")
                    return tool_params
        
        # 如果无法提取，返回原始参数（让LLM重试）
        logger.warning(f"[_supplement_missing_params] write_file 缺失content，无法从原始输出补充（original_output={type(original_output).__name__}）")
        return tool_params
    
    # 对于write_file，如果没有file_path，从content推断
    # 【适用范围】专为「写小说/长文本」场景设计，非小说内容推断可能不准确
    # 【回退机制】推断失败时返回原参数，让LLM重试
    if tool_name == "write_file" and "file_path" not in tool_params and "content" in tool_params:
        content = tool_params.get("content", "")
        first_line = content.split('\n')[0].strip() if content else ""
        inferred_path = None
        if first_line and len(first_line) < 100:
            title_match = re.match(r'^([^:：]+)', first_line)
            if title_match:
                title = title_match.group(1).strip()
                title = re.sub(r'[\\/:*?"<>|]', '', title)[:50]
                inferred_path = f"E:/故事/{title}.txt"
        
        if inferred_path:
            tool_params["file_path"] = inferred_path
            return tool_params
        else:
            # 推断失败，明确日志并返回原参数，让LLM重试
            logger.warning(f"[_supplement_missing_params] write_file 无法从content推断file_path（第一行长度={len(first_line)}字符），返回原参数让LLM重试")
            return tool_params
    
    # 对于read_file，如果没有file_path，尝试从content推断
    if tool_name == "read_file" and "file_path" not in tool_params and "content" in tool_params:
        content = tool_params.get("content", "")
        # 从content中尝试提取文件名
        # 匹配可能的小说文件名或路径
        match = re.search(r'([A-Za-z]:[/\\]|/)[^/\\:*?"<>|]+\.txt', content)
        if match:
            tool_params["file_path"] = match.group(0)
            return tool_params
        # 使用默认读取路径
        tool_params["file_path"] = "E:/默认读取.txt"
        return tool_params
    
    # 其他情况返回原参数（可能不完整）
    return tool_params


def _try_parse_non_standard_json(input_str: str) -> Optional[Dict]:
    """
    【2026-04-28 小沈新增】尝试解析非标准JSON（单引号、尾逗号、注释等）
    
    Args:
        input_str: 可能包含非标准JSON的字符串
        
    Returns:
        解析后的dict，或None如果解析失败
    """
    if not isinstance(input_str, str):
        return None
    
    try:
        # 方法1：直接尝试标准JSON解析（可能成功）
        return json.loads(input_str)
    except json.JSONDecodeError:
        pass
    
    # 方法2：尝试将单引号替换为双引号（注意处理内部单引号）
    try:
        # 简单的单引号转双引号（可能不完美，但能处理大多数情况）
        # 匹配 'xxx' 模式，替换为 "xxx"
        result = re.sub(r"'([^'\\]*(\\.[^'\\]*)*)'", r'"\1"', input_str)
        return json.loads(result)
    except json.JSONDecodeError:
        pass
    
    # 方法3：处理尾随逗号（如 {"a": 1, } -> {"a": 1}）
    try:
        result = re.sub(r',(\s*})', r'\1', input_str)
        # 再尝试单引号替换
        result = re.sub(r"'([^'\\]*(\\.[^'\\]*)*)'", r'"\1"', result)
        return json.loads(result)
    except json.JSONDecodeError:
        pass
    
    # 方法4：处理//注释（单行注释）
    try:
        # 移除//注释（不处理字符串内的//）
        lines = input_str.split('\n')
        cleaned_lines = []
        for line in lines:
            # 查找//，但确保不在字符串内
            in_string = False
            comment_pos = -1
            for i, ch in enumerate(line):
                if ch == '"' and (i == 0 or line[i-1] != '\\'):
                    in_string = not in_string
                elif ch == '/' and i + 1 < len(line) and line[i+1] == '/' and not in_string:
                    comment_pos = i
                    break
            if comment_pos != -1:
                cleaned_lines.append(line[:comment_pos])
            else:
                cleaned_lines.append(line)
        cleaned = '\n'.join(cleaned_lines)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    
    # 方法5：检测不完整JSON（缺少闭合括号）
    try:
        # 检查括号是否匹配
        stack = []
        in_string = False
        escape = False
        for ch in input_str:
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"' and not in_string:
                in_string = True
                continue
            if ch == '"' and in_string:
                in_string = False
                continue
            if not in_string:
                if ch in '{[(':
                    stack.append(ch)
                elif ch in '}])':
                    if not stack:
                        return None
                    opener = stack.pop()
                    if (ch == '}' and opener != '{') or \
                       (ch == ']' and opener != '[') or \
                       (ch == ')' and opener != '('):
                        return None
        # 如果括号不匹配，返回None
        if stack:
            return None
    except:
        pass
    
    return None


def _create_action_result(parsed: Dict, original_output: str) -> Dict[str, Any]:
    """
    【2026-04-18小沈新增】从解析后的JSON创建统一格式的结果
    
    Args:
        parsed: 解析后的JSON字典
        original_output: 原始LLM输出（用于错误恢复）
        
    Returns:
        统一格式的结果字典
    """
    # 【新增】参数校验
    if not parsed or not isinstance(parsed, dict):
        # 尝试从原始输出中提取信息
        return {
            "type": "implicit",
            "thought": "",
            "content": original_output or "",
            "reasoning": "",
            "tool_name": None,
            "tool_params": None,
            "response": original_output or "",
            "error": None
        }
    
    tool_name = parsed.get("tool_name", parsed.get("action_tool", parsed.get("action", None)))
    # 【2026-04-28 小沈修复】支持args字段（LLM可能返回args而非tool_params）
    tool_params = parsed.get("tool_params", parsed.get("params", parsed.get("action_input", parsed.get("args", {}))))
    
    # 统一工具参数处理管道（缺陷2修复 小沈 2026-05-19）
    if isinstance(tool_params, dict):
        tool_params = _process_tool_params(tool_params, tool_name, original_output)
    
    # 【2026-04-23 小沈修复】当 tool_name 为 None/null 时，检查 content 是否表明任务完成
    if tool_name is None:
        content_for_check = parsed.get("content", "") or parsed.get("thought", "") or ""
        # 检查内容中是否包含完成相关的关键词
        finish_keywords = ["完成", "结束", "任务完成", "已经", "finished", "complete", "done"]
        if any(kw in content_for_check for kw in finish_keywords):
            # 识别为 finish
            result_text = parsed.get("content", "")
            return {
                "type": "answer",
                "thought": parsed.get("thought", ""),
                "content": result_text,
                "reasoning": parsed.get("reasoning", ""),
                "tool_name": None,
                "tool_params": None,
                "response": result_text,
                "error": None
            }
    
    # 【新增】确保tool_params是字典
    if not isinstance(tool_params, dict):
        tool_params = {}
    
    # finish类型处理
    if tool_name == "finish":
        result_text = tool_params.get("result", "") if tool_params else ""
        return {
            "type": "answer",
            "thought": parsed.get("thought", ""),
            "content": result_text or parsed.get("content", ""),
            "reasoning": parsed.get("reasoning", ""),
            "tool_name": None,
            "tool_params": None,
            "response": result_text or parsed.get("content", ""),
            "error": None
        }
    
    # action类型（tool_params已在_process_tool_params中统一处理 小沈 2026-05-19）
    final_tool_params = tool_params
    result = {
        "type": "action",
        "thought": parsed.get("thought", ""),
        "content": parsed.get("content", parsed.get("thought", original_output.strip())),
        "reasoning": parsed.get("reasoning", ""),
        "tool_name": tool_name,
        "tool_params": final_tool_params,
        "response": None,
        "error": None
    }
    return _add_reasoning_warning(result)


def _extract_tool_params_from_thought(thought: str, tool_name: str = None) -> Dict[str, Any]:
    """
    【2026-04-18小沈新增】从thought内容中提取嵌套的JSON参数（fallback机制）
    
    使用场景：
    当LLM返回传统ReAct格式，但没有Action Input标记时：
    
    Thought: 用户需要检查E盘，调用list_directory工具
    Action: list_directory
    
    此时thought中可能包含参数信息，尝试提取
    
    Args:
        thought: 包含嵌套JSON的文本
        tool_name: 工具名称（用于后续扩展，可根据工具名推断参数）
        
    Returns:
        提取的参数字典，或空字典
    """
    if not thought:
        return {}
    
    # 使用平衡括号算法提取JSON（正确处理字符串内花括号）
    json_text, _ = _extract_json_with_balanced_braces(thought)
    
    if json_text:
        try:
            # 先尝试直接解析
            parsed = json.loads(json_text)
            # 优先返回tool_params，其次返回整个parsed（可能就是参数）
            if "tool_params" in parsed:
                return parsed["tool_params"]
            if "params" in parsed:
                return parsed["params"]
            # 【新增】如果parsed不包含tool_name字段，可能整个就是参数
            if "tool_name" not in parsed:
                return parsed
        except json.JSONDecodeError:
            # 处理实际换行符
            try:
                json_text_escaped = json_text.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
                parsed = json.loads(json_text_escaped)
                if "tool_params" in parsed:
                    return parsed["tool_params"]
                if "params" in parsed:
                    return parsed["params"]
                if "tool_name" not in parsed:
                    return parsed
            except:
                pass
    
    return {}


def _extract_tool_params_from_text(content: str, tool_start_pos: int) -> Optional[Dict[str, Any]]:
    """
    【2026-04-28 小沈新增】从文本中提取tool_params JSON块
    
    在tool_name位置附近查找tool_params并尝试提取完整参数
    
    Args:
        content: LLM响应文本
        tool_start_pos: tool_name在文本中的起始位置
        
    Returns:
        提取的参数字典，或None（提取失败）
    """
    # 在tool_name后面查找tool_params JSON块
    search_text = content[tool_start_pos:]
    
    # 查找 "tool_params": { 开始位置
    tp_pattern = r'"tool_params"\s*:\s*\{'
    tp_match = re.search(tp_pattern, search_text)
    
    if not tp_match:
        return None
    
    # 使用平衡括号算法提取完整的tool_params对象
    json_start = tp_match.start()
    json_text, _ = _extract_json_with_balanced_braces(search_text[json_start:])
    
    if not json_text:
        return None
    
    # 尝试解析提取的JSON
    try:
        # 方法1：直接解析
        parsed = json.loads(json_text)
        if "tool_params" in parsed:
            return parsed["tool_params"]
        elif isinstance(parsed, dict):
            # 如果没有tool_params外层，直接返回parsed
            # 过滤掉非参数字段
            return {k: v for k, v in parsed.items() if k not in ["reasoning", "thought", "type", "tool_name", "action", "action_input", "extra_field", "metadata", "context"]}
    except:
        pass
    
    # 方法2：尝试去掉外层，直接提取内部对象
    try:
        inner_start = json_text.find('{', json_text.find('tool_params'))
        if inner_start != -1:
            inner_json, _ = _extract_json_with_balanced_braces(json_text[inner_start:])
            if inner_json:
                return json.loads(inner_json)
    except:
        pass
    
    # 方法3：【2026-04-28 小沈新增】当JSON解析失败时，使用更宽松的正则提取参数
    # 处理content字段包含换行和未转义引号的情况
    params = _extract_params_by_regex(search_text)
    if params:
        return params
    
    return None


def _extract_content_value_from_json_str(json_str: str) -> Optional[str]:
    """
    【2026-04-28 小沈新增】从JSON字符串中提取外层content字段的值
    
    处理content字段包含中文引号、换行等导致JSON解析失败的情况
    
    Args:
        json_str: 完整的JSON字符串
        
    Returns:
        提取的content值，或None
    """
    # 找到第一个"content"字段（不是tool_params中的content）
    content_start = json_str.find('"content"')
    if content_start == -1:
        return None
    
    # 检查是否是tool_params中的content（通过检查前面是否有"tool_params"）
    tool_params_pos = json_str.find('"tool_params"')
    if tool_params_pos != -1 and content_start > tool_params_pos:
        # 这是tool_params中的content，不是外层的content
        return None
    
    # 找到"content"后面的引号
    quote_start = json_str.find('"', content_start + len('"content"'))
    if quote_start == -1:
        return None
    
    # 使用平衡引号算法找到结束引号
    value_start = quote_start + 1
    i = value_start
    while i < len(json_str):
        if json_str[i] == '\\' and i + 1 < len(json_str):
            i += 2
            continue
        if json_str[i] == '"':
            return json_str[value_start:i]
        i += 1
    
    return None


def _extract_params_by_regex_from_json_str(json_str: str) -> Optional[Dict[str, Any]]:
    """
    【2026-04-28 小沈新增】从JSON字符串中提取tool_params
    
    当JSON解析失败时（如content字段包含中文引号），使用正则表达式提取参数
    
    Args:
        json_str: 完整的JSON字符串
        
    Returns:
        提取的参数字典，或None
    """
    # 在整个JSON字符串中查找tool_params对象
    params = {}
    
    # 查找 tool_params 对象的开始位置
    tp_start = json_str.find('"tool_params"')
    if tp_start == -1:
        return None
    
    # 找到 "tool_params": { 的 { 位置
    brace_start = json_str.find('{', tp_start)
    if brace_start == -1:
        return None
    
    # 使用平衡括号提取整个tool_params对象
    tp_json, _ = _extract_json_with_balanced_braces(json_str[brace_start:])
    if not tp_json:
        return None
    
    # 尝试解析，如果失败使用正则提取
    try:
        return json.loads(tp_json)
    except:
        pass
    
    # 使用正则提取各个参数
    # 提取file_path
    file_path_match = re.search(r'"file_path"\s*:\s*"([^"]+)"', tp_json)
    if file_path_match:
        params["file_path"] = file_path_match.group(1)
    
    # 提取content - 使用平衡引号算法
    content_start = tp_json.find('"content"')
    if content_start != -1:
        quote_start = tp_json.find('"', content_start + len('"content"'))
        if quote_start != -1:
            value_start = quote_start + 1
            i = value_start
            while i < len(tp_json):
                if tp_json[i] == '\\' and i + 1 < len(tp_json):
                    i += 2
                    continue
                if tp_json[i] == '"':
                    params["content"] = tp_json[value_start:i]
                    break
                i += 1
    
    # 【修复 2026-05-15 小健】添加"result"参数提取（finish命令的tool_params.result）
    # 【修复 2026-05-15 小健】result可能是长文本，用平衡引号算法提取避免截断
    result_start = tp_json.find('"result"')
    if result_start != -1:
        colon_pos = tp_json.find(':', result_start + len('"result"'))
        if colon_pos != -1:
            quote_start = tp_json.find('"', colon_pos)
            if quote_start != -1:
                value_start = quote_start + 1
                i = value_start
                while i < len(tp_json):
                    if tp_json[i] == '\\' and i + 1 < len(tp_json):
                        i += 2
                        continue
                    if tp_json[i] == '"':
                        params["result"] = tp_json[value_start:i]
                        break
                    i += 1
    
    # 提取其他常见参数
    other_params = ["dir_path", "source_path", "destination_path", "file_pattern", "pattern", "offset", "limit", "encoding"]
    for p in other_params:
        pattern = rf'"{p}"\s*:\s*"([^"]+)"'
        match = re.search(pattern, tp_json)
        if match:
            params[p] = match.group(1)
    
    return params if params else None


def _extract_params_by_regex(text: str) -> Optional[Dict[str, Any]]:
    """
    【2026-04-28 小沈新增】当JSON解析失败时，使用正则表达式提取参数
    
    处理tool_params JSON中content字段包含换行和未转义引号的情况
    
    Args:
        text: 包含tool_params的文本
        
    Returns:
        提取的参数字典，或None
    """
    params = {}
    
    # 提取file_path参数（支持Windows和Unix路径）
    file_path_patterns = [
        r'"file_path"\s*:\s*"([^"]+)"',
        r'"filepath"\s*:\s*"([^"]+)"',
    ]
    for pattern in file_path_patterns:
        match = re.search(pattern, text)
        if match:
            params["file_path"] = match.group(1)
            break
    
    # 如果上面没找到，尝试更宽松的路径模式
    if "file_path" not in params:
        path_patterns = [
            r'["\']?([A-Za-z]:\\[^"\'\s,}]+)["\']?',  # Windows路径
            r'"path"\s*:\s*"([^"]+)"',
        ]
        for pattern in path_patterns:
            match = re.search(pattern, text)
            if match:
                params["file_path"] = match.group(1)
                break
    
    # 提取content参数 - 使用更宽松的模式匹配
    # 匹配 "content": " 后面到下一个 " 之前的内容（处理引号内可能有换行的情况）
    # 关键：需要找到content字段在tool_params块中的位置，然后向后查找直到找到配对的结束引号
    content_start = text.find('"content"')
    if content_start != -1:
        # 从content位置开始查找值的开始引号
        quote_start = text.find('"', content_start + len('"content"'))
        if quote_start != -1:
            # 使用平衡引号算法找到结束引号
            # 注意：需要处理引号内的转义引号
            value_start = quote_start + 1
            i = value_start
            in_string = True
            while i < len(text):
                if text[i] == '\\' and i + 1 < len(text):
                    # 转义字符，跳过
                    i += 2
                    continue
                if text[i] == '"':
                    # 找到结束引号
                    params["content"] = text[value_start:i]
                    break
                i += 1
    
    return params if params else None


# =============================================================================
# 步骤1.3：实现_parse_action()函数
# =============================================================================

def _parse_action(
    output: str, 
    thought_match: Optional[re.Match], 
    action_match: re.Match
) -> Dict[str, Any]:
    """
    解析Action格式（工具调用）
    
    格式: Thought + Action + Action Input
    支持中英文关键词混用
    
    Args:
        output: LLM原始响应文本
        thought_match: Thought关键词匹配对象（可能为None）
        action_match: Action关键词匹配对象
        
    Returns:
        type="action"的统一格式字典
        
    正则设计依据: LlamaIndex extract_tool_use() 实现
    关键改进1: 工具名约束 ``[^\n() ]+`` 禁止空格和括号
    关键改进2: Thought可选前缀（无Thought标记时捕获整行）
    关键改进3: 非贪婪匹配JSON ``.*?`` 确保正确捕获
    关键改进4: 中英文关键词完整支持
    """
    # 【24.1.4 重构后主函数】~60行骨架，调用3个提取组件
    # 提取 thought
    thought = output[thought_match.end():action_match.start()].strip() if thought_match \
        else output[:action_match.start()].strip()

    # 定位 action_input 并提取 tool_name 和 params
    action_input_match = re.search(REACT_KEYWORDS["action_input"], output, re.IGNORECASE)
    action_start = action_match.end()

    if action_input_match:
        action_section = output[action_start:action_input_match.start()].strip()
        input_section = output[action_input_match.end():].strip()
        tool_params = _parse_action_input(input_section) or {}
    else:
        action_section = output[action_start:].strip()
        tool_params = {}

    # 工具名正则
    tool_name_match = re.match(r'^([^\n\(\) ]+)', action_section)
    tool_name = tool_name_match.group(1) if tool_name_match \
        else (action_section.split()[0] if action_section else "")

    # 统一字段映射
    if isinstance(tool_params, dict):
        tool_name = _fallback_tool_name(tool_params, tool_name)
        tool_params = _normalize_tool_params(tool_params)

    # 统一管道
    final_tool_params = _process_tool_params(tool_params or {}, tool_name, output)
    return _build_action_result("action", tool_name, final_tool_params, thought)


# =============================================================================
# 步骤1.4：实现_parse_answer()函数
# =============================================================================

def _parse_answer(
    output: str, 
    thought_match: Optional[re.Match], 
    answer_match: re.Match
) -> Dict[str, Any]:
    """
    解析Answer格式（最终回答）
    
    格式: Thought + Answer
    支持中英文关键词混用
    
    Args:
        output: LLM原始响应文本
        thought_match: Thought关键词匹配对象（可能为None）
        answer_match: Answer关键词匹配对象
        
    Returns:
        type="answer"的统一格式字典
        
    正则设计依据: LlamaIndex extract_final_response() 实现
    关键改进1: 空格容忍 (允许前面有空格或换行)
    关键改进2: 非贪婪匹配 (确保Thought不包含Answer关键词)
    关键改进3: 多行回答支持 (匹配到末尾所有内容)
    关键改进4: 中英文关键词完整支持
    """
    # 提取Thought内容
    if thought_match:
        thought_start = thought_match.end()
        # 关键改进2: 非贪婪匹配确保Thought不包含Answer
        thought_end = answer_match.start()
        thought = output[thought_start:thought_end].strip()
    else:
        thought = ""
    
    # 提取Answer内容（从Answer标记后到文本末尾）
    answer_start = answer_match.end()
    # 关键改进3: 匹配到末尾所有内容（支持多行回答）
    response = output[answer_start:].strip()
    
    return {
        "type": "answer",
        "thought": thought,
        "content": thought,             # 兼容性字段
        "reasoning": thought,           # 兼容性字段
        "tool_name": None,
        "tool_params": None,
        "response": response
    }


# =============================================================================
# 步骤1.5：实现_parse_action_input()函数
# =============================================================================

def _try_parse_chain(input_str: str, parsers) -> Optional[Dict]:
    """通用链式解析：依次尝试每个解析器，首个成功返回

    小沈 2026-05-25 重构拆分
    """
    for parser in parsers:
        try:
            result = parser(input_str)
            if result is not None:
                return result
        except Exception:
            continue
    return None


def _try_markdown_parse(s: str) -> Optional[Dict]:
    mc = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', s, re.DOTALL | re.IGNORECASE)
    return json.loads(mc.group(1).strip()) if mc else None


def _try_json_parse(s: str) -> Optional[Dict]:
    return json.loads(s)


def _try_balanced_braces(s: str) -> Optional[Dict]:
    js, _ = _extract_json_with_balanced_braces(s)
    return json.loads(js) if js else None


def _try_single_quotes(s: str) -> Optional[Dict]:
    return json.loads(s.replace("'", '"'))


def _try_kv_parse(s: str) -> Optional[Dict]:
    return _extract_key_value_pairs(s)


_TOOL_NAME_KEYS = [r'"tool_name"', r'"action_tool"', r'"action"']
_TOOL_PARAMS_KEYS = [r'"tool_params"', r'"params"', r'"action_input"']


def _extract_fields_partial(s: str) -> Optional[Dict]:
    """部分损坏 JSON 的挽救性字段提取

    小沈 2026-05-25 重构拆分
    """
    result = {}
    for pat in _TOOL_NAME_KEYS:
        m = re.search(rf'{pat}\s*:\s*"([^"]*)"', s)
        if m:
            result["tool_name"] = m.group(1)
            break
    for pat in _TOOL_PARAMS_KEYS:
        m = re.search(rf'{pat}\s*:\s*(\{{[^}}]*\}})', s)
        if m:
            try:
                result["tool_params"] = json.loads(m.group(1))
            except Exception:
                result["tool_params"] = {}
            break
    return result if result else None


def _parse_action_input(input_section: str) -> Dict[str, Any]:
    """
    解析Action Input中的JSON参数

    实现五级降级策略（原四级+Markdown去除），确保最大限度解析成功

    【小沈重构 2026-05-25】链式解析管道，职责单一，每个解析器独立可测试

    Args:
        input_section: Action Input之后的文本内容

    Returns:
        解析后的参数字典（失败返回空字典）
    """
    if not input_section:
        return {}

    PARSERS = [
        _try_markdown_parse,    # L0: Markdown 去除
        _try_json_parse,        # L1: 标准 JSON
        _try_balanced_braces,   # L2: 平衡括号
        _try_single_quotes,     # L3: 单引号替换
        _extract_fields_partial, # L4: 字段提取
        _try_kv_parse,          # L5: KV 兜底
    ]

    result = _try_parse_chain(input_section, PARSERS)
    if result is not None:
        return result

    logger.error(f"[_parse_action_input] All parsers failed for: {input_section[:100]}...")
    return None


def _extract_json_with_balanced_braces(text: str) -> Tuple[Optional[str], str]:
    """
    从文本中提取JSON对象（使用平衡括号匹配算法）
    
    【基于14.0分析增强】补充截断JSON检测（tool_parser.py行65-66）
    
    Args:
        text: 包含JSON的文本
        
    Returns:
        (json_text, content_before_json)
        - json_text: 提取的JSON文本（可能截断）
        - content_before_json: JSON前面的纯文本
    """
    # 寻找第一个 { 或 [
    start_idx = None
    for i, char in enumerate(text):
        if char in '{[':
            start_idx = i
            break
    
    if start_idx is None:
        return None, text.strip()
    
    # 记录JSON前的纯文本
    content_before = text[:start_idx].strip()
    
    # 平衡括号匹配
    # 【修复 小健 2026-05-24】P1-5: 跟踪字符串内花括号，避免JSON值含{}时误匹配
    stack = []
    end_idx = None
    in_string = False
    escape_next = False
    
    for i in range(start_idx, len(text)):
        char = text[i]
        if escape_next:
            escape_next = False
            continue
        if char == '\\' and in_string:
            escape_next = True
            continue
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if char in '{[':
            stack.append(char)
        elif char == '}' and stack and stack[-1] == '{':
            stack.pop()
            if not stack:
                end_idx = i + 1
                break
        elif char == ']' and stack and stack[-1] == '[':
            stack.pop()
            if not stack:
                end_idx = i + 1
                break
    
    if end_idx:
        # 找到完整的JSON
        return text[start_idx:end_idx], content_before
    
    # ==========================================================================
    # 【基于14.0分析新增】截断JSON检测
    # 来源：tool_parser.py (行65-66)
    # 如果JSON被截断（brace_count > 0），返回不完整JSON和前面文本
    # 这允许后续降级策略尝试挽救性解析
    # ==========================================================================
    if stack:  # 括号未闭合，JSON被截断
        # 【修复 小健 2026-05-24】P1-6: 尝试补全缺失的闭合括号，提高截断JSON的挽救率
        truncated = text[start_idx:]
        for _ in range(len(stack)):
            opener = stack.pop()
            closer = '}' if opener == '{' else ']'
            truncated += closer
        return truncated, content_before
    
    # 没有找到完整JSON
    return None, content_before


def _extract_key_value_pairs(text: str) -> Dict[str, Any]:
    """
    使用正则提取key:value对（最终兜底方案）
    
    当所有JSON解析都失败时使用，尽可能提取有用信息
    
    Args:
        text: 原始文本
        
    Returns:
        提取的参数字典
    """
    result = {}
    
    # 匹配 "key": value 或 'key': value 或 key: value 格式
    pattern = r'["\']?(\w+)["\']?\s*:\s*["\']?([^,\}\]\n]+)["\']?'
    matches = re.findall(pattern, text)
    
    for key, value in matches:
        # 尝试转换类型
        value = value.strip()
        if value.lower() == 'true':
            result[key] = True
        elif value.lower() == 'false':
            result[key] = False
        elif value.isdigit():
            result[key] = int(value)
        elif re.match(r'^\d+\.\d+$', value):
            result[key] = float(value)
        else:
            result[key] = value
    
    return result


# =============================================================================
# 导出声明
# =============================================================================

__all__ = [
    "parse_react_response",
    "_parse_action",
    "_parse_answer",
    "_parse_action_input",
    "_parse_thought_only",  # 【新增】14.5节要求的独立函数
    "_extract_json_block",  # 【2026-04-18小沈新增】纯JSON块提取
    "_extract_json_with_balanced_braces",
    "_extract_key_value_pairs",
    "_create_action_result",  # 【2026-04-18小沈新增】创建统一格式结果
    "_extract_tool_params_from_thought",  # 【2026-04-18小沈新增】从thought提取参数
    "REACT_KEYWORDS",
]



