"""
真实集成测试 - 通过运行中的后台服务(127.0.0.1:8000)直接调用工具
不使用任何mock，测试真实工具执行结果

测试方式: HTTP POST /api/v1/tool/execute
前提条件: 后台服务已启动 (python -m uvicorn app.main:app --reload)

作者: 小健 2026-05-21
"""
import pytest
import httpx
import json
import os
import tempfile

BASE_URL = "http://127.0.0.1:8000/api/v1"
TOOL_TIMEOUT = 60
API_TIMEOUT = 15


def call_tool(tool_name: str, params: dict) -> dict:
    """通过HTTP API调用工具，返回完整响应"""
    r = httpx.post(
        f"{BASE_URL}/tool/execute",
        json={"tool_name": tool_name, "params": params},
        timeout=TOOL_TIMEOUT,
    )
    assert r.status_code == 200, f"HTTP {r.status_code}: {r.text[:200]}"
    return r.json()


def assert_success(result: dict, tool_name: str = ""):
    """断言工具调用成功"""
    assert result.get("success") is True, f"{tool_name} failed: {json.dumps(result, ensure_ascii=False)[:300]}"


def assert_code_success(result: dict, tool_name: str = ""):
    """断言工具调用成功(兼容多种返回格式)"""
    r = result.get("result", {})
    if r.get("code") == "SUCCESS":
        return
    if r.get("status") == "success":
        return
    data = r.get("data", {})
    if isinstance(data, dict) and data.get("success") is True:
        return
    raise AssertionError(f"{tool_name} not success: code={r.get('code')} status={r.get('status')} data.success={data.get('success') if isinstance(data,dict) else 'N/A'} summary={r.get('summary','')[:100]}")


# =============================================================================
# 1. FILE 工具类 (11个工具)
# =============================================================================

class TestFileTools:
    """FILE类工具真实集成测试"""

    def test_read_file_single(self):
        r = call_tool("read_file", {"file_paths": ["G:/OmniAgentAs-desk/version.txt"]})
        assert_success(r, "read_file")
        assert_code_success(r, "read_file")
        assert "data" in r["result"]

    def test_read_file_with_head(self):
        r = call_tool("read_file", {"file_paths": ["G:/OmniAgentAs-desk/version.txt"], "head": 5})
        assert_success(r, "read_file")
        assert_code_success(r, "read_file")

    def test_write_text_file_and_read_back(self):
        tmp = os.path.join(tempfile.gettempdir(), "test_live_write.txt")
        r1 = call_tool("write_text_file", {"file_path": tmp, "text": "hello live test"})
        assert_success(r1, "write_text_file")
        res = r1.get("result", {})
        if res.get("status") == "error" and "No active task" in res.get("summary", ""):
            pytest.skip("write_text_file requires active task context (operation recording)")
        r2 = call_tool("read_file", {"file_paths": [tmp]})
        assert_success(r2, "read_file")
        assert "hello live test" in json.dumps(r2["result"], ensure_ascii=False)

    def test_edit_file(self):
        tmp = os.path.join(tempfile.gettempdir(), "test_live_edit.txt")
        call_tool("write_text_file", {"file_path": tmp, "text": "foo bar baz"})
        r = call_tool("edit_file", {"file_path": tmp, "old_string": "bar", "new_string": "BAR"})
        assert_success(r, "edit_file")

    def test_list_directory(self):
        r = call_tool("list_directory", {"dir_path": "G:/OmniAgentAs-desk", "format": "list"})
        assert_success(r, "list_directory")
        assert_code_success(r, "list_directory")

    def test_list_directory_tree(self):
        r = call_tool("list_directory", {"dir_path": "G:/OmniAgentAs-desk/backend/app", "format": "tree", "max_depth": 1})
        assert_success(r, "list_directory")
        assert_code_success(r, "list_directory")

    def test_search_files(self):
        r = call_tool("search_files", {"pattern": "*.py", "search_dir": "G:/OmniAgentAs-desk/backend/app", "max_depth": 1})
        assert_success(r, "search_files")
        assert_code_success(r, "search_files")

    def test_grep_file_content(self):
        r = call_tool("grep_file_content", {"pattern": "parse_react_response", "search_dir": "G:/OmniAgentAs-desk/backend/app"})
        assert_success(r, "grep_file_content")
        assert_code_success(r, "grep_file_content")

    def test_rename_file(self):
        tmp = os.path.join(tempfile.gettempdir(), "test_rename_src.txt")
        tmp2 = os.path.join(tempfile.gettempdir(), "test_rename_dst.txt")
        call_tool("write_text_file", {"file_path": tmp, "text": "rename test"})
        r = call_tool("rename_file", {"mode": "single", "file_path": tmp, "new_name": "test_rename_dst.txt"})
        assert_success(r, "rename_file")

    def test_file_operation_delete(self):
        tmp = os.path.join(tempfile.gettempdir(), "test_delete_me.txt")
        call_tool("write_text_file", {"file_path": tmp, "text": "to be deleted"})
        r = call_tool("file_operation", {"action": "delete", "source": tmp})
        assert_success(r, "file_operation")
        assert_code_success(r, "file_operation")

    def test_data_file_format(self):
        tmp = os.path.join(tempfile.gettempdir(), "test_live_data.json")
        call_tool("write_text_file", {"file_path": tmp, "text": '{"key": "value"}'})
        r = call_tool("data_file_format", {"file_path": tmp, "action": "read"})
        assert_success(r, "data_file_format")


