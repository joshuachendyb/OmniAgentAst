# 测试 fetchpage 架构增强: trafilatura优先 + Playwright显式Proactor隔离 + 外部API兜底 + SPA三级降级
# 小欧 2026-07-17
# 设计对齐: doc-7月优化/fetchpage网页抓取架构隔离与多级Fallback完整设计方案-小欧-2026-07-17.md
import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tools.network import fetch_webpage as fw


def _run(coro):
    return asyncio.run(coro)


# ══════════════════════════════════════════════════════════
# ① trafilatura 优先 + 兜底（L0 增强，零退化）
# ══════════════════════════════════════════════════════════
def test_trafilatura_priority():
    """_html_to_markdown 优先用 trafilatura 结果"""
    html = "<html><body><article><p>正文内容</p></article></body></html>"
    with patch.object(fw, "_extract_via_trafilatura", return_value="TRAFLATURA_MD"):
        result = fw._html_to_markdown(html)
    assert result == "TRAFLATURA_MD"


def test_trafilatura_none_fallback_html2text():
    """trafilatura 返回None时回落 html2text 主链路（零退化）"""
    html = "<html><body><div id='main'><p>主内容区域</p></div></body></html>"
    with patch.object(fw, "_extract_via_trafilatura", return_value=None):
        result = fw._html_to_markdown(html)
    assert "主内容区域" in result


def test_trafilatura_missing_import_safe():
    """trafilatura 未装(_TRAFILATURA=None)时返回None不崩"""
    with patch.object(fw, "_TRAFILATURA", None):
        assert fw._extract_via_trafilatura("<html></html>") is None


def test_trafilatura_extract_exception_safe():
    """trafilatura.extract 抛异常时返回None不崩（异常安全）"""
    fake = MagicMock()
    fake.extract.side_effect = RuntimeError("boom")
    with patch.object(fw, "_TRAFILATURA", fake):
        assert fw._extract_via_trafilatura("<html></html>") is None


# ══════════════════════════════════════════════════════════
# ⑤ 外部 API 兜底（L2）
# ══════════════════════════════════════════════════════════
def test_external_reader_success():
    """外部API 200 返回 markdown"""
    resp = MagicMock(); resp.status_code = 200; resp.text = "JINA_MD " * 10
    client = AsyncMock(); client.__aenter__.return_value = client; client.get.return_value = resp
    with patch.object(fw, "create_http_client", return_value=client):
        assert _run(fw._fetch_via_external_reader("https://x.com", 30)) == ("JINA_MD " * 10).strip()


def test_external_reader_fail_none():
    """外部API 非200或异常返回None（异常安全）"""
    resp = MagicMock(); resp.status_code = 500; resp.text = ""
    client = AsyncMock(); client.__aenter__.return_value = client; client.get.return_value = resp
    with patch.object(fw, "create_http_client", return_value=client):
        assert _run(fw._fetch_via_external_reader("https://x.com", 30)) is None
    client2 = AsyncMock(); client2.__aenter__.side_effect = Exception("down")
    with patch.object(fw, "create_http_client", return_value=client2):
        assert _run(fw._fetch_via_external_reader("https://x.com", 30)) is None


# ══════════════════════════════════════════════════════════
# ⑥ SPA 三级降级: L1 Playwright失败 -> L2 外部API成功 -> 用L2
# ══════════════════════════════════════════════════════════
def test_spa_l1_fail_l2_ok():
    """SPA空壳: L1 Playwright失败 -> L2 外部API成功 -> 采用L2内容"""
    short_html = "<html><body><div id='app'></div></body></html>"
    ctx = AsyncMock(); ctx.__aenter__.return_value = ctx
    ctx.status_code = 200; ctx.headers = {"content-type": "text/html"}
    ctx.raise_for_status = MagicMock()
    ctx.aiter_bytes = AsyncMock(return_value=[short_html.encode()])
    client = AsyncMock(); client.__aenter__.return_value = client; client.stream.return_value = ctx
    with patch.object(fw, "create_http_client", return_value=client), \
         patch.object(fw, "check_network", return_value={"connected": True}), \
         patch.object(fw, "_needs_browser", return_value=(True, "empty_main")), \
         patch.object(fw, "_fetch_via_playwright", new=AsyncMock(return_value={"error": True, "err_code": "X"})), \
         patch.object(fw, "_fetch_via_external_reader", new=AsyncMock(return_value="L2_CONTENT_LONG_ENOUGH_XYZ " * 10)):
            result = _run(fw.fetchpage(url="https://x.com", js_render=True))
    assert "L2_CONTENT_LONG_ENOUGH_XYZ" in result["data"]["content"]


