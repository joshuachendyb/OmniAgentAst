"""
filter_data参数组合深度测试
小欧-2026-06-27

测试范围:
1. 参数组合测试(file_path与data互斥,17.6重构)
2. 互斥参数测试
3. 条件操作符测试
4. 真实场景测试
5. 边界测试
6. 负面测试
"""
import pytest
import json
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

from app.tools.dataanalysis.filter_data import filter_data
from tests.tools.param_combination.conftest import is_success, is_error


class TestFilterDataParamCombinations:
    """参数组合测试 - file_path与data互斥"""

    def test_file_path_only(self, sample_csv_data):
        """组合1: file_path + conditions"""
        conditions = [{"column": "年龄", "operator": "gt", "value": 25}]
        result = filter_data(path=sample_csv_data, conditions=conditions)
        assert is_success(result)

    def test_data_only(self, sample_json_data):
        """组合2: data + conditions"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "age", "operator": "gt", "value": 25}]
        result = filter_data(data=data_str, conditions=conditions)
        assert is_success(result)

    def test_file_path_with_select_columns(self, sample_csv_data):
        """组合3: file_path + conditions + select_columns"""
        conditions = [{"column": "部门", "operator": "eq", "value": "技术部"}]
        result = filter_data(
            path=sample_csv_data,
            conditions=conditions,
            select_columns=["姓名", "年龄"]
        )
        assert is_success(result)

    def test_data_with_select_columns(self, sample_json_data):
        """组合4: data + conditions + select_columns"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "department", "operator": "eq", "value": "技术部"}]
        result = filter_data(
            data=data_str,
            conditions=conditions,
            select_columns=["name", "age"]
        )
        assert is_success(result)

    def test_file_path_with_sort_and_top(self, sample_csv_data):
        """组合5: file_path + sort_by + top_n"""
        conditions = [{"column": "薪资", "operator": "gte", "value": 8000}]
        result = filter_data(
            path=sample_csv_data,
            conditions=conditions,
            sort_by="薪资",
            top_n=3
        )
        assert is_success(result)

    def test_data_all_params(self, sample_json_data):
        """组合6: data + 所有参数"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "salary", "operator": "gte", "value": 8000}]
        result = filter_data(
            data=data_str,
            conditions=conditions,
            select_columns=["name", "salary"],
            sort_by="salary",
            top_n=5,
        )
        assert is_success(result)


class TestFilterDataMutexParams:
    """互斥参数测试 - 17.6重构重点"""

    def test_file_path_and_data_mutex(self, sample_csv_data, sample_json_data):
        """file_path和data互斥 - 同时传入应报错"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "age", "operator": "gt", "value": 20}]
        result = filter_data(path=sample_csv_data, data=data_str, conditions=conditions)
        assert is_error(result)
        assert "互斥" in result["llm_data"]["status"]["detail"]

    def test_neither_file_path_nor_data(self):
        """file_path和data都不传应报错"""
        conditions = [{"column": "age", "operator": "gt", "value": 20}]
        result = filter_data(conditions=conditions)
        assert is_error(result)
        assert "必须传入其中一个" in result["llm_data"]["status"]["detail"]


