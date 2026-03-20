# -*- coding: utf-8 -*-
"""
LLM 调用策略模块

实现策略模式，支持三种 LLM 调用方式：
1. TextStrategy：文本模式，直接返回响应文本
2. ToolsStrategy：Function Calling 模式，通过 tools Schema 约束
3. ResponseFormatStrategy：JSON Schema 模式，通过 response_format 约束

Author: 小沈 - 2026-03-21
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional


class LLMStrategy(ABC):
    """LLM 调用策略基类"""
    
    @abstractmethod
    async def call(
        self,
        llm_client: Callable,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """
        调用 LLM
        
        Args:
            llm_client: LLM 客户端函数
            messages: 消息历史
            **kwargs: 其他参数
        
        Returns:
            LLM 响应
        """
        pass


class TextStrategy(LLMStrategy):
    """
    文本模式
    
    直接返回响应文本，不使用任何约束
    适用于简单对话或流式输出
    """
    
    async def call(
        self,
        llm_client: Callable,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """
        调用 LLM（文本模式）
        
        Args:
            llm_client: LLM 客户端函数
            messages: 消息历史
        
        Returns:
            {"content": 响应文本, "usage": token使用量}
        """
        response = await llm_client(messages=messages, **kwargs)
        
        return {
            "content": response.get("content", ""),
            "usage": response.get("usage", {}),
            "finish_reason": response.get("finish_reason", "stop")
        }


class ToolsStrategy(LLMStrategy):
    """
    Function Calling 模式
    
    通过 tools Schema 约束 LLM 输出结构化函数调用
    适用于需要精确工具调用的场景
    """
    
    def __init__(self, tools: Optional[List[Dict[str, Any]]] = None):
        """
        初始化 Function Calling 策略
        
        Args:
            tools: 工具定义列表，格式参考 OpenAI tools 规范
        """
        self.tools = tools or []
    
    async def call(
        self,
        llm_client: Callable,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """
        调用 LLM（Function Calling 模式）
        
        Args:
            llm_client: LLM 客户端函数
            messages: 消息历史
        
        Returns:
            {
                "content": None,
                "tool_calls": [{
                    "id": 函数调用ID,
                    "type": "function",
                    "function": {
                        "name": 函数名,
                        "arguments": 参数JSON字符串
                    }
                }],
                "usage": token使用量
            }
        """
        response = await llm_client(
            messages=messages,
            tools=self.tools,
            **kwargs
        )
        
        return {
            "content": response.get("content"),
            "tool_calls": response.get("tool_calls", []),
            "usage": response.get("usage", {}),
            "finish_reason": response.get("finish_reason", "tool_calls")
        }
    
    def get_tool_by_id(self, tool_call_id: str, tool_calls: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        根据 tool_call_id 获取工具调用信息
        
        Args:
            tool_call_id: 工具调用ID
            tool_calls: 工具调用列表
        
        Returns:
            工具调用信息，未找到返回 None
        """
        for call in tool_calls:
            if call.get("id") == tool_call_id:
                return call.get("function")
        return None


class ResponseFormatStrategy(LLMStrategy):
    """
    JSON Schema 模式
    
    通过 response_format 约束 LLM 输出 JSON 结构
    适用于需要结构化输出的场景（比 Function Calling 更灵活）
    """
    
    def __init__(self, response_format: Optional[Dict[str, Any]] = None):
        """
        初始化 JSON Schema 策略
        
        Args:
            response_format: JSON Schema 定义，格式参考 OpenAI response_format
        """
        self.response_format = response_format
    
    async def call(
        self,
        llm_client: Callable,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """
        调用 LLM（JSON Schema 模式）
        
        Args:
            llm_client: LLM 客户端函数
            messages: 消息历史
        
        Returns:
            {
                "content": JSON字符串,
                "structured": 解析后的结构对象,
                "usage": token使用量
            }
        """
        response = await llm_client(
            messages=messages,
            response_format=self.response_format,
            **kwargs
        )
        
        content = response.get("content", "{}")
        
        try:
            import json
            structured = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            structured = {"raw": content}
        
        return {
            "content": content,
            "structured": structured,
            "usage": response.get("usage", {}),
            "finish_reason": response.get("finish_reason", "stop")
        }
