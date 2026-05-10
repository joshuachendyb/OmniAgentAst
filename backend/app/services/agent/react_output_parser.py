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
from typing import Dict, Any, Optional, Tuple

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

def parse_react_response(output: str) -> Dict[str, Any]:
    """
    统一解析器入口函数
    
    处理LLM的所有ReAct输出格式，返回统一结构字典
    通过type字段区分：action/answer/implicit/thought_only
    
    Args:
        output: LLM原始响应文本
        
    Returns:
        统一格式字典，包含type/thought/tool_name/tool_params/response字段
        补充兼容性字段content/reasoning确保与base_react.py平滑迁移
        
    设计依据: LlamaIndex ReActOutputParser.parse() 统一入口设计思想
    """
    from app.utils.logger import logger
    
    # 【2026-04-28 小沈修复】在函数开头处理 dict 输入
    # 如果传入的是 dict（而非 JSON 字符串），直接解析并返回
    if isinstance(output, dict):
        logger.info(f"[parse_react_response] 检测到dict输入，直接解析")
        return _create_action_result_from_dict(output)
    
    # 【2026-04-28 小沈新增】处理 list 输入（数组）
    # LLM可能返回JSON数组，如：[{"tool_name": "xxx", ...}]
    if isinstance(output, list):
        logger.info(f"[parse_react_response] 检测到list输入，解析数组")
        return _create_action_result_from_list(output)
    
    # 【2026-04-28 小沈新增】处理 JSON 数组字符串
    # LLM可能返回JSON数组字符串，如：'[{"tool_name": "xxx", ...}]'
    # 需要先解析为list，再调用list处理函数
    if isinstance(output, str) and output.strip().startswith("["):
        try:
            parsed_list = json.loads(output)
            if isinstance(parsed_list, list):
                logger.info(f"[parse_react_response] 检测到JSON数组字符串，解析为list处理")
                return _create_action_result_from_list(parsed_list)
        except (json.JSONDecodeError, TypeError):
            pass  # 不是有效的JSON数组，继续其他处理
    
    output_length = len(output) if isinstance(output, str) else 0
    logger.info(f"[parse_react_response] 调用新统一解析器, output长度: {output_length}")
    
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
    
    # 【兼容 2026-04-16 小沈】预检查：如果输入是已格式化的JSON字典
    # 包含tool_name/tool_params或action/action_input字段，直接返回解析结果
    # 用途：兼容旧测试用例和直接传入JSON dict的场景
    try:
        # 【2026-04-28 小沈修复】支持 dict 和 string 两种输入
        if isinstance(output, dict):
            data = output
        else:
            data = json.loads(output)
        
        if isinstance(data, dict):
            # 新字段格式
            if "tool_name" in data:
                tool_name = data["tool_name"]
                is_finish = tool_name == "finish"
                
                # response处理：finish类型从tool_params.result获取
                if is_finish and data.get("tool_params", {}).get("result"):
                    response = data["tool_params"]["result"]
                else:
                    response = data.get("response", "")
                
                # 【2026-04-28 小沈新增】检测必需参数是否完整
                processed_tool_params = None if is_finish else _filter_tool_params(_normalize_tool_params_content(data.get("tool_params", data.get("args", {}))))
                if not is_finish and processed_tool_params:
                    processed_tool_params = _supplement_missing_params(tool_name, processed_tool_params, output if isinstance(output, str) else None)
                
                return {
                    "type": "answer" if is_finish else "action",
                    "thought": data.get("content", data.get("thought", "")),
                    "content": data.get("content", data.get("thought", "")),
                    "reasoning": data.get("reasoning", ""),
                    "tool_name": None if is_finish else tool_name,
                    "tool_params": processed_tool_params,
                    "response": response
                }
            # 旧字段格式（action/action_input → tool_name/tool_params）
            if "action" in data:
                action_name = data["action"]
                is_finish = action_name == "finish"
                
                # response处理：finish类型从action_input.result获取
                if is_finish and data.get("action_input", {}).get("result"):
                    response = data["action_input"]["result"]
                else:
                    response = ""
                
                logger.info(f"[parse_react_response] JSON预解析命中(旧格式), type=action/answer")
                # 【2026-04-28 小沈修复】支持args字段，并过滤非参数字段
                tool_params = data.get("action_input", data.get("args", {}))
                return {
                    "type": "answer" if is_finish else "action",
                    "thought": data.get("thought", ""),
                    "content": data.get("thought", ""),
                    "reasoning": data.get("reasoning", ""),
                    "tool_name": None if is_finish else action_name,
                    "tool_params": None if is_finish else _filter_tool_params(_normalize_tool_params_content(tool_params)),
                    "response": response
                }
    except (json.JSONDecodeError, TypeError):
        pass  # 不是JSON格式，继续走关键词匹配流程
    
    # 【2026-04-28 小沈新增】尝试解析非标准JSON（单引号）
    # 标准JSON解析失败后，尝试解析单引号JSON
    non_std_data = _try_parse_non_standard_json(output)
    if non_std_data and isinstance(non_std_data, dict):
        if "tool_name" in non_std_data:
            tool_name = non_std_data["tool_name"]
            is_finish = tool_name == "finish"
            # 【2026-04-28 小沈修复】支持args字段
            tool_params = non_std_data.get("tool_params", non_std_data.get("args", {}))
            
            # 标准化tool_params中的content字段类型
            if isinstance(tool_params, dict):
                tool_params = _normalize_tool_params_content(tool_params)
                # 【2026-04-28 小沈新增】过滤非参数字段
                tool_params = _filter_tool_params(tool_params)
                # 【2026-04-28 小沈新增】检测并补充缺失的必需参数
                if not is_finish and tool_params:
                    tool_params = _supplement_missing_params(tool_name, tool_params, output if isinstance(output, str) else None)
            
            logger.info(f"[parse_react_response] 非标准JSON解析成功")
            return {
                "type": "answer" if is_finish else "action",
                "thought": non_std_data.get("content", non_std_data.get("thought", "")),
                "content": non_std_data.get("content", non_std_data.get("thought", "")),
                "reasoning": non_std_data.get("reasoning", ""),
                "tool_name": None if is_finish else tool_name,
                "tool_params": None if is_finish else tool_params,
                "response": ""
            }
    
    # 【新增 2026-04-24 小沈】JSON预解析失败后，尝试从混合文本中提取JSON块
    # 解决混合文本+JSON（情况③/⑤）的解析问题：LLM返回"思考文本+JSON"格式时正确提取
    json_data = _extract_json_block(output)
    
    # 【新增 2026-04-26 小沈】检测不完整JSON格式
    # 问题来源：日志 app_2026-04-25.log 23:23:43 LLM原始返回被截断
    # 原始文本: {"thought": "用户想查看D盘的目录情况，我需要使用list_directory工具来列出D盘
    # 解析器误将thought值中的"list_directory"识别为可执行action
    #
    # 修复逻辑：
    # 1. 如果json_data为空（JSON提取失败）
    # 2. 且原始文本匹配 {"thought": "xxx" 格式（不完整JSON）
    # 3. 则返回implicit类型，不误识别为action
    #
    # 测试用例:
    #   输入: {"thought": "用户想查看D盘的目录情况，我需要使用list_directory工具来列出D盘"
    #   修复前: type=action, tool_name=list_directory  (误识别)
    #   修复后: type=implicit, tool_name=None, thought=原始文本 (正确)
    if not json_data:
        if re.match(r'^\s*\{\s*"thought":\s*"', output):
            thought_text = output.strip()
            logger.info("[parse_react_response] 检测到不完整JSON格式，返回implicit")
            return {
                "type": "implicit",
                "thought": thought_text,
                "content": thought_text,
                "reasoning": thought_text,
                "tool_name": None,
                "tool_params": None,
                "response": thought_text,
                "error": None
            }
    
    if json_data and isinstance(json_data, dict):
        # 提取前面的文本（JSON之前的部分）作为content
        # 找到第一个'{'的位置，前面的文本就是content
        json_start = output.find('{')
        if json_start != -1:
            prefix_text = output[:json_start].strip()
        else:
            prefix_text = ""
        
        # 获取tool_name并检查是否为finish
        tool_name = json_data.get("tool_name")
        tool_params = json_data.get("tool_params", {})
        
        # 确保tool_params是字典
        if not isinstance(tool_params, dict):
            tool_params = {}
        
        # 如果是finish类型
        if tool_name == "finish":
            logger.info("[parse_react_response] 混合文本中提取到finish JSON")
            result_text = tool_params.get("result", "") if tool_params else ""
            return {
                "type": "answer",
                "thought": json_data.get("thought", ""),
                "content": result_text or prefix_text,
                "reasoning": json_data.get("reasoning", ""),
                "tool_name": None,
                "tool_params": None,
                "response": result_text or prefix_text,
                "error": None
            }
        
        # 其他情况（有tool_name且不是finish）
        if tool_name:
            logger.info("[parse_react_response] 混合文本中提取到JSON，走JSON处理流程")
            # 【2026-04-28 小沈修复】优先使用json_data中的content字段，而不是prefix_text
            extracted_content = json_data.get("content", "")
            # 如果json_data中没有content字段，才使用prefix_text
            if not extracted_content:
                extracted_content = prefix_text
            # 【2026-04-28 小沈新增】检测并补充缺失的必需参数
            if tool_params:
                tool_params = _supplement_missing_params(tool_name, tool_params, output if isinstance(output, str) else None)
            return {
                "type": "action",
                "thought": json_data.get("thought", ""),
                "content": extracted_content,
                "reasoning": json_data.get("reasoning", ""),
                "tool_name": tool_name,
                "tool_params": tool_params,
                "response": None,
                "error": None
            }
        # 如果是finish类型的JSON
        if json_data.get("tool_name") == "finish":
            result_text = tool_params.get("result", "") if tool_params else "" if isinstance(tool_params, dict) else ""
            logger.info("[parse_react_response] 混合文本中提取到finish JSON")
            return {
                "type": "answer",
                "thought": json_data.get("thought", ""),
                "content": result_text or prefix_text,
                "reasoning": json_data.get("reasoning", ""),
                "tool_name": None,
                "tool_params": None,
                "response": result_text or prefix_text,
                "error": None
            }
        
        # 2026-05-02 小强新增：处理无tool_name但有content/reasoning的JSON
        # LLM可能返回 {"content": "xxx", "reasoning": "yyy"} 格式（缺少tool_name）
        # 此时应该正确提取content和reasoning字段，而不是把整个JSON当作字符串
        # 
        # 但要排除情况：JSON是Action Input的参数值而非顶层结构
        # 判断依据：JSON前面有Action/Answer关键词则走关键词匹配
        if "content" in json_data or "reasoning" in json_data:
            # 检查是否前面有Action/Answer关键词
            has_action_keyword = re.search(r'\bAction\s*:', output, re.IGNORECASE)
            has_answer_keyword = re.search(r'\bAnswer\s*:', output, re.IGNORECASE)
            if not has_action_keyword and not has_answer_keyword:
                logger.info("[parse_react_response] 检测到无tool_name的JSON，提取content/reasoning字段")
                content_value = json_data.get("content", "")
                reasoning_value = json_data.get("reasoning", "")
                # content和reasoning可能是嵌套的JSON字符串，需要尝试解析
                if isinstance(content_value, str) and content_value.startswith("{"):
                    try:
                        parsed_content = json.loads(content_value)
                        if isinstance(parsed_content, dict):
                            content_value = parsed_content.get("content", content_value)
                    except (json.JSONDecodeError, TypeError):
                        pass
                return {
                    "type": "implicit",
                    "thought": prefix_text or content_value,
                    "content": content_value,
                    "reasoning": reasoning_value,
                    "tool_name": None,
                    "tool_params": None,
                    "response": content_value,
                    "error": None
                }
    
    # 【新增 2026-05-10 小沈】关键词兜底前：正则恢复末尾 tool 调用（恶意/破损 JSON 之后的最后一道 structured 解析）
    regex_recovered = _try_regex_tool_call_fallback(output)
    if regex_recovered:
        logger.info("[parse_react_response] 正则兜底提取到 tool 调用，跳过关键词匹配")
        return _add_reasoning_warning(regex_recovered)

    # 步骤1.2：四种情况判断逻辑
    logger.info(f"[parse_react_response] 走关键词匹配流程")
    return _determine_parse_type(output)


