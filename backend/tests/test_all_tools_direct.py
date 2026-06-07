#!/usr/bin/env python
"""
工具函数全覆盖测试 v2 — 直接调用，绕过LLM

小健 2026-05-23
"""
import asyncio, json, sys, time, inspect, os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.tools import ensure_tools_registered
ensure_tools_registered()

from app.services.tools.registry import tool_registry

REPORT_DIR = Path(__file__).resolve().parent / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)
TEMP = Path(__file__).resolve().parent / "temp_runtime_test"
TEMP.mkdir(parents=True, exist_ok=True)
FRONTEND = Path(__file__).resolve().parent.parent / ".." / "frontend" / "public"
# 预创建所有测试文件（避免依赖顺序问题）
(TEMP / "test_direct.txt").write_text("hello direct test", encoding="utf-8")
(TEMP / "test_data.json").write_text('{"ver":1}', encoding="utf-8")
# 为 archive_tool 和 rename_file 预准备文件
(TEMP / "renamed_direct.txt").write_text("this file is for archive test", encoding="utf-8")
# 为 read_document 创建 .json 文件
(TEMP / "e2e_data.json").write_text('{"name":"test","value":123}', encoding="utf-8")
# 为 read_media_file 创建正确的路径
(TEMP / "test_media.txt").write_text("media test", encoding="utf-8")
FRONTEND_PUBLIC = FRONTEND  # 保留/vite.svg的原始路径引用


_TOOL_TIMEOUT = 120  # 每个工具最多等120秒

async def _call_async(func, **kw):
    """async 调用（同步函数也在此统一处理）"""
    try:
        r = func(**kw)
        if inspect.iscoroutine(r):
            r = await asyncio.wait_for(r, timeout=_TOOL_TIMEOUT)
        if isinstance(r, dict):
            code = r.get("code", "")
            msg = r.get("message", "")
            ok = (code == "SUCCESS" or code == 0)
            # 统一用消息关键词判断真实失败
            fail_keywords = ["错误","失败","不存在","不支持","缺失","缺少","无效","超时",
                             "没有活跃任务","没有当前活跃任务","需要安装","未安装",
                             "不存在于","找不到","无法找到","拒绝","禁止",
                             "no active task","not found","not installed","failed",
                             "timeout","error","invalid"]
            msg_lower = msg.lower() if msg else ""
            has_fail = any((k in msg) or (k in msg_lower) for k in fail_keywords) if msg else False
            ok = ok and not has_fail
            summary = r.get("summary", "") or r.get("message", "") or r.get("data", "")
            if isinstance(summary, (dict, list)):
                summary = str(summary)[:100]
            return ok, str(summary)[:100]
        return True, str(r)[:100]
    except asyncio.TimeoutError:
        return False, "TIMEOUT"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:150]}"


