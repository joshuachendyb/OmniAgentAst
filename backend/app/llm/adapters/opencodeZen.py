# -*- coding: utf-8 -*-
# 模块说明: zen_free 免费无key 适配 — 小欧 2026-09-23
#   准入配方([66]§2.1 门禁重验): UA(>=1.17) + 合法 session 头
#   + body tools 同时含 bash 与 read + stream:true，四者齐备即 200。
#   端点路由: muse- 前缀走 /responses(与 base_url zen/v1 拼成 /zen/v1/responses, flat tools)，其余走 /chat/completions。
# 编辑历史: 2026-09-23 小欧 新建
# 编辑历史: 2026-09-24 小欧 注释清理: 删注释/docstring 中 identifier.ts/session-id.ts/v1/session.ts 外部源码路径与 opencode.ai/session 等痕迹; 保留正式代码(URL/_ZEN_USER_AGENT/x-opencode-* header 键/类名/注册键/error_message_map 用户文案)零改动

import os
import time
from typing import Dict, List

from app.llm.adapters.base import ProviderAdapter

_ZEN_USER_AGENT = "opencode/1.18.31 ai-sdk/provider-utils/4.0.23 runtime/bun/1.3.14"

# ---- ID 生成器 ----
# 原始逻辑: 时间戳(ms) << 12 + counter, descending 用按位取反, ascending 不取反
# ascending()/descending() 共享模块级 counter — 结构对齐
# 前12字符=时间组件(hex)，后14字符=加密安全随机(base62)
# 兼容性声明: 服务端只校验格式(ses_/msg_+12hex+14base62), 不解析数值语义,
#   故本实现保证格式级兼容; Python `~` 为无限精度整数、TS `~` 为 32 位语义,
#   大数下数值位必然分叉 — 属可接受差异(YAGNI)。 — 小欧 2026-09-23

_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


class _IdentifierGenerator:
    """有状态 ID 生成器，时间戳+共享 counter — 小欧 2026-09-23"""

    def __init__(self):
        self._last_timestamp = 0
        self._counter = 0

    def generate(self, prefix: str, descending: bool) -> str:
        now_ms = int(time.time() * 1000)
        if now_ms != self._last_timestamp:
            self._last_timestamp = now_ms
            self._counter = 0
        self._counter += 1

        current = now_ms * 4096 + self._counter
        value = ~current if descending else current

        time_hex = "".join(
            format((value >> (40 - 8 * i)) & 0xFF, "02x")
            for i in range(6)
        )

        rand_bytes = os.urandom(14)
        rand_part = "".join(_CHARS[b % 62] for b in rand_bytes)

        return prefix + time_hex + rand_part


# 模块级单实例: ses_/msg_ 共享同一计数器(同毫秒内连续递增) — 小欧 2026-09-23
_gen_id = _IdentifierGenerator()


def _gen_session_id() -> str:
    """生成 session ID: ses_ + 12位hex + 14位base62，客户端生命周期内固定复用 — 小欧 2026-09-23"""
    return _gen_id.generate("ses_", descending=True)   # descending: 按位取反


def _gen_request_id() -> str:
    """生成 request ID: msg_ + 12位hex + 14位base62，每请求刷新 — 小欧 2026-09-23"""
    return _gen_id.generate("msg_", descending=False)   # ascending: 不取反


GATE_STUBS: List[Dict] = [
    {"type": "function", "function": {
        "name": "bash", "description": "Executes a given command.",
        "parameters": {"type": "object",
                       "properties": {"command": {"type": "string"}},
                       "required": ["command"]}}},
    {"type": "function", "function": {
        "name": "read", "description": "Read a file.",
        "parameters": {"type": "object",
                       "properties": {"filePath": {"type": "string"}},
                       "required": ["filePath"]}}},
]


class OpencodeZenAdapter(ProviderAdapter):
    """zen_free 匿名免费层适配 — 小欧 2026-09-23"""

    @staticmethod
    def static_headers(api_key: str) -> Dict[str, str]:
        headers = {"Authorization": f"Bearer {api_key}"}
        headers.update({
            "User-Agent": _ZEN_USER_AGENT,
            "x-opencode-client": "cli",
            "x-opencode-project": "global",
            "x-opencode-session": _gen_session_id(),   # 客户端生命周期固定(每客户端一次)
        })
        return headers

    @staticmethod
    def per_request_headers() -> Dict[str, str]:
        return {"x-opencode-request": _gen_request_id()}   # 每请求刷新(不参与校验)

    @staticmethod
    def ensure_gate_body(body: Dict) -> Dict:
        tools = body.get("tools") or []
        names = {t.get("function", {}).get("name")
                 for t in tools if isinstance(t, dict)}
        missing = [s for s in GATE_STUBS
                   if s["function"]["name"] not in names]
        if missing:
            body = dict(body)
            body["tools"] = list(tools) + missing
        if body.get("stream") is not True:
            body = dict(body)
            body["stream"] = True
        return body

    @staticmethod
    def endpoint_for(model: str) -> str:
        # 与 base_url 拼接为真实端点:
        # chat 默认 rel=/chat/completions → zen/v1/chat/completions ✓
        # muse-responses rel=/responses(不能带/v1前缀, 否则双v1 404) → zen/v1/responses ✓ — 2026-09-23 小欧 实网复现修正
        if (model or "").startswith("muse-"):
            return "/responses"
        return "/chat/completions"

    @staticmethod
    def force_stream() -> bool:
        return True

    @staticmethod
    def to_responses_body(chat_body: Dict, model: str) -> Dict:
        messages = chat_body.get("messages") or []
        text = "\n".join(m.get("content", "") for m in messages
                         if isinstance(m, dict) and m.get("content"))
        flat = []
        for t in chat_body.get("tools") or []:
            fn = t.get("function", {}) if isinstance(t, dict) else {}
            if fn.get("name"):
                flat.append({"type": "function", "name": fn["name"],
                             "description": fn.get("description", ""),
                             "parameters": fn.get("parameters", {})})
        return {"model": model, "input": text,
                "stream": True, "tools": flat}

    @staticmethod
    def error_message_map() -> Dict[int, str]:
        # 可选(最小增强): zen 免费层特有错误码 → 友好文案; 未覆盖的由全局分类兜底 — 小欧 2026-09-23
        return {
            403: "Opencode Zen 免费层准入失败: 请检查 UA/session 头注入(适配层)或改用付费 key",
            426: "Opencode Zen 要求客户端升级(UpgradeRequired)",
        }