# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-14 - 小欧 - 删除死代码_is_rate_limit_status，集中LLM_*/FC_*/TOOL_CACHE_TTL至app.constants
# 2026-07-16 - 小欧 - 新增三层防线：LLM_MAX_TOKENS/STREAM_TOTAL_TIMEOUT/tool_call流式超时
# 2026-07-17 - 小沈 - FC重命名: FCFormatError→LLMResponseError
# 2026-07-17 - 小欧 - 流式截断落库修复: tool_call.arguments改用已解析规范化后的params
# 2026-07-17 - 小欧 - 429配额耗尽增强: 明确"配额/限流耗尽"提示
# 2026-07-18 - 小欧 - #7 fix: 并行tool_calls累加器遇重复idx自增去重
# 2026-07-18 - 小欧 - #32 fix: 空name tool_call delta加warning日志
# 2026-07-18 - 小欧 - #34 fix: StreamChunk.truncated字段;超时截断时标记
# 2026-07-18 - 小欧 - #35 fix: _parse_sse_data改为generator，同chunk各yield一帧
# 2026-07-18 - 小欧 - #7 fix: 并行tool_calls累加器遇重复idx时自增去重
# 2026-07-18 - 小欧 - #38 fix: 流结束后过滤空name幽灵tool_call delta
# 2026-07-18 - 小欧 - #7回归修正: 改while自增为if not in直接合并
# 2026-07-19 - 小欧 - finish_reason字段提取/透传
# 2026-07-23 - 小欧 - #7三堂会审修复: 变量名/死代码/日志级别/非JSON行yield
# 2026-07-26 - 小欧 - 默认开启thinking模式
# 2026-08-06 - 小欧 - 核查7/31未实现项[01]修复: 重试退避基数2→3(2/4/8→3/9/27秒), 与7/31声称功能对齐
# 2026-08-06 - 小欧 - 三堂会审修复: BUG-3 DEFAULT_EXTRA_BODY_PARAMS嵌套dict深拷贝防共享引用污染
# 2026-08-06 - 小欧 - thinking配置增强(老陈审核后修复): ①默认extra_body提常量DEFAULT_EXTRA_BODY_PARAMS; ②config的model_params由整体替换改为合并(深合并chat_template_kwargs层), 保证enable_thinking:True兜底, 配thinking_budget等不再静默关闭思考
# 2026-08-11 - 小欧 - task006方案1落地: 429限流重试优先尊重服务端Retry-After头(秒), 未提供才用指数退避3^n; 避免LLM限流后仍按固定退避撞限流窗口, 增强限流场景恢复效率(不新增重试次数, 不触碰配额耗尽提示)
# 2026-08-13 - 小欧 - 三堂会审修复#30: Retry-After仅支持整数秒, "1.5"/HTTP-date静默回落指数退避
#   【病根】原 `if _ra and _ra.strip().isdigit():` 仅解析整数秒, RFC 7231允许整数/浮点秒与HTTP-date, 违背"尊重服务端Retry-After提示"意图
#   【改法】整数/浮点秒取max(int(float(_ra)),1); 否则尝试email.utils.parsedate_to_datetime解析HTTP-date(距当前秒数), 解析失败静默回落指数退避; time模块已有顶层导入
# 2026-08-13 - 小欧 - 三堂会审复核#30修复方法(老陈要求): HTTP-date分支time.mktime(_dt.timetuple())丢弃时区,
#   按本地时区解释UTC字段→东八区偏移8小时, 实测Retry-After正确3600秒被clamp成1秒(限流后狂重试);
#   改_dt.timestamp()(aware datetime直接给UTC epoch)与time.time()相减, 时区无关
# 2026-08-14 - 小欧 - llm 独立为 app 顶层能力层目录(services/llm→app/llm), 本文件 import 路径同步
# 2026-08-22 - 小欧 - model结构化归一报告v1.25 6.4: __init__ (model/api_base/provider 三参)→ llm_model: ModelRef
#   单结构承载(F8 不留 self.model/self.provider/self.api_base 兼容别名); 内部16处自用点随改读 self.llm_model.*;
#   ChatResponse/StreamChunk 构造传参同步归一(chat_model/chunk_model)
# 2026-08-23 - 小欧 - 三轮三堂会审修复(P1): 新增 reset_sdk()——L2 会话级整体换模后 _ensure_client 的 SDK 缓存
#   仍绑旧 api_base/model, 不重置则"记录身份与实际 HTTP 连接不一致"(编排层换模/还原两处已随调)
# 2026-08-23 - 小欧 - 修复回归bug(P0): _ensure_client 调 create_llm_client 仍传 provider/model 旧签名,
#   致 create_llm_client() got an unexpected keyword argument 'provider' TypeError(93dc95bc4 提交漏改此调用点);
#   改为传 llm_model=self.llm_model(ModelRef), base_url 由 LLMClient.__init__ 从 llm_model.api_base 派生
# 2026-08-23 - 小欧 - 落盘文件A/B 实施(文档[1]11.8.2 D0/11.9 P3): request_stream 工具调用聚合处
#   tool_calls_list 条目加 params_raw_str=args_str(:309 原始 arguments 串)——文件A③「LLM 原始参数」权威源,
#   无论是否走截断修复分支 raw 都以它为准; 下游经 llm_stream D0b/_build_call_list D3b 两跳透传至落盘闭包
# 2026-09-01 - 小欧 - L2 会话级切跨 provider 模型修复: snapshot 增可选 api_key/extra_body_params/context_limit
#   三参注入——L2 覆盖 provider(如 sensenova) 时, 快照必须携带"目标 provider"的 api_base/api_key/model_params,
#   否则沿用全局默认 provider(agnes) 会走错端点、用错 key、丢 reasoning_effort/context_limit(503/AgnesAI_error
#   病根)。三参缺省 None 时回退 self, 快照不重复合并(个性参数权威合并仍由 __init__ 兜底 enable_thinking:True)
"""
LLM 核心模块 — BaseAIService

重构: 删除mixin继承, 统一为request/request_stream/chat + mode参数 - 小沈 2026-06-09
FC-only: tool_calls原生yield,不走JSON roundtrip - 小沈 2026-06-12
清理: 删除死代码_is_rate_limit_status(无调用方,限流由SystemErrorClassifier覆盖) - 小欧 2026-07-14
"""

