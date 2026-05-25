# -*- coding: utf-8 -*-
"""
工具解析器模块【已弃用】

⚠️ 【P6】本模块已弃用，请使用 new parse_react_response() 或 parsers/ 目录下的解析器

解析LLM响应中的Thought-Action-ActionInput结构
Author: 小沈 - 2026-03-21
Deprecated: 2026-04-19 - 使用 app.services.agent.react_output_parser.parse_react_response() 替代
"""

import json
import re
import warnings
from typing import Any, Dict, Optional
from functools import wraps


def deprecated(func):
    """弃用装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        warnings.warn(
            f"{func.__name__} 已弃用，请使用新的解析器",
            DeprecationWarning,
            stacklevel=2
        )
        return func(*args, **kwargs)
    return wrapper


@deprecated
class ToolParser:
    """
    工具解析器
    
    解析LLM响应中的Thought-Action-ActionInput结构
    支持JSON格式和Markdown代码块格式
    """
    
    @staticmethod
    def _extract_json_with_balanced_braces(text: str) -> tuple:
        """
        Stage 1: 使用平衡括号匹配找到JSON，提取JSON前面的纯文本
        
        返回：(json_text, content_before_json)
        - json_text: 找到的JSON文本（可能截断）
        - content_before_json: JSON前面的纯文本
        """
        start = -1
        brace_count = 0
        in_string = False
        escape_next = False
        
        for i, char in enumerate(text):
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            
            if in_string:
                continue
            
            if char == '{':
                if start == -1:
                    start = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start != -1:
                    # 找到完整的JSON
                    json_text = text[start:i+1]
                    content_before = text[:start].strip()
                    return json_text, content_before
        
        # 如果JSON被截断，返回不完整JSON
        if start != -1 and brace_count > 0:
            return text[start:], text[:start].strip()
        
        # 没有找到JSON
        return None, text.strip()
    
    @staticmethod
    def _consolidate_json_extraction(text: str) -> tuple:
        """统一 JSON 提取：平衡括号 + Markdown 代码块 + 内容前置文本。
        
        小沈 2026-05-25 重构拆分
        
        Returns:
            (json_str, content_before) — json_str 可为 None
        """
        content_before = ""
        json_text = None
        
        # S0: 平衡括号提取
        json_text, content_before = ToolParser._extract_json_with_balanced_braces(text)
        
        # S1: 无论 S0 是否成功，始终检查 Markdown 代码块并更新 content_before
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL | re.IGNORECASE)
        if json_match:
            content_before = text[:text.find('```')].strip()
            if not json_text:
                # S0 失败时，取代码块内文本再提取一次
                json_text, _ = ToolParser._extract_json_with_balanced_braces(json_match.group(1).strip())
        
        return json_text, content_before
    
    @staticmethod
    def _parse_json_robust(json_str: str) -> Optional[Dict[str, Any]]:
        """三级降级 JSON 解析：直接→修复→逐字段。
        
        小沈 2026-05-25 重构拆分
        """
        # P1+P2: 尝试直接解析 + 修复尾逗号
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            try:
                fixed = re.sub(r',(\s*[}\]])', r'\1', json_str)
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass
        
        # P3: 逐字段提取
        result = {}
        for field in ["tool_name", "action", "action_tool", "tool_params", "params", "action_input"]:
            ToolParser._try_extract_field(json_str, result, field)
        
        if result.get("tool_name") or result.get("action") or result.get("action_tool"):
            return result
        return None
    
    @staticmethod
    def _try_extract_field(json_str: str, target: dict, field: str) -> None:
        """尝试从截断 JSON 中提取单个字段。
        
        小沈 2026-05-25 重构拆分
        """
        if field in ("tool_params", "params"):
            m = re.search(rf'"{field}"\s*:\s*(\{{[^}}]*\}})', json_str)
            if m:
                try:
                    target[field] = json.loads(m.group(1))
                    return
                except json.JSONDecodeError:
                    target[field] = {}
                    return
        elif field == "action_input":
            # action_input 使用贪心匹配 .* 处理嵌套JSON（修复问题20.6-1🔴）
            m = re.search(rf'"{field}"\s*:\s*(\{{.*\}})', json_str)
            if m:
                try:
                    target[field] = json.loads(m.group(1))
                    return
                except json.JSONDecodeError:
                    target[field] = {}
                    return
        else:
            m = re.search(rf'"{field}"\s*:\s*"([^"]*)"', json_str)
            if m:
                target[field] = m.group(1)
    
    @staticmethod
    def _resolve_parse_result(parsed: Dict[str, Any], content_before: str) -> Dict[str, Any]:
        """统一字段名 fallback 链 + content/thought/reasoning 组装。
        
        小沈 2026-05-25 重构拆分
        """
        content = content_before if content_before else parsed.get("thought", "")
        thought = parsed.get("thought", parsed.get("thinking", ""))
        tool_name = parsed.get("tool_name", parsed.get("action_tool", parsed.get("action", "finish")))
        
        # 使用 in 键存在检查而非 falsy or 链（修复问题20.6-4🟡）
        if "tool_params" in parsed:
            tool_params = parsed.get("tool_params", {})
        elif "params" in parsed:
            tool_params = parsed.get("params", {})
        elif "action_input" in parsed:
            tool_params = parsed.get("action_input", {})
        elif "actionInput" in parsed:
            tool_params = parsed.get("actionInput", {})
        else:
            tool_params = {}
        
        reasoning = parsed.get("reasoning", parsed.get("thinking", parsed.get("analysis", "")))
        return {
            "content": content, "thought": thought,
            "tool_name": tool_name, "tool_params": tool_params,
            "reasoning": reasoning,
        }
    
    @staticmethod
    def parse_response(response: str) -> Dict[str, Any]:
        """
        解析LLM响应
        
        【小沈重构 2026-05-25】
        - 重构拆分：提取 _consolidate_json_extraction / _parse_json_robust / _resolve_parse_result
        - 保持所有分支完整，功能不减少
        
        Args:
            response: LLM的原始响应文本
        
        Returns:
            解析后的字典，包含thought, action, action_input
        """
        try:
            # S0+S1+S2: 统一 JSON 提取
            json_str, content_before = ToolParser._consolidate_json_extraction(response)
            
            if json_str:
                # P1+P2+P3: 三级降级解析
                parsed = ToolParser._parse_json_robust(json_str)
                if parsed:
                    return ToolParser._resolve_parse_result(parsed, content_before)
            
            # P3g: 文本降级提取
            parsed = ToolParser._extract_from_text(response)
            if parsed:
                return ToolParser._resolve_parse_result(parsed, content_before)
            
            # P3h: finish 兜底
            error_info = ToolParser.format_error("json_parse_error", "JSON解析失败")
            return {
                "content": content_before or f"⚠️ {error_info['title']}\n\n{error_info['description']}",
                "thought": "", "tool_name": "finish",
                "tool_params": {}, "reasoning": None,
            }
        except Exception:
            return {
                "content": "解析异常", "thought": "",
                "tool_name": "finish", "tool_params": {}, "reasoning": None,
            }
    
    @staticmethod
    def _extract_from_text(text: str) -> Optional[Dict[str, Any]]:
        """
        从非结构化文本中提取关键信息
        
        用于处理LLM没有返回标准JSON格式的情况
        """
        result = {}
        
        thought_patterns = [
            r'(?:thought|thinking|reasoning)["\']?\s*[:=]\s*["\']?(.*?)(?:["\']?\s*[,}\n]|action)',
            r'(?:I think|I need to|Let me|First,?|Next,?)\s*(.*?)(?:\n\n|\n[A-Z]|$)',
        ]
        
        for pattern in thought_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                result["thought"] = match.group(1).strip()
                break
        
        action_patterns = [
            r'(?:action)["\']?\s*[:=]\s*["\']?([\w]+)["\']?',
            r'(?:use|call|execute)\s+(?:the\s+)?([\w]+)\s+(?:tool|function)?',
            r'(?:tool|function)\s*[:=]\s*["\']?([\w]+)["\']?',
            r'(?:调用|使用|执行)\s+[\w]+',
            r'(?:工具\s*为|函数\s*为)([\w]+)',
            r'([\w]+)\s*(?:工具|函数|操作)',
            r'(?:先)?(?:列出|读取|搜索|创建|删除|移动)\s+([\w]+)',
            r'(?:我\s*(?:需要|要|会))?\s*调用\s+([\w]+)',
            r'(?:使用|调用)\s+([\w]+)',
        ]
        
        for pattern in action_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["action"] = match.group(1).strip().lower()
                break
        
        input_patterns = [
            r'(?:action_input|actionInput|input|parameters)["\']?\s*[:=]\s*({.*?})',
            r'(?:with|using)\s+parameters?\s*:?\s*({.*?})',
        ]
        
        for pattern in input_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                try:
                    result["action_input"] = json.loads(match.group(1))
                except json.JSONDecodeError:
                    result["action_input"] = {}
                break
        
        if "action_input" not in result:
            result["action_input"] = {}
        
        if "thought" in result and "action" in result:
            return result
        
        # 【修复 2026-04-13】改进的finish判断
        # 只匹配行首/句首的总结词，不匹配中间的内容
        summarize_patterns = [
            # 英文总结 - 必须行首/句首
            r'^(?:summarize|summary|I have found|I will)',
            # 中文总结 - 必须行首/句首
            r'^(?:总结|已完成|任务完成|结束了)',
        ]
        for pattern in summarize_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                result["thought"] = text.strip()
                result["action"] = "finish"
                result["action_input"] = {}
                return result
        
        return None
    
    # ===== 方案A：分级错误信息类 =====
    ERROR_TYPES = {
        "empty_response": {
            "title": "AI返回了空响应",
            "description": "可能是网络问题或模型暂时不可用",
            "suggestion": "请稍后再试，或尝试重新提问"
        },
        "json_parse_error": {
            "title": "AI响应格式异常",
            "description": "AI返回了非标准JSON格式的内容",
            "suggestion": "请尝试简化问题，或重新组织语言"
        },
        "api_limit": {
            "title": "API调用频繁",
            "description": "模型访问量过大，已被限流",
            "suggestion": "请稍后再试，或更换其他模型"
        },
        "data_too_large": {
            "title": "数据量过大",
            "description": "查询结果超出了AI的处理能力",
            "suggestion": "请缩小查询范围，或分多次查询"
        },
        "context_lost": {
            "title": "上下文丢失",
            "description": "对话历史过长，部分上下文已被裁剪",
            "suggestion": "请重新描述任务，或开始新对话"
        },
        "unknown": {
            "title": "未知错误",
            "description": "发生了未知错误",
            "suggestion": "请重新尝试"
        }
    }
    
    @classmethod
    def format_error(cls, error_type: str, details: str = "") -> dict:
        """方案A：格式化错误信息"""
        error_info = cls.ERROR_TYPES.get(error_type, cls.ERROR_TYPES["unknown"])
        
        return {
            "title": error_info["title"],
            "description": error_info["description"],
            "details": details,
            "suggestion": error_info["suggestion"]
        }
    
    # ===== 方案B：增强错误日志和用户反馈 =====
    @staticmethod
    def handle_parse_error(llm_response: str, error: Exception, logger, content_before: str = None) -> Dict[str, Any]:
        """
        统一处理LLM响应解析错误
        
        保证所有解析失败的地方使用一致的错误处理逻辑：
        1. 记录详细日志（包含LLM原始返回内容）
        2. 分类错误类型
        3. 返回结构化错误信息
        
        Args:
            llm_response: LLM原始返回内容
            error: 解析异常
            logger: 日志对象（必须传入有效的logger，不能为None）
            content_before: （可选）JSON前面的纯文本，已在parse_response中提取好
        
        Returns:
            统一的错误结果字典
        """
        # 记录详细错误日志
        error_msg = str(error)
        
        # 安全处理 llm_response
        if llm_response:
            response_preview = llm_response[:500]
            response_length = len(llm_response)
        else:
            response_preview = "(空响应)"
            response_length = 0
        
        logger.error(f"[ToolParser] 解析失败: {error_msg}")
        logger.error(f"[ToolParser] LLM原始返回 (前500字符): {response_preview}")
        logger.error(f"[ToolParser] LLM返回长度: {response_length} 字符")
        
        # 方案B：分析错误类型
        if not llm_response or llm_response.strip() == "":
            error_type = "empty_response"
        elif "json" in error_msg.lower() or "decode" in error_msg.lower():
            error_type = "json_parse_error"
        elif "429" in llm_response or "1305" in llm_response or "rate limit" in llm_response.lower() or "rate_limit" in llm_response.lower():
            error_type = "api_limit"
        elif response_length > 10000:
            error_type = "data_too_large"
        else:
            error_type = "unknown"
        
        # 方案A：生成分级错误信息
        error_info = ToolParser.format_error(error_type, error_msg)
        
        # 生成返回给用户的完整错误消息
        user_content = f"⚠️ {error_info['title']}\n\n{error_info['description']}\n\n建议：{error_info['suggestion']}"
        
        # 【专家方法】优先使用已提取的content_before，其次使用错误提示
        # 复用在parse_response中已经提取好的JSON前面的纯文本
        final_content = content_before if content_before else user_content
        
        # 返回统一格式的错误结果
        return {
            "parsed_obs": {
                "content": final_content,
                "tool_name": "finish",
                "tool_params": {},
                "reasoning": None,
                "raw_response": llm_response,
                "error_details": error_info
            },
            "save_to_history": True,
            "error_type": error_type,
            "error_message": f"{error_info['title']}: {error_info['description']}"
        }