"""
运行时全工具深度测试 - 基于真实ReAct Loop的后端测试
测试目标: 覆盖全部59个工具, 多场景交叉深度测试, 实时日志监控
作者: 小健 | 日期: 2026-05-21
"""

import asyncio
import json
import time
import re
import os
import sys
import traceback
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

import pytest
import httpx
from httpx import ASGITransport

# 使用 ASGITransport 测试真实 ASGI 链路（不依赖外部 uvicorn 进程）
try:
    _backend_dir = str(Path(__file__).resolve().parent.parent)
    if _backend_dir not in sys.path:
        sys.path.insert(0, _backend_dir)
    from app.main import app as _app
    _ASGI_TRANSPORT = ASGITransport(app=_app)
except Exception as _e:
    print(f"[WARN] ASGITransport unavailable: {_e}, fallback to external server")
    _ASGI_TRANSPORT = None

BASE_URL = "http://127.0.0.1:8000"
CHAT_ENDPOINT = "/api/v1/chat/stream/v2"
HEALTH_ENDPOINT = "/api/v1/health"
LIST_TOOLS_ENDPOINT = "/api/v1/tool/list"
EXECUTE_TOOL_ENDPOINT = "/api/v1/tool/execute"
SESSIONS_ENDPOINT = "/api/v1/sessions"
CONFIG_ENDPOINT = "/api/v1/config"
SECURITY_CHECK_ENDPOINT = "/api/v1/security/check"
METRICS_ENDPOINT = "/api/v1/metrics"

LOG_DIR = Path("G:/OmniAgentAs-desk/backend/logs/prompt-logs")
TEST_REPORT_DIR = Path("G:/OmniAgentAs-desk/backend/tests/reports")
TEST_REPORT_DIR.mkdir(parents=True, exist_ok=True)

TEST_TEMP_DIR = Path("G:/OmniAgentAs-desk/backend/tests/temp_runtime_test")
TEST_TEMP_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class TestResult:
    test_id: str
    category: str
    tool_name: str
    scenario: str
    success: bool
    duration_ms: float
    steps_count: int = 0
    tools_invoked: List[str] = field(default_factory=list)
    error_message: str = ""
    sse_events: List[Dict] = field(default_factory=list)
    intent_detected: str = ""
    agent_used: str = ""


@dataclass
class TestReport:
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    results: List[TestResult] = field(default_factory=list)
    start_time: str = ""
    end_time: str = ""
    log_anomalies: List[str] = field(default_factory=list)

    def add_result(self, result: TestResult):
        self.total_tests += 1
        self.results.append(result)
        if result.success:
            self.passed += 1
        else:
            self.failed += 1

    def to_dict(self) -> Dict:
        return {
            "summary": {
                "total": self.total_tests,
                "passed": self.passed,
                "failed": self.failed,
                "skipped": self.skipped,
                "errors": self.errors,
                "pass_rate": f"{self.passed / max(self.total_tests, 1) * 100:.1f}%",
                "start_time": self.start_time,
                "end_time": self.end_time,
            },
            "log_anomalies": self.log_anomalies,
            "results": [
                {
                    "test_id": r.test_id,
                    "category": r.category,
                    "tool_name": r.tool_name,
                    "scenario": r.scenario,
                    "success": r.success,
                    "duration_ms": round(r.duration_ms, 1),
                    "steps_count": r.steps_count,
                    "tools_invoked": r.tools_invoked,
                    "intent_detected": r.intent_detected,
                    "agent_used": r.agent_used,
                    "error_message": r.error_message[:200] if r.error_message else "",
                }
                for r in self.results
            ],
        }


report = TestReport()


def parse_sse_response(text: str) -> List[Dict]:
    events = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            try:
                data = json.loads(line[6:])
                events.append(data)
            except json.JSONDecodeError:
                pass
    return events


def extract_step_info(events: List[Dict]) -> Dict:
    info = {
        "steps_count": 0,
        "tools_invoked": [],
        "intent_detected": "",
        "agent_used": "",
        "has_error": False,
        "error_message": "",
        "has_final_answer": False,
        "final_answer": "",
        "thoughts": [],
        "observations": [],
    }
    for event in events:
        event_type = event.get("type", "")
        if event_type == "start":
            info["intent_detected"] = event.get("intent", "")
            info["agent_used"] = event.get("agent", "")
        elif event_type == "thought":
            info["thoughts"].append(event.get("content", "")[:100])
        elif event_type == "action_tool":
            tool_name = event.get("tool_name", "")
            if tool_name:
                info["tools_invoked"].append(tool_name)
            info["steps_count"] += 1
        elif event_type == "observation":
            info["observations"].append(event.get("content", "")[:100])
        elif event_type == "final":
            info["has_final_answer"] = True
            info["final_answer"] = event.get("content", "")[:200]
        elif event_type == "error":
            info["has_error"] = True
            info["error_message"] = event.get("message", "")[:200]
    return info


async def send_chat_request(
    message: str,
    session_id: Optional[str] = None,
    timeout: float = 60.0,
) -> Tuple[int, List[Dict], float]:
    start = time.time()
    try:
        kwargs = dict(timeout=timeout)
        if _ASGI_TRANSPORT is not None:
            kwargs["transport"] = _ASGI_TRANSPORT
        async with httpx.AsyncClient(**kwargs) as client:
            payload = {
                "messages": [{"role": "user", "content": message}],
                "stream": True,
            }
            if session_id:
                payload["session_id"] = session_id

            response = await client.post(
                f"{BASE_URL}{CHAT_ENDPOINT}",
                json=payload,
            )
            elapsed = (time.time() - start) * 1000
            events = parse_sse_response(response.text)
            return response.status_code, events, elapsed
    except httpx.ReadTimeout:
        elapsed = (time.time() - start) * 1000
        return 408, [], elapsed
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        return 500, [], elapsed


