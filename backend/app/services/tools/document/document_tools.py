# -*- coding: utf-8 -*-
"""
文档读写工具函数模块

【创建时间】2026-05-02 小沈
【设计依据】按文档第8.3节 Tool 80-82 定义
【重构 2026-05-18 小健】8个旧函数抽取为内部函数，新增read_document/write_document路由函数

【重要】新函数增加规范 - 小沈 2026-05-04
新增函数时必须同步修改以下3个文件：
1. *_tools.py: 函数实现（必须有详细注释）
2. *_schema.py: Pydantic 模型（输入参数定义）
3. *_register.py: 显式注册（description + examples + input_model）

包含：
- _read_pdf / _read_docx / _read_xlsx / _read_pptx: 内部读取函数
- _write_docx / _write_xlsx / _write_pdf / _write_pptx: 内部写入函数
- read_document: 统一读取路由（按后缀自动选择解析器）
- write_document: 统一写入路由（按后缀自动选择写入器）
- convert_document: 文档格式转换

Author: 小沈 - 2026-05-02
【新增 2026-05-05 小沈】write_pdf, convert_document
【重构 2026-05-18 小健】8合2路由重构
"""

import importlib
import csv
from typing import Dict, Any, List, Optional
from pathlib import Path

from app.services.tools.document.document_schema import (
    ReadDocumentInput,
    WriteDocumentInput,
)
from app.services.tools.tool_result_utils import build_next_actions


def _check_module(module_name: str) -> bool:
    """检查模块是否可用 - 小沈 2026-05-02"""
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        return False


def _check_pandas() -> bool:
    """检查pandas是否可用 - 小沈 2026-05-18"""
    try:
        importlib.import_module("pandas")
        return True
    except ImportError:
        return False


def _check_openpyxl() -> bool:
    """检查openpyxl是否可用 - 小沈 2026-05-18"""
    try:
        importlib.import_module("openpyxl")
        return True
    except ImportError:
        return False


def _check_pdf_readable(file_path: str) -> Dict[str, Any]:
    """检查PDF文件是否可读（内部helper） - 小沈 2026-05-18，从env_check_tools.py迁入"""
    path = Path(file_path)
    if not path.exists():
        return {"code": "ERR_READ_PDF", "data": None, "message": f"文件不存在: {file_path}"}
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            page_count = len(pdf.pages)
        return {"code": "SUCCESS", "data": {"readable": True, "page_count": page_count},
                "message": f"PDF文件可读，共 {page_count} 页"}
    except ImportError:
        return {"code": "ERR_NO_PDFPLUMBER", "data": None,
                "message": "pdfplumber库未安装，请先执行: pip install pdfplumber"}
    except Exception as e:
        return {"code": "ERR_READ_PDF", "data": None, "message": f"PDF文件不可读: {str(e)}"}


def _check_docx_readable(file_path: str) -> Dict[str, Any]:
    """检查Word文件是否可读（内部helper） - 小沈 2026-05-18，从env_check_tools.py迁入"""
    path = Path(file_path)
    if not path.exists():
        return {"code": "ERR_READ_DOCX", "data": None, "message": f"文件不存在: {file_path}"}
    try:
        import docx
        doc = docx.Document(path)
        para_count = len(doc.paragraphs)
        return {"code": "SUCCESS", "data": {"readable": True, "paragraph_count": para_count},
                "message": f"Word文件可读，共 {para_count} 段"}
    except ImportError:
        return {"code": "ERR_NO_DOCX", "data": None,
                "message": "python-docx库未安装，请先执行: pip install python-docx"}
    except Exception as e:
        return {"code": "ERR_READ_DOCX", "data": None, "message": f"Word文件不可读: {str(e)}"}


def _check_xlsx_readable(file_path: str) -> Dict[str, Any]:
    """检查Excel文件是否可读（内部helper） - 小沈 2026-05-18，从env_check_tools.py迁入"""
    path = Path(file_path)
    if not path.exists():
        return {"code": "ERR_READ_XLSX", "data": None, "message": f"文件不存在: {file_path}"}
    try:
        from openpyxl import load_workbook
        wb = load_workbook(path, read_only=True)
        sheet_names = wb.sheetnames
        wb.close()
        return {"code": "SUCCESS", "data": {"readable": True, "sheet_names": sheet_names},
                "message": f"Excel文件可读，共 {len(sheet_names)} 个工作表"}
    except ImportError:
        return {"code": "ERR_NO_OPENPYXL", "data": None,
                "message": "openpyxl库未安装，请先执行: pip install openpyxl"}
    except Exception as e:
        return {"code": "ERR_READ_XLSX", "data": None, "message": f"Excel文件不可读: {str(e)}"}


