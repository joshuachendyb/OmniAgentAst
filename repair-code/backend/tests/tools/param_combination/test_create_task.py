# -*- coding: utf-8 -*-
"""
create_task parameter combination and content test -- xiaojian 2026-06-24

Covers:
- Parameter combinations: schedule format x interval x command type
- Single features: daily/weekly/monthly tasks
- Real scenarios: scheduled backup, periodic cleanup, cyclic check
- Boundary: interval=0, long task_name
- Negative: non-Windows, schtasks failure, timeout
"""
import asyncio
from unittest.mock import patch, MagicMock

import pytest

from app.tools.system.create_task import create_task, _build_schtasks_create_cmd


# ============================================================
# 1. Parameter combinations (6 groups)
# ============================================================

class TestParamCombinations:
    def test_daily_task_default(self):
        """Daily task default parameters"""
        cmd = _build_schtasks_create_cmd("TestTask", "cmd /c echo test", "09:00")
        assert "/tn" in cmd
        assert "TestTask" in cmd
        assert "/st" in cmd
        assert "09:00" in cmd

    def test_daily_with_interval(self):
        """Daily + interval"""
        cmd = _build_schtasks_create_cmd("TestTask", "cmd /c test", "09:00", interval=30)
        assert "/ri" in cmd
        assert "30" in cmd

    def test_weekly_task(self):
        """Weekly task"""
        cmd = _build_schtasks_create_cmd("TestTask", "cmd /c test", "09:00 /day 1")
        assert "/d" in cmd

    def test_monthly_task(self):
        """Monthly task"""
        cmd = _build_schtasks_create_cmd("TestTask", "cmd /c test", "09:00 /monthly 15")
        assert "/d" in cmd
        assert "15" in cmd

    def test_with_start_date(self):
        """With start_date"""
        cmd = _build_schtasks_create_cmd("TestTask", "cmd /c test", "09:00",
                                          start_date="2024/01/01")
        assert "/sd" in cmd
        assert "2024/01/01" in cmd

    def test_with_start_time_override(self):
        """start_time overrides schedule time"""
        cmd = _build_schtasks_create_cmd("TestTask", "cmd /c test", "09:00",
                                          start_time="14:30")
        assert "/st" in cmd
        assert "14:30" in cmd


# ============================================================
# 2. Single features (8 items)
# ============================================================

class TestSingleFunction:
    def test_build_cmd_minimal(self):
        """Minimal parameters build command"""
        cmd = _build_schtasks_create_cmd("MyTask", "notepad.exe", "08:00")
        assert cmd[0] == "schtasks"
        assert "/create" in cmd
        assert "/tn" in cmd
        assert "MyTask" in cmd
        assert "/tr" in cmd
        assert "notepad.exe" in cmd
        assert "/f" in cmd

    def test_build_cmd_with_user(self):
        """With user parameter"""
        cmd = _build_schtasks_create_cmd("MyTask", "cmd /c test", "08:00",
                                          user="SYSTEM")
        assert "/ru" in cmd
        assert "SYSTEM" in cmd

    def test_build_cmd_with_interval(self):
        """With interval parameter"""
        cmd = _build_schtasks_create_cmd("MyTask", "cmd /c test", "08:00", interval=15)
        assert "/ri" in cmd
        assert "15" in cmd

    def test_build_cmd_no_optional(self):
        """Without optional parameters"""
        cmd = _build_schtasks_create_cmd("MyTask", "cmd /c test", "08:00")
        assert "/ru" not in cmd
        assert "/sd" not in cmd
        assert "/ri" not in cmd

    def test_create_task_mock_success(self):
        """Create task success (mock)"""
        mock_result = MagicMock(returncode=0, stdout="success", stderr="")
        with patch("app.tools.system.create_task.platform.system", return_value="Windows"):
            with patch("app.tools.system.create_task.subprocess.run", return_value=mock_result):
                r = create_task("TestTask", "cmd /c echo test", "09:00")
                assert r["llm_data"]["status"]["exec_code"] == "success"

    def test_create_task_non_windows(self):
        """Non-Windows platform"""
        with patch("app.tools.system.create_task.platform.system", return_value="Linux"):
            r = create_task("TestTask", "cmd /c test", "09:00")
            assert r["llm_data"]["status"]["exec_code"] == "error"

    def test_create_task_schtasks_failure(self):
        """schtasks execution failure"""
        mock_result = MagicMock(returncode=1, stdout="", stderr="error: invalid parameters")
        with patch("app.tools.system.create_task.platform.system", return_value="Windows"):
            with patch("app.tools.system.create_task.subprocess.run", return_value=mock_result):
                r = create_task("TestTask", "cmd /c test", "09:00")
                assert r["llm_data"]["status"]["exec_code"] == "error"

    def test_create_task_timeout(self):
        """schtasks timeout"""
        from subprocess import TimeoutExpired
        with patch("app.tools.system.create_task.platform.system", return_value="Windows"):
            with patch("app.tools.system.create_task.subprocess.run",
                       side_effect=TimeoutExpired("schtasks", 30)):
                r = create_task("TestTask", "cmd /c test", "09:00")
                assert r["llm_data"]["status"]["exec_code"] == "error"


