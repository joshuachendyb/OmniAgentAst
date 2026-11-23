# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-15 - 小欧 - 常量归一化治理: snippet 截断改引用 tool_constants.SEARCH_SNIPPET_MAX_CHARS(原硬编码300), 功能零退化
# 2026-07-20 - 小欧 - searchweb 门限治理(章8.4): 删 SEARCH_SNIPPET_MAX_CHARS Tool层snippet截断(返回完整snippet, 3.7); 删 _MAX_SEARCH_DEPTH=3 递归深度限制(3.6); 删 len(query)<2 查询最小长度校验(3.6, 空/单字符现透传引擎); 截断唯一收口于 observation_formatter OBS_SEARCHWEB_MAX_ROWS/CHARS(两态说明); 保留 query is None 显式报错(防None透传Bing异常被吞为success空结果-正确性回归防护)
# 2026-07-20 - 小欧 - 门限复查: 删 _search_bing 的 _depth 递归死参(3.6 已去深度限制, _depth 不再校验, 递归由 _split_long_query 自然收敛兜底, 删除不影响行为)
# 2026-07-21 - 小欧 - 入参即信任: 内部 num_results 校验上界 50→1000（同步 schema le=1000）
# 2026-07-22 - 小欧 - query 校验从 None 显式报错扩展为 not query or not query.strip()，空字符串/纯空白也报错而非透传搜索
# 2026-07-24 - 小欧 - raw_text[:200]/str(e)[:200] → SEARCH_WEB_OUTPARM_LIMIT_RAW(魔数→命名常量)
# 2026-07-25 - 小欧 - 截断治理: block[:3000](5处) → SEARCH_WEB_INER_HTML_PARSE 命名常量
# 2026-10-12 小欧 - tool_zh改短名词（北京老陈令）: 搜索→搜网络
# 2026-10-20 15:22 小欧 - FIX: allowed_domains/blocked_domains 过滤失效 — schema 声明逗号分隔字符串(str)而
#   实现签名按 List[str] 收参, 引擎层类型容错又把 LLM 传的 list dumps 成字符串再传入, 原 any(domain in url)
#   对字符串**逐字符**比 URL(单字符'.'/'o'/'m'几乎必命中)致白名单/黑名单形同虚设。改为: 接口层
#   _coerce_domain_list 归一(str/JSON数组串/list → list[str]) + _url_match_domain 按 host 边界匹配
#   (host==d 或 host.endswith('.'+d), 消 'not-baidu.com' 子串假命中), 白/黑名单真正生效 | py_compile ✓
# 2026-11-23 小欧 - S1: Parallel 优先读 MCP structuredContent; text 内嵌 JSON 作为同一 provider 的响应格式容错;
#   excerpts 由只取首条改全拼("\n\n" 连接), 消除正文缺失 — 小欧-2026-11-23
# 2026-11-23 小欧 - S4: 流式读取限 MCP 响应体 + NetError 穿透通用 except + JSON-RPC error 信封检查 — 小欧-2026-11-23
# 2026-11-23 小欧 - S2: 统一调度接入 — 固定 if 降级链改 SEARCH_CHAIN + run_chain, 错误分类/分级冷却/attempts 由底座负责 — 小欧-2026-11-23
# 2026-11-23 小欧 - FIX: Parallel structured.results 字段异常时回落 text 内嵌 JSON 解析, 消除 S1 边缘退化 — 小欧-2026-11-23
# 2026-11-23 小欧 - 三堂会审整改: ①空值守卫下沉进 text 分支 —— 原来在 engine 分支前无条件 return, 只带
#   structuredContent 的合法 MCP 响应被"返回空数据"吞成 success 0 条, S1 在目标场景形同虚设;
#   ②JSON 文本容忍 ```json 围栏与前置空白, 解析失败归一为 UPSTREAM_BROKEN 而非静默空结果(DRY: 两处结果
#   提取合并为 _parse_parallel_results); ③SSE 取最后一个 result 帧而非首帧(首帧常是进度通知);
#   ④内层放行整个 httpx 家族给底座分类, 不再把 RemoteProtocolError/ReadError 吞成 EMPTY;
#   ⑤searchweb 增 timeout 参数并作为链级共享预算下传, 每家拿剩余时间, 不再被外层保险丝整链掐断;
#   ⑥bing 全域名网络失败时上抛给底座(原来 continue 吞掉, 三家全挂也报 success 0); ⑦成功也打 attempts 日志 — 小欧-2026-11-23
# 2026-11-23 商量 - P0+P2: MCP调用headers补User-Agent(TOOL_BROWSER_UA)修Cloudflare 403(原仅Accept被Exa/Parallel拒);
#   _search_mcp_engine支持config.extra_headers合并(TinyFish keyless header), 与UA并存 — 商量-2026-11-23
"""
N4: searchweb — 搜索网络获取最新信息

从network_tools.py拆分而来 — 小欧 2026-06-22
内聚: _search_mcp_engine / _search_bing / _parse_exa_results / _MCP_CONFIGS 辅助函数
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import base64
import json
import re
import time as _time_mod
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

import httpx

from app.constants import HTML_TAG_PATTERN
from app.logger import logger
from app.tools.network.http_client_sdk import create_http_client
from app.tools.network.net_backend import (
    Backend,
    NetError,
    run_chain,
)
from app.tools.tool_constants import (
    ERR_NET_INTERNAL,
    ERR_NET_NEED_SETUP,
    ERR_NET_NETWORK,
    ERR_NET_RATE_LIMITED,
    ERR_NET_TIMEOUT,
    ERR_NET_UPSTREAM_BROKEN,
    ERR_PARAM_INVALID,
    SEARCH_WEB_INER_HTML_PARSE,
    SEARCH_WEB_MCP_MAX_BYTES,
    SEARCH_WEB_OUTPARM_LIMIT_RAW,
    SEARCH_WEB_TIMEOUT_DEFAULT,
    TOOL_BROWSER_UA,
)
from app.tools.tool_response import build_error, build_success
from app.tools.validate.url_validator import validate_proxy
from app.utils.json_utils import coerce_json, parse_json


def _decode_bing_redirect_url(url: str) -> str:
    """解码Bing ck/a跳转链接 — 小欧 2026-06-22
    更新: 2026-06-23 小欧 增加空URL保护"""
    if not url or "bing.com/ck/a" not in url:
        return url
    u_match = re.search(r'[?&]u=([^&]+)', url)
    if u_match:
        try:
            u_encoded = u_match.group(1)
            u_encoded = u_encoded.replace('-', '+').replace('_', '/')
            padding = 4 - len(u_encoded) % 4
            if padding != 4:
                u_encoded += '=' * padding
            decoded = base64.b64decode(u_encoded).decode('utf-8', errors='replace')
            if decoded.startswith('http'):
                return decoded
        except Exception:
            pass
    return url


def _split_long_query(query: str, max_keywords: int = 3) -> List[str]:
    """将长查询拆分为多个短查询 — 小欧 2026-06-23
    通用方案：所有搜索引擎的长查询都可能返回0结果，拆分后搜索质量更高"""
    tokens = [t.strip() for t in re.split(r'[ ,，;；、\s]+', query) if len(t.strip()) > 1]
    if len(tokens) <= max_keywords:
        return [query]
    queries = []
    for i in range(0, len(tokens), max_keywords):
        sub = tokens[i:i + max_keywords]
        queries.append(" ".join(sub))
    return queries


def _coerce_domain_list(value: Union[str, List[str], None]) -> List[str]:
    """域名过滤参数归一: 逗号分隔字符串 / JSON数组字符串 / list → list[str], 剔除空白项 — 小欧 2026-10-20
    schema 声明逗号分隔字符串, 引擎类型容错会把 LLM 传的 list safe_json_dumps 成字符串再传入, 故两者皆可能收到。"""
    if value is None:
        return []
    coerced = coerce_json(value)
    if isinstance(coerced, list):
        items = coerced
    elif isinstance(coerced, str):
        items = re.split(r'[,，;；\s]+', coerced)
    else:
        return []
    return [d.strip() for d in items if isinstance(d, str) and d.strip()]


def _url_match_domain(url: str, domain: str) -> bool:
    """URL host 边界匹配(host==domain 或以 .domain 结尾) — 小欧 2026-10-20
    替代原子串 `domain in url`: 后者对 'evilsite.com?s=baidu.com' 等路径/参数中的域名假命中。"""
    if not url or not domain:
        return False
    host = (urlparse(url).hostname or "").lower()
    if not host:
        host = url.lower()   # 无 scheme 裸串保底: 直接按全文小写边界判
    d = domain.lower()
    return host == d or host.endswith("." + d)


# 2026-07-20 - 小欧 - searchweb 门限治理: snippet 返回完整内容(3.7 Tool 输出零限制), 不再截断; 显示域行×列截断收口于 observation_formatter OBS_SEARCHWEB_MAX_ROWS/CHARS

_CHALLENGE_KEYWORDS = ["captcha", "verify", "security", "robot", "automated",
                       "安全验证", "验证码", "机器人检测", "人机验证"]


def _build_search_web_llm_data(
    exec_code: str, duration_ms: int, query: str = "", engine_used: str = "",
    result_count: int = 0, llm_results=None,
    err_code: str = "", detail: str = "", hint: str = "",
    proxy: Optional[str] = None, allowed_domains: Optional[List[str]] = None,
    blocked_domains: Optional[List[str]] = None, num_results: int = 10,
) -> Dict[str, Any]:
    """search_web的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小欧 2026-07-05 加hint参数"""
    # 2026-10-14 小欧 - 引擎名缀 tool_zh(北京老陈令): Parallel/Exa/Bing 三引擎降级链, content/summary 带引擎名用户才知道实际用的谁;
    #   无引擎(失败/未知)回落裸"搜网络"。tool_zh 无逻辑判等(前后端只展示), 安全。 — 小欧-2026-10-14
    _zh = "搜网络" if not engine_used else f"搜网络·{engine_used}"
    _act_params = {"query": query, "num_results": num_results}
    if proxy is not None:
        _act_params["proxy"] = proxy
    if allowed_domains is not None:
        _act_params["allowed_domains"] = allowed_domains
    if blocked_domains is not None:
        _act_params["blocked_domains"] = blocked_domains
    if exec_code == "error":
        return {
            "summary": f"{_zh}{{{query}}}，失败",
            "action": {"tool": "searchweb", "tool_zh": _zh, "params": _act_params},
            "status": {"exec_code": "error", "message": f"搜索失败: {detail}", "code": err_code, "detail": detail, "hint": hint if hint else "请检查搜索词和网络连接"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
"summary": f"{_zh}{{{query}}}，成功：{result_count}条结果",  # 2026-10-14 小欧 - summary 统一口径: 动词用 tool_zh(搜网络) — 小欧-2026-10-14
            "action": {"tool": "searchweb", "tool_zh": _zh, "params": _act_params},
        "status": {"exec_code": "success", "message": f"完成:{result_count}条结果", "code": "", "detail": detail, "hint": hint},
        "duration_ms": duration_ms,
        # 2026-11-23 小欧 - 无引擎(全链空/失败)时不输出 engine 指标: 原来给空串, 前端渲染成"引擎"空标签
        "metrics": {"results": {"value": result_count, "text": f"{result_count}条"},
                    **({"engine": {"value": engine_used, "text": f"{engine_used}引擎"}} if engine_used else {})},
    }


_MCP_CONFIGS = {
    "parallel": {
        "url": "https://search.parallel.ai/mcp",
        "tool_name": "web_search",
        "build_args": lambda q, n: {"objective": q, "search_queries": [q], "session_id": "omniagent-search"},
    },
    "exa": {
        "url": "https://mcp.exa.ai/mcp",
        "tool_name": "web_search_exa",
        "build_args": lambda q, n: {"query": q, "type": "auto", "numResults": n, "livecrawl": "fallback"},
    },
    # 2026-11-23 商量 - Firecrawl keyless 免费层(实测200, 免UA); 仅 scrape/search/parse 三工具限速
    "firecrawl": {
        "url": "https://mcp.firecrawl.dev/v2/mcp",
        "tool_name": "firecrawl_search",
        "build_args": lambda q, n: {"query": q, "limit": n},
    },
    # 2026-11-23 商量 - TinyFish keyless(实测200, 免握手); 须带 X-TinyFish-Access-Mode: keyless header;
    #   build_args 不带 count(实测 count 参数致 400, 仅 query 200)
    "tinyfish": {
        "url": "https://agent.tinyfish.ai/mcp",
        "tool_name": "search",
        "build_args": lambda q, n: {"query": q},
        "extra_headers": {"X-TinyFish-Access-Mode": "keyless"},
    },
}

# 2026-11-23 小欧 - 搜索后端链: 新增来源只需在此加一行; tavily 待 S3 有 key 时接入。
#   每个后端末参数 remaining = 链级预算剩余秒数(None=不限), 底层逐家按剩余时间收敛硬超时
# 2026-11-23 商量 - 端点顺序(8.1.1): parallel(结构化首选)→exa(次选)→firecrawl(免费层三选)→tinyfish(备用四选)
SEARCH_CHAIN = (
    Backend("parallel", lambda q, n, p, t: _search_mcp_engine("parallel", q, n, p, t)),
    Backend("exa", lambda q, n, p, t: _search_mcp_engine("exa", q, n, p, t)),
    Backend("firecrawl", lambda q, n, p, t: _search_mcp_engine("firecrawl", q, n, p, t)),
    Backend("tinyfish", lambda q, n, p, t: _search_mcp_engine("tinyfish", q, n, p, t)),
)


def _parse_parallel_results(parsed: Optional[dict], num_results: int) -> List[dict]:
    """把 Parallel 结果体(结构化或 text 内嵌 JSON, 同构)统一转成 items — 2026-11-23 小欧(DRY: 两处提取合并)"""
    results = []
    for r in ((parsed or {}).get("results") or [])[:num_results]:
        title, url = r.get("title", ""), r.get("url", "")
        if title and url:
            # 2026-11-23 小欧 - 全部 excerpts 拼接, 避免只取首段造成正文缺失
            snippet = "\n\n".join(str(x) for x in (r.get("excerpts") or []) if x)
            results.append({"title": title, "url": url, "snippet": snippet, "source": "Parallel"})
    return results


def _parse_json_text(text: str) -> dict:
    """解析 MCP 文本里的 JSON 体, 容忍 ```json 围栏与前置空白; 解析失败归为上游响应坏 — 2026-11-23 小欧"""
    body = (text or "").strip()
    if body.startswith("```"):
        body = re.sub(r"^```[a-zA-Z]*\s*", "", body)
        body = re.sub(r"\s*```$", "", body).strip()
    try:
        parsed = parse_json(body, raise_on_error=True)
    except Exception as exc:  # noqa: BLE001 — 三方解析器异常类型不稳定, 统一归一为上游响应坏
        raise NetError(ERR_NET_UPSTREAM_BROKEN, f"文本结果非JSON: {str(exc)[:SEARCH_WEB_OUTPARM_LIMIT_RAW]}") from exc
    if not isinstance(parsed, dict):
        raise NetError(ERR_NET_UPSTREAM_BROKEN, "文本结果非JSON对象")
    return parsed


