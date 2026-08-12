# -*- coding: utf-8 -*-
"""
list_tasks 参数组合与内容测试——小欧 2026-06-24

覆盖:- 参数组合:task_name × state × mock输出
- 单一功能:解析,过滤,状态映射 - 真实场景:列出所有任务,按状态过滤,搜索特定任务 - 边界:空输出,大量任务,无匹配
- 负面:非Windows平台,schtasks失败,超时"""
import asyncio
from unittest.mock import patch, MagicMock

import pytest

from app.tools.system.list_tasks import (
    list_tasks, _parse_task_entries, _filter_tasks, _run_schtasks_query
)


SAMPLE_OUTPUT = """\
任务名:           \\Microsoft\\Windows\\Defrag\\ScheduledDefrag
Next Run Time:    2024-01-02 03:00:00
Status:           Ready
Task To Run:      C:\\Windows\\System32\\defrag.exe

任务名:           \\Microsoft\\Windows\\DiskCleanup\\SilentCleanup
Next Run Time:    2024-01-02 04:00:00
Status:           Running
Task To Run:      C:\\Windows\\System32\\cleanmgr.exe

任务名:           \\CustomApp\\BackupJob
Next Run Time:    2024-01-02 22:00:00
Status:           Disabled
Task To Run:      D:\\Scripts\\backup.bat

任务名:           \\Microsoft\\Windows\\WindowsUpdate\\Scheduled Start
Next Run Time:    2024-01-02 06:00:00
Status:           Ready
Task To Run:      C:\\Windows\\System32\\wuauclt.exe
"""


# ============================================================
# 1. 参数组合 (6组)
# ============================================================

class TestParamCombinations:
    def test_list_all_default(self):
        """默认参数列出所有任务"""
        with patch("app.tools.system.list_tasks._run_schtasks_query", return_value=SAMPLE_OUTPUT):
            r = list_tasks()
            assert r["llm_data"]["status"]["exec_code"] == "success"
            assert r["llm_data"]["metrics"]["total"]["value"] == 4

    def test_filter_by_name(self):
        """按名称过滤"""
        with patch("app.tools.system.list_tasks._run_schtasks_query", return_value=SAMPLE_OUTPUT):
            r = list_tasks(task_name="Backup")
            d = r["data"]
            assert r["llm_data"]["metrics"]["total"]["value"] == 4
            assert r["llm_data"]["metrics"]["matched"]["value"] == 1

    def test_filter_by_state_running(self):
        """按状态过滤Running"""
        with patch("app.tools.system.list_tasks._run_schtasks_query", return_value=SAMPLE_OUTPUT):
            r = list_tasks(state="running")
            d = r["data"]
            assert r["llm_data"]["metrics"]["matched"]["value"] == 1

    def test_filter_by_state_ready(self):
        """按状态过滤Ready"""
        with patch("app.tools.system.list_tasks._run_schtasks_query", return_value=SAMPLE_OUTPUT):
            r = list_tasks(state="ready")
            d = r["data"]
            assert r["llm_data"]["metrics"]["matched"]["value"] == 2

    def test_filter_by_state_disabled(self):
        """按状态过滤Disabled"""
        with patch("app.tools.system.list_tasks._run_schtasks_query", return_value=SAMPLE_OUTPUT):
            r = list_tasks(state="disabled")
            d = r["data"]
            assert r["llm_data"]["metrics"]["matched"]["value"] == 1

    def test_name_and_state_combined(self):
        """名称+状态组合过滤"""
        with patch("app.tools.system.list_tasks._run_schtasks_query", return_value=SAMPLE_OUTPUT):
            r = list_tasks(task_name="Defrag", state="ready")
            d = r["data"]
            assert r["llm_data"]["metrics"]["matched"]["value"] == 1


# ============================================================
# 2. 单一功能 (10个)
# ============================================================

class TestSingleFunction:
    def test_parse_task_entries(self):
        """_parse_task_entries解析"""
        tasks = _parse_task_entries(SAMPLE_OUTPUT)
        assert len(tasks) == 4
        assert tasks[0]["name"] == "\\Microsoft\\Windows\\Defrag\\ScheduledDefrag"
        assert tasks[0]["status"] == "ready"
        assert tasks[1]["status"] == "running"
        assert tasks[2]["status"] == "disabled"

    def test_parse_empty_output(self):
        """_parse_task_entries空输出"""
        tasks = _parse_task_entries("")
        assert tasks == []

    def test_filter_tasks_all(self):
        """_filter_tasks全部返回"""
        tasks = [{"name": "A", "status": "ready"}, {"name": "B", "status": "running"}]
        result, count = _filter_tasks(tasks, None, "all", 100)
        assert count == 2
        assert len(result) == 2

    def test_filter_tasks_by_name(self):
        """_filter_tasks按名称过滤"""
        tasks = [{"name": "Task_A", "status": "ready"}, {"name": "Task_B", "status": "ready"}]
        result, count = _filter_tasks(tasks, "Task_A", "all", 100)
        assert count == 1

    def test_filter_tasks_by_status(self):
        """_filter_tasks按状态过滤"""
        tasks = [{"name": "A", "status": "ready"}, {"name": "B", "status": "running"}]
        result, count = _filter_tasks(tasks, None, "ready", 100)
        assert count == 1

    def test_filter_tasks_max_results(self):
        """_filter_tasks截断"""
        tasks = [{"name": f"Task_{i}", "status": "ready"} for i in range(50)]
        result, count = _filter_tasks(tasks, None, "all", 5)
        assert count == 50
        assert len(result) == 5

    def test_filter_tasks_no_match(self):
        """_filter_tasks无匹配"""
        tasks = [{"name": "A", "status": "ready"}]
        result, count = _filter_tasks(tasks, "NonExistent", "all", 100)
        assert count == 0

    def test_filter_tasks_name_case_insensitive(self):
        """_filter_tasks名称大小写不敏感"""
        tasks = [{"name": "MyTask", "status": "ready"}]
        result, count = _filter_tasks(tasks, "mytask", "all", 100)
        assert count == 1

    def test_status_mapping(self):
        """状态映射"""
        tasks = _parse_task_entries(SAMPLE_OUTPUT)
        statuses = {t["status"] for t in tasks}
        assert "ready" in statuses
        assert "running" in statuses
        assert "disabled" in statuses

    def test_task_has_command(self):
        """解析出command字段"""
        tasks = _parse_task_entries(SAMPLE_OUTPUT)
        for t in tasks:
            assert "command" in t
            assert len(t["command"]) > 0


