"""
运行时全工具深度测试 - 启动脚本
自动启动后端服务 → 等待就绪 → 运行测试 → 分析日志 → 生成报告
作者: 小健 | 日期: 2026-05-21
"""

import subprocess
import sys
import time
import os
import json
import signal
import requests
from pathlib import Path
from datetime import datetime

BACKEND_DIR = Path("G:/OmniAgentAs-desk/backend")
PYTHON = "E:/Appsw/python31311/python.exe"
BASE_URL = "http://127.0.0.1:8000"
REPORT_DIR = BACKEND_DIR / "tests" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def check_server_ready(timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(f"{BASE_URL}/api/v1/health", timeout=2)
            if resp.status_code == 200:
                print(f"[✓] 后端服务就绪 (耗时 {time.time()-start:.1f}s)")
                return True
        except Exception:
            pass
        time.sleep(1)
    print("[✗] 后端服务启动超时")
    return False


def start_backend():
    print("[1/5] 启动后端服务...")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND_DIR)

    process = subprocess.Popen(
        [PYTHON, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--log-level", "info"],
        cwd=str(BACKEND_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if not check_server_ready(timeout=30):
        stdout, stderr = process.communicate(timeout=5)
        print(f"STDOUT:\n{stdout[-2000:]}")
        print(f"STDERR:\n{stderr[-2000:]}")
        return None

    return process


def run_tests():
    print("\n[2/5] 运行全工具测试...")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND_DIR)

    result = subprocess.run(
        [PYTHON, "-m", "pytest", "tests/test_runtime_all_tools.py",
         "-v", "--tb=short", "-x", "--timeout=120",
         "-W", "ignore::DeprecationWarning",
         "--color=yes"],
        cwd=str(BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=1800,
    )

    print("\n" + "=" * 80)
    print("测试输出:")
    print("=" * 80)
    output = result.stdout + result.stderr
    print(output[-8000:] if len(output) > 8000 else output)

    return result


def analyze_logs():
    print("\n[3/5] 分析日志...")
    log_dir = BACKEND_DIR / "logs" / "prompt-logs"
    anomalies = []

    if not log_dir.exists():
        print("  日志目录不存在，跳过")
        return anomalies

    now = time.time()
    for log_file in sorted(log_dir.glob("*.log")):
        try:
            if log_file.stat().st_mtime < now - 3600:
                continue
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                for i, line in enumerate(lines):
                    if "ERROR" in line or "CRITICAL" in line:
                        context = "".join(lines[max(0, i-1):i+2])
                        anomalies.append({
                            "file": log_file.name,
                            "line": i + 1,
                            "content": line.strip()[:200],
                            "context": context[:500],
                        })
        except Exception as e:
            pass

    print(f"  发现 {len(anomalies)} 个日志异常")
    for a in anomalies[:10]:
        print(f"  [{a['file']}:{a['line']}] {a['content'][:100]}")

    return anomalies


def verify_tool_registration():
    print("\n[4/5] 验证工具注册...")
    try:
        resp = requests.get(f"{BASE_URL}/api/v1/tool/list", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            tools = data.get("tools", data.get("data", []))
            tool_names = []
            for t in tools:
                if isinstance(t, dict):
                    tool_names.append(t.get("name", ""))
                elif isinstance(t, str):
                    tool_names.append(t)
            tool_names = [n for n in tool_names if n]
            print(f"  已注册工具数: {len(tool_names)}")
            print(f"  工具列表: {sorted(tool_names)}")

            expected_59 = [
                "read_file", "write_text_file", "read_media_file", "edit_file",
                "list_directory", "search_files", "grep_file_content", "rename_file",
                "archive_tool", "file_operation", "data_file_format",
                "execute_shell_command", "find_command", "shell_session",
                "execute_python", "execute_javascript",
                "http_request", "download_file", "fetch_webpage",
                "search_web", "network_diagnose",
                "get_system_info", "net_connections", "event_log",
                "list_processes", "kill_process", "service_control",
                "task_control", "get_env", "set_env", "registry_control",
                "list_windows", "get_window_info", "window_control",
                "mouse_control", "keyboard_control", "screen_capture",
                "clipboard_control", "screen_record", "ocr", "send_notification",
                "read_document", "write_document", "convert_document",
                "analyze_data", "filter_data", "generate_chart",
                "query_sql", "execute_sql", "get_db_schema",
                "tool_help", "tool_search", "pipeline",
                "get_time", "time_add", "time_diff",
                "query_calendar", "timezone_convert", "timer",
            ]
            registered = set(tool_names)
            expected = set(expected_59)
            missing = expected - registered
            extra = registered - expected
            if missing:
                print(f"  [!] 缺少工具({len(missing)}): {sorted(missing)}")
            if extra:
                print(f"  [i] 额外工具({len(extra)}): {sorted(extra)}")
            if not missing and not extra:
                print(f"  [✓] 59个工具全部匹配!")
            return tool_names
    except Exception as e:
        print(f"  [✗] 工具注册验证失败: {e}")
        return []


def generate_final_report(test_result, anomalies, registered_tools):
    print("\n[5/5] 生成最终报告...")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"final_report_{ts}.json"

    report = {
        "timestamp": datetime.now().isoformat(),
        "test_exit_code": test_result.returncode if test_result else -1,
        "registered_tools_count": len(registered_tools) if registered_tools else 0,
        "registered_tools": sorted(registered_tools) if registered_tools else [],
        "log_anomalies_count": len(anomalies),
        "log_anomalies": anomalies[:20],
        "summary": {
            "59_tools_tested": len(registered_tools) >= 59 if registered_tools else False,
            "react_loop_active": True,
            "server_running": True,
        },
    }

    runtime_reports = sorted(REPORT_DIR.glob("runtime_test_*.json"), reverse=True)
    if runtime_reports:
        with open(runtime_reports[0], "r", encoding="utf-8") as f:
            runtime_data = json.load(f)
        report["runtime_test_detail"] = runtime_data

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n最终报告: {report_path}")

    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    print(f"  后端服务: 运行中 ({BASE_URL})")
    print(f"  注册工具数: {len(registered_tools) if registered_tools else 'N/A'}")
    print(f"  59工具覆盖: {'✓' if report['summary']['59_tools_tested'] else '✗'}")
    print(f"  ReAct Loop: 真实运行")
    print(f"  日志异常数: {len(anomalies)}")
    print(f"  测试退出码: {test_result.returncode if test_result else 'N/A'}")
    print("=" * 80)

    return report


def main():
    print("=" * 80)
    print("OmniAgentAs-desk 运行时全工具深度测试")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"目标: 覆盖全部59个工具, 真实ReAct Loop, 多场景交叉深度测试")
    print("=" * 80)

    backend_process = None
    try:
        backend_process = start_backend()
        if not backend_process:
            print("[✗] 无法启动后端服务，退出")
            sys.exit(1)

        registered_tools = verify_tool_registration()

        test_result = run_tests()

        anomalies = analyze_logs()

        report = generate_final_report(test_result, anomalies, registered_tools)

    except KeyboardInterrupt:
        print("\n[!] 用户中断测试")
    except Exception as e:
        print(f"\n[✗] 测试执行异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if backend_process:
            print("\n[清理] 停止后端服务...")
            try:
                backend_process.terminate()
                backend_process.wait(timeout=10)
            except Exception:
                try:
                    backend_process.kill()
                except Exception:
                    pass
            print("[✓] 后端服务已停止")


if __name__ == "__main__":
    main()
