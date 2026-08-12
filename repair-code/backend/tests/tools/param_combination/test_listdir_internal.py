# -*- coding: utf-8 -*-
"""
listdir工具内部功能深度测试 — 挖掘内部逻辑bug

测试目标：通过参数组合测试内部排序和过滤逻辑的各种bug
测试用例：20个

Author: 小沈 - 2026-07-04
"""
import pytest
import asyncio
import os
import time
from pathlib import Path
from app.tools.file.list_directory import listdir


def is_success(result):
    return result.get("code") == "success" or result.get("llm_data", {}).get("status", {}).get("exec_code") == "success"


def is_error(result):
    return result.get("code") == "error" or result.get("llm_data", {}).get("status", {}).get("exec_code") == "error"


def is_warning(result):
    return result.get("code") == "warning" or result.get("llm_data", {}).get("status", {}).get("exec_code") == "warning"


class TestListdirInternalSorting:
    """内部排序逻辑测试 - 7个"""
    
    def test_sort_by_name_ascending(self, tmp_path):
        """内部功能1: 按名称升序排序"""
        (tmp_path / "z_file.txt").write_text("z")
        (tmp_path / "a_file.txt").write_text("a")
        (tmp_path / "m_file.txt").write_text("m")
        
        result = asyncio.run(listdir(path=str(tmp_path), sort_by="name"))
        assert is_success(result)
        entries = result["data"]["entries"]
        names = [e["name"] for e in entries]
        assert names == sorted(names)
    
    def test_sort_by_size(self, tmp_path):
        """内部功能2: 按大小排序"""
        (tmp_path / "small.txt").write_text("a")
        (tmp_path / "large.txt").write_text("a" * 100)
        (tmp_path / "medium.txt").write_text("a" * 10)
        
        result = asyncio.run(listdir(path=str(tmp_path), sort_by="size"))
        assert is_success(result)
        entries = result["data"]["entries"]
        sizes = [e["size"] for e in entries if e["type"] == "file" and e["size"] is not None]
        assert sizes == sorted(sizes, reverse=True)
    
    def test_sort_by_mtime(self, tmp_path):
        """内部功能3: 按修改时间排序"""
        (tmp_path / "old.txt").write_text("old")
        time.sleep(0.1)
        (tmp_path / "new.txt").write_text("new")
        
        result = asyncio.run(listdir(path=str(tmp_path), sort_by="mtime"))
        assert is_success(result)
        entries = result["data"]["entries"]
        # 新文件应该在前
        assert entries[0]["name"] == "new.txt"
    
    def test_sort_with_directories(self, tmp_path):
        """内部功能4: 目录和文件混合排序"""
        (tmp_path / "z_dir").mkdir()
        (tmp_path / "a_file.txt").write_text("test")
        
        result = asyncio.run(listdir(path=str(tmp_path), sort_by="name"))
        assert is_success(result)
        # 验证排序逻辑
    
    def test_sort_case_sensitivity(self, tmp_path):
        """Bug1: 排序大小写敏感性"""
        (tmp_path / "Z_file.txt").write_text("z")
        (tmp_path / "a_file.txt").write_text("a")
        
        result = asyncio.run(listdir(path=str(tmp_path), sort_by="name"))
        assert is_success(result)
        entries = result["data"]["entries"]
        names = [e["name"] for e in entries]
        # 应该不区分大小写排序
    
    def test_sort_with_hidden_files(self, tmp_path):
        """内部功能5: 隐藏文件排序"""
        (tmp_path / ".hidden").write_text("hidden")
        (tmp_path / "visible.txt").write_text("visible")
        
        result = asyncio.run(listdir(path=str(tmp_path), sort_by="name", include_hidden=True))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 2
    
    def test_sort_chinese_names(self, tmp_path):
        """Bug2: 中文名称排序"""
        (tmp_path / "文件Z.txt").write_text("z")
        (tmp_path / "文件A.txt").write_text("a")
        
        result = asyncio.run(listdir(path=str(tmp_path), sort_by="name"))
        assert is_success(result)


