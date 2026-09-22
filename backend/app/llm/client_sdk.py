
"""
LLM 客户端 SDK
Author: 小沈 - 2026-05-29

基础模块,被 BaseAIService 调用。
只支持 OpenAI 兼容格式的 API(/chat/completions 端点)。
SDK 只管发 HTTP 请求,不处理错误,异常原样抛出。

FC-only重构: 删除mode参数, tools不为None时始终注入 — 小沈 2026-06-11
编辑历史: 2026-07-16 小欧 request_stream 响应错误路径: >=400时记录响应体后raise_for_status(所有4xx/5xx可见错误原因)
编辑历史: 2026-07-16 小欧 M1 解决400错误根因不可见问题: 此前>=400仅把响应体写进服务器日志, 前端/用户只看到泛化文案"客户端错误:请求参数异常", 排障须翻数MB日志; 新增_extract_server_error_message解析OpenAI兼容错误信封{"error":{"message":...}}, >=400时抛HTTPStatusError并携带服务商真实错误文本(server_msg)。能力提升: 前端用户与错误记录可直接看到sensenova等真实错误原因(如参数被拒), 无需查日志即可定位根因
编辑历史: 2026-07-17 小欧 修复429/5xx限流日志污染: 可重试状态(429/5xx)由base_service L1重试处理, 降为WARNING; 仅不可重试客户端错误(400/401/403)记ERROR, 避免check_logs/测试误判FAIL
编辑历史: 2026-07-18 小欧 #33 fix: 兼容data:无空格格式
编辑历史: 2026-07-18 小欧 #37 fix: request新增request_timeout形参并传httpx.Timeout
编辑历史: 2026-07-28 小欧 BUG#1: 非流式请求必崩(AttributeError: _default_timeout undefined)。__init__ 漏存 self._default_timeout = read_timeout, request() 引用时崩溃。新增存储。
编辑历史: 2026-08-22 小欧 model结构化归一报告v1.25 6.4: LLMClient 构造 (provider, model) 分离入参 → llm_model: ModelRef
  单结构; base_url 取 llm_model.api_base(缺省回退 _default_base_url(llm_model.provider)); 请求体拼
  self.llm_model.model 属裸单值调API场景(设计要求4允许并注释)
编辑历史: 2026-08-23 小欧 三堂会审复核加固(P2): _base_url 回退链补 provider or "openai" 兜底——
  防空 provider 时 _DEFAULT_URLS.get("","") 返回空串致 httpx base_url 为空(防御性语义与归一前对齐, 不弱化)
编辑历史: 2026-09-20 小欧 P5+C-1: ①P5(13.6) LLM软配额信号量(_soft_pool_semaphore, asyncio.Semaphore 惰性初始化,
  排队超时保底放行, request_stream 入口自动获取/finally释放); ②C-1(RED-C-1) 新增 _current_response 追踪
  在飞流式HTTP响应(request_stream 进入置位/finally清空) + cancel() 方法 aclose 强关在飞流
  ——BaseAIService.cancel 优先委托此处直达HTTP层(原来 cancel 关闭的 _current_response 恒 None 假日志)
编辑历史: 2026-09-20 小欧 三堂会审BUG-04修复: cancel()中aclose后立即清_current_response引用, 防finally/__aexit__二次关闭(double-close)
编辑历史: 2026-09-22 小欧 - [61] constants.py 配置化迁移：import 改别名 + soft_pool_wait_timeout/max_connections/max_keepalive 改读 tuning 配置
编辑历史: 2026-09-23 小欧 - [64] LLM补充采样参数: _build_request_body/request/request_stream 签名加 top_p/frequency_penalty/presence_penalty 三参(仿 seed None透传写法)
"""

