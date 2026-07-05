# -*- coding: utf-8 -*-
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
from typing import Any, Dict, List, Optional

import httpx

from app.tools.tool_response import build_success, build_error, build_warning
from app.tools.network.http_client_sdk import create_http_client
from app.tools.validate.url_validator import validate_proxy
from app.utils.common_patterns import HTML_TAG_PATTERN
from app.utils.json_utils import parse_json
from app.utils.logger import logger
from app.tools.tool_constants import TOOL_BROWSER_UA
from app.tools.tool_constants import (
    ERR_NET_UNKNOWN,
    ERR_PARAM_INVALID,
)


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


_SNIPPET_MAX_CHARS = 300

_CHALLENGE_KEYWORDS = ["captcha", "verify", "security", "robot", "automated",
                       "安全验证", "验证码", "机器人检测", "人机验证"]


def _build_search_web_llm_data(
    exec_code: str, duration_ms: int, query: str = "", engine_used: str = "",
    result_count: int = 0, llm_results=None,
    err_code: str = "", detail: str = "",
    proxy: Optional[str] = None, allowed_domains: Optional[List[str]] = None,
    blocked_domains: Optional[List[str]] = None, num_results: int = 10,
) -> Dict[str, Any]:
    """search_web的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22"""
    _act_params = {"query": query, "num_results": num_results}
    if proxy is not None:
        _act_params["proxy"] = proxy
    if allowed_domains is not None:
        _act_params["allowed_domains"] = allowed_domains
    if blocked_domains is not None:
        _act_params["blocked_domains"] = blocked_domains
    if exec_code == "error":
        return {
            "summary": f"搜索失败: {query}",
            "action": {"tool": "searchweb", "tool_zh": "搜索", "target": query, "params": _act_params},
            "status": {"exec_code": "error", "message": f"搜索失败: {detail}", "code": err_code, "detail": detail, "hint": "请检查搜索词和网络连接"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    if exec_code == "warning":
        return {
            "summary": f"搜索 {query}，{result_count}条结果（降级到{engine_used}引擎）",
            "action": {"tool": "searchweb", "tool_zh": "搜索", "target": query, "params": _act_params},
            "status": {"exec_code": "warning", "message": "搜索服务降级", "code": "", "detail": f"Parallel引擎不可用，降级到{engine_used}搜索", "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {"results": {"value": result_count, "text": f"{result_count}条"}, "engine": {"value": engine_used, "text": f"{engine_used}引擎（降级）"}},
        }
    return {
        "summary": f"搜索 {query}，{result_count}条结果",
        "action": {"tool": "searchweb", "tool_zh": "搜索", "target": query, "params": _act_params},
        "status": {"exec_code": "success", "message": "搜索完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"results": {"value": result_count, "text": f"{result_count}条"}, "engine": {"value": engine_used, "text": f"{engine_used}引擎"}},
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
                current["snippet"] = line
    if current.get("title"):
        results.append(current)

    formatted = [
        {"title": r["title"], "url": r["url"], "snippet": r.get("snippet", ""), "source": "Exa"}
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

            content_type = resp.headers.get("content-type", "")
            raw_text = resp.text

            if "text/event-stream" in content_type or raw_text.lstrip().startswith("data: "):
                for line in raw_text.split("\n"):
                    line = line.strip()
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            break
                        except json.JSONDecodeError:
                            continue
                else:
                    _search_failed(engine, f"SSE无有效JSON帧: {raw_text[:200]}")
                    return None
            else:
                data = resp.json()

            content_list = data.get("result", {}).get("content", [])
            result_text = content_list[0].get("text", "") if content_list else ""
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
                    snippet = r.get("excerpts", [])[0] or ""
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

    except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError):
        raise  # 【小欧 2026-06-29】传播给ToolRetryEngine统一分类+重试
    except Exception as e:
        _search_failed(engine, f"异常: {type(e).__name__}: {str(e)[:200]}")
    return None


_MAX_SEARCH_DEPTH = 3


async def _search_bing(
    query: str,
    num_results: int,
    proxy_config: Optional[str] = None,
    _depth: int = 0,
) -> List[dict]:
    """Bing搜索(HTML解析) — 小欧 2026-06-22
    更新: 2026-06-23 小欧 多域名降级+挑战页检测+长查询拆分
          2026-06-24 小欧 增加递归深度限制"""
    if _depth >= _MAX_SEARCH_DEPTH:
        return []

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
                a_text_match = re.search(r'<a[^>]+href="[^"]+"[^>]*>(.*?)</a>', block[:3000], re.DOTALL)
                title = HTML_TAG_PATTERN.sub('', a_text_match.group(1)).strip() if a_text_match else ""
            snippet = ""
            p_match = re.search(r'<div\s+class="b_caption"[^>]*>.*?<p[^>]*>(.*?)</p>', block[:3000], re.DOTALL)
            if not p_match:
                p_match = re.search(r'<p[^>]*>(.*?)</p>', block[:3000], re.DOTALL)
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

    for domain in domains:
        try:
            async with create_http_client(timeout_sec=15.0, proxy=proxy_config) as client:
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

        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as e:
            logger.warning(f"[_search_bing:{domain}] 网络错误: {type(e).__name__}")
            continue

    # 全部域名+完整查询都失败，尝试拆分查询
    sub_queries = _split_long_query(query, max_keywords=3)
    if len(sub_queries) > 1:
        logger.info(f"[_search_bing] 查询词过多({len(sub_queries)}组),逐个搜索后合并")
        all_results = []
        seen_urls = set()
        for sq in sub_queries:
            sub_results = await _search_bing(sq, max(3, num_results // len(sub_queries)), proxy_config, _depth + 1)
            for r in sub_results:
                u = r.get("url", "")
                if u and u not in seen_urls:
                    seen_urls.add(u)
                    all_results.append(r)
            if len(all_results) >= num_results:
                break
        return all_results[:num_results]

    return []


async def searchweb(
    query: str,
    allowed_domains: Optional[List[str]] = None,
    blocked_domains: Optional[List[str]] = None,
    num_results: int = 10,
    proxy: Optional[str] = None,
) -> Dict[str, Any]:
    """搜索网络 — 小健 2026-06-21 — 小欧 2026-06-22 独立文件"""
    proxy_valid, proxy_err, _ = validate_proxy(proxy)
    if not proxy_valid:
        t0 = _time_mod.perf_counter()
        llm_data = _build_search_web_llm_data("error", 0, query, err_code=ERR_PARAM_INVALID, detail=proxy_err, proxy=proxy, num_results=num_results)
        return build_error(data={"error_detail": proxy_err, "params": {"proxy": proxy}}, llm_data=llm_data)

    t0 = _time_mod.perf_counter()
    try:
        if len(query) < 2:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_search_web_llm_data("error", duration_ms, query, err_code=ERR_PARAM_INVALID, detail="搜索查询至少需要2个字符", proxy=proxy, num_results=num_results)
            return build_error(data={"error_detail": "搜索查询至少需要2个字符", "params": {"query": query}}, llm_data=llm_data)

        if not isinstance(num_results, int) or num_results < 1 or num_results > 50:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_search_web_llm_data("error", duration_ms, query, err_code=ERR_PARAM_INVALID, detail=f"num_results必须在1-50之间,当前值: {num_results}", proxy=proxy, num_results=num_results)
            return build_error(data={"error_detail": "num_results必须在1-50之间", "params": {"num_results": num_results}}, llm_data=llm_data)

        results = await _search_mcp_engine("parallel", query, num_results, proxy)
        engine_used = "Parallel"

        if results is None:
            logger.info("[searchweb] Parallel失败,降级到Exa MCP搜索")
            results = await _search_mcp_engine("exa", query, num_results, proxy)
            engine_used = "Exa"

        if results is None:
            logger.info("[searchweb] Exa失败,降级到Bing中国搜索")
            try:
                results = await _search_bing(query, num_results, proxy)
                engine_used = "Bing"
            except Exception as e:
                logger.warning(f"[searchweb] Bing搜索也失败: {e}")
                results = []

        results = results or []

        if allowed_domains:
            results = [r for r in results if any(domain in r.get("url", "") for domain in allowed_domains)]
        if blocked_domains:
            results = [r for r in results if not any(domain in r.get("url", "") for domain in blocked_domains)]

        results = results[:num_results]

        for r in results:
            r["url"] = _decode_bing_redirect_url(r.get("url", ""))
            snippet = r.get("snippet", "")
            if snippet and len(snippet) > _SNIPPET_MAX_CHARS:
                r["snippet"] = snippet[:_SNIPPET_MAX_CHARS] + "..."

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"items": results}
        if not results:
            exec_code = "warning"
        elif engine_used != "Parallel":
            exec_code = "warning"
        else:
            exec_code = "success"
        llm_data = _build_search_web_llm_data(exec_code, duration_ms, query, engine_used, len(results), proxy=proxy, allowed_domains=allowed_domains, blocked_domains=blocked_domains, num_results=num_results)
        if exec_code == "warning":
            # ---- observation_formatter route -------------------------------------------
            # branch: #4 items
            # trigger: "items" in data — items 是 List[dict]
            # handler: _format_items(data["items"])
            # file:    observation_formatter.py:132-134
            # ------------------------------------------------------------------------------
            return build_warning(data=data, llm_data=llm_data)
        # ---- observation_formatter route -------------------------------------------
        # branch: #4 items
        # trigger: "items" in data — items 是 List[dict]
        # handler: _format_items(data["items"])
        # file:    observation_formatter.py:132-134
        # ------------------------------------------------------------------------------
        return build_success(data=data, llm_data=llm_data)

    except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError):
        raise  # 【小欧 2026-06-29】传播给ToolRetryEngine统一分类+重试
    except Exception as e:
        logger.error(f"[searchweb] 未知错误: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_search_web_llm_data("error", duration_ms, query, err_code=ERR_NET_UNKNOWN, detail=str(e), proxy=proxy, num_results=num_results)
        return build_error(data={"error_detail": str(e), "params": {"query": query}}, llm_data=llm_data)