# =============================================================================
# 步骤1.2：实现四种情况判断逻辑
# =============================================================================

def _determine_parse_type(output: str) -> Dict[str, Any]:
    """
    【2026-04-18小沈优化】判断LLM输出类型并调用对应解析函数
    
    调整后的优先级顺序：
    ① ```包裹检测 - 最高优先级
    ② 纯JSON块检测 - 第二优先级  
    ③ 关键词匹配 - 第三优先级
    ④ 工具名兜底 - 最低优先级
    
    【新增】统一的异常处理机制
    """
    if not output or not output.strip():
        return {"type": "parse_error", "error": "Empty output", "thought": "", "content": "", "reasoning": "", "tool_name": None, "tool_params": None, "response": ""}
    
    output = output.strip()
    
    # ① 【最高优先级】```包裹JSON解析
    # 【2026-04-19小沈优化】删除了对tool_parser.ToolParser的依赖，直接解析```块
    try:
        if '```' in output:
            # 提取```块内的JSON
            json_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', output)
            if json_match:
                json_str = json_match.group(1).strip()
                json_data = json.loads(json_str)
                if "tool_name" in json_data:
                    return _create_action_result(json_data, output)
    except Exception as e:
        # 记录日志，继续尝试下一个优先级
        from app.utils.logger import logger
        logger.debug(f"```包裹JSON解析失败: {e}")
    
    # ② 【第二优先级】纯JSON块检测（无```包裹）
    try:
        json_data = _extract_json_block(output)
        if json_data and "tool_name" in json_data:
            return _create_action_result(json_data, output)
    except Exception as e:
        from app.utils.logger import logger
        logger.debug(f"纯JSON块检测失败: {e}")
    
    # ③ 【第三优先级】关键词匹配（传统ReAct格式）
    try:
        # 定位关键词位置
        thought_match = re.search(REACT_KEYWORDS["thought"], output, re.IGNORECASE)
        action_match = re.search(REACT_KEYWORDS["action"], output, re.IGNORECASE)
        answer_match = re.search(REACT_KEYWORDS["answer"], output, re.IGNORECASE)
        
        # 获取位置索引（未匹配设为无穷大）
        action_idx = action_match.start() if action_match else float('inf')
        answer_idx = answer_match.start() if answer_match else float('inf')
        
        # 情况B: 有Action（且Action在Answer之前）- Action优先规则
        if action_match and action_idx < answer_idx:
            return _parse_action(output, thought_match, action_match)
        
        # 情况C: 有Answer
        if answer_match:
            return _parse_answer(output, thought_match, answer_match)
        
        # 情况D: 只有Thought（有Thought标记但无Action/Answer）
        if thought_match:
            return _parse_thought_only(output, thought_match)
    except Exception as e:
        from app.utils.logger import logger
        logger.debug(f"关键词匹配失败: {e}")
    
    # ④ 【最低优先级】工具名兜底
    try:
        tool_result = _extract_by_known_tools(output)
        if tool_result:
            # 【2026-04-28 小沈新增】检测并补充缺失的必需参数
            tp = tool_result.get("tool_params")
            if tp:
                tp = _supplement_missing_params(tool_result["tool_name"], tp, output if isinstance(output, str) else None)
            return {
                "type": "action",
                "thought": tool_result["content"],
                "content": tool_result["content"],      # 兼容性字段
                "reasoning": tool_result["content"],    # 兼容性字段
                "tool_name": tool_result["tool_name"],
                "tool_params": tp,
                "response": None,
                "error": None
            }
    except Exception as e:
        from app.utils.logger import logger
        logger.debug(f"工具名兜底失败: {e}")
    
    # 所有解析方法都失败，根据输出长度判断返回implicit或parse_error
    # 【恢复 2026-04-24 小沈】纯文本无关键词时，长文本返回implicit，短文本返回parse_error
    stripped = output.strip()
    if len(stripped) >= 5:
        # 纯文本情况，返回implicit类型
        return {
            "type": "implicit",
            "thought": stripped,
            "content": stripped,             # 兼容性字段
            "reasoning": stripped,           # 兼容性字段
            "tool_name": None,
            "tool_params": None,
            "response": stripped,
            "error": None
        }
    else:
        # 很短的输出，返回parse_error
        return {
            "type": "parse_error",
            "error": "无法解析LLM响应，所有解析层（JSON/关键词/工具名）都失败",
            "thought": stripped[:200],
            "content": stripped[:200],
            "reasoning": stripped[:200],
            "tool_name": None,
            "tool_params": None,
            "response": stripped
        }