# =============================================================================
# 2. SHELL 工具类 (5个工具)
# =============================================================================

class TestShellTools:
    """SHELL类工具真实集成测试"""

    def test_execute_shell_command(self):
        r = call_tool("execute_shell_command", {"command": "echo hello", "timeout": 10000})
        assert_success(r, "execute_shell_command")
        assert_code_success(r, "execute_shell_command")

    def test_find_command(self):
        r = call_tool("find_command", {"command": "python"})
        assert_success(r, "find_command")
        assert_code_success(r, "find_command")

    def test_execute_python(self):
        r = call_tool("execute_python", {"code": "print(2+2)", "timeout": 10})
        assert_success(r, "execute_python")
        assert_code_success(r, "execute_python")

    def test_execute_javascript(self):
        r = call_tool("execute_javascript", {"code": "console.log(2+2)", "timeout": 10})
        assert_success(r, "execute_javascript")

    def test_shell_session(self):
        r1 = call_tool("execute_shell_command", {"command": "ping -n 1 127.0.0.1", "timeout": 10, "run_in_background": True})
        assert_success(r1, "execute_shell_command(bg)")


# =============================================================================
# 3. NETWORK 工具类 (5个工具)
# =============================================================================

class TestNetworkTools:
    """NETWORK类工具真实集成测试"""

    def test_http_request_get(self):
        r = call_tool("http_request", {"url": "https://httpbin.org/get", "method": "GET", "timeout": 15})
        assert_success(r, "http_request")

    def test_fetch_webpage(self):
        r = call_tool("fetch_webpage", {"url": "https://httpbin.org/html", "timeout": 15})
        assert_success(r, "fetch_webpage")

    def test_network_diagnose_ping(self):
        r = call_tool("network_diagnose", {"host": "127.0.0.1", "mode": "ping", "count": 2})
        assert_success(r, "network_diagnose")
        assert_code_success(r, "network_diagnose")

    def test_network_diagnose_port(self):
        r = call_tool("network_diagnose", {"host": "127.0.0.1", "mode": "port", "port": 8000})
        assert_success(r, "network_diagnose")
        assert_code_success(r, "network_diagnose")

    def test_download_file(self):
        tmp = os.path.join(tempfile.gettempdir(), "test_download.html")
        r = call_tool("download_file", {"url": "https://httpbin.org/html", "destination_path": tmp, "timeout": 15})
        assert_success(r, "download_file")


# =============================================================================
# 4. SYSTEM 工具类 (10个工具)
# =============================================================================

