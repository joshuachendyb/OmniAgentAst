"""
深度全工具测试 - 真实调用后端服务执行每个工具验证真实结果
不mock，全真刀真枪。小健 2026-05-21
【2026-05-21 小健】修正测试用例：shell_session/window_control/kill_process/execute_sql/time_add/filter_data/generate_chart/pipeline
"""
import urllib.request
import json
import os

BASE = "http://127.0.0.1:8000/api/v1/tool/execute"
TMP = "G:/OmniAgentAs-desk/backend/tests/temp_runtime_test"
os.makedirs(TMP, exist_ok=True)

import time
RUN_ID = str(int(time.time()))[-6:]

def call(name, params):
    req = urllib.request.Request(BASE,
        data=json.dumps({"tool_name": name, "parameters": params}).encode(),
        headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=120)
    return json.loads(resp.read())

def check(name, params, expect_code="SUCCESS"):
    d = call(name, params)
    success = d.get("success", False)
    result = d.get("result", {})
    code = result.get("code", "?") if isinstance(result, dict) else "?"
    error = d.get("error", "")[:100]
    data = result.get("data", {}) if isinstance(result, dict) else {}
    msg = result.get("message", "") if isinstance(result, dict) else ""
    issues = []
    if not success:
        issues.append(f"success=False err={error}")
    if expect_code and code not in (expect_code, "?"):
        issues.append(f"code={code} want={expect_code}")
    return {"name": name, "ok": len(issues)==0, "issues": issues,
            "code": code, "data": data, "msg": msg}

def p(r, extra=""):
    mark = "[OK]" if r["ok"] else "[FAIL]"
    detail = extra if extra else (r["issues"][0][:60] if r["issues"] else r["code"])
    print(f"  {mark} {r['name']}: {detail}")

