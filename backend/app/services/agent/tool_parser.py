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
        tool_name = parsed.get("tool_name", parsed.get("action_tool", parsed.get("action", "finish")))
        
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
        
        reasoning = parsed.get("reasoning")
        
        return {
            "content": content,
            "tool_name": tool_name,
            "tool_params": tool_params,
            "reasoning": reasoning,
            # 保持向后兼容
            "action_tool": tool_name,
            "params": tool_params
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
        
        # 【修复 2026-03-29】处理 LLM 返回纯文本（如 "I will now summarize..."）的情况
        # 当无法提取出结构化 action 时，检查是否是总结性文本，如果是则返回 finish
        summarize_patterns = [
            # 英文总结
            r'(?:summarize|summary|I have found|I will)',
            # 中文总结
            r'(?:总结|已完成|任务完成|结束了)',
            r'(?:根据.*?结果|基于.*?内容|以上)',
            # 磁盘目录描述
            r'(?:D盘|E盘|C盘).*?(?:如下|目录|文件|内容|列表)',
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
    def handle_parse_error(llm_response: str, error: Exception, logger) -> Dict[str, Any]:
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
        elif "429" in llm_response or "1305" in llm_response or "rate limit" in llm_response.lower():
            error_type = "api_limit"
        elif response_length > 10000:
            error_type = "data_too_large"
        else:
            error_type = "unknown"
        
        # 方案A：生成分级错误信息
        error_info = ToolParser.format_error(error_type, error_msg)
        
        # 生成返回给用户的完整错误消息
        user_content = f"⚠️ {error_info['title']}\n\n{error_info['description']}\n\n建议：{error_info['suggestion']}"
        
        # 返回统一格式的错误结果
        return {
            "parsed_obs": {
                "content": user_content,
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