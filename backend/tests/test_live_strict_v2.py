"""
严苛深度集成测试 - 专为发现问题而写
每个断言都验证具体值，不是"不报错"

作者: 小健 2026-05-21
"""
import pytest
import httpx
import json
import os
import tempfile
import sys
from app.services.agent.llm_response_parser import parse_react_response
from app.services.agent.llm_response_parser._utils import _normalize_result_to_str

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

BASE = "http://127.0.0.1:8000/api/v1"


def call(tool, params, timeout=60):
    r = httpx.post(f"{BASE}/tool/execute", json={"tool_name": tool, "params": params}, timeout=timeout)
    assert r.status_code == 200
    return r.json()


def res(tool, params, timeout=60):
    d = call(tool, params, timeout)
    assert d["success"] is True, f"{tool} failed: {d.get('error','')}"
    return d["result"]


def data(tool, params, timeout=60):
    return res(tool, params, timeout).get("data", {})


# =============================================================================
# 1. read_file 严苛验证
# =============================================================================

class TestReadFileStrict:
    F = os.path.join(tempfile.gettempdir(), "strict.txt")

    @classmethod
    def setup_class(cls):
        with open(cls.F, "w", encoding="utf-8") as f:
            f.write("L1\nL2\nL3\nL4\nL5\n")

    def test_content_exact(self):
        d = data("read_file", {"file_paths": [self.F]})
        assert d["content"] == "L1\nL2\nL3\nL4\nL5\n", "content must be exact"

    def test_head_2(self):
        d = data("read_file", {"file_paths": [self.F], "head": 2})
        assert d["content"] == "L1\nL2\n" and d["line_count"] == 2

    def test_tail_1(self):
        d = data("read_file", {"file_paths": [self.F], "tail": 1})
        assert d["content"] == "L5\n"

    def test_offset_limit(self):
        d = data("read_file", {"file_paths": [self.F], "offset": 2, "limit": 2})
        assert d["content"] == "L2\nL3\n"

    def test_head_exceeds_total_capped(self):
        d = data("read_file", {"file_paths": [self.F], "head": 999})
        assert d["line_count"] == 5, "head>total must cap at total lines"

    def test_offset_exceeds_total_empty(self):
        d = data("read_file", {"file_paths": [self.F], "offset": 999, "limit": 5})
        assert d["content"] == "", "offset>total must return empty"

    def test_empty_file(self):
        ef = os.path.join(tempfile.gettempdir(), "empty_strict.txt")
        with open(ef, "w") as f:
            pass
        d = data("read_file", {"file_paths": [ef]})
        assert d["line_count"] == 0 and d["content"] == ""

    def test_chinese_content(self):
        cf = os.path.join(tempfile.gettempdir(), "cn_strict.txt")
        with open(cf, "w", encoding="utf-8") as f:
            f.write("中文第一行\n中文第二行\n")
        d = data("read_file", {"file_paths": [cf]})
        assert "中文第一行" in d["content"] and d["line_count"] == 2

    def test_nonexistent_returns_error(self):
        r = res("read_file", {"file_paths": ["C:/no_such_file_abc999.txt"]})
        assert r["data"]["success"] is False

    def test_batch_2_files(self):
        d = data("read_file", {"file_paths": [self.F, "G:/OmniAgentAs-desk/version.txt"], "head": 1})
        assert d["success"] is True and d["success_count"] == 2 and d["failed_count"] == 0


# =============================================================================
# 2. Shell 严苛验证
# =============================================================================

class TestShellStrict:
    def test_echo_output_exact(self):
        d = data("execute_shell_command", {"command": "echo VERIFY_123", "timeout": 10000})
        assert "VERIFY_123" in d["stdout"]
        assert d["returncode"] == 0

    def test_exit_code_42(self):
        d = data("execute_shell_command", {"command": "exit 42", "timeout": 10000})
        assert d["returncode"] == 42

    def test_stderr_captured(self):
        d = data("execute_shell_command", {"command": "python -c \"import sys; sys.stderr.write('ERR_X\\n')\"", "timeout": 10000})
        assert "ERR_X" in d.get("stderr", "")

    def test_find_python_exists(self):
        d = data("find_command", {"command": "python"})
        assert d["available"] is True and "python" in d["path"].lower()

    def test_find_nonexistent(self):
        d = data("find_command", {"command": "no_such_cmd_xyz_999"})
        assert d["available"] is False

    def test_python_output_exact(self):
        d = data("execute_python", {"code": "print(6*7)", "timeout": 10000})
        assert "42" in d["stdout"] and d["returncode"] == 0

    def test_python_exception_nonzero_exit(self):
        d = data("execute_python", {"code": "raise ValueError('test_err')", "timeout": 10000})
        assert d["returncode"] != 0
        assert "test_err" in d.get("stderr", "")