def _search_failed(engine: str, reason: str = "") -> None:
    """日志记录MCP搜索失败 — 小欧 2026-06-22"""
    logger.info(f"[_search_mcp_engine:{engine}] {reason}" if reason else f"[_search_mcp_engine:{engine}] 失败")


def _parse_exa_results(text: str, num_results: int) -> Optional[List[Dict[str, str]]]:
    """解析Exa MCP的文本格式结果 — 小欧 2026-06-22"""
    results = []
    current = {}
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("Title: "):
            if current.get("title"):
                results.append(current)
                if len(results) >= num_results:
                    break
            current = {"title": line[7:], "url": "", "snippet": ""}
        elif line.startswith("URL: "):
            current["url"] = line[5:]
        elif line.startswith("Highlights:") or (current.get("snippet") == "" and line and
              not line.startswith("Published") and not line.startswith("Author")):
            if not current["snippet"]:
                current["snippet"] = line
    if current.get("title"):
        results.append(current)

    formatted = [
        {"title": r["title"], "url": r["url"], "snippet": r.get("snippet", ""), "source": "Exa"}
        for r in results[:num_results] if r.get("title") and r.get("url")
    ]
    return formatted or None


# 2026-11-23 商量 - Firecrawl firecrawl_search 专用解析(实测: 返回 structuredContent {success,data:{web:[{url,title,description}]}},
#   非 Exa 的 Title:/URL: 文本块, _parse_exa_results 不适用); text 内嵌 JSON 作为同 provider 容错
def _parse_firecrawl_results(parsed: Optional[dict], num_results: int) -> List[dict]:
    results = []
    data = (parsed or {}).get("data") or {}
    for r in (data.get("web") or [])[:num_results]:
        title, url = r.get("title", ""), r.get("url", "")
        if title and url:
            results.append({"title": title, "url": url, "snippet": r.get("description", ""), "source": "Firecrawl"})
    return results


