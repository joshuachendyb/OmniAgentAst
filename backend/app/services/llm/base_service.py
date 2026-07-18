"""
LLM 核心模块 — BaseAIService

重构: 删除mixin继承, 统一为request/request_stream/chat + mode参数 - 小沈 2026-06-09
FC-only: tool_calls原生yield,不走JSON roundtrip - 小沈 2026-06-12
清理: 删除死代码_is_rate_limit_status(无调用方,限流由SystemErrorClassifier覆盖) - 小欧 2026-07-14

编辑历史:
# 格式规范: {日期} {署名} {修改内容}
  2026-07-14 小欧 删除死代码_is_rate_limit_status(无调用方,限流由SystemErrorClassifier覆盖,功能零退化)
   2026-07-14 小欧 集中LLM_*/FC_*/TOOL_CACHE_TTL至app.constants(代码变迁遗留,非功能退化,同步改llm_stream/universal_agent/测试导入)
    2026-07-16 小欧 新增三层防线——①LLM_MAX_TOKENS=16384(防无限长输出); ②STREAM_TOTAL_TIMEOUT=500s总时长硬超时(httpx idle timeout 在连续流式时不触发,用 wall-clock 兜底); ③tool_call流式超时=总时长3/5=300s(_parse_sse_data 对 tool_call delta 静默跳过, 专门卡此阶段). 三者超时后均 break→accumulator→截断修复, 不触发重试
   2026-07-17 小沈 FC重命名: FCFormatError→LLMResponseError, 导入路径同步更新
   2026-07-17 小欧 流式截断落库修复: 落库 tool_call.arguments 改为使用已解析规范化后的 params(json.dumps), 而非原始流式串。原因: 流式总超时截断时原始串为非完整JSON, 直接落库会在下一轮回传给LLM API时触发参数校验失败; 以已成功解析(或已自动修补)的合法dict为准, 保证历史消息 arguments 永远合法, 工具已执行的结果得以保留, 功能零退化
    2026-07-17 小欧 429配额耗尽增强: 重试耗尽后对前端输出"配额/限流耗尽"而非泛化"服务器错误", 提升可观测性
   2026-07-18 小欧 #7 fix: 并行tool_calls累加器遇重复idx自增去重
   2026-07-18 小欧 #32 fix: 空name tool_call delta加warning日志
   2026-07-18 小欧 #34 fix: StreamChunk.truncated字段;超时截断时标记
   2026-07-18 小欧 #35 fix: _parse_sse_data改为generator,reasoning+content同chunk各yield一帧
    2026-07-18 小欧 #7 fix: 并行tool_calls累加器遇重复idx时自增去重(while idx in tool_call_accumulator: idx+=1), 缺index或全0的并行调用不再塌缩成一个
   2026-07-18 小欧 #38 fix: 流结束后过滤空name的幽灵tool_call delta（非真实工具调用,不触发L2重试）
    2026-07-18 小欧 #7回归修正: 改while自增为if not in直接合并——OpenAI流式协议中单tool_call以稳定index跨多delta续传(首delta带name,后续仅arguments), 原#7自增致name与arguments撕裂不同槽位→解析失败→FC降级
"""

import asyncio
import time
import json as _json
from typing import List, Dict, Optional, AsyncGenerator, Any, Callable

import httpx
from app.logger import logger
from app.utils.json_utils import parse_json, _try_fix_incomplete_json, _normalize_tool_params
from app.services.llm.core import ChatResponse, LLMResponseError, StreamChunk, _resolve_exception
# 注: LLM_*/FC_*/TOOL_CACHE_TTL 已集中迁移至 app.constants(2026-07-14 小欧)
from app.services.llm.core import create_cancelled_chunk
from app.services.llm.client_sdk import create_llm_client
from app.services.llm.reasoning import extract_reasoning_from_chunk, extract_reasoning_from_message
from app.services.llm.error_classifier import SystemErrorClassifier

from app.constants import DEFAULT_READ_TIMEOUT, LLM_TEMPERATURE, LLM_STREAM_MAX_RETRIES, LLM_STREAM_OPTIONS, STREAM_TOTAL_TIMEOUT, LLM_MAX_TOKENS


