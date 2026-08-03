# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-06-22 - 小欧 - 创建文件，从document_tools.py拆分
# 2026-07-05 - 小欧 - 加hint参数
# 2026-07-26 - 小欧 - summary加路径前空格，加char_count指标供LLM验证内容写入
# 2026-07-26 - 小欧 - char_count改为统计title+content+table_data全源；之前只统计content，遗漏表格和标题内容
# 2026-07-31 - 小欧 - Bug⑧修复: CJK字体渐进回退(依次尝试simsun/msyh/simhei/Deng/simkai, 全部缺失才退默认并告警), 防simsun缺失时中文渲染方框; Bug⑯同型修复: 有序列表正则 ^\d+\.\s → ^\d{1,3}\.\s, 防"2026. 销售报告"被误当编号列表 | py_compile ✓
"""
D7: write_pdf — 写入PDF文档

从document_tools.py拆分而来 — 小欧 2026-06-22

"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import os
import re
import time as _time_mod
from pathlib import Path
from typing import Any, Dict, Optional, List

from app.logger import logger
from app.tools.tool_response import build_success, build_error
from app.tools.tool_fc_helper import _check_module
from app.tools.tool_constants import ERR_WRITE_PDF
from app.tools.validate.file_path_checker import permission_error_hint, hint_for_write_error
from reportlab.lib.units import mm
from app.tools.validate.file_type_checker import check_office_file
from app.tools.validate.file_safety_checker import check_content_safety
from app.utils.table_helper import parse_markdown_table, get_table_header_style_config, normalize_table_data  # 2026-07-31 小欧: 移除未使用 logger
from app.tools.document.md_inline_utils import _md_to_pdf_xml


# 2026-07-31 小欧: Bug⑧ CJK字体候选列表(按优先级渐进回退) — (注册名, 字体文件路径)
_CJK_FONT_CANDIDATES = [
    ("SimSun", "C:/Windows/Fonts/simsun.ttc"),
    ("MicrosoftYaHei", "C:/Windows/Fonts/msyh.ttc"),
    ("SimHei", "C:/Windows/Fonts/simhei.ttf"),
    ("DengXian", "C:/Windows/Fonts/Deng.ttf"),
    ("KaiTi", "C:/Windows/Fonts/simkai.ttf"),
]


def _create_pdf_table(table_data, chinese_style):
    """创建PDF表格 — 小健 2026-06-24"""
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors
    
    header_config = get_table_header_style_config()
    bg_color = colors.HexColor('#' + header_config["bg_color"])
    
    table = Table(table_data)
    style_commands = [
        ('BACKGROUND', (0, 0), (-1, 0), bg_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, -1), chinese_style.fontName),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]
    
    table.setStyle(TableStyle(style_commands))
    return table


def _build_write_pdf_llm_data(
    exec_code: str, duration_ms: int,
    file_path: str = "", detail: str = "", user_title: str = "",
    hint: str = "", char_count: int = 0,
) -> Dict[str, Any]:
    """write_pdf的llm_data构建函数 — 小欧 2026-06-22 — 小欧 2026-07-05 加hint参数"""
    _act_params = {"file_path": file_path}
    if user_title:
        _act_params["title"] = user_title
    if exec_code == "error":
        return {
            "summary": f"写入PDF {file_path}，失败: {detail}",
            "action": {"tool": "write_pdf", "tool_zh": "写入PDF", "target": file_path, "params": _act_params},
            "status": {"exec_code": "error", "message": "写入PDF失败", "code": ERR_WRITE_PDF, "detail": detail, "hint": hint if hint else "请检查路径和权限"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"写入PDF {file_path}，成功: {char_count}字符",
        "action": {"tool": "write_pdf", "tool_zh": "写入PDF", "target": file_path, "params": _act_params},
        "status": {"exec_code": "success", "message": "写入PDF成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {
            "char_count": {"value": char_count, "text": f"{char_count}字符"},
        },
    }



def write_pdf(
    path: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
    table_data: Optional[List[List[str]]] = None,
) -> Dict[str, Any]:
    """写入PDF文件 — 小欧 2026-06-19 — 小欧 2026-06-22 独立文件 — 小健 2026-06-24 参数简化（Markdown格式）+ table_data支持"""
    t0 = _time_mod.perf_counter()

    # 文件类型前置检查（含路径检查+类型检查+模块安全检查）— 北京老陈 2026-07-09
    is_valid, error_detail, hint = check_office_file(path, allow_create=True)
    if not is_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_pdf_llm_data("error", duration_ms, path, detail=error_detail, user_title=title or "", hint=hint)
        return build_error(data={}, llm_data=llm_data)

    if content is not None:
        cs_error, _ = check_content_safety(content, "pdf")
        if cs_error:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_write_pdf_llm_data("error", duration_ms, path, detail=cs_error, user_title=title or "", hint="请检查content参数")
            return build_error(data={}, llm_data=llm_data)

    if not _check_module("reportlab"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_pdf_llm_data("error", duration_ms, path, detail="reportlab库未安装", user_title=title or "", hint="请安装reportlab库")
        return build_error(data={}, llm_data=llm_data)

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_pdf_llm_data("error", duration_ms, path, detail="reportlab库导入失败", user_title=title or "", hint="请检查reportlab库安装完整性")
        return build_error(data={}, llm_data=llm_data)

    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(str(path), pagesize=A4)
        styles = getSampleStyleSheet()

        chinese_style = None
        title_style = None
        # 2026-07-31 小欧: Bug⑧修复 — CJK字体渐进回退, 依次尝试候选字体, 全部缺失才退默认样式(并告警)
        for font_name, font_path in _CJK_FONT_CANDIDATES:
            try:
                if not os.path.isfile(font_path):
                    continue
                pdfmetrics.registerFont(TTFont(font_name, font_path, subfontIndex=0))
                chinese_style = ParagraphStyle(
                    'Chinese', parent=styles['Normal'],
                    fontName=font_name, fontSize=10, leading=14,
                    wordWrap='CJK',
                )
                title_style = ParagraphStyle(
                    'ChineseTitle', parent=styles['Title'],
                    fontName=font_name, fontSize=18, leading=24,
                    wordWrap='CJK',
                )
                break
            except Exception:
                continue
        if chinese_style is None or title_style is None:
            chinese_style = styles['Normal']
            title_style = styles['Title']
            logger.warning("[write_pdf] 未找到可用中文字体, 中文可能显示为方框, 建议安装simsun.ttc/msyh.ttc")

        elements = []

        if title:
            elements.append(Paragraph(title, title_style))
            elements.append(Spacer(1, 10 * mm))

        if content:
            lines = content.split('\n')
            i = 0
            while i < len(lines):
                line = lines[i].rstrip()
                if not line:
                    i += 1
                    continue
                if line.startswith('# '):
                    h1_style = ParagraphStyle('h1', parent=chinese_style, fontSize=18, spaceBefore=12, spaceAfter=6)
                    elements.append(Paragraph(_md_to_pdf_xml(line[2:]), h1_style))
                    elements.append(Spacer(1, 3 * mm))
                elif line.startswith('## '):
                    h2_style = ParagraphStyle('h2', parent=chinese_style, fontSize=16, spaceBefore=10, spaceAfter=5)
                    elements.append(Paragraph(_md_to_pdf_xml(line[3:]), h2_style))
                    elements.append(Spacer(1, 3 * mm))
                elif line.startswith('### '):
                    h3_style = ParagraphStyle('h3', parent=chinese_style, fontSize=14, spaceBefore=8, spaceAfter=4)
                    elements.append(Paragraph(_md_to_pdf_xml(line[4:]), h3_style))
                    elements.append(Spacer(1, 2 * mm))
                elif line.startswith('#### '):
                    h4_style = ParagraphStyle('h4', parent=chinese_style, fontSize=12, spaceBefore=6, spaceAfter=3)
                    elements.append(Paragraph(_md_to_pdf_xml(line[5:]), h4_style))
                    elements.append(Spacer(1, 2 * mm))
                elif line.startswith('- ') or line.startswith('* '):
                    elements.append(Paragraph('• ' + _md_to_pdf_xml(line[2:]), chinese_style))
                    elements.append(Spacer(1, 2 * mm))
                elif re.match(r'^\d{1,3}\.\s', line):  # 2026-07-31 小欧: Bug⑯同型 — 限1-3位编号, 防"2026. 报告"散文被误当列表
                    elements.append(Paragraph(_md_to_pdf_xml(re.sub(r'^\d+\.\s', '', line)), chinese_style))
                    elements.append(Spacer(1, 2 * mm))
                elif line.startswith('|') and '|' in line[1:]:
                    table_rows, i = parse_markdown_table(lines, i)
                    if table_rows:
                        pdf_table = _create_pdf_table(table_rows, chinese_style)
                        elements.append(pdf_table)
                        elements.append(Spacer(1, 5 * mm))
                    continue
                else:
                    elements.append(Paragraph(_md_to_pdf_xml(line), chinese_style))
                    elements.append(Spacer(1, 3 * mm))
                i += 1
        
        if table_data:
            table_data = normalize_table_data(table_data)
            if table_data and len(table_data) > 0:
                pdf_table = _create_pdf_table(table_data, chinese_style)
                elements.append(pdf_table)

        if not elements:
            elements.append(Paragraph(" ", chinese_style))

        # 统计所有输入源的字符数（含 title + content + table_data），供 LLM 验证内容量 — 小欧 2026-07-26
        content_char_count = 0
        if title:
            content_char_count += len(title)
        if content:
            content_char_count += len(content)
        if table_data:
            for row in table_data:
                for cell in row:
                    content_char_count += len(str(cell))

        doc.build(elements)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_pdf_llm_data("success", duration_ms, str(path), user_title=title or "", char_count=content_char_count)
        # =============================================================================
        # 数据设计：file_path 从 data 移除，通过 llm_data.summary 传入 LLM observation。
        # summary 已包含文件路径: "写入PDF成功: /path.pdf"
        # data 为空 dict 时 formatter 不追加详情，避免冗余。
        # — 小欧 2026-07-06
        # =============================================================================
        return build_success(data={}, llm_data=llm_data)
    except PermissionError as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        hint = permission_error_hint(path)
        # 小欧 2026-07-12: 此处path经Path()重赋值为WindowsPath,须str()化后传入builder,
        # 避免action.target持有Path对象触发观察格式化len()崩溃
        llm_data = _build_write_pdf_llm_data("error", duration_ms, str(path), detail=str(e), user_title=title or "", hint=hint)
        return build_error(data={}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        hint = hint_for_write_error(e, path)
        # 小欧 2026-07-12: 此处path经Path()重赋值为WindowsPath,须str()化后传入builder,
        # 避免action.target持有Path对象触发观察格式化len()崩溃
        llm_data = _build_write_pdf_llm_data("error", duration_ms, str(path), detail=str(e), user_title=title or "", hint=hint)
        return build_error(data={}, llm_data=llm_data)
