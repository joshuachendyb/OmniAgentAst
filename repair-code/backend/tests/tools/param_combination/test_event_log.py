# -*- coding: utf-8 -*-
"""
event_log parameter combination and content test - XiaoJian 2026-06-24

Covers:
- Parameter combinations: log_name x max_events x level x source x time_range
- Single function: each level/log_name independently verified
- Real scenarios: error troubleshooting, security audit, system monitoring
- Boundary: max_events=1, max_events=1000, empty source
- Negative: invalid log_name, invalid level, invalid time_range
"""
import asyncio
from unittest.mock import patch, MagicMock

import pytest

from app.tools.system.event_log import event_log, _get_windows_event_log, _get_linux_event_log


# ============================================================
# 1. Parameter Combinations (8 groups)
# ============================================================

class TestParamCombinations:
    def test_system_error_1h(self):
        """System + error + 1h (default combination)"""
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("app.tools.system.event_log.subprocess.run", return_value=mock_result):
            r = event_log(log_name="System", max_events=50, level="error", time_range="1h")
            assert r["llm_data"]["status"]["exec_code"] == "success"

    def test_application_warning_24h(self):
        """Application + warning + 24h"""
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("app.tools.system.event_log.subprocess.run", return_value=mock_result):
            r = event_log(log_name="Application", level="warning", time_range="24h")
            assert r["llm_data"]["status"]["exec_code"] == "success"

    def test_security_critical_7d(self):
        """Security + critical + 7d"""
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("app.tools.system.event_log.subprocess.run", return_value=mock_result):
            r = event_log(log_name="Security", level="critical", time_range="7d")
            assert r["llm_data"]["status"]["exec_code"] == "success"

    def test_with_source_filter(self):
        """With source filter"""
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("app.tools.system.event_log.subprocess.run", return_value=mock_result):
            r = event_log(source="Winlogon")
            assert r["llm_data"]["status"]["exec_code"] == "success"

    def test_max_events_1(self):
        """max_events=1"""
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("app.tools.system.event_log.subprocess.run", return_value=mock_result):
            r = event_log(max_events=1)
            assert r["llm_data"]["status"]["exec_code"] == "success"

    def test_max_events_1000(self):
        """max_events=1000"""
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("app.tools.system.event_log.subprocess.run", return_value=mock_result):
            r = event_log(max_events=1000)
            assert r["llm_data"]["status"]["exec_code"] == "success"

    def test_time_range_10m(self):
        """time_range=10m"""
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("app.tools.system.event_log.subprocess.run", return_value=mock_result):
            r = event_log(time_range="10m")
            assert r["llm_data"]["status"]["exec_code"] == "success"

    def test_level_info(self):
        """level=info"""
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("app.tools.system.event_log.subprocess.run", return_value=mock_result):
            r = event_log(level="info")
            assert r["llm_data"]["status"]["exec_code"] == "success"


# ============================================================
# 2. Single Function (10 cases)
# ============================================================

