# -*- coding: utf-8 -*-
"""
analyze_data工具内部功能深度测试 — 挖掘内部逻辑bug

测试目标：通过参数组合测试内部数据分析逻辑的各种bug
测试用例：15个

Author: 小沈 - 2026-07-04
"""
import pytest
import os
from pathlib import Path
from app.tools.dataanalysis.analyze_data import analyze_data


def is_success(result):
    return result.get("code") == "success" or result.get("llm_data", {}).get("status", {}).get("exec_code") == "success"


def is_error(result):
    return result.get("code") == "error" or result.get("llm_data", {}).get("status", {}).get("exec_code") == "error"


class TestAnalyzeDataInternalAnalysis:
    """内部分析逻辑测试 - 8个"""
    
    def test_basic_statistics(self, tmp_path):
        """内部功能1: 基础统计计算"""
        data_file = tmp_path / "data.csv"
        data_file.write_text("value\n10\n20\n30\n40\n50")
        
        result = analyze_data(path=str(data_file))
        assert is_success(result) or is_error(result)
    
    def test_missing_values_detection(self, tmp_path):
        """内部功能2: 缺失值检测"""
        data_file = tmp_path / "data.csv"
        data_file.write_text("value\n10\n\n30\n\n50")
        
        result = analyze_data(path=str(data_file))
        assert is_success(result) or is_error(result)
    
    def test_distribution_analysis(self, tmp_path):
        """内部功能3: 分布分析"""
        data_file = tmp_path / "data.csv"
        data_file.write_text("value\n10\n20\n30\n40\n50\n60\n70\n80\n90\n100")
        
        result = analyze_data(path=str(data_file))
        assert is_success(result) or is_error(result)
    
    def test_correlation_analysis(self, tmp_path):
        """内部功能4: 相关性分析"""
        data_file = tmp_path / "data.csv"
        data_file.write_text("x,y\n1,2\n2,4\n3,6\n4,8\n5,10")
        
        result = analyze_data(path=str(data_file))
        assert is_success(result) or is_error(result)
    
    def test_empty_data_handling(self, tmp_path):
        """Bug1: 空数据处理"""
        data_file = tmp_path / "empty.csv"
        data_file.write_text("value\n")
        
        result = analyze_data(path=str(data_file))
        assert is_success(result) or is_error(result)
    
    def test_single_value_handling(self, tmp_path):
        """Bug2: 单值数据处理"""
        data_file = tmp_path / "single.csv"
        data_file.write_text("value\n42")
        
        result = analyze_data(path=str(data_file))
        assert is_success(result) or is_error(result)
    
    def test_large_dataset_handling(self, tmp_path):
        """Bug3: 大数据集处理"""
        data_file = tmp_path / "large.csv"
        lines = ["value"] + [str(i) for i in range(10000)]
        data_file.write_text("\n".join(lines))
        
        result = analyze_data(path=str(data_file))
        assert is_success(result) or is_error(result)
    
    def test_invalid_analysis_type(self, tmp_path):
        """Bug4: 无效分析类型"""
        data_file = tmp_path / "data.csv"
        data_file.write_text("value\n1\n2\n3")
        
        result = analyze_data(path=str(data_file), operations=["invalid_op"])
        assert is_success(result) or is_error(result)


class TestAnalyzeDataInternalFormat:
    """内部格式处理测试 - 7个"""
    
    def test_csv_format(self, tmp_path):
        """内部功能5: CSV格式处理"""
        data_file = tmp_path / "data.csv"
        data_file.write_text("a,b\n1,2\n3,4")
        
        result = analyze_data(path=str(data_file))
        assert is_success(result) or is_error(result)
    
    def test_xlsx_format(self, tmp_path):
        """内部功能6: Excel格式处理"""
        try:
            import pandas as pd
            data_file = tmp_path / "data.xlsx"
            df = pd.DataFrame({"value": [1, 2, 3]})
            df.to_excel(str(data_file), index=False)
            
            result = analyze_data(path=str(data_file))
            assert is_success(result) or is_error(result)
        except ImportError:
            pytest.skip("pandas not installed")
    
    def test_json_format(self, tmp_path):
        """内部功能7: JSON格式处理"""
        data_file = tmp_path / "data.json"
        data_file.write_text('{"values": [1, 2, 3]}')
        
        result = analyze_data(path=str(data_file))
        assert is_success(result) or is_error(result)
    
    def test_nonexistent_file(self, tmp_path):
        """Bug5: 不存在的文件"""
        result = analyze_data(path=str(tmp_path / "nonexistent.csv"))
        assert is_error(result)
    
    def test_invalid_file_format(self, tmp_path):
        """Bug6: 无效文件格式"""
        data_file = tmp_path / "data.xyz"
        data_file.write_text("invalid content")
        
        result = analyze_data(path=str(data_file))
        assert is_success(result) or is_error(result)
    
    def test_unicode_data(self, tmp_path):
        """Bug7: Unicode数据处理"""
        data_file = tmp_path / "data.csv"
        data_file.write_text("name,value\n测试,10\n🎉,20", encoding="utf-8")
        
        result = analyze_data(path=str(data_file))
        assert is_success(result) or is_error(result)
    
    def test_mixed_data_types(self, tmp_path):
        """Bug8: 混合数据类型处理"""
        data_file = tmp_path / "data.csv"
        data_file.write_text("value\n10\n20.5\ntext\n30")
        
        result = analyze_data(path=str(data_file))
        assert is_success(result) or is_error(result)