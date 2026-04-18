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

# 【基于14.0分析新增】已知工具名列表（从配置或注册中心动态获取）
# 来源：llm_strategies.py KNOWN_TOOLS (行62-67)
KNOWN_TOOLS = [
    "list_directory", "read_file", "write_file", "delete_file",
    "move_file", "search_files", "search_file_content", "generate_report",
    # 更多工具名从配置动态加载...
]


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
        data = json.loads(output)
        if isinstance(data, dict):
            # 新字段格式
            if "tool_name" in data:
                logger.info(f"[parse_react_response] JSON预解析命中, type=action/answer")
                return {
                    "type": "action" if data.get("tool_name") != "finish" else "answer",
                    "thought": data.get("content", data.get("thought", "")),
                    "content": data.get("content", data.get("thought", "")),
                    "reasoning": data.get("reasoning", ""),
                    "tool_name": data["tool_name"],
                    "tool_params": data.get("tool_params", {}),
                    "response": data.get("response", "")
                }
            # 旧字段格式（action/action_input → tool_name/tool_params）
            if "action" in data:
                logger.info(f"[parse_react_response] JSON预解析命中(旧格式), type=action/answer")
                return {
                    "type": "action" if data.get("action") != "finish" else "answer",
                    "thought": data.get("thought", ""),
                    "content": data.get("thought", ""),
                    "reasoning": data.get("reasoning", ""),
                    "tool_name": data["action"],
                    "tool_params": data.get("action_input", {}),
                    "response": ""
                }
    except (json.JSONDecodeError, TypeError):
        pass  # 不是JSON格式，继续走关键词匹配流程
    
    # 步骤1.2：四种情况判断逻辑
    logger.info(f"[parse_react_response] 走关键词匹配流程")
    return _determine_parse_type(output)


# =============================================================================
# 步骤1.2：实现四种情况判断逻辑
# =============================================================================

