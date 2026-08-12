# -*- coding: utf-8 -*-
"""
pytest fixtures for tool parameter combination tests
xiaojian 2026-06-27
"""
import csv
import json
import pytest
import tempfile
import os
from pathlib import Path


@pytest.fixture
def temp_output_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_input_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_csv_data(temp_input_dir):
    csv_path = temp_input_dir / "test_employees.csv"
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(["name", "age", "salary", "department"])
        w.writerow(["zhangsan", 25, 50000, "engineering"])
        w.writerow(["lisi", 30, 60000, "marketing"])
        w.writerow(["wangwu", 28, 55000, "engineering"])
        w.writerow(["zhaoliu", 35, 70000, "sales"])
        w.writerow(["sunqi", 22, 45000, "marketing"])
    return str(csv_path)


@pytest.fixture
def sample_json_data():
    return [
        {"name": "zhangsan", "age": 25, "salary": 50000, "department": "engineering"},
        {"name": "lisi", "age": 30, "salary": 60000, "department": "marketing"},
        {"name": "wangwu", "age": 28, "salary": 55000, "department": "engineering"},
        {"name": "zhaoliu", "age": 35, "salary": 70000, "department": "sales"},
        {"name": "sunqi", "age": 22, "salary": 45000, "department": "marketing"},
    ]


def is_success(result: dict) -> bool:
    """Check if tool result indicates success."""
    if not isinstance(result, dict):
        return False
    status = result.get("llm_data", {}).get("status", {})
    return status.get("exec_code") == "success"


def is_error(result: dict) -> bool:
    """Check if tool result indicates error."""
    if not isinstance(result, dict):
        return False
    status = result.get("llm_data", {}).get("status", {})
    return status.get("exec_code") == "error"


def rows_to_dicts(rows: list, columns: list) -> list:
    """rows(list-of-lists)+columns(list) -> list-of-dicts - xiaojian 2026-06-27"""
    return [dict(zip(columns, row)) for row in rows]


@pytest.fixture
def docx_test_data():
    """write_docx / write_pdf 共用的参数组合测试数据 — 小欧 2026-07-12

    每个值均为 {title, content} 字典,供 write_x(title=..., content=...) 调用。
    覆盖: 空文档 / 仅标题 / 仅内容 / 标题+内容 / 多级标题 / 各类列表 / 真实场景 / 边界。
    """
    return {
        "empty": {"title": "", "content": ""},
        "title_only": {"title": "测试报告", "content": ""},
        "content_only": {"title": "", "content": "正文内容：这是仅包含内容的文档。"},
        "simple": {"title": "简单测试文档", "content": "这是内容段落，用于验证标题加内容的组合渲染。"},
        "headings": {"title": "标题测试", "content": "\n".join(f"{'#' * i} 标题{i}" for i in range(1, 7))},
        "unordered_list_dash": {"title": "无序列表-短横线", "content": "\n".join(f"- 项目{i}" for i in range(1, 5))},
        "unordered_list_asterisk": {"title": "无序列表-星号", "content": "\n".join(f"* 项目{i}" for i in range(1, 4))},
        "ordered_list": {"title": "有序列表", "content": "\n".join(f"{n}. 项目{n}" for n in (10, 20, 30, 40, 50))},
        "mixed_lists": {
            "title": "混合列表",
            "content": "\n".join([f"- 无序项{i}" for i in range(1, 4)] + [f"{n}. 有序项{n}" for n in (5, 6, 7)]),
        },
        "tech_report": {
            "title": "技术审计报告",
            "content": (
                "# 技术审查报告\n\n"
                "## 一、审查范围\n本次审查覆盖核心模块。\n\n"
                "## 二、发现问题\n发现若干性能问题需要修复。\n\n"
                "## 三、解决方案\n提出相应优化方案。\n\n"
                "## 四、结论\n审查工作已完成。"
            ),
        },
        "meeting_minutes": {
            "title": "会议纪要",
            "content": "\n".join(f"第{i}点：会议内容说明与后续行动项。" for i in range(1, 8)),
        },
        "special_chars": {"title": "特殊字符测试", "content": "包含 <tag> 与 > 符号 以及 & 字符 的文档内容。"},
        "long_content": {
            "title": "长内容文档",
            "content": "\n".join(f"这是第{i}段内容，用于测试长文档的生成与渲染。" for i in range(1, 105)),
        },
    }


@pytest.fixture
def setup_test_files(tmp_path):
    """read_text_file 测试用的真实文件集 — 小欧 2026-07-12

    提供: text_file(>100行, 含审计报告标题/二级标题/代码块, 支持分页到100行)、
    py_file(含 class UserService / async def get_user)、json_file(含 name/version)。
    """
    text_file = tmp_path / "report.txt"
    text_lines = [
        "# 技术审计报告",
        "## 一,执行摘要",
        "本文档为技术审计报告示例，用于验证文本读取工具的各项能力。",
        "```python",
        "def example():",
        "    return 42",
        "```",
    ]
    text_lines.extend(f"这是第{i}行内容，用于测试分页与长文件读取。" for i in range(8, 121))
    text_file.write_text("\n".join(text_lines), encoding="utf-8")

    py_file = tmp_path / "user_service.py"
    py_file.write_text(
        "class UserService:\n"
        "    def __init__(self):\n"
        "        self.users = {}\n\n"
        "    async def get_user(self, user_id: int):\n"
        "        return self.users.get(user_id)\n",
        encoding="utf-8",
    )

    json_file = tmp_path / "config.json"
    json_file.write_text(
        '{\n  "name": "test",\n  "version": "1.0.0",\n  "description": "test config"\n}\n',
        encoding="utf-8",
    )

    return {
        "text_file": str(text_file),
        "py_file": str(py_file),
        "json_file": str(json_file),
    }
