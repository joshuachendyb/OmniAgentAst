# -*- coding: utf-8 -*-
"""测试 table_helper.py 公用表格函数 — 小欧 2026-07-08"""

import pytest
from app.utils.table_helper import dict_table_to_rows, normalize_table_data


class TestDictTableToRows:
    """测试 dict_table_to_rows — 小欧 2026-07-08"""

    def test_normal(self):
        result = dict_table_to_rows({"headers": ["Name", "Age"], "rows": [["Alice", "30"], ["Bob", "25"]]})
        assert result == [["Name", "Age"], ["Alice", "30"], ["Bob", "25"]]

    def test_no_headers(self):
        result = dict_table_to_rows({"rows": [["A", "1"], ["B", "2"]]})
        assert result == [["A", "1"], ["B", "2"]]

    def test_no_rows(self):
        result = dict_table_to_rows({"headers": ["X", "Y"]})
        assert result == [["X", "Y"]]

    def test_empty_headers(self):
        result = dict_table_to_rows({"headers": [], "rows": [["a"]]})
        assert result == [["a"]]

    def test_empty_rows(self):
        result = dict_table_to_rows({"headers": ["A"], "rows": []})
        assert result == [["A"]]

    def test_single_row_not_list(self):
        result = dict_table_to_rows({"headers": ["Item"], "rows": ["single"]})
        assert result == [["Item"], ["single"]]

    def test_none_cells(self):
        result = dict_table_to_rows({"headers": [None, "B"], "rows": [[None, "2"]]})
        assert result == [["", "B"], ["", "2"]]

    def test_empty_dict(self):
        result = dict_table_to_rows({})
        assert result == []


class TestNormalizeTableData:
    """测试 normalize_table_data — 小欧 2026-07-08"""

    def test_list_of_list_standard(self):
        result = normalize_table_data([["Name", "Age"], ["Alice", "30"]])
        assert result == [["Name", "Age"], ["Alice", "30"]]

    def test_list_of_list_with_mixed_types(self):
        result = normalize_table_data([["Name", "Count"], ["A", 1], ["B", None]])
        assert result == [["Name", "Count"], ["A", "1"], ["B", ""]]

    def test_dict_format(self):
        result = normalize_table_data({"headers": ["X", "Y"], "rows": [["1", "2"], ["3", "4"]]})
        assert result == [["X", "Y"], ["1", "2"], ["3", "4"]]

    def test_list_of_dict(self):
        data = [
            {"headers": ["A", "B"], "rows": [["1", "2"]]},
            {"headers": ["A", "B"], "rows": [["3", "4"]]},
        ]
        result = normalize_table_data(data)
        assert result == [["A", "B"], ["1", "2"], ["A", "B"], ["3", "4"]]

    def test_none(self):
        assert normalize_table_data(None) is None

    def test_empty_list(self):
        assert normalize_table_data([]) is None

    def test_empty_dict(self):
        assert normalize_table_data({}) is None

    def test_single_row_list(self):
        result = normalize_table_data([["only"]])
        assert result == [["only"]]

    def test_integer_cells(self):
        result = normalize_table_data([[1, 2], [3, 4]])
        assert result == [["1", "2"], ["3", "4"]]

    def test_mixed_cells_with_none(self):
        result = normalize_table_data([["A", None], [None, "B"]])
        assert result == [["A", ""], ["", "B"]]


class TestNormalizeIntegrationDocxPdf:
    """集成测试：模拟 write_docx/write_pdf 的 table_data 处理路径 — 小欧 2026-07-08

    三个工具统一走 normalize_table_data → list[list[str]] → 写入
    """

    def test_docx_like_table_data_list(self):
        table_data = [["H1", "H2"], ["r1c1", "r1c2"]]
        normalized = normalize_table_data(table_data)
        assert normalized is not None
        assert len(normalized) == 2
        assert normalized[0] == ["H1", "H2"]

    def test_docx_like_table_data_dict(self):
        table_data = {"headers": ["Name"], "rows": [["Alice"]]}
        normalized = normalize_table_data(table_data)
        assert normalized is not None
        assert normalized == [["Name"], ["Alice"]]

    def test_docx_like_table_data_none(self):
        assert normalize_table_data(None) is None

    def test_docx_like_table_data_empty(self):
        assert normalize_table_data([]) is None
