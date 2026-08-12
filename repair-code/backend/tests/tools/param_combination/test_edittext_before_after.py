# -*- coding: utf-8 -*-
"""
edittext before/after 模式行拼接缺陷回归测试 — 小欧 2026-07-12

验证 before/after 模式在匹配行之前/之后插入独立新行(而非与原文行拼接)。

注意:本文件位于 backend/tests/(被 .gitignore 忽略),不入库,符合铁规。
"""
import asyncio
import os
from app.tools.file.edit_text_file import edittext
from app.services.task.task_context import _current_task_id


def _run(coro):
    token = _current_task_id.set("test-task-before-after")
    try:
        return asyncio.run(coro)
    finally:
        _current_task_id.reset(token)


def _read(fp):
    with open(fp, 'r', encoding='utf-8') as f:
        return f.read()


class TestBeforeAfterLineInsertion:
    """before/after 模式独立新行插入回归测试"""

    def test_case17_before_insert_new_line(self, tmp_path):
        """用例17: before模式 old=时间 行,new=编辑时间 行 → 新内容在独立新行,不拼接"""
        fp = os.path.join(str(tmp_path), "t17.txt")
        with open(fp, 'w', encoding='utf-8') as f:
            f.write("时间: 2026-07-12\n内容: 测试\n")
        result = _run(edittext(fp, "时间: 2026-07-12", "编辑时间: 2026-07-12", mode="before"))
        assert result["llm_data"]["status"]["exec_code"] in ("success", "warning")
        modified = _read(fp)
        # 新行独立存在,且与原文行不拼接
        assert modified.splitlines()[0] == "编辑时间: 2026-07-12"
        assert "编辑时间: 2026-07-12时间: 2026-07-12" not in modified
        assert "时间: 2026-07-12" in modified

    def test_case18_after_insert_new_line(self, tmp_path):
        """用例18: after模式 old=内容 行,new=验证结果 行 → 新内容在独立新行,不拼接"""
        fp = os.path.join(str(tmp_path), "t18.txt")
        with open(fp, 'w', encoding='utf-8') as f:
            f.write("时间: 2026-07-12\n内容: 测试\n")
        result = _run(edittext(fp, "内容: 测试", "验证结果: 通过", mode="after"))
        assert result["llm_data"]["status"]["exec_code"] in ("success", "warning")
        modified = _read(fp)
        lines = modified.splitlines()
        assert "验证结果: 通过" in lines
        assert "内容: 测试验证结果: 通过" not in modified
        # 验证结果应在 内容 行之后
        assert lines.index("内容: 测试") < lines.index("验证结果: 通过")

    def test_before_on_first_line(self, tmp_path):
        """before模式匹配首行:新内容成为首行,不拼接"""
        fp = os.path.join(str(tmp_path), "first.txt")
        with open(fp, 'w', encoding='utf-8') as f:
            f.write("首行\n次行\n")
        result = _run(edittext(fp, "首行", "新增首行", mode="before"))
        assert result["llm_data"]["status"]["exec_code"] in ("success", "warning")
        modified = _read(fp)
        assert modified.splitlines()[0] == "新增首行"
        assert "新增首行首行" not in modified

    def test_after_on_last_line(self, tmp_path):
        """after模式匹配末行(无尾随换行):新内容在末行之后独立新行"""
        fp = os.path.join(str(tmp_path), "last.txt")
        with open(fp, 'w', encoding='utf-8') as f:
            f.write("首行\n末行")
        result = _run(edittext(fp, "末行", "新增末行", mode="after"))
        assert result["llm_data"]["status"]["exec_code"] in ("success", "warning")
        modified = _read(fp)
        lines = modified.splitlines()
        assert lines[-1] == "新增末行"
        assert "末行新增末行" not in modified

    def test_before_mid_line_match(self, tmp_path):
        """before模式 old_string 为行内子串:新内容仍插在该行之前独立新行"""
        fp = os.path.join(str(tmp_path), "mid.txt")
        with open(fp, 'w', encoding='utf-8') as f:
            f.write("会议时间: 2026\n")
        result = _run(edittext(fp, "时间", "标记", mode="before"))
        assert result["llm_data"]["status"]["exec_code"] in ("success", "warning")
        modified = _read(fp)
        lines = modified.splitlines()
        # 2026-07-17 before 模式: 插入行与锚点行之间按 PEP8 隔一个空行
        assert lines[0] == "标记"
        assert lines[1] == ""
        assert lines[2] == "会议时间: 2026"
        assert "会议标记时间" not in modified

    def test_before_ignore_case(self, tmp_path):
        """before模式 + ignore_case:独立新行插入"""
        fp = os.path.join(str(tmp_path), "ic.txt")
        with open(fp, 'w', encoding='utf-8') as f:
            f.write("Hello World\n")
        result = _run(edittext(fp, "hello", "Hi", mode="before", ignore_case=True))
        assert result["llm_data"]["status"]["exec_code"] in ("success", "warning")
        modified = _read(fp)
        assert modified.splitlines()[0] == "Hi"
        assert "HiHello World" not in modified

    def test_after_multiline_old_string(self, tmp_path):
        """after模式 old_string 为多行:新内容插在整块之后独立新行"""
        fp = os.path.join(str(tmp_path), "multi.txt")
        with open(fp, 'w', encoding='utf-8') as f:
            f.write("Line A\nLine B\nLine C\n")
        result = _run(edittext(fp, "Line A\nLine B", "插入块", mode="after"))
        assert result["llm_data"]["status"]["exec_code"] in ("success", "warning")
        modified = _read(fp)
        lines = modified.splitlines()
        # 2026-07-17 after 模式: 插入块与锚点行(Line B)之间按 PEP8 隔一个空行
        b_idx = lines.index("Line B")
        ins_idx = lines.index("插入块")
        assert ins_idx == b_idx + 2
        assert "Line B插入块" not in modified
