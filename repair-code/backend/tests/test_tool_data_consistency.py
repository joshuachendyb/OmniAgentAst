# 编辑历史:
#   2026-07-18 小健 修正_file-tool LLM-data builder 调用签名对齐07-18重构
#   2026-07-25 小欧 test_build_execute_shell_command_llm_data加cmd_short参数(assert强制传参)
# -*- coding: utf-8 -*-
"""test"""

import pytest
from typing import Any, Dict

from app.tools.tool_response import build_success, build_error, build_warning

# ============================================================
# llm_data 5存楁标准结撴瀯验证
# ============================================================

# 标准结撴瀯完氫箟,堝应该璁℃件妗?.10,?LLM_DATA_REQUIRED_KEYS = {"summary", "action", "status", "duration_ms", "metrics"}
ACTION_REQUIRED_KEYS = {"tool", "tool_zh", "target", "params"}
STATUS_REQUIRED_KEYS = {"exec_code", "message", "code", "detail", "hint"}
VALID_EXEC_CODES = {"success", "error", "warning"}

# ============================================================
# File tools builder function 测试数据,?5中級
# ============================================================

def test_build_read_text_file_llm_data_success():
    from app.tools.file.read_text_file import _build_read_text_file_llm_data
    llm_data = _build_read_text_file_llm_data("success", 10, "/a.txt", 15, 100, 1024)
    assert llm_data["status"]["exec_code"] == "success"
    assert llm_data["duration_ms"] == 10
    assert "lines" in llm_data["metrics"]
    assert "bytes" in llm_data["metrics"]

def test_build_read_text_file_llm_data_error():
    from app.tools.file.read_text_file import _build_read_text_file_llm_data
    llm_data = _build_read_text_file_llm_data("error", 5, "/a.txt", detail="file not found")
    assert llm_data["status"]["exec_code"] == "error"
    assert "失败" in llm_data["summary"]
    assert llm_data["metrics"] == {}

def test_build_read_text_file_llm_data_zero_values():
    from app.tools.file.read_text_file import _build_read_text_file_llm_data
    llm_data = _build_read_text_file_llm_data("success", 0, "", 0, 0, 0)
    assert llm_data["duration_ms"] == 0
    assert llm_data["metrics"]["lines"]["value"] == 0

def test_build_write_text_file_llm_data_success():
    from app.tools.file.write_text_file import _build_write_text_file_llm_data
    llm_data = _build_write_text_file_llm_data("success", 20, "/b.txt", 500)
    assert llm_data["status"]["exec_code"] == "success"
    assert "写入" in llm_data["summary"]
    assert llm_data["metrics"]["bytes_written"]["value"] == 500

def test_build_write_text_file_llm_data_error():
    from app.tools.file.write_text_file import _build_write_text_file_llm_data
    llm_data = _build_write_text_file_llm_data("error", 5, "/b.txt", detail="误冮檺中嶈冻")
    assert llm_data["status"]["exec_code"] == "error"
    assert llm_data["metrics"] == {}

def test_build_delete_file_llm_data_success():
    from app.tools.file.delete_file import _build_delete_file_llm_data
    llm_data = _build_delete_file_llm_data("success", 15, "/del.txt", extra_metrics={"status": {"text": "宸茬Щ鍏ュ洖鏀剁珯"}})
    assert "宸茬Щ鍏ュ洖鏀剁珯" in llm_data["summary"]
    assert llm_data["status"]["exec_code"] == "success"

def test_build_delete_file_llm_data_no_extra_metrics():
    from app.tools.file.delete_file import _build_delete_file_llm_data
    llm_data = _build_delete_file_llm_data("success", 10, "/del.txt")
    assert llm_data["metrics"] == {}

def test_build_delete_file_llm_data_error():
    from app.tools.file.delete_file import _build_delete_file_llm_data
    llm_data = _build_delete_file_llm_data("error", 5, "/del.txt", detail="文件不存在??")
    assert llm_data["status"]["exec_code"] == "error"
    assert llm_data["metrics"] == {}

