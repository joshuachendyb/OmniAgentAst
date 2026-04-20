"""
FileSessionStats 测试 - 小沈

测试file意图统计数据的核心功能。

Author: 小沈 - 2026-03-21
"""

import pytest

from app.services.intents.definitions.file.file_stats import FileSessionStats


class TestFileSessionStatsCreation:
    """测试FileSessionStats创建"""
    
    def test_create_default(self):
        """测试默认创建"""
        stats = FileSessionStats()
        
        assert stats.rolled_back_count == 0
        assert stats.report_generated == False
        assert stats.report_path is None
        assert stats.report_type is None
    
    def test_create_with_values(self):
        """测试带值创建"""
        stats = FileSessionStats(
            rolled_back_count=2,
            report_generated=True,
            report_path="/path/to/report.html",
            report_type="html"
        )
        
        assert stats.rolled_back_count == 2
        assert stats.report_generated == True
        assert stats.report_path == "/path/to/report.html"
        assert stats.report_type == "html"


class TestFileSessionStatsFields:
    """测试FileSessionStats字段"""
    
    def test_has_rolled_back_count_field(self):
        """测试有rolled_back_count字段"""
        stats = FileSessionStats()
        assert hasattr(stats, 'rolled_back_count')
        assert isinstance(stats.rolled_back_count, int)
    
    def test_has_report_generated_field(self):
        """测试有report_generated字段"""
        stats = FileSessionStats()
        assert hasattr(stats, 'report_generated')
        assert isinstance(stats.report_generated, bool)
    
    def test_has_report_path_field(self):
        """测试有report_path字段"""
        stats = FileSessionStats()
        assert hasattr(stats, 'report_path')
        assert stats.report_path is None
    
    def test_has_report_type_field(self):
        """测试有report_type字段"""
        stats = FileSessionStats()
        assert hasattr(stats, 'report_type')
        assert stats.report_type is None


class TestFileSessionStatsValues:
    """测试FileSessionStats值"""
    
    def test_rolled_back_count_default(self):
        """测试rolled_back_count默认值"""
        stats = FileSessionStats()
        assert stats.rolled_back_count == 0
    
    def test_rolled_back_count_positive(self):
        """测试rolled_back_count正数"""
        stats = FileSessionStats(rolled_back_count=5)
        assert stats.rolled_back_count == 5
    
    def test_report_generated_default(self):
        """测试report_generated默认值"""
        stats = FileSessionStats()
        assert stats.report_generated == False
    
    def test_report_generated_true(self):
        """测试report_generated为True"""
        stats = FileSessionStats(report_generated=True)
        assert stats.report_generated == True
    
    def test_report_path_default(self):
        """测试report_path默认值"""
        stats = FileSessionStats()
        assert stats.report_path is None
    
    def test_report_path_set(self):
        """测试report_path设置值"""
        stats = FileSessionStats(report_path="/path/to/report.html")
        assert stats.report_path == "/path/to/report.html"
    
    def test_report_type_default(self):
        """测试report_type默认值"""
        stats = FileSessionStats()
        assert stats.report_type is None
    
    def test_report_type_set(self):
        """测试report_type设置值"""
        stats = FileSessionStats(report_type="html")
        assert stats.report_type == "html"


class TestFileSessionStatsSerialization:
    """测试FileSessionStats序列化"""
    
    def test_to_dict(self):
        """测试转换为字典"""
        stats = FileSessionStats(
            rolled_back_count=1,
            report_generated=True,
            report_path="/report.html",
            report_type="html"
        )
        
        data = stats.model_dump()
        
        assert isinstance(data, dict)
        assert data["rolled_back_count"] == 1
        assert data["report_generated"] == True
        assert data["report_path"] == "/report.html"
        assert data["report_type"] == "html"
    
    def test_to_json(self):
        """测试转换为JSON"""
        import json
        stats = FileSessionStats(
            rolled_back_count=1,
            report_generated=True
        )
        
        json_str = stats.model_dump_json()
        data = json.loads(json_str)
        
        assert data["rolled_back_count"] == 1
        assert data["report_generated"] == True
    
    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "rolled_back_count": 3,
            "report_generated": True,
            "report_path": "/report.html",
            "report_type": "json"
        }
        
        stats = FileSessionStats(**data)
        
        assert stats.rolled_back_count == 3
        assert stats.report_generated == True
        assert stats.report_path == "/report.html"
        assert stats.report_type == "json"


class TestFileSessionStatsReportTypes:
    """测试FileSessionStats报告类型"""
    
    def test_text_report_type(self):
        """测试text报告类型"""
        stats = FileSessionStats(report_type="text")
        assert stats.report_type == "text"
    
    def test_json_report_type(self):
        """测试json报告类型"""
        stats = FileSessionStats(report_type="json")
        assert stats.report_type == "json"
    
    def test_html_report_type(self):
        """测试html报告类型"""
        stats = FileSessionStats(report_type="html")
        assert stats.report_type == "html"
    
    def test_mermaid_report_type(self):
        """测试mermaid报告类型"""
        stats = FileSessionStats(report_type="mermaid")
        assert stats.report_type == "mermaid"
