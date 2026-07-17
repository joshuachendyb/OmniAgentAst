# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-15 - 小欧 - fetchpage异常日志修复: 某些httpx底层异常__str__返回空串, 致logger.error("未知错误:")后空白, 开发排查丢失异常类型。LLM侧detail(line 672)早已用type(e).__name__: str(e) or repr(e)正确传递, 本次仅增强开发日志可读性, 非功能缺陷。
# 2026-07-15 - 小欧 - 常量归一化治理: 网页正文提取上限改引用 tool_constants.WEB_FETCH_MAX_CHARS(原 max_tokens=8000→32000字符, 现对齐 OBS 10000字符), 功能零退化
# 2026-07-17 - 小欧 - HTTPStatusError hint 按状态码精化(4xx/5xx/429)
# 2026-07-17 - 小欧 - fetchpage架构增强: ①提取正文trafilatura优先(html2text/SSR兜底保留) ②Playwright改独立Proactor子循环隔离运行(消Windows Selector NotImplementedError红字) ③SPA回退加外部API(Jina Reader)兜底, 三级降级HTTP→Playwright→外部API→友好提示, 功能零退化
"""
N3: fetchpage — 获取和处理网页内容

从network_tools.py拆分而来 — 小欧 2026-06-22
内聚: _extract_html_content / _build_media_result / _fetch_via_playwright 辅助函数
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
import asyncio
import base64
import html2text
import json
import re
import traceback
import time as _time_mod
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple

import httpx

import sys

try:
    import trafilatura as _TRAFILATURA
except ImportError:
    _TRAFILATURA = None

from app.tools.tool_response import build_success, build_error, build_warning
from app.tools.network.http_client_sdk import create_http_client
from app.tools.network.network_register import check_network
from app.tools.validate.url_validator import validate_url, validate_proxy
from app.tools.validate.timeout_validator import validate_timeout

from app.constants import HTML_TAG_PATTERN, SCRIPT_TAG_PATTERN, STYLE_TAG_PATTERN, MULTI_WHITESPACE_PATTERN
from app.logger import logger
from app.tools.tool_constants import TOOL_BROWSER_UA, WEB_FETCH_MAX_CHARS
from app.tools.tool_constants import (
    ERR_INVALID_URL,
    ERR_NETWORK_DOWN,
    ERR_NETWORK_HTTP_ERROR,
    ERR_NETWORK_JS_RENDER,
    ERR_NETWORK_REQUEST_ERROR,
    ERR_NETWORK_TIMEOUT,
    ERR_NET_UNKNOWN,
)


_VOID_ELEMENTS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img",
    "input", "link", "meta", "param", "source", "track", "wbr",
})


def _match_attrs(attrs: Dict[str, str], required: Dict[str, str]) -> bool:
    """检查HTML属性是否匹配要求的模式 — 小沈 2026-07-08"""
    for key, val in required.items():
        actual = attrs.get(key)
        if actual is None:
            return False
        if val is True:
            continue
        if hasattr(val, "search"):
            if not val.search(actual):
                return False
        elif val != actual:
            return False
    return True


class _ContentExtractor(HTMLParser):
    """用HTMLParser正确提取匹配指定属性的容器内容(处理嵌套标签)—小欧2026-06-23"""

    def __init__(self, tag_matchers: List[tuple]):
        super().__init__(convert_charrefs=False)
        self._tag_matchers = tag_matchers
        self._depth = 0
        self._started = False
        self._parts: List[str] = []
        self._found: Optional[str] = None

    def handle_starttag(self, tag, attrs):
        if self._started:
            if tag not in _VOID_ELEMENTS:
                self._depth += 1
            self._parts.append(self.get_starttag_text())
        elif self._found is None:
            for t, attr_dict in self._tag_matchers:
                if tag == t and _match_attrs(dict(attrs), attr_dict):
                    self._started = True
                    self._depth = 0
                    self._parts = []
                    break

    def handle_endtag(self, tag):
        if self._started:
            if self._depth == 0 and any(tag == t for t, _ in self._tag_matchers):
                self._found = "".join(self._parts)
                self._started = False
            else:
                if self._depth > 0:
                    self._parts.append(f"</{tag}>")
                if tag not in _VOID_ELEMENTS:
                    self._depth -= 1

    def handle_startendtag(self, tag, attrs):
        if self._started:
            self._parts.append(self.get_starttag_text())

    def handle_data(self, data):
        if self._started:
            self._parts.append(data)

    def handle_entityref(self, name):
        if self._started:
            self._parts.append(f"&{name};")

    def handle_charref(self, name):
        if self._started:
            self._parts.append(f"&#{name};")

    def handle_comment(self, data):
        pass

    def get_content(self) -> Optional[str]:
        return self._found


def _extract_main_content(html: str) -> Optional[str]:
    """提取页面主要内容区域HTML — 小欧 2026-06-23

    用HTMLParser正确提取正文容器(处理嵌套标签):
    1. <article> 语义标签
    2. <main> 语义标签
    3. <div id="main">
    4. <div class~=w3-main> (w3schools典型结构)
    5. <div class/id 含 content/main/article/post/entry
    找不到则返回None。
    """
    id_main = re.compile(r'(?:^|\s)main(?:\s|$)')
    w3_main = re.compile(r'w3-main')
    content_like = re.compile(r'(?:content|main|article|post|entry)')
    tag_matchers = [
        ("article", {}),
        ("main", {}),
        ("div", {"id": "main"}),
        ("div", {"class": w3_main}),
        ("div", {"id": id_main}),
        ("div", {"class": content_like}),
    ]
    extractor = _ContentExtractor(tag_matchers)
    extractor.feed(html)
    content = extractor.get_content()
    if content:
        text_len = len(re.sub(r'<[^>]+>', "", content).strip())
        if text_len > 50:
            return content
    return None


def _convert_html2text(html: str) -> str:
    """html2text转换 — 小欧 2026-07-08"""
    h = html2text.HTML2Text()
    h.body_width = 0
    h.ignore_links = False
    h.ignore_images = False
    h.ignore_tables = False
    h.emphasis_mark = "*"
    h.strong_mark = "**"
    return h.handle(html)


def _extract_via_trafilatura(html: str) -> Optional[str]:
    """trafilatura提取正文Markdown(质量优于html2text), 失败返回None — 小欧 2026-07-17"""
    if _TRAFILATURA is None:
        return None
    try:
        md = _TRAFILATURA.extract(html, output_format="markdown", include_comments=False)
        if md and len(md.strip()) > 50:
            return md.strip()
    except Exception:
        pass
    return None


def _clean_markdown_content(text: str) -> str:
    """清理markdown导航噪音 — 小沈 2026-07-05 (html2text已处理实体和注释，简化)"""
    text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'\bnew\b\s*\|\s*\bpast\b\s*\|\s*\bcomments?\b[^\n]*?(?:login|submit)\b[^\n]*?1\.', '1.', text, flags=re.IGNORECASE)
    text = re.sub(r'\bask\b\s*\|\s*\bshow\b\s*\|\s*\bjobs?\b[^\n]*?(?:login|submit)\b[^\n]*?1\.', '1.', text, flags=re.IGNORECASE)
    text = re.sub(r'\d+\s+points?\s+by\s+\S+[^\n]*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\|?\s*\d+\s+comments?\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\|?\s*hide\?id=\S+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()


def _balanced_braces_extract(text: str, start: int = 0) -> Optional[str]:
    """从start位置找第一个{，返回平衡大括号匹配的完整JSON字符串 — 小沈 2026-07-08

    正确处理嵌套大括号和字符串中的转义引号，
    解决旧版正则{.*?}在嵌套JSON时截断的问题。
    """
    brace_start = text.find('{', start)
    if brace_start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(brace_start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == '\\' and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if not in_string:
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return text[brace_start:i + 1]
    return None


def _extract_ssr_json_content(html: str) -> Optional[str]:
    """从SPA站点的SSR JSON中提取文章内容 — 小欧 2026-07-08
    小沈 2026-07-08: 替换为正则+平衡大括号匹配，支持嵌套JSON

    支持:
      - window.__INITIAL_STATE__ (CSDN等Vue SSR)
      - window.__NUXT__ (掘金等Nuxt.js)
      - <script id="__NEXT_DATA__"> (Next.js)
    递归扫描JSON中所有 title+description/summary 字段对。
    """
    # 各SSR框架：找到前缀后，用平衡大括号匹配提取完整JSON
    prefixes = [
        r'window\.__INITIAL_STATE__\s*=\s*',
        r'window\.__NUXT__\s*=\s*',
        r'<script\s+id="__NEXT_DATA__"[^>]*>\s*',
    ]
    articles = []
    for pat in prefixes:
        m = re.search(pat, html, re.DOTALL)
        if not m:
            continue
        json_str = _balanced_braces_extract(html, m.end())
        if not json_str:
            continue
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            continue
        _scan_json_for_articles(data, articles, max_items=50)
        if articles:
            break

    if not articles:
        return None

    lines = []
    for art in articles:
        t = art.get("title", "").strip()
        d = art.get("desc", "").strip()
        if not t or len(t) < 4:
            continue
        if d:
            lines.append(f"- {t}: {d[:300]}")
        else:
            lines.append(f"- {t}")
    return "\n".join(lines) if lines else None


def _scan_json_for_articles(obj, results, max_items=50, depth=0):
    """递归扫描JSON找 title+description/summary 文章对 — 小欧 2026-07-08"""
    if depth > 6 or len(results) >= max_items:
        return
    if isinstance(obj, dict):
        title = obj.get("title") or obj.get("articleTitle") or ""
        if isinstance(title, str) and len(title) > 4:
            desc = (obj.get("description") or obj.get("summary")
                    or obj.get("desc") or obj.get("digest") or "")
            if isinstance(desc, str):
                results.append({"title": title.strip(), "desc": desc.strip()})
        for v in obj.values():
            _scan_json_for_articles(v, results, max_items, depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            _scan_json_for_articles(item, results, max_items, depth + 1)


def _html_to_markdown(html: str) -> str:
    """html2text 转换HTML为Markdown — 小沈 2026-07-05
    小欧 2026-07-08: 加入_extract_ssr_json_content兜底
    小欧 2026-07-17: 优先trafilatura提取正文(质量优于html2text), 失败回落原链路"""
    md = _extract_via_trafilatura(html)
    if md:
        return _clean_markdown_content(md)
    main_html = _extract_main_content(html)
    if main_html:
        return _clean_markdown_content(_convert_html2text(main_html))

    ssr_md = _extract_ssr_json_content(html)
    if ssr_md:
        return ssr_md

    return _clean_markdown_content(_convert_html2text(html))


def _has_embedded_state(html: str) -> bool:
    """检查HTML是否含有可在HTTP层提取的SSR JSON — 小沈 2026-07-08 (从rolling-reader借鉴)"""
    patterns = [
        r'window\.__INITIAL_STATE__\s*=\s*\{',
        r'window\.__NUXT__\s*=\s*\{',
        r'<script id="__NEXT_DATA__"',
    ]
    for pat in patterns:
        if re.search(pat, html, re.IGNORECASE):
            return True
    return False


def _needs_browser(html: str, status_code: int, mime: str) -> tuple:
    """检测页面是否需要浏览器渲染 — 小沈 2026-07-08 (从rolling-reader http.py needs_browser() V4借鉴)

    Returns:
        (needs_browser: bool, reason: str)
    """
    if not html:
        return False, ""

    if "application/json" in mime:
        return False, ""

    if status_code in (400, 401, 403, 407):
        return True, f"http_{status_code}"

    if len(html) < 500:
        return True, "short_html"

    # SSR JSON override: 有嵌入state的页面无需浏览器
    if _has_embedded_state(html):
        return False, ""

    # 空标题检测 — 小沈 2026-07-08
    title_match = re.search(r'<title[^>]*>\s*</title>', html, re.IGNORECASE)
    if title_match and len(html) < 20000:
        return True, "empty_title"

    lower_html = html.lower()
    js_markers = ['id="app"', "id='app'", 'id="root"', "id='root'",
                  'id="__next"', "id='__next'",
                  'id="__nuxt"', "id='__nuxt'",
                  "enable javascript", "you need javascript", "javascript is required"]
    for marker in js_markers:
        if marker in lower_html:
            return True, "js_marker"

    # Body 脚本占比检测 — 小沈 2026-07-08
    body_m = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
    if body_m:
        body_html = body_m.group(1)
        scripts = re.findall(r'<script[^>]*>.*?</script>', body_html, re.DOTALL | re.IGNORECASE)
        script_text_len = sum(len(s) for s in scripts)
        if len(body_html) > 0 and script_text_len / len(body_html) > 0.50:
            return True, f"high_script_ratio:{script_text_len/max(len(body_html),1):.0%}"

    # Text ratio 分析
    text_content = re.sub(r'<[^>]+>', ' ', html)
    text_content = re.sub(r'\s+', ' ', text_content).strip()
    text_len = len(text_content)
    html_len = len(html)
    text_ratio = text_len / max(html_len, 1)

    if text_ratio < 0.005:
        return True, f"ratio_near_zero:{text_ratio:.4f}"

    if text_len < 200 and text_ratio < 0.15:
        return True, f"tiny_shell:tlen={text_len}"

    if html_len > 50000 and text_ratio < 0.018 and text_len < 3000:
        return True, f"large_page_low_ratio:{text_ratio:.4f}"

    # 空 main 容器检测（轻量正则，避免调_extract_main_content重复解析）— 小沈 2026-07-08
    main_tags = re.findall(r'<(?:main|article)[^>]*>(.*?)</(?:main|article)>', html, re.DOTALL | re.IGNORECASE)
    for main_html in main_tags:
        main_text = re.sub(r'<[^>]+>', ' ', main_html)
        main_text = re.sub(r'\s+', ' ', main_text).strip()
        if len(main_text) < 50 and text_len > 300:
            return True, "empty_main"

    return False, ""


def _build_fetch_webpage_llm_data(
    exec_code: str, duration_ms: int, url: str = "", extract_format: str = "markdown",
    status_code: int = 0, truncated: bool = False,
    err_code: str = "", detail: str = "", hint: str = "",
    mime_type: str = "",
    prompt: Optional[str] = None, js_render: bool = False, timeout: int = 30,
    proxy: Optional[str] = None,
) -> Dict[str, Any]:
    """fetch_webpage的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小欧 2026-07-05 过滤None值"""
    _act_params = {"url": url, "extract_format": extract_format, "js_render": js_render, "timeout": timeout}
    if prompt is not None:
        _act_params["prompt"] = prompt
    if proxy is not None:
        _act_params["proxy"] = proxy
    if exec_code == "error":
        return {
            "summary": f"获取{url}网页，失败",
            "action": {"tool": "fetchpage", "tool_zh": "获取网页", "target": url, "params": _act_params},
            "status": {"exec_code": "error", "message": "获取网页失败", "code": err_code, "detail": detail, "hint": hint if hint else "请检查URL和网络连接"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    if exec_code == "warning":
        base_msg = f"获取网页{url}内容，成功但有警告"
        if mime_type:
            base_msg = f"获取{url}资源，成功但有警告: {mime_type}，HTTP {status_code}"
        return {
            "summary": base_msg,
            "action": {"tool": "fetchpage", "tool_zh": "获取网页", "target": url, "params": _act_params},
            "status": {"exec_code": "warning", "message": "获取网页完成但有警告", "code": "", "detail": detail, "hint": hint},
            "duration_ms": duration_ms,
            "metrics": {"status_code": {"value": status_code, "text": f"HTTP {status_code}"}} if status_code else {},
        }
    if mime_type:
        summary = f"获取{url}资源，成功: {mime_type}，HTTP {status_code}"
    else:
        summary = f"获取网页{url}内容成功: {extract_format}格式，HTTP {status_code}"
    if truncated:
        summary += "（内容有部分截断）"
    return {
        "summary": summary,
        "action": {"tool": "fetchpage", "tool_zh": "获取网页", "target": url, "params": _act_params},
        "status": {"exec_code": "success", "message": "获取网页内容成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"status_code": {"value": status_code, "text": f"HTTP {status_code}"}},
    }


def _extract_html_content(html_content: str, extract_format: str, max_tokens: int) -> Tuple[str, bool]:
    """3路格式提取+截断检查 — 小欧 2026-06-22"""
    if extract_format == "html":
        content = html_content
    elif extract_format == "text":
        content = SCRIPT_TAG_PATTERN.sub('', html_content)
        content = STYLE_TAG_PATTERN.sub('', content)
        content = HTML_TAG_PATTERN.sub(' ', content)
        content = MULTI_WHITESPACE_PATTERN.sub(' ', content).strip()
    else:
        content = _html_to_markdown(html_content)
    max_len = max_tokens * 4
    truncated = len(content) > max_len
    if truncated:
        content = content[:max_len]
    return content, truncated


def _build_media_result(url: str, mime: str, raw_bytes: bytes) -> Dict[str, Any]:
    """构建图片/PDF的base64附件响应 — 小欧 2026-06-22 — 小欧 2026-07-06 data仅保留content，其余通过summary
    小沈 2026-07-08: 删除未使用的response_status参数"""
    b64 = base64.b64encode(raw_bytes).decode("ascii")
    data = {
        "content": f"[{mime} 文件,大小: {len(raw_bytes)} 字节]",
    }
    other_data = {
        "attachment": {
            "type": "base64",
            "mime": mime,
            "data": b64,
            "filename": url.split("/")[-1].split("?")[0] or "download",
        }
    }
    return {"data": data, "other_data": other_data}


def _pw_run(url: str, proxy: Optional[str], timeout: float,
            extract_format: str, max_tokens: int) -> Dict[str, Any]:
    """Playwright同步内核: 独立Proactor子循环跑, 规避主循环Selector约束 — 小欧 2026-07-17"""
    async def _go() -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        loop.set_exception_handler(lambda loop, ctx: None)   # 吞掉transport后台Task泄漏(红字)
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return {"error": True, "error_detail": "js_render需要安装Playwright", "params": {"url": url}, "err_code": ERR_NETWORK_JS_RENDER, "detail": "js_render需要安装Playwright"}
        try:
            browser_config = {
                "headless": True,
                "proxy": {"server": proxy} if proxy else None,
            }
            async with async_playwright() as p:
                browser = await p.chromium.launch(**browser_config)
                try:
                    page = await browser.new_page()
                    await page.set_default_timeout(timeout * 1000)
                    await page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
                    current_url = page.url
                    if current_url and current_url != url:
                        is_valid, err, _ = validate_url(current_url)
                        if not is_valid:
                            return {"error": True, "error_detail": f"重定向到不安全地址: {err or 'URL无效'}", "params": {"url": url}, "err_code": ERR_INVALID_URL, "detail": err}
                    html_content = await page.content()
                finally:
                    await browser.close()
            content, truncated = _extract_html_content(html_content, extract_format, max_tokens)
            return {
                "html_content": html_content,
                "extracted_content": content,
                "truncated": truncated,
                "content_type": "text/html",
                "status_code": 200,
            }
        except Exception as e:
            return {"error": True, "error_detail": str(e), "params": {"url": url}, "err_code": ERR_NETWORK_JS_RENDER, "detail": str(e)}

    if sys.platform == "win32" and hasattr(asyncio, "ProactorEventLoop"):
        loop = asyncio.ProactorEventLoop()
        try:
            return loop.run_until_complete(_go())
        finally:
            loop.close()
    return asyncio.run(_go())


async def _fetch_via_playwright(url: str, proxy: Optional[str], timeout: float,
                                extract_format: str, max_tokens: int) -> Dict[str, Any]:
    """Playwright路径封装(隔离执行) — 小欧 2026-07-17 改为子循环隔离"""
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: _pw_run(url, proxy, timeout, extract_format, max_tokens))
    except Exception as e:
        return {"error": True, "error_detail": str(e), "params": {"url": url}, "err_code": ERR_NETWORK_JS_RENDER, "detail": str(e)}


async def _fetch_via_external_reader(url: str, timeout: int) -> Optional[str]:
    """外部抓取API兜底(Jina Reader, 零本地浏览器, 可选) — 小欧 2026-07-17"""
    try:
        async with create_http_client(timeout_sec=timeout) as client:
            r = await client.get(f"https://r.jina.ai/{url}")
            if r.status_code == 200:
                md = r.text.strip()
                if len(md) > 50:
                    return md
    except Exception:
        pass
    return None


async def fetchpage(
    url: str,
    prompt: Optional[str] = None,
    extract_format: str = "markdown",
    js_render: bool = False,
    timeout: int = 30,
    proxy: Optional[str] = None,
) -> Dict[str, Any]:
    """获取网页内容 — 小健 2026-06-21 — 小欧 2026-06-22 独立文件"""
    max_tokens = WEB_FETCH_MAX_CHARS // 4  # 字符上限=WEB_FETCH_MAX_CHARS(10000)→max_len=10000字符(原8000 token→32000字符已偏大, 归一化治理 2026-07-15)
    timeout_valid, timeout_err, _ = validate_timeout(timeout, "fetchpage")
    if not timeout_valid:
        llm_data = _build_fetch_webpage_llm_data("error", 0, url, extract_format, err_code=ERR_INVALID_URL, detail=timeout_err, hint="请检查超时设置", prompt=prompt, js_render=js_render, timeout=timeout, proxy=proxy)
        return build_error(data={}, llm_data=llm_data)

    proxy_valid, proxy_err, _ = validate_proxy(proxy)
    if not proxy_valid:
        llm_data = _build_fetch_webpage_llm_data("error", 0, url, extract_format, err_code=ERR_INVALID_URL, detail=proxy_err, hint="请检查代理配置", prompt=prompt, js_render=js_render, timeout=timeout, proxy=proxy)
        return build_error(data={}, llm_data=llm_data)

    t0 = _time_mod.perf_counter()

    try:
        is_valid, error_msg, warning_msg = validate_url(url)
        if not is_valid:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_fetch_webpage_llm_data("error", duration_ms, url, extract_format, err_code=ERR_INVALID_URL, detail=error_msg or "URL格式无效", hint="请检查URL格式", prompt=prompt, js_render=js_render, timeout=timeout, proxy=proxy)
            return build_error(data={}, llm_data=llm_data)
        if warning_msg:
            logger.warning(f"[fetchpage] {warning_msg}")

        net_info = check_network()
        if not net_info["connected"]:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_fetch_webpage_llm_data("error", duration_ms, url, extract_format, err_code=ERR_NETWORK_DOWN, detail="网络不可用", hint="请检查网络连接", prompt=prompt, js_render=js_render, timeout=timeout, proxy=proxy)
            return build_error(data={}, llm_data=llm_data)

        headers = {
            "User-Agent": TOOL_BROWSER_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
            "Accept-Encoding": "gzip, deflate",
        }

        playwright_result = None
        if js_render:
            playwright_result = await _fetch_via_playwright(url, proxy, timeout, extract_format, max_tokens)
        if js_render and playwright_result.get("error"):
            # 浏览器渲染失败, 先尝试外部API兜底(Jina Reader) — 小欧 2026-07-17
            external_md = await _fetch_via_external_reader(url, timeout)
            if external_md and len(external_md) >= 200:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_fetch_webpage_llm_data("success", duration_ms, url, extract_format, 200, False, detail="内容来自外部API(Jina Reader)兜底", prompt=prompt, js_render=js_render, timeout=timeout, proxy=proxy)
                return build_success(data={"content": external_md}, llm_data=llm_data)
            logger.warning(f"js_render渲染失败, 外部API兜底失败, 回落静态抓取: {playwright_result.get('detail')}")
            # 不return, 继续下方静态抓取
        elif js_render and not playwright_result.get("error"):
            # js_render成功: 取L1渲染结果, 不进静态抓取 — 小欧 2026-07-17
            html_content = playwright_result["html_content"]
            extracted_content = playwright_result["extracted_content"]
            truncated = playwright_result["truncated"]
            content_type = playwright_result["content_type"]
            status_code = playwright_result["status_code"]
            mime = content_type.split(";")[0].strip().lower() if content_type else ""
        if not (js_render and playwright_result is not None and not playwright_result.get("error")):
            async with create_http_client(timeout_sec=timeout, proxy=proxy) as client:
                actual_headers = dict(headers)

                # 流式请求 + 读取硬截断5MB防OOM — 小沈 2026-07-05
                async with client.stream("GET", url, headers=actual_headers) as resp:
                    content_type = resp.headers.get("content-type", "")
                    mime = content_type.split(";")[0].strip().lower() if content_type else ""

                    if resp.status_code == 403 and resp.headers.get("cf-mitigated") == "challenge":
                        logger.info(f"[fetchpage] Cloudflare挑战检测,降级UA重试: {url}")
                        actual_headers["User-Agent"] = "Chrome/120.0.0.0"
                        cf_resp = await client.get(url, headers=actual_headers)
                        cf_resp.raise_for_status()
                        content_type = cf_resp.headers.get("content-type", "")
                        mime = content_type.split(";")[0].strip().lower() if content_type else ""
                        if mime and (mime.startswith("image/") or mime in ("application/pdf",)):
                            raw_bytes = cf_resp.content
                            media_result = _build_media_result(url, mime, raw_bytes)
                            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                            llm_data = _build_fetch_webpage_llm_data("success", duration_ms, url, extract_format, cf_resp.status_code, mime_type=mime, prompt=prompt, js_render=js_render, timeout=timeout, proxy=proxy)
                            return build_success(data=media_result["data"], llm_data=llm_data, other_data=media_result["other_data"])
                        html_content = cf_resp.text[:5_242_880]
                        status_code = cf_resp.status_code
                    else:
                        resp.raise_for_status()

                        MAX_CONTENT_LENGTH = 100 * 1024 * 1024
                        cl = resp.headers.get("content-length")
                        if cl and int(cl) > MAX_CONTENT_LENGTH:
                            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                            return build_error(data={}, llm_data=_build_fetch_webpage_llm_data("error", duration_ms, url, extract_format, err_code=ERR_NETWORK_REQUEST_ERROR, detail=f"内容过大({int(int(cl)/1024/1024)}MB)", hint="请使用更具体的URL或减少内容", prompt=prompt, js_render=js_render, timeout=timeout, proxy=proxy))

                        if mime and (mime.startswith("image/") or mime in ("application/pdf",)):
                            raw_bytes = await resp.aread()
                            media_result = _build_media_result(url, mime, raw_bytes)
                            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                            llm_data = _build_fetch_webpage_llm_data("success", duration_ms, url, extract_format, resp.status_code, mime_type=mime, prompt=prompt, js_render=js_render, timeout=timeout, proxy=proxy)
                            return build_success(data=media_result["data"], llm_data=llm_data, other_data=media_result["other_data"])

                        MAX_READ_BYTES = 5_242_880
                        chunks, total = [], 0
                        async for chunk in resp.aiter_bytes():
                            remaining = MAX_READ_BYTES - total
                            if remaining <= 0:
                                break
                            chunks.append(chunk[:remaining] if len(chunk) > remaining else chunk)
                            total += len(chunk)
                        html_content = b''.join(chunks).decode('utf-8', errors='replace')
                        status_code = resp.status_code

            # 自动Playwright回退 — 小沈 2026-07-08 (从rolling-reader needs_browser() V4借鉴)
            pw_content = None
            if _needs_browser(html_content, status_code, mime)[0]:
                logger.info(f"[fetchpage] SPA空壳检测,自动回退Playwright: {url}")
                pw_res = await _fetch_via_playwright(url, proxy, timeout, extract_format, max_tokens)
                if not pw_res.get("error"):
                    pw_content = pw_res
                else:
                    ext_md = await _fetch_via_external_reader(url, timeout)   # 小欧 2026-07-17 L2兜底
                    if ext_md:
                        pw_content = {"extracted_content": ext_md, "truncated": False, "content_type": "text/markdown", "status_code": 200}

            if pw_content:
                # HTTP HTML先提取做fallback — 小沈 2026-07-08
                http_extracted, http_truncated = _extract_html_content(html_content, extract_format, max_tokens)
                pw_extracted = pw_content["extracted_content"]
                # Playwright提取内容显著更好才用它,否则回退HTTP HTML
                if len(pw_extracted) >= len(http_extracted) * 1.5:
                    extracted_content = pw_extracted
                    truncated = pw_content["truncated"]
                    content_type = pw_content.get("content_type", content_type)
                    status_code = pw_content.get("status_code", status_code)
                else:
                    extracted_content, truncated = http_extracted, http_truncated
            else:
                extracted_content, truncated = _extract_html_content(html_content, extract_format, max_tokens)

        # =============================================================================
        # 数据设计：data仅保留content纯数据，format/content_type/truncated通过summary传递
        # summary 示例: "成功获取网页内容(markdown格式, HTTP 200，已截断)"
        # — 小欧 2026-07-06
        # =============================================================================
        result_data = {
            "content": extracted_content,
        }

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        # 内容<100字走warning，<30字data置空 — 小沈 2026-07-08
        content_len = len(extracted_content)
        if content_len >= 100:
            # ---- observation_formatter route -------------------------------------------
            # branch: #2 raw str
            # trigger: "content" in data and isinstance(data["content"], str)
            # handler: inline — 直接返回 data["content"], OBS_MAX_STRING_LENGTH 截断
            # file:    observation_formatter.py:117-122
            # ------------------------------------------------------------------------------
            llm_data = _build_fetch_webpage_llm_data("success", duration_ms, url, extract_format, status_code, truncated, prompt=prompt, js_render=js_render, timeout=timeout, proxy=proxy)
            return build_success(data=result_data, llm_data=llm_data)
        result_data = {} if content_len < 30 else result_data
        llm_data = _build_fetch_webpage_llm_data("warning", duration_ms, url, extract_format, status_code, truncated, hint="尝试其他的网站地址", prompt=prompt, js_render=js_render, timeout=timeout, proxy=proxy)
        return build_warning(data=result_data, llm_data=llm_data)

    except (httpx.TimeoutException, asyncio.TimeoutError):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_fetch_webpage_llm_data("error", duration_ms, url, extract_format, err_code=ERR_NETWORK_TIMEOUT, detail=f"超时({timeout:.1f}秒)", hint="可增大timeout参数重试", prompt=prompt, js_render=js_render, timeout=timeout, proxy=proxy)
        return build_error(data={}, llm_data=llm_data)
    except httpx.HTTPStatusError as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        _sc = e.response.status_code
        if _sc == 429:
            _hint = "请求过于频繁(限流),请稍后重试或降低请求频率"
        elif 400 <= _sc < 500:
            # hint不重复具体状态码(detail已有"HTTP {_sc}"),仅给可行动建议 — 小欧 2026-07-17
            _hint = "客户端请求错误,请检查URL/请求方法与参数"
        elif 500 <= _sc < 600:
            _hint = "服务器暂时不可用,可稍后重试或换用其他地址"
        else:
            _hint = "请检查URL和服务器状态"  # 兜底 — 小欧 2026-07-17
        llm_data = _build_fetch_webpage_llm_data("error", duration_ms, url, extract_format, err_code=ERR_NETWORK_HTTP_ERROR, detail=f"HTTP {_sc}", hint=_hint, prompt=prompt, js_render=js_render, timeout=timeout, proxy=proxy)
        return build_error(data={}, llm_data=llm_data)
    except httpx.RequestError as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_fetch_webpage_llm_data("error", duration_ms, url, extract_format, err_code=ERR_NETWORK_REQUEST_ERROR, detail=f"{type(e).__name__}: {str(e) or repr(e)}", hint="请检查URL和网络连接", prompt=prompt, js_render=js_render, timeout=timeout, proxy=proxy)
        return build_error(data={}, llm_data=llm_data)
    except Exception as e:
        logger.error(f"[fetchpage] 未知错误: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_fetch_webpage_llm_data("error", duration_ms, url, extract_format, err_code=ERR_NET_UNKNOWN, detail=f"{type(e).__name__}: {str(e) or repr(e)}", hint="请检查URL和网络连接", prompt=prompt, js_render=js_render, timeout=timeout, proxy=proxy)
        return build_error(data={}, llm_data=llm_data)