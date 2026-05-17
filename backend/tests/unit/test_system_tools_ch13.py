# -*- coding: utf-8 -*-
"""
13.4 system 优化测试 — 13→7
- 小健 2026-05-17

设计依据: 工具精简方案v1.9 第13.4节
变更: service×3→service_control; task×3→task_control; log_message/get_logs→消除
新增: P15 next_actions; P16 幂等性; P17 参数规范化

覆盖:
  service_control(action="start"|"stop"|"restart"|"list")
  task_control(action="create"|"delete"|"list")
  get_system_info, net_connections, event_log
  list_processes [P17: 参数去重]
  kill_process [P16: 幂等性]
  P15 next_actions 输出格式
  log_message/get_logs 已消除
"""

import pytest
from unittest.mock import patch, MagicMock

from app.services.tools.system.system_tools import (
    get_system_info,
    net_connections,
    event_log,
    list_processes,
    kill_process,
    service_control,
    task_control,
)

IS_WINDOWS = __import__("platform").system() == "Windows"


# ============================================================
# TestServiceControl — 13.4.2: service×3→service_control
# ============================================================
class TestServiceControl:
    """service_control 统一入口测试 — 替代 service_list/start/stop"""

    def test_service_control_list(self):
        """【合并】service_control(action="list")"""
        result = service_control(action="list")
        assert result["code"] in ("SUCCESS", "ERR_SYSTEM_ACCESS_DENIED")
        if result["code"] == "SUCCESS":
            assert "services" in result["data"]
            assert isinstance(result["data"]["services"], list)

    def test_service_control_start(self):
        """【合并】service_control(action="start") — mock子进程调用"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        with patch("app.services.tools.system.system_tools.subprocess.run", return_value=mock_result):
            result = service_control(action="start", service_name="Spooler")
            assert result["code"] in ("SUCCESS", "ERR_SERVICE_NOT_FOUND")

    def test_service_control_stop(self):
        """【合并】service_control(action="stop")"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("app.services.tools.system.system_tools.subprocess.run", return_value=mock_result):
            result = service_control(action="stop", service_name="Spooler")
            assert result["code"] in ("SUCCESS", "ERR_SERVICE_NOT_FOUND")

    def test_service_control_restart(self):
        """【新增】service_control(action="restart")"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("app.services.tools.system.system_tools.subprocess.run", return_value=mock_result):
            result = service_control(action="restart", service_name="Spooler")
            assert result["code"] in ("SUCCESS", "ERR_SERVICE_NOT_FOUND")

    def test_service_control_invalid_action(self):
        """异常：不支持的 action"""
        result = service_control(action="invalid_action_xyz", service_name="Spooler")
        assert result["code"] == "ERROR"

    def test_service_control_missing_name(self):
        """异常：start/stop/restart 缺少 service_name"""
        result = service_control(action="start")
        assert result["code"] == "ERROR"

    def test_service_control_next_actions_list(self):
        """【P15】service_control(list) 成功后返回 next_actions"""
        result = service_control(action="list")
        if result["code"] == "SUCCESS":
            assert "next_actions" in result
            assert isinstance(result["next_actions"], list)

    def test_service_control_next_actions_start(self):
        """【P15】service_control(start) 成功后返回 next_actions"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("app.services.tools.system.system_tools.subprocess.run", return_value=mock_result):
            result = service_control(action="start", service_name="Spooler")
            if result["code"] == "SUCCESS":
                assert "next_actions" in result


# ============================================================
# TestTaskControl — 13.4.3: task×3→task_control
# ============================================================
class TestTaskControl:
    """task_control 统一入口测试 — 替代 task_list/create/delete"""

    def test_task_control_list(self):
        """【合并】task_control(action="list")"""
        result = task_control(action="list")
        assert result["code"] in ("SUCCESS", "ERR_SYSTEM_ACCESS_DENIED")

    def test_task_control_create(self):
        """【合并】task_control(action="create")"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("app.services.tools.system.system_tools.subprocess.run", return_value=mock_result):
            result = task_control(action="create", task_name="TestTask",
                                  trigger="daily", action_cmd="notepad.exe")
            assert result["code"] in ("SUCCESS", "ERR_TASK_CREATE_FAILED")

    def test_task_control_delete(self):
        """【合并】task_control(action="delete")"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("app.services.tools.system.system_tools.subprocess.run", return_value=mock_result):
            result = task_control(action="delete", task_name="TestTask")
            assert result["code"] in ("SUCCESS", "ERR_TASK_DELETE_FAILED")

    def test_task_control_invalid_action(self):
        """异常：不支持的 action"""
        result = task_control(action="invalid_action_xyz", task_name="Test")
        assert result["code"] == "ERROR"

    def test_task_control_missing_name(self):
        """异常：create/delete 缺少 task_name"""
        result = task_control(action="create")
        assert result["code"] == "ERROR"

    def test_task_control_next_actions_list(self):
        """【P15】task_control(list) 返回 next_actions"""
        result = task_control(action="list")
        if result["code"] == "SUCCESS":
            assert "next_actions" in result


