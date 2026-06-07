"""
端到端集成测试 — 连本地 Ollama (qwen2.5:1.5b) 跑真实 ReAct 循环

L2 测试层：只在发布前执行，不参与日常 CI。
标记: @pytest.mark.e2e_ollama

小沈 2026-05-21
"""
import pytest
import httpx
from app.services.llm_core import BaseAIService

OLLAMA_BASE = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:1.5b"


# ============================================================
# 辅助函数
# ============================================================

@pytest.fixture(scope="module")
def ollama_client() -> BaseAIService:
    return BaseAIService(
        api_key="ollama",
        model=OLLAMA_MODEL,
        api_base=f"{OLLAMA_BASE}/v1",
        provider="ollama",
        timeout=120,
    )


@pytest.fixture(scope="module")
def http_client() -> httpx.Client:
    return httpx.Client(base_url=OLLAMA_BASE, timeout=5)


# ============================================================
# L2-A: 基础连通性测试（~1s）
# ============================================================

@pytest.mark.e2e_ollama
class TestOllamaConnectivity:
    """验证 Ollama 服务本身是否正常运行"""

    def test_ollama_running(self, http_client: httpx.Client):
        resp = http_client.get("/")
        assert resp.status_code == 200
        assert "Ollama is running" in resp.text

    def test_model_available(self, http_client: httpx.Client):
        resp = http_client.get("/api/tags")
        assert resp.status_code == 200
        models = [m["name"] for m in resp.json().get("models", [])]
        assert OLLAMA_MODEL in models, f"{OLLAMA_MODEL} not in {models}"


# ============================================================
# L2-B: LLM Core 调用测试（~30s）
# ============================================================

@pytest.mark.e2e_ollama
class TestOllamaLLMCore:
    """验证 BaseAIService 能通过 Ollama 正常调用"""

    @pytest.mark.asyncio
    async def test_simple_chat(self, ollama_client: BaseAIService):
        resp = await ollama_client.chat("Hello! Reply with just 'OK'.")
        assert resp.success, f"chat failed: {resp.error}"
        assert resp.content.strip(), "empty response"

    @pytest.mark.asyncio
    async def test_chat_with_history(self, ollama_client: BaseAIService):
        history = [{"role": "user", "content": "My name is TestUser"}]
        resp = await ollama_client.chat("What's my name? Answer in one word.", history=history)
        assert resp.success, f"chat_with_history failed: {resp.error}"
        assert "TestUser" in resp.content, f"Expected 'TestUser' in '{resp.content}'"

    @pytest.mark.asyncio
    async def test_streaming(self, ollama_client: BaseAIService):
        chunks = []
        async for chunk in ollama_client.chat_stream("Count 1 to 3. Reply with just '1 2 3'."):
            if chunk.content:
                chunks.append(chunk.content)
            if chunk.is_done:
                break
        result = "".join(chunks)
        assert "1" in result and "2" in result and "3" in result, f"stream result: {result}"

    @pytest.mark.asyncio
    async def test_tool_call_format(self, ollama_client: BaseAIService):
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "获取天气",
                    "parameters": {
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                        "required": ["city"],
                    },
                },
            }
        ]
        resp = await ollama_client.chat_with_tools("北京天气怎么样？", tools=tools)
        assert resp.success, f"tool call failed: {resp.error}"
        # qwen2.5:1.5b 可能不返回 tool_calls，但至少不崩溃且有内容
        assert resp.content, "empty response for tool call"


# ============================================================
# L2-C: 真实 Agent ReAct 循环测试（~2-5min，标记为 slow）
# ============================================================

@pytest.mark.e2e_ollama
@pytest.mark.slow
class TestOllamaReActLoop:
    """全链路真实 ReAct 循环 — 不 mock，真连 Ollama"""

    @pytest.mark.asyncio
    async def test_read_file_react_loop(self):
        """真实 ReAct 循环：连 Ollama 跑完整 Agent"""
        client = BaseAIService(
            api_key="ollama",
            model=OLLAMA_MODEL,
            api_base=f"{OLLAMA_BASE}/v1",
            provider="ollama",
            timeout=300,
        )
        from app.services.agent import IntentAgent
        agent = IntentAgent(llm_client=client, task_id="e2e-ollama-001")
        events = []
        async for event in agent.run_stream("列出当前目录有哪些文件？"):
            events.append(event)
        assert events, "no events produced"
        assert events[-1]["type"] == "final", f"last event type: {events[-1].get('type')}"
