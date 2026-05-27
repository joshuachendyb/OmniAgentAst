# -*- coding: utf-8 -*-
"""
LLM 调用策略模块

两种策略：
1. TextStrategy：文本模式，直接返回响应文本
2. ToolsStrategy：Function Calling 模式，通过 tools Schema 约束

策略在首次LLM调用时确定，后续不再变化。

Author: 小沈 - 2026-03-21
"""

import json
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime

from app.utils.logger import logger
from app.chat_stream.error_handler import resolve_http_error_type, get_stream_error_info


class LLMStrategy(ABC):
    """LLM 调用策略基类 — 429重试已移到llm_core.py传输层"""
    
    @abstractmethod
    async def call(
        self,
        llm_client: Callable,
        messages: List[Dict[str, str]],
        conversation_history: List[Dict[str, str]],
        **kwargs
    ) -> str:
        """调用 LLM — messages是完整的消息列表（含system/user/assistant/tool）"""
        pass
    
    def _make_parse_error(self, error: str, content: str = "") -> str:
        """构建parse_error返回（消除5倍内联字典重复）- 小沈 2026-05-24"""
        return json.dumps({
            "type": "parse_error",
            "error": error,
            "content": content,
            "tool_name": None,
            "tool_params": None,
            "reasoning": None
        }, ensure_ascii=False)
    
    def _make_result(self, content: str, tool_name: str, tool_params: dict, reasoning: Any = None, response: str = "") -> str:
        """构建返回结果（基类方法，供子类使用）- 小沈2026-05-07加response字段"""
        result = {
            "content": content,
            "tool_name": tool_name,
            "tool_params": tool_params,
            "reasoning": reasoning
        }
        if response:
            result["response"] = response
        return json.dumps(result, ensure_ascii=False)


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
    # P4: 从注册中心动态获取工具名 - 小健 2026-05-02
    from app.services.agent.react_output_parser import _get_all_tool_names

    def _extract_llm_content(self, response: Any) -> tuple:
        """提取LLM响应的文本内容 + error_info + reasoning。三段式：content→dict→str - 北京老陈 2026-05-25"""
        error_info = None
        if getattr(response, "error", None):
            error_info = response.error
            logger.warning(f"[LLM Response] LLM returned error: {error_info}")
        content = response.content if hasattr(response, "content") and response.content else None
        if content is None and isinstance(response, dict):
            content = response.get("content") or str(response)
        elif content is None:
            content = str(response)
        response_reasoning = getattr(response, "reasoning", "") or ""
        return content, error_info, response_reasoning

    def _handle_answer_response(self, parsed: Dict, reasoning: Optional[str]) -> str:
        """统一处理answer和implicit的finish结果构造 - 北京老陈 2026-05-25"""
        _response = parsed.get("response", "")
        if not _response or not _response.strip():
            _response = parsed.get("content", "")
        return self._make_result(
            content=parsed.get("content", ""),
            tool_name="finish",
            tool_params={"result": _response},
            reasoning=parsed.get("reasoning"),
            response=_response
        )

    @staticmethod
    def _build_chunk_data(parsed: Dict, response_reasoning: Optional[str]) -> str:
        """构造chunk_data结构体，TextStrategy/JsonStrategy共享 - 北京老陈 2026-05-25"""
        chunk_data = {
            "type": "chunk",
            "content": parsed.get("content", ""),
            "thought": parsed.get("thought", ""),
            "reasoning": parsed.get("reasoning", ""),
            "tool_name": None,
            "tool_params": None,
            "response": parsed.get("content", ""),
            "error": None
        }
        if response_reasoning:
            chunk_data["_thinking"] = response_reasoning
            chunk_data["is_reasoning"] = True
        return json.dumps(chunk_data, ensure_ascii=False)

    def _handle_action_response(self, parsed: Dict, reasoning: Optional[str]) -> Optional[str]:
        """处理action类型。tool_name有效→返回result；缺失→fallthrough返回None - 北京老陈 2026-05-25"""
        tool_name = parsed.get("tool_name")
        raw_tool_params = parsed.get("tool_params")
        tool_params = raw_tool_params if raw_tool_params is not None else {}
        if tool_name and raw_tool_params is not None:
            logger.info(f"[TextStrategy] type=action, tool_name和tool_params都有值，直接返回")
            return self._make_result(
                content=parsed.get("content", ""),
                tool_name=tool_name,
                tool_params=tool_params,
                reasoning=parsed.get("reasoning")
            )
        logger.info(f"[TextStrategy] type=action 但 tool_name={tool_name}, tool_params={bool(tool_params)}，继续下一层解析")
        return None

    def _resolve_parse_fallback(self, content: str, parsed_type: Optional[str]) -> str:
        """统一fallback处理：所有解析失败都返回parse_error - 北京老陈 2026-05-25"""
        logger.info(f"[TextStrategy] parse_react_response返回type={parsed_type}，fallback到parse_error")
        return self._make_parse_error(
            "无法从 LLM 响应中提取工具调用",
            content=content[:200] + ("..." if len(content) > 200 else "")
        )

    async def call(
        self,
        llm_client: Callable,
        messages: List[Dict[str, str]],
        conversation_history: List[Dict[str, str]],
        **kwargs
    ) -> str:
        """调用 LLM（文本模式）— 429重试由llm_core传输层统一处理 - 北京老陈 2026-05-25 重构"""
        logger.info(f"[TextStrategy] call() 被调用, model={getattr(llm_client, 'model', '?')}")
        response = await llm_client(message="", history=messages)
        content, error_info, response_reasoning = self._extract_llm_content(response)
        logger.info(f"[LLM Response Raw (text)] len={len(content) if isinstance(content, str) else '非字符串'} type={type(content)} preview={str(content)[:200] if content else '空'}")
        logger.info(f"[LLM Response Raw (text)] content={content}")
        if not content:
            logger.warning("[LLM Response] Warning: LLM returned empty content!")
            if error_info:
                error_hint = self._format_error_hint(error_info)
                logger.warning(f"[LLM Response] Error hint: {error_hint}")
                return self._make_parse_error(error_hint)
            _, user_message = get_stream_error_info('empty_response')
            return self._make_parse_error(user_message)
        from app.services.agent.react_output_parser import parse_react_response
        logger.info(f"[DEBUG] 传给parse前 - content长度: {len(content) if isinstance(content, str) else '非字符串'}, content类型: {type(content)}")
        try:
            parsed = parse_react_response(content)
            parsed_type = parsed.get("type")
            logger.info(f"[TextStrategy] parse_react_response success: type={parsed_type}")
            handler_map: Dict[str, Callable] = {
                "answer": lambda: self._handle_answer_response(parsed, response_reasoning),
                "implicit": lambda: self._handle_answer_response(parsed, response_reasoning),
                "chunk": lambda: self._build_chunk_data(parsed, response_reasoning),
                "action": lambda: self._handle_action_response(parsed, response_reasoning),
            }
            handler = handler_map.get(parsed_type)
            if handler:
                result = handler()
                if result:
                    return result
            return self._resolve_parse_fallback(content, parsed_type)
        except ValueError:
            return self._resolve_parse_fallback(content, None)
    
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

    async def _fallback_to_text(self, messages: List[Dict], **kwargs) -> str:
        """fallback到TextStrategy（消除重复3次的内联回退模式）- 小沈 2026-05-24"""
        text_strategy = TextStrategy()
        if self.tools:
            messages = self._inject_tools_into_messages(messages)
            logger.info(f"[Function Calling] fallback前注入{len(self.tools)}个工具描述到messages")
        return await text_strategy.call(
            llm_client=kwargs.pop('llm_client'),
            messages=messages,
            conversation_history=kwargs.pop('conversation_history'),
            **kwargs
        )

    def _inject_tools_into_messages(self, messages: List[Dict]) -> List[Dict]:
        """将tools定义作为文本注入到messages中（fallback到text模式时使用）— 小沈 2026-05-24"""
        if not self.tools:
            return messages
        lines = ["【可用工具】"]
        for t in self.tools:
            func = t.get("function", {})
            name = func.get("name", "")
            desc = func.get("description", "")
            params = func.get("parameters", {})
            props = params.get("properties", {})
            required = params.get("required", [])
            param_strs = []
            for pname, pinfo in props.items():
                ptype = pinfo.get("type", "any")
                pdesc = pinfo.get("description", "")
                req = "(必填)" if pname in required else "(可选)"
                param_strs.append(f"  - {pname}({ptype}){req}: {pdesc}" if pdesc else f"  - {pname}({ptype}){req}")
            lines.append(f"- {name}: {desc}")
            if param_strs:
                lines.extend(param_strs)
        if len(lines) <= 1:
            return messages
        tools_text = "\n".join(lines)
        return [{"role": "system", "content": tools_text}] + list(messages)

    async def call(
        self,
        llm_client: Callable,
        messages: List[Dict[str, str]],
        conversation_history: List[Dict[str, str]],
        **kwargs
    ) -> str:
        """调用 LLM（Function Calling 模式）"""
        logger.info(f"[ToolsStrategy] call() 被调用, model={getattr(llm_client, 'model', '?')}, tools_count={len(self.tools)}")
        
        if not hasattr(llm_client, 'chat_with_tools'):
            logger.warning("[Function Calling] llm_client has no chat_with_tools method, falling back to text mode")
            return await self._fallback_to_text(messages, **kwargs)
        
        try:
            response = await llm_client.chat_with_tools(
                message="",
                history=messages,
                tools=self.tools
            )
            # 保存原始response供FC协议注入使用
            llm_client._last_chat_response = response
            
            if hasattr(response, 'error') and response.error:
                error_msg = response.error
                logger.error(f"[Function Calling] API Error: {error_msg}")
                error_type = resolve_http_error_type(error_msg)
                error_code, error_message = get_stream_error_info(error_type, original_message=error_msg)
                return self._make_parse_error(error_message, content=f"[错误] {error_message}")
            
            if hasattr(response, 'content') and response.content:
                raw_content = response.content
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                content_length = len(raw_content) if raw_content else 0
                logger.info(f"[LLM Response Raw] timestamp={timestamp}, length={content_length}")
                logger.info(f"[LLM Response Content] {raw_content}")
                
                try:
                    tool_calls = json.loads(response.content)
                    if isinstance(tool_calls, list):
                        if len(tool_calls) > 0:
                            content = self._format_tool_calls(tool_calls)
                            logger.info(f"[Function Calling] Received tool_calls: {len(tool_calls)} calls")
                            return content
                        else:
                            logger.info("[Function Calling] Empty tool_calls, convert to finish")
                            return json.dumps({"thought": "任务完成", "tool_name": "finish", "tool_params": {}}, ensure_ascii=False)
                    else:
                        content = response.content
                        logger.info(f"[Function Calling] Non-list response: {content[:200]}")
                        return content
                except (json.JSONDecodeError, TypeError) as e:
                    # 非JSON响应直接给下游parse_react_response统一解析（SRP：策略层只负责调用LLM，不负责解析）
                    content = response.content
                    logger.info(f"[Function Calling] 非JSON响应，原始文本交给parse_react_response解析: {content[:200]}")
                    return content
            else:
                logger.warning("[Function Calling] Empty response, falling back to text mode")
                return await self._fallback_to_text(messages, **kwargs)
        except Exception as e:
            logger.error(f"[Function Calling] Exception: {e}")
            error_type = resolve_http_error_type(str(e))
            error_code, error_message = get_stream_error_info(error_type, original_message=str(e))
            return self._make_parse_error(error_message, content=f"[错误] {error_message}")
    
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
            # 多个工具调用（执行第一个，其余放入_pending_calls依次执行）
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
            
            first_call = calls_info[0]
            remaining = calls_info[1:]
            formatted = {
                "thought": f"Calling {len(tool_calls)} tools: {[c['name'] for c in calls_info]}",
                "tool_name": first_call["name"],
                "tool_params": first_call["args"],
                "_pending_calls": remaining
            }
        
        return json.dumps(formatted, ensure_ascii=False)