# 测试参数定义：name → (category, {kwarg_dict})
# 按实际函数签名 / Schema 填写参数名
TOOL_PARAMS = {
    # ----- file (12) -----
    "read_file":          ("file", {"file_paths": [str(TEMP / "test_direct.txt")]}),
    "write_text_file":    ("file", {"file_path": str(TEMP / "write_test.txt"), "text": "hello direct"}),
    "list_directory":     ("file", {"dir_path": str(TEMP)}),
    "search_files":       ("file", {"pattern": "*.txt", "search_dir": str(TEMP)}),
    "grep_file_content":  ("file", {"pattern": "hello", "search_dir": str(TEMP)}),
    "edit_file":          ("file", {"file_path": str(TEMP / "test_direct.txt"), "old_string": "hello", "new_string": "hi"}),
    "file_operation":     ("file", {"action": "copy", "source": str(TEMP / "test_direct.txt"), "destination": str(TEMP / "copied_test.txt")}),
    # rename_file 独立工具处理重命名
    "archive_tool":       ("file", {"action": "compress", "source": str(TEMP / "renamed_direct.txt"), "destination": str(TEMP / "test_archive.zip")}),
    "rename_file":        ("file", {"file_path": str(TEMP / "renamed_direct.txt"), "new_name": "final_direct.txt"}),
    "data_file_format":   ("file", {"file_path": str(TEMP / "test_data.json"), "action": "read", "format": "json"}),
    "read_media_file":    ("file", {"file_path": str(TEMP / "test_media.txt")}),
    "batch_process":      ("file", {"source_pattern": str(TEMP / "*.txt"), "action": "copy", "target_dir": str(TEMP / "batch_out"), "exist_ok": True}),

    # ----- shell (4) -----
    "execute_shell_command": ("shell", {"command": "Get-Date", "timeout": 15000}),
    "find_command":          ("shell", {"command": "python"}),
    "shell_session":         ("shell", {"shell_id": "test_shell_direct", "action": "output"}),
    "execute_code":          ("shell", {"code": "print('test success')", "language": "python", "timeout": 30000}),

    # ----- network (5) -----
    "http_request":  ("network", {"url": "https://httpbin.org/get", "method": "GET"}),
    "fetch_webpage": ("network", {"url": "https://httpbin.org/html"}),
    "download_file": ("network", {"url": "https://httpbin.org/json", "destination_path": str(TEMP / "httpbin.json")}),
    "search_web":    ("network", {"query": "Python programming"}),
    "network_diagnose": ("network", {"host": "127.0.0.1", "mode": "ping"}),

    # ----- system (10) -----
    "get_system_info": ("system", {}),
    "net_connections": ("system", {}),
    "event_log":       ("system", {"log_name": "Application", "max_events": 5}),
    "list_processes":  ("system", {"sort_by": "memory"}),
    "get_env":         ("system", {"name": "PATH", "scope": "process"}),
    "set_env":         ("system", {"name": "TEST_E2E_VAR", "value": "hello", "scope": "process", "action": "set"}),
    "registry_control": ("system", {"action": "read", "key_path": r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion", "value_name": "ProductName"}),
    "service_control":  ("system", {"action": "list", "state": "running"}),
    "kill_process":     ("system", {"pid": 999999, "force": False, "timeout": 5}),
    "task_control":     ("system", {"action": "list"}),

    # ----- desktop (9) -----
    "window_info":         ("desktop", {}),
    "screen_capture":      ("desktop", {"output_path": str(TEMP / "screenshot.png")}),
    "clipboard_control":   ("desktop", {"action": "read"}),
    "mouse_control":       ("desktop", {"action": "position"}),
    "keyboard_control":    ("desktop", {"action": "type", "text_or_keys": "hello"}),
    "send_notification":   ("desktop", {"title": "E2E Test", "message": "Testing..."}),
    "ocr":                 ("desktop", {"image_path": str(TEMP / "screenshot.png")}),
    "window_control":      ("desktop", {"window_title": "", "action": "minimize"}),
    "screen_record":       ("desktop", {"duration": 1, "output_path": str(TEMP / "screen_record.mp4")}),

    # ----- document (12) -----
    "read_document":    ("document", {"file_path": str(TEMP / "e2e_data.json")}),
    "write_document":   ("document", {"file_path": str(TEMP / "e2e_test.docx"), "content": "hello document"}),
    "convert_document": ("document", {"input_path": str(TEMP / "e2e_data.json"), "output_format": "pdf", "output_path": str(TEMP / "converted.pdf")}),
    "analyze_data":     ("document", {"data": [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}], "operations": ["count"]}),
    "filter_data":      ("document", {"data": [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}], "conditions": [{"column": "name", "op": "eq", "value": "Alice"}]}),
    "generate_chart":   ("document", {"data": {"categories": ["A", "B"], "values": [10, 20]}, "chart_type": "bar", "output_path": str(TEMP / "chart.png")}),
    "get_db_schema":    ("document", {"table_name": "sessions"}),
    "query_sql":        ("document", {"sql": "SELECT name FROM sqlite_master WHERE type='table'", "limit": 5}),
    "execute_sql":      ("document", {"sql": "SELECT 1", "connection_type": "sqlite"}),

    # ----- meta (8) -----
    "tool_help":      ("meta", {"tool_name": "read_file"}),
    "tool_search":    ("meta", {"query": "file"}),
    "get_time":       ("meta", {}),
    "time_add":       ("meta", {"delta": 5, "start": "2026-05-23 12:00:00", "unit": "days"}),
    "time_diff":      ("meta", {"start": "2026-01-01", "end": "2026-05-23"}),
    "query_calendar": ("meta", {"date": "2026-05-23", "check_type": "workday"}),
    "timezone_convert": ("meta", {"time_value": "2026-05-23 12:00:00", "direction": "local_to_utc", "tz": "Asia/Shanghai"}),
    "timer":          ("meta", {"action": "list"}),
}

