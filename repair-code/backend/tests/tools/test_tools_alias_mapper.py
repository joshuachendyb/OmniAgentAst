# -*- coding: utf-8 -*-
"""test"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.tools.tools_alias_mapper import normalize_params, get_param_aliases


class TestParamAliasMapper:
    """test"""
    def test_param_alias(self):
        # 路径参数统一为path后, 旧规范名file_path降级为别名 — 小欧 2026-07-11
        params = {"file_path": "D:/test.txt", "content": "hello"}
        normalized, has_mapping = normalize_params("writetext", params)
        
        assert has_mapping is True
        assert "path" in normalized
        assert normalized["path"] == "D:/test.txt"
        assert normalized["content"] == "hello"
        assert "file_path" not in normalized
    
    def test_write_text_file_filepath_alias(self):
        """write text file filepath alias — 小欧 2026-07-11 别名归一到path"""
        params = {"filepath": "D:/test.txt", "content": "hello"}
        normalized, has_mapping = normalize_params("writetext", params)
        
        assert has_mapping is True
        assert "path" in normalized
        assert normalized["path"] == "D:/test.txt"
    
    def test_write_text_file_correct_param(self):
        """listdir别名dir归一到path(注册名listdir) — 小欧 2026-07-11"""
        params = {"dir": "D:/project"}
        normalized, has_mapping = normalize_params("listdir", params)
        
        assert has_mapping is True
        assert "path" in normalized
        assert normalized["path"] == "D:/project"
    
    def test_move_file_aliases(self):
        """move file aliases — 路径参数统一为path/dest后,别名归一到path/dest — 小欧 2026-07-12"""
        params = {"src": "D:/a.txt", "dst": "E:/b.txt"}
        normalized, has_mapping = normalize_params("move", params)
        
        assert has_mapping is True
        assert normalized["path"] == "D:/a.txt"
        assert normalized["dest"] == "E:/b.txt"
    
    def test_unknown_tool(self):
        """unknown tool"""
        params = {}
        normalized, has_mapping = normalize_params("writetext", params)
        
        assert has_mapping is False
        assert normalized == {}
    
    def test_priority_canonical_over_alias(self):
        """read_pdf: 别名file_name→path(规范名现已统一为path)"""
        params = {"file_name": "D:/doc.pdf"}
        normalized, has_mapping = normalize_params("read_pdf", params)

        assert has_mapping is True
        assert "path" in normalized
        assert normalized["path"] == "D:/doc.pdf"
    
    # execute_code removed in refactoring -- 小欧 2026-07-05
    
    def test_registry_read_path_alias(self):
        """registry read path alias: registry_key→path(规范名key_path已统一为path)"""
        params = {"registry_key": "HKLM\\Software\\Test"}
        normalized, has_mapping = normalize_params("registry_read", params)

        assert has_mapping is True
        assert "path" in normalized
        assert normalized["path"] == "HKLM\\Software\\Test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])