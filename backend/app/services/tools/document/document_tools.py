# -*- coding: utf-8 -*-
"""
文档读写工具函数模块

【创建时间】2026-05-02 小沈
【设计依据】按文档第8.3节 Tool 80-82 定义

包含：
- read_pdf: 读取PDF文件并提取文本内容
- read_docx: 读取Word文档并提取文本内容
- read_xlsx: 读取Excel文件并提取表格数据

Author: 小沈 - 2026-05-02
"""

import importlib
from typing import Dict, Any, List, Optional
from pathlib import Path

from app.services.tools.registry import register_tool, ToolCategory

from app.services.tools.document.document_schema import (
    ReadPdfInput,
    ReadDocxInput,
    ReadXlsxInput,
)


def _check_module(module_name: str) -> bool:
    """检查模块是否可用 - 小沈 2026-05-02"""
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        return False


def _parse_pages(pages_str: str) -> List[int]:
    """解析页码字符串为页码列表 - 小沈 2026-05-02"""
    result = []
    for part in pages_str.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            try:
                result.extend(range(int(start), int(end) + 1))
            except ValueError:
                pass
        else:
            try:
                result.append(int(part))
            except ValueError:
                pass
    return sorted(set(result))


@register_tool(
    name="read_pdf",
    description="""读取 PDF 文件并提取文本内容。

使用场景：
- 当用户需要读取 PDF 文档内容时使用
- 当用户想要从 PDF 中提取文字信息时使用
- 当用户需要分析 PDF 文档内容时使用

参数说明：
- file_path：PDF 文件路径
- pages：要读取的页面（如 "1-5" 或 "1,3,5"）
- extract_images：是否提取图片，默认 false

【重要】需要安装 pdfplumber 库（pip install pdfplumber）

返回数据说明：
- code: 状态码（SUCCESS/ERR_READ_PDF/ERR_NO_PDFPLUMBER）
- data: 包含text、page_count、pages_read的字典
- message: 操作结果消息""",
    category=ToolCategory.DOCUMENT,
    input_model=ReadPdfInput,
    examples=[
        {"file_path": "D:/documents/report.pdf"},
        {"file_path": "D:/documents/report.pdf", "pages": "1-3"},
    ]
)
def read_pdf(
    file_path: str,
    pages: str = None,
    extract_images: bool = False
) -> Dict[str, Any]:
    """读取PDF文件并提取文本内容 - 小沈 2026-05-02"""
    if not _check_module("pdfplumber"):
        return {
            "code": "ERR_NO_PDFPLUMBER",
            "data": None,
            "message": "pdfplumber库未安装，请先执行: pip install pdfplumber"
        }

    try:
        import pdfplumber

        path = Path(file_path)
        if not path.exists():
            return {
                "code": "ERR_READ_PDF",
                "data": None,
                "message": f"文件不存在: {file_path}"
            }

        all_text = []
        page_count = 0
        pages_read = []

        with pdfplumber.open(path) as pdf:
            page_count = len(pdf.pages)

            if pages:
                target_pages = _parse_pages(pages)
                target_pages = [p for p in target_pages if 1 <= p <= page_count]
            else:
                target_pages = list(range(1, page_count + 1))

            for page_num in target_pages:
                page = pdf.pages[page_num - 1]
                text = page.extract_text() or ""
                all_text.append(f"--- 第 {page_num} 页 ---\n{text}")
                pages_read.append(page_num)

        result_data = {
            "text": "\n\n".join(all_text),
            "page_count": page_count,
            "pages_read": pages_read,
        }

        return {
            "code": "SUCCESS",
            "data": result_data,
            "message": f"成功读取PDF文件: {file_path}，共读取 {len(pages_read)} 页"
        }
    except Exception as e:
        return {
            "code": "ERR_READ_PDF",
            "data": None,
            "message": f"读取PDF文件失败: {str(e)}"
        }


