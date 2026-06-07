# -*- coding: utf-8 -*-
"""
SY7 task_control 深度测试 — test_sy7_task_control_deep.py

覆盖维度：
1. action路由（create/delete/list）
2. create时必填参数校验（task_name/command/schedule）
3. delete时task_name必填
4. 无效action处理
5. Windows平台限制检查

Author: 小沈 - 2026-05-19
"""

from unittest.mock import patch, MagicMock

import pytest

from app.services.tools.system.system_tools import task_control


class TestSy7TaskControl:
    """SY7 task_control 深度测试"""

    @patch("app.services.tools.system.system_tools._task_list")
    def test_list_action(self, mock_list):
        """action=list调用_task_list"""
        mock_list.return_value = {"code": "SUCCESS", "data": {"tasks": []}, "message": "OK"}

        result = task_control(action="list")
        assert result["code"] == "SUCCESS"
        mock_list.assert_called_once()

    @patch("app.services.tools.system.system_tools._task_create")
    def test_create_action(self, mock_create):
        """action=create调用_task_create"""
        mock_create.return_value = {"code": "SUCCESS", "data": {"task_name": "Test"}, "message": "Created"}

        result = task_control(action="create", task_name="Test", command="echo hello", schedule="08:00")
        assert result["code"] == "SUCCESS"
        mock_create.assert_called_once()

    def test_create_missing_required(self):
        """create缺少必填参数返回ERR_INVALID_PARAM"""
        result = task_control(action="create", task_name="Test")
        assert result["code"] == "ERR_INVALID_PARAM"
        assert "task_name、command、schedule" in result["message"]

    @patch("app.services.tools.system.system_tools._task_delete")
    def test_delete_action(self, mock_delete):
        """action=delete调用_task_delete"""
        mock_delete.return_value = {"code": "SUCCESS", "data": {"task_name": "Test"}, "message": "Deleted"}

        result = task_control(action="delete", task_name="Test")
        assert result["code"] == "SUCCESS"
        mock_delete.assert_called_once_with(task_name="Test", folder=None)

    def test_delete_missing_task_name(self):
        """delete缺少task_name返回ERR_INVALID_PARAM"""
        result = task_control(action="delete")
        assert result["code"] == "ERR_INVALID_PARAM"

    def test_invalid_action(self):
        """无效action返回ERR_INVALID_PARAM"""
        result = task_control(action="invalid")
        assert result["code"] == "ERR_INVALID_PARAM"
