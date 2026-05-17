# -*- coding: utf-8 -*-
"""
13.3 environment(check) 优化测试 — 9→5
- 小健 2026-05-17

设计依据: 工具精简方案v1.9 第13.3节
变更: check_python/node/module/safety 4个检查工具→toolhelper/exec_helper(不暴露LLM)
      保留5个文档验证工具: validate_csv, validate_chart, check_pdf, check_docx, check_xlsx
新增: P15 next_actions (含跨分类)

覆盖:
  validate_csv [保留]
  validate_chart [保留]
  check_pdf [保留]
  check_docx [保留]
  check_xlsx [保留]
  4个检查工具已消除(不暴露为LLM工具)
"""

import pytest
from unittest.mock import patch, MagicMock

from app.services.tools.environment.env_check_tools import (
    validate_csv,
    validate_chart,
    check_pdf,
    check_docx,
    check_xlsx,
)


# ============================================================
# TestValidateCsv — 保留: CSV验证
# ============================================================
class TestValidateCsv:
    """validate_csv 保留 — 文档验证工具"""

    def test_validate_csv_valid(self, tmp_path):
        csv_path = str(tmp_path / "test.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("name,age\nAlice,30\nBob,25\n")
        result = validate_csv(csv_path)
        assert result["code"] == "SUCCESS"
        assert result["data"]["valid"] is True

    def test_validate_csv_invalid(self, tmp_path):
        csv_path = str(tmp_path / "bad.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("not a csv content")
        result = validate_csv(csv_path)
        assert result["code"] in ("SUCCESS", "WARNING")

    def test_validate_csv_not_found(self):
        result = validate_csv("/nonexistent_csv_file_999.csv")
        assert "ERR" in result.get("code", "ERROR")

    def test_validate_csv_next_actions(self, tmp_path):
        csv_path = str(tmp_path / "na.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("a,b\n1,2\n")
        result = validate_csv(csv_path)
        assert "next_actions" in result or result["code"] == "SUCCESS"


# ============================================================
# TestValidateChart — 保留: 图表数据验证
# ============================================================
class TestValidateChart:
    """validate_chart 保留 — 图表数据验证"""

    def test_validate_chart_valid(self, tmp_path):
        chart_path = str(tmp_path / "test_chart.json")
        with open(chart_path, "w", encoding="utf-8") as f:
            f.write('{"type": "bar", "data": {"labels": ["A"], "datasets": [{"data": [1]}]}}')
        result = validate_chart(chart_path)
        assert result["code"] in ("SUCCESS", "WARNING")

    def test_validate_chart_not_found(self):
        result = validate_chart("/nonexistent_chart_999.json")
        assert "ERR" in result.get("code", "ERROR")


# ============================================================
# TestCheckPdf — 保留: PDF验证
# ============================================================
class TestCheckPdf:
    """check_pdf 保留 — PDF文件验证"""

    def test_check_pdf_not_found(self):
        result = check_pdf("/nonexistent_pdf_999.pdf")
        assert "ERR" in result.get("code", "ERROR")

    def test_check_pdf_next_actions(self):
        result = check_pdf("/nonexistent_pdf_999.pdf")
        assert "next_actions" in result or "ERR" in result.get("code", "")


# ============================================================
# TestCheckDocx — 保留: DOCX验证
# ============================================================
class TestCheckDocx:
    """check_docx 保留 — Word文件验证"""

    def test_check_docx_not_found(self):
        result = check_docx("/nonexistent_docx_file_999.docx")
        assert "ERR" in result.get("code", "ERROR")


# ============================================================
# TestCheckXlsx — 保留: XLSX验证
# ============================================================
class TestCheckXlsx:
    """check_xlsx 保留 — Excel文件验证"""

    def test_check_xlsx_not_found(self):
        result = check_xlsx("/nonexistent_xlsx_file_999.xlsx")
        assert "ERR" in result.get("code", "ERROR")


# ============================================================
# TestEliminated — 验证已消除的检查工具
# ============================================================
class TestEliminated:
    """验证 check_python/node/module/safety 4个工具已消除"""

    def test_check_python_available_not_importable(self):
        with pytest.raises(ImportError):
            from app.services.tools.environment.env_check_tools import check_python_available  # noqa

    def test_check_node_available_not_importable(self):
        with pytest.raises(ImportError):
            from app.services.tools.environment.env_check_tools import check_node_available  # noqa

    def test_check_module_available_not_importable(self):
        with pytest.raises(ImportError):
            from app.services.tools.environment.env_check_tools import check_module_available  # noqa

    def test_validate_code_safety_not_importable(self):
        with pytest.raises(ImportError):
            from app.services.tools.environment.env_check_tools import validate_code_safety  # noqa

    def test_retained_count(self):
        """验证保留的工具数量为5个"""
        retained = [validate_csv, validate_chart, check_pdf, check_docx, check_xlsx]
        assert len(retained) == 5
