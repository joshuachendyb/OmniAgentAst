# -*- coding: utf-8 -*-
"""httpget observation 行×列回归测试 — 小欧 2026-07-20

验证 httpget(章9.4) 落地后:
1. Tool 输出零限制(JSON 完整返回, 仅 3.4 硬安全网 INER_HTTPGET_JSON_PREVIEW_MAX_BYTES 预览截断置 _truncated+_reason)
2. observation_formatter._format_httpget_result 行×列(OBS_HTTPGET_MAX_ROWS=200行 / OBS_HTTPGET_MAX_ROW_CHARS=2000字符)+ 两态说明行
"""
import json

from app.services.agent import observation_formatter as of
from app.tools.tool_constants import OBS_HTTPGET_MAX_ROWS, OBS_HTTPGET_MAX_ROW_CHARS


def _data(body, status=200, headers=None):
    return {"status_code": status, "headers": headers or {"content-type": "application/json"}, "body": body}


def test_httpget_format_normal():
    """小样本 JSON: 全量保留 + Headers + 末行 ✓ 无截断-完整"""
    out = of._format_httpget_result(_data({"userId": 1, "title": "hello"}))
    assert "── HTTP GET ── 200" in out
    assert "── Body ──" in out
    assert '"userId": 1' in out
    assert "── Headers ──" in out
    assert "✓ 无截断-完整" in out
    assert "⚠ 已截断" not in out


def test_httpget_format_truncated_rows():
    """超 200 行: 截断到 OBS_HTTPGET_MAX_ROWS + ⚠ 已截断 + 还有 N 行明细"""
    big = {"items": [{"k": i, "v": "x" * 50} for i in range(300)]}
    out = of._format_httpget_result(_data(big))
    lines = out.split("\n")
    assert lines[-1] == "⚠ 已截断", lines[-1]
    assert "还有" in out and "行" in out
    # 仅展示前 OBS_HTTPGET_MAX_ROWS 行(body 部分), 总行数受控
    assert "k\": 299" not in out or out.count("\n") <= OBS_HTTPGET_MAX_ROWS + 20


def test_httpget_format_overwide_line():
    """单行超 2000 字符: 该行截到 OBS_HTTPGET_MAX_ROW_CHARS + ...(截断)"""
    wide = {"big": "X" * (OBS_HTTPGET_MAX_ROW_CHARS + 500)}
    out = of._format_httpget_result(_data(wide))
    assert "...(截断)" in out
    assert "⚠ 已截断" in out


def test_httpget_format_html_str():
    """HTML 字符串 body: 经 _extract_html_summary, 不崩溃且完整标记"""
    html = "<html><body><p>hello world</p></body></html>"
    out = of._format_httpget_result(_data(html))
    assert "── Body ──" in out
    assert "✓ 无截断-完整" in out


def test_httpget_format_empty_body():
    """body 为 None: 无 Body 段, 仍追加 ✓ 无截断-完整"""
    out = of._format_httpget_result(_data(None))
    assert "── Body ──" not in out
    assert "── Headers ──" in out
    assert "✓ 无截断-完整" in out
