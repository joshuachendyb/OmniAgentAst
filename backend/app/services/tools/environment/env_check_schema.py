# -*- coding: utf-8 -*-
"""
Env Check 工具参数 Schema 定义

【创建时间】2026-05-02 小沈
【设计依据】按文档第8.4节 Tool 83-91 定义

Author: 小沈 - 2026-05-02
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class ValidateCodeSafetyInput(BaseModel):
    """validate_code_safety 工具的输入参数（Tool 84）"""
    code: str = Field(
        ...,
        description="要验证的代码。检查是否存在危险操作，如系统调用、文件删除、网络请求等"
    )


class CheckModuleAvailableInput(BaseModel):
    """check_module_available 工具的输入参数（Tool 86）"""
    module_name: str = Field(
        ...,
        description="模块名称。如 pandas、numpy、matplotlib"
    )


class ValidateCsvFormatInput(BaseModel):
    """validate_csv_format 工具的输入参数（Tool 87）"""
    file_path: str = Field(
        ...,
        description="CSV文件路径。如 D:/data/users.csv"
    )


class ValidateChartDataInput(BaseModel):
    """validate_chart_data 工具的输入参数（Tool 88）"""
    data: Dict[str, Any] = Field(
        ...,
        description="图表数据（JSON格式）。检查是否包含必要的 labels 和 values 字段"
    )


class CheckPdfReadableInput(BaseModel):
    """check_pdf_readable 工具的输入参数（Tool 89）"""
    file_path: str = Field(
        ...,
        description="PDF文件路径。如 D:/documents/report.pdf"
    )


class CheckDocxReadableInput(BaseModel):
    """check_docx_readable 工具的输入参数（Tool 90）"""
    file_path: str = Field(
        ...,
        description="Word文件路径。如 D:/documents/report.docx"
    )


class CheckXlsxReadableInput(BaseModel):
    """check_xlsx_readable 工具的输入参数（Tool 91）"""
    file_path: str = Field(
        ...,
        description="Excel文件路径。如 D:/data/report.xlsx"
    )