# ============================================================
# 3. Real scenarios (3 items)
# ============================================================

class TestRealScenarios:
    def test_daily_backup_task(self):
        """Daily backup task"""
        cmd = _build_schtasks_create_cmd(
            "DailyBackup",
            "robocopy C:\\Data D:\\Backup /MIR",
            "22:00",
            description="Daily data backup"
        )
        assert "/tn" in cmd
        assert "DailyBackup" in cmd

    def test_weekly_cleanup_task(self):
        """Weekly cleanup task"""
        cmd = _build_schtasks_create_cmd(
            "WeeklyCleanup",
            "cmd /c del /q /f C:\\Temp\\*",
            "03:00 /day 7"
        )
        assert "/d" in cmd

    def test_interval_monitoring(self):
        """Cyclic monitoring task (every 5 minutes)"""
        cmd = _build_schtasks_create_cmd(
            "HealthCheck",
            "powershell -File C:\\Scripts\\health.ps1",
            "00:00",
            interval=5
        )
        assert "/ri" in cmd
        assert "5" in cmd


# ============================================================
# 4. Boundary (3 items)
# ============================================================

class TestBoundary:
    def test_interval_zero(self):
        """interval=0 does not add /ri"""
        cmd = _build_schtasks_create_cmd("Test", "cmd /c test", "08:00", interval=0)
        assert "/ri" not in cmd

    def test_long_task_name(self):
        """Very long task_name"""
        long_name = "A" * 256
        cmd = _build_schtasks_create_cmd(long_name, "cmd /c test", "08:00")
        assert long_name in cmd

    def test_special_chars_command(self):
        """Command with special characters"""
        cmd = _build_schtasks_create_cmd("Test", "cmd /c echo hello & dir", "08:00")
        assert any("hello & dir" in c for c in cmd)


# ============================================================
# 5. Negative (3 items)
# ============================================================

class TestNegative:
    def test_file_not_found(self):
        """schtasks command not found"""
        with patch("app.tools.system.create_task.platform.system", return_value="Windows"):
            with patch("app.tools.system.create_task.subprocess.run",
                       side_effect=FileNotFoundError):
                r = create_task("TestTask", "cmd /c test", "09:00")
                assert r["llm_data"]["status"]["exec_code"] == "error"

    def test_general_exception(self):
        """General exception"""
        with patch("app.tools.system.create_task.platform.system", return_value="Windows"):
            with patch("app.tools.system.create_task.subprocess.run",
                       side_effect=RuntimeError("unexpected")):
                r = create_task("TestTask", "cmd /c test", "09:00")
                assert r["llm_data"]["status"]["exec_code"] == "error"

    def test_command_with_empty_name(self):
        """Empty task_name"""
        cmd = _build_schtasks_create_cmd("", "cmd /c test", "08:00")
        assert "/tn" in cmd
        # Empty name will fail in schtasks