# ══════════════════════════════════════════════════════════
# ④ 显式 Proactor 隔离（C1 精髓 = nbconvert 范式，Windows 专用）
# ══════════════════════════════════════════════════════════
@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_pw_run_proactor_isolation():
    """Windows下 _pw_run 显式创建 ProactorEventLoop 隔离运行（不依赖全局策略）"""
    fake_loop = MagicMock()
    captured = {}

    def _rtc(coro):
        captured["coro"] = coro
        coro.close()  # 消费协程, 消除 never-awaited RuntimeWarning
        return {
            "html_content": "<html>rendered</html>", "extracted_content": "x",
            "truncated": False, "content_type": "text/html", "status_code": 200}

    fake_loop.run_until_complete = MagicMock(side_effect=_rtc)
    fake_browser = AsyncMock(); fake_page = AsyncMock()
    fake_page.content = AsyncMock(return_value="<html>rendered</html>")
    fake_page.goto = AsyncMock(); fake_page.set_default_timeout = AsyncMock(); fake_page.url = "https://x.com"
    fake_browser.new_page = AsyncMock(return_value=fake_page); fake_browser.close = AsyncMock()
    fake_pw = AsyncMock(); fake_pw.chromium.launch = AsyncMock(return_value=fake_browser)
    fake_ctx = AsyncMock(); fake_ctx.__aenter__.return_value = fake_ctx
    fake_pw.__aenter__.return_value = fake_ctx
    with patch.dict(sys.modules, {"playwright.async_api": MagicMock(async_playwright=lambda: fake_ctx)}), \
         patch.object(fw.asyncio, "ProactorEventLoop", return_value=fake_loop) as mp:
        res = fw._pw_run("https://x.com", None, 30, "markdown")
    assert mp.called, "应显式创建 ProactorEventLoop(隔离), 而非依赖 asyncio.run"
    assert res["status_code"] == 200


# ═════════════════════════════════════════════════════════
# ⑦ 分支与组合全覆盖（绝不退化）— 小欧 2026-07-17
# ═════════════════════════════════════════════════════════
def test_trafilatura_short_fallback():
    """trafilatura 提取过短(<50)返回None, 回落 html2text 主链路 — 小欧 2026-07-17"""
    html = "<html><body><div id='main'><p>主内容区域足够长用于html2text兜底验证渲染</p></div></body></html>"
    with patch.object(fw, "_extract_via_trafilatura", return_value=None):
        result = fw._html_to_markdown(html)
    assert "主内容区域" in result


def _fake_pw_ctx(page_url="https://x.com", content="<html>rendered</html>", launch=None):
    fake_page = AsyncMock()
    fake_page.content = AsyncMock(return_value=content)
    fake_page.goto = AsyncMock()
    fake_page.set_default_timeout = AsyncMock()
    fake_page.url = page_url
    fake_browser = AsyncMock()
    fake_browser.new_page = AsyncMock(return_value=fake_page)
    fake_browser.close = AsyncMock()
    fake_pw = AsyncMock()
    fake_pw.chromium.launch = AsyncMock(return_value=fake_browser) if launch is None else launch
    fake_ctx = AsyncMock()
    fake_ctx.__aenter__.return_value = fake_ctx
    fake_pw.__aenter__.return_value = fake_ctx
    return fake_ctx


def test_pw_run_redirect_unsafe():
    """validate_url 不通过 → error / ERR_INVALID_URL（早期守卫） — 小欧 2026-07-17"""
    fake_ctx = _fake_pw_ctx(page_url="http://127.0.0.1:1")
    with patch.dict(sys.modules, {"playwright.async_api": MagicMock(async_playwright=lambda: fake_ctx)}), \
         patch.object(fw, "validate_url", return_value=(False, "bad", None)):
        res = fw._pw_run("https://x.com", None, 30, "markdown")
    assert res["error"] is True
    assert res["err_code"] == "ERR_INVALID_URL"


def test_pw_run_render_exception():
    """渲染异常 → error / ERR_NETWORK_JS_RENDER — 小欧 2026-07-17"""
    fake_pw = AsyncMock()
    fake_pw.chromium.launch = AsyncMock(side_effect=RuntimeError("launch fail"))
    fake_pw.__aenter__.return_value = fake_pw  # p.chromium.launch 即此对象
    with patch.dict(sys.modules, {"playwright.async_api": MagicMock(async_playwright=lambda: fake_pw)}):
        res = fw._pw_run("https://x.com", None, 30, "markdown")
    assert res["error"] is True
    assert res["err_code"] == "ERR_NETWORK_JS_RENDER"