# =============================================================================
# 3. 时间工具 严苛验证
# =============================================================================

class TestTimeStrict:
    def test_get_time_iso_has_year(self):
        d = data("get_time", {})
        assert "2026" in d["iso"] and isinstance(d["timestamp"], (int, float))

    def test_time_add_1_day(self):
        d = data("time_add", {"delta": 1, "unit": "days", "start": "2026-01-01"})
        assert "2026-01-02" in d["result_time"]

    def test_time_add_neg_30_days(self):
        d = data("time_add", {"delta": -30, "unit": "days", "start": "2026-03-01"})
        assert "2026-01-30" in d["result_time"]

    def test_time_diff_9_days(self):
        d = data("time_diff", {"start": "2026-06-01", "end": "2026-06-10"})
        assert d["days"] == 9.0

    def test_time_diff_same_day_zero(self):
        d = data("time_diff", {"start": "2026-01-01", "end": "2026-01-01"})
        assert d["days"] == 0.0

    def test_time_diff_signed_available(self):
        r = res("time_diff", {"start": "2026-12-31", "end": "2026-01-01"})
        d = r["data"]
        assert "diff_seconds_signed" in d, "time_diff must provide diff_seconds_signed for negative diffs"
        assert d["diff_seconds_signed"] < 0, "start>end must give negative signed diff"

    def test_query_calendar_weekend_true(self):
        d = data("query_calendar", {"date": "2026-05-24", "check_type": "weekend"})
        assert d.get("is_weekend") is True

    def test_query_calendar_weekend_false(self):
        d = data("query_calendar", {"date": "2026-05-25", "check_type": "weekend"})
        assert d.get("is_weekend") is False

    def test_invalid_date_error(self):
        r = res("query_calendar", {"date": "2026-13-45", "check_type": "weekend"})
        assert r.get("code", "").startswith("ERR")


# =============================================================================
# 4. 系统工具 严苛验证
# =============================================================================

class TestSystemStrict:
    def test_platform_windows(self):
        d = data("get_system_info", {})
        assert d["basic"]["platform"] == "Windows"

    def test_cpu_cores_positive(self):
        d = data("get_system_info", {})
        assert d["cpu"]["physical_cores"] > 0

    def test_memory_percent_0_to_100(self):
        d = data("get_system_info", {})
        assert 0 < d["memory"]["percent"] <= 100

    def test_python_process_exists(self):
        d = data("list_processes", {"filter_name": "python", "max_results": 3})
        assert len(d["processes"]) > 0
        assert d["processes"][0]["pid"] > 0

    def test_port_8000_has_connections(self):
        d = data("net_connections", {"filter_port": 8000})
        assert len(d["connections"]) > 0

    def test_env_path_exists(self):
        d = data("get_env", {"name": "PATH"})
        assert d["exists"] is True and len(d["value"]) > 0

    def test_env_nonexistent(self):
        d = data("get_env", {"name": "NONEXISTENT_VAR_XYZ"})
        assert d["exists"] is False


# =============================================================================
# 5. 网络 严苛验证
# =============================================================================

class TestNetworkStrict:
    def test_ping_localhost_reachable(self):
        d = data("network_diagnose", {"host": "127.0.0.1", "mode": "ping", "count": 2})
        assert d["is_reachable"] is True and d["packets_lost"] == 0

    def test_port_8000_open(self):
        d = data("network_diagnose", {"host": "127.0.0.1", "mode": "port", "port": 8000})
        assert d["is_open"] is True

    def test_port_9999_closed(self):
        d = data("network_diagnose", {"host": "127.0.0.1", "mode": "port", "port": 9999})
        assert d["is_open"] is False


# =============================================================================
# 6. 搜索 严苛验证
# =============================================================================

class TestSearchStrict:
    def test_search_finds_main_py(self):
        d = data("search_files", {"pattern": "*.py", "search_dir": "G:/OmniAgentAs-desk/backend/app", "max_depth": 1})
        assert "main.py" in [m["name"] for m in d["matches"]]

    def test_search_type_filter(self):
        d = data("search_files", {"pattern": "*", "search_dir": "G:/OmniAgentAs-desk/backend/app", "type": "file", "max_depth": 1})
        assert all(m["type"] == "file" for m in d["matches"])

    def test_search_empty_pattern_error(self):
        r = res("search_files", {"pattern": "", "search_dir": "G:/OmniAgentAs-desk/backend/app"})
        assert r["data"]["success"] is False

    def test_grep_finds_base_agent(self):
        d = data("grep_file_content", {"pattern": "class BaseAgent", "search_dir": "G:/OmniAgentAs-desk/backend/app/services/agent", "output_mode": "files_with_matches"})
        assert len(d["matches"]) >= 1 and "base_react.py" in d["matches"][0]["file"]

    def test_grep_ignore_case_works(self):
        d = data("grep_file_content", {"pattern": "FastAPI", "search_dir": "G:/OmniAgentAs-desk/backend/app", "ignore_case": True, "output_mode": "files_with_matches"})
        assert len(d["matches"]) > 0