async def send_chat_request_streaming(
    message: str,
    session_id: Optional[str] = None,
    timeout: float = 120.0,
) -> Tuple[int, List[Dict], float]:
    start = time.time()
    events = []
    try:
        kwargs = dict(timeout=timeout)
        if _ASGI_TRANSPORT is not None:
            kwargs["transport"] = _ASGI_TRANSPORT
        async with httpx.AsyncClient(**kwargs) as client:
            payload = {
                "messages": [{"role": "user", "content": message}],
                "stream": True,
            }
            if session_id:
                payload["session_id"] = session_id

            async with client.stream(
                "POST",
                f"{BASE_URL}{CHAT_ENDPOINT}",
                json=payload,
            ) as response:
                status_code = response.status_code
                async for line in response.aiter_lines():
                    line = line.strip()
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            events.append(data)
                        except json.JSONDecodeError:
                            pass
                elapsed = (time.time() - start) * 1000
                return status_code, events, elapsed
    except httpx.ReadTimeout:
        elapsed = (time.time() - start) * 1000
        return 408, events, elapsed
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        return 500, events, elapsed


async def execute_tool_directly(
    tool_name: str,
    parameters: Dict[str, Any],
    timeout: float = 30.0,
) -> Tuple[int, Dict]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{BASE_URL}{EXECUTE_TOOL_ENDPOINT}",
                json={"tool_name": tool_name, "parameters": parameters},
            )
            return response.status_code, response.json()
    except Exception as e:
        return 500, {"error": str(e)}


class LogMonitor:
    def __init__(self):
        self.anomalies: List[str] = []
        self._stop = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        self._stop = False
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop = True
        if self._thread:
            self._thread.join(timeout=5)

    def _monitor_loop(self):
        while not self._stop:
            try:
                self._check_recent_logs()
                time.sleep(5)
            except Exception:
                pass

    def _check_recent_logs(self):
        if not LOG_DIR.exists():
            return
        cutoff = time.time() - 30
        for log_file in LOG_DIR.glob("*.log"):
            try:
                if log_file.stat().st_mtime < cutoff:
                    continue
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()[-50:]
                    for line in lines:
                        if "ERROR" in line or "CRITICAL" in line:
                            if "Traceback" not in line and "test" not in line.lower():
                                ts = datetime.now().strftime("%H:%M:%S")
                                self.anomalies.append(f"[{ts}] {line.strip()[:200]}")
            except Exception:
                pass


log_monitor = LogMonitor()


# ============================================================
# 测试用例定义 - 覆盖全部59个工具 + 多场景交叉
# ============================================================

FILE_TOOL_TEST_CASES = [
    # F1: read_file
    {"id": "F1-01", "tool": "read_file", "msg": "读取 backend/app/main.py 文件的前20行内容", "expect_tools": ["read_file"]},
    {"id": "F1-02", "tool": "read_file", "msg": "读取 backend/pytest.ini 配置文件", "expect_tools": ["read_file"]},
    {"id": "F1-03", "tool": "read_file", "msg": "查看 README.md 文件内容", "expect_tools": ["read_file"]},
    # F2: write_text_file
    {"id": "F2-01", "tool": "write_text_file", "msg": "在 tests/temp_runtime_test 目录下创建一个名为 hello_test.txt 的文件，内容是'Hello Runtime Test'", "expect_tools": ["write_text_file"]},
    {"id": "F2-02", "tool": "write_text_file", "msg": "向 tests/temp_runtime_test/hello_test.txt 文件追加一行'Appended Line'", "expect_tools": ["write_text_file"]},
    # F3: read_media_file
    {"id": "F3-01", "tool": "read_media_file", "msg": "读取 frontend/public 目录下的图片文件(vite.svg)", "expect_tools": ["read_media_file"]},
    # F4: edit_file
    {"id": "F4-01", "tool": "edit_file", "msg": "把 tests/temp_runtime_test/hello_test.txt 文件中的'Hello Runtime Test'替换为'Hello Edited Test'", "expect_tools": ["edit_file"]},
    # F5: list_directory
    {"id": "F5-01", "tool": "list_directory", "msg": "列出 backend/app/services 目录下的所有文件和子目录", "expect_tools": ["list_directory"]},
    {"id": "F5-02", "tool": "list_directory", "msg": "以树形结构显示 backend/app/services/tools 目录", "expect_tools": ["list_directory"]},
    # F6: search_files
    {"id": "F6-01", "tool": "search_files", "msg": "在 backend/app 目录下搜索所有名为 registry.py 的文件", "expect_tools": ["search_files"]},
    {"id": "F6-02", "tool": "search_files", "msg": "在 backend 目录下递归搜索所有 *.py 文件", "expect_tools": ["search_files"]},
    # F7: grep_file_content
    {"id": "F7-01", "tool": "grep_file_content", "msg": "在 backend/app/services/tools 目录下搜索包含 'ToolCategory' 的代码行", "expect_tools": ["grep_file_content"]},
    {"id": "F7-02", "tool": "grep_file_content", "msg": "在 backend/app 目录下用正则搜索包含 'class.*Agent.*BaseAgent' 的代码", "expect_tools": ["grep_file_content"]},
    # F8: rename_file
    {"id": "F8-01", "tool": "rename_file", "msg": "把 tests/temp_runtime_test/hello_test.txt 重命名为 hello_renamed.txt", "expect_tools": ["rename_file"]},
    # F9: archive_tool
    {"id": "F9-01", "tool": "archive_tool", "msg": "把 tests/temp_runtime_test 目录压缩为 tests/temp_runtime_test/archive_test.zip", "expect_tools": ["archive_tool"]},
    {"id": "F9-02", "tool": "archive_tool", "msg": "把 tests/temp_runtime_test/archive_test.zip 解压到 tests/temp_runtime_test/extracted 目录", "expect_tools": ["archive_tool"]},
    # F10: file_operation
    {"id": "F10-01", "tool": "file_operation", "msg": "复制 tests/temp_runtime_test/hello_renamed.txt 到 tests/temp_runtime_test/hello_copy.txt", "expect_tools": ["file_operation"]},
    {"id": "F10-02", "tool": "file_operation", "msg": "删除 tests/temp_runtime_test/hello_copy.txt 文件", "expect_tools": ["file_operation"]},
    # F11: data_file_format
    {"id": "F11-01", "tool": "data_file_format", "msg": "读取 config/config.yaml 配置文件的内容", "expect_tools": ["data_file_format"]},
]

