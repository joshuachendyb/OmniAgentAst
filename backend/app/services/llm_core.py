"""
LLM 核心模块 - 提供通用的 LLM API 调用能力

包含：
- Message: 消息类
- ChatResponse: 非流式响应类
- StreamChunk: 流式响应片段类
- BaseAIService: 通用AI服务（支持所有OpenAI兼容API）

使用方式：
1. 只需在 config.yaml 配置 api_base、model、api_key
2. 新增provider无需修改任何代码

作者：小沈
创建时间：2026-03-27
"""

import json
import re
import asyncio
import httpx
import httpcore
from typing import List, Dict, Optional, AsyncGenerator, Any

from app.utils.logger import logger


def _convert_xml_tool_call_to_json(content: str) -> Optional[str]:
    """
    通用XML工具调用转JSON
    
    某些模型（如LongCat）返回XML格式工具调用而不是标准OpenAI tool_calls。
    格式: <XXX_tool_call>TOOL_NAME\\n<XXX_arg_key>k</XXX_arg_key>\\n<XXX_arg_value>v</XXX_arg_value>\\n</XXX_tool_call>
    
    此函数通用检测任意前缀的XML工具调用标签并转为标准JSON格式。
    
    Returns:
        转换后的JSON字符串，如果无匹配返回None
    """
    if not content or '<' not in content or '_tool_call>' not in content:
        return None
    
    # 匹配 <任意前缀_tool_call>TOOL_NAME
    m = re.search(r'<(\w+)_tool_call>\s*(\w+)', content)
    if not m:
        return None
    
    prefix = m.group(1)   # 如: longcat
    tool_name = m.group(2)  # 如: search_web
    
    # 匹配 <prefix_arg_key>KEY</prefix_arg_key> 和 <prefix_arg_value>VALUE</prefix_arg_value> 对
    arg_keys = re.findall(rf'<{prefix}_arg_key>([^<]+)</{prefix}_arg_key>', content)
    arg_values = re.findall(rf'<{prefix}_arg_value>([^<]*)</{prefix}_arg_value>', content)
    
    if not arg_keys:
        return None
    
    # 构建标准JSON格式
    tool_params = {}
    for i, key in enumerate(arg_keys):
        val = arg_values[i] if i < len(arg_values) else ''
        tool_params[key.strip()] = val.strip()
    
    result = json.dumps({
        "tool_name": tool_name,
        "tool_params": tool_params
    }, ensure_ascii=False)
    
    return result


class Message:
    """消息类 - 用于构建 LLM 调用时的消息列表"""
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content
    
    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


class ChatResponse:
    """聊天响应类 - 非流式响应"""
    def __init__(self, content: str, model: str, provider: str = "", error: Optional[str] = None,
                 reasoning: Optional[str] = None):
        self.content = content
        self.model = model
        self.provider = provider
        self.error = error
        self.success = error is None
        self.reasoning = reasoning or ""


class StreamChunk:
    """流式响应片段"""
    def __init__(self, content: str, model: str, is_done: bool = False, 
                 stream_error: Optional[str] = None, stream_error_type: Optional[str] = None,
                 reasoning: Optional[str] = None, is_reasoning: bool = False):
        self.content = content
        self.model = model
        self.is_done = is_done
        self.stream_error = stream_error
        self.stream_error_type = stream_error_type
        self.reasoning = reasoning
        self.is_reasoning = is_reasoning