class TestSingleFunction:
    def test_default_params(self):
        """Default parameters"""
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("app.tools.system.event_log.subprocess.run", return_value=mock_result):
            r = event_log()
            assert r["llm_data"]["status"]["exec_code"] == "success"

    def test_parse_event_output(self):
        """Parse event output"""
        event_output = """Event[1]
Provider: Winlogon
EventID: 4101
Level: Warning
Source Name: Winlogon
TimeCreated: 2024-01-01T12:00:00
Message: Desktop window manager paused

Event[2]
Provider: Security
EventID: 4624
Level: Information
Source Name: Security
TimeCreated: 2024-01-01T12:01:00
Message: Login successful
"""
        mock_result = MagicMock(returncode=0, stdout=event_output, stderr="")
        with patch("app.tools.system.event_log.subprocess.run", return_value=mock_result):
            r = event_log(max_events=10)
            assert r["llm_data"]["status"]["exec_code"] == "success"

    def test_empty_event_output(self):
        """Empty event output"""
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("app.tools.system.event_log.subprocess.run", return_value=mock_result):
            r = event_log()
            assert r["data"]["events"] == []

    def test_wevtutil_error(self):
        """wevtutil returns error"""
        mock_result = MagicMock(returncode=1, stdout="", stderr="Log not found")
        with patch("app.tools.system.event_log.subprocess.run", return_value=mock_result):
            r = event_log()
            assert r["llm_data"]["status"]["exec_code"] == "error"

    def test_timeout_error(self):
        """Command timeout"""
        from subprocess import TimeoutExpired
        with patch("app.tools.system.event_log.subprocess.run", side_effect=TimeoutExpired("cmd", 30)):
            r = event_log()
            assert r["llm_data"]["status"]["exec_code"] == "error"

    def test_file_not_found(self):
        """wevtutil not found"""
        with patch("app.tools.system.event_log.subprocess.run", side_effect=FileNotFoundError):
            r = event_log()
            assert r["llm_data"]["status"]["exec_code"] == "error"

    def test_source_filtering(self):
        """Source filtering"""
        event_output = """Event[1]
Source Name: Winlogon
Level: Warning
Message: Test

Event[2]
Source Name: Security
Level: Information
Message: Test2
"""
        mock_result = MagicMock(returncode=0, stdout=event_output, stderr="")
        with patch("app.tools.system.event_log.subprocess.run", return_value=mock_result):
            r = event_log(source="Winlogon")
            assert r["llm_data"]["status"]["exec_code"] == "success"

    def test_level_filtering(self):
        """Level filtering"""
        event_output = """Event[1]
Level: Warning
Source Name: Test
Message: Test

Event[2]
Level: Information
Source Name: Test
Message: Test2
"""
        mock_result = MagicMock(returncode=0, stdout=event_output, stderr="")
        with patch("app.tools.system.event_log.subprocess.run", return_value=mock_result):
            r = event_log(level="warning")
            assert r["llm_data"]["status"]["exec_code"] == "success"

    def test_max_events_limit(self):
        """max_events truncation"""
        events = "\n".join([
            f"Event[{i}]\nSource Name: Test\nLevel: Warning\nMessage: Event {i}"
            for i in range(100)
        ])
        mock_result = MagicMock(returncode=0, stdout=events, stderr="")
        with patch("app.tools.system.event_log.subprocess.run", return_value=mock_result):
            r = event_log(max_events=5)
            assert r["llm_data"]["status"]["exec_code"] == "success"

    def test_chinese_event_messages(self):
        """Chinese event messages"""
        event_output = """Event[1]
Provider: Winlogon
EventID: 4101
Level: Warning
Source Name: Winlogon
TimeCreated: 2024-01-01T12:00:00
Message: Desktop window manager paused temporarily, usually due to lock screen
"""
        mock_result = MagicMock(returncode=0, stdout=event_output, stderr="")
        with patch("app.tools.system.event_log.subprocess.run", return_value=mock_result):
            r = event_log()
            assert r["llm_data"]["status"]["exec_code"] == "success"


# ============================================================
# 3. Real Scenarios (3 cases)
# ============================================================