# ============================================================
# 3. 真实场景 (3个)
# ============================================================

class TestRealScenarios:
    def test_list_all_system_tasks(self):
        """列出所有系统任务"""
        with patch("app.tools.system.list_tasks._run_schtasks_query", return_value=SAMPLE_OUTPUT):
            r = list_tasks()
            assert r["llm_data"]["status"]["exec_code"] == "success"

    def test_find_running_tasks(self):
        """查找运行中的任务"""
        with patch("app.tools.system.list_tasks._run_schtasks_query", return_value=SAMPLE_OUTPUT):
            r = list_tasks(state="running")
            assert r["llm_data"]["metrics"]["matched"]["value"] == 1

    def test_search_custom_tasks(self):
        """搜索自定义任务"""
        custom_output = """\
任务名:           \\MyCompany\\App\\AutoBackup
Next Run Time:    2024-01-02 02:00:00
Status:           Ready
Task To Run:      D:\\Scripts\\backup.exe

任务名:           \\MyCompany\\App\\HealthCheck
Next Run Time:    2024-01-02 06:00:00
Status:           Ready
Task To Run:      D:\\Scripts\\health.exe
"""
        with patch("app.tools.system.list_tasks._run_schtasks_query", return_value=custom_output):
            r = list_tasks(task_name="MyCompany")
            assert r["llm_data"]["metrics"]["matched"]["value"] == 2


# ============================================================
# 4. 边界 (4个)
# ============================================================

class TestBoundary:
    def test_empty_output(self):
        """空输出"""
        with patch("app.tools.system.list_tasks._run_schtasks_query", return_value=""):
            r = list_tasks()
            # 空输出可能触发ValueError

    def test_single_task(self):
        """单个任务"""
        single = """\
任务名:           \\SingleTask
Next Run Time:    2024-01-02 09:00:00
Status:           Ready
Task To Run:      notepad.exe
"""
        with patch("app.tools.system.list_tasks._run_schtasks_query", return_value=single):
            r = list_tasks()
            assert r["llm_data"]["metrics"]["total"]["value"] == 1

    def test_many_tasks(self):
        """大量任务"""
        many = "\n".join([
            f"任务名:           \\Task{i}\nNext Run Time:    2024-01-02 09:00:00\nStatus:           Ready\nTask To Run:      cmd.exe\n"
            for i in range(100)
        ])
        with patch("app.tools.system.list_tasks._run_schtasks_query", return_value=many):
            r = list_tasks()
            assert r["llm_data"]["metrics"]["total"]["value"] == 100

    def test_tasks_with_unknown_status(self):
        """未知状态的任务"""
        output = """\
任务名:           \\WeirdTask
Next Run Time:    N/A
Status:           Unknown
Task To Run:      test.exe
"""
        with patch("app.tools.system.list_tasks._run_schtasks_query", return_value=output):
            r = list_tasks()
            assert r["llm_data"]["status"]["exec_code"] == "success"


# ============================================================
# 5. 负面 (3个)
# ============================================================

class TestNegative:
    def test_non_windows(self):
        """非Windows平台"""
        with patch("app.tools.system.list_tasks.platform.system", return_value="Linux"):
            r = list_tasks()
            assert r["llm_data"]["status"]["exec_code"] == "error"

    def test_schtasks_timeout(self):
        """schtasks超时"""
        from subprocess import TimeoutExpired
        with patch("app.tools.system.list_tasks.platform.system", return_value="Windows"):
            with patch("app.tools.system.list_tasks._run_schtasks_query",
                       side_effect=TimeoutExpired("schtasks", 30)):
                r = list_tasks()
                assert r["llm_data"]["status"]["exec_code"] == "error"

    def test_schtasks_empty_raises_value_error(self):
        """schtasks返回空触发ValueError"""
        with patch("app.tools.system.list_tasks._run_schtasks_query",
                   side_effect=ValueError("计划任务列表为空")):
            r = list_tasks()
            assert r["llm_data"]["status"]["exec_code"] == "error"