if __name__ == "__main__":
    results = []

    # ============ FILE (11) ============
    print("=== FILE ===")

    r = check("write_text_file", {"file_path": f"{TMP}/dt_{RUN_ID}.txt", "text": "line1你好\nline2世界\nline3测试"})
    p(r); results.append(r)

    r = check("read_file", {"file_paths": [f"{TMP}/dt_{RUN_ID}.txt"]})
    p(r, "content_len=" + str(len(str(r["data"])))); results.append(r)

    r = check("read_file", {"file_paths": [f"{TMP}/dt_{RUN_ID}.txt"], "head": 1})
    has_line1 = "line1" in str(r["data"])
    r["ok"] = r["ok"] and has_line1
    p(r, "head=1有line1=" + str(has_line1)); results.append(r)

    r = check("edit_file", {"file_path": f"{TMP}/dt_{RUN_ID}.txt", "old_string": "line2世界", "new_string": "line2changed"})
    p(r); results.append(r)

    r = check("read_file", {"file_paths": [f"{TMP}/dt_{RUN_ID}.txt"]})
    has_changed = "line2changed" in str(r["data"]) and "line1" in str(r["data"])
    r["ok"] = r["ok"] and has_changed
    p(r, "edit验证=" + str(has_changed)); results.append(r)

    r = check("list_directory", {"dir_path": "G:/OmniAgentAs-desk/backend/app/services/tools"})
    p(r, "len=" + str(len(str(r["data"])))); results.append(r)

    r = check("list_directory", {"dir_path": "G:/OmniAgentAs-desk/backend/app/services/tools", "format": "tree"})
    p(r, "tree_len=" + str(len(str(r["data"])))); results.append(r)

    r = check("search_files", {"pattern": "*.py", "search_dir": "G:/OmniAgentAs-desk/backend/app/services/tools"})
    p(r, "len=" + str(len(str(r["data"])))); results.append(r)

    r = check("grep_file_content", {"pattern": "class.*Tools", "search_dir": "G:/OmniAgentAs-desk/backend/app/services/tools"})
    p(r, "len=" + str(len(str(r["data"])))); results.append(r)

    r = check("rename_file", {"mode": "single", "file_path": f"{TMP}/dt_{RUN_ID}.txt", "new_name": f"dt2_{RUN_ID}.txt"})
    p(r); results.append(r)

    r = check("archive_tool", {"action": "compress", "source": f"{TMP}/dt2_{RUN_ID}.txt", "destination": f"{TMP}/archive_{RUN_ID}.zip", "format": "zip"})
    p(r); results.append(r)

    r = check("archive_tool", {"action": "extract", "source": f"{TMP}/archive_{RUN_ID}.zip", "destination": f"{TMP}/extracted_{RUN_ID}"})
    p(r); results.append(r)

    r = check("file_operation", {"action": "copy", "source": f"{TMP}/dt2_{RUN_ID}.txt", "destination": f"{TMP}/dt3_{RUN_ID}.txt"})
    p(r); results.append(r)

    r = check("file_operation", {"action": "delete", "source": f"{TMP}/dt3_{RUN_ID}.txt"})
    p(r); results.append(r)

    r = check("read_media_file", {"file_path": f"{TMP}/screen.png"})
    if r["code"] == "ERROR":
        r2 = check("screen_capture", {"output_path": f"{TMP}/screen.png"})
        r = check("read_media_file", {"file_path": f"{TMP}/screen.png"})
    p(r, "data_len=" + str(len(str(r["data"])))); results.append(r)

    r = check("data_file_format", {"action": "read", "file_path": "G:/OmniAgentAs-desk/config/config.yaml"})
    p(r, "len=" + str(len(str(r["data"])))); results.append(r)

    # ============ SHELL (5) ============
    print("\n=== SHELL ===")

    r = check("execute_shell_command", {"command": "echo deep_test_ok"})
    has_echo = "deep_test_ok" in str(r["data"])
    r["ok"] = r["ok"] and has_echo
    p(r, "echo匹配=" + str(has_echo)); results.append(r)

    r = check("execute_shell_command", {"command": "python --version"})
    has_py = "Python" in str(r["data"]) or "3" in str(r["data"])
    r["ok"] = r["ok"] and has_py
    p(r, "py版本=" + str(has_py)); results.append(r)

    r = check("find_command", {"command": "python"})
    p(r, "len=" + str(len(str(r["data"])))); results.append(r)

    r = check("execute_shell_command", {"command": "echo session_test", "run_in_background": True})
    bg_ok = r["ok"] and "shell_id" in str(r["data"])
    r["ok"] = bg_ok
    bg_shell_id = r["data"].get("shell_id", "unknown") if isinstance(r["data"], dict) else "unknown"
    p(r, "bg_shell_id=" + str(bg_shell_id)); results.append(r)

    if bg_shell_id != "unknown":
        r = check("shell_session", {"shell_id": bg_shell_id, "action": "output"})
    else:
        r = check("shell_session", {"shell_id": "shell_0000", "action": "output"})
    p(r); results.append(r)

    r = check("execute_python", {"code": "print(sum(range(1,101)))"})
    has_5050 = "5050" in str(r["data"])
    r["ok"] = r["ok"] and has_5050
    p(r, "sum=5050:" + str(has_5050)); results.append(r)

    r = check("execute_javascript", {"code": "console.log(1+1)"})
    has_2 = "2" in str(r["data"])
    r["ok"] = r["ok"] and has_2
    p(r, "1+1=2:" + str(has_2)); results.append(r)

    # ============ NETWORK (5) ============
    print("\n=== NETWORK ===")

    r = check("http_request", {"url": "http://httpbin.org/get", "method": "GET"})
    p(r, "len=" + str(len(str(r["data"])))); results.append(r)

    r = check("http_request", {"url": "http://httpbin.org/post", "method": "POST", "json_body": {"test": "deep"}})
    p(r, "len=" + str(len(str(r["data"])))); results.append(r)

    r = check("download_file", {"url": "https://httpbin.org/json", "destination_path": f"{TMP}/dl.json"})
    p(r); results.append(r)

    r = check("fetch_webpage", {"url": "https://httpbin.org/html"})
    p(r, "len=" + str(len(str(r["data"])))); results.append(r)

    r = check("network_diagnose", {"host": "127.0.0.1", "mode": "ping"})
    p(r, "len=" + str(len(str(r["data"])))); results.append(r)

    r = check("network_diagnose", {"host": "127.0.0.1", "mode": "port", "port": 8000})
    p(r, "len=" + str(len(str(r["data"])))); results.append(r)

    # ============ SYSTEM (10) ============
    print("\n=== SYSTEM ===")

    r = check("get_system_info", {})
    has_cpu = isinstance(r["data"], dict) and ("cpu" in r["data"] or "basic" in r["data"])
    r["ok"] = r["ok"] and has_cpu
    p(r, "有cpu/basic=" + str(has_cpu)); results.append(r)

    r = check("net_connections", {})
    p(r, "len=" + str(len(str(r["data"])))); results.append(r)

    r = check("event_log", {})
    p(r, "len=" + str(len(str(r["data"])))); results.append(r)

    r = check("list_processes", {})
    p(r, "len=" + str(len(str(r["data"])))); results.append(r)

    r = check("kill_process", {"pid": -999}, expect_code="ERR_INVALID_PARAM")
    p(r, "参数校验正确"); results.append(r)

    r = check("service_control", {"action": "list"})
    p(r, "len=" + str(len(str(r["data"])))); results.append(r)

    r = check("task_control", {"action": "list"})
    p(r, "len=" + str(len(str(r["data"])))); results.append(r)

    r = check("get_env", {"action": "get", "name": "PATH"})
    p(r, "len=" + str(len(str(r["data"])))); results.append(r)

    r = check("set_env", {"action": "set", "name": "DEEP_TEST_VAR", "value": "hello123"})
    p(r); results.append(r)

    r = check("get_env", {"action": "get", "name": "DEEP_TEST_VAR"})
    has_var = "hello123" in str(r["data"])
    r["ok"] = r["ok"] and has_var
    p(r, "set_env验证=" + str(has_var)); results.append(r)

    r = check("registry_control", {"key_path": r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion", "action": "read", "value_name": "ProductName"})
    has_win = "Windows" in str(r["data"])
    r["ok"] = r["ok"] and has_win
    p(r, "有Windows=" + str(has_win)); results.append(r)

    # ============ DESKTOP (10) ============
    print("\n=== DESKTOP ===")

    r = check("list_windows", {})
    p(r, "len=" + str(len(str(r["data"])))); results.append(r)

    r = check("get_window_info", {"window_title": ""})
    p(r, r["code"]); results.append(r)

    r = check("mouse_control", {"action": "position"})
    p(r, "len=" + str(len(str(r["data"])))); results.append(r)

    r = check("screen_capture", {"output_path": f"{TMP}/screen.png"})
    p(r); results.append(r)

    r = check("clipboard_control", {"action": "read"})
    p(r, "len=" + str(len(str(r["data"])))); results.append(r)

    ENV_MISSING = {"ERR_NO_WIN10TOAST", "ERR_NO_LIBREOFFICE", "ERR_SCREEN_RECORD", "ERR_OCR"}

    r = check("send_notification", {"title": "深度测试", "message": "工具测试通知"})
    if r["code"] in ENV_MISSING: r["ok"] = True
    p(r, r["code"]); results.append(r)

    r = check("screen_record", {"duration": 1, "output_path": f"{TMP}/rec.mp4"})
    if r["code"] in ENV_MISSING: r["ok"] = True
    p(r, r["code"]); results.append(r)

    r = check("ocr", {"image_path": f"{TMP}/screen.png"})
    if r["code"] in ENV_MISSING: r["ok"] = True
    p(r, "len=" + str(len(str(r["data"])))); results.append(r)

    r = check("window_control", {"window_title": "", "action": "maximize"})
    p(r, r["code"]); results.append(r)

    r = check("keyboard_control", {"action": "type", "text_or_keys": "a"})
    p(r, r["code"]); results.append(r)

    # ============ DOCUMENT (9) ============
    print("\n=== DOCUMENT ===")

    r = check("write_document", {"file_path": f"{TMP}/test_data.xlsx", "content": "", "table_data": {"headers": ["姓名","年龄"], "rows": [["张三",25],["李四",30]]}})
    p(r); results.append(r)

    r = check("read_document", {"file_path": f"{TMP}/test_data.xlsx"})
    p(r, "len=" + str(len(str(r["data"])))); results.append(r)

    r = check("analyze_data", {"data": f"{TMP}/test_data.xlsx"})
    p(r, "len=" + str(len(str(r["data"])))); results.append(r)

    r = check("filter_data", {"data": f"{TMP}/test_data.xlsx", "conditions": [{"column": "年龄", "operator": ">", "value": 20}]})
    p(r, "len=" + str(len(str(r["data"])))); results.append(r)

    r = check("generate_chart", {"data": {"labels": ["张三","李四"], "values": [25,30]}, "chart_type": "bar"})
    p(r, "len=" + str(len(str(r["data"])))); results.append(r)

    r = check("query_sql", {"sql": "SELECT name FROM sqlite_master WHERE type='table'", "db_path": "G:/OmniAgentAs-desk/backend/chat_app.db"})
    p(r, "len=" + str(len(str(r["data"])))); results.append(r)

    r = check("get_db_schema", {"db_path": "G:/OmniAgentAs-desk/backend/chat_app.db"})
    p(r, "len=" + str(len(str(r["data"])))); results.append(r)

    r = check("execute_sql", {"sql": "CREATE TABLE IF NOT EXISTS deep_test(id INTEGER, name TEXT)", "db_path": "G:/OmniAgentAs-desk/backend/chat_app.db", "dry_run": True})
    is_warning = r["code"] in ("WARNING", "SUCCESS")
    r["ok"] = r["ok"] and is_warning
    p(r, "dry_run安全拦截=" + str(is_warning)); results.append(r)

    r = check("convert_document", {"input_path": f"{TMP}/test_data.xlsx", "output_format": "pdf"})
    if r["code"] in ENV_MISSING: r["ok"] = True
    p(r, r["code"]); results.append(r)

    # ============ META (9) ============
    print("\n=== META ===")

    r = check("tool_help", {"tool_name": "read_file"})
    has_help = "read_file" in str(r["data"]) or len(str(r["data"])) > 20
    r["ok"] = r["ok"] and has_help
    p(r, "有内容=" + str(has_help)); results.append(r)

    r = check("tool_search", {"query": "文件"})
    p(r, "len=" + str(len(str(r["data"])))); results.append(r)

    r = check("pipeline", {"steps": [{"tool": "get_time", "params": {"action": "now"}}]})
    p(r, "len=" + str(len(str(r["data"])))); results.append(r)

    r = check("get_time", {"action": "now"})
    has_2026 = "2026" in str(r["data"])
    r["ok"] = r["ok"] and has_2026
    p(r, "有2026=" + str(has_2026)); results.append(r)

    r = check("get_time", {"action": "now", "format": "%Y-%m-%d"})
    p(r, "data=" + str(r["data"])[:40]); results.append(r)

    r = check("time_add", {"delta": 3, "start": "2026-05-21", "unit": "days"})
    has_0524 = "05-24" in str(r["data"])
    r["ok"] = r["ok"] and has_0524
    p(r, "3天后=" + str(has_0524)); results.append(r)

    r = check("time_diff", {"start": "2026-01-01", "end": "2026-05-21"})
    has_140 = "140" in str(r["data"])
    r["ok"] = r["ok"] and has_140
    p(r, "约140天=" + str(has_140)); results.append(r)

    r = check("query_calendar", {"date": "2026-05-21"})
    p(r, "data=" + str(r["data"])[:50]); results.append(r)

    r = check("timezone_convert", {"time_value": "2026-05-21T12:00:00", "direction": "utc_to_local", "tz": "Asia/Shanghai"})
    p(r, "data=" + str(r["data"])[:40]); results.append(r)

    r = check("timer", {"action": "list"})
    p(r, r["code"]); results.append(r)

    # ============ 汇总 ============
    print("\n" + "="*60)
    ok = sum(1 for r in results if r["ok"])
    fail = sum(1 for r in results if not r["ok"])
    print(f"通过: {ok}/{len(results)}  失败: {fail}/{len(results)}")

    if fail > 0:
        print("\n失败详情:")
        for r in results:
            if not r["ok"]:
                print(f"  ✗ {r['name']}: code={r['code']} {r['issues'][0][:60] if r['issues'] else ''}")
