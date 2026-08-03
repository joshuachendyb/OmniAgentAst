"""Markdown行内格式解析工具 — 小欧 2026-07-08

提供跨 write_docx/write_pdf 的共享行内格式处理。
2026-07-31 小欧: Bug⑱修复 — 链接正则支持 text内嵌套[]、URL内嵌套() | py_compile ✓
"""

import re


def _parse_inline_md(text: str):
    """解析行内Markdown，返回 [(文本, 粗体, 斜体, 代码, 链接URL)]

    支持: **粗体**, *斜体*, ***粗斜体***, `代码`, [文本](链接)
    不处理嵌套（如**粗体*斜体**），KISS原则。
    """
    segments = []
    pos = 0
    while pos < len(text):
        # 代码 `code` 优先（避免匹配`内的**bold**）
        m = re.match(r'`([^`]+)`', text[pos:])
        if m:
            segments.append((m.group(1), False, False, True, None))
            pos += m.end()
            continue
        # 粗斜体 ***text***
        m = re.match(r'\*\*\*([^*]+)\*\*\*', text[pos:])
        if m:
            segments.append((m.group(1), True, True, False, None))
            pos += m.end()
            continue
        # 粗体 **text**
        m = re.match(r'\*\*([^*]+)\*\*', text[pos:])
        if m:
            segments.append((m.group(1), True, False, False, None))
            pos += m.end()
            continue
        # 斜体 *text*
        m = re.match(r'\*([^*]+)\*', text[pos:])
        if m:
            segments.append((m.group(1), False, True, False, None))
            pos += m.end()
            continue
        # 链接 [text](url) — 支持text内嵌套[]、URL内嵌套() — 小欧 2026-07-31 Bug⑱修复
        # 旧正则 [^\]]+ / [^)]+ 遇 text含]或url含)时截断误判
        m = re.match(r'\[((?:[^\[\]]|\[[^\[\]]*\])*)\]\(((?:[^()]|\([^()]*\))*)\)', text[pos:])
        if m:
            segments.append((m.group(1), False, False, False, m.group(2)))
            pos += m.end()
            continue
        # 普通字符
        segments.append((text[pos], False, False, False, None))
        pos += 1
    return segments


def _escape_xml(text):
    """转义XML特殊字符"""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def _md_to_pdf_xml(text):
    """行内Markdown → reportlab Paragraph XML标签

    例: '**a** `b`' → '<b>a</b> <font face="Courier" size="8">b</font>'
    """
    parts = []
    for seg_text, bold, italic, code, link_url in _parse_inline_md(text):
        t = _escape_xml(seg_text)
        if bold:
            t = f'<b>{t}</b>'
        if italic:
            t = f'<i>{t}</i>'
        if code:
            t = f'<font face="Courier" size="8">{t}</font>'
        if link_url:
            t = f'<a href="{_escape_xml(link_url)}">{t}</a>'
        parts.append(t)
    return ''.join(parts)