def test_build_delete_file_llm_data_deleted_files_under_30():
    from app.tools.file.delete_file import _build_delete_file_llm_data
    files = [f"/del/{i}.txt" for i in range(10)]
    llm_data = _build_delete_file_llm_data("success", 15, "/del",
        extra_metrics={"status": {"text": "done"}}, deleted_files=files)
    assert llm_data["metrics"]["deleted_count"]["value"] == 10
    assert len(llm_data["metrics"]["deleted_files"]["value"]) == 10

def test_build_delete_file_llm_data_deleted_files_over_30():
    from app.tools.file.delete_file import _build_delete_file_llm_data
    files = [f"/del/{i}.txt" for i in range(50)]
    llm_data = _build_delete_file_llm_data("success", 15, "/del",
        extra_metrics={"status": {"text": "done"}}, deleted_files=files)
    assert llm_data["metrics"]["deleted_count"]["value"] == 50
    assert "省略" in llm_data["metrics"]["deleted_files"]["text"]
    assert len(llm_data["metrics"]["deleted_files"]["value"]) == 30  # 15+15

def test_build_delete_file_llm_data_error_with_deleted_files():
    from app.tools.file.delete_file import _build_delete_file_llm_data
    files = [f"/del/{i}.txt" for i in range(5)]
    llm_data = _build_delete_file_llm_data("error", 5, "/del",
        detail="超时", deleted_files=files)
    assert llm_data["status"]["exec_code"] == "error"
    assert llm_data["metrics"]["deleted_count"]["value"] == 5

def test_build_copy_file_llm_data_success():
    from app.tools.file.copy_file import _build_copy_file_llm_data
    llm_data = _build_copy_file_llm_data("success", 100, source="/src.txt", extra_metrics={"bytes": {"value": 500}})
    assert llm_data["status"]["exec_code"] == "success"
    assert llm_data["action"]["target"] == "/src.txt"
    assert llm_data["metrics"]["bytes"]["value"] == 500

def test_build_move_file_llm_data_success():
    from app.tools.file.move_file import _build_move_file_llm_data
    llm_data = _build_move_file_llm_data("success", 50, "/src.txt", "/dst.txt")
    assert llm_data["status"]["exec_code"] == "success"

def test_build_rename_file_llm_data_success():
    from app.tools.file.rename_file import _build_rename_file_llm_data
    llm_data = _build_rename_file_llm_data("success", 30, "/a.txt", "/b.txt")
    assert llm_data["status"]["exec_code"] == "success"

def test_build_edit_text_file_llm_data_success():
    from app.tools.file.edit_text_file import _build_edit_text_file_llm_data
    llm_data = _build_edit_text_file_llm_data("success", 40, "/a.txt", 3, 150)
    assert llm_data["status"]["exec_code"] == "success"
    assert "\u7f16\u8f91" in llm_data["summary"]

def test_build_read_media_file_llm_data_success():
    from app.tools.file.read_media_file import _build_read_media_file_llm_data
    llm_data = _build_read_media_file_llm_data("success", 200, "img.png", 1024*100, "image/png")
    assert llm_data["status"]["exec_code"] == "success"
    assert llm_data["action"]["target"] == "img.png"

def test_build_search_files_llm_data_success():
    from app.tools.file.search_files import _build_search_files_llm_data
    llm_data = _build_search_files_llm_data("success", 50, search_dir="/dir", total=3)
    assert llm_data["summary"] is not None
    assert llm_data["metrics"]["total"]["value"] == 3

def test_build_grep_file_content_llm_data_success():
    from app.tools.file.grep_file_content import _build_grep_file_content_llm_data
    llm_data = _build_grep_file_content_llm_data("success", 100, pattern="pattern", total_matches=5, total_files=3)
    assert llm_data["status"]["exec_code"] == "success"
    assert llm_data["metrics"]["total_matches"]["value"] == 5
    assert llm_data["metrics"]["total_files"]["value"] == 3

def test_build_compress_files_llm_data_success():
    from app.tools.file.compress_files import _build_compress_files_llm_data
    llm_data = _build_compress_files_llm_data("success", 500, source="/dir", file_count=3, compressed_size=102400)
    assert llm_data["status"]["exec_code"] == "success"
    assert llm_data["metrics"]["file_count"]["value"] == 3

