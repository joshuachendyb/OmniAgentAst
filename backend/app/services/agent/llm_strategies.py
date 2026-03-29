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
    
    【分层处理架构 C + A + B】
    - 方案C: 复用 ToolParser.parse_response() 解析 JSON
    - 方案A: ToolParser._extract_from_text() 支持中文提取
    - 方案B: 工具名保底匹配
    """
    
    KNOWN_TOOLS = [
        "list_directory", "read_file", "write_file", "delete_file",
        "move_file", "search_files", "search_file_content", "generate_report"
    ]
    
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
            响应文本（JSON 格式）
        """
        history_messages = dict_list_to_messages(history_dicts)
        
        response = await llm_client(
            message=message,
            history=history_messages
        )
        
        error_info = None
        if hasattr(response, 'error') and response.error:
            error_info = response.error
            logger.warning(f"[LLM Response] LLM returned error: {error_info}")
        
        if hasattr(response, 'content'):
            content = response.content
        elif isinstance(response, dict):
            content = response.get("content", str(response))
        else:
            content = str(response)
        
        logger.info(f"[LLM Response Raw (text)] content={repr(content)[:500]}")
        
        # ===== 情况0: 空内容 =====
        if not content:
            logger.warning("[LLM Response] Warning: LLM returned empty content!")
            # 如果有错误信息，生成更详细的错误提示
            if error_info:
                error_hint = self._format_error_hint(error_info)
                logger.warning(f"[LLM Response] Error hint: {error_hint}")
                return self._make_result(
                    content=f"[错误] {error_hint}",
                    action_tool="finish",
                    params={"result": f"[错误] {error_hint}"}
                )
            return self._make_result(content="", action_tool="finish", params={})
        
        # ===== 方案C: 尝试 ToolParser.parse_response() =====
        from app.services.agent.tool_parser import ToolParser
        try:
            parsed = ToolParser.parse_response(content)
            action = parsed.get("action_tool", "finish")
            thought = parsed.get("content", "")
            params = parsed.get("params", {})
            reasoning = parsed.get("reasoning")
            logger.info(f"[TextStrategy] ToolParser success: action={action}")
            return self._make_result(content=thought, action_tool=action, params=params, reasoning=reasoning)
        except ValueError:
            pass  # ToolParser 无法解析，继续方案A/B
        
        # ===== 方案B: 工具名保底匹配 =====
        tool_result = self._extract_by_known_tools(content)
        if tool_result:
            logger.info(f"[TextStrategy] Tool match found: {tool_result['action_tool']}")
            return self._make_result(
                content=tool_result.get("content", content),
                action_tool=tool_result["action_tool"],
                params=tool_result.get("params", {})
            )
        
        # ===== 无法提取工具调用，返回 finish =====
        logger.info(f"[TextStrategy] No action extracted, returning finish with full content")
        return self._make_result(content=content, action_tool="finish", params={})
    
    def _make_result(self, content: str, action_tool: str, params: dict, reasoning: Any = None) -> str:
        """构建返回结果"""
        return json.dumps({
            "content": content,
            "action_tool": action_tool,
            "params": params,
            "reasoning": reasoning
        }, ensure_ascii=False)
    
    def _format_error_hint(self, error: str) -> str:
        """
        格式化错误提示信息，让用户更清楚地了解错误原因
        
        Args:
            error: 原始错误信息
        
        Returns:
            格式化后的错误提示
        """
        error_str = str(error).lower()
        
        # 限流错误
        if "429" in error_str or "1305" in error_str or "访问量过大" in error_str or "rate limit" in error_str:
            return "模型访问量过大（429限流），请稍后再试或更换模型"
        
        # 超时错误
        if "timeout" in error_str or "超时" in error_str:
            return "请求超时，请检查网络后重试"
        
        # 连接错误
        if "connect" in error_str or "连接" in error_str:
            return "网络连接失败，请检查网络后重试"
        
        # 认证错误
        if "401" in error_str or "403" in error_str or "认证" in error_str or "auth" in error_str:
            return "API认证失败，请检查API密钥是否有效"
        
        # 余额不足
        if "余额" in error_str or "quota" in error_str or "credit" in error_str:
            return "API额度或余额不足，请充值后重试"
        
        # 默认错误
        return f"服务暂时不可用（{error}），请稍后重试"
    
    def _extract_by_known_tools(self, content: str) -> Optional[dict]:
        """
        【方案B】通过已知工具名匹配提取 action
        
        当 ToolParser 无法解析时，尝试在 content 中查找已知工具名
        """
        import re
        
        content_lower = content.lower()
        
        for tool in self.KNOWN_TOOLS:
            # 查找工具名出现位置
            pattern = rf'\b{re.escape(tool)}\b'
            if re.search(pattern, content_lower, re.IGNORECASE):
                logger.info(f"[TextStrategy] Found known tool: {tool}")
                
                # 尝试提取参数（简化版：查找引号内的内容）
                params = {}
                
                # 查找路径参数
                path_patterns = [
                    r'["\']?([A-Za-z]:\\[^"\'\s]+)["\']?',  # Windows 路径 C:\path
                    r'["\']?(/[^\s"\'<>]+)["\']?',  # Unix 路径 /path
                    r'["\']?([^"\'\s]+)["\']?',  # 一般字符串
                ]
                
                for p in path_patterns:
                    matches = re.findall(p, content)
                    if matches:
                        params["path"] = matches[0]
                        break
                
                return {
                    "action_tool": tool,
                    "content": content,
                    "params": params
                }
        
        return None