def test_fetch_via_playwright_catches_exception():
    """_pw_run 抛异常 → _fetch_via_playwright 捕获返回 error — 小欧 2026-07-17"""
    with patch.object(fw, "_pw_run", side_effect=RuntimeError("boom")):
        res = _run(fw._fetch_via_playwright("https://x.com", None, 30, "markdown"))
    assert res["error"] is True
    assert res["err_code"] == "ERR_NETWORK_JS_RENDER"


async def _aiter_bytes(data):
    yield data


def _static_client_ctx(short_html):
    ctx = AsyncMock(); ctx.__aenter__.return_value = ctx; ctx.__aexit__.return_value = False
    ctx.status_code = 200; ctx.headers = {"content-type": "text/html"}
    ctx.raise_for_status = MagicMock()
    ctx.aiter_bytes = lambda: _aiter_bytes(short_html.encode())
    client = AsyncMock(); client.__aenter__.return_value = client; client.__aexit__.return_value = False
    client.stream = MagicMock(return_value=ctx)
    return client


def _patch_http(mocker, client):
    return mocker


def test_auto_fallback_l1_ok():
    """自动回退: _needs_browser=True, L1成功 → 用L1内容 — 小欧 2026-07-17"""
    short_html = "<html><body><div id='app'></div></body></html>"
    client = _static_client_ctx(short_html)
    with patch.object(fw, "create_http_client", return_value=client), \
         patch.object(fw, "check_network", return_value={"connected": True}), \
         patch.object(fw, "_needs_browser", return_value=(True, "empty_main")), \
         patch.object(fw, "_fetch_via_playwright", new=AsyncMock(return_value={"html_content": "<html>rendered</html>", "extracted_content": "X" * 200, "truncated": False, "content_type": "text/html", "status_code": 200})), \
         patch.object(fw, "_fetch_via_external_reader", new=AsyncMock(return_value=None)):
        result = _run(fw.fetchpage(url="https://x.com"))
    assert "X" * 200 in result["data"]["content"]


def test_auto_fallback_l1_fail_l2_ok():
    """自动回退: L1失败→L2成功 → 用L2内容 — 小欧 2026-07-17"""
    short_html = "<html><body><div id='app'></div></body></html>"
    client = _static_client_ctx(short_html)
    with patch.object(fw, "create_http_client", return_value=client), \
         patch.object(fw, "check_network", return_value={"connected": True}), \
         patch.object(fw, "_needs_browser", return_value=(True, "empty_main")), \
         patch.object(fw, "_fetch_via_playwright", new=AsyncMock(return_value={"error": True, "err_code": "X"})), \
         patch.object(fw, "_fetch_via_external_reader", new=AsyncMock(return_value="L2_CONTENT_LONG_ENOUGH_XYZ " * 10)):
        result = _run(fw.fetchpage(url="https://x.com"))
    assert "L2_CONTENT_LONG_ENOUGH_XYZ" in result["data"]["content"]


def test_auto_fallback_l1_fail_l2_fail():
    """自动回退: L1失败→L2失败 → 回落HTTP静态 — 小欧 2026-07-17"""
    long_html = "<html><body><div id='main'>" + "静态HTTP提取内容用于验证回落，" * 10 + "</div></body></html>"
    client = _static_client_ctx(long_html)
    with patch.object(fw, "create_http_client", return_value=client), \
         patch.object(fw, "check_network", return_value={"connected": True}), \
         patch.object(fw, "_needs_browser", return_value=(True, "empty_main")), \
         patch.object(fw, "_fetch_via_playwright", new=AsyncMock(return_value={"error": True, "err_code": "X"})), \
         patch.object(fw, "_fetch_via_external_reader", new=AsyncMock(return_value=None)):
        result = _run(fw.fetchpage(url="https://x.com"))
    assert "静态HTTP提取内容用于验证回落" in result["data"]["content"]


def test_js_render_l1_ok():
    """js_render=True, L1成功 → 用L1内容 — 小欧 2026-07-17"""
    with patch.object(fw, "check_network", return_value={"connected": True}), \
         patch.object(fw, "_fetch_via_playwright", new=AsyncMock(return_value={"html_content": "<html>rendered</html>", "extracted_content": "Y" * 200, "truncated": False, "content_type": "text/html", "status_code": 200})):
        result = _run(fw.fetchpage(url="https://x.com", js_render=True))
    assert "Y" * 200 in result["data"]["content"]
