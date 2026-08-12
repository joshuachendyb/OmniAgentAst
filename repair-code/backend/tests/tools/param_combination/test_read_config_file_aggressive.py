# -*- coding: utf-8 -*-
"""
read_config_file 激进测试(迁移版) - 目标:发现代码bug
小欧 2026-06-24 — 小欧 2026-07-12 迁移: read_config_file 已在 2026-06-24 重构中删除,
文本读取由 readtext 覆盖(见 app/tools/file/file_register.py:9),故本文件改用 readtext 验证
"配置文件可被正确读取为文本"这一可验证意图(格式解析能力不再由独立工具提供)。
"""
import asyncio
import json
import os
import tempfile
import pytest
from app.tools.file.read_text_file import readtext
from app.tools.tool_response import is_success, is_error


def _run(coro):
    return asyncio.run(coro)


class TestReadConfigFileBugs:
    """激进测试 - 专门找Bug(基于 readtext 的等价验证)"""

    def test_json_truncated_content(self):
        """截断的JSON文件: readtext 应成功读取原文(不做JSON解析)"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            f.write('{"key": "value", "nested": {"a": 1, "b": ')
            tmp = f.name
        try:
            result = _run(readtext(path=tmp))
            assert is_success(result), f"截断JSON应可读原文: {result}"
            assert "value" in result["data"]["content"]
        finally:
            os.unlink(tmp)

    def test_json_empty_object(self):
        """空JSON对象: 读取原文成功"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            f.write('{}')
            tmp = f.name
        try:
            result = _run(readtext(path=tmp))
            assert is_success(result)
            assert "{}" in result["data"]["content"]
        finally:
            os.unlink(tmp)

    def test_json_empty_array(self):
        """空JSON数组: 读取原文成功"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            f.write('[]')
            tmp = f.name
        try:
            result = _run(readtext(path=tmp))
            assert is_success(result)
            assert "[]" in result["data"]["content"]
        finally:
            os.unlink(tmp)

    def test_json_unicode_content(self):
        """JSON包含Unicode字符: 正确读取"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump({"中文": "测试", "emoji": "😀🎉", "arabic": "مرحبا"}, f, ensure_ascii=False)
            tmp = f.name
        try:
            result = _run(readtext(path=tmp))
            assert is_success(result)
            content = result["data"]["content"]
            assert "中文" in content
            assert "😀🎉" in content
        finally:
            os.unlink(tmp)

    def test_json_deeply_nested(self):
        """深层嵌套JSON: 读取原文不崩溃"""
        nested = {"level": 0}
        current = nested
        for i in range(1, 50):
            current["child"] = {"level": i}
            current = current["child"]
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(nested, f)
            tmp = f.name
        try:
            result = _run(readtext(path=tmp))
            assert is_success(result)
        finally:
            os.unlink(tmp)

    def test_json_duplicate_keys(self):
        """JSON重复键: 读取原文成功(Python json.loads 取最后一个,但 readtext 只返回原文)"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            f.write('{"key": "first", "key": "second"}')
            tmp = f.name
        try:
            result = _run(readtext(path=tmp))
            assert is_success(result)
            assert '"key"' in result["data"]["content"]
        finally:
            os.unlink(tmp)

    def test_json_bom_utf8(self):
        """UTF-8 BOM头的JSON文件: 编码检测应剥离BOM并读取"""
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.json', delete=False) as f:
            f.write(b'\xef\xbb\xbf{"key": "value"}')
            tmp = f.name
        try:
            result = _run(readtext(path=tmp))
            assert is_success(result), f"BOM JSON应可读: {result}"
            assert "value" in result["data"]["content"]
        finally:
            os.unlink(tmp)

    def test_yaml_simple(self):
        """简单YAML: 读取原文成功"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write("name: test\nvalue: 123\nlist:\n  - item1\n  - item2")
            tmp = f.name
        try:
            result = _run(readtext(path=tmp))
            assert is_success(result)
            assert "name: test" in result["data"]["content"]
        finally:
            os.unlink(tmp)

    def test_yaml_invalid_syntax(self):
        """YAML语法错误: readtext 仅读原文(不解析),应成功返回原文"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write("key: value\n  invalid indentation\nanother: value")
            tmp = f.name
        try:
            result = _run(readtext(path=tmp))
            assert is_success(result), f"无效YAML原文应可读: {result}"
            assert "key: value" in result["data"]["content"]
        finally:
            os.unlink(tmp)

    def test_ini_file(self):
        """INI配置文件: 读取原文成功"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False, encoding='utf-8') as f:
            f.write("[section1]\nkey1 = value1\nkey2 = value2\n\n[section2]\nkey3 = value3")
            tmp = f.name
        try:
            result = _run(readtext(path=tmp))
            assert is_success(result)
            assert "section1" in result["data"]["content"]
        finally:
            os.unlink(tmp)

    def test_xml_file(self):
        """XML配置文件: 读取原文成功"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n<root><key>value</key></root>')
            tmp = f.name
        try:
            result = _run(readtext(path=tmp))
            assert is_success(result)
            assert "<root>" in result["data"]["content"]
        finally:
            os.unlink(tmp)

    def test_properties_file(self):
        """Properties配置文件: 读取原文成功"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.properties', delete=False, encoding='utf-8') as f:
            f.write("key1=value1\nkey2=value2\n# comment\nkey3=value3")
            tmp = f.name
        try:
            result = _run(readtext(path=tmp))
            assert is_success(result)
            assert "key1=value1" in result["data"]["content"]
        finally:
            os.unlink(tmp)

    def test_unknown_extension_with_format_param(self):
        """未知扩展名: readtext 直接读原文成功"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xyz', delete=False, encoding='utf-8') as f:
            json.dump({"key": "value"}, f)
            tmp = f.name
        try:
            result = _run(readtext(path=tmp))
            assert is_success(result)
            assert "key" in result["data"]["content"]
        finally:
            os.unlink(tmp)

    def test_unknown_extension_without_format(self):
        """未知扩展名且不指定format: readtext 直接读原文成功(不解析格式)"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xyz', delete=False, encoding='utf-8') as f:
            json.dump({"key": "value"}, f)
            tmp = f.name
        try:
            result = _run(readtext(path=tmp))
            assert is_success(result), f"未知扩展名原文应可读: {result}"
            assert "key" in result["data"]["content"]
        finally:
            os.unlink(tmp)

    def test_file_not_exists(self):
        """文件不存在: 应返回error"""
        result = _run(readtext(path="Z:/nonexistent/config.json"))
        assert is_error(result)

    def test_directory_not_file(self):
        """传入目录而非文件: 应返回error"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run(readtext(path=tmpdir))
            assert is_error(result), f"目录应被拒绝: {result}"

    def test_empty_file(self):
        """空文件: 读取成功(内容为空)"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            f.write('')
            tmp = f.name
        try:
            result = _run(readtext(path=tmp))
            assert is_success(result), f"空文件应可读: {result}"
        finally:
            os.unlink(tmp)

    def test_read_only_file(self):
        """只读文件: 读取成功"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump({"key": "value"}, f)
            tmp = f.name
        try:
            os.chmod(tmp, 0o444)
            result = _run(readtext(path=tmp))
            assert is_success(result), f"只读文件应可读: {result}"
        finally:
            os.chmod(tmp, 0o666)
            os.unlink(tmp)

    def test_json_large_number(self):
        """JSON大数值: 读取原文成功"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump({"large": 123456789012345678901234567890, "small": 0.0000001}, f)
            tmp = f.name
        try:
            result = _run(readtext(path=tmp))
            assert is_success(result)
            assert "large" in result["data"]["content"]
        finally:
            os.unlink(tmp)

    def test_json_null_values(self):
        """JSON null值: 读取原文成功"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump({"key": None, "list": [None, 1, None]}, f)
            tmp = f.name
        try:
            result = _run(readtext(path=tmp))
            assert is_success(result)
            assert "null" in result["data"]["content"]
        finally:
            os.unlink(tmp)