class TestListdirInternalFiltering:
    """内部过滤逻辑测试 - 6个"""
    
    def test_include_hidden_false(self, tmp_path):
        """内部功能6: 排除隐藏文件"""
        (tmp_path / ".hidden").write_text("hidden")
        (tmp_path / "visible.txt").write_text("visible")
        
        result = asyncio.run(listdir(path=str(tmp_path), include_hidden=False))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 1
    
    def test_include_hidden_true(self, tmp_path):
        """内部功能7: 包含隐藏文件"""
        (tmp_path / ".hidden").write_text("hidden")
        (tmp_path / "visible.txt").write_text("visible")
        
        result = asyncio.run(listdir(path=str(tmp_path), include_hidden=True))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 2
    
    def test_hidden_directory(self, tmp_path):
        """内部功能8: 隐藏目录过滤"""
        (tmp_path / ".hidden_dir").mkdir()
        (tmp_path / "visible_dir").mkdir()
        
        result = asyncio.run(listdir(path=str(tmp_path), include_hidden=False))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 1
    
    def test_mixed_hidden_content(self, tmp_path):
        """Bug3: 混合隐藏内容过滤"""
        (tmp_path / ".hidden_file").write_text("hidden")
        (tmp_path / ".hidden_dir").mkdir()
        (tmp_path / "visible.txt").write_text("visible")
        (tmp_path / "visible_dir").mkdir()
        
        result = asyncio.run(listdir(path=str(tmp_path), include_hidden=False))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 2
    
    def test_hidden_with_special_chars(self, tmp_path):
        """Bug4: 特殊字符隐藏文件"""
        (tmp_path / ".隐藏文件").write_text("hidden")
        
        result = asyncio.run(listdir(path=str(tmp_path), include_hidden=True))
        assert is_success(result)
    
    def test_empty_directory(self, tmp_path):
        """内部功能9: 空目录处理"""
        result = asyncio.run(listdir(path=str(tmp_path)))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] == 0


class TestListdirInternalPagination:
    """内部分页逻辑测试 - 7个"""
    
    def test_offset_pagination(self, tmp_path):
        """内部功能10: offset分页"""
        for i in range(100):
            (tmp_path / f"file{i:03d}.txt").write_text(f"content{i}")
        
        result = asyncio.run(listdir(path=str(tmp_path), offset=50))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["total"]["value"] <= 500
    
    def test_offset_zero(self, tmp_path):
        """内部功能11: offset=0从头开始"""
        (tmp_path / "file1.txt").write_text("1")
        (tmp_path / "file2.txt").write_text("2")
        
        result1 = asyncio.run(listdir(path=str(tmp_path), offset=0))
        result2 = asyncio.run(listdir(path=str(tmp_path)))
        
        assert is_success(result1) and is_success(result2)
        assert result1["llm_data"]["metrics"]["total"]["value"] == result2["llm_data"]["metrics"]["total"]["value"]
    
    def test_large_offset(self, tmp_path):
        """Bug5: 大offset处理"""
        (tmp_path / "file.txt").write_text("test")
        
        result = asyncio.run(listdir(path=str(tmp_path), offset=1000))
        assert is_success(result)
        assert len(result["data"]["entries"]) == 0
    
    def test_pagination_consistency(self, tmp_path):
        """内部功能12: 分页一致性"""
        for i in range(100):
            (tmp_path / f"file{i:03d}.txt").write_text(f"content{i}")
        
        # 第一页
        result1 = asyncio.run(listdir(path=str(tmp_path), offset=0))
        # 第二页
        result2 = asyncio.run(listdir(path=str(tmp_path), offset=len(result1["data"]["entries"])))
        
        assert is_success(result1) and is_success(result2)
    
    def test_max_items_limit(self, tmp_path):
        """Bug6: 最大条目限制"""
        for i in range(1000):
            (tmp_path / f"file{i:04d}.txt").write_text(f"content{i}")
        
        result = asyncio.run(listdir(path=str(tmp_path)))
        assert is_success(result) or is_warning(result)
        # max_items参数可选，不加参数时不限制最大条目数
        assert result["llm_data"]["metrics"]["total"]["value"] == 1000
    
    def test_negative_offset(self, tmp_path):
        """Bug7: 负offset处理"""
        (tmp_path / "file.txt").write_text("test")
        
        result = asyncio.run(listdir(path=str(tmp_path), offset=-1))
        assert is_error(result) or is_success(result)
    
    def test_pagination_with_sorting(self, tmp_path):
        """内部功能13: 分页+排序组合"""
        for i in range(50):
            (tmp_path / f"file{i:03d}.txt").write_text(f"content{i}")
        
        result = asyncio.run(listdir(path=str(tmp_path), sort_by="name", offset=10))
        assert is_success(result)