@register_tool(
    name="read_docx",
    description="""读取 Word 文档并提取文本内容。

使用场景：
- 当用户需要读取 Word 文档内容时使用
- 当用户想要从 Word 文档中提取文字信息时使用
- 当用户需要分析 Word 文档内容时使用

参数说明：
- file_path：Word 文件路径

【重要】需要安装 python-docx 库（pip install python-docx）

返回数据说明：
- code: 状态码（SUCCESS/ERR_READ_DOCX/ERR_NO_DOCX）
- data: 包含text、paragraph_count的字典
- message: 操作结果消息""",
    category=ToolCategory.DOCUMENT,
    input_model=ReadDocxInput,
    examples=[
        {"file_path": "D:/documents/report.docx"},
    ]
)
def read_docx(file_path: str) -> Dict[str, Any]:
    """读取Word文档并提取文本内容 - 小沈 2026-05-02"""
    if not _check_module("docx"):
        return {
            "code": "ERR_NO_DOCX",
            "data": None,
            "message": "python-docx库未安装，请先执行: pip install python-docx"
        }

    try:
        import docx

        path = Path(file_path)
        if not path.exists():
            return {
                "code": "ERR_READ_DOCX",
                "data": None,
                "message": f"文件不存在: {file_path}"
            }

        doc = docx.Document(path)
        paragraphs = [para.text for para in doc.paragraphs]
        text = "\n".join(paragraphs)

        return {
            "code": "SUCCESS",
            "data": {
                "text": text,
                "paragraph_count": len(paragraphs),
            },
            "message": f"成功读取Word文档: {file_path}，共 {len(paragraphs)} 段"
        }
    except Exception as e:
        return {
            "code": "ERR_READ_DOCX",
            "data": None,
            "message": f"读取Word文档失败: {str(e)}"
        }


@register_tool(
    name="read_xlsx",
    description="""读取 Excel 文件并提取表格数据。

使用场景：
- 当用户需要读取 Excel 表格数据时使用
- 当用户想要从 Excel 中提取数据进行分析时使用
- 当用户需要查看 Excel 文件内容时使用

参数说明：
- file_path：Excel 文件路径
- sheet_name：工作表名称（默认第一个）
- max_rows：最大读取行数，默认 1000

【重要】需要安装 openpyxl 库（pip install openpyxl）

返回数据说明：
- code: 状态码（SUCCESS/ERR_READ_XLSX/ERR_NO_OPENPYXL）
- data: 包含headers、rows、row_count、sheet_names的字典
- message: 操作结果消息""",
    category=ToolCategory.DOCUMENT,
    input_model=ReadXlsxInput,
    examples=[
        {"file_path": "D:/data/report.xlsx"},
        {"file_path": "D:/data/report.xlsx", "sheet_name": "Sheet2"},
    ]
)
def read_xlsx(
    file_path: str,
    sheet_name: str = None,
    max_rows: int = 1000
) -> Dict[str, Any]:
    """读取Excel文件并提取表格数据 - 小沈 2026-05-02"""
    if not _check_module("openpyxl"):
        return {
            "code": "ERR_NO_OPENPYXL",
            "data": None,
            "message": "openpyxl库未安装，请先执行: pip install openpyxl"
        }

    try:
        from openpyxl import load_workbook

        path = Path(file_path)
        if not path.exists():
            return {
                "code": "ERR_READ_XLSX",
                "data": None,
                "message": f"文件不存在: {file_path}"
            }

        wb = load_workbook(path, read_only=True, data_only=True)
        sheet_names = wb.sheetnames

        if sheet_name:
            if sheet_name not in sheet_names:
                wb.close()
                return {
                    "code": "ERR_READ_XLSX",
                    "data": None,
                    "message": f"工作表不存在: {sheet_name}，可用工作表: {sheet_names}"
                }
            ws = wb[sheet_name]
        else:
            ws = wb.active

        rows = []
        headers = []
        row_count = 0

        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i >= max_rows + 1:
                break
            row_data = [
                None if val is None else val
                for val in row
            ]
            if i == 0:
                headers = [str(h) if h is not None else f"column_{j}" for j, h in enumerate(row_data)]
            else:
                rows.append(row_data)
                row_count += 1

        wb.close()

        return {
            "code": "SUCCESS",
            "data": {
                "headers": headers,
                "rows": rows,
                "row_count": row_count,
                "sheet_names": sheet_names,
            },
            "message": f"成功读取Excel文件: {file_path}，工作表: {ws.title}，共 {row_count} 行数据"
        }
    except Exception as e:
        return {
            "code": "ERR_READ_XLSX",
            "data": None,
            "message": f"读取Excel文件失败: {str(e)}"
        }
