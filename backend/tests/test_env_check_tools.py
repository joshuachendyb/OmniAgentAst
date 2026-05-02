# -*- coding: utf-8 -*-
"""
环境检查工具测试模块

【创建时间】2026-05-02 小沈

Author: 小沈 - 2026-05-02
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.tools.env_check.env_check_tools import (
    check_python_available,
    validate_code_safety,
    check_node_available,
    check_module_available,
    validate_csv_format,
    validate_chart_data,
    check_pdf_readable,
    check_docx_readable,
    check_xlsx_readable,
)


class TestCheckPythonAvailable:
    """check_python_available 测试 - 小沈 2026-05-02"""

    def test_python_available(self):
        result = check_python_available()
        assert result["code"] == "SUCCESS"
        assert result["data"]["available"] is True
        assert result["data"]["version"] is not None


class TestValidateCodeSafety:
    """validate_code_safety 测试 - 小沈 2026-05-02"""

    def test_safe_code(self):
        result = validate_code_safety(code="x = 1 + 2")
        assert result["code"] == "SUCCESS"
        assert result["data"]["safe"] is True

    def test_dangerous_os_system(self):
        result = validate_code_safety(code="os.system('rm -rf /')")
        assert result["code"] == "SUCCESS"
        assert result["data"]["safe"] is False
        assert result["data"]["warning_count"] > 0

    def test_dangerous_eval(self):
        result = validate_code_safety(code="eval('1+1')")
        assert result["code"] == "SUCCESS"
        assert result["data"]["safe"] is False

    def test_dangerous_subprocess(self):
        result = validate_code_safety(code="subprocess.run(['ls'])")
        assert result["code"] == "SUCCESS"
        assert result["data"]["safe"] is False


class TestCheckNodeAvailable:
    """check_node_available 测试 - 小沈 2026-05-02"""

    def test_node_check(self):
        result = check_node_available()
        assert result["code"] == "SUCCESS"
        assert "available" in result["data"]


class TestCheckModuleAvailable:
    """check_module_available 测试 - 小沈 2026-05-02"""

    def test_os_module(self):
        result = check_module_available(module_name="os")
        assert result["code"] == "SUCCESS"
        assert result["data"]["available"] is True

    def test_nonexistent_module(self):
        result = check_module_available(module_name="nonexistent_module_xyz")
        assert result["code"] == "SUCCESS"
        assert result["data"]["available"] is False


class TestValidateCsvFormat:
    """validate_csv_format 测试 - 小沈 2026-05-02"""

    def test_file_not_exists(self):
        result = validate_csv_format(file_path="D:/nonexistent/file.csv")
        assert result["data"]["valid"] is False

    def test_valid_csv(self):
        fd, path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("name,age\nAlice,25\nBob,30\n")
        try:
            result = validate_csv_format(file_path=path)
            assert result["data"]["valid"] is True
        finally:
            os.unlink(path)

    def test_invalid_extension(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("{}")
        try:
            result = validate_csv_format(file_path=path)
            assert result["data"]["valid"] is False
        finally:
            os.unlink(path)


class TestValidateChartData:
    """validate_chart_data 测试 - 小沈 2026-05-02"""

    def test_valid_data(self):
        result = validate_chart_data(data={"labels": ["A", "B"], "values": [10, 20]})
        assert result["data"]["valid"] is True

    def test_missing_labels(self):
        result = validate_chart_data(data={"values": [10, 20]})
        assert result["data"]["valid"] is False

    def test_missing_values(self):
        result = validate_chart_data(data={"labels": ["A", "B"]})
        assert result["data"]["valid"] is False

    def test_length_mismatch(self):
        result = validate_chart_data(data={"labels": ["A", "B", "C"], "values": [10, 20]})
        assert result["data"]["valid"] is False


class TestCheckPdfReadable:
    """check_pdf_readable 测试 - 小沈 2026-05-02"""

    def test_file_not_exists(self):
        result = check_pdf_readable(file_path="D:/nonexistent/file.pdf")
        assert result["data"]["readable"] is False


class TestCheckDocxReadable:
    """check_docx_readable 测试 - 小沈 2026-05-02"""

    def test_file_not_exists(self):
        result = check_docx_readable(file_path="D:/nonexistent/file.docx")
        assert result["data"]["readable"] is False

    def test_readable_docx(self):
        try:
            import docx
        except ImportError:
            pytest.skip("python-docx not installed")

        fd, path = tempfile.mkstemp(suffix=".docx")
        os.close(fd)
        try:
            doc = docx.Document()
            doc.add_paragraph("test")
            doc.save(path)
            result = check_docx_readable(file_path=path)
            assert result["data"]["readable"] is True
        finally:
            if os.path.exists(path):
                os.unlink(path)


class TestCheckXlsxReadable:
    """check_xlsx_readable 测试 - 小沈 2026-05-02"""

    def test_file_not_exists(self):
        result = check_xlsx_readable(file_path="D:/nonexistent/file.xlsx")
        assert result["data"]["readable"] is False