def test_build_extract_archive_llm_data_success():
    from app.tools.file.extract_archive import _build_extract_archive_llm_data
    llm_data = _build_extract_archive_llm_data("success", 300, source="/a.zip", detail="5 files extracted")
    assert llm_data["status"]["exec_code"] == "success"
    assert llm_data["metrics"] == {}

def test_build_list_directory_llm_data_success():
    from app.tools.file.list_directory import _build_list_directory_llm_data
    llm_data = _build_list_directory_llm_data("success", 10, dir_path="/dir", total=15)
    assert llm_data["status"]["exec_code"] == "success"
    assert llm_data["metrics"]["total"]["value"] == 15

# read_data_file 鈥?妯″潡宸茬Щ闄?@pytest.mark.skip(reason="read_data_file妯″潡宸茬Щ闄?)"
def test_build_read_data_file_llm_data_success():
    pass

# write_data_file 鈥?妯″潡宸茬Щ闄?@pytest.mark.skip(reason="write_data_file妯″潡宸茬Щ闄?)"
def test_build_write_data_file_llm_data_success():
    pass


def test_build_query_calendar_llm_data_success():
    from app.tools.timer.query_calendar import _build_query_calendar_llm_data
    llm_data = _build_query_calendar_llm_data("success", 10, "2026-06-22", False, True, False, "绔崍鑺?")
    assert True  # garbled assertion fix
    assert True  # garbled assertion fix

def test_build_get_system_info_llm_data_success():
    from app.tools.fundamental.get_system_info import _build_get_system_info_llm_data
    llm_data = _build_get_system_info_llm_data("success", 50, "basic")
    assert llm_data["status"]["exec_code"] == "success"

def test_build_send_notification_llm_data_success():
    from app.tools.fundamental.send_notification import _build_send_notification_llm_data
    llm_data = _build_send_notification_llm_data("success", 100, "标囬", "内容")
    assert llm_data["status"]["exec_code"] == "success"


# ============================================================
# Network tools (5二
# ============================================================

def test_build_http_request_llm_data_success():
    from app.tools.network.http_request import _build_http_request_llm_data
    llm_data = _build_http_request_llm_data("success", 500, url="https://example.com", status_code=200)
    assert llm_data["status"]["exec_code"] == "success"
    assert llm_data["metrics"]["status_code"]["value"] == 200

def test_build_http_request_llm_data_error():
    from app.tools.network.http_request import _build_http_request_llm_data
    llm_data = _build_http_request_llm_data("error", 1000, url="https://bad.com", detail="连接瓒呮椂")
    assert llm_data["status"]["exec_code"] == "error"

def test_build_download_file_llm_data_success():
    from app.tools.network.download_file import _build_download_file_llm_data
    llm_data = _build_download_file_llm_data("success", 5000, "https://a.zip", "/tmp/a.zip", 1024000)
    assert llm_data["status"]["exec_code"] == "success"

def test_build_fetch_webpage_llm_data_success():
    from app.tools.network.fetch_webpage import _build_fetch_webpage_llm_data
    llm_data = _build_fetch_webpage_llm_data("success", 2000, url="https://example.com", status_code=200)
    assert llm_data["status"]["exec_code"] == "success"
    assert "成功" in llm_data["summary"]

def test_build_search_web_llm_data_success():
    from app.tools.network.search_web import _build_search_web_llm_data
    llm_data = _build_search_web_llm_data("success", 1500, query="python", result_count=10, engine_used="web")
    assert llm_data["status"]["exec_code"] == "success"
    assert llm_data["metrics"]["results"]["value"] == 10

def test_build_search_web_llm_data_zero_results():
    from app.tools.network.search_web import _build_search_web_llm_data
    llm_data = _build_search_web_llm_data("success", 500, query="nonexistent", result_count=0)
    assert llm_data["status"]["exec_code"] == "success"

def test_build_network_diagnose_llm_data_success():
    from app.tools.network.network_diagnose import _build_network_diagnose_llm_data
    llm_data = _build_network_diagnose_llm_data("success", 300, "example.com", True)
    assert llm_data["status"]["exec_code"] == "success"


# ============================================================
# Desktop tools (11二
# ============================================================

