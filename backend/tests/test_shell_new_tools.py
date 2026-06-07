# -*- coding: utf-8 -*-
"""
测试Shell会话管理工具：shell_session（合并get_shell_output + terminate_shell）

更新日：2026-05-18 小健（适配shell_session统一API）
Author: 小沈 - 2026-05-02
"""

import pytest
import sys
sys.path.insert(0, '.')

from app.services.tools.shell.shell_tools import shell_session, _background_shells
import subprocess
import time


class TestShellOutput:
    """测试 shell_session(action='output') 工具"""
    
    def test_get_output_nonexistent_shell(self):
        """测试获取不存在的shell输出"""
        result = shell_session("nonexistent_id", action="output")
        assert result["code"] == "ERR_SHELL_NOT_FOUND"
        assert "不存在" in result["message"]
    
    def test_get_output_with_filter(self):
        """测试带过滤器的输出获取"""
        # 创建一个模拟的后台shell
        shell_id = "test_shell_001"
        process = subprocess.Popen(
            ["echo", "ERROR: test error\nSUCCESS: ok\nERROR: another error"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True
        )
        _background_shells[shell_id] = {
            "process": process,
            "command": "echo test",
            "started_at": time.time()
        }
        
        try:
            result = shell_session(shell_id, action="output", filter="ERROR")
            assert result["code"] == "SUCCESS"
            assert "ERROR" in result["data"]["stdout"] or result["data"]["stderr"]
        finally:
            if shell_id in _background_shells:
                del _background_shells[shell_id]
    
    def test_get_output_with_max_lines(self):
        """测试限制最大行数"""
        shell_id = "test_shell_002"
        # 创建大量输出
        lines = "\n".join([f"Line {i}" for i in range(2000)])
        process = subprocess.Popen(
            ["echo", lines],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True
        )
        _background_shells[shell_id] = {
            "process": process,
            "command": "echo lines",
            "started_at": time.time()
        }
        
        try:
            result = shell_session(shell_id, action="output", max_lines=100)
            assert result["code"] == "SUCCESS"
            # shell_session返回stdout字符串，验证行数不超过max_lines
            stdout_lines = result["data"]["stdout"].splitlines()
            assert len(stdout_lines) <= 100
        finally:
            if shell_id in _background_shells:
                del _background_shells[shell_id]


class TestShellTerminate:
    """测试 shell_session(action='terminate') 工具"""
    
    def test_terminate_nonexistent_shell(self):
        """测试终止不存在的shell"""
        result = shell_session("nonexistent_id", action="terminate")
        assert result["code"] == "ERR_SHELL_NOT_FOUND"
    
    def test_terminate_completed_shell(self):
        """测试终止已完成的shell"""
        shell_id = "test_shell_003"
        process = subprocess.Popen(
            ["echo", "done"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True
        )
        process.wait()  # 等待完成
        
        _background_shells[shell_id] = {
            "process": process,
            "command": "echo done",
            "started_at": time.time()
        }
        
        try:
            result = shell_session(shell_id, action="terminate")
            assert result["code"] == "SUCCESS"
            # 已完成的进程终止后terminated=True
            assert result["data"]["terminated"] == True
        finally:
            if shell_id in _background_shells:
                del _background_shells[shell_id]
    
    def test_terminate_running_shell(self):
        """测试终止正在运行的shell"""
        shell_id = "test_shell_004"
        # 启动一个长时间运行的命令
        process = subprocess.Popen(
            ["ping", "-n", "10", "localhost"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True
        )
        
        _background_shells[shell_id] = {
            "process": process,
            "command": "ping -n 10 localhost",
            "started_at": time.time()
        }
        
        try:
            time.sleep(0.5)  # 等待进程启动
            result = shell_session(shell_id, action="terminate", force=True)
            assert result["code"] == "SUCCESS"
            assert result["data"]["terminated"] == True
            assert shell_id not in _background_shells
        finally:
            if shell_id in _background_shells:
                del _background_shells[shell_id]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