def _validate_csv_format(file_path: str) -> Dict[str, Any]:
    """验证CSV文件格式（内部helper） - 小沈 2026-05-18，从env_check_tools.py迁入"""
    path = Path(file_path)
    if not path.exists():
        return {"code": "ERR_READ_CSV", "data": None, "message": f"文件不存在: {file_path}"}
    if not path.suffix.lower() in (".csv", ".tsv", ".txt"):
        return {"code": "ERR_READ_CSV", "data": None, "message": "文件扩展名不是CSV格式"}

    errors = []
    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            row_count = 0
            col_count = None
            for i, row in enumerate(reader):
                row_count += 1
                if col_count is None:
                    col_count = len(row)
                elif len(row) != col_count:
                    if len(row) != 0:
                        errors.append(f"第{i+1}行列数不一致: 期望{col_count}列，实际{len(row)}列")
                if row_count > 1000:
                    break
    except UnicodeDecodeError:
        try:
            with open(path, "r", encoding="gbk", newline="") as f:
                reader = csv.reader(f)
                row_count = 0
                for _ in reader:
                    row_count += 1
                    if row_count > 1000:
                        break
        except Exception as e:
            errors.append(f"文件编码错误: {str(e)}")
    except Exception as e:
        errors.append(f"文件读取错误: {str(e)}")

    is_valid = len(errors) == 0
    if is_valid:
        return {"code": "SUCCESS", "data": {"valid": True}, "message": "CSV格式正确"}
    else:
        return {"code": "ERR_READ_CSV", "data": {"valid": False, "errors": errors},
                "message": f"CSV格式有 {len(errors)} 个问题"}


def _validate_chart_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """验证图表数据格式（内部helper） - 小沈 2026-05-18，从env_check_tools.py迁入"""
    errors = []
    if not isinstance(data, dict):
        errors.append("data必须是字典类型")
    else:
        if "labels" not in data:
            errors.append("缺少labels字段")
        elif not isinstance(data["labels"], list):
            errors.append("labels必须是数组类型")
        if "values" not in data:
            errors.append("缺少values字段")
        elif not isinstance(data["values"], list):
            errors.append("values必须是数组类型")
        if "labels" in data and "values" in data:
            if isinstance(data["labels"], list) and isinstance(data["values"], list):
                if len(data["labels"]) != len(data["values"]):
                    errors.append(f"labels和values长度不一致: labels={len(data['labels'])}, values={len(data['values'])}")
    is_valid = len(errors) == 0
    if is_valid:
        return {"code": "SUCCESS", "data": {"valid": True}, "message": "图表数据格式正确"}
    else:
        return {"code": "ERR_GENERATE_CHART", "data": {"valid": False, "errors": errors},
                "message": f"图表数据格式有 {len(errors)} 个问题"}


def _serialize_pandas_rows(df) -> List[Any]:
    """将DataFrame行数据序列化为JSON安全格式 - 小沈 2026-05-18"""
    import pandas as pd
    rows = df.values.tolist()
    serialized_rows = []
    for row in rows:
        serialized_row = []
        for val in row:
            if pd.isna(val):
                serialized_row.append(None)
            elif hasattr(val, 'item'):
                serialized_row.append(val.item())
            else:
                serialized_row.append(val)
        serialized_rows.append(serialized_row)
    return serialized_rows


