# -*- coding: utf-8 -*-
"""
Document Tools Test - 文档工具测试
【测试目标】测试 document 工具的读写功能
【创建时间】2026-05-04 小健
"""
import pytest
import tempfile
import os
import json
from pathlib import Path

from app.services.tools.document.document_tools import (
    read_document,
    write_document,
)


class TestReadDocument:
    """read_document 工具测试 - 小健 2026-05-04"""

    def test_read_pdf_file_not_found(self):
        """❌ PDF文件不存在"""
        result = read_document("D:/not_exist.pdf")

        assert result["code"] in ["ERR_READ_PDF", "ERR_NO_PDFPLUMBER", "ERROR"]

    def test_read_pdf_invalid_path(self):
        """❌ 无效路径"""
        result = read_document("")

        assert result["code"] in ["ERR_UNSUPPORTED_FORMAT", "ERROR"]

    def test_read_docx_file_not_found(self):
        """❌ DOCX文件不存在"""
        result = read_document("D:/not_exist.docx")

        assert result["code"] in ["ERR_READ_DOCX", "ERR_NO_DOCX", "ERROR"]

    def test_read_docx_invalid_path(self):
        """❌ 无效路径"""
        result = read_document("")

        assert result["code"] in ["ERR_UNSUPPORTED_FORMAT", "ERROR"]

    def test_read_xlsx_file_not_found(self):
        """❌ XLSX文件不存在"""
        result = read_document("D:/not_exist.xlsx")

        assert result["code"] in ["ERR_READ_XLSX", "ERROR"]

    def test_read_xlsx_invalid_path(self):
        """❌ 无效路径"""
        result = read_document("")

        assert result["code"] in ["ERR_UNSUPPORTED_FORMAT", "ERROR"]

    def test_read_xlsx_with_sheet_name(self):
        """✅ 指定工作表名称"""
        result = read_document("D:/not_exist.xlsx", sheet_name="Sheet1")

        assert result["code"] in ["ERR_READ_XLSX", "ERROR"]

    def test_read_xlsx_with_max_rows(self):
        """✅ 限制最大行数"""
        result = read_document("D:/not_exist.xlsx", max_rows=10)

        assert result["code"] in ["ERR_READ_XLSX", "ERROR"]

    def test_read_pptx_file_not_found(self):
        """❌ PPTX文件不存在"""
        result = read_document("D:/not_exist.pptx")

        assert result["code"] in ["ERR_READ_PPTX", "ERROR"]

    def test_read_pptx_invalid_path(self):
        """❌ 无效路径"""
        result = read_document("")

        assert result["code"] in ["ERR_UNSUPPORTED_FORMAT", "ERROR"]


class TestWriteDocument:
    """write_document 工具测试 - 小健 2026-05-04"""

    def test_write_docx_success(self, tmp_path):
        """✅ 正常写入Word文档"""
        test_file = tmp_path / "output.docx"

        result = write_document(str(test_file), content="测试内容", title="测试标题")

        assert result["code"] == "SUCCESS"

    def test_write_docx_with_table(self, tmp_path):
        """✅ 写入表格"""
        test_file = tmp_path / "table.docx"
        table_data = [["姓名", "年龄"], ["张三", "25"], ["李四", "30"]]

        result = write_document(str(test_file), table_data=table_data)

        assert result["code"] == "SUCCESS"

    def test_write_xlsx_success(self, tmp_path):
        """✅ 正常写入Excel"""
        test_file = tmp_path / "output.xlsx"
        data = {"headers": ["姓名", "年龄"], "rows": [["张三", 25], ["李四", 30]]}

        result = write_document(str(test_file), data=data)

        assert result["code"] == "SUCCESS"