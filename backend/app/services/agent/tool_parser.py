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
    
    @staticmethod
    def handle_parse_error(llm_response: str, error: Exception, logger) -> Dict[str, Any]:
        """
        统一处理LLM响应解析错误
        
        保证所有解析失败的地方使用一致的错误处理逻辑：
        1. 记录详细日志（包含LLM原始返回内容）
        2. 返回统一的错误结果字典
        
        Args:
            llm_response: LLM原始返回内容
            error: 解析异常
            logger: 日志对象（必须传入有效的logger，不能为None）
        
        Returns:
            统一的错误结果字典，包含：
            - parsed_obs: 解析结果（用于后续处理）
            - save_to_history: 是否保存原始response到history
            - error_type: 错误类型
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
        
        # 分类错误类型
        if not llm_response or llm_response.strip() == "":
            error_type = "empty_response"
        elif "json" in error_msg.lower() or "decode" in error_msg.lower():
            error_type = "json_parse_error"
        else:
            error_type = "unknown"
        
        # 生成用户友好的错误消息
        error_messages = {
            "empty_response": "AI返回了空响应，可能是网络问题或模型限流",
            "json_parse_error": "AI返回了非标准JSON格式，无法解析",
            "unknown": "无法解析AI响应"
        }
        
        user_message = error_messages.get(error_type, "无法解析AI响应")
        
        # 返回统一格式的错误结果
        return {
            "parsed_obs": {
                "content": f"[解析失败] {user_message}。原始内容: {response_preview}",
                "action_tool": "finish",
                "params": {},
                "reasoning": None,
                "raw_response": llm_response  # 保留原始响应，供调用方使用
            },
            "save_to_history": True,  # 保存原始response到history
            "error_type": error_type,
            "error_message": user_message
        }