def _read_csv_pandas(
    file_path: str,
    encoding: str = "utf-8",
    delimiter: str = ",",
    has_header: bool = True,
    max_rows: int = 1000,
) -> Dict[str, Any]:
    """使用pandas读取CSV文件 - 小沈 2026-05-18（从data_analysis迁入）"""
    if not _check_pandas():
        return {"code": "ERR_NO_PANDAS", "data": None, "message": "pandas库未安装，请先执行: pip install pandas"}
    try:
        import pandas as pd
        path = Path(file_path)
        if not path.exists():
            return {"code": "ERR_READ_CSV_DATAFRAME", "data": None, "message": f"文件不存在: {file_path}"}
        header = 0 if has_header else None
        df = pd.read_csv(path, encoding=encoding, delimiter=delimiter, header=header, nrows=max_rows)
        columns = df.columns.tolist()
        serialized_rows = _serialize_pandas_rows(df)
        dtypes = {col: str(dtype) for col, dtype in df.dtypes.items()}
        return {"code": "SUCCESS", "data": {"columns": columns, "rows": serialized_rows, "row_count": len(serialized_rows), "dtypes": dtypes}, "message": f"成功读取CSV文件: {file_path}，共 {len(serialized_rows)} 行数据"}
    except Exception as e:
        return {"code": "ERR_READ_CSV_DATAFRAME", "data": None, "message": f"读取CSV文件失败: {str(e)}"}


def _read_excel_pandas(
    file_path: str,
    sheet_name: Optional[str] = None,
    max_rows: int = 1000,
) -> Dict[str, Any]:
    """使用pandas读取Excel文件 - 小沈 2026-05-18（从data_analysis迁入）"""
    if not _check_pandas():
        return {"code": "ERR_NO_PANDAS", "data": None, "message": "pandas库未安装，请先执行: pip install pandas openpyxl"}
    if not _check_openpyxl():
        return {"code": "ERR_NO_OPENPYXL", "data": None, "message": "openpyxl库未安装，请先执行: pip install openpyxl"}
    try:
        import pandas as pd
        path = Path(file_path)
        if not path.exists():
            return {"code": "ERR_READ_EXCEL_DATAFRAME", "data": None, "message": f"文件不存在: {file_path}"}
        df = pd.read_excel(path, sheet_name=sheet_name if sheet_name else 0, nrows=max_rows, engine="openpyxl")
        columns = df.columns.tolist()
        serialized_rows = _serialize_pandas_rows(df)
        dtypes = {col: str(dtype) for col, dtype in df.dtypes.items()}
        actual_sheet = sheet_name if sheet_name else "Sheet1"
        return {"code": "SUCCESS", "data": {"columns": columns, "rows": serialized_rows, "row_count": len(serialized_rows), "dtypes": dtypes, "sheet_name": actual_sheet}, "message": f"成功读取Excel文件: {file_path}，共 {len(serialized_rows)} 行数据"}
    except Exception as e:
        return {"code": "ERR_READ_EXCEL_DATAFRAME", "data": None, "message": f"读取Excel文件失败: {str(e)}"}


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


# ============================================================
# 内部读取函数（原 read_pdf/read_docx/read_xlsx/read_pptx 逻辑）
# ============================================================

def _read_pdf(
    file_path: str,
    pages: str = None,
    extract_images: bool = False,
    extract_tables: bool = False
) -> Dict[str, Any]:
    """读取PDF文件并提取文本内容（内部函数） - 小健 2026-05-18
    【2026-05-18 小沈】增加extract_images图片提取功能
    """
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
        images_data = []

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
                
                if extract_tables:
                    tables = page.extract_tables()
                    if tables:
                        for idx, table in enumerate(tables):
                            tables_data.append({
                                "page": page_num,
                                "table_idx": idx,
                                "data": table
                            })
                
                if extract_images:
                    images = page.images
                    if images:
                        for idx, img in enumerate(images):
                            images_data.append({
                                "page": page_num,
                                "image_idx": idx,
                                "x0": float(img.get("x0", 0)),
                                "y0": float(img.get("y0", 0)),
                                "x1": float(img.get("x1", 0)),
                                "y1": float(img.get("y1", 0)),
                                "width": float(img.get("width", 0)),
                                "height": float(img.get("height", 0)),
                            })

        result_data = {
            "text": "\n\n".join(all_text),
            "page_count": page_count,
            "pages_read": pages_read,
        }
        
        if extract_tables and tables_data:
            result_data["tables"] = tables_data
            result_data["table_count"] = len(tables_data)
        
        if extract_images and images_data:
            result_data["images"] = images_data
            result_data["image_count"] = len(images_data)

        full_text = result_data["text"]
        _llm = {
            "文件": file_path,
            "页数": f"{page_count}页(读取{len(pages_read)}页)",
            "文本长度": f"{len(full_text)}字符",
            "内容": full_text,
        }
        if extract_tables and tables_data:
            _llm["表格数"] = len(tables_data)
        if extract_images and images_data:
            _llm["图片数"] = len(images_data)
        
        msg = f"成功读取PDF文件: {file_path}，共读取 {len(pages_read)} 页"
        if extract_tables and tables_data:
            msg += f"，{len(tables_data)} 个表格"
        if extract_images and images_data:
            msg += f"，{len(images_data)} 张图片"
        
        return {
            "code": "SUCCESS",
            "data": result_data,
            "message": msg,
            "llm_data": _llm,
            "capabilities_used": ["pdfplumber"],
            "capabilities_missing": ["pytesseract"]
        }
    except Exception as e:
        return {
            "code": "ERR_READ_PDF",
            "data": None,
            "message": f"读取PDF文件失败: {str(e)}"
        }


