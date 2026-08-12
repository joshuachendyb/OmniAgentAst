# -*- coding: utf-8 -*-
"""#4 自动纠正: _auto_correct_file_tool 单元测试 + execute_tools 集成测试 — 小欧 2026-07-21"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ═══════════════════════════════════════════════════════════
# _auto_correct_file_tool 单元测试
# ═══════════════════════════════════════════════════════════

class TestAutoCorrectFileTool:
    """#4 文件扩展名预检自动纠正 — 单元测试"""

    def _import(self):
        from app.services.agent.handlers.action_handler import _auto_correct_file_tool
        return _auto_correct_file_tool

    # ── read 工具系列 ──

    def test_readtext_to_read_docx_for_docx(self):
        """readtext(.docx) → read_docx"""
        fn = self._import()
        corrected, orig = fn("readtext", {"path": "report.docx"})
        assert corrected == "read_docx"
        assert orig == "readtext"

    def test_readtext_to_read_xlsx_for_xlsx(self):
        """readtext(.xlsx) → read_xlsx"""
        fn = self._import()
        corrected, orig = fn("readtext", {"path": "data.xlsx"})
        assert corrected == "read_xlsx"
        assert orig == "readtext"

    def test_readtext_to_read_pdf_for_pdf(self):
        """readtext(.pdf) → read_pdf"""
        fn = self._import()
        corrected, orig = fn("readtext", {"path": "doc.pdf"})
        assert corrected == "read_pdf"
        assert orig == "readtext"

    def test_readtext_to_read_pptx_for_pptx(self):
        """readtext(.pptx) → read_pptx"""
        fn = self._import()
        corrected, orig = fn("readtext", {"path": "slides.pptx"})
        assert corrected == "read_pptx"
        assert orig == "readtext"

    def test_readtext_with_csv_unchanged(self):
        """readtext(.csv) 保持原样（CSV是文本格式，readtext能读）"""
        fn = self._import()
        corrected, orig = fn("readtext", {"path": "data.csv"})
        assert corrected == "readtext"
        assert orig is None

    def test_read_xlsx_with_csv_unchanged(self):
        """P07: read_xlsx(.csv) 保持原样 — CSV双域(文本+表格), 不被改写为readtext — 小欧 2026-08-07"""
        fn = self._import()
        corrected, orig = fn("read_xlsx", {"path": "data.csv"})
        assert corrected == "read_xlsx"
        assert orig is None

    def test_read_xlsx_with_xlsx_unchanged(self):
        """read_xlsx(.xlsx) 保持原样（扩展名匹配）"""
        fn = self._import()
        corrected, orig = fn("read_xlsx", {"path": "data.xlsx"})
        assert corrected == "read_xlsx"
        assert orig is None

    # ── write 工具系列 ──

    def test_writetext_to_write_docx_for_docx(self):
        """writetext(.docx) → write_docx"""
        fn = self._import()
        corrected, orig = fn("writetext", {"path": "report.docx"})
        assert corrected == "write_docx"
        assert orig == "writetext"

    def test_writetext_to_write_xlsx_for_xlsx(self):
        """writetext(.xlsx) → write_xlsx"""
        fn = self._import()
        corrected, orig = fn("writetext", {"path": "data.xlsx"})
        assert corrected == "write_xlsx"
        assert orig == "writetext"

    def test_writetext_to_write_pdf_for_pdf(self):
        """writetext(.pdf) → write_pdf"""
        fn = self._import()
        corrected, orig = fn("writetext", {"path": "doc.pdf"})
        assert corrected == "write_pdf"
        assert orig == "writetext"

    def test_writetext_to_write_pptx_for_pptx(self):
        """writetext(.pptx) → write_pptx"""
        fn = self._import()
        corrected, orig = fn("writetext", {"path": "slides.pptx"})
        assert corrected == "write_pptx"
        assert orig == "writetext"

    # ── 已知正确工具不纠正 ──

    def test_read_docx_with_docx_unchanged(self):
        """read_docx(.docx) 不纠正"""
        fn = self._import()
        corrected, orig = fn("read_docx", {"path": "report.docx"})
        assert corrected == "read_docx"
        assert orig is None

    def test_read_xlsx_with_xlsx_unchanged(self):
        """read_xlsx(.xlsx) 不纠正"""
        fn = self._import()
        corrected, orig = fn("read_xlsx", {"path": "data.xlsx"})
        assert corrected == "read_xlsx"
        assert orig is None

    def test_read_pdf_with_pdf_unchanged(self):
        """read_pdf(.pdf) 不纠正"""
        fn = self._import()
        corrected, orig = fn("read_pdf", {"path": "doc.pdf"})
        assert corrected == "read_pdf"
        assert orig is None

    def test_read_pptx_with_pptx_unchanged(self):
        """read_pptx(.pptx) 不纠正"""
        fn = self._import()
        corrected, orig = fn("read_pptx", {"path": "slides.pptx"})
        assert corrected == "read_pptx"
        assert orig is None

    # ── 兜底: 专用工具拿错文件→纠正为通用工具 ──

    def test_read_docx_with_md_falls_to_readtext(self):
        """read_docx(.md) → readtext（专用工具拿错文本文件，兜底文本工具）"""
        fn = self._import()
        corrected, orig = fn("read_docx", {"path": "readme.md"})
        assert corrected == "readtext"
        assert orig == "read_docx"

    def test_read_xlsx_with_txt_falls_to_readtext(self):
        """read_xlsx(.txt) → readtext"""
        fn = self._import()
        corrected, orig = fn("read_xlsx", {"path": "notes.txt"})
        assert corrected == "readtext"
        assert orig == "read_xlsx"

    def test_write_xlsx_with_txt_falls_to_writetext(self):
        """write_xlsx(.txt) → writetext"""
        fn = self._import()
        corrected, orig = fn("write_xlsx", {"path": "notes.txt"})
        assert corrected == "writetext"
        assert orig == "write_xlsx"

    def test_write_docx_with_log_falls_to_writetext(self):
        """write_docx(.log) → writetext"""
        fn = self._import()
        corrected, orig = fn("write_docx", {"path": "app.log"})
        assert corrected == "writetext"
        assert orig == "write_docx"

    # ── 媒体工具系列 ──

    def test_readtext_to_readmedia_for_png(self):
        """readtext(.png) → readmedia"""
        fn = self._import()
        corrected, orig = fn("readtext", {"path": "image.png"})
        assert corrected == "readmedia"
        assert orig == "readtext"

    def test_readmedia_with_png_unchanged(self):
        """readmedia(.png) 保持原样"""
        fn = self._import()
        corrected, orig = fn("readmedia", {"path": "image.png"})
        assert corrected == "readmedia"
        assert orig is None

    # ── 非文件工具不参与纠正 ──

    def test_searchweb_not_corrected(self):
        """searchweb 不参与纠正"""
        fn = self._import()
        corrected, orig = fn("searchweb", {"query": "test"})
        assert corrected == "searchweb"
        assert orig is None

    def test_grep_not_corrected(self):
        """grep 不参与纠正"""
        fn = self._import()
        corrected, orig = fn("grep", {"pattern": "test", "path": "file.txt"})
        assert corrected == "grep"
        assert orig is None

    # ── 边界: 无path参数不纠正 ──

    def test_no_path_unchanged(self):
        """无 path 参数不纠正"""
        fn = self._import()
        corrected, orig = fn("readtext", {})
        assert corrected == "readtext"
        assert orig is None

    def test_empty_path_unchanged(self):
        """空 path 不纠正"""
        fn = self._import()
        corrected, orig = fn("readtext", {"path": ""})
        assert corrected == "readtext"
        assert orig is None

    # ── 大小写不敏感 ──

    def test_uppercase_extension(self):
        """大写扩展名 .DOCX 也纠正"""
        fn = self._import()
        corrected, orig = fn("readtext", {"path": "REPORT.DOCX"})
        assert corrected == "read_docx"
        assert orig == "readtext"

    # ── 路径中包含点的情况 ──

    def test_dotted_filename(self):
        """文件名包含多点的 .tar.gz 不触发专用映射，兜底 readtext"""
        fn = self._import()
        corrected, orig = fn("readtext", {"path": "archive.tar.gz"})
        assert corrected == "readtext"
        assert orig is None

    def test_dotfile_no_ext(self):
        """点文件无扩展名（如 .gitignore）不纠正"""
        fn = self._import()
        corrected, orig = fn("readtext", {"path": "/path/to/.gitignore"})
        assert corrected == "readtext"
        assert orig is None


