# -*- coding: utf-8 -*-
"""
数据分析工具测试模块

【创建时间】2026-05-02 小沈
【设计依据】按文档第8.2节 Tool 77-79 定义

测试覆盖：
- read_csv_dataframe: pandas读取CSV
- generate_chart: matplotlib生成图表
- analyze_data: 数据统计分析

Author: 小沈 - 2026-05-02
"""

import os
import sys
import json
import tempfile
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.tools.document.data_analysis_tools import (
    read_csv_dataframe,
    generate_chart,
    analyze_data,
)


class TestReadCsvDataframe:
    """read_csv_dataframe 工具测试 - 小沈 2026-05-02"""

    def _create_csv(self, content: str, suffix=".csv") -> str:
        fd, path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def test_file_not_exists(self):
        result = read_csv_dataframe(file_path="D:/nonexistent/file.csv")
        assert result["code"] in ("ERR_READ_CSV_DATAFRAME", "ERR_NO_PANDAS")

    def test_read_basic_csv(self):
        try:
            import pandas
        except ImportError:
            pytest.skip("pandas not installed")

        csv_content = "name,age,score\nAlice,25,90\nBob,30,85\nCharlie,28,95"
        path = self._create_csv(csv_content)
        try:
            result = read_csv_dataframe(file_path=path)
            assert result["code"] == "SUCCESS"
            assert result["data"]["row_count"] == 3
            assert "name" in result["data"]["columns"]
            assert "age" in result["data"]["columns"]
        finally:
            os.unlink(path)

    def test_read_csv_with_max_rows(self):
        try:
            import pandas
        except ImportError:
            pytest.skip("pandas not installed")

        lines = ["name,value\n"] + [f"item_{i},{i}\n" for i in range(100)]
        csv_content = "".join(lines)
        path = self._create_csv(csv_content)
        try:
            result = read_csv_dataframe(file_path=path, max_rows=10)
            assert result["code"] == "SUCCESS"
            assert result["data"]["row_count"] == 10
        finally:
            os.unlink(path)

    def test_read_csv_no_header(self):
        try:
            import pandas
        except ImportError:
            pytest.skip("pandas not installed")

        csv_content = "Alice,25,90\nBob,30,85"
        path = self._create_csv(csv_content)
        try:
            result = read_csv_dataframe(file_path=path, has_header=False)
            assert result["code"] == "SUCCESS"
            assert result["data"]["row_count"] == 2
        finally:
            os.unlink(path)

    def test_read_csv_semicolon_delimiter(self):
        try:
            import pandas
        except ImportError:
            pytest.skip("pandas not installed")

        csv_content = "name;age\nAlice;25\nBob;30"
        path = self._create_csv(csv_content)
        try:
            result = read_csv_dataframe(file_path=path, delimiter=";")
            assert result["code"] == "SUCCESS"
            assert result["data"]["row_count"] == 2
        finally:
            os.unlink(path)


class TestGenerateChart:
    """generate_chart 工具测试 - 小沈 2026-05-02"""

    def test_no_matplotlib(self):
        try:
            import matplotlib
            pytest.skip("matplotlib installed, cannot test missing case")
        except ImportError:
            result = generate_chart(data={"labels": ["A"], "values": [1]})
            assert result["code"] == "ERR_NO_MATPLOTLIB"

    def test_generate_bar_chart(self):
        try:
            import matplotlib
        except ImportError:
            pytest.skip("matplotlib not installed")

        fd, path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            result = generate_chart(
                data={"labels": ["A", "B", "C"], "values": [10, 20, 30]},
                chart_type="bar",
                title="测试柱状图",
                output_path=path
            )
            assert result["code"] == "SUCCESS"
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_generate_line_chart(self):
        try:
            import matplotlib
        except ImportError:
            pytest.skip("matplotlib not installed")

        fd, path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            result = generate_chart(
                data={"labels": ["1月", "2月", "3月"], "values": [100, 200, 150]},
                chart_type="line",
                title="测试折线图",
                output_path=path
            )
            assert result["code"] == "SUCCESS"
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_generate_pie_chart(self):
        try:
            import matplotlib
        except ImportError:
            pytest.skip("matplotlib not installed")

        fd, path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            result = generate_chart(
                data={"labels": ["A", "B"], "values": [60, 40]},
                chart_type="pie",
                title="测试饼图",
                output_path=path
            )
            assert result["code"] == "SUCCESS"
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_invalid_data_format(self):
        try:
            import matplotlib
        except ImportError:
            pytest.skip("matplotlib not installed")

        result = generate_chart(data={"wrong_key": []})
        assert result["code"] == "ERR_GENERATE_CHART"

    def test_auto_output_path(self):
        try:
            import matplotlib
        except ImportError:
            pytest.skip("matplotlib not installed")

        result = generate_chart(
            data={"labels": ["A", "B"], "values": [1, 2]},
            chart_type="bar"
        )
        assert result["code"] == "SUCCESS"
        assert result["data"].endswith(".png")


class TestAnalyzeData:
    """analyze_data 工具测试 - 小沈 2026-05-02"""

    def test_no_pandas(self):
        try:
            import pandas
            pytest.skip("pandas installed, cannot test missing case")
        except ImportError:
            result = analyze_data(data=[{"name": "A", "value": 10}])
            assert result["code"] == "ERR_NO_PANDAS"

    def test_analyze_list_data(self):
        try:
            import pandas
        except ImportError:
            pytest.skip("pandas not installed")

        data = [
            {"name": "A", "value": 10},
            {"name": "B", "value": 20},
            {"name": "C", "value": 30},
        ]
        result = analyze_data(data=data)
        assert result["code"] == "SUCCESS"
        assert "statistics" in result["data"]

    def test_analyze_with_specific_operations(self):
        try:
            import pandas
        except ImportError:
            pytest.skip("pandas not installed")

        data = [
            {"name": "A", "value": 10},
            {"name": "B", "value": 20},
        ]
        result = analyze_data(data=data, operations=["mean", "sum"])
        assert result["code"] == "SUCCESS"
        stats = result["data"]["statistics"]
        assert "mean" in stats
        assert "sum" in stats

    def test_analyze_csv_file(self):
        try:
            import pandas
        except ImportError:
            pytest.skip("pandas not installed")

        fd, path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("name,value\nA,10\nB,20\nC,30\n")
        try:
            result = analyze_data(data=path)
            assert result["code"] == "SUCCESS"
            assert result["data"]["row_count"] == 3
        finally:
            os.unlink(path)

    def test_analyze_nonexistent_file(self):
        try:
            import pandas
        except ImportError:
            pytest.skip("pandas not installed")

        result = analyze_data(data="D:/nonexistent/file.csv")
        assert result["code"] == "ERR_ANALYZE_DATA"

    def test_analyze_with_group_by(self):
        try:
            import pandas
        except ImportError:
            pytest.skip("pandas not installed")

        data = [
            {"category": "X", "value": 10},
            {"category": "X", "value": 20},
            {"category": "Y", "value": 30},
        ]
        result = analyze_data(data=data, group_by="category")
        assert result["code"] == "SUCCESS"
        assert "grouped_statistics" in result["data"]

    def test_analyze_no_numeric_columns(self):
        try:
            import pandas
        except ImportError:
            pytest.skip("pandas not installed")

        data = [
            {"name": "Alice", "city": "Beijing"},
            {"name": "Bob", "city": "Shanghai"},
        ]
        result = analyze_data(data=data)
        assert result["code"] == "SUCCESS"