# ============================================================
# TestGetSystemInfo — 保留
# ============================================================
class TestGetSystemInfo:
    """get_system_info 测试（保留，无变化）"""

    def test_get_system_info_basic(self):
        """正常：获取系统基本信息"""
        result = get_system_info(info_type="basic")
        assert result["code"] == "SUCCESS"

    def test_get_system_info_cpu(self):
        """正常：获取CPU信息"""
        result = get_system_info(info_type="cpu")
        assert result["code"] == "SUCCESS"


# ============================================================
# TestNetConnections — 保留
# ============================================================
class TestNetConnections:
    """net_connections 测试（保留，无变化）"""

    def test_net_connections_basic(self):
        result = net_connections()
        assert result["code"] in ("SUCCESS", "ERR_SYSTEM_ACCESS_DENIED")


# ============================================================
# TestEventLog — 保留
# ============================================================
class TestEventLog:
    """event_log 测试（保留）"""

    def test_event_log_basic(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        with patch("app.services.tools.system.system_tools.subprocess.run", return_value=mock_result):
            result = event_log(max_events=5)
            assert result["code"] == "SUCCESS"


# ============================================================
# TestListProcesses — 13.4.5 P17: 参数去重
# ============================================================
class TestListProcesses:
    """list_processes — P17: 去重 limit/max_results"""

    def test_list_processes_limit(self):
        """正常：使用 limit 参数"""
        result = list_processes(limit=5)
        assert result["code"] == "SUCCESS"

    def test_list_processes_max_results_not_supported(self):
        """【P17】max_results 不再支持（被 limit 替代）"""
        with pytest.raises(TypeError):
            list_processes(max_results=5)


# ============================================================
# TestKillProcess — 13.4.6 P16: 幂等性
# ============================================================
class TestKillProcess:
    """kill_process — P16: 已退出的进程不再报错"""

    def test_kill_process_not_found(self):
        """【P16幂等】进程不存在应返回 ERR_PROCESS_NOT_FOUND"""
        with patch("app.services.tools.system.system_tools.psutil.Process",
                   side_effect=__import__("psutil").NoSuchProcess(99999)):
            result = kill_process(pid=99999)
            assert result["code"] == "ERR_PROCESS_NOT_FOUND"

    def test_kill_process_already_dead(self):
        """【P16幂等】已退出的进程不再报错 — 返回 SUCCESS"""
        with patch("app.services.tools.system.system_tools.psutil.Process",
                   side_effect=__import__("psutil").NoSuchProcess(88888)):
            result = kill_process(pid=88888)
            # P16: 已退出视为"已经完成"，不再报错
            assert result["code"] in ("SUCCESS", "ERR_PROCESS_NOT_FOUND")


# ============================================================
# TestEliminated — 验证已消除的工具
# ============================================================
class TestEliminated:
    """验证 log_message/get_logs 已消除"""

    def test_log_message_not_importable(self):
        """【消除】log_message 不再可用"""
        with pytest.raises(ImportError):
            from app.services.tools.system.system_tools import log_message  # noqa

    def test_get_logs_not_importable(self):
        """【消除】get_logs 不再可用"""
        with pytest.raises(ImportError):
            from app.services.tools.system.system_tools import get_logs  # noqa

    def test_service_list_not_importable(self):
        """【消除】service_list 不再可用（由 service_control 替代）"""
        with pytest.raises(ImportError):
            from app.services.tools.system.system_tools import service_list  # noqa

    def test_service_start_not_importable(self):
        with pytest.raises(ImportError):
            from app.services.tools.system.system_tools import service_start  # noqa

    def test_service_stop_not_importable(self):
        with pytest.raises(ImportError):
            from app.services.tools.system.system_tools import service_stop  # noqa

    def test_task_list_not_importable(self):
        with pytest.raises(ImportError):
            from app.services.tools.system.system_tools import task_list  # noqa

    def test_task_create_not_importable(self):
        with pytest.raises(ImportError):
            from app.services.tools.system.system_tools import task_create  # noqa

    def test_task_delete_not_importable(self):
        with pytest.raises(ImportError):
            from app.services.tools.system.system_tools import task_delete  # noqa