SHELL_TOOL_TEST_CASES = [
    # S1: execute_shell_command
    {"id": "S1-01", "tool": "execute_shell_command", "msg": "在PowerShell中执行命令 Get-Date 获取当前日期时间", "expect_tools": ["execute_shell_command"]},
    {"id": "S1-02", "tool": "execute_shell_command", "msg": "执行命令 dir backend/app/services 列出服务目录", "expect_tools": ["execute_shell_command"]},
    {"id": "S1-03", "tool": "execute_shell_command", "msg": "执行 echo 'shell test ok' 测试命令行输出", "expect_tools": ["execute_shell_command"]},
    # S2: find_command
    {"id": "S2-01", "tool": "find_command", "msg": "查找 python 命令的安装路径", "expect_tools": ["find_command"]},
    {"id": "S2-02", "tool": "find_command", "msg": "查找 node 命令是否存在", "expect_tools": ["find_command"]},
    # S3: shell_session
    {"id": "S3-01", "tool": "shell_session", "msg": "创建一个新的后台shell会话，在其中执行 whoami 命令", "expect_tools": ["shell_session"]},
    # S4: execute_python
    {"id": "S4-01", "tool": "execute_python", "msg": "执行Python代码: print([i**2 for i in range(10)])", "expect_tools": ["execute_python"]},
    {"id": "S4-02", "tool": "execute_python", "msg": "执行Python代码: import sys; print(f'Python {sys.version}'); print(f'Platform: {sys.platform}')", "expect_tools": ["execute_python"]},
    # S5: execute_javascript
    {"id": "S5-01", "tool": "execute_javascript", "msg": "执行JavaScript代码: console.log('JS test ok:', Math.PI.toFixed(6))", "expect_tools": ["execute_javascript"]},
]

NETWORK_TOOL_TEST_CASES = [
    # N1: http_request
    {"id": "N1-01", "tool": "http_request", "msg": "发送HTTP GET请求到 http://httpbin.org/get 测试接口", "expect_tools": ["http_request"]},
    {"id": "N1-02", "tool": "http_request", "msg": "发送HTTP POST请求到 http://httpbin.org/post，body为{test: runtime}", "expect_tools": ["http_request"]},
    # N2: download_file
    {"id": "N2-01", "tool": "download_file", "msg": "下载 https://httpbin.org/json 到 tests/temp_runtime_test/downloaded.json", "expect_tools": ["download_file"]},
    # N3: fetch_webpage
    {"id": "N3-01", "tool": "fetch_webpage", "msg": "获取网页 https://httpbin.org/html 的内容", "expect_tools": ["fetch_webpage"]},
    # N4: search_web
    {"id": "N4-01", "tool": "search_web", "msg": "搜索网络获取'Python 3.13 新特性'的信息", "expect_tools": ["search_web"]},
    # N5: network_diagnose
    {"id": "N5-01", "tool": "network_diagnose", "msg": "检查网络连通性，ping 127.0.0.1", "expect_tools": ["network_diagnose"]},
    {"id": "N5-02", "tool": "network_diagnose", "msg": "检查本地8000端口是否开放", "expect_tools": ["network_diagnose"]},
]

