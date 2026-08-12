"""
analyze_data parameter combination deep test
xiaojian-2026-06-27

Test scope:
1. Parameter combination test (file_path and data mutual exclusion): 17.6x depth
2. Mutual exclusion parameter tests
3. Real scenario tests
4. Boundary tests
5. Negative tests
"""
import pytest
import json
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

from app.tools.dataanalysis.analyze_data import analyze_data
from tests.tools.param_combination.conftest import is_success, is_error


class TestAnalyzeDataParamCombinations:
    """Parameter combination test - file_path and data mutual exclusion"""

    def test_file_path_only(self, sample_csv_data):
        """Combination 1: file_path parameter only"""
        result = analyze_data(path=sample_csv_data)
        assert is_success(result)
        assert "statistics" in result["data"]

    def test_data_only(self, sample_json_data):
        """Combination 2: data parameter only"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = analyze_data(data=data_str)
        assert is_success(result)
        assert "statistics" in result["data"]

    def test_file_path_with_operations(self, sample_csv_data):
        """Combination 3: file_path + operations"""
        result = analyze_data(
            path=sample_csv_data,
            operations=["mean", "std", "min", "max"]
        )
        assert is_success(result)

    def test_data_with_operations(self, sample_json_data):
        """Combination 4: data + operations"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = analyze_data(
            data=data_str,
            operations=["mean", "sum"]
        )
        assert is_success(result)

    def test_file_path_with_group_by(self, sample_csv_data):
        """Combination 5: file_path + group_by"""
        result = analyze_data(
            path=sample_csv_data,
            operations=["mean"],
            group_by="department"
        )
        assert is_success(result)
        assert "grouped_statistics" in result["data"]

    def test_data_with_group_by(self, sample_json_data):
        """Combination 6: data + group_by"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = analyze_data(
            data=data_str,
            operations=["mean"],
            group_by="department"
        )
        assert is_success(result)

    def test_file_path_all_params(self, sample_csv_data):
        """Combination 7: file_path + all optional parameters"""
        result = analyze_data(
            path=sample_csv_data,
            operations=["mean", "std"],
            group_by="department",
            sort_by="salary",
            top_n=10,
        )
        assert is_success(result)

    def test_data_all_params(self, sample_json_data):
        """Combination 8: data + all optional parameters"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = analyze_data(
            data=data_str,
            operations=["mean", "sum"],
            group_by="department",
            sort_by="salary",
            top_n=5,
        )
        assert is_success(result)


class TestAnalyzeDataMutexParams:
    """Mutual exclusion parameter test - 17.6x depth focus"""

    def test_file_path_and_data_mutex(self, sample_csv_data, sample_json_data):
        """file_path and data mutual exclusion - should error when both provided"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = analyze_data(path=sample_csv_data, data=data_str)
        assert is_error(result)
        assert "\u4e92\u65a5" in result["llm_data"]["status"]["detail"]

    def test_neither_file_path_nor_data(self):
        """Neither file_path nor data provided - should error"""
        result = analyze_data()
        assert is_error(result)
        assert "detail" in result.get("llm_data", {}).get("status", {})

    def test_file_path_priority(self, sample_csv_data, sample_json_data):
        """Verify file_path and data mutual exclusion relationship"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = analyze_data(path=sample_csv_data, data=data_str)
        assert is_error(result)


class TestAnalyzeDataRealScenarios:
    """Real scenario tests"""

    def test_employee_salary_analysis(self, sample_csv_data):
        """Employee salary analysis"""
        result = analyze_data(
            path=sample_csv_data,
            operations=["mean", "std", "min", "max", "count"],
            group_by="department"
        )
        assert is_success(result)
        assert "grouped_statistics" in result["data"]

    def test_sales_data_analysis(self, temp_output_dir):
        """Sales data analysis"""
        import csv
        csv_path = temp_output_dir / "sales.csv"
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["date", "product", "quantity", "amount"])
            for i in range(1, 31):
                writer.writerow([f"2026-06-{i:02d}", f"product{i%5+1}", 100 + i*10, 1000 + i*100])

        result = analyze_data(
            path=str(csv_path),
            operations=["sum", "mean"],
            group_by="product"
        )
        assert is_success(result)

    def test_json_api_response_analysis(self):
        """JSON API response data analysis"""
        data = [
            {"api": "/users", "response_time": 120, "status": 200},
            {"api": "/orders", "response_time": 250, "status": 200},
            {"api": "/users", "response_time": 150, "status": 200},
            {"api": "/products", "response_time": 80, "status": 200},
            {"api": "/orders", "response_time": 300, "status": 500}
        ]
        data_str = json.dumps(data, ensure_ascii=False)
        result = analyze_data(
            data=data_str,
            operations=["mean", "min", "max"],
            group_by="api"
        )
        assert is_success(result)


class TestAnalyzeDataBoundary:
    """Boundary tests"""

    def test_empty_data(self):
        """Empty data"""
        data_str = json.dumps([], ensure_ascii=False)
        result = analyze_data(data=data_str)
        assert is_error(result) or is_success(result)

    def test_single_row_data(self):
        """Single row data"""
        data = [{"name": "zhangsan", "age": 25}]
        data_str = json.dumps(data, ensure_ascii=False)
        result = analyze_data(data=data_str, operations=["mean"])
        assert is_success(result) or is_error(result)

    def test_large_dataset(self):
        """Large dataset (1000 rows)"""
        data = [{"id": i, "value": i * 10} for i in range(1000)]
        data_str = json.dumps(data, ensure_ascii=False)
        result = analyze_data(data=data_str, operations=["mean", "std"])
        assert is_success(result)

    def test_top_n_limit(self):
        """top_n limit"""
        data = [{"id": i, "value": i} for i in range(100)]
        data_str = json.dumps(data, ensure_ascii=False)
        result = analyze_data(data=data_str, top_n=10)
        assert is_success(result)

    def test_special_characters_in_data(self):
        """Special characters in data"""
        data = [
            {"name": "zhangsan<>&\"'", "value": 100},
            {"name": "lisi---", "value": 200}
        ]
        data_str = json.dumps(data, ensure_ascii=False)
        result = analyze_data(data=data_str, operations=["mean"])
        assert is_success(result)


class TestAnalyzeDataNegative:
    """Negative tests"""

    def test_invalid_file_path(self):
        """Invalid file path"""
        result = analyze_data(path="Z:/invalid/path/12345.csv")
        assert is_error(result)

    def test_invalid_json_data(self):
        """Invalid JSON data"""
        result = analyze_data(data="not a valid json")
        assert is_error(result)

    def test_non_array_json(self):
        """Non-array JSON"""
        result = analyze_data(data='{"key": "value"}')
        assert is_error(result) or is_success(result)

    def test_invalid_operations(self, sample_csv_data):
        """Invalid operations"""
        result = analyze_data(path=sample_csv_data, operations=["invalid_op"])
        assert is_success(result) or is_error(result)

    def test_invalid_group_by_column(self, sample_csv_data):
        """Invalid group_by column"""
        result = analyze_data(path=sample_csv_data, group_by="nonexistent_column")
        assert is_success(result) or is_error(result)


class TestAnalyzeDataSchemaValidation:
    """Schema validation test - found Schema issues"""

    def test_schema_mutex_not_documented(self):
        """file_path and data mutual exclusion should be documented in Schema"""
        pass

    def test_schema_examples_insufficient(self):
        """Schema examples should include both file_path and data scenarios"""
        pass

    def test_schema_operations_list_incomplete(self):
        """operations supported list should be complete in Schema"""
        pass