def _read_docx(
    file_path: str,
    extract_tables: bool = False
) -> Dict[str, Any]:
    """读取Word文档并提取文本内容（内部函数） - 小健 2026-05-18"""
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
        
        _llm = {
            "文件": file_path,
            "段落数": len(paragraphs),
            "文本长度": f"{len(text)}字符",
            "内容": text,
        }
        return {
            "code": "SUCCESS",
            "data": result_data,
            "message": f"成功读取Word文档: {file_path}，共 {len(paragraphs)} 段",
            "llm_data": _llm,
            "capabilities_used": ["python-docx"]
        }
    except Exception as e:
        return {
            "code": "ERR_READ_DOCX",
            "data": None,
            "message": f"读取Word文档失败: {str(e)}"
        }


def _read_xlsx(
    file_path: str,
    sheet_name: str = None,
    max_rows: int = 1000,
    header: bool = True
) -> Dict[str, Any]:
    """读取Excel文件并提取表格数据（内部函数） - 小健 2026-05-18"""
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
            "message": f"成功读取Excel文件: {file_path}，工作表: {ws.title}，共 {row_count} 行数据",
            "capabilities_used": ["openpyxl"],
            "capabilities_missing": ["pandas"]
        }
    except Exception as e:
        return {
            "code": "ERR_READ_XLSX",
            "data": None,
            "message": f"读取Excel文件失败: {str(e)}"
        }


def _read_csv_stdlib(
    file_path: str,
    encoding: str = "utf-8",
    delimiter: str = ",",
    has_header: bool = True,
    max_rows: int = 1000
) -> Dict[str, Any]:
    """使用标准库csv读取CSV文件（内部函数）— 小健 2026-05-18"""
    import csv
    
    try:
        path = Path(file_path)
        if not path.exists():
            return {
                "code": "ERR_READ_CSV",
                "data": None,
                "message": f"文件不存在: {file_path}"
            }
        
        rows = []
        columns = []
        with open(path, "r", encoding=encoding, newline="") as f:
            reader = csv.reader(f, delimiter=delimiter)
            for i, row in enumerate(reader):
                if i >= max_rows:
                    break
                if i == 0:
                    if has_header:
                        columns = row
                    else:
                        columns = [f"col_{j}" for j in range(len(row))]
                        rows.append(row)
                else:
                    rows.append(row)
        
        return {
            "code": "SUCCESS",
            "data": {
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
            },
            "message": f"成功读取CSV文件: {file_path}，共 {len(rows)} 行数据"
        }
    except Exception as e:
        return {
            "code": "ERR_READ_CSV",
            "data": None,
            "message": f"读取CSV文件失败: {str(e)}"
        }


def _read_pptx(
    file_path: str,
    extract_notes: bool = False
) -> Dict[str, Any]:
    """读取PPT幻灯片（内部函数） - 小健 2026-05-18"""
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

        _total_text = sum(len(s.get("text", "")) for s in slides_data)
        _llm = {
            "文件": file_path,
            "幻灯片数": len(prs.slides),
            "文本总长度": f"{_total_text}字符",
            "幻灯片内容": [{"页码": s["slide_num"], "文本": s.get("text", "")} for s in slides_data],
        }
        if extract_notes and notes_data:
            _llm["备注数"] = len(notes_data)

        return {
            "code": "SUCCESS",
            "data": result_data,
            "message": f"成功读取PPT文件: {file_path}，共 {len(prs.slides)} 页",
            "llm_data": _llm,
            "capabilities_used": ["python-pptx"]
        }
    except Exception as e:
        return {
            "code": "ERR_READ_PPTX",
            "data": None,
            "message": f"读取PPT文件失败: {str(e)}"
        }