import asyncio  # 2026-09-20 小欧 P5: 软配额信号量 — 小欧-2026-09-20
import httpx
import json
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.constants import (
    DEFAULT_CONNECT_TIMEOUT as _D_CONNECT_TIMEOUT,
    DEFAULT_READ_TIMEOUT as _D_READ_TIMEOUT,
    DEFAULT_WRITE_TIMEOUT as _D_WRITE_TIMEOUT,
    DEFAULT_POOL_TIMEOUT as _D_POOL_TIMEOUT,
    LLM_MAX_CONNECTIONS as _D_MAX_CONNECTIONS,
    LLM_MAX_KEEPALIVE as _D_MAX_KEEPALIVE,
)
from app.config import get_config
from app.db.models.chat_models import ModelRef   # 归一: 模型身份唯一结构 — 小欧 2026-08-22
from app.logger import logger

# 可重试 HTTP 状态: 429限流 / 5xx服务端瞬时错误, 由 base_service L1 重试处理 — 小欧 2026-07-17
_RETRYABLE_STATUS = (429, 500, 502, 503, 504)


def _build_request_body(
    messages: List[Dict],
    model: str,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,  # 新增 — 小欧 2026-09-23
    frequency_penalty: Optional[float] = None,  # 新增 — 小欧 2026-09-23
    presence_penalty: Optional[float] = None,  # 新增 — 小欧 2026-09-23
    seed: Optional[int] = None,
    tools: Optional[List[Dict]] = None,
    tool_choice: Optional[str] = None,
    stream: bool = False,
    parallel_tool_calls: Optional[bool] = None,
    stream_options: Optional[Dict] = None,
    extra_body: Optional[Dict] = None,
) -> Dict:
    """统一构建 LLM 请求体 — FC-only: 无mode参数 — 小沈 2026-06-11; 小沈 2026-06-17 新增parallel_tool_calls; 小健 2026-06-17 新增stream_options; 小欧 2026-07-09 新增extra_body"""
    body = {"model": model, "messages": messages}
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    if temperature is not None:
        body["temperature"] = temperature
    if seed is not None:
        body["seed"] = seed
    # ✅ 仿 seed 现写法：None 即不拼（旁路），有值才拼 — 小欧 2026-09-23
    if top_p is not None:
        body["top_p"] = top_p
    if frequency_penalty is not None:
        body["frequency_penalty"] = frequency_penalty
    if presence_penalty is not None:
        body["presence_penalty"] = presence_penalty
    if stream:
        body["stream"] = True
        if stream_options is not None:
            body["stream_options"] = stream_options
    if tools:
        body["tools"] = tools
        if tool_choice:
            body["tool_choice"] = tool_choice
        
        if parallel_tool_calls is None:
            parallel_tool_calls = True  # 执行层(action_handler)的_has_conflict控制并发安全 — 北京老陈 2026-07-04
        
        body["parallel_tool_calls"] = parallel_tool_calls
    
    if extra_body:
        body.update(extra_body)
    
    return body


def _extract_server_error_message(body_text: str) -> str:
    """从LLM服务商错误响应体提取真实错误(OpenAI兼容信封 {"error":{"message":...}}) — 小欧 2026-07-16"""
    if not body_text:
        return ""
    try:
        data = json.loads(body_text)
        err = data.get("error") if isinstance(data, dict) else None
        if isinstance(err, dict):
            msg = err.get("message")
            if msg:
                return str(msg)[:500]
        if isinstance(err, str):
            return err[:500]
    except (ValueError, TypeError):
        pass
    return body_text[:500]


_soft_pool_semaphore = None  # 2026-09-20 小欧 P5: 延迟初始化, 绑定首次使用时的 event loop — 小欧-2026-09-20
_SOFT_POOL_WAIT_TIMEOUT = get_config().get("tuning.concurrency.soft_pool_wait_timeout", 30.0)  # 软配额排队等待上限(秒): 超时保底放行(不拒绝不降级) — 小欧-2026-09-20