# 2026-11-23 商量 - TinyFish search 专用解析(实测: 返回 result_text JSON {query,results:[{title,url,snippet,...}]},
#   非 Exa 的 Title:/URL: 文本块); 解析失败返回 None 交底座分类
def _parse_tinyfish_results(text: str, num_results: int) -> Optional[List[dict]]:
    try:
        parsed = parse_json(text, raise_on_error=True)
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None
    results = []
    for r in (parsed.get("results") or [])[:num_results]:
        title, url = r.get("title", ""), r.get("url", "")
        if title and url:
            results.append({"title": title, "url": url, "snippet": r.get("snippet", ""), "source": "TinyFish"})
    return results or None


async def _search_mcp_engine(
    engine: str,
    query: str,
    num_results: int,
    proxy: Optional[str] = None,
    timeout_sec: Optional[float] = None,
) -> Optional[List[dict]]:
    """MCP搜索引擎统一入口 — 小欧 2026-06-22
    timeout_sec: 链级预算剩余秒数(None=按单家缺省25s)，只收敛本次调用，不改变解析语义 — 2026-11-23 小欧"""
    config = _MCP_CONFIGS.get(engine)
    if not config:
        _search_failed(engine, "未知引擎")
        return None

    payload = {
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": config["tool_name"], "arguments": config["build_args"](query, num_results)},
    }
    call_timeout = 25.0 if timeout_sec is None else max(1.0, min(25.0, timeout_sec))
    try:
        async with create_http_client(timeout_sec=call_timeout, proxy=proxy) as client:
            # 2026-11-23 小欧 - S4: 流式读取并限制响应体, 避免大响应整体进内存
            # 2026-11-23 商量 - P0 UA修复 + P2 extra_headers合并: MCP调用带浏览器UA(TOOL_BROWSER_UA)修Cloudflare 403
            #   (原仅Accept, httpx默认python-httpx被Exa/Parallel拒); 并合并config.extra_headers(TinyFish keyless header)
            _headers = {"Accept": "application/json, text/event-stream", "User-Agent": TOOL_BROWSER_UA}
            _headers.update(config.get("extra_headers") or {})
            async with client.stream("POST", config["url"], json=payload,
                    headers=_headers) as resp:
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "")
                chunks = []
                total = 0
                async for chunk in resp.aiter_bytes():
                    total += len(chunk)
                    if total > SEARCH_WEB_MCP_MAX_BYTES:
                        raise NetError(ERR_NET_UPSTREAM_BROKEN, f"响应超过{SEARCH_WEB_MCP_MAX_BYTES}字节")
                    chunks.append(chunk)
                raw_text = b"".join(chunks).decode("utf-8", errors="replace")

            if "text/event-stream" in content_type or raw_text.lstrip().startswith("data: "):
                # 2026-11-23 小欧 - 整改: 取最后一个携带 result/error 的帧; 首帧常是 notifications/progress,
                #   原实现遇到首个可解析帧就 break, 会把进度通知当结果 → "返回空数据"
                data = None
                fallback = None
                for line in raw_text.split("\n"):
                    line = line.strip()
                    if not line.startswith("data: "):
                        continue
                    try:
                        frame = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue
                    fallback = frame
                    if isinstance(frame, dict) and ("result" in frame or "error" in frame):
                        data = frame
                if data is None:
                    data = fallback
                if data is None:
                    _search_failed(engine, f"SSE无有效JSON帧: {raw_text[:SEARCH_WEB_OUTPARM_LIMIT_RAW]}")
                    return None
            else:
                # 2026-11-23 小欧 - 流式模式下 body 未入 resp._content, 直接解析已拼接的受限文本
                data = json.loads(raw_text)

            # 2026-11-23 小欧 - MCP 特有: HTTP 200 也可能带 JSON-RPC error envelope, 不检查会被当空数据吞掉
            rpc_error = data.get("error")
            if isinstance(rpc_error, dict):
                raise NetError(ERR_NET_UPSTREAM_BROKEN,
                               f"JSON-RPC error: {str(rpc_error.get('message', ''))[:SEARCH_WEB_OUTPARM_LIMIT_RAW]}")

            content_list = (data.get("result") or {}).get("content") or []
            result_text = content_list[0].get("text", "") if content_list else ""
            structured = (data.get("result") or {}).get("structuredContent") or {}

    # 2026-11-23 小欧 - 整改: 空值守卫下沉进各分支 —— 原来在 engine 分支前无条件 return,
    #   MCP 只返回 structuredContent 的合法响应被当"空数据"吞掉, S1 的结构化优先在目标场景完全失效
        if engine == "parallel":
            # 2026-11-23 小欧 - S1: 优先读 MCP 结构化结果; text 内嵌 JSON 作为同一 provider 的响应格式容错
            results = _parse_parallel_results(structured, num_results)
            if not results and result_text:
                results = _parse_parallel_results(_parse_json_text(result_text), num_results)
            if not results:
                _search_failed(engine, "无搜索结果")
                return None
            return results

        if engine == "firecrawl":
            # 2026-11-23 商量 - Firecrawl 返回 structuredContent{data:{web:[]}}; text 内嵌 JSON 作容错
            results = _parse_firecrawl_results(structured, num_results)
            if not results and result_text:
                results = _parse_firecrawl_results(_parse_json_text(result_text), num_results)
            if not results:
                _search_failed(engine, "无搜索结果")
                return None
            return results

        if engine == "tinyfish":
            # 2026-11-23 商量 - TinyFish 返回 result_text JSON{results:[]}; 解析失败归 None 交底座
            formatted = _parse_tinyfish_results(result_text, num_results)
            if not formatted:
                _search_failed(engine, "无搜索结果")
            return formatted

        if not result_text:
            _search_failed(engine, "返回空数据")
            return None
        formatted = _parse_exa_results(result_text, num_results)
        if not formatted:
            _search_failed(engine, "无搜索结果")
        return formatted

    # 2026-11-23 小欧 - 整改: 放行整个 httpx 家族(HTTPStatus/Transport/Timeout/InvalidURL)交给底座分类,
    #   原来只放行三个子类, RemoteProtocolError/ReadError 被吞成 EMPTY 导致既不分类也不冷却
    except (httpx.HTTPError, NetError):
        raise  # 【小欧 2026-06-29】传播给调度底座统一分类+冷却
    except Exception as e:
        # 本侧解析/取值缺陷: 归 INTERNAL 交给底座(不冷却、不掩盖), 不再静默吞成空结果
        _search_failed(engine, f"异常: {type(e).__name__}: {str(e)[:SEARCH_WEB_OUTPARM_LIMIT_RAW]}")
        raise NetError(ERR_NET_INTERNAL,
                       f"{engine} 解析异常: {type(e).__name__}: {str(e)[:SEARCH_WEB_OUTPARM_LIMIT_RAW]}") from e