# ============================================================
# 内部写入函数（原 write_docx/write_xlsx/write_pdf/write_pptx 逻辑）
# ============================================================

def _write_docx(
    file_path: str,
    content: str = None,
    paragraphs: list = None,
    title: str = None,
    table_data: list = None
) -> Dict[str, Any]:
    """写入Word文档（内部函数） - 小健 2026-05-18"""
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
        
        if title:
            doc.add_heading(title, 0)
        
        if paragraphs:
            for para in paragraphs:
                doc.add_paragraph(para)
        
        if content:
            doc.add_paragraph(content)
        
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


def _write_xlsx(
    file_path: str,
    data: dict,
    sheet_name: str = "Sheet1"
) -> Dict[str, Any]:
    """写入Excel文件（内部函数） - 小健 2026-05-18"""
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


def _write_pdf(
    file_path: str,
    title: str = None,
    content: str = None,
    paragraphs: list = None,
    table_data: list = None
) -> Dict[str, Any]:
    """写入PDF文档（内部函数） - 小健 2026-05-18"""
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


def _write_pptx(
    file_path: str,
    title: str = None,
    slides: list = None
) -> Dict[str, Any]:
    """写入PPT幻灯片（内部函数） - 小健 2026-05-18"""
    if not _check_module("pptx"):
        return {
            "code": "ERR_NO_PPTX",
            "data": None,
            "message": "python-pptx库未安装，请先执行: pip install python-pptx"
        }
    
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt
        
        prs = Presentation()
        
        if title:
            title_slide_layout = prs.slide_layouts[0]
            slide = prs.slides.add_slide(title_slide_layout)
            title_shape = slide.shapes.title
            title_shape.text = title
        
        if slides:
            for slide_data in slides:
                slide_title = slide_data.get("title", "幻灯片")
                content = slide_data.get("content", "")
                
                content_layout = prs.slide_layouts[1]
                slide = prs.slides.add_slide(content_layout)
                
                if slide.shapes.title:
                    slide.shapes.title.text = slide_title
                
                for shape in slide.shapes:
                    if shape.has_text_frame and not shape.text_frame.text.strip():
                        text_frame = shape.text_frame
                        text_frame.clear()
                        p = text_frame.paragraphs[0]
                        p.text = content
                        p.font.size = Pt(18)
                        break
        
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


# ============================================================
# 路由函数 — LLM调用的统一入口
# ============================================================