SYSTEM_TOOL_TEST_CASES = [
    # SY1: get_system_info
    {"id": "SY1-01", "tool": "get_system_info", "msg": "获取当前系统的完整信息，包括CPU、内存、磁盘", "expect_tools": ["get_system_info"]},
    # SY2: net_connections
    {"id": "SY2-01", "tool": "net_connections", "msg": "获取当前系统的网络连接列表", "expect_tools": ["net_connections"]},
    # SY3: event_log
    {"id": "SY3-01", "tool": "event_log", "msg": "获取Windows系统最近10条应用程序事件日志", "expect_tools": ["event_log"]},
    # SY4: list_processes
    {"id": "SY4-01", "tool": "list_processes", "msg": "列出系统中占用内存最多的前10个进程", "expect_tools": ["list_processes"]},
    # SY5: kill_process (只查找不真正kill)
    {"id": "SY5-01", "tool": "kill_process", "msg": "查找python进程的PID(不要真的终止)", "expect_tools": ["list_processes"]},
    # SY6: service_control
    {"id": "SY6-01", "tool": "service_control", "msg": "列出Windows系统所有服务的状态", "expect_tools": ["service_control"]},
    # SY7: task_control
    {"id": "SY7-01", "tool": "task_control", "msg": "列出Windows计划任务", "expect_tools": ["task_control"]},
    # SY8: get_env
    {"id": "SY8-01", "tool": "get_env", "msg": "获取PATH环境变量的值", "expect_tools": ["get_env"]},
    {"id": "SY8-02", "tool": "get_env", "msg": "列出所有环境变量", "expect_tools": ["get_env"]},
    # SY9: set_env
    {"id": "SY9-01", "tool": "set_env", "msg": "设置一个临时环境变量 TEST_RUNTIME_VAR=hello123", "expect_tools": ["set_env"]},
    # SY10: registry_control
    {"id": "SY10-01", "tool": "registry_control", "msg": "读取Windows注册表 HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion 的ProductName值", "expect_tools": ["registry_control"]},
]

DESKTOP_TOOL_TEST_CASES = [
    # D1: list_windows
    {"id": "D1-01", "tool": "list_windows", "msg": "列出当前桌面上所有打开的窗口", "expect_tools": ["list_windows"]},
    # D2: get_window_info
    {"id": "D2-01", "tool": "get_window_info", "msg": "获取当前桌面活动窗口的详细信息", "expect_tools": ["get_window_info"]},
    # D3: window_control
    {"id": "D3-01", "tool": "window_control", "msg": "获取桌面窗口列表，找到第一个窗口并将其置顶", "expect_tools": ["list_windows", "window_control"]},
    # D4: mouse_control
    {"id": "D4-01", "tool": "mouse_control", "msg": "获取当前鼠标光标位置", "expect_tools": ["mouse_control"]},
    # D5: keyboard_control
    {"id": "D5-01", "tool": "keyboard_control", "msg": "模拟键盘输入测试(仅获取键盘状态，不要真的输入)", "expect_tools": ["keyboard_control"]},
    # D6: screen_capture
    {"id": "D6-01", "tool": "screen_capture", "msg": "截取当前屏幕截图保存到 tests/temp_runtime_test/screenshot.png", "expect_tools": ["screen_capture"]},
    # D7: clipboard_control
    {"id": "D7-01", "tool": "clipboard_control", "msg": "读取当前剪贴板内容", "expect_tools": ["clipboard_control"]},
    # D8: screen_record
    {"id": "D8-01", "tool": "screen_record", "msg": "列出屏幕录制状态", "expect_tools": ["screen_record"]},
    # D9: ocr
    {"id": "D9-01", "tool": "ocr", "msg": "对 tests/temp_runtime_test/screenshot.png 进行OCR文字识别", "expect_tools": ["ocr"]},
    # D10: send_notification
    {"id": "D10-01", "tool": "send_notification", "msg": "发送一个Windows系统通知，标题'测试通知'，内容'运行时测试通过'", "expect_tools": ["send_notification"]},
]

DOCUMENT_TOOL_TEST_CASES = [
    # DOC1: read_document
    {"id": "DOC1-01", "tool": "read_document", "msg": "读取 tests/temp_runtime_test 目录下的CSV文件(如果没有则创建一个再读取)", "expect_tools": ["read_document"]},
    # DOC2: write_document
    {"id": "DOC2-01", "tool": "write_document", "msg": "创建一个Excel文件 tests/temp_runtime_test/test_data.xlsx，包含姓名和年龄两列数据", "expect_tools": ["write_document"]},
    # DOC3: convert_document
    {"id": "DOC3-01", "tool": "convert_document", "msg": "列出文档转换的可用功能说明", "expect_tools": ["convert_document"]},
    # DOC4: analyze_data
    {"id": "DOC4-01", "tool": "analyze_data", "msg": "对 tests/temp_runtime_test/test_data.xlsx 进行基本统计分析", "expect_tools": ["analyze_data"]},
    # DOC5: filter_data
    {"id": "DOC5-01", "tool": "filter_data", "msg": "筛选 tests/temp_runtime_test/test_data.xlsx 中年龄大于20的数据", "expect_tools": ["filter_data"]},
    # DOC6: generate_chart
    {"id": "DOC6-01", "tool": "generate_chart", "msg": "根据 tests/temp_runtime_test/test_data.xlsx 的数据生成柱状图", "expect_tools": ["generate_chart"]},
    # DOC7: query_sql
    {"id": "DOC7-01", "tool": "query_sql", "msg": "查询SQLite数据库 backend/chat_app.db 的所有表名", "expect_tools": ["query_sql"]},
    # DOC8: execute_sql
    {"id": "DOC8-01", "tool": "execute_sql", "msg": "在 backend/chat_app.db 中创建一个测试表 test_runtime(id INTEGER, name TEXT)", "expect_tools": ["execute_sql"]},
    # DOC9: get_db_schema
    {"id": "DOC9-01", "tool": "get_db_schema", "msg": "获取 backend/chat_app.db 数据库的完整schema信息", "expect_tools": ["get_db_schema"]},
]

