# -*- coding: utf-8 -*-
"""
write_pdf参数组合测试 - 小健 2026-06-24

测试类型:
1. 基础功能测试 - 参数组合
2. Markdown功能测试 - 各语法元素
3. 真实场景测试 - 业务文档
4. 边界测试 - 特殊情况
5. 负面测试 - 错误处理
"""

import pytest
from pathlib import Path
import pdfplumber
from app.tools.document.write_pdf import write_pdf
from app.tools.tool_response import is_success, is_error


class TestWritePdfBasicParams:
    """基础参数组合测试"""

    def test_empty_document(self, temp_output_dir, docx_test_data):
        """Case 1: 空文档"""
        test_data = docx_test_data["empty"]
        file_path = temp_output_dir / "empty.pdf"

        result = write_pdf(str(file_path), title=test_data["title"], content=None)

        assert is_success(result)
        assert file_path.exists()
        assert file_path.stat().st_size > 0, "PDF文件大小应该大于0"

    def test_title_only(self, temp_output_dir, docx_test_data):
        """Case 2: 仅标题"""
        test_data = docx_test_data["title_only"]
        file_path = temp_output_dir / "title_only.pdf"

        result = write_pdf(str(file_path), title=test_data["title"], content=None)

        assert is_success(result)
        assert file_path.exists()

        with pdfplumber.open(str(file_path)) as pdf:
            text = pdf.pages[0].extract_text()
            assert "测试报告" in text, "PDF应该包含标题'测试报告'"

    def test_content_only(self, temp_output_dir, docx_test_data):
        """Case 3: 仅内容"""
        test_data = docx_test_data["content_only"]
        file_path = temp_output_dir / "content_only.pdf"

        result = write_pdf(str(file_path), title=test_data["title"], content=test_data["content"])

        assert is_success(result)
        assert file_path.exists()

        with pdfplumber.open(str(file_path)) as pdf:
            text = pdf.pages[0].extract_text()
            assert "正文内容" in text, "PDF应该包含内容'正文内容'"

    def test_title_and_content(self, temp_output_dir, docx_test_data):
        """Case 4: 标题+内容"""
        test_data = docx_test_data["simple"]
        file_path = temp_output_dir / "simple.pdf"

        result = write_pdf(str(file_path), title=test_data["title"], content=test_data["content"])

        assert is_success(result)
        assert file_path.exists()

        with pdfplumber.open(str(file_path)) as pdf:
            text = pdf.pages[0].extract_text()
            assert "简单文档" in text or "内容" in text, "PDF应该包含标题或内容"


class TestWritePdfMarkdownHeadings:
    """Markdown标题功能测试"""

    @pytest.mark.parametrize("level,prefix,content_key", [
        (1, "# ", "h1"),
        (2, "## ", "h2"),
        (3, "### ", "h3"),
        (4, "#### ", "h4"),
    ])
    def test_single_heading_level(self, temp_output_dir, level, prefix, content_key):
        """测试单个标题级别(PDF支持到4级)"""
        file_path = temp_output_dir / f"heading_{content_key}.pdf"
        content = f"{prefix}{content_key}标题内容"

        result = write_pdf(str(file_path), title=None, content=content)

        assert is_success(result)
        assert file_path.exists()

    def test_all_heading_levels(self, temp_output_dir):
        """测试所有4级标题"""
        file_path = temp_output_dir / "all_headings.pdf"
        content = """# 一级标题

一级标题下的内容.

## 二级标题

二级标题下的内容.

### 三级标题

三级标题下的内容.

#### 四级标题

四级标题下的内容.
"""
        result = write_pdf(str(file_path), title="标题测试", content=content)

        assert is_success(result)


class TestWritePdfMarkdownLists:
    """Markdown列表功能测试"""

    def test_unordered_list_dash(self, temp_output_dir):
        """无序列表 - 短横线(-)"""
        file_path = temp_output_dir / "unordered_dash.pdf"
        content = """- 项目1
- 项目2
- 项目3
"""
        result = write_pdf(str(file_path), content=content)

        assert is_success(result)

    def test_unordered_list_asterisk(self, temp_output_dir):
        """无序列表 - 星号(*)"""
        file_path = temp_output_dir / "unordered_asterisk.pdf"
        content = """* 星号项
* 星号项
* 星号项
"""
        result = write_pdf(str(file_path), content=content)

        assert is_success(result)

    def test_ordered_list(self, temp_output_dir):
        """有序列表 - 任意数字前缀"""
        file_path = temp_output_dir / "ordered.pdf"
        content = """1. 第一项
2. 第二项
10. 第十项
99. 第九十九项
"""
        result = write_pdf(str(file_path), content=content)

        assert is_success(result)

    def test_mixed_lists(self, temp_output_dir):
        """混合列表"""
        file_path = temp_output_dir / "mixed_lists.pdf"
        content = """无序列表:
- 项目A
- 项目B

有序列表:
1. 步骤1
2. 步骤2
"""
        result = write_pdf(str(file_path), title="混合列表测试", content=content)

        assert is_success(result)