def read_document(
    file_path: str,
    pages: Optional[str] = None,
    extract_tables: bool = False,
    extract_images: bool = False,
    extract_notes: bool = False,
    sheet_name: Optional[str] = None,
    max_rows: int = 1000,
    header: bool = True,
    use_pandas: bool = False,
    encoding: str = "utf-8",
    delimiter: Optional[str] = None,
) -> Dict[str, Any]:
    """读取文档内容 — 小健 2026-05-18
    合并 read_pdf + read_docx + read_pptx + read_xlsx + read_csv
    按文件后缀自动路由到对应解析器
    支持 .doc 后缀（通过 win32com 降级处理）
    支持 .csv/.tsv 后缀（use_pandas=True时使用pandas，否则使用标准库csv）
    """
    path = Path(file_path)
    suffix = path.suffix.lower()
    
    if suffix == ".pdf":
        check = _check_pdf_readable(file_path)
        if check["code"] != "SUCCESS" or not check["data"].get("readable", False):
            return check
        result = _read_pdf(file_path, pages=pages, extract_tables=extract_tables, extract_images=extract_images)
    elif suffix in (".docx", ".doc"):
        check = _check_docx_readable(file_path)
        if check["code"] != "SUCCESS" or not check["data"].get("readable", False):
            return check
        result = _read_docx(file_path, extract_tables=extract_tables)
    elif suffix == ".pptx":
        result = _read_pptx(file_path, extract_notes=extract_notes)
    elif suffix in (".xlsx", ".xls"):
        check = _check_xlsx_readable(file_path)
        if check["code"] != "SUCCESS" or not check["data"].get("readable", False):
            return check
        if use_pandas:
            result = _read_excel_pandas(file_path=file_path, sheet_name=sheet_name, max_rows=max_rows)
        else:
            result = _read_xlsx(file_path, sheet_name=sheet_name, max_rows=max_rows, header=header)
    elif suffix in (".csv", ".tsv"):
        actual_delimiter = "\t" if suffix == ".tsv" else (delimiter or ",")
        if use_pandas:
            result = _read_csv_pandas(file_path=file_path, encoding=encoding, delimiter=actual_delimiter, has_header=header, max_rows=max_rows)
        else:
            result = _read_csv_stdlib(file_path, encoding=encoding, delimiter=actual_delimiter, has_header=header, max_rows=max_rows)
    else:
        return {"code": "ERR_UNSUPPORTED_FORMAT", "data": None,
                "message": f"不支持的格式: {suffix}。支持: .pdf/.doc/.docx/.xlsx/.xls/.pptx/.csv/.tsv"}
    
    if result.get("code") == "SUCCESS":
        result["next_actions"] = build_next_actions([
            ("write_document", "修改文档", "需要编辑文档时"),
            ("convert_document", "转换格式", "需要转PDF/DOCX时"),
            ("analyze_data", "分析数据", "读取的是数据文件时"),
        ])
        # 透传内部函数的capabilities字段 - 小沈 2026-05-19
        if "capabilities_used" not in result:
            if suffix == ".pdf":
                result["capabilities_used"] = ["pdfplumber"]
                result["capabilities_missing"] = ["pytesseract"]
            elif suffix in (".docx", ".doc"):
                result["capabilities_used"] = ["python-docx"]
            elif suffix == ".pptx":
                result["capabilities_used"] = ["python-pptx"]
            elif suffix in (".xlsx", ".xls"):
                result["capabilities_used"] = ["openpyxl"]
                result["capabilities_missing"] = ["pandas"]
    return result


def write_document(
    file_path: str,
    content: Optional[str] = None,
    paragraphs: Optional[List[str]] = None,
    title: Optional[str] = None,
    table_data: Optional[List] = None,
    data: Optional[Dict[str, Any]] = None,
    sheet_name: str = "Sheet1",
    slides: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """写入文档 — 小健 2026-05-18
    合并 write_docx + write_xlsx + write_pdf + write_pptx
    按文件后缀自动路由到对应写入器
    """
    path = Path(file_path)
    suffix = path.suffix.lower()
    path.parent.mkdir(parents=True, exist_ok=True)
    
    if suffix == ".docx":
        result = _write_docx(file_path, content=content, paragraphs=paragraphs, title=title, table_data=table_data)
    elif suffix == ".xlsx":
        if data is None:
            data = {"headers": [], "rows": []}
        result = _write_xlsx(file_path, data=data, sheet_name=sheet_name)
    elif suffix == ".pdf":
        result = _write_pdf(file_path, title=title, content=content, paragraphs=paragraphs, table_data=table_data)
    elif suffix == ".pptx":
        result = _write_pptx(file_path, title=title, slides=slides)
    else:
        return {"code": "ERR_UNSUPPORTED_FORMAT", "data": None,
                "message": f"不支持的输出格式: {suffix}。支持: .docx/.xlsx/.pdf/.pptx"}
    
    if result.get("code") == "SUCCESS":
        result["next_actions"] = build_next_actions([
            ("read_document", "验证写入结果", "需要确认内容时"),
        ])
    return result


def convert_document(
    input_path: str,
    output_format: str = "pdf",
    output_path: str = None
) -> Dict[str, Any]:
    """文档格式转换 - 小健 2026-05-06 output_format改可选对齐Schema"""
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
            "message": f"成功转换: {src_ext} → .pdf",
            "next_actions": build_next_actions([
                ("read_document", "读取转换后文件", "需要查看结果时"),
            ])
        }
    except Exception as e:
        return {
            "code": "ERR_CONVERT_DOCUMENT",
            "data": None,
            "message": f"文档转换失败: {str(e)}"
        }


# === 公开接口定义 — 小健 2026-05-18 ===
__all__ = [
    "read_document",
    "write_document",
    "convert_document",
]
