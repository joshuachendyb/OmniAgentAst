# -*- coding: utf-8 -*-
"""
grep_file_content参数组合测试 - 小欧 2026-06-24

测试类型:
1. 参数组合测试 - 12个组合(pattern/glob/ignore_case/output_mode)
2. 功能测试 - 正则/大小写/输出模式
3. 真实场景测试 - 代码搜索/日志搜索
4. 边界测试 - 空目录/无匹配/大文件
5. 负面测试 - 不存在/无效正则/空pattern
"""

import pytest
import asyncio
from pathlib import Path
from app.tools.file.grep_file_content import grep
from app.tools.tool_response import is_success, is_error


class TestGrepFileContentParamCombinations:
    """参数组合测试 - 穷举所有参数组合"""

    def test_basic_search(self, temp_output_dir):
        """组合1: 仅pattern+search_dir(默认参数)"""
        (temp_output_dir / "a.py").write_text("def hello():\n    pass", encoding="utf-8")
        (temp_output_dir / "b.py").write_text("def world():\n    pass", encoding="utf-8")

        result = asyncio.run(
            grep("def", str(temp_output_dir))
        )

        assert is_success(result)
        assert result["data"]["total_files"] == 2
        assert result["llm_data"]["metrics"]["total_matches"]["value"] == 2

    def test_with_glob_filter(self, temp_output_dir):
        """组合2: pattern+search_dir+glob"""
        (temp_output_dir / "app.py").write_text("import os", encoding="utf-8")
        (temp_output_dir / "style.css").write_text("import os", encoding="utf-8")
        (temp_output_dir / "test.py").write_text("import os", encoding="utf-8")

        result = asyncio.run(
            grep("import", str(temp_output_dir), glob="*.py")
        )

        assert is_success(result)
        assert result["data"]["total_files"] == 2

    def test_case_sensitive(self, temp_output_dir):
        """组合3: pattern+search_dir+ignore_case=False"""
        (temp_output_dir / "code.py").write_text("Hello\nhello\nHELLO", encoding="utf-8")

        result_sensitive = asyncio.run(
            grep("Hello", str(temp_output_dir), ignore_case=False)
        )
        result_insensitive = asyncio.run(
            grep("Hello", str(temp_output_dir), ignore_case=True)
        )

        assert is_success(result_sensitive)
        assert is_success(result_insensitive)
        assert result_sensitive["data"]["total_matches"] < result_insensitive["data"]["total_matches"]

    def test_glob_and_case_combined(self, temp_output_dir):
        """组合6: glob+ignore_case=False"""
        (temp_output_dir / "App.py").write_text("Class Name", encoding="utf-8")
        (temp_output_dir / "app.js").write_text("class name", encoding="utf-8")

        result = asyncio.run(
            grep("Class", str(temp_output_dir), glob="*.py", ignore_case=False)
        )

        assert is_success(result)
        assert result["data"]["total_files"] == 1

    def test_regex_pattern(self, temp_output_dir):
        """组合7: 正则表达式pattern"""
        (temp_output_dir / "code.py").write_text("def func1():\ndef func2():\nclass Foo:", encoding="utf-8")

        result = asyncio.run(
            grep(r"def \w+\(\):", str(temp_output_dir))
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total_matches"]["value"] == 2

    def test_regex_with_glob(self, temp_output_dir):
        """组合8: 正则+glob(fnmatch不支持{py,js},用*.py测试)"""
        (temp_output_dir / "app.py").write_text("import os\nimport sys", encoding="utf-8")
        (temp_output_dir / "utils.py").write_text("import os\nimport sys", encoding="utf-8")
        (temp_output_dir / "readme.md").write_text("import os", encoding="utf-8")

        result = asyncio.run(
            grep(r"import \w+", str(temp_output_dir), glob="*.py")
        )

        assert is_success(result)
        assert result["data"]["total_files"] == 2

    def test_all_params_combined(self, temp_output_dir):
        """组合9: 所有参数"""
        (temp_output_dir / "a.py").write_text("TODO: fix\nTODO: review", encoding="utf-8")
        (temp_output_dir / "b.py").write_text("todo: done", encoding="utf-8")

        result = asyncio.run(
            grep(
                "TODO", str(temp_output_dir),
                glob="*.py", ignore_case=False,
            )
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total_matches"]["value"] == 2

    def test_no_match(self, temp_output_dir):
        """组合10: 无匹配结果"""
        (temp_output_dir / "code.py").write_text("hello world", encoding="utf-8")

        result = asyncio.run(
            grep("NONEXISTENT_PATTERN", str(temp_output_dir))
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total_matches"]["value"] == 0
        assert result["data"]["total_files"] == 0

    def test_chinese_pattern(self, temp_output_dir):
        """组合11: 中文搜索模式"""
        (temp_output_dir / "doc.txt").write_text("这是一个测试文件\n包含中文内容", encoding="utf-8")

        result = asyncio.run(
            grep("测试", str(temp_output_dir))
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total_matches"]["value"] == 1

    def test_multiline_content_search(self, temp_output_dir):
        """组合12: 多行内容搜索"""
        content = """# 项目配置
database:
  host: localhost
  port: 5432

# 日志配置
logging:
  level: INFO
"""
        (temp_output_dir / "config.yaml").write_text(content, encoding="utf-8")

        result = asyncio.run(
            grep("host|port|level", str(temp_output_dir))
        )

        assert is_success(result)
        # "host"在"host: localhost"中出现2次(冒号前+localhost中), "port"1次 "level"1次
        assert result["llm_data"]["metrics"]["total_matches"]["value"] == 4


class TestGrepFileContentFeatures:
    """功能测试"""

    def test_subdirectory_search(self, temp_output_dir):
        """功能1: 递归搜索子目录"""
        sub = temp_output_dir / "src"
        sub.mkdir()
        (temp_output_dir / "root.py").write_text("TODO root", encoding="utf-8")
        (sub / "sub.py").write_text("TODO sub", encoding="utf-8")

        result = asyncio.run(
            grep("TODO", str(temp_output_dir))
        )

        assert is_success(result)
        assert result["data"]["total_files"] == 2

    def test_multiple_matches_per_file(self, temp_output_dir):
        """功能2: 单文件多行匹配"""
        (temp_output_dir / "code.py").write_text(
            "error line 1\nok line\nerror line 2\nerror line 3", encoding="utf-8"
        )

        result = asyncio.run(
            grep("error", str(temp_output_dir))
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total_matches"]["value"] == 3
        assert result["data"]["total_files"] == 1

    def test_match_content_accuracy(self, temp_output_dir):
        """功能3: 匹配内容准认性"""
        (temp_output_dir / "code.py").write_text(
            "def calculate_sum(a, b):\n    return a + b", encoding="utf-8"
        )

        result = asyncio.run(
            grep("calculate", str(temp_output_dir))
        )

        assert is_success(result)
        matches = result["data"]["matches"]
        assert len(matches) == 1
        assert "matched" in matches[0]
        assert "calculate_sum" in matches[0]["content"]
        assert matches[0]["line"] == 1
        assert matches[0]["file"].endswith("code.py")

    def test_case_insensitive_default(self, temp_output_dir):
        """功能4: 默认大小写不敏感"""
        (temp_output_dir / "code.py").write_text("ERROR\nerror\nError\n", encoding="utf-8")

        result = asyncio.run(
            grep("error", str(temp_output_dir))
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total_matches"]["value"] == 3


class TestGrepFileContentRealScenarios:
    """真实业务场景测试"""

    def test_search_todo_comments(self, temp_output_dir):
        """场景1: 搜索TODO注释"""
        (temp_output_dir / "main.py").write_text(
            "# TODO: implement login\ndef login():\n    pass\n# TODO: add validation", encoding="utf-8"
        )
        (temp_output_dir / "utils.py").write_text(
            "# FIXME: temporary workaround\ndef helper():\n    pass", encoding="utf-8"
        )

        result = asyncio.run(
            grep("TODO|FIXME", str(temp_output_dir))
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total_matches"]["value"] == 3
        assert result["data"]["total_files"] == 2

    def test_search_error_logs(self, temp_output_dir):
        """场景2: 搜索错误日志"""
        logs = """2026-06-24 10:00:00 [INFO] Server started
2026-06-24 10:01:00 [ERROR] Connection failed
2026-06-24 10:02:00 [INFO] Request processed
2026-06-24 10:03:00 [ERROR] Timeout error
2026-06-24 10:04:00 [WARNING] Slow response
"""
        (temp_output_dir / "app.log").write_text(logs, encoding="utf-8")

        result = asyncio.run(
            grep(r"\[ERROR\]", str(temp_output_dir))
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total_matches"]["value"] == 2

    def test_search_import_statements(self, temp_output_dir):
        """场景3: 搜索import语找"""
        (temp_output_dir / "app.py").write_text(
            "import os\nimport sys\nfrom pathlib import Path\nimport json", encoding="utf-8"
        )

        result = asyncio.run(
            grep(r"^(import|from) \w+", str(temp_output_dir), glob="*.py")
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total_matches"]["value"] == 4

    def test_search_function_definitions(self, temp_output_dir):
        """场景4: 搜索函数定义"""
        (temp_output_dir / "service.py").write_text(
            "class UserService:\n    def get_user(self, id):\n        pass\n    def create_user(self, data):\n        pass",
            encoding="utf-8"
        )

        result = asyncio.run(
            grep(r"def \w+\(", str(temp_output_dir), glob="*.py")
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total_matches"]["value"] == 2


class TestGrepFileContentBoundary:
    """边界测试"""

    def test_empty_directory(self, temp_output_dir):
        """边界1: 空目录"""
        empty = temp_output_dir / "empty"
        empty.mkdir()

        result = asyncio.run(
            grep("test", str(empty))
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total_matches"]["value"] == 0

    def test_binary_file_skipped(self, temp_output_dir):
        """边界2: 二进制文件被跳过"""
        (temp_output_dir / "image.png").write_bytes(b'\x89PNG\r\n\x1a\n')
        (temp_output_dir / "code.py").write_text("TODO: fix", encoding="utf-8")

        result = asyncio.run(
            grep("TODO", str(temp_output_dir))
        )

        assert is_success(result)
        assert result["data"]["total_files"] == 1

    def test_large_file_search(self, temp_output_dir):
        """边界3: 大文件搜索"""
        lines = [f"line {i}: normal content\n" for i in range(1, 501)]
        lines[100] = "line 100: TARGET_FOUND\n"
        lines[300] = "line 300: TARGET_FOUND\n"
        (temp_output_dir / "large.txt").write_text("".join(lines), encoding="utf-8")

        result = asyncio.run(
            grep("TARGET_FOUND", str(temp_output_dir))
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total_matches"]["value"] == 2

    def test_special_regex_chars(self, temp_output_dir):
        """边界4: 特殊正则字符"""
        (temp_output_dir / "code.py").write_text(
            "url = 'https://example.com'\npath = '/api/v1/users'", encoding="utf-8"
        )

        result = asyncio.run(
            grep(r"https://\w+\.\w+", str(temp_output_dir))
        )

        assert is_success(result)
        assert result["llm_data"]["metrics"]["total_matches"]["value"] == 1


class TestGrepFileContentNegative:
    """负面测试"""

    def test_search_dir_not_found(self, temp_output_dir):
        """负面1: 搜索目录不存在"""
        result = asyncio.run(
            grep("test", str(temp_output_dir / "nonexistent"))
        )

        assert is_error(result)
        assert result["llm_data"]["status"]["exec_code"] == "error"

    def test_empty_pattern(self, temp_output_dir):
        """负面2: 空搜索模式"""
        (temp_output_dir / "file.txt").write_text("content", encoding="utf-8")

        result = asyncio.run(
            grep("", str(temp_output_dir))
        )

        assert is_error(result)
        assert result["llm_data"]["status"]["exec_code"] == "error"

    def test_invalid_regex(self, temp_output_dir):
        """负面3: 无效正则表达式"""
        (temp_output_dir / "file.txt").write_text("content", encoding="utf-8")

        result = asyncio.run(
            grep("[invalid", str(temp_output_dir))
        )

        assert is_error(result)
        assert result["llm_data"]["status"]["exec_code"] == "error"

    def test_whitespace_only_pattern(self, temp_output_dir):
        """负面4: 纯空白pattern"""
        (temp_output_dir / "file.txt").write_text("content", encoding="utf-8")

        result = asyncio.run(
            grep("   ", str(temp_output_dir))
        )

        assert is_error(result)
        assert result["llm_data"]["status"]["exec_code"] == "error"


class TestGrepDeletedFileFilter:
    """P06: 搜索后文件被删除 → 从结果过滤并重算计数 — 小欧 2026-08-07"""

    def test_deleted_file_filtered_from_results(self, temp_output_dir):
        """删除命中的文件后重新grep: 该文件不再出现在matches, 计数重算"""
        f1 = temp_output_dir / "keep.py"
        f2 = temp_output_dir / "todelete.py"
        f1.write_text("def token():\n    pass", encoding="utf-8")
        f2.write_text("def token():\n    pass", encoding="utf-8")

        r1 = asyncio.run(grep("token", str(temp_output_dir)))
        assert r1["data"]["total_files"] == 2

        # 删除一个命中文件后重新搜索
        f2.unlink()
        r2 = asyncio.run(grep("token", str(temp_output_dir)))
        assert r2["data"]["total_files"] == 1
        assert r2["data"]["total_matches"] == 1
        files = [m.get("file") for m in r2["data"]["matches"]]
        assert all(Path(f).exists() for f in files)
        assert "todelete.py" not in "".join(files)

    def test_all_files_deleted_yields_empty(self, temp_output_dir):
        """所有命中文件被删除 → matches为空且计数为0"""
        f1 = temp_output_dir / "gone1.py"
        f1.write_text("def foo():\n    pass", encoding="utf-8")
        r1 = asyncio.run(grep("foo", str(temp_output_dir)))
        assert r1["data"]["total_files"] == 1

        f1.unlink()
        r2 = asyncio.run(grep("foo", str(temp_output_dir)))
        assert r2["data"]["total_files"] == 0
        assert r2["data"]["total_matches"] == 0
        assert r2["data"]["matches"] == []