async def _search_bing(
    query: str,
    num_results: int,
    proxy_config: Optional[str] = None,
    timeout_sec: Optional[float] = None,
) -> List[dict]:
    """Bing搜索(HTML解析) — 小欧 2026-06-22
    更新: 2026-06-23 小欧 多域名降级+挑战页检测+长查询拆分
          2026-07-20 小欧 章8.4 按3.6去除递归深度限制(查询拆分自然收敛兜底)
          2026-11-23 小欧 链级预算: timeout_sec=剩余预算(收敛单次硬超时); 全部域名均网络失败时上抛,
            不再 continue 吞成空结果 —— 否则三家全挂也报 success 0 条"""
    import time as _t

    deadline = None if timeout_sec is None else _t.monotonic() + timeout_sec

    def _remaining(default: float) -> float:
        if deadline is None:
            return default
        return max(1.0, min(default, deadline - _t.monotonic()))

    headers = {"User-Agent": TOOL_BROWSER_UA}
    params = {"q": query, "count": num_results}

    def _has_challenge_page(html: str) -> Optional[str]:
        html_lower = html.lower()
        for kw in _CHALLENGE_KEYWORDS:
            if kw in html_lower:
                return kw
        return None

    def _parse_bing_html(html: str, num: int, domain_name: str) -> List[dict]:
        results = []
        algo_blocks = re.split(r'<li\s+class="b_algo"', html)
        if len(algo_blocks) <= 1:
            algo_blocks = re.split(r'<li class="b_algo"', html)
        for block in algo_blocks[1:]:
            if len(results) >= num:
                break
            a_match = re.search(r'<a[^>]+href="(https?://[^"]+)"[^>]*>', block[:SEARCH_WEB_INER_HTML_PARSE])
            if not a_match:
                continue
            url = a_match.group(1)
            if "bing.com/ck/a" in url:
                pass
            elif "bing.com" in url or "microsoft.com" in url:
                continue
            h2_match = re.search(r'<h2[^>]*>(.*?)</h2>', block[:SEARCH_WEB_INER_HTML_PARSE], re.DOTALL)
            if h2_match:
                title = HTML_TAG_PATTERN.sub('', h2_match.group(1)).strip()
            else:
                a_text_match = re.search(r'<a[^>]+href="[^"]+"[^>]*>(.*?)</a>', block[:SEARCH_WEB_INER_HTML_PARSE], re.DOTALL)
                title = HTML_TAG_PATTERN.sub('', a_text_match.group(1)).strip() if a_text_match else ""
            snippet = ""
            p_match = re.search(r'<div\s+class="b_caption"[^>]*>.*?<p[^>]*>(.*?)</p>', block[:SEARCH_WEB_INER_HTML_PARSE], re.DOTALL)
            if not p_match:
                p_match = re.search(r'<p[^>]*>(.*?)</p>', block[:SEARCH_WEB_INER_HTML_PARSE], re.DOTALL)
            if p_match:
                snippet = HTML_TAG_PATTERN.sub('', p_match.group(1)).strip()
                snippet = re.sub(r'&ensp;|&#\d+;', ' ', snippet).strip()
            if title and url:
                results.append({"title": title, "url": url, "snippet": snippet, "source": f"Bing({domain_name})"})
        return results

    def _parse_simple(html: str, num: int, domain_name: str) -> List[dict]:
        href_pattern = re.compile(r'<a\s+href="(https?://[^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
        results = []
        seen_urls = set()
        for match in href_pattern.finditer(html):
            url = match.group(1)
            title = HTML_TAG_PATTERN.sub('', match.group(2)).strip()
            if "bing.com/ck/a" in url:
                continue
            if "bing.com" in url or "microsoft.com" in url or "javascript:" in url or url.startswith("#"):
                continue
            if not title or len(title) < 8:
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)
            results.append({"title": title, "url": url, "snippet": "", "source": f"Bing({domain_name})"})
            if len(results) >= num:
                break
        return results

    domains = ["cn.bing.com", "www.bing.com"]
    tried_domains = []
    net_error: Optional[httpx.HTTPError] = None  # 2026-11-23 小欧 - 记最后一个网络异常, 全域名失败时上抛给底座

    for domain in domains:
        try:
            async with create_http_client(timeout_sec=_remaining(15.0), proxy=proxy_config) as client:
                response = await client.get(f"https://{domain}/search", params=params, headers=headers)
                response.raise_for_status()
                html = response.text
                tried_domains.append(domain)

            challenge = _has_challenge_page(html)
            if challenge:
                logger.warning(f"[_search_bing:{domain}] 检测到挑战页({challenge}),继续下一步")
                continue

            results = _parse_bing_html(html, num_results, domain)
            if results:
                return results

            logger.warning(f"[_search_bing:{domain}] 主解析无结果,尝试简易模式")
            results = _parse_simple(html, num_results, domain)
            if results:
                return results

            logger.warning(f"[_search_bing:{domain}] 简易模式也无结果({len(html)}字节HTML)")
            continue

        except httpx.HTTPError as e:
            # 域名级降级继续下一个域名; 但异常留痕, 全域名都失败时上抛, 让底座记冷却换家
            logger.warning(f"[_search_bing:{domain}] 网络错误: {type(e).__name__}")
            net_error = e
            continue

    # 全部域名+完整查询都失败，尝试拆分查询
    sub_queries = _split_long_query(query, max_keywords=3)
    if len(sub_queries) > 1:
        logger.info(f"[_search_bing] 查询词过多({len(sub_queries)}组),逐个搜索后合并")
        all_results = []
        seen_urls = set()
        for sq in sub_queries:
            sub_results = await _search_bing(sq, max(3, num_results // len(sub_queries)), proxy_config,
                                             _remaining(15.0))
            for r in sub_results:
                u = r.get("url", "")
                if u and u not in seen_urls:
                    seen_urls.add(u)
                    all_results.append(r)
            if len(all_results) >= num_results:
                break
        if all_results:
            return all_results[:num_results]

    # 2026-11-23 小欧 - 全部域名都网络失败(没有一页取到 HTML)才上抛; 挑战页/无结果属正常空结果, 保持 []
    if net_error is not None:
        raise net_error
    return []


async def searchweb(
    query: str,
    allowed_domains: Optional[str] = None,
    blocked_domains: Optional[str] = None,
    num_results: int = 10,
    proxy: Optional[str] = None,
    timeout: int = SEARCH_WEB_TIMEOUT_DEFAULT,
) -> Dict[str, Any]:
    """搜索网络 — 小健 2026-06-21 — 小欧 2026-06-22 独立文件 — 小欧 2026-10-20 域名过滤参数口径与schema对齐(str,逗号分隔)
    2026-11-23 小欧 - timeout = 链级共享预算(秒): 每家后端只拿剩余时间, 预算用完即停并如实报超时,
      不再让各家硬超时之和(25+25+15×2=80s)超过外层保险丝被整链掐断"""
    proxy_valid, proxy_err, _ = validate_proxy(proxy)
    if not proxy_valid:
        t0 = _time_mod.perf_counter()
        llm_data = _build_search_web_llm_data("error", 0, query, err_code=ERR_PARAM_INVALID, detail=proxy_err, hint="请检查代理配置", proxy=proxy, num_results=num_results)
        return build_error(data={}, llm_data=llm_data)

    # 2026-10-20 小欧 - 域名过滤参数归一(见文件头编辑历史): str/JSON数组串/list → list[str]
    _allowed_domains = _coerce_domain_list(allowed_domains)
    _blocked_domains = _coerce_domain_list(blocked_domains)

    # 2026-07-22 - 小欧 - None 显式报错(防None透传Bing引发NoneType异常被except吞为success空结果, 属正确性回归防护; 非长度/格式限制, 与3.6删除len(query)<2无关)
    if not query or not query.strip():
        detail = "query 不能为空" if not query else "query 不能为纯空白"  # 2026-10-14 小欧 - detail 去行动: "请提供搜索关键词"归 hint(已有), detail 只讲事实 — 小欧-2026-10-14
        llm_data = _build_search_web_llm_data("error", 0, query, err_code=ERR_PARAM_INVALID, detail=detail, hint="请提供搜索关键词", proxy=proxy, num_results=num_results)
        return build_error(data={}, llm_data=llm_data)

    t0 = _time_mod.perf_counter()
    try:
        if not isinstance(num_results, int) or num_results < 1 or num_results > 1000:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_search_web_llm_data("error", duration_ms, query, err_code=ERR_PARAM_INVALID, detail=f"num_results必须在1-1000之间,当前值: {num_results}", hint="请将结果数量设置在1-1000之间", proxy=proxy, num_results=num_results)
            return build_error(data={}, llm_data=llm_data)

        # 2026-11-23 小欧 - S2 统一调度: 错误分类/分级冷却/尝试轨迹/链级预算由底座负责
        budget = SEARCH_WEB_TIMEOUT_DEFAULT if timeout is None else timeout
        out = await run_chain(
            "search",
            SEARCH_CHAIN + (Backend("bing", lambda q, n, p, t: _search_bing(q, n, p, t)),),
            (query, num_results, proxy),
            budget_sec=budget,
        )
        if out["error"] is not None:
            error = out["error"]
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            hint = {
                ERR_NET_RATE_LIMITED: "搜索源限流冷却中，请稍后重试",
                ERR_NET_NEED_SETUP: "搜索源拒绝访问(鉴权/额度)，请检查该服务的 key 或额度配置",
                ERR_NET_NETWORK: "连不上搜索服务，请检查本机网络或代理设置",
                ERR_NET_TIMEOUT: "搜索超时，建议简化搜索词或稍后重试",
                ERR_NET_UPSTREAM_BROKEN: "搜索服务返回异常，请稍后重试",
            }.get(error.code, "请检查搜索词和网络连接")
            llm_data = _build_search_web_llm_data(
                "error", duration_ms, query, err_code=error.code,
                detail=error.message, hint=hint, proxy=proxy, num_results=num_results,
            )
            logger.info("[searchweb] 失败 attempts=%s budget=%ss elapsed=%sms", out["attempts"], budget, duration_ms)
            return build_error(data={}, llm_data=llm_data)
        # backend 为 None = 至少一家正常往返但均无结果, 保持 success 0 条语义
        results = out["items"]
        engine_used = (out["backend"] or "").capitalize()

        if _allowed_domains:
            results = [r for r in results if any(_url_match_domain(r.get("url", ""), d) for d in _allowed_domains)]
        if _blocked_domains:
            results = [r for r in results if not any(_url_match_domain(r.get("url", ""), d) for d in _blocked_domains)]

        results = results[:num_results]

        for r in results:
            r["url"] = _decode_bing_redirect_url(r.get("url", ""))
            snippet = r.get("snippet", "")
            if snippet:
                # 清理HTML标签和Markdown链接 — 小欧 2026-07-07
                snippet = HTML_TAG_PATTERN.sub('', snippet)
                snippet = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', snippet)
                snippet = re.sub(r'\n{2,}', ' ', snippet).strip()
                r["snippet"] = snippet

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"items": results}
        exec_code = "success"
        # 2026-11-23 小欧 - 有后端失败/冷却但仍拿到空结果时, 显式告知"结果可能不完整", 不让故障被静默吞掉
        degraded_hint = ""
        if out["failures"]:
            _codes = "、".join(sorted({f["code"] for f in out["failures"]}))
            degraded_hint = f"部分搜索源不可用({_codes})，结果可能不完整"
        llm_data = _build_search_web_llm_data(exec_code, duration_ms, query, engine_used, len(results), proxy=proxy, allowed_domains=_allowed_domains, blocked_domains=_blocked_domains, num_results=num_results, hint=degraded_hint)
        logger.info("[searchweb] 成功 attempts=%s budget=%ss elapsed=%sms", out["attempts"], budget, duration_ms)
        # ---- observation_formatter route -------------------------------------------
        # branch: #4 items
        # trigger: "items" in data — items 是 List[dict]
        # handler: _format_items(data["items"])
        # file:    observation_formatter.py:132-134
        # ------------------------------------------------------------------------------
        return build_success(data=data, llm_data=llm_data)

    except (httpx.HTTPError, NetError):
        raise  # 【小欧 2026-06-29】传播给ToolRetryEngine统一分类+重试
    except Exception as e:
        logger.error(f"[searchweb] 未知错误: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_search_web_llm_data("error", duration_ms, query, err_code=ERR_NET_INTERNAL, detail=f"{type(e).__name__}: {str(e) or repr(e)}", hint="搜索异常，请重试", proxy=proxy, num_results=num_results)
        return build_error(data={}, llm_data=llm_data)
