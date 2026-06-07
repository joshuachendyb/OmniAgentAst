# -*- coding: utf-8 -*-
"""
测试新增的系统工具：net_connections 和 event_log

Author: 小沈 - 2026-05-02
"""

import pytest
import sys
sys.path.insert(0, '.')

from app.services.tools.system.system_tools import net_connections, event_log


class TestNetConnections:
    """测试 net_connections 工具"""
    
    def test_net_connections_basic(self):
        """测试基本网络连接获取"""
        result = net_connections()
        assert result["code"] == "SUCCESS"
        assert "connections" in result["data"]
        assert "total" in result["data"]
    
    def test_net_connections_tcp_only(self):
        """测试只获取TCP连接"""
        result = net_connections(kind="tcp")
        assert result["code"] == "SUCCESS"
        # 检查所有连接都是TCP
        for conn in result["data"]["connections"]:
            assert conn["type"] == "TCP"
    
    def test_net_connections_with_port_filter(self):
        """测试端口过滤"""
        result = net_connections(filter_port=80)
        assert result["code"] == "SUCCESS"
        # 验证所有连接都涉及80端口
        for conn in result["data"]["connections"]:
            local = conn.get("local_address", "")
            remote = conn.get("remote_address", "")
            assert ":80" in local or ":80" in remote or result["data"]["total"] == 0


class TestEventLog:
    """测试 event_log 工具"""
    
    def test_event_log_system(self):
        """测试获取系统日志"""
        result = event_log(log_name="System", max_events=10)
        assert result["code"] == "SUCCESS"
        assert "events" in result["data"]
        assert result["data"]["total"] <= 10
    
    def test_event_log_with_time_range(self):
        """测试时间范围过滤"""
        result = event_log(time_range="1h", max_events=5)
        assert result["code"] == "SUCCESS"
    
    def test_event_log_application(self):
        """测试获取应用程序日志"""
        result = event_log(log_name="Application", max_events=5, level="error")
        assert result["code"] in ["SUCCESS", "ERR_SYSTEM_EVENT_LOG"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
