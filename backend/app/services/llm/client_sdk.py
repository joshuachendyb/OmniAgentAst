"""
LLM 客户端 SDK
Author: 小沈 - 2026-05-29

基础模块，被 BaseAIService / intent_classifier / capability_detector 调用。
只支持 OpenAI 兼容格式的 API（/chat/completions 端点）。
SDK 只管发 HTTP 请求，不处理错误，异常原样抛出。
"""

import httpx
from typing import Any, AsyncGenerator, Dict, List, Optional


# 集中配置
DEFAULT_CONNECT_TIMEOUT = 30.0
DEFAULT_READ_TIMEOUT = 60.0
DEFAULT_WRITE_TIMEOUT = 10.0
DEFAULT_POOL_TIMEOUT = 10.0
DEFAULT_MAX_CONNECTIONS = 10
DEFAULT_MAX_KEEPALIVE = 5


# ===== 请求体构建 =====

def _build_request_body(
    messages: List[Dict],
    model: str,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    seed: Optional[int] = None,
    tools: Optional[List[Dict]] = None,
    tool_choice: Optional[str] = None,
    stream: bool = False,
) -> Dict:
    """统一构建 LLM 请求体"""
    body = {"model": model, "messages": messages}
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    if temperature is not None:
        body["temperature"] = temperature
    if seed is not None:
        body["seed"] = seed
    if stream:
        body["stream"] = True
    if tools:
        body["tools"] = tools
    if tool_choice:
        body["tool_choice"] = tool_choice
    return body


# ===== LLM 客户端 =====

class LLMClient:
    """LLM 客户端实例"""

    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.provider = provider
        self.model = model
        self._api_key = api_key
        self._base_url = base_url or self._default_base_url(provider)

        read_timeout = float(timeout) if timeout else DEFAULT_READ_TIMEOUT
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=DEFAULT_CONNECT_TIMEOUT,
                read=read_timeout,
                write=DEFAULT_WRITE_TIMEOUT,
                pool=DEFAULT_POOL_TIMEOUT,
            ),
            limits=httpx.Limits(
                max_connections=DEFAULT_MAX_CONNECTIONS,
                max_keepalive_connections=DEFAULT_MAX_KEEPALIVE,
            ),
            headers={"Authorization": f"Bearer {api_key}"},
            base_url=self._base_url,
        )

    def _default_base_url(self, provider: str) -> str:
        """根据 provider 返回默认 API 地址（仅 OpenAI 兼容格式）"""
        urls = {
            "openai": "https://api.openai.com/v1",
            "deepseek": "https://api.deepseek.com",
            "qwen": "https://dashscope.aliyuncs.com/compatible-mode",
            "groq": "https://api.groq.com/openai",
            "ollama": "http://localhost:11434",
        }
        return urls.get(provider, "")

    async def chat(
        self,
        messages: List[Dict],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        seed: Optional[int] = None,
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[str] = None,
    ) -> Dict[str, Any]:
        """非流式 LLM 调用，返回原始响应"""
        body = _build_request_body(
            messages=messages, model=self.model,
            max_tokens=max_tokens, temperature=temperature, seed=seed,
            tools=tools, tool_choice=tool_choice, stream=False,
        )
        response = await self._client.post("/chat/completions", json=body)
        response.raise_for_status()
        return response.json()

    async def chat_stream(
        self,
        messages: List[Dict],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        seed: Optional[int] = None,
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """流式 LLM 调用，逐行 yield SSE data 字符串"""
        body = _build_request_body(
            messages=messages, model=self.model,
            max_tokens=max_tokens, temperature=temperature, seed=seed,
            tools=tools, tool_choice=tool_choice, stream=True,
        )
        async with self._client.stream("POST", "/chat/completions", json=body) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    yield data

    async def close(self):
        """关闭客户端，释放连接池"""
        await self._client.aclose()


def create_llm_client(
    provider: str,
    model: str,
    api_key: str,
    base_url: Optional[str] = None,
    timeout: Optional[int] = None,
) -> LLMClient:
    """
    创建 LLM 客户端 — 唯一入口

    Args:
        provider: 提供商（openai / deepseek / qwen / groq / ollama）
        model: 模型名（gpt-4 / deepseek-chat / qwen-plus 等）
        api_key: API 密钥
        base_url: API 地址（可选，默认根据 provider 自动设置）
        timeout: 超时秒数（可选，默认 60）

    Returns:
        LLMClient 实例
    """
    return LLMClient(provider=provider, model=model, api_key=api_key, base_url=base_url, timeout=timeout)
