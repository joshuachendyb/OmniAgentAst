# -*- coding: utf-8 -*-
"""
第15章Document分类精简深度检测测试 - 小健 2026-05-18
覆盖路由逻辑、__all__定义、注册表一致性等边界情况
"""

import sys
from app.services.tools.document.document_tools import read_document
from app.services.tools.document.document_tools import write_document
from app.services.tools.document import document_tools
from app.services.tools.document import document_register
from app.services.tools.document import __all__ as doc_all
from app.services.tools import document
from app.services.tools.lazy_loader import CATEGORY_MODULES
from app.services.tools.document.document_tools import _read_pdf
from app.services.tools.document.document_tools import _read_docx
from app.services.tools.document.document_tools import _read_xlsx
from app.services.tools.document.document_tools import _read_pptx
from app.services.tools.document.document_tools import _write_docx
from app.services.tools.document.document_tools import _write_xlsx
from app.services.tools.document.document_tools import _write_pdf
from app.services.tools.document.document_tools import _write_pptx
sys.path.insert(0, r"G:\OmniAgentAs-desk\backend")

import os
import tempfile
import pytest
from pathlib import Path


class TestReadDocumentRouting:
    """read_document路由函数深度测试"""

    def test_unsupported_format(self):
        """不支持格式返回ERR_DOC_FORMAT_NOT_SUPPORTED"""
        result = read_document("test.xyz")
        assert result["code"] == "ERR_DOC_FORMAT_NOT_SUPPORTED"
        assert "不支持的格式" in result["message"]

    def test_unsupported_format_uppercase(self):
        """不支持格式大写后缀"""
        result = read_document("test.TXT")
        assert result["code"] == "ERR_DOC_FORMAT_NOT_SUPPORTED"

    def test_pdf_routes_correctly(self):
        """.pdf后缀正确路由（不返回ERR_DOC_FORMAT_NOT_SUPPORTED）"""
        result = read_document("nonexistent.pdf")
        assert result["code"] != "ERR_DOC_FORMAT_NOT_SUPPORTED"

    def test_pdf_uppercase_routes(self):
        """.PDF大写后缀正确路由"""
        result = read_document("nonexistent.PDF")
        assert result["code"] != "ERR_DOC_FORMAT_NOT_SUPPORTED"

    def test_docx_routes_correctly(self):
        """.docx后缀正确路由"""
        result = read_document("nonexistent.docx")
        assert result["code"] != "ERR_DOC_FORMAT_NOT_SUPPORTED"

    def test_docx_uppercase_routes(self):
        """.DOCX大写后缀正确路由"""
        result = read_document("nonexistent.DOCX")
        assert result["code"] != "ERR_DOC_FORMAT_NOT_SUPPORTED"

    def test_xlsx_routes_correctly(self):
        """.xlsx后缀正确路由"""
        result = read_document("nonexistent.xlsx")
        assert result["code"] != "ERR_DOC_FORMAT_NOT_SUPPORTED"

    def test_xls_routes_correctly(self):
        """.xls后缀正确路由到_read_xlsx"""
        result = read_document("nonexistent.xls")
        assert result["code"] != "ERR_DOC_FORMAT_NOT_SUPPORTED"

    def test_pptx_routes_correctly(self):
        """.pptx后缀正确路由"""
        result = read_document("nonexistent.pptx")
        assert result["code"] != "ERR_DOC_FORMAT_NOT_SUPPORTED"

    def test_doc_routes_correctly(self):
        """.doc后缀正确路由（P2修复：通过win32com降级）"""
        result = read_document("nonexistent.doc")
        assert result["code"] != "ERR_DOC_FORMAT_NOT_SUPPORTED", "read_document应支持.doc后缀（通过win32com降级）"

    def test_csv_routes_correctly(self):
        """.csv后缀正确路由"""
        result = read_document("nonexistent.csv")
        assert result["code"] != "ERR_DOC_FORMAT_NOT_SUPPORTED", "read_document应支持.csv后缀"
        assert result["code"] == "ERR_DOC_READ_CSV", f"CSV文件不存在应返回ERR_DOC_READ_CSV: {result['code']}"

    def test_tsv_routes_correctly(self):
        """.tsv后缀正确路由"""
        result = read_document("nonexistent.tsv")
        assert result["code"] != "ERR_DOC_FORMAT_NOT_SUPPORTED", "read_document应支持.tsv后缀"

    def test_csv_uppercase_routes(self):
        """.CSV大写后缀正确路由"""
        result = read_document("nonexistent.CSV")
        assert result["code"] != "ERR_DOC_FORMAT_NOT_SUPPORTED"


class TestWriteDocumentRouting:
    """write_document路由函数深度测试"""

    def test_unsupported_format(self):
        """不支持格式返回ERR_DOC_FORMAT_NOT_SUPPORTED"""
        result = write_document("test.xyz", content="test")
        assert result["code"] == "ERR_DOC_FORMAT_NOT_SUPPORTED"

    def test_docx_routes_correctly(self):
        """.docx后缀正确路由"""
        result = write_document(os.path.join(tempfile.gettempdir(), "test_write_12345.docx"), content="test")
        assert result["code"] != "ERR_DOC_FORMAT_NOT_SUPPORTED"
        Path(os.path.join(tempfile.gettempdir(), "test_write_12345.docx")).unlink(missing_ok=True)

    def test_xlsx_routes_correctly(self):
        """.xlsx后缀正确路由"""
        result = write_document(os.path.join(tempfile.gettempdir(), "test_write_12345.xlsx"), data={"Sheet1": [["a", "b"]]})
        assert result["code"] != "ERR_DOC_FORMAT_NOT_SUPPORTED"
        Path(os.path.join(tempfile.gettempdir(), "test_write_12345.xlsx")).unlink(missing_ok=True)

    def test_pdf_routes_correctly(self):
        """.pdf后缀正确路由"""
        result = write_document(os.path.join(tempfile.gettempdir(), "test_write_12345.pdf"), content="test")
        assert result["code"] != "ERR_DOC_FORMAT_NOT_SUPPORTED"
        Path(os.path.join(tempfile.gettempdir(), "test_write_12345.pdf")).unlink(missing_ok=True)

    def test_pptx_routes_correctly(self):
        """.pptx后缀正确路由"""
        result = write_document(os.path.join(tempfile.gettempdir(), "test_write_12345.pptx"), slides=[{"title": "test"}])
        assert result["code"] != "ERR_DOC_FORMAT_NOT_SUPPORTED"
        Path(os.path.join(tempfile.gettempdir(), "test_write_12345.pptx")).unlink(missing_ok=True)


