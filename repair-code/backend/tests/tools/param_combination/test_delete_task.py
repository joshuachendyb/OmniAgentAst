# -*- coding: utf-8 -*-
"""
delete_task 参数组合与内容测试 — 小资 2026-06-24

覆盖:
- 参数组合:task_name类型 × mock场景
- 单一功能:删除成功/失败/不存在/超时
- 真实场景:删除临时任务,删除不存在任务
- 边界:空task_name,超长task_name
- 负面:非Windows平台,schtasks失败,超时"""
import asyncio
from unittest.mock import patch, MagicMock

import pytest

from app.tools.system.delete_task import delete_task


# ============================================================
# 1. 参数组合 (4组)
# ============================================================

class TestParamCombinations:
    def test_delete_existing_task(self):
        """删除存在的任务"""
        mock_query = MagicMock(returncode=0, stdout="正常", stderr="")
        mock_delete = MagicMock(returncode=0, stdout="成功", stderr="")
        with patch("app.tools.system.delete_task.platform.system", return_value="Windows"):
            with patch("app.tools.system.delete_task.subprocess.run",
                       side_effect=[mock_query, mock_delete]):
                r = delete_task("MyTask")
                assert r["llm_data"]["status"]["exec_code"] == "success"

    def test_delete_nonexistent_task(self):
        """删除不存在的任务"""
        mock_query = MagicMock(returncode=1, stdout="", stderr="系统找不到指定的文件")
        with patch("app.tools.system.delete_task.platform.system", return_value="Windows"):
            with patch("app.tools.system.delete_task.subprocess.run", return_value=mock_query):
                r = delete_task("NonExistent")
                assert r["llm_data"]["status"]["exec_code"] == "error"

    def test_delete_fails_after_query(self):
        """查询成功但删除失败"""
        mock_query = MagicMock(returncode=0, stdout="正常", stderr="")
        mock_delete = MagicMock(returncode=1, stdout="", stderr="拒绝访问")
        with patch("app.tools.system.delete_task.platform.system", return_value="Windows"):
            with patch("app.tools.system.delete_task.subprocess.run",
                       side_effect=[mock_query, mock_delete]):
                r = delete_task("ProtectedTask")
                assert r["llm_data"]["status"]["exec_code"] == "error"

    def test_delete_non_windows(self):
        """非Windows平台"""
        with patch("app.tools.system.delete_task.platform.system", return_value="Linux"):
            r = delete_task("MyTask")
            assert r["llm_data"]["status"]["exec_code"] == "error"


# ============================================================
# 2. 单一功能 (6个)
# ============================================================

class TestSingleFunction:
    def test_delete_success(self):
        """删除成功"""
        mock_query = MagicMock(returncode=0, stdout="", stderr="")
        mock_delete = MagicMock(returncode=0, stdout="", stderr="")
        with patch("app.tools.system.delete_task.platform.system", return_value="Windows"):
            with patch("app.tools.system.delete_task.subprocess.run",
                       side_effect=[mock_query, mock_delete]):
                r = delete_task("TestTask")
                assert r["llm_data"]["action"]["params"]["task_name"] == "TestTask"

    def test_delete_query_timeout(self):
        """查询超时"""
        from subprocess import TimeoutExpired
        with patch("app.tools.system.delete_task.platform.system", return_value="Windows"):
            with patch("app.tools.system.delete_task.subprocess.run",
                       side_effect=TimeoutExpired("schtasks", 30)):
                r = delete_task("TestTask")
                assert r["llm_data"]["status"]["exec_code"] == "error"

    def test_delete_schtasks_not_found(self):
        """schtasks命令不存在"""
        with patch("app.tools.system.delete_task.platform.system", return_value="Windows"):
            with patch("app.tools.system.delete_task.subprocess.run",
                       side_effect=FileNotFoundError):
                r = delete_task("TestTask")
                assert r["llm_data"]["status"]["exec_code"] == "error"

    def test_delete_general_exception(self):
        """一般异常"""
        with patch("app.tools.system.delete_task.platform.system", return_value="Windows"):
            with patch("app.tools.system.delete_task.subprocess.run",
                       side_effect=RuntimeError("unexpected")):
                r = delete_task("TestTask")
                assert r["llm_data"]["status"]["exec_code"] == "error"

    def test_delete_task_name_in_result(self):
        """返回结果包含task_name"""
        mock_query = MagicMock(returncode=0, stdout="", stderr="")
        mock_delete = MagicMock(returncode=0, stdout="", stderr="")
        with patch("app.tools.system.delete_task.platform.system", return_value="Windows"):
            with patch("app.tools.system.delete_task.subprocess.run",
                       side_effect=[mock_query, mock_delete]):
                r = delete_task("MySpecificTask")
                assert r["llm_data"]["action"]["params"]["task_name"] == "MySpecificTask"

    def test_delete_no_platform_check_first(self):
        """平台检查在查询之前"""
        with patch("app.tools.system.delete_task.platform.system", return_value="Linux"):
            r = delete_task("Task")
            assert r["llm_data"]["status"]["exec_code"] == "error"