class BaseAIService:
    """
    通用AI服务 - 一个类支持所有OpenAI兼容API
    
    适用于所有遵循OpenAI API格式的服务提供商：
    - 智谱GLM (zhipuai)
    - OpenCode
    - DeepSeek
    - Kimi
    - 月之暗面 (moonshot)
    - 通义千问 (qwen)
    - 无限可能...
    
    新增provider只需在配置文件中添加配置，零代码修改！
    """
    
    # 模型格式缓存：key=model_name, value=True(数组)/False(字符串) - 小健 2026-05-16
    _model_format_cache: Dict[str, bool] = {}

    def __init__(self, api_key: str, model: str, api_base: str, provider: str = "", timeout: int = 60,
                 max_tokens: int = 4096, temperature: float = 0.7, seed: Optional[int] = None):
        self.api_key = api_key
        self.model = model
        self.api_base = api_base
        self.provider = provider
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.seed = seed
        
        try:
            timeout_value = float(timeout) if timeout else 60.0
        except (ValueError, TypeError):
            timeout_value = 60.0
        self.timeout = int(timeout_value)
        
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=30.0,  # 【2026-05-14 小健/小沈】httpx 0.26.0→0.28.1后TLS偶发超时，10→30
                read=None,
                write=10.0,
                pool=10.0,
            ),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )
        
        self._cancelled = False
        self._current_response: Optional[httpx.Response] = None

    def _build_request_body(self, messages: List[Dict]) -> Dict:
        """
        构建LLM API请求体

        【改进8 2026-05-01 小沈 小健】添加max_tokens/temperature/seed参数

        Returns:
            包含model/messages/stream/参数的请求体字典
        """
        body = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        # seed可选，None时不传（避免不支持seed的API报错）
        if self.seed is not None:
            body["seed"] = self.seed
        return body
    
    def cancel(self):
        """强制取消当前请求"""
        logger.info(f"[BaseAIService.cancel] 正在强制取消请求, model={self.model}")
        self._cancelled = True
        if self._current_response:
            try:
                # 【修复 2026-04-30 小沈】异步流用aclose()，不能用同步close()
                if hasattr(self._current_response, 'aclose'):
                    import asyncio
                    try:
                        asyncio.get_event_loop().run_until_complete(self._current_response.aclose())
                    except RuntimeError:
                        pass
                else:
                    self._current_response.close()
                logger.info("[BaseAIService.cancel] HTTP响应已强制关闭")
            except Exception as e:
                logger.error(f"[BaseAIService.cancel] 关闭响应失败: {e}")
    
    def reset_cancel(self):
        """重置取消状态（用于新请求）"""
        self._cancelled = False
        self._current_response = None
    
    def _build_messages(self, message: str, history: Optional[List[Message]] = None, array_format: bool = True) -> List[Dict]:
        """构建消息列表 - 小健 2026-05-16 添加数组格式支持(先试数组，失败退回到字符串)"""
        messages = []
        if history:
            for msg in history:
                msg_dict = msg.to_dict()
                if array_format and isinstance(msg_dict.get("content"), str):
                    msg_dict["content"] = [{"type": "text", "text": msg_dict["content"]}]
                messages.append(msg_dict)
        content = message
        if array_format:
            content = [{"type": "text", "text": message}]
        messages.append({"role": "user", "content": content})
        return messages
    
    async def chat(self, message: str, history: Optional[List[Message]] = None) -> ChatResponse:
        """发送对话请求（一次性返回）
        
        【修复 2026-05-05 小沈】添加reasoning_content聚合日志，
        便于诊断thinking模型空响应问题
        """
        try:
            full_content = ""
            full_reasoning = ""
            has_non_reasoning_content = False
            stream_error = None
            async for chunk in self.chat_stream(message, history):
                if chunk.content:
                    if getattr(chunk, "is_reasoning", False):
                        # reasoning_content: 收集到reasoning字段，不合并到content
                        full_reasoning += chunk.content
                    else:
                        # 普通content: 正常收集
                        full_content += chunk.content
                        has_non_reasoning_content = True
                # 【修复 2026-05-05 小沈】记录explicit reasoning字段
                if chunk.reasoning:
                    full_reasoning += chunk.reasoning
                if chunk.stream_error:
                    stream_error = chunk.stream_error
                if chunk.is_done:
                    break
            # 【2026-05-13 小沈】fallback：如果没有非推理内容，用推理内容代替（thinking模型）
            if not has_non_reasoning_content and full_reasoning:
                full_content = full_reasoning
                logger.info(f"[chat] 无普通content，使用reasoning_content作为fallback")
            # 【修复 2026-05-05 小沈】日志：记录聚合结果，便于诊断空响应
            logger.info(
                f"[chat] 聚合结果, model={self.model}, "
                f"full_content长度={len(full_content)}, "
                f"full_reasoning长度={len(full_reasoning)}, "
                f"has_error={stream_error is not None}"
            )
            if stream_error:
                return ChatResponse(content="", model=self.model, provider=self.provider, error=stream_error)
            return ChatResponse(content=full_content, model=self.model, provider=self.provider,
                                reasoning=full_reasoning)
        except Exception as e:
            logger.error(f"[chat] 异常: {e}")
            return ChatResponse(content="", model=self.model, provider=self.provider, error=str(e))
    
    async def chat_stream(self, message: str, history: Optional[List[Message]] = None) -> AsyncGenerator[StreamChunk, None]:
        """发送对话请求（流式返回）- 小健 2026-05-16 先试数组格式，记住结果后续复用"""
        self.reset_cancel()
        
        # 查缓存：之前试过这个模型吗？
        cached_array = self._model_format_cache.get(self.model)
        if cached_array is not None:
            formats_to_try = [cached_array]
        else:
            formats_to_try = [True, False]  # 先试数组，不行再试字符串
        
        last_error = None
        for is_array in formats_to_try:
            if is_array and cached_array is False:
                continue  # 缓存说不要用数组，跳过
            if not is_array and cached_array is True:
                continue  # 缓存说要用数组，跳过
            
            messages = self._build_messages(message, history, array_format=is_array)
            fmt_label = "数组" if is_array else "字符串"
            logger.info(f"[LLM Request] model={self.model}, format={fmt_label}, messages={len(messages)}")
            
            try:
                async with self.client.stream(
                    "POST",
                    f"{self.api_base}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=self._build_request_body(messages)
                ) as response:
                    self._current_response = response
                    
                    if self._cancelled:
                        await response.aclose()
                        yield StreamChunk(content="", model=self.model, is_done=True, stream_error="任务已取消", stream_error_type="cancelled")
                        return
                    
                    if response.status_code != 200:
                        error_body = await response.aread()
                        error_text = error_body.decode("utf-8", errors="ignore")
                        logger.error(f"[chat_stream] HTTP {response.status_code} error: {error_text[:200]}")
                        
                        # 格式错误？记下来，下次用另一种格式
                        if "invalid_format" in error_text.lower() or "json format" in error_text.lower():
                            self._model_format_cache[self.model] = False  # 下次用字符串
                            if not formats_to_try[-1]:  # 还有下一轮
                                last_error = error_text[:200]
                                continue
                        
                        yield StreamChunk(content="", model=self.model, is_done=True,
                            stream_error=f"API Error: {response.status_code}, {error_text[:200]}", stream_error_type="api_error")
                        return
                    
                    # 成功！记住这个模型用数组格式没问题
                    if is_array and self.model not in self._model_format_cache:
                        self._model_format_cache[self.model] = True
                    
                    # 处理流式响应
                    line_iterator = response.aiter_lines()
                    _reasoning_content_total = 0
                    _content_total = 0
                    
                    while True:
                        try:
                            line = await asyncio.wait_for(line_iterator.__anext__(), timeout=1.0)
                        except asyncio.TimeoutError:
                            if self._cancelled:
                                yield StreamChunk(content="", model=self.model, is_done=True, stream_error="任务已取消", stream_error_type="cancelled")
                                return
                            continue
                        except StopAsyncIteration:
                            break
                        
                        if self._cancelled:
                            yield StreamChunk(content="", model=self.model, is_done=True, stream_error="任务已取消", stream_error_type="cancelled")
                            return
                        if not line or line.strip() == "":
                            continue
                        
                        if line.startswith("data: "):
                            data_str = line[6:]
                        elif line.startswith("data:"):
                            data_str = line[5:]
                        else:
                            continue
                        
                        if data_str.strip() == "[DONE]":
                            logger.info(f"[chat_stream] 流结束[DONE], model={self.model}")
                            yield StreamChunk(content="", model=self.model, is_done=True)
                            return
                        
                        try:
                            data = json.loads(data_str)
                            for choice in data.get("choices", []):
                                delta = choice.get("delta", {})
                                content = delta.get("content", "") or ""
                                reasoning = delta.get("reasoning_content", "") or ""
                                if content:
                                    _content_total += len(content)
                                    yield StreamChunk(content=content, model=self.model, is_done=False, is_reasoning=False)
                                if reasoning:
                                    _reasoning_content_total += len(reasoning)
                                    if _reasoning_content_total == len(reasoning):
                                        logger.info(f"[chat_stream] 首次收到reasoning_content, model={self.model}")
                                    yield StreamChunk(content=reasoning, model=self.model, is_done=False, is_reasoning=True)
                        except json.JSONDecodeError:
                            continue
                    
                    logger.info(f"[chat_stream] 流正常结束, model={self.model}")
                    yield StreamChunk(content="", model=self.model, is_done=True)
                    return
                    
            except httpx.TimeoutException:
                yield StreamChunk(content="", model=self.model, is_done=True, stream_error="请求超时，请重试", stream_error_type="timeout_error")
                return
            except (httpx.ReadError, httpcore.ReadError):
                yield StreamChunk(content="", model=self.model, is_done=True, stream_error="读取响应失败，请重试", stream_error_type="read_error")
                return
            except (httpx.ConnectError, httpcore.ConnectError):
                yield StreamChunk(content="", model=self.model, is_done=True, stream_error="连接失败，请检查网络", stream_error_type="connect_error")
                return
            except httpx.HTTPStatusError as e:
                yield StreamChunk(content="", model=self.model, is_done=True, stream_error=f"HTTP {e.response.status_code}: {str(e)[:100]}", stream_error_type="http_error")
                return
            except Exception as e:
                logger.error(f"[chat_stream] 异常: {e}")
                yield StreamChunk(content="", model=self.model, is_done=True, stream_error=str(e)[:200], stream_error_type="unknown_error")
                return
        
        # 所有格式都试完了
        yield StreamChunk(content="", model=self.model, is_done=True,
            stream_error=f"API Error: {last_error}" if last_error else "服务调用失败",
            stream_error_type="api_error")


    async def validate(self) -> bool:
        """验证API Key是否有效 - 已废弃，请使用 init_model_select.py 中的接口实现"""
        raise NotImplementedError("validate() 已废弃，请使用 /api/v1/chat/validate 接口")
    
    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()
    
    async def chat_with_tools(
        self,
        message: str,
        history: Optional[List[Message]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto"
    ) -> ChatResponse:
        """发送对话请求（使用 Function Calling）
        
        【小沈优化 2026-04-21】使用后台任务+心跳检查，1秒内响应取消
        """
        try:
            messages = self._build_messages(message, history)
            
            request_json = {
                "model": self.model,
                "messages": messages
            }
            
            if tools:
                request_json["tools"] = tools
                request_json["tool_choice"] = tool_choice
            
            logger.info(
                f"[chat_with_tools] model={self.model}, "
                f"messages数量={len(messages)}, "
                f"tools数量={len(tools) if tools else 0}"
            )
            
            # 【小沈优化 2026-04-21】使用后台任务+心跳检查，支持1秒内响应取消
            request_task = asyncio.ensure_future(
                self.client.post(
                    f"{self.api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json=request_json
                )
            )
            
            try:
                while not request_task.done():
                    # 等待1秒或直到任务完成
                    try:
                        await asyncio.wait_for(asyncio.shield(request_task), timeout=1.0)
                    except asyncio.TimeoutError:
                        # 检查是否被取消
                        if self._cancelled:
                            logger.info("[chat_with_tools] 检测到取消，中断请求")
                            request_task.cancel()
                            try:
                                await request_task
                            except asyncio.CancelledError:
                                pass
                            return ChatResponse(
                                content="",
                                model=self.model,
                                provider=self.provider,
                                error="任务已取消"
                            )
                        continue
                
                response = await request_task
                
            except asyncio.CancelledError:
                return ChatResponse(
                    content="",
                    model=self.model,
                    provider=self.provider,
                    error="任务已取消"
                )
            
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"[chat_with_tools] API Error: {response.status_code}, {error_text}")
                return ChatResponse(
                    content="",
                    model=self.model,
                    provider=self.provider,
                    error=f"API Error: {response.status_code}, {error_text}"
                )
            
            data = response.json()
            choices = data.get("choices", [])
            
            if not choices:
                return ChatResponse(
                    content="",
                    model=self.model,
                    provider=self.provider,
                    error="No response from API"
                )
            
            msg = choices[0].get("message", {})
            tool_calls = msg.get("tool_calls", [])
            if tool_calls:
                return ChatResponse(
                    content=json.dumps(tool_calls, ensure_ascii=False),
                    model=self.model,
                    provider=self.provider
                )
            else:
                content = msg.get("content", "")
                if not content:
                    finish_reason = choices[0].get("finish_reason", "")
                    if finish_reason == "tool_calls":
                        return ChatResponse(
                            content="",
                            model=self.model,
                            provider=self.provider,
                            error="Failed to parse tool_calls"
                        )
                
                # 【通用XML工具调用检测 2026-05-13 小沈】某些模型（如LongCat）返回XML格式工具调用
                # 格式: <XXX_tool_call>TOOL_NAME\n<XXX_arg_key>k</XXX_arg_key>\n<XXX_arg_value>v</XXX_arg_value>\n</XXX_tool_call>
                xml_converted = _convert_xml_tool_call_to_json(content)
                if xml_converted:
                    logger.info(f"[chat_with_tools] 检测到XML工具调用格式，已转为JSON: {xml_converted}")
                    return ChatResponse(
                        content=xml_converted,
                        model=self.model,
                        provider=self.provider
                    )
                
                return ChatResponse(
                    content=content,
                    model=self.model,
                    provider=self.provider
                )
                
        except Exception as e:
            import traceback
            error_type_name = type(e).__name__
            logger.error(
                f"[chat_with_tools] Exception: {str(e)}, "
                f"type: {error_type_name}, "
                f"stack: {traceback.format_exc()}"
            )
            return ChatResponse(
                content="",
                model=self.model,
                provider=self.provider,
                error=f"{error_type_name}: {str(e)}"
            )
    
    async def chat_with_tools_stream(
        self,
        message: str,
        history: Optional[List[Message]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto"
    ) -> AsyncGenerator[StreamChunk, None]:
        """发送对话请求（使用 Function Calling，流式返回）"""
        self.reset_cancel()
        
        try:
            messages = self._build_messages(message, history)
            
            request_json = {
                "model": self.model,
                "messages": messages,
                "stream": True
            }
            
            if tools:
                request_json["tools"] = tools
                request_json["tool_choice"] = tool_choice
            
            logger.info(
                f"[chat_with_tools_stream] model={self.model}, "
                f"tools数量={len(tools) if tools else 0}"
            )
            
            async with self.client.stream(
                "POST",
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=request_json
            ) as response:
                self._current_response = response
                
                # 【修复】发送请求后立即检查取消标志，避免延迟
                if self._cancelled:
                    logger.info("[chat_with_tools_stream] 请求发送后立即检测到取消")
                    # 【修复 2026-04-30 小沈】异步流用aclose()
                    await response.aclose()
                    yield StreamChunk(content="", model=self.model, is_done=True, stream_error="任务已取消", stream_error_type="cancelled")
                    return
                
                if response.status_code != 200:
                    yield StreamChunk(
                        content="",
                        model=self.model,
                        is_done=True,
                        stream_error=f"API Error: {response.status_code}"
                    )
                    return
                
                # 【问题2修复】同样使用wait_for定期检查，每1秒超时
                # 【小沈修复 2026-04-21】修复StreamConsumed错误：使用单个迭代器，避免重复创建
                line_iterator = response.aiter_lines()
                
                # 【修复 2026-05-05 小沈】统计reasoning_content和content的接收情况
                _reasoning_content_total = 0
                _content_total = 0
                
                while True:
                    try:
                        line = await asyncio.wait_for(line_iterator.__anext__(), timeout=1.0)
                    except asyncio.TimeoutError:
                        if self._cancelled:
                            logger.info("[chat_with_tools_stream] Cancelled (1s timeout check)")
                            yield StreamChunk(
                                content="",
                                model=self.model,
                                is_done=True,
                                stream_error="任务已取消",
                                stream_error_type="cancelled"
                            )
                            return
                        continue
                    except StopAsyncIteration:
                        break
                    
                    if self._cancelled:
                        logger.info("[chat_with_tools_stream] Cancelled")
                        yield StreamChunk(
                            content="",
                            model=self.model,
                            is_done=True,
                            stream_error="任务已取消",
                            stream_error_type="cancelled"
                        )
                        return
                    
                    if not line or line.strip() == "":
                        continue
                    
                    if line.startswith("data: "):
                        data_str = line[6:]
                    elif line.startswith("data:"):
                        data_str = line[5:]
                    else:
                        continue
                    
                    if data_str.strip() == "[DONE]":
                        # 【修复 2026-05-05 小沈】日志：记录流结束时的统计信息
                        logger.info(
                            f"[chat_with_tools_stream] 流结束[DONE], model={self.model}, "
                            f"content_total={_content_total}, "
                            f"reasoning_content_total={_reasoning_content_total}"
                        )
                        yield StreamChunk(content="", model=self.model, is_done=True)
                        return
                    
                    try:
                        data = json.loads(data_str)
                        choices = data.get("choices", [])
                        
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "") or ""
                            # 【修复 2026-05-05 小沈】处理thinking模型的reasoning_content
                            reasoning_content = delta.get("reasoning_content", "") or ""
                            
                            if content:
                                _content_total += len(content)
                                yield StreamChunk(
                                    content=content,
                                    model=self.model,
                                    is_done=False,
                                    is_reasoning=False
                                )
                            
                            # 【修复 2026-05-05 小沈】reasoning_content也作为content输出
                            if reasoning_content:
                                _reasoning_content_total += len(reasoning_content)
                                if _reasoning_content_total == len(reasoning_content):
                                    logger.info(
                                        f"[chat_with_tools_stream] 首次收到reasoning_content, "
                                        f"model={self.model}, "
                                        f"delta_keys={list(delta.keys())}"
                                    )
                                yield StreamChunk(
                                    content=reasoning_content,
                                    model=self.model,
                                    is_done=False,
                                    is_reasoning=True
                                )
                    except json.JSONDecodeError:
                        continue
                
                # 【修复 2026-05-05 小沈】日志：记录流正常结束时的统计信息
                logger.info(
                    f"[chat_with_tools_stream] 流正常结束(迭代器耗尽), model={self.model}, "
                    f"content_total={_content_total}, "
                    f"reasoning_content_total={_reasoning_content_total}"
                )
                yield StreamChunk(content="", model=self.model, is_done=True)
                
        except Exception as e:
            import traceback
            logger.error(f"[chat_with_tools_stream] Error: {e}")
            yield StreamChunk(
                content="",
                model=self.model,
                is_done=True,
                stream_error=str(e)
            )
        finally:
            self._current_response = None
    
    async def chat_with_response_format(
        self,
        message: str,
        history: Optional[List[Message]] = None,
        response_format: Optional[Dict[str, Any]] = None
    ) -> ChatResponse:
        """发送对话请求（使用 Structured Outputs response_format）"""
        try:
            messages = self._build_messages(message, history)
            
            request_json: Dict[str, Any] = {
                "model": self.model,
                "messages": messages
            }
            
            if response_format:
                request_json["response_format"] = response_format
            
            logger.info(
                f"[chat_with_response_format] model={self.model}, "
                f"response_format={'provided' if response_format else 'None'}"
            )
            
            response = await self.client.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=request_json
            )
            
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"[chat_with_response_format] API Error: {response.status_code}, {error_text}")
                return ChatResponse(
                    content="",
                    model=self.model,
                    provider=self.provider,
                    error=f"API Error: {response.status_code}"
                )
            
            data = response.json()
            choices = data.get("choices", [])
            
            if not choices:
                return ChatResponse(
                    content="",
                    model=self.model,
                    provider=self.provider,
                    error="No response from API"
                )
            
            msg = choices[0].get("message", {})
            content = msg.get("content", "")
            
            return ChatResponse(
                content=content,
                model=self.model,
                provider=self.provider
            )
            
        except Exception as e:
            import traceback
            error_type_name = type(e).__name__
            logger.error(
                f"[chat_with_response_format] Exception: {str(e)}, "
                f"type: {error_type_name}, "
                f"stack: {traceback.format_exc()}"
            )
            return ChatResponse(
                content="",
                model=self.model,
                provider=self.provider,
                error=f"{error_type_name}: {str(e)}"
            )