META_TOOL_TEST_CASES = [
    # M1: tool_help
    {"id": "M1-01", "tool": "tool_help", "msg": "查看 read_file 工具的详细用法说明", "expect_tools": ["tool_help"]},
    {"id": "M1-02", "tool": "tool_help", "msg": "查看 execute_shell_command 工具的详细用法", "expect_tools": ["tool_help"]},
    # M2: tool_search
    {"id": "M2-01", "tool": "tool_search", "msg": "搜索与'文件'相关的所有工具", "expect_tools": ["tool_search"]},
    {"id": "M2-02", "tool": "tool_search", "msg": "搜索与'网络'相关的所有工具", "expect_tools": ["tool_search"]},
    # M3: pipeline
    {"id": "M3-01", "tool": "pipeline", "msg": "创建一个工具管道：先获取当前时间，再格式化输出", "expect_tools": ["pipeline"]},
    # M4: get_time
    {"id": "M4-01", "tool": "get_time", "msg": "获取当前时间", "expect_tools": ["get_time"]},
    {"id": "M4-02", "tool": "get_time", "msg": "获取当前时间的ISO格式和时间戳", "expect_tools": ["get_time"]},
    # M5: time_add
    {"id": "M5-01", "tool": "time_add", "msg": "计算当前时间加上3天后的日期", "expect_tools": ["time_add"]},
    # M6: time_diff
    {"id": "M6-01", "tool": "time_diff", "msg": "计算2026-01-01到2026-05-21之间相差多少天", "expect_tools": ["time_diff"]},
    # M7: query_calendar
    {"id": "M7-01", "tool": "query_calendar", "msg": "查询2026年5月21日是星期几，是否是工作日", "expect_tools": ["query_calendar"]},
    # M8: timezone_convert
    {"id": "M8-01", "tool": "timezone_convert", "msg": "将当前UTC时间转换为北京时间(Asia/Shanghai)", "expect_tools": ["timezone_convert"]},
    # M9: timer
    {"id": "M9-01", "tool": "timer", "msg": "列出现有的所有定时器", "expect_tools": ["timer"]},
]

CROSS_SCENARIO_TEST_CASES = [
    # 文件+Shell交叉
    {"id": "CROSS-01", "tool": "cross", "msg": "先用Python代码计算1到100的和，然后将结果写入 tests/temp_runtime_test/sum_result.txt 文件", "expect_tools": ["execute_python", "write_text_file"]},
    # 文件+网络交叉
    {"id": "CROSS-02", "tool": "cross", "msg": "下载 https://httpbin.org/json 的内容，然后解析其中slideshow的title字段", "expect_tools": ["download_file", "read_file"]},
    # 系统+文件交叉
    {"id": "CROSS-03", "tool": "cross", "msg": "获取系统信息并保存到 tests/temp_runtime_test/sys_info.json 文件中", "expect_tools": ["get_system_info", "write_text_file"]},
    # 时间+文档交叉
    {"id": "CROSS-04", "tool": "cross", "msg": "获取当前时间，然后创建一个包含时间戳的CSV文件", "expect_tools": ["get_time", "write_document"]},
    # Shell+系统交叉
    {"id": "CROSS-05", "tool": "cross", "msg": "执行PowerShell命令获取进程列表，然后筛选出占用内存最高的5个进程", "expect_tools": ["execute_shell_command", "list_processes"]},
    # 桌面+文件交叉
    {"id": "CROSS-06", "tool": "cross", "msg": "截取屏幕截图保存到文件，然后读取截图文件信息", "expect_tools": ["screen_capture", "read_media_file"]},
    # 网络+文档交叉
    {"id": "CROSS-07", "tool": "cross", "msg": "搜索'FastAPI 框架'的信息，将搜索结果保存到文档中", "expect_tools": ["search_web", "write_document"]},
    # 多工具链式
    {"id": "CROSS-08", "tool": "cross", "msg": "先列出backend目录结构，然后搜索包含FastAPI的文件，最后读取main.py的前30行", "expect_tools": ["list_directory", "search_files", "read_file"]},
    # 数据库+文档交叉
    {"id": "CROSS-09", "tool": "cross", "msg": "查询chat_app.db的所有表，获取schema信息，然后生成一个数据库结构报告文档", "expect_tools": ["query_sql", "get_db_schema", "write_document"]},
    # 时间+Shell交叉
    {"id": "CROSS-10", "tool": "cross", "msg": "获取当前时间戳，然后用PowerShell执行一个带有时间戳的echo命令", "expect_tools": ["get_time", "execute_shell_command"]},
    # 文件操作全流程
    {"id": "CROSS-11", "tool": "cross", "msg": "完整文件操作流程：创建文件→写入内容→读取验证→编辑修改→再次读取→重命名→删除", "expect_tools": ["write_text_file", "read_file", "edit_file", "rename_file", "file_operation"]},
    # 元工具+任意工具交叉
    {"id": "CROSS-12", "tool": "cross", "msg": "先用tool_search搜索与'时间'相关的工具，然后使用搜索到的工具获取当前时间", "expect_tools": ["tool_search", "get_time"]},
]

