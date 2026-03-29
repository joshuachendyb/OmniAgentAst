# -*- coding: utf-8 -*-
"""
LLM 调用策略模块

实现策略模式，支持三种 LLM 调用方式：
1. TextStrategy：文本模式，直接返回响应文本
2. ToolsStrategy：Function Calling 模式，通过 tools Schema 约束
3. ResponseFormatStrategy：JSON Schema 模式，通过 response_format 约束

Author: 小沈 - 2026-03-21
"""

import json
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

from app.services.agent.adapter import dict_list_to_messages
from app.utils.logger import logger


class LLMStrategy(ABC):
    """LLM 调用策略基类"""
    
    @abstractmethod
    async def call(
        self,
        llm_client: Callable,
        message: str,
        history_dicts: List[Dict[str, str]],
        conversation_history: List[Dict[str, str]],
        **kwargs
    ) -> str:
        """
        调用 LLM
        
        Args:
            llm_client: LLM 客户端函数
            message: 当前消息
            history_dicts: 历史消息（字典格式）
            conversation_history: 对话历史（用于追加）
            **kwargs: 其他参数
        
        Returns:
            LLM 响应内容（字符串）
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
        message: str,
        history_dicts: List[Dict[str, str]],
        conversation_history: List[Dict[str, str]],
        **kwargs
    ) -> str:
        """
        调用 LLM（文本模式）
        
        Args:
            llm_client: LLM 客户端函数
            message: 当前消息
            history_dicts: 历史消息（字典格式）
            conversation_history: 对话历史（用于追加）
        
        Returns:
            响应文本
        """
        history_messages = dict_list_to_messages(history_dicts)
        
        response = await llm_client(
            message=message,
            history=history_messages
        )
        
        if hasattr(response, 'content'):
            content = response.content
        elif isinstance(response, dict):
            content = response.get("content", str(response))
        else:
            content = str(response)
        
        logger.info(f"[LLM Response Raw (text)] content={repr(content)[:500]}")
        
        # 情况1：LLM 返回空内容
        if not content:
            logger.warning("[LLM Response] Warning: LLM returned empty content!")
            return json.dumps({
                "content": "",
                "action_tool": "finish",
                "params": {},
                "reasoning": None
            }, ensure_ascii=False)
        
        # 情况2：尝试解析 JSON 格式（可能是 LLM 按 Prompt 输出了 JSON）
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                # 检查是否有 action_tool 或 action 字段
                action = parsed.get("action_tool") or parsed.get("action")
                if action:
                    # 统一格式，转换为 action_tool
                    thought = parsed.get("content") or parsed.get("thought") or content
                    params = parsed.get("params") or parsed.get("action_input") or parsed.get("actionInput") or {}
                    reasoning = parsed.get("reasoning")
                    logger.info(f"[TextStrategy] LLM returned valid JSON with action: {action}")
                    return json.dumps({
                        "content": thought,
                        "action_tool": action,
                        "params": params,
                        "reasoning": reasoning
                    }, ensure_ascii=False)
                else:
                    # JSON 但没有 action 字段，视为 finish
                    logger.info(f"[TextStrategy] LLM returned JSON but no action, treating as finish")
                    return json.dumps({
                        "content": parsed.get("content") or parsed.get("thought") or content,
                        "action_tool": "finish",
                        "params": {},
                        "reasoning": None
                    }, ensure_ascii=False)
            elif isinstance(parsed, list) and len(parsed) > 0:
                # 数组格式，提取第一个元素的 action
                first = parsed[0]
                if isinstance(first, dict):
                    action = first.get("action_tool") or first.get("action")
                    if action:
                        logger.info(f"[TextStrategy] LLM returned JSON array, using first element action: {action}")
                        return json.dumps({
                            "content": first.get("content") or first.get("thought") or content,
                            "action_tool": action,
                            "params": first.get("params") or first.get("action_input") or {},
                            "reasoning": first.get("reasoning")
                        }, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            pass
        
        # 情况3：非 JSON 格式，尝试从纯文本中提取工具调用
        from app.services.agent.tool_parser import ToolParser
        extracted = ToolParser._extract_from_text(content)
        if extracted and extracted.get("action"):
            action = extracted.get("action", "finish")
            thought = extracted.get("thought") or content
            params = extracted.get("action_input") or {}
            logger.info(f"[TextStrategy] Extracted from text: action={action}, thought={str(thought)[:50]}...")
            return json.dumps({
                "content": thought,
                "action_tool": action,
                "params": params,
                "reasoning": None
            }, ensure_ascii=False)
        
        # 情况4：无法提取工具调用，返回带有完整 content 的 finish
        logger.info(f"[TextStrategy] No action extracted, returning finish with full content")
        return json.dumps({
            "content": content,
            "action_tool": "finish",
            "params": {},
            "reasoning": None
        }, ensure_ascii=False)


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
        message: str,
        history_dicts: List[Dict[str, str]],
        conversation_history: List[Dict[str, str]],
        **kwargs
    ) -> str:
        """
        调用 LLM（Function Calling 模式）
        
        Args:
            llm_client: LLM 客户端函数
            message: 当前消息
            history_dicts: 历史消息
            conversation_history: 对话历史
        
        Returns:
            格式化的响应文本
        """
        history_messages = dict_list_to_messages(history_dicts)
        
        # 检查 llm_client 是否有 chat_with_tools 方法
        if hasattr(llm_client, 'chat_with_tools'):
            response = await llm_client.chat_with_tools(
                message=message,
                history=history_messages,
                tools=self.tools
            )
        else:
            # 如果没有 chat_with_tools 方法，回退到文本模式
            logger.warning("[Function Calling] llm_client has no chat_with_tools method, falling back to text mode")
            text_strategy = TextStrategy()
            return await text_strategy.call(
                llm_client=llm_client,
                message=message,
                history_dicts=history_dicts,
                conversation_history=conversation_history,
                **kwargs
            )
        
        # 解析 tool_calls
        if hasattr(response, 'content') and response.content:
            try:
                tool_calls = json.loads(response.content)
                
                if isinstance(tool_calls, list) and len(tool_calls) > 0:
                    content = self._format_tool_calls(tool_calls)
                    logger.info(f"[Function Calling] Received tool_calls: {len(tool_calls)} calls")
                else:
                    content = response.content
                    logger.info(f"[Function Calling] LLM returned text (no tool call): {repr(content)[:200]}")
                    
            except (json.JSONDecodeError, TypeError) as e:
                content = response.content
                logger.info(f"[Function Calling] Non-JSON response: {repr(content)[:200]}")
        else:
            content = ""
            logger.warning("[Function Calling] Empty response from LLM")
        
        # 注意：不在这里添加assistant消息，由base_react.py统一添加（步骤11修复）
        return content
    
    def _format_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> str:
        """
        将 tool_calls 格式化为 Agent 可以理解的 JSON 格式
        
        Args:
            tool_calls: OpenAI 格式的 tool_calls 列表
        
        Returns:
            格式化的 JSON 字符串
        """
        if len(tool_calls) == 1:
            # 单个工具调用
            call = tool_calls[0]
            func = call.get("function", {})
            func_name = func.get("name", "")
            func_args = func.get("arguments", "{}")
            
            try:
                args = json.loads(func_args) if isinstance(func_args, str) else func_args
            except (json.JSONDecodeError, TypeError):
                args = {}
            
            formatted = {
                "thought": f"Calling tool: {func_name}",
                "action_tool": func_name,
                "params": args
            }
        else:
            # 多个工具调用（合并为一个）
            calls_info = []
            for call in tool_calls:
                func = call.get("function", {})
                func_name = func.get("name", "")
                func_args = func.get("arguments", "{}")
                
                try:
                    args = json.loads(func_args) if isinstance(func_args, str) else func_args
                except (json.JSONDecodeError, TypeError):
                    args = {}
                
                calls_info.append({"name": func_name, "args": args})
            
            # 取第一个工具调用作为主要操作
            first_call = calls_info[0]
            formatted = {
                "thought": f"Calling {len(tool_calls)} tools: {[c['name'] for c in calls_info]}",
                "action_tool": first_call["name"],
                "params": first_call["args"]
            }
        
        return json.dumps(formatted, ensure_ascii=False)


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
        self.response_format = response_format or {
            "type": "json_object",
            "json_schema": {
                "type": "object",
                "properties": {
                    "thought": {"type": "string", "description": "思考过程"},
                    "action": {"type": "string", "description": "工具名称"},
                    "action_input": {
                        "type": "object",
                        "description": "工具参数"
                    }
                },
                "required": ["thought", "action", "action_input"]
            }
        }
    
    async def call(
        self,
        llm_client: Callable,
        message: str,
        history_dicts: List[Dict[str, str]],
        conversation_history: List[Dict[str, str]],
        **kwargs
    ) -> str:
        """
        调用 LLM（JSON Schema 模式）
        
        Args:
            llm_client: LLM 客户端函数
            message: 当前消息
            history_dicts: 历史消息
            conversation_history: 对话历史
        
        Returns:
            格式化的 JSON 字符串
        """
        try:
            history_messages = dict_list_to_messages(history_dicts)
            
            # 调用 LLM（使用 chat_with_response_format 方法）
            response = await llm_client.chat_with_response_format(
                message=message,
                history=history_messages,
                response_format=self.response_format
            )
            
            # 处理响应
            if hasattr(response, 'error') and response.error:
                logger.error(f"[Agent] response_format error: {response.error}")
                raise Exception(response.error)
            
            if hasattr(response, 'content'):
                content = response.content
            elif isinstance(response, dict):
                content = response.get("content", str(response))
            else:
                content = str(response)
            
            logger.info(f"[Agent] response_format raw content: {repr(content)[:500]}")
            
            # 解析 JSON 响应
            try:
                result = json.loads(content)
                
                thought = result.get("thought", "")
                action = result.get("action", "")
                action_input = result.get("action_input", {})
                
                # 转换为 Agent 的 ToolParser 可以理解的格式
                formatted = {
                    "thought": thought,
                    "action_tool": action,
                    "params": action_input
                }
                
                content = json.dumps(formatted, ensure_ascii=False)
                logger.info(f"[Agent] response_format parsed: action={action}")
                
            except json.JSONDecodeError as e:
                logger.error(f"[Agent] Failed to parse response_format JSON: {e}, content={repr(content)[:200]}")
                raise Exception(f"Invalid JSON from LLM: {content}")
            
            
        except Exception as e:
            logger.error(f"[Agent] _get_llm_response_with_response_format failed: {e}")
            raise