import asyncio
import time
import json as _json
from typing import List, Dict, Optional, AsyncGenerator, Any, Callable

import httpx
from app.logger import logger
from app.utils.json_utils import parse_json, _try_fix_incomplete_json, _normalize_tool_params
from app.db.models.chat_models import ModelRef   # 归一: 模型身份唯一结构 — 小欧 2026-08-22
from app.llm.core import ChatResponse, LLMResponseError, StreamChunk, _resolve_exception
# 注: LLM_*/FC_*/TOOL_CACHE_TTL 已集中迁移至 app.constants(2026-07-14 小欧)
from app.llm.core import create_cancelled_chunk
from app.llm.client_sdk import create_llm_client
from app.llm.reasoning import extract_reasoning_from_chunk, extract_reasoning_from_message
from app.llm.error_classifier import SystemErrorClassifier

from app.constants import DEFAULT_READ_TIMEOUT, LLM_TEMPERATURE, LLM_STREAM_MAX_RETRIES, LLM_STREAM_OPTIONS, STREAM_TOTAL_TIMEOUT, LLM_MAX_TOKENS

# 默认extra_body: 开启thinking模式; 配置文件model_params可覆盖/扩展, 合并策略见__init__ — 小欧 2026-08-06
DEFAULT_EXTRA_BODY_PARAMS: Dict = {"chat_template_kwargs": {"enable_thinking": True}}


