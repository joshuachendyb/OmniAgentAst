# -*- coding: utf-8 -*-
"""
错误收集器 — 从app log、SSE事件、进程状态等多维度收集错误信息

设计思路：
1. AppLogCollector: 读取 backend/logs/app_*.log 中的ERROR/WARNING
2. SSEEventCollector: 从SSE流中提取error类型事件和异常action_tool
3. ProcessCollector: 检查后端/Ollama进程是否存活
4. PromptLogCollector: 读取 backend/logs/prompt-logs/ 中的异常prompt

小健 2026-05-24
"""
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
PROMPT_LOG_DIR = LOG_DIR / "prompt-logs"
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass
class ErrorRecord:
    source: str
    timestamp: str
    level: str
    message: str
    detail: str = ""
    file_path: str = ""
    line_no: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "timestamp": self.timestamp,
            "level": self.level,
            "message": self.message,
            "detail": self.detail[:500],
            "file_path": self.file_path,
            "line_no": self.line_no,
        }


class AppLogCollector:
    """从 app_*.log 收集 ERROR 和 WARNING"""

    LOG_PATTERN = re.compile(
        r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s*-\s*(\w+)\s*-\s*(.+?)\s*-\s*(.+)$"
    )

    def __init__(self, log_dir: Optional[Path] = None, min_level: str = "WARNING"):
        self.log_dir = log_dir or LOG_DIR
        self.min_level = min_level
        self._level_order = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}

    def collect(self, since: Optional[datetime] = None) -> List[ErrorRecord]:
        errors = []
        if not self.log_dir.exists():
            return errors

        for log_file in sorted(self.log_dir.glob("app_*.log")):
            try:
                file_date_str = log_file.stem.replace("app_", "")
                file_date = datetime.strptime(file_date_str, "%Y-%m-%d")
                if since and file_date < since:
                    continue
            except ValueError:
                pass

            try:
                content = log_file.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            for line in content.splitlines():
                m = self.LOG_PATTERN.match(line)
                if not m:
                    continue
                ts_str, level, location, message = m.groups()
                if self._level_order.get(level, 0) < self._level_order.get(self.min_level, 2):
                    continue
                if since:
                    try:
                        ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                        if ts < since:
                            continue
                    except ValueError:
                        pass

                errors.append(ErrorRecord(
                    source="app_log",
                    timestamp=ts_str,
                    level=level,
                    message=message[:300],
                    detail="",
                    file_path=location,
                ))

        return sorted(errors, key=lambda e: e.timestamp)


class SSEEventCollector:
    """从SSE事件列表中提取错误"""

    def collect(self, events: List[Dict[str, Any]]) -> List[ErrorRecord]:
        errors = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for ev in events:
            evt_type = ev.get("type", "")

            if evt_type == "error":
                errors.append(ErrorRecord(
                    source="sse_error_event",
                    timestamp=now,
                    level="ERROR",
                    message=ev.get("message", "unknown SSE error")[:300],
                    detail=json.dumps(ev, ensure_ascii=False)[:500],
                ))

            elif evt_type == "action_tool":
                tool_name = ev.get("tool_name", "")
                tool_result = ev.get("tool_result", {})
                if isinstance(tool_result, dict):
                    code = tool_result.get("code", 0)
                    if code != 0 and code != "0":
                        errors.append(ErrorRecord(
                            source="sse_tool_error",
                            timestamp=now,
                            level="ERROR",
                            message=f"工具 {tool_name} 执行失败 code={code}",
                            detail=tool_result.get("message", "")[:500],
                        ))

            elif evt_type == "final":
                response = ev.get("response", "")
                error_keywords = ["错误", "error", "失败", "failed", "异常", "exception", "429", "500"]
                if any(kw in str(response).lower() for kw in error_keywords):
                    errors.append(ErrorRecord(
                        source="sse_final_with_error",
                        timestamp=now,
                        level="WARNING",
                        message=f"final事件含错误关键词: {str(response)[:200]}",
                        detail="",
                    ))

        return errors