def _determine_parse_type(output: str) -> Dict[str, Any]:
    """
    判断LLM输出类型并调用对应解析函数
    
    优先级：Action > Answer > Thought_only > Implicit
    
    Args:
        output: LLM原始响应文本
        
    Returns:
        统一格式解析结果
        
    设计依据: LlamaIndex核心判断逻辑 - 关键词位置定位 + Action优先规则
    
    【基于14.0分析新增】P0-必须：工具名兜底匹配作为Pre-check
    """
    # ==========================================================================
    # 【P0-必须新增】Pre-check: 工具名兜底匹配（在关键词定位之前执行）
    # 来源：llm_strategies.py _extract_by_known_tools() (行229-267)
    # 重要性：无此功能时，格式略不规范的LLM输出将导致工具调用完全失败
    # ==========================================================================
    # ==========================================================================
    # 【16章融合方案新增】Markdown JSON 检测（优先级最高，必须在最前面）
    # 来源：设计文档第16章
    # 当LLM返回Markdown包裹的JSON时，调用tool_parser完整解析
    # 注意：这个检测必须在 _extract_by_known_tools 之前执行
    # ==========================================================================
    if '```' in output:
        from app.services.agent.tool_parser import ToolParser
        try:
            result = ToolParser.parse_response(output)
            
            # 转换为 react_output_parser 的统一格式
            if result["tool_name"] == "finish":
                return {
                    "type": "answer",
                    "thought": result["thought"],
                    "content": result["content"],
                    "reasoning": result.get("reasoning", ""),
                    "tool_name": None,
                    "tool_params": None,
                    "response": result["content"],
                    "error": None
                }
            else:
                return {
                    "type": "action",
                    "thought": result["thought"],
                    "content": result["content"],
                    "reasoning": result.get("reasoning", ""),
                    "tool_name": result["tool_name"],
                    "tool_params": result["tool_params"],
                    "response": None,
                    "error": None
                }
        except Exception as e:
            # 解析失败，回退到原有逻辑
            from app.utils.logger import logger
            logger.warning(f"[_determine_parse_type] ToolParser failed: {e}, fallback to keyword matching")
    
    # ==========================================================================
    # 【2026-04-18 小沈新增】纯JSON块检测
    # 解决LLM返回无```包裹的JSON块时，_extract_by_known_tools兜底函数错误提取参数的问题
    # 当LLM返回格式如：Thought内容...\n{...JSON...} 时，提取JSON块中的tool_name和tool_params
    # ==========================================================================
    json_data = _extract_json_block(output)
    if json_data and "tool_name" in json_data:
        tool_name = json_data["tool_name"]
        tool_params = json_data.get("tool_params", {})
        from app.utils.logger import logger
        logger.info(f"[_determine_parse_type] 纯JSON块提取成功: tool={tool_name}, params={tool_params}")
        return {
            "type": "action",
            "thought": json_data.get("thought", json_data.get("reasoning", output[:200])),
            "content": json_data.get("thought", json_data.get("reasoning", output[:200])),
            "reasoning": json_data.get("reasoning", ""),
            "tool_name": tool_name,
            "tool_params": tool_params,
            "response": None,
            "error": None
        }
    
    # ==========================================================================
    # 【P0-必须新增】Pre-check: 工具名兜底匹配
    # 来源：llm_strategies.py _extract_by_known_tools()
    # 重要性：无此功能时，格式略不规范的LLM输出将导致工具调用完全失败
    # ==========================================================================
    tool_result = _extract_by_known_tools(output)
    if tool_result:
        return {
            "type": "action",
            "thought": tool_result["content"],
            "content": tool_result["content"],      # 兼容性字段
            "reasoning": tool_result["content"],    # 兼容性字段
            "tool_name": tool_result["tool_name"],
            "tool_params": tool_result["tool_params"],
            "response": None,
            "error": None
        }
    
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
    
    # 情况A: 无关键词匹配 - 隐式回答
    # 【深度分析】如果文本很长且没有关键词，可能是隐式回答；如果很短或乱码，可能是解析失败
    if len(output.strip()) < 5:
        thought = "Response too short to be meaningful"
        return {
            "type": "parse_error",
            "error": "LLM response is too short or malformed",
            "thought": thought,
            "content": thought,
            "reasoning": thought,
            "tool_name": None,
            "tool_params": None,
            "response": output.strip()
        }

    thought = "(Implicit) I can answer without any more tools!"
    return {
        "type": "implicit",
        "thought": thought,
        "content": thought,             # 兼容性字段
        "reasoning": thought,           # 兼容性字段
        "tool_name": None,
        "tool_params": None,
        "response": output.strip(),
        "error": None
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
    从文本中提取JSON对象（支持嵌套结构）
    
    当LLM返回类似：Thought内容...\n{...JSON...} 格式时，
    使用平衡括号匹配提取完整的JSON对象。
    
    Args:
        content: LLM原始响应文本
        
    Returns:
        解析后的JSON字典，如果提取失败返回None
    """
    start = content.find('{')
    if start == -1:
        return None
    
    # 平衡括号匹配
    depth = 0
    for i in range(start, len(content)):
        if content[i] == '{':
            depth += 1
        elif content[i] == '}':
            depth -= 1
            if depth == 0:
                json_str = content[start:i+1]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    return None
    return None


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
    
    Args:
        content: LLM响应文本
        
    Returns:
        工具信息字典（成功）或None（失败）
        {
            "tool_name": str,       # 匹配到的工具名
            "content": str,         # 原始文本作为thought
            "tool_params": dict     # 提取的参数（简化版）
        }
    """
    content_lower = content.lower()
    
    for tool in KNOWN_TOOLS:
        # 查找工具名出现位置（单词边界匹配）
        pattern = rf'\b{re.escape(tool)}\b'
        if re.search(pattern, content_lower, re.IGNORECASE):
            # 尝试提取参数（简化版：查找引号内的内容）
            params = {}
            
            # 查找路径参数（Windows/Unix路径）
            path_patterns = [
                r'["\']?([A-Za-z]:\\[^"\'\s]+)["\']?',  # Windows路径 C:\path
                r'["\']?(/[^\s"\'<>]+)["\']?',          # Unix路径 /path
            ]
            
            for p in path_patterns:
                matches = re.findall(p, content)
                if matches:
                    params["path"] = matches[0]
                    break
            
            return {
                "tool_name": tool,
                "content": content,
                "tool_params": params
            }
    
    return None


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

    return {
        "type": "action",
        "thought": thought,
        "content": thought,             # 兼容性字段
        "reasoning": thought,           # 兼容性字段
        "tool_name": tool_name,
        "tool_params": tool_params or {},
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
    "REACT_KEYWORDS",
    "KNOWN_TOOLS",  # 【新增】已知工具名列表
    "ToolParser",   # 【兼容层】旧接口兼容包装器
]


# =============================================================================
# 【必选】ToolParser兼容层（阶段一必须集成）
# 来源：第14章 14.6.1.5节
# 重要性：llm_strategies.py等代码仍在调用ToolParser.parse_response()
# =============================================================================

class ToolParser:
    """兼容旧接口的包装器（必须集成，阶段一必须加入）"""
    
    @staticmethod
    def parse_response(response: str) -> Dict[str, Any]:
        """兼容旧接口"""
        parsed = parse_react_response(response)
        
        # 转换为旧格式
        if parsed["type"] == "action":
            return {
                "content": parsed.get("thought", ""),
                "thought": parsed.get("thought", ""),
                "tool_name": parsed["tool_name"],
                "tool_params": parsed["tool_params"] or {},
                "reasoning": ""
            }
        elif parsed["type"] in ["answer", "implicit"]:
            return {
                "content": parsed.get("response", ""),
                "thought": parsed.get("thought", ""),
                "tool_name": "finish",
                "tool_params": {},
                "reasoning": ""
            }
        elif parsed["type"] == "parse_error":
            # 【修复D8】解析失败：返回错误信息，不当作finish处理
            return {
                "content": parsed.get("error", "Parse error"),
                "thought": parsed.get("thought", ""),
                "tool_name": "parse_error",  # 明确标识解析错误
                "tool_params": {},
                "reasoning": parsed.get("error", "")
            }
        else:  # thought_only
            return {
                "content": parsed.get("thought", ""),
                "thought": parsed.get("thought", ""),
                "tool_name": "finish",
                "tool_params": {},
                "reasoning": ""
            }