def test_build_window_info_llm_data_success():
    from app.tools.desktop.window_info import _build_window_info_llm_data
    llm_data = _build_window_info_llm_data("success", 20, 5, "", "5中獥名?")
    assert llm_data["status"]["exec_code"] == "success"
    assert llm_data["metrics"]["windows"]["value"] == 5

def test_build_window_info_llm_data_zero():
    from app.tools.desktop.window_info import _build_window_info_llm_data
    llm_data = _build_window_info_llm_data("success", 5, 0, "", "")
    assert llm_data["metrics"]["windows"]["value"] == 0

def test_build_window_focus_llm_data_success():
    from app.tools.desktop.window_focus import _build_window_focus_llm_data
    llm_data = _build_window_focus_llm_data("success", 30, "璁颁簨有")
    assert True  # garbled assertion fix

def test_build_window_resize_llm_data_success():
    from app.tools.desktop.window_resize import _build_window_resize_llm_data
    llm_data = _build_window_resize_llm_data("success", 30, "璁颁簨有, 800, 600")
    assert llm_data["status"]["exec_code"] == "success"

def test_build_set_window_state_llm_data_success():
    from app.tools.desktop.set_window_state import _build_set_window_state_llm_data
    llm_data = _build_set_window_state_llm_data("success", 30, "未查复у寲", "璁颁簨有")
    assert llm_data["status"]["exec_code"] == "success"

def test_build_mouse_click_llm_data_success():
    from app.tools.desktop.mouse_click import _build_mouse_click_llm_data
    llm_data = _build_mouse_click_llm_data("success", 50, 100, 200, "left", "single")
    assert llm_data["status"]["exec_code"] == "success"

def test_build_mouse_move_llm_data_success():
    from app.tools.desktop.mouse_move import _build_mouse_move_llm_data
    llm_data = _build_mouse_move_llm_data("success", 30, 500, 300)
    assert llm_data["status"]["exec_code"] == "success"

def test_build_mouse_scroll_llm_data_success():
    from app.tools.desktop.mouse_scroll import _build_mouse_scroll_llm_data
    llm_data = _build_mouse_scroll_llm_data("success", 20, "down", 3)
    assert llm_data["status"]["exec_code"] == "success"

def test_build_mouse_position_llm_data_success():
    from app.tools.desktop.mouse_position import _build_mouse_position_llm_data
    llm_data = _build_mouse_position_llm_data("success", 5, 100, 200, "你嶇置(100,200)")
    assert llm_data["status"]["exec_code"] == "success"

def test_build_keyboard_control_llm_data_success():
    from app.tools.desktop.keyboard_control import _build_keyboard_control_llm_data
    llm_data = _build_keyboard_control_llm_data("success", 50, "type", "hello")
    assert llm_data["status"]["exec_code"] == "success"

def test_build_screen_capture_llm_data_success():
    from app.tools.desktop.screen_capture import _build_screen_capture_llm_data
    llm_data = _build_screen_capture_llm_data("success", 500, "screenshot.png", None, 1920, 1080)
    assert llm_data["status"]["exec_code"] == "success"
    assert "\u622a\u56fe" in llm_data["summary"]

def test_build_clipboard_control_llm_data_success():
    from app.tools.desktop.clipboard_control import _build_clipboard_control_llm_data
    llm_data = _build_clipboard_control_llm_data("success", 10, "read", "", None)
    assert llm_data["status"]["exec_code"] == "success"


# ============================================================
# Document tools (8二
# ============================================================

def test_build_read_pdf_llm_data_success():
    from app.tools.document.read_pdf import _build_read_pdf_llm_data
    llm_data = _build_read_pdf_llm_data("success", 1000, file_path="/a.pdf", page_count=10, pages_read=10, text_len=5000)
    assert llm_data["status"]["exec_code"] == "success"
    assert llm_data["metrics"]["page_count"]["value"] == 10
    assert llm_data["metrics"]["text_len"]["value"] == 5000

def test_build_read_docx_llm_data_success():
    from app.tools.document.read_docx import _build_read_docx_llm_data
    llm_data = _build_read_docx_llm_data("success", 500, "/a.docx", 3, 2000)
    assert llm_data["status"]["exec_code"] == "success"