def _get_soft_pool_semaphore():
    """惰性获取软配额信号量(避免模块级创建绑定错误 loop) — 小欧 2026-09-20"""
    global _soft_pool_semaphore
    if _soft_pool_semaphore is None:
        _soft_pool_semaphore = asyncio.Semaphore(get_config().get("tuning.llm_net.max_connections", _D_MAX_CONNECTIONS))
    return _soft_pool_semaphore


class LLMClient:
    """LLM 客户端实例 - 小沈 2026-06-09
    2026-08-22 小欧 归一报告v1.25 6.4: (provider, model) 分离入参 → llm_model: ModelRef 单结构
    (F8 不留 self.model/self.provider 兼容别名); 请求体拼 model 单值属裸单值场景(设计要求4允许)"""

    def __init__(
        self,
        llm_model: ModelRef,
        api_key: str,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        shared_client: Optional[httpx.AsyncClient] = None,  # 2026-09-20 小欧 C1: 共享连接池注入, 快照复用不 new — 小欧-2026-09-20
    ):
        self.llm_model = llm_model   # 前导+model 命名铁律 — 小欧 2026-08-22
        self._api_key = api_key
        # 三堂会审复核加固(小欧 2026-08-23): 保留原 provider or "openai" 兜底语义(防空 provider 时
        # _default_base_url 返回空串致 httpx base_url 为空; 当前可达路径虽恒非空, 防御不弱化)
        self._base_url = llm_model.api_base or self._default_base_url(llm_model.provider or "openai")

        read_timeout = float(timeout) if timeout else _D_READ_TIMEOUT
        self._default_timeout = read_timeout
        self._owns_client = shared_client is None   # 真连接池仅全局单例持有, 快照共享不重复建 — 小欧-2026-09-20
        self._current_response: Optional[httpx.Response] = None  # C-1(小欧 2026-09-20): 在飞流式HTTP响应, 供 cancel() 直达HTTP层强关 — 小欧-2026-09-20
        if shared_client is not None:
            self._client = shared_client
        else:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=_D_CONNECT_TIMEOUT,
                    read=read_timeout,
                    write=_D_WRITE_TIMEOUT,
                    pool=_D_POOL_TIMEOUT,
                ),
                limits=httpx.Limits(
                    max_connections=get_config().get("tuning.llm_net.max_connections", _D_MAX_CONNECTIONS),
                    max_keepalive_connections=get_config().get("tuning.llm_net.max_keepalive", _D_MAX_KEEPALIVE),
                ),
                headers={"Authorization": f"Bearer {api_key}"},
                base_url=self._base_url,
            )

    _DEFAULT_URLS = {
        "deepseek": "https://api.deepseek.com",
        "qwen": "https://dashscope.aliyuncs.com/compatible-mode",
        "ollama": "http://localhost:11434",
    }

    def _default_base_url(self, provider: str) -> str:
        """根据 provider 返回默认 API 地址 — 小健 2026-06-17 OCP: 优先配置,其次硬编码默认"""
        try:
            custom_urls = get_config().get("llm", {}).get("provider_urls", {})
            if provider in custom_urls:
                return custom_urls[provider]
        except Exception:
            logger.warning(f"[client_sdk] 读取自定义URL配置失败: provider={provider}")
        return self._DEFAULT_URLS.get(provider, "")

    async def request(
        self,
        messages: List[Dict],
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,  # 新增 — 小欧 2026-09-23
        frequency_penalty: Optional[float] = None,  # 新增 — 小欧 2026-09-23
        presence_penalty: Optional[float] = None,  # 新增 — 小欧 2026-09-23
        seed: Optional[int] = None,
        extra_body: Optional[Dict] = None,
        request_timeout: Optional[int] = None,  # #37 fix: per-request timeout — 小欧 2026-07-18
    ) -> Dict[str, Any]:
        """非流式请求 — FC-only: 无mode参数 — 小沈 2026-06-11; 小欧 2026-07-09 新增extra_body; #37 新增request_timeout"""
        body = _build_request_body(
            messages=messages, model=self.llm_model.model,   # 裸单值调API(设计要求4允许) — 小欧 2026-08-22
            max_tokens=max_tokens, temperature=temperature, top_p=top_p,  # 新增 — 小欧 2026-09-23
            frequency_penalty=frequency_penalty, presence_penalty=presence_penalty,  # 新增 — 小欧 2026-09-23
            seed=seed,
            tools=tools, tool_choice=tool_choice, stream=False,
            extra_body=extra_body,
        )
        _to = httpx.Timeout(request_timeout) if request_timeout else self._default_timeout
        # 软配额: 排队超时保底放行(非硬闸不 503 不降级, 防长时间卡等) — 小欧-2026-09-20
        _acquired = False
        _sem = _get_soft_pool_semaphore()
        try:
            await asyncio.wait_for(_sem.acquire(), timeout=_SOFT_POOL_WAIT_TIMEOUT)
            _acquired = True
        except asyncio.TimeoutError:
            logger.warning(f"[LLM] 软配额排队超{_SOFT_POOL_WAIT_TIMEOUT}s 保底放行")
        try:
            response = await self._client.post("/chat/completions", json=body, timeout=_to)
        finally:
            if _acquired:
                _sem.release()
        if response.status_code >= 400:
            body_text = response.text
            if response.status_code in _RETRYABLE_STATUS:
                logger.warning(f"[LLM] HTTP {response.status_code} 响应体(可重试, base_service将重试): {body_text}")
            else:
                logger.error(f"[LLM] HTTP {response.status_code} 响应体: {body_text}")
            server_msg = _extract_server_error_message(body_text)
            raise httpx.HTTPStatusError(
                f"HTTP {response.status_code} 错误: {server_msg or '（服务商未返回错误详情）'}",
                request=response.request, response=response)
        return response.json()

    async def request_stream(
        self,
        messages: List[Dict],
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,  # 新增 — 小欧 2026-09-23
        frequency_penalty: Optional[float] = None,  # 新增 — 小欧 2026-09-23
        presence_penalty: Optional[float] = None,  # 新增 — 小欧 2026-09-23
        seed: Optional[int] = None,
        stream_options: Optional[Dict] = None,
        request_timeout: Optional[int] = None,
        extra_body: Optional[Dict] = None,
    ) -> AsyncGenerator[str, None]:
        """流式请求 — FC-only: 无mode参数 — 小沈 2026-06-11; 小健 2026-06-17 新增stream_options; 小欧 2026-07-09 新增extra_body"""
        body = _build_request_body(
            messages=messages, model=self.llm_model.model,   # 裸单值调API(设计要求4允许) — 小欧 2026-08-22
            max_tokens=max_tokens, temperature=temperature, top_p=top_p,  # 新增 — 小欧 2026-09-23
            frequency_penalty=frequency_penalty, presence_penalty=presence_penalty,  # 新增 — 小欧 2026-09-23
            seed=seed,
            tools=tools, tool_choice=tool_choice, stream=True,
            stream_options=stream_options,
            extra_body=extra_body,
        )
        # 结构化超时: request_timeout 仅作用于 read 阶段, connect/write/pool 独立固定。
        # 避免浮点标量将四者全部拉长 (浮点标量 = 全阶段统一值, 会误将 connect 也拉长至 90+秒)。
        # request_timeout 由 base_service 传入 (provider.timeout + 重试递增),
        # 未显式传入时用 _D_READ_TIMEOUT 兜底 — 小欧 2026-07-13
        _timeout = httpx.Timeout(
            connect=_D_CONNECT_TIMEOUT,
            read=float(request_timeout) if request_timeout is not None else _D_READ_TIMEOUT,
            write=_D_WRITE_TIMEOUT,
            pool=_D_POOL_TIMEOUT,
        )
        _acquired = False
        _sem = _get_soft_pool_semaphore()
        try:
            await asyncio.wait_for(_sem.acquire(), timeout=_SOFT_POOL_WAIT_TIMEOUT)
            _acquired = True
        except asyncio.TimeoutError:
            logger.warning(f"[LLM] 软配额排队超{_SOFT_POOL_WAIT_TIMEOUT}s 保底放行")
        try:
            async with self._client.stream("POST", "/chat/completions", json=body, timeout=_timeout) as response:
                # C-1(小欧 2026-09-20): 记录在飞流式响应, BaseAIService 镜像后供 cancel() 直达HTTP层强关 — 小欧-2026-09-20
                self._current_response = response
                # 记录所有 4xx/5xx 错误响应体(>=400), 定位错误原因 — 小欧 2026-07-16
                # 2026-07-17 小欧 修复: 可重试状态(429限流/5xx服务端瞬时错误)由 base_service 的 L1 重试处理,
                #   降为 WARNING 避免污染 ERROR 日志(check_logs/测试据此误判 FAIL); 仅不可重试客户端错误(400/401/403等)记 ERROR
                if response.status_code >= 400:
                    response_body = await response.aread()
                    body_text = response_body.decode("utf-8", errors="replace")
                    if response.status_code in _RETRYABLE_STATUS:
                        logger.warning(f"[LLM] HTTP {response.status_code} 响应体(可重试, base_service将重试): {body_text}")
                    else:
                        logger.error(f"[LLM] HTTP {response.status_code} 响应体: {body_text}")
                    server_msg = _extract_server_error_message(body_text)
                    raise httpx.HTTPStatusError(
                        f"HTTP {response.status_code} 错误: {server_msg or '（服务商未返回错误详情）'}",
                        request=response.request, response=response)
                async for line in response.aiter_lines():
                    if line.startswith("data:"):  # #33 fix: 兼容无空格 data: — 小欧 2026-07-18
                        _body = line[len("data:"):].lstrip()
                        if _body.strip() == "[DONE]":
                            break
                        yield _body
        finally:
            # C-1(小欧 2026-09-20): 流结束/异常清在飞响应(镜像随流清), 防悬挂旧HTTP响应 — 小欧-2026-09-20
            self._current_response = None
            if _acquired:
                _sem.release()

    async def cancel(self):
        """强制取消在飞流式请求 — C-1(小欧 2026-09-20): 直达HTTP层关闭流式响应, 供 BaseAIService.cancel 委托。
        RED-C-1 根因: 此前 cancel() 关闭的 _current_response 恒 None(从未赋值), 取消只能等 chunk 级轮询, 假日志。
        BUG-04修复(小欧 2026-09-20): aclose后立即清引用, 防finally/__aexit__二次关闭(double-close)。"""
        resp = self._current_response
        if resp is not None:
            self._current_response = None  # BUG-04: 立即清空, 阻止finally块重复关闭
            try:
                await resp.aclose()
                logger.info("[LLMClient.cancel] 流式HTTP响应已强制关闭")
            except Exception as e:
                logger.warning(f"[LLMClient.cancel] 关闭流式响应失败: {e}")

    async def close(self):
        """关闭客户端,释放连接池 - 小沈 2026-06-09"""
        await self._client.aclose()

    # 【P1-22修复】添加异步上下文管理器,防止AsyncClient连接池泄漏 — chendyg 2026-06-26
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


def create_llm_client(
    llm_model: ModelRef,
    api_key: str,
    base_url: Optional[str] = None,
    timeout: Optional[int] = None,
    shared_client: Optional[httpx.AsyncClient] = None,  # 2026-09-20 小欧 C1 透传 — 小欧-2026-09-20
) -> LLMClient:
    """创建 LLM 客户端 — 唯一入口 - 小沈 2026-06-09; 2026-08-22 小欧 归一: 入参 llm_model: ModelRef"""
    return LLMClient(llm_model=llm_model, api_key=api_key, base_url=base_url, timeout=timeout, shared_client=shared_client)