# ═══════════════════════════════════════════════════════════
# execute_tools 集成测试
# ═══════════════════════════════════════════════════════════

class TestExecuteToolsAutoCorrect:
    """#4 execute_tools 中自动纠正集成测试"""

    @pytest.mark.asyncio
    async def test_single_tool_corrects_tool_name(self):
        """单工具路径: tool_name 被纠正，llm_data.summary 含纠正标注"""
        from app.services.agent.handlers.action_handler import execute_tools
        from app.services.agent.tool_executor import execute_tool

        agent = MagicMock()
        agent.task_id = "test-task-id"
        agent._retry_engine = MagicMock()
        agent._retry_engine.execute_tool_with_retry = AsyncMock(return_value={
            "code": 200, "data": {},
            "llm_data": {
                "action": {"tool": "read_docx", "target": "report.docx"},
                "summary": "读取Word report.docx，成功",
                "status": {"exec_code": "success"},
            }
        })

        all_calls = [
            {"tool_name": "readtext", "tool_params": {"path": "report.docx"},
             "_tool_call_id": "tc_1"}
        ]
        results = await execute_tools(
            agent, all_calls, False,
            "readtext", {"path": "report.docx"}
        )
        assert len(results) == 1
        llm = results[0].get("llm_data", {})
        assert "工具自动纠正自:readtext" in llm.get("summary", "")

    @pytest.mark.asyncio
    async def test_parallel_tools_each_corrected(self):
        """并行多工具: 每个工具各自纠正"""
        from app.services.agent.handlers.action_handler import execute_tools

        agent = MagicMock()
        agent.task_id = "test-task-id"
        agent._retry_engine = MagicMock()

        async def _mock_exec(agent, tool_name, tool_params, parallel=False, on_retry_started=None):
            return {
                "code": 200, "data": {},
                "llm_data": {
                    "action": {"tool": tool_name},
                    "summary": f"执行{tool_name}成功",
                    "status": {"exec_code": "success"},
                }
            }

        with patch("app.services.agent.handlers.action_handler.execute_tool", _mock_exec):
            all_calls = [
                {"tool_name": "readtext", "tool_params": {"path": "a.docx"},
                 "_tool_call_id": "tc_1"},
                {"tool_name": "readtext", "tool_params": {"path": "b.pdf"},
                 "_tool_call_id": "tc_2"},
            ]
            results = await execute_tools(
                agent, all_calls, True,
                "readtext", {"path": "a.docx"}
            )
            assert len(results) == 2
            assert "工具自动纠正自:readtext" in results[0]["llm_data"]["summary"]
            assert "工具自动纠正自:readtext" in results[1]["llm_data"]["summary"]

    @pytest.mark.asyncio
    async def test_already_correct_tool_no_correction_note(self):
        """已正确的工具不追加纠正标注"""
        from app.services.agent.handlers.action_handler import execute_tools

        agent = MagicMock()
        agent.task_id = "test-task-id"
        agent._retry_engine = MagicMock()
        agent._retry_engine.execute_tool_with_retry = AsyncMock(return_value={
            "code": 200, "data": {},
            "llm_data": {
                "action": {"tool": "read_docx"},
                "summary": "读取Word成功",
                "status": {"exec_code": "success"},
            }
        })

        all_calls = [
            {"tool_name": "read_docx", "tool_params": {"path": "report.docx"},
             "_tool_call_id": "tc_1"}
        ]
        results = await execute_tools(
            agent, all_calls, False,
            "read_docx", {"path": "report.docx"}
        )
        assert len(results) == 1
        summary = results[0]["llm_data"]["summary"]
        assert "工具自动纠正自" not in summary

    @pytest.mark.asyncio
    async def test_non_file_tool_no_correction(self):
        """非文件工具（searchweb）不纠正"""
        from app.services.agent.handlers.action_handler import execute_tools

        agent = MagicMock()
        agent.task_id = "test-task-id"
        agent._retry_engine = MagicMock()
        agent._retry_engine.execute_tool_with_retry = AsyncMock(return_value={
            "code": 200, "data": {},
            "llm_data": {
                "action": {"tool": "searchweb"},
                "summary": "搜索成功",
                "status": {"exec_code": "success"},
            }
        })

        all_calls = [
            {"tool_name": "searchweb", "tool_params": {"query": "hello"},
             "_tool_call_id": "tc_1"}
        ]
        results = await execute_tools(
            agent, all_calls, False,
            "searchweb", {"query": "hello"}
        )
        assert len(results) == 1
        summary = results[0]["llm_data"]["summary"]
        assert "工具自动纠正自" not in summary