# =============================================================================
# 【必选】步骤1.5：实现纯思考内容提取函数（设计文档14.5节要求）
# =============================================================================

def _parse_thought_only(output: str, thought_match: re.Match) -> Dict[str, Any]:
    """
    提取纯思考内容（无Action/Answer的场景）
    
    来源：设计文档第14章 14.5节
    重要性：独立函数便于单独测试和复用
    
    Args:
        output: LLM原始响应文本
        thought_match: Thought关键词的re.Match对象
        
    Returns:
        统一格式解析结果，type="thought_only"
    """
    thought_text = output[thought_match.end():].strip()
    return {
        "type": "thought_only",
        "thought": thought_text,
        "content": thought_text,          # 兼容性字段
        "reasoning": thought_text,        # 兼容性字段
        "tool_name": None,
        "tool_params": None,
        "response": None
    }


# =============================================================================
# 【2026-04-18 小沈新增】纯JSON块提取函数
# 用于从无```包裹的LLM响应中提取JSON对象
# 解决兜底函数_extract_by_known_tools错误提取参数的问题
# =============================================================================

def _extract_json_block(content: str) -> Optional[Dict[str, Any]]:
    """
    【P0-必须新增】从纯JSON块（无```包裹）中提取数据
    
    处理以下情况：
    1. 纯JSON：{"tool_name": "xxx", "tool_params": {...}}
    2. 文本+JSON：some text {"tool_name": "xxx"...}
    3. JSON中的实际换行符
    
    【2026-04-18小沈优化】简化逻辑，移除冗余的状态处理
    - _extract_json_with_balanced_braces()已包含完整的字符串状态处理
    - 不需要在调用前再进行一次状态处理
    
    Args:
        content: LLM响应文本
        
    Returns:
        解析后的字典，或None（解析失败）
    """
    if not content:
        return None
    
    import re  # 确保re可用
    
    content = content.strip()
    
    # 直接使用平衡括号算法提取JSON（已包含字符串状态处理）
    json_str, _ = _extract_json_with_balanced_braces(content)
    
    if not json_str:
        return None
    
    json_str_escaped = json_str  # 初始化默认
    json_str_fixed = json_str    # 初始化默认
    
    # 尝试直接解析
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # 失败原因1: 编码问题 - 尝试用errors='replace'
        try:
            json_fixed = json_str.encode('utf-8', errors='replace').decode('utf-8')
            return json.loads(json_fixed)
        except:
            pass
    
    # 失败原因2: 未转义换行符 - 用空格替换
    try:
        json_str_escaped = json_str.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
        return json.loads(json_str_escaped)
    except json.JSONDecodeError:
        pass
    
    # 失败原因3: 尾随逗号 - 修复后重试
    try:
        json_str_fixed = re.sub(r',(\s*[}\]])', r'\1', json_str_escaped)
        return json.loads(json_str_fixed)
    except json.JSONDecodeError:
        pass
    
