# -*- coding: utf-8 -*-
"""
输入处理器 + 解析入口模块（第6层 - 顶层，依赖所有下层模块）
"""

import re
import json
from typing import Dict, Any, Optional

from app.utils.logger import logger
from ._utils import _add_reasoning_warning, _normalize_result_to_str, _build_handler_result, _get_all_tool_names, _extract_json_with_balanced_braces
from ._tool_params import _normalize_tool_params_content, _filter_tool_params, _process_tool_params
from ._json_strategies import _extract_json_block, _try_parse_non_standard_json
from ._result_builders import _process_json_result, _create_action_result_from_dict, _create_action_result_from_list
from ._keyword_parsers import _determine_parse_type


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

    result = _process_json_result(non_std_data, output)
    if result is not None:
        if result.get("type") == "parse_error":
            result["error"] = non_std_data.get("error", "非标准JSON解析错误")
        logger.info(f"[parse_react_response] 非标准JSON解析成功")
        return result
    return None


# ---------------------------------------------------------------------------
# Handler #7: 混合文本中提取JSON块 + 不完整JSON检测
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Handler #7: 混合文本中提取JSON块 + 不完整JSON检测
# ---------------------------------------------------------------------------

def _handle_incomplete_json(output: str) -> Optional[Dict[str, Any]]:
    """处理不完整JSON：检测是否像截断的JSON，尝试正则兜底
    
    与 Handler #8 的区别：
    - 本函数：JSON 提取失败后的降级，针对"看起来像截断的JSON"的特定情况
    - Handler #8：所有 JSON 解析都失败后的最终兜底，针对任意输入
    
    错误处理路径：
    - 像不完整JSON + 正则成功 → 返回 action（带 warning）
    - 像不完整JSON + 正则失败 → 返回 chunk
    - 不像不完整JSON → 返回 None（交给下一个 handler）
    """
    if not re.match(r'^\s*\{\s*"thought":\s*"', output):
        return None

    regex_recovered = _try_regex_tool_call_fallback(output)
    if regex_recovered:
        logger.info("不完整JSON但正则兜底提取到tool调用")
        return _add_reasoning_warning(regex_recovered)

    thought_text = output.strip()
    logger.info("检测到不完整JSON格式，返回chunk")
    return _build_handler_result("chunk", thought=thought_text)


def _handle_finish_tool(json_data: Dict, prefix_text: str) -> Optional[Dict[str, Any]]:
    """处理 tool_name == "finish" 的情况
    
    错误处理路径：
    - tool_params.result 存在 → 拼接 prefix_text + result_text
    - tool_params.result 不存在 → 返回空 content
    - prefix_text 为空 → 直接用 result_text
    """
    tool_params = json_data.get("tool_params", {})
    if not isinstance(tool_params, dict):
        tool_params = {}

    raw_result = tool_params.get("result") if tool_params else None
    result_text = _normalize_result_to_str(raw_result) if raw_result is not None else ""

    if prefix_text and result_text:
        content = prefix_text + ("\n\n" + result_text if result_text not in prefix_text else "")
    else:
        content = prefix_text or result_text or ""

    thought = prefix_text or json_data.get("thought", "")
    return _build_handler_result("answer", thought=thought,
        content=content, response=content)


def _handle_implicit_content(json_data: Dict, output: str, prefix_text: str) -> Optional[Dict[str, Any]]:
    """处理有 content/reasoning 但无 tool_name 的隐式解析
    
    错误处理路径：
    - output 包含 "Action:" 或 "Answer:" → 返回 None（让后续 handler 处理）
    - content 是嵌套 JSON 字符串 → 尝试解析提取内层 content
    - content 解析失败 → 保留原始 content
    """
    if "content" not in json_data and "reasoning" not in json_data:
        return None

    if re.search(r'\bAction\s*:', output, re.IGNORECASE) or \
       re.search(r'\bAnswer\s*:', output, re.IGNORECASE):
        return None

    content = json_data.get("content", "")
    reasoning = json_data.get("reasoning", "")

    # 尝试解析嵌套的 content JSON（如 content 字段本身是 JSON 字符串）
    if isinstance(content, str) and content.startswith("{"):
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                content = parsed.get("content", content)
        except (json.JSONDecodeError, TypeError):
            pass  # 解析失败，保留原始 content

    return _build_handler_result("implicit", thought=prefix_text or content,
        content=content, reasoning=reasoning, response=content)


def _handle_mixed_text_json(output) -> Optional[Dict[str, Any]]:
    if not isinstance(output, str):
        return None

    json_data = _extract_json_block(output)
    prefix_text = ""
    if json_data:
        json_start = output.find("{")
        prefix_text = output[:json_start].strip() if json_start != -1 else ""

    # 没有 JSON 块：尝试不完整 JSON 处理
    if not json_data:
        return _handle_incomplete_json(output)

    if not isinstance(json_data, dict):
        return None

    tool_name = json_data.get("tool_name")
    tool_params = json_data.get("tool_params", {})
    if not isinstance(tool_params, dict):
        tool_params = {}

    # tool_name == "finish" → 返回 answer
    if tool_name == "finish":
        return _handle_finish_tool(json_data, prefix_text)

    # 有 tool_name → 返回 action
    if tool_name:
        extracted = json_data.get("content", "") or prefix_text
        params = _process_tool_params(tool_params, tool_name, output)
        return _build_handler_result("action", thought=json_data.get("thought", ""),
            content=extracted, tool_name=tool_name, tool_params=params)

    # 有 content/reasoning → 隐式解析
    return _handle_implicit_content(json_data, output, prefix_text)