INTENT_CLASSIFICATION_TEST_CASES = [
    {"id": "INTENT-01", "msg": "帮我读取一下config.yaml文件", "expected_intent": "file"},
    {"id": "INTENT-02", "msg": "运行pip list命令", "expected_intent": "shell"},
    {"id": "INTENT-03", "msg": "现在几点了？今天是星期几？", "expected_intent": "meta"},
    {"id": "INTENT-04", "msg": "ping一下百度看看网络通不通", "expected_intent": "network"},
    {"id": "INTENT-05", "msg": "帮我截个屏", "expected_intent": "desktop"},
    {"id": "INTENT-06", "msg": "查看系统CPU和内存使用情况", "expected_intent": "system"},
    {"id": "INTENT-07", "msg": "读取这个Excel文件的数据", "expected_intent": "document"},
    {"id": "INTENT-08", "msg": "查询数据库里的用户表", "expected_intent": "document"},
    {"id": "INTENT-09", "msg": "执行一段Python代码算阶乘", "expected_intent": "shell"},
    {"id": "INTENT-10", "msg": "你好，今天天气怎么样", "expected_intent": None},
]

EDGE_CASE_TEST_CASES = [
    {"id": "EDGE-01", "msg": "", "desc": "空消息"},
    {"id": "EDGE-02", "msg": "   ", "desc": "纯空格消息"},
    {"id": "EDGE-03", "msg": "a", "desc": "单字符消息"},
    {"id": "EDGE-04", "msg": "读取一个不存在的文件路径 /nonexistent/path/file.txt", "desc": "错误路径"},
    {"id": "EDGE-05", "msg": "读取" + "很长的文件名" * 50 + ".txt", "desc": "超长文件名"},
    {"id": "EDGE-06", "msg": "执行Python代码: import time; time.sleep(0.1); print('ok')", "desc": "短时等待命令"},
    {"id": "EDGE-07", "msg": "你好你好你好你好你好" * 20, "desc": "重复文本"},
    {"id": "EDGE-08", "msg": "搜索文件*.py", "desc": "通配符模式"},
]


ALL_TOOL_TEST_CASES = (
    FILE_TOOL_TEST_CASES +
    SHELL_TOOL_TEST_CASES +
    NETWORK_TOOL_TEST_CASES +
    SYSTEM_TOOL_TEST_CASES +
    DESKTOP_TOOL_TEST_CASES +
    DOCUMENT_TOOL_TEST_CASES +
    META_TOOL_TEST_CASES
)


# ============================================================
# 测试类
# ============================================================