# =============================================================================
# 7. META 严苛验证
# =============================================================================

class TestMetaStrict:
    def test_tool_help_name_correct(self):
        d = data("tool_help", {"tool_name": "read_file"})
        assert d["name"] == "read_file" and "description" in d and "params" in d

    def test_tool_help_5_tools(self):
        for t in ["read_file", "execute_shell_command", "get_time", "get_system_info", "search_web"]:
            d = data("tool_help", {"tool_name": t})
            assert d["name"] == t

    def test_tool_help_nonexistent_error(self):
        r = res("tool_help", {"tool_name": "nonexistent_xyz"})
        assert r.get("code", "").startswith("ERR")

    def test_tool_search_finds_file(self):
        d = data("tool_search", {"query": "file"})
        tools = d.get("tools", d.get("matches", []))
        assert len(tools) > 0

    def test_tool_search_chinese(self):
        d = data("tool_search", {"query": "文件"})
        tools = d.get("tools", d.get("matches", []))
        assert len(tools) > 0


# =============================================================================
# 8. 解析器 严苛验证（Python层）
# =============================================================================

class TestParserStrict:
    def test_old_format_dict_finish(self):
        """BUG修复验证: dict含action不含tool_name不再降级为implicit"""
        r = parse_react_response({"action": "finish", "action_input": {"result": 42}})
        assert r["type"] == "answer", f"旧格式dict finish必须=answer, got {r['type']}"
        assert r["response"] == "42"

    def test_old_format_dict_action(self):
        r = parse_react_response({"action": "search_web", "action_input": {"query": "test"}, "thought": "search"})
        assert r["type"] == "action" and r["tool_name"] == "search_web"

    def test_old_format_dict_finish_dict_result(self):
        r = parse_react_response({"action": "finish", "action_input": {"result": {"status": "ok"}}})
        assert r["type"] == "answer" and isinstance(r["response"], str)

    def test_new_format_dict_finish(self):
        r = parse_react_response({"tool_name": "finish", "tool_params": {"result": 42}})
        assert r["type"] == "answer" and r["response"] == "42"

    def test_json_string_old_format_finish(self):
        r = parse_react_response(json.dumps({"action": "finish", "action_input": {"result": 42}}))
        assert r["type"] == "answer" and r["response"] == "42"

    def test_bool_not_int(self):
        assert _normalize_result_to_str(True) == "True" != _normalize_result_to_str(1)

    def test_none_returns_empty(self):
        assert _normalize_result_to_str(None) == ""

    def test_filter_reasoning(self):
        r = parse_react_response({"tool_name": "search_web", "tool_params": {"query": "test", "reasoning": "internal"}})
        assert "reasoning" not in r.get("tool_params", {})

    def test_empty_and_none_parse_error(self):
        assert parse_react_response("")["type"] == "parse_error"
        assert parse_react_response(None)["type"] == "parse_error"


# =============================================================================
# 9. 服务API模块 严苛验证
# =============================================================================

class TestAPIStrict:
    def test_health_200(self):
        assert httpx.get(f"{BASE}/health", timeout=15).status_code == 200

    def test_tool_list_59(self):
        d = httpx.get(f"{BASE}/tool/list", timeout=15).json()
        assert d["total"] == 59 and len(d["tools"]) == 59

    def test_session_create_list_delete(self):
        r = httpx.post(f"{BASE}/sessions", json={}, timeout=15)
        assert r.status_code == 200
        sid = r.json().get("session_id") or r.json().get("data", {}).get("session_id")
        assert sid is not None
        r2 = httpx.get(f"{BASE}/sessions", timeout=15)
        assert r2.status_code == 200
        r3 = httpx.delete(f"{BASE}/sessions/{sid}", timeout=15)
        assert r3.status_code == 200

    def test_security_dangerous_command(self):
        r = httpx.post(f"{BASE}/security/check", json={"command": "rm -rf /"}, timeout=15)
        assert r.status_code == 200

    def test_config_get(self):
        r = httpx.get(f"{BASE}/config", timeout=15)
        assert r.status_code == 200 and "ai_model" in r.json()