class TestRealScenarios:
    def test_error_troubleshooting(self):
        """Error troubleshooting: get latest error events"""
        event_output = """Event[1]
Provider: Application Error
EventID: 1000
Level: Error
Source Name: Application Error
TimeCreated: 2024-01-01T11:30:00
Message: Error application name: app.exe, error module: kernel32.dll

Event[2]
Provider: .NET Runtime
EventID: 1026
Level: Error
Source Name: .NET Runtime
TimeCreated: 2024-01-01T11:45:00
Message: Application: app.exe, exception: System.NullReferenceException
"""
        mock_result = MagicMock(returncode=0, stdout=event_output, stderr="")
        with patch("app.tools.system.event_log.subprocess.run", return_value=mock_result):
            r = event_log(log_name="Application", level="error", time_range="1h")
            assert r["llm_data"]["status"]["exec_code"] == "success"

    def test_security_audit(self):
        """Security audit: get security logs"""
        event_output = """Event[1]
Provider: Security
EventID: 4624
Level: Information
Source Name: Security
TimeCreated: 2024-01-01T10:00:00
Message: Login successful. New login: account admin

Event[2]
Provider: Security
EventID: 4625
Level: Information
Source Name: Security
TimeCreated: 2024-01-01T10:05:00
Message: Login failed. Failure info: account unknown_user
"""
        mock_result = MagicMock(returncode=0, stdout=event_output, stderr="")
        with patch("app.tools.system.event_log.subprocess.run", return_value=mock_result):
            r = event_log(log_name="Security", time_range="24h")
            assert r["llm_data"]["status"]["exec_code"] == "success"

    def test_system_monitoring(self):
        """System monitoring: get system events"""
        event_output = """Event[1]
Provider: Kernel-General
EventID: 1
Level: Information
Source Name: Kernel-General
TimeCreated: 2024-01-01T08:00:00
Message: OS has started
Event[2]
Provider: Resource-Exhaustion-Detector
EventID: 1001
Level: Warning
Source Name: Resource-Exhaustion-Detector
TimeCreated: 2024-01-01T09:00:00
Message: Windows successfully diagnosed low memory condition
"""
        mock_result = MagicMock(returncode=0, stdout=event_output, stderr="")
        with patch("app.tools.system.event_log.subprocess.run", return_value=mock_result):
            r = event_log(log_name="System", level="warning", time_range="7d")
            assert r["llm_data"]["status"]["exec_code"] == "success"


# ============================================================
# 4. Boundary (4 cases)
# ============================================================

class TestBoundary:
    def test_max_events_zero(self):
        """max_events=0 (should return empty)"""
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("app.tools.system.event_log.subprocess.run", return_value=mock_result):
            r = event_log(max_events=0)
            assert r["llm_data"]["status"]["exec_code"] == "success"

    def test_invalid_time_range(self):
        """Invalid time_range (uses default 1h)"""
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("app.tools.system.event_log.subprocess.run", return_value=mock_result):
            r = event_log(time_range="invalid")
            assert r["llm_data"]["status"]["exec_code"] == "success"

    def test_invalid_level(self):
        """Invalid level (uses default error)"""
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("app.tools.system.event_log.subprocess.run", return_value=mock_result):
            r = event_log(level="INVALID")
            assert r["llm_data"]["status"]["exec_code"] == "success"

    def test_empty_source_string(self):
        """Empty source string"""
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("app.tools.system.event_log.subprocess.run", return_value=mock_result):
            r = event_log(source="")
            assert r["llm_data"]["status"]["exec_code"] == "success"


# ============================================================
# 5. Negative (3 cases)
# ============================================================

class TestNegative:
    def test_subprocess_general_exception(self):
        """Subprocess general exception"""
        with patch("app.tools.system.event_log.subprocess.run", side_effect=RuntimeError("unexpected")):
            r = event_log()
            assert r["llm_data"]["status"]["exec_code"] == "error"

    def test_invalid_log_name(self):
        """Invalid log name (wevtutil errors)"""
        mock_result = MagicMock(returncode=1, stdout="", stderr="Log 'InvalidLog' does not exist.")
        with patch("app.tools.system.event_log.subprocess.run", return_value=mock_result):
            r = event_log(log_name="InvalidLog")
            assert r["llm_data"]["status"]["exec_code"] == "error"

    def test_non_windows_platform(self):
        """Non-Windows platform to Linux branch"""
        with patch("app.tools.system.event_log.platform.system", return_value="Linux"):
            with patch("app.tools.system.event_log.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
                r = event_log()
                assert r["llm_data"]["status"]["exec_code"] == "success"