TOOL_PARAMS["pipeline"] = ("meta", {"steps": json.dumps([{"step": "1", "action": "get_time", "tool": "get_time"}]), "stop_on_error": True})

# 补充未在38→58扩展中注明的工具
TOOL_PARAMS["task_control"] = ("system", {"action": "list"})
TOOL_PARAMS["pipeline"] = ("meta", {"steps": json.dumps([{"step": "1", "action": "get_time"}]), "stop_on_error": True})
TOOL_PARAMS["execute_sql"] = ("document", {"sql": "SELECT 1", "connection_type": "sqlite"})


async def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    all_tools = sorted(TOOL_PARAMS.items(), key=lambda x: x[0])
    total = len(all_tools)
    lines = []

    def log(msg):
        lines.append(msg)
        print(msg)

    log(f"\n{'='*60}")
    log(f"  工具函数全覆盖测试 | {total} tools")
    log(f"  启动: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"{'='*60}\n")

    results = []
    for idx, (name, (cat, params)) in enumerate(all_tools, 1):
        impl = tool_registry.get_implementation(name)
        if impl is None:
            log(f"[{idx:02d}/{total}] {name:30s} NOT_REGISTERED")
            results.append({"name": name, "category": cat, "ok": False, "summary": "not registered", "detail": "", "dur": 0})
            continue

        start = time.time()
        msg = f"[{idx:02d}/{total}] {name:30s} ({cat})"
        print(msg, end=" ... ", flush=True)
        ok, summary = await _call_async(impl, **params)
        dur = time.time() - start
        status = "OK" if ok else "FAIL"
        line = f" {status} {dur:6.1f}s  {summary[:80]}"
        print(line)
        lines.append(f"{msg} ... {line}")
        results.append({"name": name, "category": cat, "ok": ok, "summary": summary[:100], "detail": "", "dur": round(dur, 2)})

        if not ok:
            ps = ", ".join(f"{k}={v}" for k, v in params.items())
            line = f"         args: {ps}"
            print(line)
            lines.append(line)

    # summary
    passed = sum(1 for r in results if r["ok"])
    failed = total - passed
    by_cat = {}
    for r in results:
        by_cat.setdefault(r["category"], []).append(r)

    log(f"\n{'='*60}")
    log(f"  结果汇总")
    log(f"{'='*60}")
    log(f"  总计: {total} | 通过: {passed} | 失败: {failed} | 通过率: {passed/total*100:.1f}%")
    log("")
    for c in sorted(by_cat):
        items = by_cat[c]
        cp = sum(1 for r in items if r["ok"])
        fails = [r["name"] for r in items if not r["ok"]]
        fstr = f"  FAIL: {', '.join(fails)}" if fails else ""
        log(f"  {c:15s}: {cp:2d}/{len(items):2d} ({cp/len(items)*100:3.0f}%){fstr}")

    if failed:
        log(f"\n--- 失败详情 ---")
        for r in results:
            if not r["ok"]:
                log(f"  [{r['category']}] {r['name']:30s} | {r['summary'][:100]}")

    report = {
        "end": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": total, "passed": passed, "failed": failed,
        "rate": f"{passed/total*100:.1f}%",
        "by_category": {c: {"pass": sum(1 for r in by_cat[c] if r["ok"]), "total": len(by_cat[c])} for c in sorted(by_cat)},
        "results": results,
    }
    rp = REPORT_DIR / f"direct_tool_test_{ts}.json"
    with open(rp, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    log(f"\n  报告: {rp}")

if __name__ == "__main__":
    asyncio.run(main())