class BaseAIService:
    """通用AI服务 — request/request_stream/chat — FC-only重构 2026-06-11 小沈"""

    def __init__(
        self,
        api_key: str,
        model: str,
        api_base: str,
        provider: str = "",
        timeout: int = DEFAULT_READ_TIMEOUT,
        max_tokens: Optional[int] = None,
        temperature: float = None,
        seed: Optional[int] = None,
        extra_body_params: Optional[Dict] = None,
        context_limit: Optional[int] = None,
    ):
        if temperature is None:
            temperature = LLM_TEMPERATURE
        self.api_key = api_key
        self.model = model
        self.api_base = api_base
        self.provider = provider
        self.max_tokens = max_tokens if max_tokens is not None else LLM_MAX_TOKENS
        self.temperature = temperature
        self.seed = seed
        self.extra_body_params = extra_body_params
        self.context_limit = context_limit
        self._llm_sdk = None
        try:
            timeout_value = float(timeout) if timeout else float(DEFAULT_READ_TIMEOUT)
        except (ValueError, TypeError):
            timeout_value = float(DEFAULT_READ_TIMEOUT)
        self.timeout = int(timeout_value)
        self._cancelled = False
        self._current_response: Optional[httpx.Response] = None
        self._stop_check: Optional[Callable] = None

    def _ensure_client(self):
        if self._llm_sdk is None:
            self._llm_sdk = create_llm_client(
                provider=self.provider or "openai",
                model=self.model,
                api_key=self.api_key,
                base_url=self.api_base,
                timeout=self.timeout,
            )

    async def cancel(self):
        logger.info(f"[BaseAIService.cancel] 正在强制取消请求, model={self.model}")
        self._cancelled = True
        if self._current_response:
            try:
                if hasattr(self._current_response, 'aclose'):
                    await self._current_response.aclose()
                else:
                    self._current_response.close()
                logger.info("[BaseAIService.cancel] HTTP响应已强制关闭")
            except Exception as e:
                logger.error(f"[BaseAIService.cancel] 关闭响应失败: {e}")

    def reset_cancel(self):
        self._cancelled = False
        self._current_response = None

    def set_stop_check(self, check_fn: Callable):
        """设置停止检查回调 — 由调用方注入，消除llm→task反向依赖 — 小沈 2026-06-17"""
        self._stop_check = check_fn

    async def _check_stop(self) -> bool:
        """检查是否应该停止 — 优先调用注入的回调，否则检查本地_cancelled — 小沈 2026-06-17"""
        if self._stop_check:
            return await self._stop_check()
        return self._cancelled


    def _create_stream_error_chunk(self, e: Exception) -> StreamChunk:
        msg, err_type = _resolve_exception(e)
        if err_type == "unknown":
            logger.warning(f"[{type(e).__name__}] 未分类异常: {e}")
        return StreamChunk(content="", model=self.model, is_done=True, stream_error=msg, stream_error_type=err_type)

    async def request(
        self,
        messages: List[Dict],
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
    ) -> ChatResponse:
        """非流式请求 — FC-only: 无mode参数 — 小沈 2026-06-11"""
        self._ensure_client()
        try:
            response = await self._llm_sdk.request(
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                seed=self.seed,
                extra_body=self.extra_body_params,
            )
            choices = response.get("choices", [])
            if not choices:
                return ChatResponse(content="", model=self.model, provider=self.provider, error="无响应")

            msg = choices[0].get("message", {})
            content = msg.get("content", "") or ""
            tool_calls = msg.get("tool_calls", [])

            reasoning = extract_reasoning_from_message(msg) or ""

            return ChatResponse(
                content=content,
                model=self.model,
                provider=self.provider,
                tool_calls=tool_calls,
                reasoning=reasoning,
            )
        except Exception as e:
            return ChatResponse(content="", model=self.model, provider=self.provider, error=str(e))

    async def request_stream(
        self,
        messages: List[Dict],
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
    ) -> AsyncGenerator[StreamChunk, None]:
        """流式请求 — FC-only: tool_calls原生yield,不走JSON roundtrip — 小沈 2026-06-12; 小健 2026-06-17 新增usage"""
        self.reset_cancel()
        self._ensure_client()

        retry_count = 0
        max_retries = LLM_STREAM_MAX_RETRIES
        stream_options = LLM_STREAM_OPTIONS

        # ======== 系统层HTTP请求重试（真正的重试逻辑）========
        # 同一个 LLM 调用（llm_call_count 不变），HTTP请求超时/断连时自动重新发送。
        # 与 Agent 层（react_cycle.py）的 RETRYING 机制无关，是两套独立机制。
        # Agent 层感知不到这里重试了几次。
        # retry_count=0,1,2,3 共4次机会，每次超时递增20s。
        while retry_count <= max_retries:
            effective_timeout = self.timeout + (retry_count + 1) * 20
            try:
                tool_call_accumulator = {}
                raw_data_buf: list = []
                usage_data = None
                _truncated = False  # #34 fix: 超时截断标记 — 小欧 2026-07-18
                tool_call_streaming_start = None
                deadline = time.monotonic() + STREAM_TOTAL_TIMEOUT
                async for data_str in self._llm_sdk.request_stream(
                    messages=messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    seed=self.seed,
                    stream_options=stream_options,
                    request_timeout=effective_timeout,
                    extra_body=self.extra_body_params,
                ):
                    if await self._check_stop():
                        yield create_cancelled_chunk(self.model)
                        return

                    # ② 总时长硬超时 — 2026-07-16 小欧
                    # httpx read timeout 是空闲超时(两字节间隙), 非总时长。
                    # LLM 持续流式返回 tool_call delta 时字节不断到达, read timeout 永不触发。
                    # 此处用 wall-clock deadline 做总时长保护, 超时 break→accumulator→截断修复。
                    if time.monotonic() > deadline:
                        logger.warning(f"[request_stream] 流调用总时长超时({STREAM_TOTAL_TIMEOUT}s), 截断已累积数据")
                        _truncated = True  # #34 fix — 小欧 2026-07-18
                        break

                    raw_data_buf.append(data_str)

                    usage_from_chunk = self._extract_usage(data_str)
                    if usage_from_chunk:
                        usage_data = usage_from_chunk

                    # 跨chunk聚合tool_calls — FC-only: 含id — 小沈 2026-06-11
                    # #7 fix 回归修正(小欧 2026-07-18): OpenAI 流式协议里单个 tool_call 以「稳定 index」跨多个 delta 续传,
                    #   首 delta 带 name, 后续 delta 仅带 arguments(无 name)。须按 index【合并】进同一槽位,
                    #   原 #7 误把"arguments-only 续传"当"并行碰撞"而自增新槽位, 致 name 与 arguments 撕裂→解析失败→FC降级。
                    #   并行碰撞(#7原意)已由 _extract_tool_calls 的 index 字典去重, 此处直接合并即可, 不再自增。
                    tc_data = self._extract_tool_calls(data_str)
                    for idx, entry in tc_data.items():
                        if idx not in tool_call_accumulator:
                            tool_call_accumulator[idx] = {"id": None, "name": "", "arguments": ""}
                        _tc_id = entry.get("id")
                        _tc_name = entry.get("name")
                        _tc_args = entry.get("arguments")
                        if _tc_id:
                            tool_call_accumulator[idx]["id"] = _tc_id
                        if _tc_name:
                            tool_call_accumulator[idx]["name"] = _tc_name
                        if _tc_args:
                            tool_call_accumulator[idx]["arguments"] += _tc_args
                        # #32 修正(小欧 2026-07-18): 仅当整个 delta 完全为空(协议残余)才告警;
                        #   正常的参数续传(arguments-only, 无 name)属预期行为, 不再刷屏 warning。
                        if not (_tc_id or _tc_name or _tc_args):
                            logger.warning(f"[BaseAIService] 收到完全为空的 tool_call delta, 跳过: idx={idx}, entry={entry}")

                    # ③ tool_call流式超时（总时长的3/5）— 2026-07-16 小欧
                    # 工具参数(如 writetext content)可能极长(>10万字符), LLM 生成期间
                    # _parse_sse_data 对 tool_call delta 返回 None(静默跳过), Console 无输出。
                    # 此超时专卡 tool_call 参数流式阶段, 不误伤普通文本回答。
                    # 首次检测到 tool_call delta 时开始计时, 超时 break→accumulator→截断修复。
                    if tc_data and tool_call_streaming_start is None:
                        tool_call_streaming_start = time.monotonic()
                    if tool_call_streaming_start and (time.monotonic() - tool_call_streaming_start) > STREAM_TOTAL_TIMEOUT * 3 // 5:
                        logger.warning(f"[request_stream] tool_call参数流式已持续{time.monotonic()-tool_call_streaming_start:.0f}s, 强制截断")
                        break

                    for chunk in self._parse_sse_data(data_str):  # #35 fix: generator — 小欧 2026-07-18
                        if chunk:
                            yield chunk

                # 流结束后，如有聚合的tool_calls，原生结构一次性yield — 小沈 2026-06-12
                complete_raw = "\n".join(raw_data_buf)
                # #38 fix: 过滤掉只有id无name的幽灵tool_call delta（LLM流式协议残余，非真实工具调用）— 小欧 2026-07-18
                tool_call_accumulator = {k: v for k, v in tool_call_accumulator.items() if v.get("name")}
                if tool_call_accumulator:
                    tool_calls_list = []
                    failed_parses = []  # 小欧 2026-06-25 收集解析失败的tool_call
                    for idx in sorted(tool_call_accumulator):
                        tc = tool_call_accumulator[idx]
                        if tc["name"]:
                            try:
                                args_str = tc["arguments"].strip() if tc["arguments"] else ""
                                if not args_str:
                                    failed_parses.append(tc["name"])
                                    continue
                                else:
                                    params = _normalize_tool_params(_json.loads(args_str))
                            except _json.JSONDecodeError as e:
                                logger.warning(f"[request_stream] tool_call '{tc['name']}' 参数JSON解析失败: {str(e)[:100]}, arguments前100字符: {args_str[:100]}")
                                fixed_params = _try_fix_incomplete_json(args_str)
                                if fixed_params is not None:
                                    logger.warning(f"[request_stream] 参数截断修复: tool_call '{tc['name']}' 参数JSON不完整, 已自动修复为 {_json.dumps(fixed_params, ensure_ascii=False)}")
                                    params = _normalize_tool_params(fixed_params)
                                    tc["_repair_warning"] = f"[Warning: LLM返回的'{tc['name']}' tool_call参数不完整(截断位置: {args_str[:20]}...),已自动修复为 {_json.dumps(params, ensure_ascii=False)}]"
                                else:
                                    failed_parses.append(tc["name"])
                                    continue
                            tool_calls_list.append({
                                "tool_name": tc["name"],
                                "tool_params": params,
                                "tool_call_id": tc.get("id"),
                                "_repair_warning": tc.get("_repair_warning", ""),
                                "tool_calls": [{
                                    "id": tc.get("id"),
                                    "type": "function",
                                    "function": {
                                        "name": tc["name"],
                                        # 落库 arguments 统一用已解析规范化后的 params(json.dumps), 而非原始流式串 —
                                        # 流式超时截断时原始串为非完整JSON, 落库后下一轮回传会触发LLM API参数校验失败; 以已解析/已修补的合法dict为准, 保证历史合法且工具结果保留 — 小欧 2026-07-17
                                        "arguments": _json.dumps(params, ensure_ascii=False)
                                    }
                                }]
                            })
                    # 小欧 2026-06-25: 所有tool_calls都解析失败 → LLMResponseError
                    if tool_call_accumulator and not tool_calls_list:
                        raise LLMResponseError(
                            message="所有tool_calls参数解析失败",
                            details={"failed_parses": failed_parses}
                        )
                    yield StreamChunk(content="", model=self.model, is_done=False,
                                      tool_calls=tool_calls_list, raw_data=complete_raw)

                yield StreamChunk(content="", model=self.model, is_done=True, raw_data=complete_raw, usage=usage_data, truncated=_truncated)  # #34 fix — 小欧 2026-07-18
                return

            except LLMResponseError:
                raise  # 穿透给call_llm_with_fallback重试/降级 — 2026-06-26
            except Exception as e:
                if self._should_retry(e) and retry_count < max_retries:
                    retry_count += 1
                    wait_time = 2 ** retry_count
                    logger.warning(f"[Retry][L1] 重试 {retry_count}/{max_retries}, 等待{wait_time}秒, 错误: [{type(e).__name__}] {e}")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # 检出 429 重试耗尽 → 明确"配额/限流"提示, 非泛化"服务器错误" — 小欧 2026-07-17
                    if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 429:
                        yield StreamChunk(
                            content="", model=self.model, is_done=True,
                            stream_error="API配额/速率限制已耗尽(rpm exhausted)，请稍后重试或升级配额",
                            stream_error_type="quota_exceeded",
                        )
                        return
                    yield self._create_stream_error_chunk(e)
                    return


    def _extract_tool_calls(self, data_str: str) -> Dict[int, Dict]:
        """从SSE delta中提取tool_calls增量 — FC-only: 含id捕获 — 小沈 2026-06-11"""
        try:
            data = parse_json(data_str)
            if not data:
                return {}
            choices = data.get("choices", [])
            if not choices:
                return {}
            delta = choices[0].get("delta", {})
            raw_tool_calls = delta.get("tool_calls", [])
            if not raw_tool_calls:
                return {}
            result = {}
            for tc in raw_tool_calls:
                idx = tc.get("index", 0)
                entry = {}
                if tc.get("id"):
                    entry["id"] = tc["id"]
                func = tc.get("function", {})
                if func.get("name"):
                    entry["name"] = func["name"]
                if func.get("arguments"):
                    entry["arguments"] = func["arguments"]
                if entry:
                    result[idx] = entry
            return result
        except Exception as e:
            logger.warning(f"[BaseAIService] _extract_tool_calls异常: {e}")
            return {}

    def _extract_usage(self, data_str: str) -> Optional[Dict]:
        """从SSE data中提取usage(token用量) — 小健 2026-06-17"""
        try:
            data = parse_json(data_str)
            if not data:
                return None
            usage = data.get("usage")
            if usage and isinstance(usage, dict):
                return usage
            return None
        except Exception as e:
            logger.warning(f"[BaseAIService] _extract_usage异常: {e}")
            return None

    def _parse_sse_data(self, data_str: str):  # → Generator[StreamChunk, None, None] — #35 fix
        """解析 SSE data 行, yield StreamChunk — 2026-06-12 小沈 FC-only: tool_calls原生传递
        小沈 2026-06-14 新增tool_calls_delta逻辑
        小欧 2026-07-10 M-17: usage兼容纯字符串
        2026-07-14 小欧 补充捕获IndexError(空choices安全异常)
        #35 fix: reasoning+content 同 chunk 各 yield 一帧, 不再因 reasoning 存在而丢弃 content — 小欧 2026-07-18"""
        try:
            data = parse_json(data_str)
            if data is None:
                return

            choices = data.get("choices", [])
            if not choices:
                return

            delta = choices[0].get("delta", {})
            content = delta.get("content", "") or ""
            reasoning_text = extract_reasoning_from_chunk(delta) or ""

            if reasoning_text:
                yield StreamChunk(content=reasoning_text, model=self.model, is_done=False, is_reasoning=True, raw_data=data_str)
            if content:
                yield StreamChunk(content=content, model=self.model, is_done=False, is_reasoning=False, raw_data=data_str)
            if not reasoning_text and not content:
                tool_calls_delta = delta.get("tool_calls", [])
                if not tool_calls_delta:
                    return
                # tool_calls delta 处理顺延至外层
                yield None
        except (json.JSONDecodeError, AttributeError, IndexError) as e:
            logger.warning(f"[_parse_sse_data] 解析异常: {e}")
            return

            choices = data.get("choices", [])
            if not choices:
                return None

            delta = choices[0].get("delta", {})
            content = delta.get("content", "") or ""
            # 这条消息是不是"思考"及多模型识别规则，统一见 reasoning.py 模块注释 — 小欧 2026-07-12
            reasoning_text = extract_reasoning_from_chunk(delta) or ""

            # 是思考 → 存进"思考区"；不是 → 存进"答案区"（详见 reasoning.py 第三节）
            if reasoning_text:
                return StreamChunk(content=reasoning_text, model=self.model, is_done=False, is_reasoning=True, raw_data=data_str)

            if content:
                return StreamChunk(content=content, model=self.model, is_done=False, is_reasoning=False, raw_data=data_str)

            # tool_calls delta — _extract_tool_calls 已处理,跳过冗余空 chunk — 小沈 2026-06-14
            tool_calls_delta = delta.get("tool_calls", [])
            if tool_calls_delta:
                return None

            return None

        except Exception as e:
            logger.debug(f"[_parse_sse_data] 解析失败: {e}, data={data_str[:100]}")
            return None

    def _should_retry(self, e: Exception) -> bool:
        """判断是否应该重试 — 委托给SystemErrorClassifier - 小沈 2026-06-17"""
        return SystemErrorClassifier.classify_error(e).is_retryable

    async def close(self):
        if self._llm_sdk:
            await self._llm_sdk.close()


__all__ = ["BaseAIService", "ChatResponse", "StreamChunk"]
