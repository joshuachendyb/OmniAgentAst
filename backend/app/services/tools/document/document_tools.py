# -*- coding: utf-8 -*-
"""
文档读写工具函数模块

【创建时间】2026-05-02 小沈
【设计依据】按文档第8.3节 Tool 80-82 定义

【重要】新函数增加规范 - 小沈 2026-05-04
新增函数时必须同步修改以下3个文件：
1. *_tools.py: 函数实现（必须有详细注释）
2. *_schema.py: Pydantic 模型（输入参数定义）
3. *_register.py: 显式注册（description + examples + input_model）

包含：
- read_pdf: 读取PDF文件并提取文本内容
- read_docx: 读取Word文档并提取文本内容
- read_xlsx: 读取Excel文件并提取表格数据
- write_docx: 写入Word文档
- write_xlsx: 写入Excel文件
- read_pptx: 读取PPT幻灯片
- write_pdf: 写入PDF文档
- convert_document: 文档格式转换

Author: 小沈 - 2026-05-02
【新增 2026-05-05 小沈】write_pdf, convert_document
"""

import importlib
from typing import Dict, Any, List, Optional
from pathlib import Path

from app.services.tools.document.document_schema import (
    ReadPdfInput,
    ReadDocxInput,
    ReadXlsxInput,
    WriteDocxInput,
    WriteXlsxInput,
    ReadPptxInput,
    WritePptxInput,
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


def read_pdf(
    file_path: str,
    pages: str = None,
    extract_images: bool = False,
    extract_tables: bool = False
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
        tables_data = []

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
                
                # 提取表格
                if extract_tables:
                    tables = page.extract_tables()
                    if tables:
                        for idx, table in enumerate(tables):
                            tables_data.append({
                                "page": page_num,
                                "table_idx": idx,
                                "data": table
                            })

        result_data = {
            "text": "\n\n".join(all_text),
            "page_count": page_count,
            "pages_read": pages_read,
        }
        
        if extract_tables and tables_data:
            result_data["tables"] = tables_data

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


def read_docx(
    file_path: str,
    extract_tables: bool = False
) -> Dict[str, Any]:
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
        
        result_data = {
            "text": text,
            "paragraph_count": len(paragraphs),
        }
        
        # 提取表格
        if extract_tables:
            tables_data = []
            for table in doc.tables:
                table_rows = []
                for row in table.rows:
                    row_data = [cell.text.strip() for cell in row.cells]
                    table_rows.append(row_data)
                tables_data.append(table_rows)
            result_data["tables"] = tables_data
            result_data["table_count"] = len(tables_data)
        
        return {
            "code": "SUCCESS",
            "data": result_data,
            "message": f"成功读取Word文档: {file_path}，共 {len(paragraphs)} 段"
        }
    except Exception as e:
        return {
            "code": "ERR_READ_DOCX",
            "data": None,
            "message": f"读取Word文档失败: {str(e)}"
        }


def read_xlsx(
    file_path: str,
    sheet_name: str = None,
    max_rows: int = 1000,
    header: bool = True
) -> Dict[str, Any]:
    """读取Excel文件并提取表格数据 - 小沈 2026-05-02, 修正 2026-05-05
    【修正】删除未使用的index_col参数；header=False时正确处理首行数据
    """
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
            if i >= max_rows + (1 if header else 0):
                break
            row_data = [
                None if val is None else val
                for val in row
            ]
            if i == 0 and header:
                headers = [str(h) if h is not None else f"column_{j}" for j, h in enumerate(row_data)]
            else:
                if i == 0 and not header:
                    headers = [f"column_{j}" for j in range(len(row_data))]
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


def write_docx(
    file_path: str,
    content: str = None,
    paragraphs: list = None,
    title: str = None,
    table_data: list = None
) -> Dict[str, Any]:
    """写入Word文档 - 小沈 2026-05-04"""
    if not _check_module("docx"):
        return {
            "code": "ERR_NO_DOCX",
            "data": None,
            "message": "python-docx库未安装，请先执行: pip install python-docx"
        }

    try:
        import docx
        from docx import Document
        from docx.shared import Inches, Pt

        doc = Document()
        
        # 添加标题
        if title:
            doc.add_heading(title, 0)
        
        # 添加段落列表
        if paragraphs:
            for para in paragraphs:
                doc.add_paragraph(para)
        
        # 添加纯文本内容
        if content:
            doc.add_paragraph(content)
        
        # 添加表格
        if table_data:
            for tbl in table_data:
                if tbl and len(tbl) > 0:
                    rows = len(tbl)
                    cols = len(tbl[0]) if tbl[0] else 0
                    if rows > 0 and cols > 0:
                        table = doc.add_table(rows=rows, cols=cols)
                        for i, row_data in enumerate(tbl):
                            for j, cell_data in enumerate(row_data):
                                table.rows[i].cells[j].text = str(cell_data if cell_data is not None else "")
        
        # 保存文档
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(path)
        
        return {
            "code": "SUCCESS",
            "data": {"file_path": str(path)},
            "message": f"成功写入Word文档: {file_path}"
        }
    except Exception as e:
        return {
            "code": "ERR_WRITE_DOCX",
            "data": None,
            "message": f"写入Word文档失败: {str(e)}"
        }


def write_xlsx(
    file_path: str,
    data: dict,
    sheet_name: str = "Sheet1"
) -> Dict[str, Any]:
    """写入Excel文件 - 小沈 2026-05-04"""
    if not _check_module("openpyxl"):
        return {
            "code": "ERR_NO_OPENPYXL",
            "data": None,
            "message": "openpyxl库未安装，请先执行: pip install openpyxl"
        }

    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment

        wb = Workbook()
        ws = wb.active
        ws.title = sheet_name
        
        # 写入数据
        if "headers" in data and data["headers"]:
            headers = data["headers"]
            for col_idx, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col_idx, value=header)
                cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal="center")
        
        if "rows" in data and data["rows"]:
            for row_idx, row_data in enumerate(data["rows"], 2):
                for col_idx, cell_data in enumerate(row_data, 1):
                    ws.cell(row=row_idx, column=col_idx, value=cell_data)
        
        # 保存文档
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(path)
        
        return {
            "code": "SUCCESS",
            "data": {"file_path": str(path), "row_count": len(data.get("rows", []))},
            "message": f"成功写入Excel文件: {file_path}"
        }
    except Exception as e:
        return {
            "code": "ERR_WRITE_XLSX",
            "data": None,
            "message": f"写入Excel文件失败: {str(e)}"
        }


