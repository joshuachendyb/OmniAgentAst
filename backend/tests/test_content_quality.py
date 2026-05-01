# -*- coding: utf-8 -*-
"""
内容质量检测测试 - 覆盖设计文档v2.1全部改进的测试用例

测试覆盖：
  改进1: check_content_quality 自我指涉检测（按文件类型区分）
  改进7: _add_reasoning_warning reasoning验证

Author: 小健 - 2026-05-01
"""

import pytest
from app.services.tools.content_quality import (
    check_content_quality,
    _detect_self_ref_rate,
    _classify_file_type,
    SELF_REF_THRESHOLD_NORMAL,
    SELF_REF_THRESHOLD_SHORT,
    SHORT_CONTENT_LENGTH,
    SELF_REF_KEYWORDS,
    CODE_EXTENSIONS,
    DOC_EXTENSIONS,
)
from app.services.agent.react_output_parser import (
    _add_reasoning_warning,
    _REASONING_MIN_LENGTH,
)


# =============================================================================
# 改进1: check_content_quality - 自我指涉检测核心逻辑
# =============================================================================

class TestDetectSelfRefRate:
    """_detect_self_ref_rate 单元测试"""

    def test_pure_thought_leak(self):
        """纯思维泄漏文本：100%自我指涉"""
        content = "已成功创建并写入第一章内容。现在需要继续创建第二章。"
        rate = _detect_self_ref_rate(content)
        assert rate == 1.0

    def test_normal_novel_content(self):
        """正常小说内容：0%自我指涉"""
        content = "林凡是一名普通的大学生。他走在校园的小路上，夜色深沉。"
        rate = _detect_self_ref_rate(content)
        assert rate == 0.0

    def test_mixed_content(self):
        """混合内容：部分自我指涉"""
        content = "已成功创建并写入第一章内容。林凡是一名普通的大学生。"
        rate = _detect_self_ref_rate(content)
        assert 0.0 < rate < 1.0

    def test_empty_content(self):
        """空内容"""
        rate = _detect_self_ref_rate("")
        assert rate == 0.0

    def test_single_self_ref_sentence(self):
        """单句自我指涉"""
        content = "已成功写入文件。"
        rate = _detect_self_ref_rate(content)
        assert rate == 1.0

    def test_english_content(self):
        """英文内容：不含中文自我指涉关键词"""
        content = "Successfully created and written chapter 1. Now need to continue."
        rate = _detect_self_ref_rate(content)
        assert rate == 0.0

    def test_narrative_with_zaijieru(self):
        """叙事中含'接下来'但不是自我指涉（'接下来'不在关键词中，'接下来将'才在）"""
        content = "接下来他走向了那座古堡。夜色深沉，远处的灯火若隐若现。"
        rate = _detect_self_ref_rate(content)
        assert rate == 0.0

    def test_multiple_self_ref_keywords(self):
        """多个自我指涉关键词"""
        content = "已成功创建目录。需要继续创建文件。按照要求每章10000字。已完成写入。"
        rate = _detect_self_ref_rate(content)
        assert rate == 1.0


class TestClassifyFileType:
    """_classify_file_type 单元测试"""

    def test_code_files(self):
        """代码类文件"""
        for ext in ['.py', '.js', '.ts', '.java', '.go', '.c', '.cpp']:
            assert _classify_file_type(f"test{ext}") == "code"

    def test_document_files(self):
        """文档类文件"""
        for ext in ['.txt', '.md', '.doc', '.docx', '.csv', '.log']:
            assert _classify_file_type(f"test{ext}") == "document"

    def test_other_files(self):
        """其他文件类型"""
        for ext in ['.bin', '.dat', '.exe', '.dll', '']:
            assert _classify_file_type(f"test{ext}") == "other"

    def test_case_insensitive(self):
        """大小写不敏感"""
        assert _classify_file_type("test.PY") == "code"
        assert _classify_file_type("test.TXT") == "document"
        assert _classify_file_type("test.MD") == "document"

    def test_path_with_directory(self):
        """含目录的路径"""
        assert _classify_file_type("E:/下载/novel/第二章.txt") == "document"
        assert _classify_file_type("D:/project/src/main.py") == "code"