# ---------------------------------------------------------------------------
# Handler #8: 正则兜底
# ---------------------------------------------------------------------------
# Handler #8: 正则兜底（所有 JSON 解析失败后的最终兜底）
# 与 _handle_incomplete_json 的区别：本 handler 不检查输入格式，直接尝试正则
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
# Handler #9: 已知工具名匹配（从内容中提取工具名）
# ---------------------------------------------------------------------------
def _handle_known_tool_match(output) -> Optional[Dict[str, Any]]:
    if not isinstance(output, str):
        return None

    logger.info(f"[parse_react_response] 尝试已知工具名匹配流程")

    known_tool_names = _get_all_tool_names()
    if not known_tool_names:
        return None

    # 构建单个正则，一次匹配所有工具名（O(m) 替代 O(n×m)）
    escaped_names = [re.escape(name) for name in known_tool_names]
    combined_pattern = rf'(?i)\b({"|".join(escaped_names)})\b'
    match = re.search(combined_pattern, output)
    if not match:
        logger.info(f"[parse_react_response] 未找到已知工具名")
        return None

    tool_name = match.group(1)
    logger.info(f"[parse_react_response] 在内容中找到已知工具名: {tool_name}")

    params = {}
    path_pattern = r'["\']?([\w\-/\.]+\.(?:txt|md|py|json|yaml|yml|csv|xlsx|xls|doc|docx|pdf|jpg|jpeg|png|gif))["\']?'
    path_matches = re.findall(path_pattern, output, re.IGNORECASE)
    if path_matches:
        params["path"] = path_matches[0]

    content_pattern = r'["\']content["\']?\s*:\s*["\']([^"\']+)["\']'
    content_match = re.search(content_pattern, output)
    if content_match:
        params["content"] = content_match.group(1)

    return {
        "type": "action",
        "thought": output[:200] + ("..." if len(output) > 200 else ""),
        "content": output,
        "reasoning": "",
        "tool_name": tool_name,
        "tool_params": params if params else {"unknown_params": True},
        "response": None,
        "error": None
    }


# ---------------------------------------------------------------------------
# Handler #10: 关键词匹配（最终兜底）
# ---------------------------------------------------------------------------
def _handle_keyword_match(output) -> Optional[Dict[str, Any]]:
    logger.info(f"[parse_react_response] 走关键词匹配流程")
    return _determine_parse_type(output) if isinstance(output, str) else None


# ---------------------------------------------------------------------------
# 解析器链配置：按优先级顺序排列
# ---------------------------------------------------------------------------
_HANDLERS = [
    _handle_dict_input,
    _handle_list_input,
    _handle_json_array_string,
    _handle_empty_input,
    _handle_standard_json,
    _handle_non_standard_json,
    _handle_mixed_text_json,
    _handle_regex_fallback,
    _handle_known_tool_match,
    _handle_keyword_match,
]


def parse_react_response(output: str) -> Dict[str, Any]:
    output_length = len(output) if isinstance(output, str) else 0
    logger.info(f"[parse_react_response] 解析器链开始, output长度: {output_length}")

    for handler in _HANDLERS:
        result = handler(output)
        if result is not None:
            return result

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


def _try_regex_tool_call_fallback(output: str) -> Optional[Dict[str, Any]]:
    if not output or not isinstance(output, str):
        return None
    matches = list(re.finditer(r'"tool_name"\s*:\s*"([^"]+)"', output))
    if not matches:
        return None
    tool_name = matches[-1].group(1).strip()
    if not tool_name:
        return None
    if tool_name == "finish":
        tp: Dict[str, Any] = {}
        tp_marks = list(re.finditer(r'"tool_params"\s*:\s*\{', output))
        tp_mark = tp_marks[-1] if tp_marks else None
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
        finish_mark = list(re.finditer(r'"tool_name"\s*:\s*"finish"', output))
        if finish_mark:
            prefix_text = output[:finish_mark[-1].start()].strip()
            content = prefix_text + ("\n\n" + result_text if result_text and result_text not in prefix_text else "")
        else:
            content = result_text or ""
        return {
            "type": "answer",
            "thought": content[:200],
            "content": content,
            "reasoning": "",
            "tool_name": None,
            "tool_params": None,
            "response": content,
            "error": None
        }
    try:
        from app.services.tools.registry import tool_registry
        if tool_registry.get_implementation(tool_name) is None:
            return None
    except Exception:
        return None

    tp: Dict[str, Any] = {}
    tp_marks = list(re.finditer(r'"tool_params"\s*:\s*\{', output))
    tp_mark = tp_marks[-1] if tp_marks else None
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
