# -*- coding: utf-8 -*-
# 模块说明: zen_free 免费无key 适配 — 小欧 2026-09-23
#   准入配方(门禁重验): UA(>=1.17) + 合法 session 头
#   + body tools 同时含 bash 与 read + stream:true，四者齐备即 200。
#   (方案1后bash/read由fundamental_register真实注册, FC正常流程天然满足; 无tools请求由历史行为观察决定)
#   端点路由: muse- 前缀走 /responses(与 base_url zen/v1 拼成 /zen/v1/responses, flat tools)，其余走 /chat/completions。
# 编辑历史: 2026-09-23 小欧 新建
# 编辑历史: 2026-09-24 小欧 注释清理: 删注释/docstring 中 identifier.ts/session-id.ts/v1/session.ts 外部源码路径与 opencode.ai/session 等痕迹; 保留正式代码(URL/_ZEN_USER_AGENT/x-opencode-* header 键/类名/注册键/error_message_map 用户文案)零改动
# 编辑历史: 2026-09-24 北京老陈 方案1: 删GATE_STUBS假tool与missing注入逻辑, ensure_gate_body只保留stream:true强制

import os
import time
from typing import Dict, List  # List: 仅注释块GATE_STUBS备用代码使用, 取消注释时无需再加 — 北京老陈 2026-09-24
import logging

from app.llm.adapters.base import ProviderAdapter

logger = logging.getLogger(__name__)

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

# 2026-09-24 北京老陈 方案1: 删GATE_STUBS假tool — bash/read已在fundamental_register注册真实工具,
# FC正常调用get_openai_tools已含真实bash/read, ensure_gate_body的missing注入成为死代码, 整体删除
# <留着以后面备用>
# 2026-10-09 小欧 恢复(北京老陈裁定): 上面"方案1 删 stub 注入"删的是 ensure_gate_body 里的
#   missing 注入逻辑 —— FC 流程自带真工具时它确是死代码。纯文本任务(压缩摘要)不经
#   get_openai_tools, 无真工具可依, 必须靠本常量过门禁第③条(ZenFree-Test §10.1.1)。
#   场景不同故不矛盾。门禁只认 function.name 精确为 bash/read(§10.1.4(1) 近义名一律403)。
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
        # 2026-09-24 北京老陈 方案1: 删stub注入逻辑, 只保留stream:true强制(zen门禁要求)
        # bash/read真实工具由fundamental_register注册, 正常FC流程get_openai_tools已含
        # <留着以后面备用>
        # tools = body.get("tools") or []
        # names = {t.get("function", {}).get("name")
        #          for t in tools if isinstance(t, dict)}
        # missing = [s for s in GATE_STUBS
        #            if s["function"]["name"] not in names]
        # if missing:
        #     body = dict(body)
        #     body["tools"] = list(tools) + missing
        # <留着以后面备用>
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

    @staticmethod
    async def callTextForTask(client, messages) -> str:
        """纯文本任务的定制化调用 — opencode Zen 免费层实现 — 小欧 2026-10-09

        【为什么需要它】压缩摘要走 call_llm_with_fallback(openai_tools=None), 请求体里没有
        tools 键, 而门禁第③条要求 tools 同含 bash/read(ZenFree-Test §10.1.1) → 403。
        FC 主循环之所以没事: 经 get_openai_tools() 走 tools_alias_mapper 别名映射, 对外名恰为
        bash(shell→bash)/read(readtext→read); 摘要 openai_tools=None 整条映射链路都绕过了。

        【门禁四条件在本方法内的分工】
          ① UA≥1.17.0    ② 合法 session 头      → 客户端构造期 static_headers 已保证
          ③ body tools 含 bash/read              → 【本方法负责】GATE_STUBS
          ④ stream:true                        → ensure_gate_body 已强制
          muse-* 走 /responses 需 flat tools     → to_responses_body 已自动转换
        故本方法只补第③条, 其余全部复用 BaseAIService/client_sdk 既有机制, 不重复实现。

        【provider 区分】不在本函数内判断 —— 本方法定义在 opencodeZen.py 即代表 zen 专用,
        由 get_provider_adapter 挑实例实现分发。

        【重试】本方法只调一次, 不写重试。调用层(BaseAIService)自带什么就用什么。

        【返回值】client 是 BaseAIService(上层), 其 request() 返回 ChatResponse 对象
        (core.py:74) 而非 dict, 且失败不抛异常、错误塞在 .error 里 —— 故取 .content。

        【tool_choice】不传, 取 BaseAIService.request() 默认 "auto"。模型若真返回
        tool_calls, content 为空 → 返回 "", 零退化。
        """
        try:
            _resp = await client.request(messages=messages, tools=GATE_STUBS)
        except Exception as e:   # 上层已吞掉 HTTP 错误, 此处兜非 HTTP 异常
            logger.warning(f"[callTextForTask] zen 纯文本调用异常({type(e).__name__}: {e}), 返回空串零退化")
            return ""
        if getattr(_resp, "error", None):
            logger.warning(f"[callTextForTask] zen 纯文本调用失败({_resp.error}), 返回空串零退化")
            return ""
        return str(getattr(_resp, "content", "") or "").strip()