# 【新增强降级】如果JSON提取成功但解析失败，尝试手动提取tool_params
    # 这是最后的fallback确保不丢失参数
    try:
        # 【2026-04-27 小沈修复】使用平衡括号算法替代正则表达式
        # 问题：正则 `[^}]+` 无法正确匹配嵌套 `}` 的JSON对象，导致 file_pattern 丢失
        # 修复：使用 _extract_json_with_balanced_braces 正确提取完整的 JSON 对象
        
        # 先尝试直接解析整个 json_str
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        
        # 【2026-04-28 小沈修复】使用平衡括号算法正确提取所有字段（包括长文本content）
        # 问题：正则 `"content":\s*"([^"]*)"` 无法正确匹配含引号/换行的长文本
        # 修复：使用 _extract_json_with_balanced_braces 提取每个字段的完整值
        
        result = {}
        
        # 1. 提取 tool_name（使用平衡括号算法）
        tn_start_pattern = r'"tool_name"\s*:\s*"'
        tn_start_match = re.search(tn_start_pattern, json_str)
        if tn_start_match:
            # 从 tool_name 位置开始提取
            json_after_tn, _ = _extract_json_with_balanced_braces(json_str[tn_start_match.start():])
            if json_after_tn:
                try:
                    partial_json = json.loads(json_after_tn)
                    result["tool_name"] = partial_json.get("tool_name", "")
                except:
                    # 备用：从文本中提取
                    tool_name_match = re.search(r'"tool_name":\s*"([^"]+)"', json_str)
                    if tool_name_match:
                        result["tool_name"] = tool_name_match.group(1)
        
        # 2. 提取 tool_params（使用平衡括号算法）
        # 【2026-04-28 小沈修复】确保正确提取嵌套的tool_params对象
        tp_start_pattern = r'"tool_params"\s*:\s*\{'
        tp_start_match = re.search(tp_start_pattern, json_str)
        if tp_start_match:
            # 从 tool_params 位置开始，使用平衡括号算法提取完整对象
            json_after_tp, _ = _extract_json_with_balanced_braces(json_str[tp_start_match.start():])
            if json_after_tp:
                # 尝试直接解析整个提取的JSON（包含 "tool_params": {...}）
                try:
                    partial_json = json.loads(json_after_tp)
                    # 如果解析成功，检查是 {"tool_params": {...}} 还是直接是 {...}
                    if "tool_params" in partial_json:
                        tp = partial_json.get("tool_params", {})
                    else:
                        # 没有外层tool_params键，可能是直接返回的params对象
                        tp = partial_json
                except:
                    # 如果直接解析失败，尝试提取tool_params内部的内容
                    try:
                        # 去掉外层的 "tool_params": 部分，提取内部对象
                        inner_start = json_after_tp.find('{', json_after_tp.find('tool_params'))
                        if inner_start != -1:
                            inner_json, _ = _extract_json_with_balanced_braces(json_after_tp[inner_start:])
                            if inner_json:
                                tp = json.loads(inner_json)
                            else:
                                tp = {}
                        else:
                            tp = {}
                    except:
                        # 【2026-04-28 小沈新增】当JSON解析失败时，使用正则提取参数
                        # 处理content字段包含中文引号的情况
                        tp = _extract_params_by_regex_from_json_str(json_after_tp)
            
            else:
                tp = {}
        else:
            tp = {}
        
        # 【2026-04-28 小沈新增】如果tp仍然为空，尝试用正则提取
        if not tp:
            tp = _extract_params_by_regex_from_json_str(json_str)
        
        if tp:
            result["tool_params"] = tp
        
        # 3. 提取 content（使用平衡括号算法修复长文本截断问题）
        ct_start_pattern = r'"content"\s*:\s*"'
        ct_start_match = re.search(ct_start_pattern, json_str)
        if ct_start_match:
            # 从 content 位置开始提取，使用平衡括号算法处理引号内的内容
            json_after_ct, _ = _extract_json_with_balanced_braces(json_str[ct_start_match.start():])
            if json_after_ct:
                try:
                    partial_json = json.loads(json_after_ct)
                    content_value = partial_json.get("content", "")
                    content_fixed = content_value.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                    result["content"] = content_fixed
                    result["thought"] = content_fixed
                except:
                    # 【2026-04-28 小沈修复】如果解析失败，使用平衡引号算法提取content值
                    # 处理content字段包含中文引号的情况
                    content_fixed = _extract_content_value_from_json_str(json_str)
                    if content_fixed:
                        result["content"] = content_fixed
                        result["thought"] = content_fixed
        
        # 4. 提取 reasoning（使用平衡括号算法）
        rs_start_pattern = r'"reasoning"\s*:\s*"'
        rs_start_match = re.search(rs_start_pattern, json_str)
        if rs_start_match:
            json_after_rs, _ = _extract_json_with_balanced_braces(json_str[rs_start_match.start():])
            if json_after_rs:
                try:
                    partial_json = json.loads(json_after_rs)
                    reasoning_value = partial_json.get("reasoning", "")
                    reasoning_fixed = reasoning_value.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                    result["reasoning"] = reasoning_fixed
                except:
                    reasoning_match = re.search(r'"reasoning":\s*"([^"]*)"', json_str)
                    if reasoning_match:
                        reasoning_fixed = reasoning_match.group(1).encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                        result["reasoning"] = reasoning_fixed
        
        # 【修复 2026-05-10 小沈】仅有 tool_name、tool_params 解析失败时仍返回，交由 executor/补充参数兜底
        if result.get("tool_name"):
            if not result.get("tool_params"):
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
    if not tool_name or tool_name == "finish":
        return None
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
    
    tool_name = data.get("tool_name")
    # 【2026-04-28 小沈修复】支持args字段（LLM可能返回args而非tool_params）
    tool_params = data.get("tool_params", data.get("args", {}))
    # 【2026-04-28 小沈修复】thought字段独立获取，不被content字段覆盖
    thought = data.get("thought", "")
    content = data.get("content", thought)
    reasoning = data.get("reasoning", "")
    
    # 【2026-04-28 小沈新增】标准化tool_params中的content字段类型
    # 处理数字、布尔值等非字符串类型
    if isinstance(tool_params, dict):
        tool_params = _normalize_tool_params_content(tool_params)
    
    # 【2026-04-28 小沈新增】过滤tool_params中的非参数字段（如reasoning、thought等）
    if isinstance(tool_params, dict):
        tool_params = _filter_tool_params(tool_params)
    
    # finish 类型处理
    if tool_name == "finish":
        result_text = tool_params.get("result", "") if isinstance(tool_params, dict) else ""
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
    
    # action 类型
    # 【2026-04-28 小沈修复】thought字段独立获取，不被content字段覆盖
    # 【2026-04-28 小沈新增】检测并补充缺失的必需参数
    # 【改进7 2026-05-01 小沈 小健】添加reasoning验证
    final_tool_params = tool_params if tool_params is not None else None
    if final_tool_params:
        final_tool_params = _supplement_missing_params(tool_name, final_tool_params, None)
    result = {
        "type": "action",
        "thought": thought,
        "content": content,
        "reasoning": reasoning,
        "tool_name": tool_name,
        "tool_params": final_tool_params,
        "response": None,
        "error": None
    }
    return _add_reasoning_warning(result)