class TestDocumentToolsAllDefinition:
    """document_tools.py的__all__定义检查"""

    def test_all_exists(self):
        """document_tools.py必须有__all__定义"""
        assert hasattr(document_tools, "__all__"), "document_tools.py缺少__all__定义"

    def test_all_contains_public_functions(self):
        """__all__必须包含公开函数"""
        all_list = document_tools.__all__
        assert "read_document" in all_list
        assert "write_document" in all_list
        assert "convert_document" in all_list

    def test_all_not_contains_internal_functions(self):
        """__all__不应包含内部函数（下划线前缀）"""
        all_list = document_tools.__all__
        assert "_read_pdf" not in all_list, "_read_pdf是内部函数，不应在__all__中"
        assert "_read_docx" not in all_list
        assert "_write_docx" not in all_list
        assert "_check_module" not in all_list

    def test_all_count(self):
        """__all__应该正好包含3个公开函数"""
        assert len(document_tools.__all__) == 3, f"__all__应包含3个函数，实际: {document_tools.__all__}"


class TestDocumentRegister:
    """document_register.py注册检查"""

    def test_register_exactly_6_tools(self):
        """注册必须正好9个工具（含Database迁入）— 小沈 2026-05-18"""
        impls = document_register.TOOL_IMPLEMENTATIONS
        assert len(impls) == 9, f"应注册9个工具，实际: {len(impls)}"

    def test_register_tool_names(self):
        """注册工具名必须正确"""
        expected = {"read_document", "write_document", "convert_document", 
                    "analyze_data", "filter_data", "generate_chart",
                    "query_sql", "execute_sql", "get_db_schema"}
        actual = set(document_register.TOOL_IMPLEMENTATIONS.keys())
        assert actual == expected, f"工具名不匹配: {actual} vs {expected}"

    def test_register_all_definition(self):
        """document_register.py必须有__all__定义"""
        assert hasattr(document_register, "__all__")
        assert "_register_document_tools" in document_register.__all__


class TestDocumentInitPy:
    """document/__init__.py检查"""

    def test_init_all_count(self):
        """__init__.py的__all__应包含9个工具名（含Database迁入）"""
        assert len(doc_all) == 9, f"__init__.py __all__应包含9个，实际: {len(doc_all)}"

    def test_init_all_contains_correct_names(self):
        """__init__.py的__all__包含正确工具名"""
        expected = {"read_document", "write_document", "convert_document",
                    "analyze_data", "filter_data", "generate_chart",
                    "query_sql", "execute_sql", "get_db_schema"}
        assert set(doc_all) == expected


class TestDataAnalysisRegisterDeprecated:
    """data_analysis_register.py已删除（功能迁入document_register）— 小沈 2026-05-18"""

    def test_module_not_importable(self):
        """data_analysis_register模块已删除，不应可导入"""
        assert not hasattr(document, 'data_analysis_register'), "data_analysis_register应已删除"

    def test_functions_in_document_register(self):
        """原data_analysis功能已在document_register中"""
        impls = document_register.TOOL_IMPLEMENTATIONS
        assert "analyze_data" in impls
        assert "filter_data" in impls
        assert "generate_chart" in impls


class TestCategoryModules:
    """tools/__init__.py的CATEGORY_MODULES检查"""

    def test_document_data_analysis_removed(self):
        """CATEGORY_MODULES不应包含document_data_analysis条目"""
        assert "document_data_analysis" not in CATEGORY_MODULES, \
            "CATEGORY_MODULES应删除document_data_analysis条目"

    def test_document_exists(self):
        """CATEGORY_MODULES必须包含document条目"""
        assert "document" in CATEGORY_MODULES


class TestInternalFunctionsExist:
    """内部函数存在性检查"""

    def test_read_pdf_internal_exists(self):
        """_read_pdf内部函数必须存在"""
        assert callable(_read_pdf)

    def test_read_docx_internal_exists(self):
        """_read_docx内部函数必须存在"""
        assert callable(_read_docx)

    def test_read_xlsx_internal_exists(self):
        """_read_xlsx内部函数必须存在"""
        assert callable(_read_xlsx)

    def test_read_pptx_internal_exists(self):
        """_read_pptx内部函数必须存在"""
        assert callable(_read_pptx)

    def test_write_docx_internal_exists(self):
        """_write_docx内部函数必须存在"""
        assert callable(_write_docx)

    def test_write_xlsx_internal_exists(self):
        """_write_xlsx内部函数必须存在"""
        assert callable(_write_xlsx)

    def test_write_pdf_internal_exists(self):
        """_write_pdf内部函数必须存在"""
        assert callable(_write_pdf)

    def test_write_pptx_internal_exists(self):
        """_write_pptx内部函数必须存在"""
        assert callable(_write_pptx)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