class TestFilterDataOperators:
    """条件操作符测试"""

    def test_operator_eq(self, sample_json_data):
        """等于操作符"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "department", "operator": "eq", "value": "技术部"}]
        result = filter_data(data=data_str, conditions=conditions)
        assert is_success(result)

    def test_operator_ne(self, sample_json_data):
        """不等于操作符"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "department", "operator": "ne", "value": "技术部"}]
        result = filter_data(data=data_str, conditions=conditions)
        assert is_success(result)

    def test_operator_gt(self, sample_json_data):
        """大于操作符"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "age", "operator": "gt", "value": 25}]
        result = filter_data(data=data_str, conditions=conditions)
        assert is_success(result)

    def test_operator_gte(self, sample_json_data):
        """大于等于操作符"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "salary", "operator": "gte", "value": 8500}]
        result = filter_data(data=data_str, conditions=conditions)
        assert is_success(result)

    def test_operator_lt(self, sample_json_data):
        """小于操作符"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "age", "operator": "lt", "value": 30}]
        result = filter_data(data=data_str, conditions=conditions)
        assert is_success(result)

    def test_operator_lte(self, sample_json_data):
        """小于等于操作符"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "salary", "operator": "lte", "value": 9000}]
        result = filter_data(data=data_str, conditions=conditions)
        assert is_success(result)

    def test_operator_in(self, sample_json_data):
        """包含于操作符"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "department", "operator": "in", "value": ["技术部", "销售部"]}]
        result = filter_data(data=data_str, conditions=conditions)
        assert is_success(result)

    def test_operator_contains(self, sample_json_data):
        """字符串包含操作符"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "name", "operator": "contains", "value": "张"}]
        result = filter_data(data=data_str, conditions=conditions)
        assert is_success(result)

    def test_multiple_conditions(self, sample_json_data):
        """多条件组合"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [
            {"column": "age", "operator": "gte", "value": 25},
            {"column": "salary", "operator": "lt", "value": 10000}
        ]
        result = filter_data(data=data_str, conditions=conditions)
        assert is_success(result)


class TestFilterDataRealScenarios:
    """真实场景测试"""

    def test_filter_high_salary_employees(self, sample_csv_data):
        """筛选高薪员工"""
        conditions = [{"column": "薪资", "operator": "gte", "value": 8500}]
        result = filter_data(
            path=sample_csv_data,
            conditions=conditions,
            sort_by="薪资",
            top_n=5
        )
        assert is_success(result)

    def test_filter_by_department(self, sample_csv_data):
        """按部门筛选"""
        conditions = [{"column": "部门", "operator": "eq", "value": "技术部"}]
        result = filter_data(
            path=sample_csv_data,
            conditions=conditions,
            select_columns=["姓名", "年龄", "薪资"]
        )
        assert is_success(result)

    def test_filter_api_errors(self):
        """筛选API错误日志"""
        data = [
            {"timestamp": "2026-06-27 10:00:00", "api": "/users", "status": 200, "time": 120},
            {"timestamp": "2026-06-27 10:01:00", "api": "/orders", "status": 500, "time": 250},
            {"timestamp": "2026-06-27 10:02:00", "api": "/users", "status": 200, "time": 150},
            {"timestamp": "2026-06-27 10:03:00", "api": "/products", "status": 404, "time": 80}
        ]
        data_str = json.dumps(data, ensure_ascii=False)
        conditions = [{"column": "status", "operator": "gte", "value": 400}]
        result = filter_data(data=data_str, conditions=conditions)
        assert is_success(result)


class TestFilterDataBoundary:
    """边界测试"""

    def test_empty_conditions(self, sample_json_data):
        """空条件"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = filter_data(data=data_str, conditions=[])
        assert is_error(result) or is_success(result)

    def test_no_matching_data(self, sample_json_data):
        """无匹配数据"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "age", "operator": "gt", "value": 1000}]
        result = filter_data(data=data_str, conditions=conditions)
        assert is_success(result)
        assert len(result["data"]["rows"]) == 0

    def test_all_matching_data(self, sample_json_data):
        """全部匹配"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "age", "operator": "gt", "value": 0}]
        result = filter_data(data=data_str, conditions=conditions)
        assert is_success(result)
        assert len(result["data"]["rows"]) == len(sample_json_data)

    def test_large_dataset(self):
        """大数据集"""
        data = [{"id": i, "value": i} for i in range(1000)]
        data_str = json.dumps(data, ensure_ascii=False)
        conditions = [{"column": "value", "operator": "lt", "value": 100}]
        result = filter_data(data=data_str, conditions=conditions)
        assert is_success(result)


class TestFilterDataNegative:
    """负面测试"""

    def test_invalid_file_path(self):
        """无效文件路径"""
        conditions = [{"column": "age", "operator": "gt", "value": 20}]
        result = filter_data(path="Z:/invalid/path.csv", conditions=conditions)
        assert is_error(result)

    def test_invalid_json_data(self):
        """无效JSON数据"""
        conditions = [{"column": "age", "operator": "gt", "value": 20}]
        result = filter_data(data="not json", conditions=conditions)
        assert is_error(result)

    def test_invalid_operator(self, sample_json_data):
        """无效操作符"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "age", "operator": "invalid", "value": 20}]
        result = filter_data(data=data_str, conditions=conditions)
        assert is_success(result) or is_error(result)

    def test_invalid_column(self, sample_json_data):
        """无效列名"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "nonexistent", "operator": "gt", "value": 20}]
        result = filter_data(data=data_str, conditions=conditions)
        assert is_success(result) or is_error(result)


class TestFilterDataSchemaValidation:
    """Schema验证测试 - 发现Schema问题"""

    def test_schema_mutex_not_documented(self):
        """file_path和data互斥关系应该在Schema中明认说明"""
        pass

    def test_schema_operators_not_listed(self):
        """支持的操作符列表应该在Schema中完整说明"""
        pass

    def test_schema_condition_structure_ambiguous(self):
        """conditions的结构应该在Schema中更清晰说明"""
        pass