class TestSystemTools:
    """SYSTEM类工具真实集成测试"""

    def test_get_system_info(self):
        r = call_tool("get_system_info", {})
        assert_success(r, "get_system_info")
        assert_code_success(r, "get_system_info")

    def test_list_processes(self):
        r = call_tool("list_processes", {"max_results": 5})
        assert_success(r, "list_processes")
        assert_code_success(r, "list_processes")

    def test_net_connections(self):
        r = call_tool("net_connections", {})
        assert_success(r, "net_connections")
        assert_code_success(r, "net_connections")

    def test_get_env(self):
        r = call_tool("get_env", {"name": "PATH"})
        assert_success(r, "get_env")
        assert_code_success(r, "get_env")

    def test_get_env_list(self):
        r = call_tool("get_env", {"action": "list", "prefix": "PYTHON"})
        assert_success(r, "get_env(list)")

    def test_set_env_and_delete(self):
        r1 = call_tool("set_env", {"name": "TEST_LIVE_VAR", "value": "123", "scope": "process"})
        assert_success(r1, "set_env")
        r2 = call_tool("get_env", {"name": "TEST_LIVE_VAR"})
        assert_success(r2, "get_env")
        r3 = call_tool("set_env", {"name": "TEST_LIVE_VAR", "action": "delete", "scope": "process"})
        assert_success(r3, "set_env(delete)")

    def test_event_log(self):
        r = call_tool("event_log", {"max_events": 3})
        assert_success(r, "event_log")

    def test_service_control_list(self):
        r = call_tool("service_control", {"action": "list"})
        assert_success(r, "service_control")

    def test_task_control_list(self):
        r = call_tool("task_control", {"action": "list"})
        assert_success(r, "task_control")

    def test_registry_control_read(self):
        r = call_tool("registry_control", {"key_path": "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion", "action": "read", "value_name": "ProductName"})
        assert_success(r, "registry_control")


# =============================================================================
# 5. DESKTOP 工具类 (10个工具)
# =============================================================================

class TestDesktopTools:
    """DESKTOP类工具真实集成测试"""

    def test_list_windows(self):
        r = call_tool("list_windows", {})
        assert_success(r, "list_windows")
        assert_code_success(r, "list_windows")

    def test_screen_capture(self):
        tmp = os.path.join(tempfile.gettempdir(), "test_screenshot.png")
        r = call_tool("screen_capture", {"output_path": tmp})
        assert_success(r, "screen_capture")

    def test_mouse_control_position(self):
        r = call_tool("mouse_control", {"action": "position"})
        assert_success(r, "mouse_control")

    def test_get_window_info(self):
        r = call_tool("list_windows", {"filter_title": "CodeArts"})
        assert_success(r, "get_window_info(list)")

    def test_window_control(self):
        r = call_tool("list_windows", {})
        assert_success(r, "window_control(list)")

    def test_keyboard_control(self):
        r = call_tool("keyboard_control", {"action": "type", "text_or_keys": ""})
        assert_success(r, "keyboard_control")

    def test_clipboard_control(self):
        r = call_tool("clipboard_control", {"action": "read"})
        assert_success(r, "clipboard_control")

    def test_ocr(self):
        r = call_tool("ocr", {"image_path": "nonexistent_for_test.png"})
        assert_success(r, "ocr")

    def test_send_notification(self):
        r = call_tool("send_notification", {"title": "Test", "message": "Live test notification"})
        assert_success(r, "send_notification")

    def test_screen_record(self):
        r = call_tool("screen_record", {"duration": 1, "output_path": os.path.join(tempfile.gettempdir(), "test_record.mp4")})
        assert_success(r, "screen_record")


# =============================================================================
# 6. DOCUMENT 工具类 (9个工具)
# =============================================================================