class TestWritePdfRealScenarios:
    """真实场景测试"""

    def test_tech_report(self, temp_output_dir, docx_test_data):
        """场景1: 技术报告"""
        test_data = docx_test_data["tech_report"]
        file_path = temp_output_dir / "tech_report.pdf"

        result = write_pdf(str(file_path), title=test_data["title"], content=test_data["content"])

        assert is_success(result)
        assert file_path.exists()

        with pdfplumber.open(str(file_path)) as pdf:
            text = pdf.pages[0].extract_text()
            assert "审查" in text or "问题" in text, "PDF应该包含技术报告内容"

    def test_meeting_minutes(self, temp_output_dir, docx_test_data):
        """场景2: 会议纪要"""
        test_data = docx_test_data["meeting_minutes"]
        file_path = temp_output_dir / "meeting_minutes.pdf"

        result = write_pdf(str(file_path), title=test_data["title"], content=test_data["content"])

        assert is_success(result)
        assert file_path.exists()

        with pdfplumber.open(str(file_path)) as pdf:
            text = pdf.pages[0].extract_text()
            assert "会议" in text or "项目" in text, "PDF应该包含会议纪要内容"

    def test_from_register_examples(self, temp_output_dir):
        """场景3: register.py中的examples"""
        file_path1 = temp_output_dir / "report.pdf"
        result1 = write_pdf(str(file_path1), title="测试报告", content="这是报告内容")
        assert is_success(result1)
        assert file_path1.stat().st_size > 0

        file_path2 = temp_output_dir / "structured_report.pdf"
        content = "# 第一章\n\n正文内容\n\n- 列表项\n- 列表项"
        result2 = write_pdf(str(file_path2), title="结构化报告", content=content)
        assert is_success(result2)
        assert file_path2.stat().st_size > 0


class TestWritePdfBoundary:
    """边界测试"""

    def test_special_chars(self, temp_output_dir, docx_test_data):
        """边界1: 特殊字符"""
        test_data = docx_test_data["special_chars"]
        file_path = temp_output_dir / "special_chars.pdf"

        result = write_pdf(str(file_path), title=test_data["title"], content=test_data["content"])

        assert is_success(result)

    def test_long_content(self, temp_output_dir, docx_test_data):
        """边界2: 长内容100行"""
        test_data = docx_test_data["long_content"]
        file_path = temp_output_dir / "long_content.pdf"

        result = write_pdf(str(file_path), title=test_data["title"], content=test_data["content"])

        assert is_success(result)

    def test_chinese_only(self, temp_output_dir):
        """边界3: 纯中文"""
        file_path = temp_output_dir / "chinese_only.pdf"
        content = "这是纯中文内容测试.包含中文标点:,.,!?"

        result = write_pdf(str(file_path), title="中文标题", content=content)

        assert is_success(result)

        with pdfplumber.open(str(file_path)) as pdf:
            text = pdf.pages[0].extract_text()
            assert "中文" in text, "PDF应该包含中文内容"

    def test_empty_lines(self, temp_output_dir):
        """边界4: 多空行"""
        file_path = temp_output_dir / "empty_lines.pdf"
        content = """第一段


第二段


第三段
"""
        result = write_pdf(str(file_path), content=content)

        assert is_success(result)

    def test_overwrite_existing(self, temp_output_dir):
        """边界5: 覆盖已存在文件"""
        file_path = temp_output_dir / "overwrite.pdf"

        result1 = write_pdf(str(file_path), title="第一次", content="内容1")
        assert is_success(result1)
        first_size = file_path.stat().st_size

        result2 = write_pdf(str(file_path), title="第二次", content="内容2")
        assert is_success(result2)
        second_size = file_path.stat().st_size

        assert first_size > 0 and second_size > 0, "文件大小应该大于0"


class TestWritePdfNegative:
    """负面测试 - 错误处理"""

    def test_invalid_path_nonexistent_drive(self):
        """负面1: 无效驱动器"""
        result = write_pdf("Z:/nonexistent/path/file.pdf", title="测试")

        assert is_error(result)
        assert result["llm_data"]["status"]["exec_code"] == "error"


class TestWritePdfLlmData:
    """llm_data结构验证"""

    def test_llm_data_success_structure(self, temp_output_dir):
        """验证成功时llm_data结构"""
        file_path = temp_output_dir / "llm_test.pdf"
        result = write_pdf(str(file_path), title="测试", content="内容")

        llm_data = result["llm_data"]

        assert "summary" in llm_data
        assert "action" in llm_data
        assert "status" in llm_data
        assert "duration_ms" in llm_data
        assert "metrics" in llm_data

        assert llm_data["status"]["exec_code"] == "success"
        assert llm_data["action"]["tool"] == "write_pdf"
        assert llm_data["action"]["tool_zh"] == "写入PDF"

    def test_llm_data_error_structure(self):
        """验证错误时llm_data结构"""
        result = write_pdf("Z:/invalid/path.pdf")

        llm_data = result["llm_data"]

        assert llm_data["status"]["exec_code"] == "error"
        assert "detail" in llm_data["status"]
        assert llm_data["metrics"] == {}