def _create_action_result_from_list(data: list) -> Dict[str, Any]:
    """
    【2026-04-28 小沈新增】从 list 输入创建统一格式的结果
    处理LLM返回的JSON数组场景
    
    Args:
        data: 已经解析好的 list（来自 LLM 返回的 JSON 数组）
        
    Returns:
        统一格式的结果字典
    """
    from app.utils.logger import logger
    
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
    logger.info(f"[parse_react_response] list解析成功，使用最后一个元素")
    
    return _create_action_result_from_dict(last_item)


def _normalize_tool_params_content(tool_params: Dict) -> Dict:
    """
    【2026-04-28 小沈新增】标准化tool_params中的content字段类型
    确保content字段始终为字符串，处理数字、布尔值等类型
    
    Args:
        tool_params: 原始tool_params字典
        
    Returns:
        标准化后的tool_params字典
    """
    if not isinstance(tool_params, dict):
        return tool_params
    
    # 复制一份避免修改原始数据
    normalized = dict(tool_params)
    
    # 检查content字段
    if "content" in normalized:
        content_value = normalized["content"]
        
        # 数字类型转换为字符串
        if isinstance(content_value, (int, float)):
            normalized["content"] = str(content_value)
        # 布尔类型转换为字符串
        elif isinstance(content_value, bool):
            normalized["content"] = str(content_value)
        # 列表/字典类型转换为JSON字符串
        elif isinstance(content_value, (list, dict)):
            normalized["content"] = json.dumps(content_value, ensure_ascii=False)
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
    import re
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
    
    根据TOOL_REQUIRED_PARAMS定义的工具必需参数列表，检查LLM返回的参数字典是否完整。
    如果存在缺失，尝试从LLM原始输出中提取缺失的参数值。
    
    检测逻辑：
    1. 查找tool_name在TOOL_REQUIRED_PARAMS中定义的必需参数列表
    2. 遍历必需参数，检查是否都存在于tool_params中
    3. 如果有缺失，尝试用正则从original_output中提取：
       - 匹配 "param_name": "value" 或 param_name: value 格式
       - 兼容file_path和path参数的互相提取
    4. 如果仍无法补充，返回(None, True)让调用方返回parse_error
    
    Args:
        tool_name: 工具名称（如write_file, read_file, list_directory等）
        tool_params: 已解析的参数字典（可能缺少必需参数）
        original_output: LLM原始输出文本（用于从中提取缺失的参数值）
        
    Returns:
        tuple: (补充后的参数字典, 是否有缺失)
            - 如果成功补充或无需补充: (完整参数字典, False)
            - 如果无法补充必需参数: (None, True)
            
    示例:
        # write_file需要file_path和content两个必需参数
        >>> _check_missing_required_params("write_file", {"file_path": "a.txt"}, '{"tool_name":"write_file","tool_params":{"file_path":"a.txt","content":"内容"}}')
        ({"file_path": "a.txt", "content": "内容"}, False)
        
        # 缺失必需参数且无法补充
        >>> _check_missing_required_params("write_file", {"file_path": "a.txt"}, None)
        (None, True)
    """
    from app.utils.logger import logger
    
    # 必需参数校验已删除 - 小健 2026-05-02
    # Pydantic模型在执行时自动校验required参数，此处不再重复检查
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
            import re
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
            import re
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
        import re
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
    
    # 【2026-04-28 小沈新增】过滤tool_params中的非参数字段
    if isinstance(tool_params, dict):
        tool_params = _filter_tool_params(tool_params)
    
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
    
    # action类型
    # 【2026-04-28 小沈新增】检测并补充缺失的必需参数
    # 【改进7 2026-05-01 小沈 小健】添加reasoning验证
    final_tool_params = tool_params
    if final_tool_params:
        final_tool_params = _supplement_missing_params(tool_name, final_tool_params, original_output if isinstance(original_output, str) else None)
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


# =============================================================================
# 【P0-必须新增】步骤1.2.1：实现工具名兜底匹配函数
# =============================================================================

def _extract_by_known_tools(content: str) -> Optional[Dict[str, Any]]:
    """
    【P0-必须新增】通过已知工具名匹配提取action
    
    来源：llm_strategies.py _extract_by_known_tools() (行229-267)
    调用位置：_determine_parse_type() 入口处作为pre-check
    
    当关键词定位失败时，尝试在content中查找已知工具名作为兜底。
    这是系统鲁棒性的关键保障，必须在关键词定位之前执行。
    
    【2026-04-28 小沈修复】增强参数提取逻辑：
    1. 先尝试从tool_params JSON块中提取完整参数（包括content字段）
    2. 再使用正确的参数名（file_path而非path）
    3. 最后才使用简单的正则提取作为兜底
    
    Args:
        content: LLM响应文本
        
    Returns:
        工具信息字典（成功）或None（失败）
        {
            "tool_name": str,       # 匹配到的工具名
            "content": str,         # 原始文本作为thought
            "tool_params": dict     # 提取的参数（完整版）
        }
    """
    content_lower = content.lower()
    
    for tool in _get_all_tool_names():
        # 查找工具名出现位置（单词边界匹配）
        pattern = rf'\b{re.escape(tool)}\b'
        tool_match = re.search(pattern, content_lower, re.IGNORECASE)
        if not tool_match:
            continue
            
        # 【2026-04-28 小沈新增】尝试提取完整的tool_params JSON块
        params = _extract_tool_params_from_text(content, tool_match.start())
        
        if params:
            return {
                "tool_name": tool,
                "content": content,
                "tool_params": params
            }
        
        # 如果上面失败，使用简单的路径提取作为兜底，但使用正确的参数名
        params = {}
        
        # 根据工具类型选择正确的参数名
        path_param_name = "file_path" if tool in ["read_file", "write_file", "delete_file"] else "path"
        
        # 【2026-04-28 小沈修复】同时添加path作为别名，保持向后兼容
        also_add_path_alias = tool in ["read_file", "write_file", "delete_file"]
        
        # 查找路径参数（Windows/Unix路径）
        path_patterns = [
            r'["\']?([A-Za-z]:\\[^"\'\s]+)["\']?',  # Windows路径 C:\path
            r'["\']?(/[^\s"\'<>]+)["\']?',          # Unix路径 /path
        ]
        
        for p in path_patterns:
            matches = re.findall(p, content)
            if matches:
                params[path_param_name] = matches[0]
                # 同时添加path别名以保持向后兼容
                if also_add_path_alias:
                    params["path"] = matches[0]
                break
        
        # 【2026-04-28 小沈修复】即使没有找到路径参数，只要找到了工具名就返回
        # 这确保 "I will list_directory the files" 这种情况也能正确匹配
        return {
            "tool_name": tool,
            "content": content,
            "tool_params": params
        }
    
    return None


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
    from .react_output_parser import _extract_json_with_balanced_braces
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
    # 提取Thought内容
    if thought_match:
        thought_start = thought_match.end()
        thought_end = action_match.start()
        thought = output[thought_start:thought_end].strip()
    else:
        # 关键改进2: 无Thought标记时捕获Action之前的内容
        thought = output[:action_match.start()].strip()
    
    # 定位Action Input
    action_input_match = re.search(REACT_KEYWORDS["action_input"], output, re.IGNORECASE)
    
    # 提取工具名（Action和Action Input之间）
    action_start = action_match.end()
    if action_input_match:
        action_end = action_input_match.start()
        action_section = output[action_start:action_end].strip()
    else:
        # 没有Action Input，取Action之后到行尾
        action_section = output[action_start:].strip()
    
    # 关键改进1: 工具名约束 - 禁止空格和括号
    tool_name_match = re.match(r'^([^\n\(\) ]+)', action_section)
    if tool_name_match:
        tool_name = tool_name_match.group(1)
    else:
        # Action 为空或格式异常时，避免 split()[0] 越界
        parts = action_section.split()
        tool_name = parts[0] if parts else ""
    
    # 提取工具参数
    if action_input_match:
        input_start = action_input_match.end()
        input_section = output[input_start:].strip()
        tool_params = _parse_action_input(input_section)
    else:
        tool_params = {}
    
    # ==========================================================================
    # 【P1-高优先级新增】多字段名映射（兼容不同LLM输出格式）
    # 来源：tool_parser.py (行200-215)
    # 处理不同LLM可能使用的不同字段名
    # ==========================================================================
    # 如果解析到的tool_params中包含备用字段名，进行统一映射
    if isinstance(tool_params, dict):
        # 工具名映射：action -> action_tool -> tool_name
        if not tool_name and "action" in tool_params:
            tool_name = tool_params.pop("action")
        if not tool_name and "action_tool" in tool_params:
            tool_name = tool_params.pop("action_tool")
        
        # 参数映射：params -> action_input -> actionInput
        if "params" in tool_params and "tool_params" not in tool_params:
            tool_params["tool_params"] = tool_params.pop("params")
        if "action_input" in tool_params and "tool_params" not in tool_params:
            tool_params["tool_params"] = tool_params.pop("action_input")
        if "actionInput" in tool_params and "tool_params" not in tool_params:
            tool_params["tool_params"] = tool_params.pop("actionInput")
    
    # 深度检查：如果工具名解析成功但参数解析彻底失败（返回None而非{}）
    if tool_name and tool_params is None:
        return {
            "type": "parse_error",
            "error": f"Failed to parse parameters for tool '{tool_name}' after 5 levels of fallback",
            "thought": thought,
            "content": thought,
            "reasoning": thought,
            "tool_name": tool_name,
            "tool_params": {},
            "response": None
        }

    # 【2026-04-28 小沈新增】检测并补充缺失的必需参数
    final_tool_params = tool_params or {}
    final_tool_params = _supplement_missing_params(tool_name, final_tool_params, None)
    return {
        "type": "action",
        "thought": thought,
        "content": thought,             # 兼容性字段
        "reasoning": thought,           # 兼容性字段
        "tool_name": tool_name,
        "tool_params": final_tool_params,
        "response": None,
        "error": None
    }


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

def _parse_action_input(input_section: str) -> Dict[str, Any]:
    """
    解析Action Input中的JSON参数
    
    实现五级降级策略（原四级+Markdown去除），确保最大限度解析成功
    
    Args:
        input_section: Action Input之后的文本内容
        
    Returns:
        解析后的参数字典（失败返回空字典）
        
    解析策略依据: LlamaIndex action_input_parser 实现 + 现有代码改进
    五级降级策略:
        第0级: Markdown代码块去除（【基于14.0分析修正位置】）
        第1级: 标准json.loads()解析
        第2级: 正则提取JSON片段（平衡括号匹配）- 额外改进
        第3级: 替换单引号为双引号后解析
        第4级: 截断JSON字段提取 + 正则提取key:value对作为兜底
    """
    if not input_section:
        return {}
    
    # 记录原始输入用于错误分析
    from app.utils.logger import logger
    # ==========================================================================
    # 【基于14.0分析修正】第0级: Markdown代码块去除（在_parse_action_input内处理）
    # 原建议位置：parse_react_response() 入口 ❌
    # 修正位置：_parse_action_input() 第0级 ✅
    # 理由：Markdown只包裹JSON参数部分，应在局部精准处理
    # 来源：tool_parser.py (行92-106)
    # ==========================================================================
    json_str = input_section
    
    # 尝试去除Markdown代码块
    md_match = re.search(
        r'```(?:json)?\s*\n?(.*?)\n?```',
        input_section,
        re.DOTALL | re.IGNORECASE
    )
    if md_match:
        json_str = md_match.group(1).strip()
    
    # 第1级: 标准JSON解析
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass
    
    # 第2级: 正则提取JSON片段（平衡括号匹配算法）- 额外改进
    # 来源：tool_parser.py _extract_json_with_balanced_braces()
    try:
        json_match, _ = _extract_json_with_balanced_braces(json_str)
        if json_match:
            return json.loads(json_match)
    except (json.JSONDecodeError, ValueError):
        pass
    
    # 第3级: 替换单引号为双引号
    try:
        # 替换单引号为双引号，但保留字符串内的单引号
        normalized = json_str.replace("'", '"')
        return json.loads(normalized)
    except json.JSONDecodeError:
        pass
    
    # ==========================================================================
    # 【基于14.0分析新增】第4级增强: 截断JSON字段提取 + key:value兜底
    # 来源：tool_parser.py (行136-177)
    # 处理JSON部分损坏的情况，尝试挽救性提取
    # ==========================================================================
    parsed_fallback = {}
    
    # 尝试提取 tool_name（多种字段名）
    for field_pattern in [r'"tool_name"', r'"action_tool"', r'"action"']:
        match = re.search(rf'{field_pattern}\s*:\s*"([^"]*)"', json_str)
        if match:
            parsed_fallback["tool_name"] = match.group(1)
            break
    
    # 尝试提取 tool_params（多种字段名）
    for field_pattern in [r'"tool_params"', r'"params"', r'"action_input"']:
        match = re.search(rf'{field_pattern}\s*:\s*(\{{[^}}]*\}})', json_str)
        if match:
            try:
                parsed_fallback["tool_params"] = json.loads(match.group(1))
                break
            except:
                parsed_fallback["tool_params"] = {}
                break
    
    # 如果成功提取到任何字段，返回挽救性结果
    if parsed_fallback:
        return parsed_fallback
    
    # 第5级: 正则提取key:value对（最坏情况兜底）
    fallback_kv = _extract_key_value_pairs(json_str)
    if fallback_kv:
        return fallback_kv
        
    # 如果所有级别都失败，返回 None 触发上层的 type="error"
    logger.error(f"[_parse_action_input] All 5 levels of JSON parsing failed for: {input_section[:100]}...")
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
    stack = []
    end_idx = None
    
    for i in range(start_idx, len(text)):
        char = text[i]
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
        return text[start_idx:], content_before
    
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
    "_extract_by_known_tools",  # 【P0新增】工具名兜底匹配
    "_extract_json_block",  # 【2026-04-18小沈新增】纯JSON块提取
    "_extract_json_with_balanced_braces",
    "_extract_key_value_pairs",
    "_create_action_result",  # 【2026-04-18小沈新增】创建统一格式结果
    "_extract_tool_params_from_thought",  # 【2026-04-18小沈新增】从thought提取参数
    "REACT_KEYWORDS",
]