class ProcessCollector:
    """检查后端和Ollama进程状态"""

    def collect(self) -> List[ErrorRecord]:
        errors = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            result = subprocess.run(
                ["powershell", "-Command", "Get-Process -Name 'python' -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,StartTime | ConvertTo-Json"],
                capture_output=True, text=True, timeout=5
            )
            procs = json.loads(result.stdout) if result.stdout.strip() else []
            if not isinstance(procs, list):
                procs = [procs]
            uvicorn_found = False
            for p in procs:
                start_time = p.get("StartTime", "")
                if start_time:
                    uvicorn_found = True
            if not uvicorn_found and not procs:
                errors.append(ErrorRecord(
                    source="process_check",
                    timestamp=now, level="WARNING",
                    message="未发现运行中的Python进程（uvicorn可能未启动）",
                ))
        except Exception as e:
            errors.append(ErrorRecord(
                source="process_check",
                timestamp=now, level="WARNING",
                message=f"进程检查失败: {e}",
            ))

        try:
            import httpx
            resp = httpx.get("http://localhost:11434/api/tags", timeout=5)
            if resp.status_code != 200:
                errors.append(ErrorRecord(
                    source="process_check",
                    timestamp=now, level="ERROR",
                    message=f"Ollama服务异常: HTTP {resp.status_code}",
                ))
            else:
                models = [m["name"] for m in resp.json().get("models", [])]
                if "qwen2.5:1.5b" not in models:
                    errors.append(ErrorRecord(
                        source="process_check",
                        timestamp=now, level="ERROR",
                        message=f"qwen2.5:1.5b 模型不可用，现有模型: {models}",
                    ))
        except Exception as e:
            errors.append(ErrorRecord(
                source="process_check",
                timestamp=now, level="ERROR",
                message=f"Ollama服务不可达: {e}",
            ))

        return errors


class PromptLogCollector:
    """从 prompt-logs/ 收集异常prompt记录"""

    def collect(self, since: Optional[datetime] = None, limit: int = 20) -> List[ErrorRecord]:
        errors = []
        if not PROMPT_LOG_DIR.exists():
            return errors

        files = sorted(PROMPT_LOG_DIR.glob("prompt_*.json"), reverse=True)[:limit]

        for f in files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue

            if isinstance(data, dict):
                error_msg = data.get("error") or data.get("exception")
                if error_msg:
                    errors.append(ErrorRecord(
                        source="prompt_log",
                        timestamp=data.get("timestamp", f.stem),
                        level="ERROR",
                        message=str(error_msg)[:300],
                        detail=f.name,
                    ))
                resp = data.get("response", "")
                if isinstance(resp, str) and any(kw in resp.lower() for kw in ["429", "error", "rate_limit"]):
                    errors.append(ErrorRecord(
                        source="prompt_log",
                        timestamp=data.get("timestamp", f.stem),
                        level="WARNING",
                        message=f"prompt响应含429/error: {resp[:200]}",
                        detail=f.name,
                    ))

        return errors


class CompositeCollector:
    """组合收集器 — 统一入口"""

    def __init__(self):
        self.app_log = AppLogCollector()
        self.sse = SSEEventCollector()
        self.process = ProcessCollector()
        self.prompt = PromptLogCollector()

    def collect_all(
        self,
        sse_events: Optional[List[Dict[str, Any]]] = None,
        since: Optional[datetime] = None,
    ) -> Dict[str, List[ErrorRecord]]:
        result = {}
        result["app_log"] = self.app_log.collect(since=since)
        result["process"] = self.process.collect()
        result["prompt"] = self.prompt.collect(since=since)

        if sse_events:
            result["sse"] = self.sse.collect(sse_events)
        else:
            result["sse"] = []

        return result

    def collect_flat(
        self,
        sse_events: Optional[List[Dict[str, Any]]] = None,
        since: Optional[datetime] = None,
    ) -> List[ErrorRecord]:
        grouped = self.collect_all(sse_events=sse_events, since=since)
        all_errors = []
        for errors in grouped.values():
            all_errors.extend(errors)
        return sorted(all_errors, key=lambda e: (e.level, e.timestamp))