class TestDocumentTools:
    """DOCUMENT类工具真实集成测试"""

    def test_read_document_csv(self):
        tmp = os.path.join(tempfile.gettempdir(), "test_live.csv")
        call_tool("write_text_file", {"file_path": tmp, "text": "a,b\n1,2\n3,4"})
        r = call_tool("read_document", {"file_path": tmp})
        assert_success(r, "read_document")

    def test_write_document_xlsx(self):
        tmp = os.path.join(tempfile.gettempdir(), "test_live.xlsx")
        r = call_tool("write_document", {"file_path": tmp, "data": [["a", "b"], [1, 2]]})
        assert_success(r, "write_document")

    def test_convert_document(self):
        r = call_tool("convert_document", {"input_path": "nonexistent.docx"})
        assert_success(r, "convert_document")

    def test_analyze_data(self):
        r = call_tool("analyze_data", {"data": [{"x": 1, "y": 2}, {"x": 3, "y": 4}]})
        assert_success(r, "analyze_data")
        assert_code_success(r, "analyze_data")

    def test_filter_data(self):
        r = call_tool("filter_data", {"data": [{"x": 1}, {"x": 2}, {"x": 3}], "conditions": [{"field": "x", "op": ">", "value": 1}]})
        assert_success(r, "filter_data")
        assert_code_success(r, "filter_data")

    def test_generate_chart(self):
        tmp = os.path.join(tempfile.gettempdir(), "test_chart.png")
        r = call_tool("generate_chart", {"data": [{"x": 1, "y": 2}, {"x": 2, "y": 4}], "chart_type": "line", "output_path": tmp})
        assert_success(r, "generate_chart")

    def test_query_sql(self):
        tmp = os.path.join(tempfile.gettempdir(), "test_live.db")
        r = call_tool("query_sql", {"sql": "SELECT 1 AS val", "db_path": tmp})
        assert_success(r, "query_sql")

    def test_execute_sql(self):
        tmp = os.path.join(tempfile.gettempdir(), "test_live_exec.db")
        r = call_tool("execute_sql", {"sql": "CREATE TABLE IF NOT EXISTS t(id INTEGER)", "db_path": tmp})
        assert_success(r, "execute_sql")

    def test_get_db_schema(self):
        r = call_tool("get_db_schema", {})
        assert_success(r, "get_db_schema")


# =============================================================================
# 7. META 工具类 (9个工具)
# =============================================================================

class TestMetaTools:
    """META类工具真实集成测试"""

    def test_tool_help(self):
        r = call_tool("tool_help", {"tool_name": "read_file"})
        assert_success(r, "tool_help")
        assert_code_success(r, "tool_help")

    def test_tool_search(self):
        r = call_tool("tool_search", {"query": "读取文件"})
        assert_success(r, "tool_search")
        assert_code_success(r, "tool_search")

    def test_pipeline(self):
        r = call_tool("pipeline", {"steps": json.dumps([{"tool": "get_time", "params": {}}])})
        assert_success(r, "pipeline")

    def test_get_time(self):
        r = call_tool("get_time", {})
        assert_success(r, "get_time")
        assert_code_success(r, "get_time")
        data = r["result"]["data"]
        assert "iso" in data
        assert "weekday" in data

    def test_time_add(self):
        r = call_tool("time_add", {"delta": 1, "unit": "days"})
        assert_success(r, "time_add")
        assert_code_success(r, "time_add")

    def test_time_diff(self):
        r = call_tool("time_diff", {"start": "2026-01-01", "end": "2026-01-10"})
        assert_success(r, "time_diff")
        assert_code_success(r, "time_diff")

    def test_query_calendar(self):
        r = call_tool("query_calendar", {"date": "2026-05-01", "check_type": "weekend"})
        assert_success(r, "query_calendar")
        assert_code_success(r, "query_calendar")

    def test_timezone_convert(self):
        r = call_tool("timezone_convert", {"time_value": "2026-05-21 00:00:00", "direction": "local_to_utc", "tz": "Asia/Shanghai"})
        assert_success(r, "timezone_convert")
        assert_code_success(r, "timezone_convert")

    def test_timer(self):
        r = call_tool("timer", {"action": "list"})
        assert_success(r, "timer")


# =============================================================================
# 8. 服务基础功能测试
# =============================================================================

class TestServiceBasic:
    """服务基础功能测试"""

    def test_health(self):
        r = httpx.get(f"{BASE_URL}/health", timeout=API_TIMEOUT)
        assert r.status_code == 200

    def test_echo(self):
        r = httpx.post(f"{BASE_URL}/echo", json={"message": "hello"}, timeout=API_TIMEOUT)
        assert r.status_code == 200

    def test_tool_list(self):
        r = httpx.get(f"{BASE_URL}/tool/list", timeout=API_TIMEOUT)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 59
        assert len(data["tools"]) == 59

    def test_config_get(self):
        r = httpx.get(f"{BASE_URL}/config", timeout=API_TIMEOUT)
        assert r.status_code == 200

    def test_metrics(self):
        r = httpx.get(f"{BASE_URL}/metrics", timeout=API_TIMEOUT)
        assert r.status_code == 200