class BaseAIService:
    """通用AI服务 — request/request_stream/chat — FC-only重构 2026-06-11 小沈"""

    def __init__(
        self,
        api_key: str,
        llm_model: ModelRef,
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
        self.llm_model = llm_model   # 归一唯一模型身份结构(provider+model+api_base) — 小欧 2026-08-22
        self.max_tokens = max_tokens if max_tokens is not None else LLM_MAX_TOKENS
        self.temperature = temperature
        self.seed = seed
        # 默认开启 thinking 模式；配置文件传参可覆盖（如 chat_template_kwargs.enable_thinking: false 可关）— 小欧 2026-07-26
        # 2026-08-06 小欧 合并而非替换: 顶层键用户覆盖优先, chat_template_kwargs 层深合并保 enable_thinking:True 兜底
        # 2026-08-06 小欧 BUG-3修复: 嵌套dict深拷贝, 避免与全局常量共享引用污染后续实例
        merged_params = {"chat_template_kwargs": dict(DEFAULT_EXTRA_BODY_PARAMS["chat_template_kwargs"])}
        if extra_body_params:
            merged_params.update(extra_body_params)
            default_ctk = DEFAULT_EXTRA_BODY_PARAMS.get("chat_template_kwargs", {})
            user_ctk = extra_body_params.get("chat_template_kwargs")
            if isinstance(user_ctk, dict) and default_ctk:
                merged_params["chat_template_kwargs"] = {**default_ctk, **user_ctk}
        self.extra_body_params = merged_params
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
            # 归一(小欧 2026-08-23): create_llm_client 入参已改 llm_model: ModelRef,
            # 不再接受 provider/model 拆包; base_url 由 LLMClient.__init__ 从 llm_model.api_base 派生
            self._llm_sdk = create_llm_client(
                llm_model=self.llm_model,
                api_key=self.api_key,
                timeout=self.timeout,
            )

    def reset_sdk(self):
        """重置底层 SDK 缓存 — L2 会话级换模(整体替换 llm_model, 可能变更 api_base)后必须调用:
        _ensure_client 只在首次创建 SDK 时读取 llm_model, 不重置则新 api_base/model 不生效,
        造成"记录身份与实际 HTTP 连接不一致" — 三堂会审 P1 修复 小欧 2026-08-22"""
        self._llm_sdk = None

    def snapshot(self, model_ref: Optional[ModelRef] = None,
                 api_key: Optional[str] = None,
                 extra_body_params: Optional[Dict] = None,
                 context_limit: Optional[int] = None) -> "BaseAIService":
        """构造本实例的独立副本(携带 model_ref 或当前模型), 与进程级共享单例解耦 — 小沈 2026-08-29
        病根修复: sessionModel 覆盖此前直接改进程单例 llm_model + reset_sdk(全局副作用), 单例还原时序竞态
        导致"断连时后台任务误用旧模型"与"后续无覆盖会话串用错误模型"两类退化。改为后台任务/会话持有自身
        模型快照, 共享单例恒定全局默认不再被污染, 彻底根除该竞态。返回实例带 _is_snapshot 标记,
        供 run_agent_in_background 结束后释放其 httpx 连接池。
        L2 切跨 provider 模型(2026-09-01 小欧): 快照必须携带"目标 provider"的 api_key 与
        个性参数(model_params/context_limit), 否则沿用全局默认 provider(agnes) 会走错端点、
        用错 key、丢 reasoning_effort/context_limit(api_base/api_key/model_params 缺一不可)。
        extra_body_params 由 __init__ 权威合并(顶层键用户优先, chat_template_kwargs 深合并,
        保 enable_thinking:True 兜底), 此处仅直传不重复合并(DRY+KISS-DIRECT)。"""
        snap = BaseAIService(
            api_key=api_key or self.api_key,
            llm_model=model_ref if model_ref is not None else self.llm_model,
            timeout=self.timeout,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            seed=self.seed,
            extra_body_params=extra_body_params
            if extra_body_params is not None else self.extra_body_params,
            context_limit=context_limit
            if context_limit is not None else self.context_limit,
        )
        snap._is_snapshot = True
        logger.info(f"[BaseAIService.snapshot] 构造独立客户端快照: model={snap.llm_model.model}, provider={snap.llm_model.provider}")
        return snap

    async def cancel(self):
        logger.info(f"[BaseAIService.cancel] 正在强制取消请求, model={self.llm_model.model}")
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
        return StreamChunk(content="", chunk_model=self.llm_model, is_done=True, stream_error=msg, stream_error_type=err_type)

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
                return ChatResponse(content="", chat_model=self.llm_model, error="无响应")

            msg = choices[0].get("message", {})
            content = msg.get("content", "") or ""
            tool_calls = msg.get("tool_calls", [])

            reasoning = extract_reasoning_from_message(msg) or ""

            return ChatResponse(
                content=content,
                chat_model=self.llm_model,
                tool_calls=tool_calls,
                reasoning=reasoning,
            )
        except Exception as e:
            return ChatResponse(content="", chat_model=self.llm_model, error=str(e))

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
                finish_reason = None  # 2026-07-19 小欧 新增: SSE最后chunk的finish_reason
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
                        yield create_cancelled_chunk(self.llm_model)
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

                    fr_from_chunk = self._extract_finish_reason(data_str)  # 2026-07-19 小欧
                    if fr_from_chunk:
                        finish_reason = fr_from_chunk

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
                                "params_raw_str": args_str,      # LLM 原始 arguments 串(文档[1]11.8.2 D0/文件A③) — 小欧 2026-08-23
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
                    yield StreamChunk(content="", chunk_model=self.llm_model, is_done=False,
                                      tool_calls=tool_calls_list, raw_data=complete_raw)

                yield StreamChunk(content="", chunk_model=self.llm_model, is_done=True, raw_data=complete_raw, usage=usage_data, truncated=_truncated, finish_reason=finish_reason)  # #34 fix — 小欧 2026-07-18; finish_reason — 2026-07-19 小欧
                return

            except LLMResponseError:
                raise  # 穿透给call_llm_with_fallback重试/降级 — 2026-06-26
            except Exception as e:
                if self._should_retry(e) and retry_count < max_retries:
                    retry_count += 1
                    # 429限流: 优先尊重服务端Retry-After头(秒), 未提供才用指数退避 — 小欧 2026-08-11
                    wait_time = 3 ** retry_count
                    if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 429:
                        _ra = e.response.headers.get("Retry-After")
                        if _ra:
                            _ra = _ra.strip()
                            # 2026-08-13 小欧 三堂会审修复#30: RFC 7231允许整数/浮点秒与HTTP-date, 原仅isdigit整数秒("1.5"/日期静默回落指数退避)
                            if _ra.replace(".", "", 1).isdigit():
                                wait_time = max(int(float(_ra)), 1)
                            else:
                                try:
                                    import email.utils as _eu
                                    _dt = _eu.parsedate_to_datetime(_ra)
                                    # 2026-08-13 小欧 三堂会审复核#30修复方法: mktime(timetuple())丢弃时区→东八区偏移8h(实测3600→1秒);
                                    #   改 _dt.timestamp()(aware→UTC epoch)与 time.time() 直接相减, 时区无关
                                    wait_time = max(int(_dt.timestamp() - time.time()), 1)
                                except Exception:
                                    pass
                    logger.warning(f"[Retry][L1] 重试 {retry_count}/{max_retries}, 等待{wait_time}秒, 错误: [{type(e).__name__}] {e}")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # 检出 429 重试耗尽 → 明确"配额/限流"提示, 非泛化"服务器错误" — 小欧 2026-07-17
                    if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 429:
                        yield StreamChunk(
                            content="", chunk_model=self.llm_model, is_done=True,
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
            # #7: 降级为DEBUG(异常时返回{},外层逻辑跳过tool_calls) — 三堂会审 小欧 2026-07-23
            logger.debug(f"[BaseAIService] _extract_tool_calls异常: {e}")
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
            # #7: 降级为DEBUG(异常时返回None,不影响主流程) — 三堂会审 小欧 2026-07-23
            logger.debug(f"[BaseAIService] _extract_usage异常: {e}")
            return None

    def _extract_finish_reason(self, data_str: str) -> Optional[str]:
        """从SSE data中提取finish_reason(stop/length/tool_calls/content_filter) — 小欧 2026-07-19"""
        try:
            data = parse_json(data_str)
            if not data:
                return None
            choices = data.get("choices", [])
            if not choices or not isinstance(choices, list):
                return None
            fr = choices[0].get("finish_reason")
            if fr and isinstance(fr, str) and fr.strip():
                return fr.strip()
            return None
        except Exception as e:
            logger.debug(f"[BaseAIService] _extract_finish_reason异常: {e}")
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
                # #7: 非JSON行(LLM非标准回复)尝试作为纯文本yield,防内容静默丢失 — 三堂会审 小欧 2026-07-23
                if data_str and data_str.strip():
                    yield StreamChunk(content=data_str.strip(), chunk_model=self.llm_model, is_done=False, raw_data=data_str)
                return

            choices = data.get("choices", [])
            if not choices:
                return

            delta = choices[0].get("delta", {})
            content = delta.get("content", "") or ""
            reasoning_text = extract_reasoning_from_chunk(delta) or ""

            if reasoning_text:
                yield StreamChunk(content=reasoning_text, chunk_model=self.llm_model, is_done=False, is_reasoning=True, raw_data=data_str)
            if content:
                yield StreamChunk(content=content, chunk_model=self.llm_model, is_done=False, is_reasoning=False, raw_data=data_str)
            if not reasoning_text and not content:
                tool_calls_delta = delta.get("tool_calls", [])
                if not tool_calls_delta:
                    return
                # tool_calls delta 处理顺延至外层
                yield None
        except (_json.JSONDecodeError, AttributeError, IndexError) as e:
            # #7: 降级为DEBUG(parse_json已内部消化JSONDecodeError,异常路径有 None/{} fallback) — 三堂会审 小欧 2026-07-23
            logger.debug(f"[_parse_sse_data] 解析异常: {e}")
            return

    def _should_retry(self, e: Exception) -> bool:
        """判断是否应该重试 — 委托给SystemErrorClassifier - 小沈 2026-06-17"""
        return SystemErrorClassifier.classify_error(e).is_retryable

    async def close(self):
        if self._llm_sdk:
            await self._llm_sdk.close()


__all__ = ["BaseAIService", "ChatResponse", "StreamChunk"]