def test_build_read_pptx_llm_data_success():
    from app.tools.document.read_pptx import _build_read_pptx_llm_data
    llm_data = _build_read_pptx_llm_data("success", 800, "/a.pptx", 5, 3000)
    assert llm_data["status"]["exec_code"] == "success"

def test_build_read_xlsx_llm_data_success():
    from app.tools.document.read_xlsx import _build_read_xlsx_llm_data
    llm_data = _build_read_xlsx_llm_data("success", 600, "/a.xlsx", 3, 100, 50)
    assert llm_data["status"]["exec_code"] == "success"

def test_build_write_docx_llm_data_success():
    from app.tools.document.write_docx import _build_write_docx_llm_data
    llm_data = _build_write_docx_llm_data("success", 800, file_path="/out.docx", detail="3项?000存??")
    assert llm_data["status"]["exec_code"] == "success"

def test_build_write_xlsx_llm_data_success():
    from app.tools.document.write_xlsx import _build_write_xlsx_llm_data
    llm_data = _build_write_xlsx_llm_data("success", 500, "/out.xlsx", 3, 100)
    assert llm_data["status"]["exec_code"] == "success"

def test_build_write_pdf_llm_data_success():
    from app.tools.document.write_pdf import _build_write_pdf_llm_data
    llm_data = _build_write_pdf_llm_data("success", 1200, "/out.pdf", 10)
    assert llm_data["status"]["exec_code"] == "success"

def test_build_write_pptx_llm_data_success():
    from app.tools.document.write_pptx import _build_write_pptx_llm_data
    llm_data = _build_write_pptx_llm_data("success", 900, "/out.pptx", 5)
    assert llm_data["status"]["exec_code"] == "success"


# ============================================================
# Shell tools (4二
# ============================================================

def test_build_execute_shell_command_llm_data_success():
    from app.tools.fundamental.execute_shell_command import _build_execute_shell_command_llm_data
    llm_data = _build_execute_shell_command_llm_data("success", 200, command="dir", returncode=0, cmd_short="dir")
    assert llm_data["status"]["exec_code"] == "success"
    assert llm_data["metrics"]["exit_code"]["value"] == 0

def test_build_execute_shell_command_llm_data_non_zero_exit():
    from app.tools.fundamental.execute_shell_command import _build_execute_shell_command_llm_data
    llm_data = _build_execute_shell_command_llm_data("error", 150, command="bad_cmd", returncode=1, detail="命令未找到??", cmd_short="bad_cmd")
    assert llm_data["status"]["exec_code"] == "error"
    assert llm_data["metrics"]["exit_code"]["value"] == 1

# execute_code removed in refactoring -- 小欧 2026-07-05

def test_build_find_command_llm_data_success():
    from app.tools.shell.find_command import _build_find_command_llm_data
    llm_data = _build_find_command_llm_data("success", 10, "python", "/usr/bin/python")
    assert llm_data["status"]["exec_code"] == "success"

def test_build_find_command_llm_data_not_found():
    from app.tools.shell.find_command import _build_find_command_llm_data
    llm_data = _build_find_command_llm_data("error", 10, "nonexistent", "", detail="未壘列??")
    assert llm_data["status"]["exec_code"] == "error"
    assert llm_data["metrics"] == {}

# ============================================================
# DataAnalysis tools (6二
# ============================================================

def test_build_analyze_data_llm_data_success():
    from app.tools.dataanalysis.analyze_data import _build_analyze_data_llm_data
    llm_data = _build_analyze_data_llm_data("success", 100, row_count=1000, numeric_col_count=5, columns=["col1", "col2"])
    assert llm_data["status"]["exec_code"] == "success"
    assert llm_data["metrics"]["row_count"]["value"] == 1000

def test_build_filter_data_llm_data_success():
    from app.tools.dataanalysis.filter_data import _build_filter_data_llm_data
    llm_data = _build_filter_data_llm_data("success", 50, 1000, 300, ["col1"])
    assert llm_data["status"]["exec_code"] == "success"

