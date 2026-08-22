
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
"""

import httpx
import json
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.constants import (
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_READ_TIMEOUT,
    DEFAULT_WRITE_TIMEOUT,
    DEFAULT_POOL_TIMEOUT,
    LLM_MAX_CONNECTIONS,
    LLM_MAX_KEEPALIVE,
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
    ):
        self.llm_model = llm_model   # 前导+model 命名铁律 — 小欧 2026-08-22
        self._api_key = api_key
        self._base_url = llm_model.api_base or self._default_base_url(llm_model.provider)

        read_timeout = float(timeout) if timeout else DEFAULT_READ_TIMEOUT
        self._default_timeout = read_timeout
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=DEFAULT_CONNECT_TIMEOUT,
                read=read_timeout,
                write=DEFAULT_WRITE_TIMEOUT,
                pool=DEFAULT_POOL_TIMEOUT,
            ),
            limits=httpx.Limits(
                max_connections=LLM_MAX_CONNECTIONS,
                max_keepalive_connections=LLM_MAX_KEEPALIVE,
            ),
            headers={"Authorization": f"Bearer {api_key}"},
            base_url=self._base_url,
        )

    _DEFAULT_URLS = {
        "openai": "https://api.openai.com/v1",
        "deepseek": "https://api.deepseek.com",
        "qwen": "https://dashscope.aliyuncs.com/compatible-mode",
        "groq": "https://api.groq.com/openai",
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
        seed: Optional[int] = None,
        extra_body: Optional[Dict] = None,
        request_timeout: Optional[int] = None,  # #37 fix: per-request timeout — 小欧 2026-07-18
    ) -> Dict[str, Any]:
        """非流式请求 — FC-only: 无mode参数 — 小沈 2026-06-11; 小欧 2026-07-09 新增extra_body; #37 新增request_timeout"""
        body = _build_request_body(
            messages=messages, model=self.llm_model.model,   # 裸单值调API(设计要求4允许) — 小欧 2026-08-22
            max_tokens=max_tokens, temperature=temperature, seed=seed,
            tools=tools, tool_choice=tool_choice, stream=False,
            extra_body=extra_body,
        )
        _to = httpx.Timeout(request_timeout) if request_timeout else self._default_timeout
        response = await self._client.post("/chat/completions", json=body, timeout=_to)
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
        seed: Optional[int] = None,
        stream_options: Optional[Dict] = None,
        request_timeout: Optional[int] = None,
        extra_body: Optional[Dict] = None,
    ) -> AsyncGenerator[str, None]:
        """流式请求 — FC-only: 无mode参数 — 小沈 2026-06-11; 小健 2026-06-17 新增stream_options; 小欧 2026-07-09 新增extra_body"""
        body = _build_request_body(
            messages=messages, model=self.llm_model.model,   # 裸单值调API(设计要求4允许) — 小欧 2026-08-22
            max_tokens=max_tokens, temperature=temperature, seed=seed,
            tools=tools, tool_choice=tool_choice, stream=True,
            stream_options=stream_options,
            extra_body=extra_body,
        )
        # 结构化超时: request_timeout 仅作用于 read 阶段, connect/write/pool 独立固定。
        # 避免浮点标量将四者全部拉长 (浮点标量 = 全阶段统一值, 会误将 connect 也拉长至 90+秒)。
        # request_timeout 由 base_service 传入 (provider.timeout + 重试递增),
        # 未显式传入时用 DEFAULT_READ_TIMEOUT 兜底 — 小欧 2026-07-13
        _timeout = httpx.Timeout(
            connect=DEFAULT_CONNECT_TIMEOUT,
            read=float(request_timeout) if request_timeout is not None else DEFAULT_READ_TIMEOUT,
            write=DEFAULT_WRITE_TIMEOUT,
            pool=DEFAULT_POOL_TIMEOUT,
        )
        async with self._client.stream("POST", "/chat/completions", json=body, timeout=_timeout) as response:
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
) -> LLMClient:
    """创建 LLM 客户端 — 唯一入口 - 小沈 2026-06-09; 2026-08-22 小欧 归一: 入参 llm_model: ModelRef"""
    return LLMClient(llm_model=llm_model, api_key=api_key, base_url=base_url, timeout=timeout)