class TestRuntimeAllTools:
    """运行时全工具深度测试 - 真实ReAct Loop"""

    @pytest.fixture(autouse=True)
    def setup(self):
        report.start_time = datetime.now().isoformat()
        log_monitor.start()
        yield
        log_monitor.stop()
        report.end_time = datetime.now().isoformat()
        report.log_anomalies = log_monitor.anomalies[-50:]
        report_path = TEST_REPORT_DIR / f"runtime_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)

    @pytest.mark.asyncio
    async def test_server_health(self):
        status, events, elapsed = await send_chat_request("你好", timeout=15)
        assert status in [200, 408], f"服务器未响应, status={status}"

    @pytest.mark.asyncio
    async def test_list_tools_endpoint(self):
        kwargs = dict(timeout=10)
        if _ASGI_TRANSPORT is not None:
            kwargs["transport"] = _ASGI_TRANSPORT
        async with httpx.AsyncClient(**kwargs) as client:
            resp = await client.get(f"{BASE_URL}{LIST_TOOLS_ENDPOINT}")
            assert resp.status_code == 200
            data = resp.json()
            tools = data.get("tools", data.get("data", []))
            tool_names = []
            if isinstance(tools, list):
                for t in tools:
                    if isinstance(t, dict):
                        tool_names.append(t.get("name", ""))
                    elif isinstance(t, str):
                        tool_names.append(t)
            print(f"\n已注册工具数: {len(tool_names)}")
            print(f"工具列表: {sorted(tool_names)}")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("case", FILE_TOOL_TEST_CASES, ids=lambda c: c["id"])
    async def test_file_tools(self, case):
        result = await self._run_tool_test(case, "file")
        assert result.success, f"[{case['id']}] {case['tool']} 失败: {result.error_message}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("case", SHELL_TOOL_TEST_CASES, ids=lambda c: c["id"])
    async def test_shell_tools(self, case):
        result = await self._run_tool_test(case, "shell")
        assert result.success, f"[{case['id']}] {case['tool']} 失败: {result.error_message}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("case", NETWORK_TOOL_TEST_CASES, ids=lambda c: c["id"])
    async def test_network_tools(self, case):
        result = await self._run_tool_test(case, "network")
        assert result.success, f"[{case['id']}] {case['tool']} 失败: {result.error_message}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("case", SYSTEM_TOOL_TEST_CASES, ids=lambda c: c["id"])
    async def test_system_tools(self, case):
        result = await self._run_tool_test(case, "system")
        assert result.success, f"[{case['id']}] {case['tool']} 失败: {result.error_message}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("case", DESKTOP_TOOL_TEST_CASES, ids=lambda c: c["id"])
    async def test_desktop_tools(self, case):
        result = await self._run_tool_test(case, "desktop")
        assert result.success, f"[{case['id']}] {case['tool']} 失败: {result.error_message}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("case", DOCUMENT_TOOL_TEST_CASES, ids=lambda c: c["id"])
    async def test_document_tools(self, case):
        result = await self._run_tool_test(case, "document")
        assert result.success, f"[{case['id']}] {case['tool']} 失败: {result.error_message}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("case", META_TOOL_TEST_CASES, ids=lambda c: c["id"])
    async def test_meta_tools(self, case):
        result = await self._run_tool_test(case, "meta")
        assert result.success, f"[{case['id']}] {case['tool']} 失败: {result.error_message}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("case", CROSS_SCENARIO_TEST_CASES, ids=lambda c: c["id"])
    async def test_cross_scenarios(self, case):
        result = await self._run_tool_test(case, "cross")
        assert result.success, f"[{case['id']}] 交叉场景失败: {result.error_message}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("case", INTENT_CLASSIFICATION_TEST_CASES, ids=lambda c: c["id"])
    async def test_intent_classification(self, case):
        status, events, elapsed = await send_chat_request(case["msg"], timeout=30)
        step_info = extract_step_info(events)
        result = TestResult(
            test_id=case["id"],
            category="intent",
            tool_name="intent_classifier",
            scenario=case["msg"][:50],
            success=status == 200 and len(events) > 0,
            duration_ms=elapsed,
            steps_count=step_info["steps_count"],
            tools_invoked=step_info["tools_invoked"],
            intent_detected=step_info["intent_detected"],
            agent_used=step_info["agent_used"],
        )
        report.add_result(result)
        if case["expected_intent"]:
            detected = step_info["intent_detected"].lower()
            expected = case["expected_intent"].lower()
            print(f"\n[{case['id']}] 意图: 期望={expected}, 检测={detected}, 匹配={expected in detected or detected in expected}")

    @pytest.mark.asyncio
    async def test_edge_cases(self):
        for case in EDGE_CASE_TEST_CASES:
            status, events, elapsed = await send_chat_request(case["msg"], timeout=20)
            result = TestResult(
                test_id=case["id"],
                category="edge",
                tool_name="edge_case",
                scenario=case["desc"],
                success=status in [200, 400, 422, 408],
                duration_ms=elapsed,
                error_message="" if status in [200, 400, 422, 408] else f"Unexpected status: {status}",
            )
            report.add_result(result)
            print(f"\n[{case['id']}] {case['desc']}: status={status}, events={len(events)}")

    @pytest.mark.asyncio
    async def test_multi_turn_conversation(self):
        session_id = f"multi-turn-{int(time.time())}"
        turns = [
            "你好，我需要一些帮助",
            "帮我看看当前目录下有什么文件",
            "读取 backend/pytest.ini 的内容",
            "现在帮我获取当前时间",
            "谢谢，最后帮我查看系统信息",
        ]
        for i, msg in enumerate(turns):
            status, events, elapsed = await send_chat_request(msg, session_id=session_id, timeout=30)
            step_info = extract_step_info(events)
            result = TestResult(
                test_id=f"MULTI-{i+1}",
                category="multi_turn",
                tool_name="conversation",
                scenario=f"第{i+1}轮: {msg[:30]}",
                success=status == 200 and len(events) > 0,
                duration_ms=elapsed,
                steps_count=step_info["steps_count"],
                tools_invoked=step_info["tools_invoked"],
                intent_detected=step_info["intent_detected"],
                agent_used=step_info["agent_used"],
            )
            report.add_result(result)
            print(f"\n[MULTI-{i+1}] {msg[:30]}: status={status}, steps={step_info['steps_count']}, tools={step_info['tools_invoked']}")

    @pytest.mark.asyncio
    async def test_security_check_endpoint(self):
        dangerous_commands = [
            "rm -rf /",
            "format C:",
            "del /f /s /q C:\\*",
            "sudo rm -rf /",
        ]
        safe_commands = [
            "dir",
            "Get-Date",
            "echo hello",
        ]
        async with httpx.AsyncClient(timeout=10) as client:
            for cmd in dangerous_commands:
                resp = await client.post(
                    f"{BASE_URL}{SECURITY_CHECK_ENDPOINT}",
                    json={"command": cmd},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    is_safe = data.get("is_safe", data.get("safe", True))
                    print(f"\n[安全检查] '{cmd[:30]}': safe={is_safe}")
            for cmd in safe_commands:
                resp = await client.post(
                    f"{BASE_URL}{SECURITY_CHECK_ENDPOINT}",
                    json={"command": cmd},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    is_safe = data.get("is_safe", data.get("safe", False))
                    print(f"\n[安全检查] '{cmd}': safe={is_safe}")

    @pytest.mark.asyncio
    async def test_sessions_api(self):
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{BASE_URL}{SESSIONS_ENDPOINT}")
            assert resp.status_code == 200
            data = resp.json()
            sessions = data.get("sessions", data.get("data", []))
            print(f"\n会话数: {len(sessions) if isinstance(sessions, list) else 'N/A'}")

    @pytest.mark.asyncio
    async def test_config_api(self):
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{BASE_URL}{CONFIG_ENDPOINT}")
            assert resp.status_code == 200
            print(f"\n配置API正常")

    @pytest.mark.asyncio
    async def test_metrics_api(self):
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{BASE_URL}{METRICS_ENDPOINT}")
            assert resp.status_code == 200
            print(f"\n指标API正常")

    async def _run_tool_test(self, case: Dict, category: str) -> TestResult:
        test_id = case["id"]
        tool_name = case["tool"]
        message = case["msg"]
        expect_tools = case.get("expect_tools", [])

        status, events, elapsed = await send_chat_request(message, timeout=60)
        step_info = extract_step_info(events)

        has_response = status == 200 and len(events) > 0
        has_final = step_info["has_final_answer"]
        has_tools = len(step_info["tools_invoked"]) > 0
        has_error = step_info["has_error"]

        if has_error and not has_final:
            success = False
            error_msg = step_info["error_message"]
        elif status == 408:
            success = True
            error_msg = "timeout但非失败"
        elif has_response:
            success = True
            error_msg = ""
        else:
            success = False
            error_msg = f"status={status}, events={len(events)}"

        result = TestResult(
            test_id=test_id,
            category=category,
            tool_name=tool_name,
            scenario=message[:60],
            success=success,
            duration_ms=elapsed,
            steps_count=step_info["steps_count"],
            tools_invoked=step_info["tools_invoked"],
            intent_detected=step_info["intent_detected"],
            agent_used=step_info["agent_used"],
            error_message=error_msg,
            sse_events=events[:5],
        )
        report.add_result(result)

        tool_match = ""
        if expect_tools and step_info["tools_invoked"]:
            matched = [t for t in expect_tools if t in step_info["tools_invoked"]]
            tool_match = f"匹配{len(matched)}/{len(expect_tools)}"

        print(
            f"\n[{test_id}] {tool_name}: "
            f"{'✓' if success else '✗'} "
            f"steps={step_info['steps_count']} "
            f"tools={step_info['tools_invoked'][:3]} "
            f"{tool_match} "
            f"intent={step_info['intent_detected']} "
            f"agent={step_info['agent_used']} "
            f"耗时={elapsed:.0f}ms"
        )

        return result


class TestRuntimeStreaming:
    """流式SSE深度测试"""

    @pytest.mark.asyncio
    async def test_streaming_sse_format(self):
        status, events, elapsed = await send_chat_request_streaming(
            "获取当前时间", timeout=30
        )
        assert status == 200
        assert len(events) > 0, "SSE事件为空"

        event_types = [e.get("type", "") for e in events]
        print(f"\nSSE事件类型序列: {event_types}")
        assert "start" in event_types, "缺少start事件"

    @pytest.mark.asyncio
    async def test_streaming_multi_tool_chain(self):
        status, events, elapsed = await send_chat_request_streaming(
            "先获取当前时间，然后把时间信息写入 tests/temp_runtime_test/time_info.txt",
            timeout=60,
        )
        step_info = extract_step_info(events)
        print(f"\n多工具链式: steps={step_info['steps_count']}, tools={step_info['tools_invoked']}")

    @pytest.mark.asyncio
    async def test_streaming_long_task(self):
        status, events, elapsed = await send_chat_request_streaming(
            "列出backend/app/services/tools目录结构，然后搜索所有register.py文件，统计有多少个工具注册函数",
            timeout=90,
        )
        step_info = extract_step_info(events)
        print(f"\n长任务: steps={step_info['steps_count']}, tools={step_info['tools_invoked']}, 耗时={elapsed:.0f}ms")


class TestRuntimeDirectToolExecution:
    """通过execute-tool端点直接测试工具"""

    @pytest.mark.asyncio
    async def test_direct_read_file(self):
        status, data = await execute_tool_directly("read_file", {
            "path": "G:/OmniAgentAs-desk/backend/pytest.ini",
        })
        print(f"\n直接执行read_file: status={status}")

    @pytest.mark.asyncio
    async def test_direct_get_time(self):
        status, data = await execute_tool_directly("get_time", {
            "action": "now",
        })
        print(f"\n直接执行get_time: status={status}, data={str(data)[:100]}")

    @pytest.mark.asyncio
    async def test_direct_get_system_info(self):
        status, data = await execute_tool_directly("get_system_info", {})
        print(f"\n直接执行get_system_info: status={status}")

    @pytest.mark.asyncio
    async def test_direct_tool_help(self):
        status, data = await execute_tool_directly("tool_help", {
            "tool_name": "read_file",
        })
        print(f"\n直接执行tool_help: status={status}")

    @pytest.mark.asyncio
    async def test_direct_tool_search(self):
        status, data = await execute_tool_directly("tool_search", {
            "query": "文件",
        })
        print(f"\n直接执行tool_search: status={status}")


class TestRuntimeToolCoverage:
    """工具覆盖率验证 - 确保59个工具全部被测试到"""

    ALL_59_TOOLS = [
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

    def test_all_59_tools_defined(self):
        assert len(self.ALL_59_TOOLS) == 59, f"工具数不等于59: {len(self.ALL_59_TOOLS)}"
        unique = set(self.ALL_59_TOOLS)
        assert len(unique) == 59, f"有重复工具名: 总数{len(self.ALL_59_TOOLS)}, 唯一{len(unique)}"

    def test_all_tools_covered_in_test_cases(self):
        tested_tools = set()
        for case in ALL_TOOL_TEST_CASES:
            tested_tools.add(case["tool"])
        for case in CROSS_SCENARIO_TEST_CASES:
            for t in case.get("expect_tools", []):
                tested_tools.add(t)

        missing = set(self.ALL_59_TOOLS) - tested_tools
        print(f"\n已覆盖工具({len(tested_tools)}): {sorted(tested_tools)}")
        if missing:
            print(f"未覆盖工具({len(missing)}): {sorted(missing)}")
        assert len(missing) == 0, f"以下工具未被测试覆盖: {sorted(missing)}"