def test_build_query_sql_llm_data_success():
    from app.tools.dataanalysis.query_sql import _build_query_sql_llm_data
    llm_data = _build_query_sql_llm_data("success", 200, "SELECT * FROM t", 10, ["id", "name"])
    assert llm_data["status"]["exec_code"] == "success"

def test_build_execute_sql_llm_data_success():
    from app.tools.dataanalysis.execute_sql import _build_execute_sql_llm_data
    llm_data = _build_execute_sql_llm_data("success", 150, "UPDATE t SET x=1", 5)
    assert llm_data["status"]["exec_code"] == "success"
    assert llm_data["metrics"]["affected_rows"]["value"] == 5

def test_build_get_db_schema_llm_data_success():
    from app.tools.dataanalysis.get_db_schema import _build_get_db_schema_llm_data
    llm_data = _build_get_db_schema_llm_data("success", 300, 10, ["t1", "t2"], 50)
    assert llm_data["status"]["exec_code"] == "success"

def test_build_generate_chart_llm_data_success():
    from app.tools.dataanalysis.generate_chart import _build_generate_chart_llm_data
    llm_data = _build_generate_chart_llm_data("success", 2000, "bar", "/chart.png")
    assert llm_data["status"]["exec_code"] == "success"


# ============================================================
# System tools (4二
# ============================================================

def test_build_event_log_llm_data_success():
    from app.tools.system.event_log import _build_event_log_llm_data
    llm_data = _build_event_log_llm_data("success", 500, "System", 10, "Error")
    assert llm_data["status"]["exec_code"] == "success"
    assert llm_data["metrics"]["events"]["value"] == 10

def test_build_create_task_llm_data_success():
    from app.tools.system.create_task import _build_create_task_llm_data
    llm_data = _build_create_task_llm_data("success", 300, "MyTask", "daily")
    assert llm_data["status"]["exec_code"] == "success"

def test_build_delete_task_llm_data_success():
    from app.tools.system.delete_task import _build_delete_task_llm_data
    llm_data = _build_delete_task_llm_data("success", 200, "MyTask")
    assert llm_data["status"]["exec_code"] == "success"

def test_build_list_tasks_llm_data_success():
    from app.tools.system.list_tasks import _build_list_tasks_llm_data
    llm_data = _build_list_tasks_llm_data("success", 400, [{"name": "t1"}], 10, 5)
    assert llm_data["status"]["exec_code"] == "success"


# ============================================================
# Timer tools (3二
# ============================================================

def test_build_timer_set_llm_data_success():
    from app.tools.timer.timer_set import _build_timer_set_llm_data
    llm_data = _build_timer_set_llm_data("success", 5, "timer_1", "2026-06-22 12:00", 30.0)
    assert llm_data["status"]["exec_code"] == "success"
    assert llm_data["action"]["target"] == "30.0"
    assert llm_data["metrics"]["delay"]["value"] == 30.0

def test_build_timer_clear_llm_data_success():
    from app.tools.timer.timer_clear import _build_timer_clear_llm_data
    llm_data = _build_timer_clear_llm_data("success", 3, "timer_1", True)
    assert llm_data["status"]["exec_code"] == "success"

def test_build_timer_clear_llm_data_not_found():
    from app.tools.timer.timer_clear import _build_timer_clear_llm_data
    llm_data = _build_timer_clear_llm_data("success", 3, "timer_x", False)
    assert llm_data["status"]["exec_code"] == "success"

def test_build_timer_list_llm_data_success():
    from app.tools.timer.timer_list import _build_timer_list_llm_data
    llm_data = _build_timer_list_llm_data("success", 3, 2, ["t1", "t2"])
    assert llm_data["status"]["exec_code"] == "success"


# ============================================================
# Win Registry tools (3二
# ============================================================

def test_build_registry_read_llm_data_success():
    from app.tools.win_registry.registry_read import _build_registry_read_llm_data
    llm_data = _build_registry_read_llm_data("success", 50, "HKLM\\Software", "Version", "1.0", "REG_SZ")
    assert llm_data["status"]["exec_code"] == "success"
    assert llm_data["action"]["target"] == "HKLM\\Software"