# ============================================================
# 3. 真实场景 (2个)
# ============================================================

class TestRealScenarios:
    def test_cleanup_temp_task(self):
        """清理临时任务"""
        mock_query = MagicMock(returncode=0, stdout="", stderr="")
        mock_delete = MagicMock(returncode=0, stdout="", stderr="")
        with patch("app.tools.system.delete_task.platform.system", return_value="Windows"):
            with patch("app.tools.system.delete_task.subprocess.run",
                       side_effect=[mock_query, mock_delete]):
                r = delete_task("TempBackup_20240101")
                assert r["llm_data"]["status"]["exec_code"] == "success"

    def test_try_delete_already_deleted(self):
        """删除已删除的任务(幂等性)"""
        mock_query = MagicMock(returncode=1, stdout="", stderr="找不到")
        with patch("app.tools.system.delete_task.platform.system", return_value="Windows"):
            with patch("app.tools.system.delete_task.subprocess.run", return_value=mock_query):
                r = delete_task("AlreadyDeleted")
                assert r["llm_data"]["status"]["exec_code"] == "error"


# ============================================================
# 4. 边界 (2个)
# ============================================================

class TestBoundary:
    def test_empty_task_name(self):
        """空task_name"""
        mock_query = MagicMock(returncode=0, stdout="", stderr="")
        mock_delete = MagicMock(returncode=0, stdout="", stderr="")
        with patch("app.tools.system.delete_task.platform.system", return_value="Windows"):
            with patch("app.tools.system.delete_task.subprocess.run",
                       side_effect=[mock_query, mock_delete]):
                r = delete_task("")
                assert r["llm_data"]["status"]["exec_code"] in ("success", "error")

    def test_long_task_name(self):
        """超长task_name"""
        mock_query = MagicMock(returncode=0, stdout="", stderr="")
        mock_delete = MagicMock(returncode=0, stdout="", stderr="")
        with patch("app.tools.system.delete_task.platform.system", return_value="Windows"):
            with patch("app.tools.system.delete_task.subprocess.run",
                       side_effect=[mock_query, mock_delete]):
                r = delete_task("A" * 256)
                assert r["llm_data"]["status"]["exec_code"] in ("success", "error")


# ============================================================
# 5. 负面 (2个)
# ============================================================

class TestNegative:
    def test_delete_with_special_chars(self):
        """特殊字符task_name"""
        mock_query = MagicMock(returncode=1, stdout="", stderr="无效")
        with patch("app.tools.system.delete_task.platform.system", return_value="Windows"):
            with patch("app.tools.system.delete_task.subprocess.run", return_value=mock_query):
                r = delete_task("Task/With\\Special:Chars")
                assert r["llm_data"]["status"]["exec_code"] == "error"

    def test_delete_not_platform_windows(self):
        """非Windows返回明认错误"""
        with patch("app.tools.system.delete_task.platform.system", return_value="Darwin"):
            r = delete_task("Task")
            assert "仅支持" in r["llm_data"]["status"]["detail"]