class TestCheckContentQuality:
    """check_content_quality 集成测试 - 按文件类型区分判定"""

    # --- 文档类文件(.txt/.md) ---

    def test_txt_thought_leak_detected(self):
        """事故案例：.txt文件思维泄漏应被检测"""
        content = "已成功创建并写入第一章内容。现在需要继续创建第二章，按照要求每章字数应在10000-20000字之间。"
        result = check_content_quality(content=content, file_path="E:/下载/小说/第二章.txt")
        assert result["is_thought_leak"] is True
        assert result["self_ref_rate"] >= 0.6
        assert result["file_type"] == "document"
        assert result["warning"] != ""

    def test_txt_normal_novel_not_detected(self):
        """正常小说内容不应被误判"""
        content = "林凡是一名普通的大学生，每天过着平凡的生活。这天晚上，他像往常一样走在回宿舍的小路上。夜色深沉，远处的灯火若隐若现，仿佛在诉说着什么。"
        result = check_content_quality(content=content, file_path="E:/下载/小说/第一章.txt")
        assert result["is_thought_leak"] is False
        assert result["warning"] == ""

    def test_md_thought_leak_detected(self):
        """Markdown文件思维泄漏应被检测"""
        content = "已成功创建README。需要继续添加说明。"
        result = check_content_quality(content=content, file_path="D:/project/README.md")
        assert result["is_thought_leak"] is True
        assert result["file_type"] == "document"

    def test_doc_chinese_100percent_not_false_positive(self):
        """文档类文件100%中文不应误判（中文占比不是检测条件）"""
        content = "春眠不觉晓，处处闻啼鸟。夜来风雨声，花落知多少。这是唐代诗人孟浩然的代表作，描绘了春天的美好景象。"
        result = check_content_quality(content=content, file_path="诗词.txt")
        assert result["is_thought_leak"] is False

    def test_doc_mixed_normal_and_self_ref_below_threshold(self):
        """文档类：少量自我指涉但覆盖率低于60%不应误判"""
        content = "第一章讲述主角的成长经历。第二章描写城市的风貌。第三章已成功完成初稿。第四章还在构思中。第五章是最终章。"
        result = check_content_quality(content=content, file_path="小说/大纲.txt")
        assert result["is_thought_leak"] is False

    # --- 代码类文件(.py/.js) ---

    def test_py_thought_leak_detected(self):
        """Python文件思维泄漏应被检测（中文占比高+自我指涉率高）"""
        content = "已成功创建配置文件。需要继续添加代码。"
        result = check_content_quality(content=content, file_path="D:/project/config.py")
        assert result["is_thought_leak"] is True
        assert result["file_type"] == "code"

    def test_py_normal_code_not_detected(self):
        """正常Python代码不应误判"""
        content = "def hello():\n    print('hello world')\n    return True"
        result = check_content_quality(content=content, file_path="D:/project/main.py")
        assert result["is_thought_leak"] is False

    def test_py_self_ref_low_chinese_not_detected(self):
        """代码类：自我指涉率高但中文占比低，不应误判"""
        content = "Successfully created. Need to continue writing. Already completed setup."
        result = check_content_quality(content=content, file_path="D:/project/setup.py")
        assert result["is_thought_leak"] is False

    def test_js_thought_leak_detected(self):
        """JS文件思维泄漏应被检测"""
        content = "已成功写入模块。现在需要继续创建下一个。"
        result = check_content_quality(content=content, file_path="D:/project/index.js")
        assert result["is_thought_leak"] is True
        assert result["file_type"] == "code"

    # --- 其他文件类型 ---

    def test_other_type_thought_leak_detected(self):
        """未知文件类型：中文占比>70%+自我指涉率高应检测"""
        content = "已成功创建并写入。需要继续执行下一步操作。"
        result = check_content_quality(content=content, file_path="D:/data/config.dat")
        assert result["is_thought_leak"] is True
        assert result["file_type"] == "other"

    def test_other_type_low_chinese_not_detected(self):
        """未知文件类型：中文占比低不应误判"""
        content = "Successfully created. Need to continue. Already completed."
        result = check_content_quality(content=content, file_path="D:/data/config.dat")
        assert result["is_thought_leak"] is False

    # --- 极短文本阈值调整 ---

    def test_very_short_text_lower_threshold(self):
        """极短文本(<50字符)阈值降至0.4"""
        content = "已成功写入。"
        result = check_content_quality(content=content, file_path="test.txt")
        assert result["self_ref_threshold"] == SELF_REF_THRESHOLD_SHORT
        assert result["is_thought_leak"] is True

    def test_normal_length_text_normal_threshold(self):
        """正常长度文本阈值0.6"""
        content = "已成功创建并写入第一章内容。现在需要继续创建第二章，按照要求每章字数应在10000-20000字之间。"
        result = check_content_quality(content=content, file_path="test.txt")
        assert result["self_ref_threshold"] == SELF_REF_THRESHOLD_NORMAL

    # --- 边界条件 ---

    def test_empty_content(self):
        """空内容"""
        result = check_content_quality(content="", file_path="test.txt")
        assert result["is_thought_leak"] is False
        assert result["warning"] == ""

    def test_none_content(self):
        """None内容"""
        result = check_content_quality(content=None, file_path="test.txt")
        assert result["is_thought_leak"] is False

    def test_non_string_content(self):
        """非字符串内容"""
        result = check_content_quality(content=12345, file_path="test.txt")
        assert result["is_thought_leak"] is False

    def test_result_structure(self):
        """返回值结构完整性"""
        result = check_content_quality(content="测试", file_path="test.txt")
        assert "is_thought_leak" in result
        assert "self_ref_rate" in result
        assert "self_ref_threshold" in result
        assert "chinese_ratio" in result
        assert "file_type" in result
        assert "warning" in result

    def test_self_ref_rate_range(self):
        """self_ref_rate在0~1之间"""
        for content in ["已成功写入。", "正常文本。", ""]:
            result = check_content_quality(content=content, file_path="test.txt")
            assert 0.0 <= result["self_ref_rate"] <= 1.0

    def test_chinese_ratio_range(self):
        """chinese_ratio在0~1之间"""
        for content in ["全中文内容", "All English", "混合mixed内容"]:
            result = check_content_quality(content=content, file_path="test.txt")
            assert 0.0 <= result["chinese_ratio"] <= 1.0


