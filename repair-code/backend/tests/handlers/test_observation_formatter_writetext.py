# -*- coding: utf-8 -*-
# 测试 writetext 结果(写入内容预览)在用户裁定回退后的行为:
#  - preview 由 Tool 层 _build_content_preview 生成(文首50+文末50)
#  - 经 format_data_detail 走 #23 专属分支(简单拼接 "已写入内容\\n"+preview), 无 OBS_WRITETEXT_* / 无截断
# 对齐: 门限治理规范 doc 章14.4/14.5/14.6
# 小欧 2026-07-20 新增(本地验证用, 不提交); 2026-07-20 用户裁定回退后修订
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.agent.observation_formatter import format_data_detail
from app.tools.file.write_text_file import _build_content_preview


def _llm(tool="writetext", path="/tmp/a.txt"):
    return {"action": {"tool": tool, "target": path, "params": {}}}


def test_preview_small_full():
    """小内容(<=100): preview 即全文, 不折叠"""
    content = "hello\nworld\n"
    assert _build_content_preview(content) == content


def test_preview_large_head_tail():
    """大内容: 文首50 + 文末50 折叠, 中间标记省略"""
    content = "x" * 200 + "MID" + "y" * 200
    preview = _build_content_preview(content)
    assert "文首(50字符):" in preview
    assert "文末(50字符):" in preview
    assert "中间省略" in preview
    assert preview.startswith("文首(50字符):" + "x" * 50)
    assert preview.endswith("文末(50字符):" + "y" * 50)


def test_dispatch_writetext_via_format_data_detail():
    """经 format_data_detail 命中 #23 专属分支: 简单拼接 '已写入内容\\n'+preview, 不含 key 名/两态行"""
    content = "写入内容行\n" * 3
    out = format_data_detail({"content_preview": content}, _llm(tool="writetext"))
    assert out.startswith("已写入内容")
    assert content in out
    # 不应出现 key 名 / 专属标题 / 两态说明行
    assert "content_preview" not in out
    assert "── 写入内容预览" not in out
    assert "✓ 无截断-完整" not in out
    assert "⚠ 已截断" not in out


def test_empty_preview_no_error():
    """空内容: 不抛异常, 渲染 '已写入内容' 前缀"""
    out = format_data_detail({"content_preview": ""}, _llm())
    assert out.startswith("已写入内容")


def test_no_obsolete_handler_symbols():
    """回归: writetext 不再引用已删除的 OBS_WRITETEXT_* 专属逻辑(prevent 死代码回归)"""
    # fallback 渲染不应含专属截断提示
    content = "a" * 5000
    out = format_data_detail({"content_preview": content}, _llm())
    assert "...(截断)" not in out