def read_pptx(
    file_path: str,
    extract_notes: bool = False
) -> Dict[str, Any]:
    """读取PPT幻灯片 - 小沈 2026-05-04"""
    if not _check_module("pptx"):
        return {
            "code": "ERR_NO_PPTX",
            "data": None,
            "message": "python-pptx库未安装，请先执行: pip install python-pptx"
        }

    try:
        from pptx import Presentation

        path = Path(file_path)
        if not path.exists():
            return {
                "code": "ERR_READ_PPTX",
                "data": None,
                "message": f"文件不存在: {file_path}"
            }

        prs = Presentation(path)
        slides_data = []
        notes_data = []
        
        for slide_num, slide in enumerate(prs.slides, 1):
            slide_text = []
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        text = para.text.strip()
                        if text:
                            slide_text.append(text)
            
            slides_data.append({
                "slide_num": slide_num,
                "text": "\n".join(slide_text)
            })
            
            # 提取备注
            if extract_notes and slide.has_notes_slide:
                notes = slide.notes_slide.notes_text_frame.text.strip()
                if notes:
                    notes_data.append({
                        "slide_num": slide_num,
                        "notes": notes
                    })

        result_data = {
            "slide_count": len(prs.slides),
            "slides": slides_data,
        }
        
        if extract_notes and notes_data:
            result_data["notes"] = notes_data

        return {
            "code": "SUCCESS",
            "data": result_data,
            "message": f"成功读取PPT文件: {file_path}，共 {len(prs.slides)} 页"
        }
    except Exception as e:
        return {
            "code": "ERR_READ_PPTX",
            "data": None,
            "message": f"读取PPT文件失败: {str(e)}"
        }


def write_pdf(
    file_path: str,
    title: str = None,
    content: str = None,
    paragraphs: list = None,
    table_data: list = None
) -> Dict[str, Any]:
    """写入PDF文档 - 小沈 2026-05-05"""
    if not _check_module("reportlab"):
        return {
            "code": "ERR_NO_REPORTLAB",
            "data": None,
            "message": "reportlab库未安装，请先执行: pip install reportlab"
        }

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
        from reportlab.lib import colors
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(str(path), pagesize=A4)
        styles = getSampleStyleSheet()

        try:
            font_path = "C:/Windows/Fonts/simsun.ttc"
            pdfmetrics.registerFont(TTFont('SimSun', font_path, subfontIndex=0))
            chinese_style = ParagraphStyle(
                'Chinese', parent=styles['Normal'],
                fontName='SimSun', fontSize=10, leading=14,
                wordWrap='CJK'
            )
            title_style = ParagraphStyle(
                'ChineseTitle', parent=styles['Title'],
                fontName='SimSun', fontSize=18, leading=24,
                wordWrap='CJK'
            )
        except Exception:
            chinese_style = styles['Normal']
            title_style = styles['Title']

        elements = []

        if title:
            elements.append(Paragraph(title, title_style))
            elements.append(Spacer(1, 10*mm))

        if content:
            elements.append(Paragraph(content, chinese_style))
            elements.append(Spacer(1, 5*mm))

        if paragraphs:
            for para in paragraphs:
                elements.append(Paragraph(str(para), chinese_style))
                elements.append(Spacer(1, 3*mm))

        if table_data:
            for tbl in table_data:
                if tbl and len(tbl) > 0:
                    try:
                        t = Table(tbl)
                        t.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                            ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ]))
                        elements.append(t)
                        elements.append(Spacer(1, 5*mm))
                    except Exception:
                        pass

        if not elements:
            elements.append(Paragraph(" ", chinese_style))

        doc.build(elements)

        return {
            "code": "SUCCESS",
            "data": {"file_path": str(path)},
            "message": f"成功写入PDF文档: {file_path}"
        }
    except Exception as e:
        return {
            "code": "ERR_WRITE_PDF",
            "data": None,
            "message": f"写入PDF文档失败: {str(e)}"
        }


