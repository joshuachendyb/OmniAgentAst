# -*- coding: utf-8 -*-
"""
N4: search_web — 搜索网络获取最新信息

从network_tools.py拆分而来 — 小欧 2026-06-22
内聚: _search_mcp_engine / _search_bing / _parse_exa_results / _MCP_CONFIGS 辅助函数
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import base64
import re
import time as _time_mod
from typing import Any, Dict, List, Optional

import httpx

from app.tools.tool_response import build_success, build_error
from app.tools.network.http_client_sdk import create_http_client
from app.utils.common_patterns import HTML_TAG_PATTERN
from app.utils.json_utils import parse_json
from app.utils.logger import logger
from app.constants import (
    BROWSER_USER_AGENT,
    ERR_NET_UNKNOWN,
    ERR_PARAM_INVALID,
)


def _decode_bing_redirect_url(url: str) -> str:
    """解码Bing ck/a跳转链接 — 小欧 2026-06-22"""
    if "bing.com/ck/a" not in url:
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


def _build_search_web_llm_data(
    exec_code: str, duration_ms: int, query: str = "", engine_used: str = "",
    result_count: int = 0, llm_results=None,
    err_code: str = "", detail: str = "",
) -> Dict[str, Any]:
    """search_web的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"搜索失败: {query}",
            "action": {"tool": "search_web", "tool_zh": "网络搜索", "target": query, "params": {"query": query}},
            "status": {"exec_code": "error", "message": "搜索失败", "code": err_code, "detail": detail, "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"找到 {result_count} 条搜索结果({engine_used})",
        "action": {"tool": "search_web", "tool_zh": "网络搜索", "target": query, "params": {"query": query}},
        "status": {"exec_code": "success", "message": "搜索完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"results": {"value": result_count, "text": f"{result_count}条"}},
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
}


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
                current["snippet"] = line[:300]
    if current.get("title"):
        results.append(current)

    formatted = [
        {"title": r["title"], "url": r["url"], "snippet": r.get("snippet", "")[:300], "source": "Exa"}
        for r in results[:num_results] if r.get("title") and r.get("url")
    ]
    return formatted or None


async def _search_mcp_engine(engine: str, query: str, num_results: int, proxy: Optional[str] = None) -> Optional[List[dict]]:
    """MCP搜索引擎统一入口 — 小欧 2026-06-22"""
    config = _MCP_CONFIGS.get(engine)
    if not config:
        _search_failed(engine, "未知引擎")
        return None

    payload = {
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": config["tool_name"], "arguments": config["build_args"](query, num_results)},
    }
    try:
        async with create_http_client(timeout_sec=25.0, proxy=proxy) as client:
            resp = await client.post(config["url"], json=payload,
                headers={"Accept": "application/json, text/event-stream"})
            resp.raise_for_status()
            data = resp.json()
            result_text = data.get("result", {}).get("content", [{}])[0].get("text", "")
            if not result_text:
                _search_failed(engine, "返回空数据")
                return None

        if engine == "parallel":
            if not result_text.startswith("{"):
                _search_failed(engine, "返回数据非JSON")
                return None
            parsed = parse_json(result_text, raise_on_error=True)
            results = []
            for r in parsed.get("results", [])[:num_results]:
                title, url = r.get("title", ""), r.get("url", "")
                if title and url:
                    snippet = (r.get("excerpts", [])[0] or "")[:300]
                    results.append({"title": title, "url": url, "snippet": snippet, "source": "Parallel"})
            if not results:
                _search_failed(engine, "无搜索结果")
                return None
            return results
        else:
            formatted = _parse_exa_results(result_text, num_results)
            if not formatted:
                _search_failed(engine, "无搜索结果")
            return formatted

    except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as e:
        _search_failed(engine, f"网络错误: {type(e).__name__}")
    except Exception as e:
        _search_failed(engine, f"异常: {type(e).__name__}")
    return None


async def _search_bing(
    query: str,
    num_results: int,
    proxy_config: Optional[str] = None,
) -> List[dict]:
    """Bing搜索(HTML解析) — 小欧 2026-06-22"""
    headers = {"User-Agent": BROWSER_USER_AGENT}
    params = {"q": query, "count": num_results}

    async with create_http_client(timeout_sec=15.0, proxy=proxy_config) as client:
        response = await client.get("https://cn.bing.com/search", params=params, headers=headers)
        response.raise_for_status()
        html = response.text

    results = []
    algo_blocks = re.split(r'<li\s+class="b_algo"', html)
    for block in algo_blocks[1:]:
        if len(results) >= num_results:
            break
        a_match = re.search(r'<a[^>]+href="(https?://[^"]+)"[^>]*>', block[:3000])
        if not a_match:
            continue
        url = a_match.group(1)
        if "bing.com/ck/a" in url:
            pass
        elif "bing.com" in url or "microsoft.com" in url:
            continue

        h2_match = re.search(r'<h2[^>]*>(.*?)</h2>', block[:3000], re.DOTALL)
        if h2_match:
            title = HTML_TAG_PATTERN.sub('', h2_match.group(1)).strip()
        else:
            a_text_match = re.search(r'<a[^>]+href="[^"]+ "[^>]*>(.*?)</a>', block[:3000], re.DOTALL)
            title = HTML_TAG_PATTERN.sub('', a_text_match.group(1)).strip() if a_text_match else ""

        snippet = ""
        p_match = re.search(r'<div\s+class="b_caption"[^>]*>.*?<p[^>]*>(.*?)</p>', block[:3000], re.DOTALL)
        if not p_match:
            p_match = re.search(r'<p[^>]*>(.*?)</p>', block[:3000], re.DOTALL)
        if p_match:
            snippet = HTML_TAG_PATTERN.sub('', p_match.group(1)).strip()
            snippet = re.sub(r'&ensp;|&#\d+;', ' ', snippet).strip()

        if title and url:
            results.append({"title": title, "url": url, "snippet": snippet, "source": "Bing"})

    if not results:
        logger.warning("[_search_bing] 主解析未提取到结果,尝试简易模式")
        href_pattern = re.compile(r'<a\s+href="(https?://[^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
        for match in href_pattern.finditer(html):
            url = match.group(1)
            title = HTML_TAG_PATTERN.sub('', match.group(2)).strip()
            if "bing.com/ck/a" in url:
                pass
            elif "bing.com" in url or "microsoft.com" in url:
                continue
            if title and len(title) > 5:
                results.append({"title": title, "url": url, "snippet": "", "source": "Bing"})
            if len(results) >= num_results:
                break

    return results


async def search_web(
    query: str,
    allowed_domains: Optional[List[str]] = None,
    blocked_domains: Optional[List[str]] = None,
    num_results: int = 10,
    proxy: Optional[str] = None,
) -> Dict[str, Any]:
    """搜索网络 — 小健 2026-06-21 — 小欧 2026-06-22 独立文件"""
    t0 = _time_mod.perf_counter()
    try:
        if len(query) < 2:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_search_web_llm_data("error", duration_ms, query, err_code=ERR_PARAM_INVALID, detail="搜索查询至少需要2个字符")
            return build_error(data={"error_detail": "搜索查询至少需要2个字符", "params": {"query": query}}, llm_data=llm_data)

        results = await _search_mcp_engine("parallel", query, num_results, proxy)
        engine_used = "Parallel"

        if results is None:
            logger.info("[search_web] Parallel失败,降级到Exa MCP搜索")
            results = await _search_mcp_engine("exa", query, num_results, proxy)
            engine_used = "Exa"

        if results is None:
            logger.info("[search_web] Exa失败,降级到Bing中国搜索")
            try:
                results = await _search_bing(query, num_results, proxy)
                engine_used = "Bing"
            except Exception as e:
                logger.warning(f"[search_web] Bing搜索也失败: {e}")
                results = []

        if allowed_domains:
            results = [r for r in results if any(domain in r.get("url", "") for domain in allowed_domains)]
        if blocked_domains:
            results = [r for r in results if not any(domain in r.get("url", "") for domain in blocked_domains)]

        results = results[:num_results]

        for r in results:
            r["url"] = _decode_bing_redirect_url(r.get("url", ""))

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"query": query, "results": results, "total": len(results), "engine": engine_used}
        llm_data = _build_search_web_llm_data("success", duration_ms, query, engine_used, len(results))
        return build_success(data=data, llm_data=llm_data)

    except Exception as e:
        logger.error(f"[search_web] 未知错误: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_search_web_llm_data("error", duration_ms, query, err_code=ERR_NET_UNKNOWN, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {"query": query}}, llm_data=llm_data)