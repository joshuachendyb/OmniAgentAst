# -*- coding: utf-8 -*-
"""
工具解析器模块

解析LLM响应中的Thought-Action-ActionInput结构
Author: 小沈 - 2026-03-21
"""

import json
import re
from typing import Any, Dict, Optional


class ToolParser:
    """
    工具解析器
    
    解析LLM响应中的Thought-Action-ActionInput结构
    支持JSON格式和Markdown代码块格式
    """
    
    @staticmethod
    def parse_response(response: str) -> Dict[str, Any]:
        """
        解析LLM响应
        
        Args:
            response: LLM的原始响应文本
        
        Returns:
            解析后的字典，包含thought, action, action_input
        
        Raises:
            ValueError: 如果解析失败
        """
        json_match = re.search(
            r'```(?:json)?\s*\n?(.*?)\n?```',
            response,
            re.DOTALL | re.IGNORECASE
        )
        
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            json_str = response.strip()
        
        try:
            parsed = json.loads(json_str)
        except json.JSONDecodeError as e:
            parsed = ToolParser._extract_from_text(response)
            if not parsed:
                raise ValueError(f"Failed to parse response as JSON: {e}")
        
        content = parsed.get("content", parsed.get("thought", ""))
        action_tool = parsed.get("action_tool", parsed.get("action", "finish"))
        
        if "params" in parsed:
            params = parsed.get("params", {})
        elif "action_input" in parsed:
            params = parsed.get("action_input", {})
        elif "actionInput" in parsed:
            params = parsed.get("actionInput", {})
        else:
            params = {}
        
        reasoning = parsed.get("reasoning")
        
        return {
            "content": content,
            "action_tool": action_tool,
            "params": params,
            "reasoning": reasoning
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
            r'(?:action)["\']?\s*[:=]\s*["\']?(\w+)["\']?',
            r'(?:use|call|execute)\s+(?:the\s+)?(\w+)\s+(?:tool|function)?',
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
        
        return None