def convert_document(
    input_path: str,
    output_format: str,
    output_path: str = None
) -> Dict[str, Any]:
    """文档格式转换 - 小沈 2026-05-05"""
    try:
        src = Path(input_path)
        if not src.exists():
            return {
                "code": "ERR_CONVERT_DOCUMENT",
                "data": None,
                "message": f"文件不存在: {input_path}"
            }
        
        src_ext = src.suffix.lower()
        supported_inputs = ['.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt', '.odt', '.ods']
        
        if src_ext not in supported_inputs:
            return {
                "code": "ERR_CONVERT_DOCUMENT",
                "data": None,
                "message": f"不支持的输入格式: {src_ext}，支持: {supported_inputs}"
            }
        
        if output_format.lower() != 'pdf':
            return {
                "code": "ERR_CONVERT_DOCUMENT",
                "data": None,
                "message": f"当前仅支持转换为PDF格式"
            }
        
        if output_path is None:
            output_path = str(src.with_suffix('.pdf'))
        
        import subprocess
         
        soffice_paths = [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ]
        import platform
        if platform.system() != 'Windows':
            soffice_paths = ["/usr/bin/soffice", "/usr/local/bin/soffice"]
        
        soffice = None
        for p in soffice_paths:
            if Path(p).exists():
                soffice = p
                break
        
        if not soffice:
            return {
                "code": "ERR_NO_LIBREOFFICE",
                "data": None,
                "message": "LibreOffice未安装，无法转换。请安装LibreOffice: https://www.libreoffice.org/download/"
            }
        
        out_dir = str(Path(output_path).parent)
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        
        cmd = [
            soffice,
            "--headless",
            "--convert-to", "pdf",
            "--outdir", out_dir,
            str(src)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            return {
                "code": "ERR_CONVERT_DOCUMENT",
                "data": None,
                "message": f"LibreOffice转换失败: {result.stderr}"
            }
        
        expected_pdf = Path(out_dir) / src.with_suffix('.pdf').name
        if not expected_pdf.exists():
            return {
                "code": "ERR_CONVERT_DOCUMENT",
                "data": None,
                "message": "转换后PDF文件未生成"
            }
        
        if output_path != str(expected_pdf):
            import shutil
            shutil.move(str(expected_pdf), output_path)
        
        return {
            "code": "SUCCESS",
            "data": {"input_path": str(src), "output_path": output_path},
            "message": f"成功转换: {src_ext} → .pdf"
        }
    except Exception as e:
        return {
            "code": "ERR_CONVERT_DOCUMENT",
            "data": None,
            "message": f"文档转换失败: {str(e)}"
        }


def write_pptx(
    file_path: str,
    title: str = None,
    slides: list = None
) -> Dict[str, Any]:
    """写入PPT幻灯片 - 小沈 2026-05-05"""
    if not _check_module("pptx"):
        return {
            "code": "ERR_NO_PPTX",
            "data": None,
            "message": "python-pptx库未安装，请先执行: pip install python-pptx"
        }
    
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt
        
        # 创建演示文稿
        prs = Presentation()
        
        # 添加标题页
        if title:
            title_slide_layout = prs.slide_layouts[0]  # 标题布局
            slide = prs.slides.add_slide(title_slide_layout)
            title_shape = slide.shapes.title
            title_shape.text = title
        
        # 添加内容幻灯片
        if slides:
            for slide_data in slides:
                slide_title = slide_data.get("title", "幻灯片")
                content = slide_data.get("content", "")
                
                # 使用标题和内容布局
                content_layout = prs.slide_layouts[1]
                slide = prs.slides.add_slide(content_layout)
                
                # 设置标题
                if slide.shapes.title:
                    slide.shapes.title.text = slide_title
                
                # 设置内容
                for shape in slide.shapes:
                    if shape.has_text_frame and not shape.text_frame.text.strip():
                        text_frame = shape.text_frame
                        text_frame.clear()
                        p = text_frame.paragraphs[0]
                        p.text = content
                        p.font.size = Pt(18)
                        break
        
        # 保存文件
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        prs.save(path)
        
        return {
            "code": "SUCCESS",
            "data": {"file_path": str(path), "slide_count": len(prs.slides)},
            "message": f"成功写入PPT文件: {file_path}，共 {len(prs.slides)} 页"
        }
    except Exception as e:
        return {
            "code": "ERR_WRITE_PPTX",
            "data": None,
            "message": f"写入PPT文件失败: {str(e)}"
        }
