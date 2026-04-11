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
from datetime import datetime

from app.services.agent.adapter import dict_list_to_messages
from app.utils.logger import logger
from app.chat_stream.error_handler import resolve_http_error_type, get_stream_error_info


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
        
        logger.info(f"[LLM Response Raw (text)] content={content}")
        
        # ===== 情况0: 空内容 =====
        if not content:
            logger.warning("[LLM Response] Warning: LLM returned empty content!")
            # 如果有错误信息，生成更详细的错误提示
            if error_info:
                error_hint = self._format_error_hint(error_info)
                logger.warning(f"[LLM Response] Error hint: {error_hint}")
                return self._make_result(
                    content=f"[错误] {error_hint}",
                    tool_name="finish",
                    tool_params={"result": f"[错误] {error_hint}"}
                )
            # 没有具体错误信息时，使用统一的 empty_response 错误提示
            _, user_message = get_stream_error_info('empty_response')
            return self._make_result(
                content=f"⚠️ {user_message}",
                tool_name="finish",
                tool_params={"result": f"⚠️ {user_message}"}
            )
        
        # ===== 方案C: 尝试 ToolParser.parse_response() =====
        from app.services.agent.tool_parser import ToolParser
        try:
            parsed = ToolParser.parse_response(content)
            tool_name = parsed.get("tool_name", "finish")
            thought = parsed.get("content", "")
            tool_params = parsed.get("tool_params", {})
            reasoning = parsed.get("reasoning")
            logger.info(f"[TextStrategy] ToolParser success: tool_name={tool_name}")
            return self._make_result(content=thought, tool_name=tool_name, tool_params=tool_params, reasoning=reasoning)
        except ValueError:
            pass  # ToolParser 无法解析，继续方案A/B
        
        # ===== 方案B: 工具名保底匹配 =====
        tool_result = self._extract_by_known_tools(content)
        if tool_result:
            logger.info(f"[TextStrategy] Tool match found: {tool_result['tool_name']}")
            return self._make_result(
                content=tool_result.get("content", content),
                tool_name=tool_result.get("tool_name", "finish"),
                tool_params=tool_result.get("tool_params", {})
            )
        
        # ===== 无法提取工具调用，返回 finish =====
        logger.info(f"[TextStrategy] No action extracted, returning finish with full content")
        return self._make_result(content=content, tool_name="finish", tool_params={})
    
    def _make_result(self, content: str, tool_name: str, tool_params: dict, reasoning: Any = None) -> str:
        """构建返回结果"""
        return json.dumps({
            "content": content,
            "tool_name": tool_name,
            "tool_params": tool_params,
            "reasoning": reasoning
        }, ensure_ascii=False)
    
    # ===== 方案A：分级错误信息 =====
    ERROR_HINTS = {
        "api_limit": {
            "title": "API调用频繁",
            "description": "模型访问量过大，已被限流",
            "suggestion": "请稍后再试，或更换其他模型"
        },
        "timeout": {
            "title": "请求超时",
            "description": "AI响应时间过长",
            "suggestion": "请检查网络后重试"
        },
        "connect": {
            "title": "网络连接失败",
            "description": "无法连接到AI服务",
            "suggestion": "请检查网络后重试"
        },
        "auth": {
            "title": "API认证失败",
            "description": "API密钥无效或已过期",
            "suggestion": "请检查API密钥是否有效"
        },
        "quota": {
            "title": "API额度不足",
            "description": "账户余额或调用配额已用尽",
            "suggestion": "请充值后重试"
        },
        "unknown": {
            "title": "服务暂时不可用",
            "description": "发生了未知错误",
            "suggestion": "请稍后重试"
        }
    }
    
    def _format_error_hint(self, error: str) -> str:
        """
        【2026-04-10 小沈重构】
        格式化错误提示信息，使用统一的 error_handler.py 分类
        复用 resolve_http_error_type 解析HTTP错误码，确保错误分类统一
        
        Args:
            error: 原始错误信息（如 "limit_error", "HTTP 500" 等）
        
        Returns:
            格式化后的错误提示（用户友好的中文提示）
        """
        # 【修复 2026-04-10】使用 resolve_http_error_type 解析HTTP错误码
        # 优先匹配数字错误码（429、500等），保留API返回的真实信息
        error_type = resolve_http_error_type(str(error))
        
        # 如果无法解析HTTP错误码，使用 'unknown' 作为后备
        if error_type is None:
            error_type = 'unknown'
        
        # 【修复 2026-04-10】使用带原始错误信息的 get_stream_error_info
        # 在 error_handler.py 中统一处理 message 和 type 的追加
        error_code, user_message = get_stream_error_info(error_type, original_message=str(error))
        
        logger.info(f"[LLM Error] 原始错误: {error}, 分类: {error_type}, 提示: {user_message}")
        
        # 返回统一格式的错误提示
        return f"⚠️ {user_message}"
    
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
                    "tool_name": tool,
                    "content": content,
                    "tool_params": params
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
                    
                    # 检查是否是限流错误，使用指数退避
                    if "429" in str(error_msg) or "1305" in str(error_msg):
                        if attempt < self.MAX_RETRIES - 1:
                            # 指数退避: 2, 4, 8 秒递增
                            retry_delay = self.RETRY_DELAY * (2 ** attempt)
                            logger.warning(f"[Function Calling] Rate limit detected (attempt {attempt + 1}/{self.MAX_RETRIES}), retrying in {retry_delay}s...")
                            await asyncio.sleep(retry_delay)
                            continue
                        else:
                            logger.error(f"[Function Calling] Rate limit persists after {self.MAX_RETRIES} attempts, falling back to text mode")
                            break
                    else:
                        logger.error(f"[Function Calling] API Error: {error_msg}")
                        break
                
                # 解析 tool_calls
                if hasattr(response, 'content') and response.content:
                    # 第一时间记录LLM返回的原始全部信息 - 必须满足用户要求
                    raw_content = response.content
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                    content_length = len(raw_content) if raw_content else 0
                    
                    # 记录完整的原始信息，不截断，不解析，原封不动
                    logger.info(f"[LLM Response Raw] timestamp={timestamp}, length={content_length}")
                    logger.info(f"[LLM Response Content] {raw_content}")
                    
                    try:
                        tool_calls = json.loads(response.content)
                        
                        if isinstance(tool_calls, list) and len(tool_calls) > 0:
                            content = self._format_tool_calls(tool_calls)
                            logger.info(f"[Function Calling] Received tool_calls: {len(tool_calls)} calls")
                            return content
                        else:
                            content = response.content
                            logger.info(f"[Function Calling] LLM returned text (no tool call): {content}")
                            return content
                            
                    except (json.JSONDecodeError, TypeError) as e:
                        content = response.content
                        logger.info(f"[Function Calling] Non-JSON response: {content}")
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
        
        # 【修复 2026-04-11 小沈】统一错误处理：不应该降级到 TextStrategy，应该调用 error_handler 统一处理
        if last_error:
            # 调用统一的错误处理函数
            error_type = resolve_http_error_type(last_error) if last_error else None
            error_code, error_message = get_stream_error_info(error_type, original_message=last_error)
            logger.error(f"[Function Calling] 错误统一处理: error_type={error_type}, error_message={error_message}")
            # 返回统一格式的错误响应
            return self._make_result(
                content=f"[错误] {error_message}",
                tool_name="finish",
                tool_params={"result": f"[错误] {error_message}"}
            )
        
        # 没有错误但走到了这里，说明是意外情况，仍降级到 TextStrategy
        logger.warning(f"[Function Calling] Falling back to TextStrategy (no error, unexpected)")
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
                "tool_name": func_name,
                "tool_params": args
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
                "tool_name": first_call["name"],
                "tool_params": first_call["args"]
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
                    "tool_name": {"type": "string", "description": "工具名称"},
                    "tool_params": {
                        "type": "object",
                        "description": "工具参数"
                    }
                },
                "required": ["thought", "tool_name", "tool_params"]
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
            
            logger.info(f"[Agent] response_format raw content: {content}")
            
            # 解析 JSON 响应
            try:
                result = json.loads(content)
                
                thought = result.get("thought", "")
                tool_name = result.get("tool_name", result.get("action_tool", ""))
                tool_params = result.get("tool_params", result.get("params", {}))
                
                # 转换为 Agent 的 ToolParser 可以理解的格式
                formatted = {
                    "thought": thought,
                    "tool_name": tool_name,
                    "tool_params": tool_params
                }
                
                content = json.dumps(formatted, ensure_ascii=False)
                logger.info(f"[Agent] response_format parsed: tool_name={tool_name}")
                
            except json.JSONDecodeError as e:
                logger.error(f"[Agent] Failed to parse response_format JSON: {e}, content={content}")
                raise Exception(f"Invalid JSON from LLM: {content}")
            
            
        except Exception as e:
            logger.error(f"[Agent] _get_llm_response_with_response_format failed: {e}")
            raise