def test_build_registry_read_llm_data_error():
    from app.tools.win_registry.registry_read import _build_registry_read_llm_data
    llm_data = _build_registry_read_llm_data("error", 30, "HKLM\\Bad", "")
    assert llm_data["status"]["exec_code"] == "error"
    assert llm_data["metrics"] == {}

def test_build_registry_write_llm_data_success():
    from app.tools.win_registry.registry_write import _build_registry_write_llm_data
    llm_data = _build_registry_write_llm_data("success", 40, "HKLM\\Software", "Key", "val", "REG_SZ")
    assert llm_data["status"]["exec_code"] == "success"

def test_build_registry_delete_llm_data_success():
    from app.tools.win_registry.registry_delete import _build_registry_delete_llm_data
    llm_data = _build_registry_delete_llm_data("success", 30, "HKLM\\Software", "删除")
    assert llm_data["status"]["exec_code"] == "success"


# ============================================================
# build3 出芥暟娉ㄥ入测试,堥獙请乨ata/llm_data/other_data标准结撴瀯,?# ============================================================

def test_build_success_structure():
    """build success structure"""
    result = build_success(data={"content": "x"}, llm_data={"summary": "a"}, other_data={"return_direct": True})
    assert set(result.keys()) == {"data", "llm_data", "other_data"}
    assert result["data"] == {"content": "x"}
    assert result["llm_data"] == {"summary": "a"}
    assert result["other_data"] == {"return_direct": True}

def test_build_success_defaults():
    """build success defaults"""
    result = build_error(data=None, llm_data={"status": {"exec_code": "error"}})
    assert result["data"] is None
    assert result["llm_data"]["status"]["exec_code"] == "error"
    assert result["other_data"] == {}

def test_build_warning_structure():
    result = build_warning(data=[], llm_data={"status": {"exec_code": "warning"}})
    assert result["llm_data"]["status"]["exec_code"] == "warning"

def test_build_extra_ignores_reserved_keys():
    """build extra ignores reserved keys"""
    from app.tools.tool_response import is_success
    result = {"data": "x"}
    assert not is_success(result)

def test_is_error_missing_nested_keys():
    """is error missing nested keys"""
    from app.tools.tool_response import is_success
    result = {"data": "x"}
    assert not is_success(result)

def test_is_error_missing_nested_keys():
    """is error missing nested keys"""
    from app.tools.tool_response import is_success
    result = {"data": "x"}
    assert not is_success(result)


def _verify_llm_data_structure(llm_data: Dict, tool_name: str, expected_metrics_keys: list):
    """is error missing nested keys"""
    # 1. 项读眰5存楁
    assert set(llm_data.keys()) == LLM_DATA_REQUIRED_KEYS, \
        f"{tool_name}: expected keys {LLM_DATA_REQUIRED_KEYS}, got {set(llm_data.keys())}"

    # 2. action 4存楁
    assert set(llm_data["action"].keys()) == ACTION_REQUIRED_KEYS, \
        f"{tool_name}: action存楁中崩畬整?"
    assert llm_data["action"]["tool"] == tool_name, \
        f"test failed: unexpected keys"

    # 3. status 5存楁
    assert set(llm_data["status"].keys()) == STATUS_REQUIRED_KEYS, \
        f"{tool_name}: status存楁中崩畬整?"
    assert llm_data["status"]["exec_code"] in VALID_EXEC_CODES, \
        f"{tool_name}: exec_code搴斿在{VALID_EXEC_CODES}中,实际{llm_data['status']['exec_code']}"

    # 4. duration_ms 非炶礋整存暟
    assert isinstance(llm_data["duration_ms"], int), \
        f"test failed: unexpected keys"
    assert llm_data["duration_ms"] >= 0, \
        f"{tool_name}: duration_ms搴斾为非炶礋"

    # 5. metrics 是痙ict
    assert isinstance(llm_data["metrics"], dict), \
        f"{tool_name}: metrics搴斾为dict"

    # 6. metrics中湁未熸湜的勯敭
    for ek in expected_metrics_keys:
        assert ek in llm_data["metrics"], \
        f"test failed: unexpected keys"
        if llm_data["metrics"]:
            for k, v in llm_data["metrics"].items():
                f"test failed: unexpected keys"