class ToolsStrategy(LLMStrategy):
    """
    Function Calling 模式
    
    通过 tools Schema 约束 LLM 输出结构化函数调用
    适用于需要精确工具调用的场景
    """
    
    MAX_RETRIES = 3  # 最大重试次数
    RETRY_DELAY = 2  # 重试等待时间（秒）
    
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
        import asyncio
        
        history_messages = dict_list_to_messages(history_dicts)
        
        # 检查 llm_client 是否有 chat_with_tools 方法
        if not hasattr(llm_client, 'chat_with_tools'):
            logger.warning("[Function Calling] llm_client has no chat_with_tools method, falling back to text mode")
            text_strategy = TextStrategy()
            return await text_strategy.call(
                llm_client=llm_client,
                message=message,
                history_dicts=history_dicts,
                conversation_history=conversation_history,
                **kwargs
            )
        
        # 重试机制
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                response = await llm_client.chat_with_tools(
                    message=message,
                    history=history_messages,
                    tools=self.tools
                )
                
                # 检查是否有错误
                if hasattr(response, 'error') and response.error:
                    error_msg = response.error
                    last_error = error_msg
                    
                    # 检查是否是限流错误
                    if "429" in str(error_msg) or "1305" in str(error_msg):
                        if attempt < self.MAX_RETRIES - 1:
                            logger.warning(f"[Function Calling] Rate limit detected (attempt {attempt + 1}/{self.MAX_RETRIES}), retrying in {self.RETRY_DELAY}s...")
                            await asyncio.sleep(self.RETRY_DELAY)
                            continue
                        else:
                            logger.error(f"[Function Calling] Rate limit persists after {self.MAX_RETRIES} attempts, falling back to text mode")
                            break
                    else:
                        logger.error(f"[Function Calling] API Error: {error_msg}")
                        break
                
                # 解析 tool_calls
                if hasattr(response, 'content') and response.content:
                    try:
                        tool_calls = json.loads(response.content)
                        
                        if isinstance(tool_calls, list) and len(tool_calls) > 0:
                            content = self._format_tool_calls(tool_calls)
                            logger.info(f"[Function Calling] Received tool_calls: {len(tool_calls)} calls")
                            return content
                        else:
                            content = response.content
                            logger.info(f"[Function Calling] LLM returned text (no tool call): {repr(content)[:200]}")
                            return content
                            
                    except (json.JSONDecodeError, TypeError) as e:
                        content = response.content
                        logger.info(f"[Function Calling] Non-JSON response: {repr(content)[:200]}")
                        return content
                else:
                    # 空响应，重试
                    last_error = "Empty response"
                    if attempt < self.MAX_RETRIES - 1:
                        logger.warning(f"[Function Calling] Empty response (attempt {attempt + 1}/{self.MAX_RETRIES}), retrying in {self.RETRY_DELAY}s...")
                        await asyncio.sleep(self.RETRY_DELAY)
                        continue
                    else:
                        logger.error(f"[Function Calling] Empty response persists after {self.MAX_RETRIES} attempts, falling back to text mode")
                        break
                        
            except Exception as e:
                last_error = str(e)
                logger.error(f"[Function Calling] Exception (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}")
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(self.RETRY_DELAY)
                    continue
                else:
                    break
        
        # 降级到 TextStrategy
        logger.warning(f"[Function Calling] Falling back to TextStrategy (last error: {last_error})")
        text_strategy = TextStrategy()
        return await text_strategy.call(
            llm_client=llm_client,
            message=message,
            history_dicts=history_dicts,
            conversation_history=conversation_history,
            **kwargs
        )
    
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