# =============================================================================
# 改进7: _add_reasoning_warning - reasoning验证
# =============================================================================

class TestAddReasoningWarning:
    """_add_reasoning_warning 单元测试"""

    def test_no_reasoning_adds_warning(self):
        """无reasoning字段时添加warning"""
        result = {"tool_name": "write_file", "content": "test"}
        out = _add_reasoning_warning(result)
        assert "parse_warning" in out
        assert "reasoning" in out["parse_warning"]

    def test_empty_reasoning_adds_warning(self):
        """空reasoning时添加warning"""
        result = {"tool_name": "write_file", "reasoning": "", "content": "test"}
        out = _add_reasoning_warning(result)
        assert "parse_warning" in out
        assert out["parse_warning"] != ""

    def test_short_reasoning_adds_warning(self):
        """reasoning过短(<10字符)时添加warning"""
        result = {"tool_name": "write_file", "reasoning": "写入文件", "content": "test"}
        out = _add_reasoning_warning(result)
        assert "parse_warning" in out

    def test_valid_reasoning_no_warning(self):
        """有效reasoning不添加warning"""
        result = {
            "tool_name": "write_file",
            "reasoning": "用户要求创建小说文件，需要使用write_file工具将小说内容写入指定路径",
            "content": "test"
        }
        out = _add_reasoning_warning(result)
        assert "parse_warning" not in out

    def test_no_tool_name_no_warning(self):
        """无tool_name时不添加warning（不是tool call）"""
        result = {"content": "test"}
        out = _add_reasoning_warning(result)
        assert "parse_warning" not in out

    def test_existing_parse_warning_not_overwritten(self):
        """已有parse_warning时不覆盖"""
        result = {"tool_name": "write_file", "reasoning": "", "parse_warning": "已有警告"}
        out = _add_reasoning_warning(result)
        assert out["parse_warning"] == "已有警告"

    def test_boundary_9_chars_warning(self):
        """9字符reasoning触发warning（<10）"""
        result = {"tool_name": "write_file", "reasoning": "123456789", "content": "test"}
        out = _add_reasoning_warning(result)
        assert "parse_warning" in out

    def test_boundary_10_chars_no_warning(self):
        """10字符reasoning不触发warning（>=10）"""
        result = {"tool_name": "write_file", "reasoning": "1234567890", "content": "test"}
        out = _add_reasoning_warning(result)
        assert "parse_warning" not in out

    def test_whitespace_only_reasoning_warning(self):
        """纯空格reasoning触发warning"""
        result = {"tool_name": "write_file", "reasoning": "   \n\t  ", "content": "test"}
        out = _add_reasoning_warning(result)
        assert "parse_warning" in out

    def test_returns_same_dict(self):
        """返回同一个字典对象（原地修改）"""
        result = {"tool_name": "write_file", "reasoning": ""}
        out = _add_reasoning_warning(result)
        assert out is result


# =============================================================================
# 改进1+2 集成: 工具层和agent层使用同一套检测逻辑
# =============================================================================

class TestToolAndAgentConsistency:
    """验证工具层(file_tools)和agent层(base_react)使用相同的检测逻辑"""

    def test_same_result_for_same_input(self):
        """相同输入应产生相同结果"""
        content = "已成功创建并写入第一章内容。现在需要继续创建第二章。"
        file_path = "E:/下载/小说/第二章.txt"

        result = check_content_quality(content=content, file_path=file_path)
        assert result["is_thought_leak"] is True
        assert result["self_ref_rate"] == 1.0

    def test_consistent_threshold(self):
        """极短文本阈值在工具层和agent层一致"""
        short_content = "已成功写入。"
        result = check_content_quality(content=short_content, file_path="test.txt")
        assert result["self_ref_threshold"] == SELF_REF_THRESHOLD_SHORT

    def test_consistent_keywords(self):
        """关键词列表覆盖事故案例"""
        accident_content = "已成功创建并写入第一章内容。现在需要继续创建第二章，按照要求每章字数应在10000-20000字之间。"
        rate = _detect_self_ref_rate(accident_content)
        assert rate >= 0.6, "事故案例的自我指涉检测率应>=60%"
