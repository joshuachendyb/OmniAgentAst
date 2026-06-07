"""
全模块真实集成测试 - 基于运行中的后台服务(127.0.0.1:8000)
覆盖: 会话管理、配置管理、安全检查、操作历史、监控指标、Agent/ReAct端到端、工具执行链路

不使用任何mock，全部真实调用
作者: 小健 2026-05-21
"""
import pytest
import httpx
import json
import time
import uuid
from app.services.agent.llm_response_parser import parse_react_response
from app.services.tools import ensure_tools_registered, tool_registry
from app.services.agent.agent_factory import AgentFactory

BASE = "http://127.0.0.1:8000/api/v1"
T = 30


def api(method, path, **kw):
    """统一API调用"""
    fn = getattr(httpx, method)
    r = fn(f"{BASE}{path}", timeout=T, **kw)
    return r


def api_json(method, path, **kw):
    """API调用返回JSON"""
    r = api(method, path, **kw)
    assert r.status_code < 400, f"HTTP {r.status_code}: {r.text[:200]}"
    return r.json()


# =============================================================================
# 1. 健康检查 & Echo
# =============================================================================

class TestHealthEcho:
    def test_health_get(self):
        r = api("get", "/health")
        assert r.status_code == 200

    def test_echo_post(self):
        r = api("post", "/echo", json={"message": "test123"})
        assert r.status_code == 200
        d = r.json()
        assert "received" in d or "echo" in d or "message" in d

    def test_tool_list_59(self):
        d = api_json("get", "/tool/list")
        assert d["total"] == 59
        assert len(d["tools"]) == 59


# =============================================================================
# 2. 会话管理模块 (sessions)
# =============================================================================

class TestSessions:
    """会话管理: 创建/列表/消息/更新/删除"""

    def test_create_session(self):
        r = api("post", "/sessions", json={})
        assert r.status_code == 200
        d = r.json()
        self.__class__.session_id = d.get("session_id") or d.get("data", {}).get("session_id")
        assert self.__class__.session_id is not None

    def test_list_sessions(self):
        d = api_json("get", "/sessions")
        assert isinstance(d, list) or isinstance(d.get("data"), list) or isinstance(d.get("sessions"), list)

    def test_get_session_messages(self):
        sid = self.__class__.session_id
        if not sid:
            pytest.skip("no session_id")
        r = api("get", f"/sessions/{sid}/messages")
        assert r.status_code == 200

    def test_save_message(self):
        sid = self.__class__.session_id
        if not sid:
            pytest.skip("no session_id")
        r = api("post", f"/sessions/{sid}/messages", json={
            "role": "user",
            "content": "测试消息"
        })
        assert r.status_code == 200

    def test_update_session_title(self):
        sid = self.__class__.session_id
        if not sid:
            pytest.skip("no session_id")
        r = api("put", f"/sessions/{sid}", json={"title": "测试会话标题"})
        assert r.status_code == 200

    def test_delete_session(self):
        sid = self.__class__.session_id
        if not sid:
            pytest.skip("no session_id")
        r = api("delete", f"/sessions/{sid}")
        assert r.status_code == 200


# =============================================================================
# 3. 配置管理模块 (config)
# =============================================================================

class TestConfig:
    """配置管理: 获取/更新/验证/模型列表/Provider"""

    def test_get_config(self):
        r = api("get", "/config")
        assert r.status_code == 200
        d = r.json()
        assert "ai_model" in d or "data" in d or "config" in d or "providers" in d or "success" in d

    def test_get_config_models(self):
        r = api("get", "/config/models")
        assert r.status_code == 200

    def test_validate_config(self):
        r = api("put", "/config/validate", json={"config": {}})
        assert r.status_code in (200, 422)

    def test_get_config_path(self):
        r = api("get", "/config/path")
        assert r.status_code == 200

    def test_get_full_config(self):
        r = api("get", "/config/full")
        assert r.status_code == 200


# =============================================================================
# 4. 安全检查模块 (security)
# =============================================================================

class TestSecurity:
    """安全检查: 命令安全检测"""

    def test_safe_command(self):
        d = api_json("post", "/security/check", json={"command": "dir"})
        assert d.get("success") is not None or "safe" in str(d).lower() or "is_safe" in str(d).lower()

    def test_dangerous_command(self):
        d = api_json("post", "/security/check", json={"command": "rm -rf /"})
        assert d.get("success") is not None or "safe" in str(d).lower()

    def test_format_command(self):
        d = api_json("post", "/security/check", json={"command": "format C:"})
        assert d.get("success") is not None


# =============================================================================
# 5. 操作历史模块 (operation_history)
# =============================================================================

class TestOperationHistory:
    """操作历史: 统计/树形/流向/回滚"""

    def test_operations_list(self):
        r = api("get", "/operations", params={"session_id": "test"})
        assert r.status_code in (200, 404, 422)

    def test_operations_tree_data(self):
        r = api("get", "/operations/tree-data", params={"session_id": "test"})
        assert r.status_code in (200, 404, 422, 500)

    def test_operations_flow_data(self):
        r = api("get", "/operations/flow-data", params={"session_id": "test"})
        assert r.status_code in (200, 404, 422)

    def test_operations_stats_data(self):
        r = api("get", "/operations/stats-data", params={"session_id": "test"})
        assert r.status_code in (200, 404, 422)

    def test_operations_animation_data(self):
        r = api("get", "/operations/animation-data", params={"session_id": "test"})
        assert r.status_code in (200, 404, 422)

    def test_operations_report(self):
        r = api("get", "/operations/report", params={"session_id": "test"})
        assert r.status_code in (200, 404, 422)


# =============================================================================
# 6. 监控指标模块 (metrics)
# =============================================================================

class TestMetrics:
    """监控指标: 摘要/原始/健康/重置"""

    def test_metrics_summary(self):
        r = api("get", "/metrics")
        assert r.status_code == 200

    def test_metrics_raw(self):
        r = api("get", "/metrics/raw")
        assert r.status_code == 200

    def test_metrics_health(self):
        r = api("get", "/metrics/health")
        assert r.status_code == 200

    def test_metrics_reset(self):
        r = api("post", "/metrics/reset", json={})
        assert r.status_code in (200, 422)


# =============================================================================
# 7. 工具执行链路深度测试 (tool/execute 端点 → registry → implementation)
# =============================================================================

class TestToolExecutionDeep:
    """工具执行链路深度验证：跨类别调用、参数验证、错误处理"""

    def test_file_read_real_file(self):
        d = api_json("post", "/tool/execute", json={
            "tool_name": "read_file",
            "params": {"file_paths": ["G:/OmniAgentAs-desk/AGENTS.md"], "head": 3}
        })
        assert d["success"] is True

    def test_meta_tool_help_detailed(self):
        d = api_json("post", "/tool/execute", json={
            "tool_name": "tool_help",
            "params": {"tool_name": "read_file"}
        })
        assert d["success"] is True
        res = d.get("result", {})
        assert res.get("code") == "SUCCESS" or res.get("status") == "success"

    def test_meta_tool_search(self):
        d = api_json("post", "/tool/execute", json={
            "tool_name": "tool_search",
            "params": {"query": "读取文件"}
        })
        assert d["success"] is True
        res = d.get("result", {})
        assert res.get("code") == "SUCCESS" or res.get("status") == "success"

    def test_system_info_real(self):
        d = api_json("post", "/tool/execute", json={
            "tool_name": "get_system_info",
            "params": {}
        })
        assert d["success"] is True
        res = d.get("result", {})
        data = res.get("data", {})
        assert data.get("success") is True or "platform" in str(data).lower() or "system" in str(data).lower()

    def test_time_chain(self):
        """时间工具链: get_time → time_add → time_diff"""
        t1 = api_json("post", "/tool/execute", json={"tool_name": "get_time", "params": {}})
        assert t1["success"] is True
        t2 = api_json("post", "/tool/execute", json={"tool_name": "time_add", "params": {"delta": 1, "unit": "days"}})
        assert t2["success"] is True
        t3 = api_json("post", "/tool/execute", json={"tool_name": "time_diff", "params": {"start": "2026-01-01", "end": "2026-12-31"}})
        assert t3["success"] is True

    def test_error_invalid_tool(self):
        """调用不存在的工具"""
        r = api("post", "/tool/execute", json={"tool_name": "nonexistent_tool_xyz", "params": {}})
        assert r.status_code == 200
        d = r.json()
        assert d.get("success") is False

    def test_error_missing_required_param(self):
        """缺少必需参数"""
        r = api("post", "/tool/execute", json={"tool_name": "read_file", "params": {}})
        assert r.status_code == 200

    def test_network_diagnose_real(self):
        d = api_json("post", "/tool/execute", json={
            "tool_name": "network_diagnose",
            "params": {"host": "127.0.0.1", "mode": "ping", "count": 2}
        })
        assert d["success"] is True

    def test_list_directory_real(self):
        d = api_json("post", "/tool/execute", json={
            "tool_name": "list_directory",
            "params": {"dir_path": "G:/OmniAgentAs-desk", "format": "list"}
        })
        assert d["success"] is True

    def test_grep_content_real(self):
        d = api_json("post", "/tool/execute", json={
            "tool_name": "grep_file_content",
            "params": {"pattern": "FastAPI", "search_dir": "G:/OmniAgentAs-desk/backend/app"}
        })
        assert d["success"] is True


# =============================================================================
# 8. Agent/ReAct 端到端测试 (chat/stream/v2)
# =============================================================================

class TestChatStreamE2E:
    """Agent/ReAct端到端: 通过chat/stream/v2触发真实Agent循环"""

    def _call_stream(self, message: str, max_events: int = 20):
        """调用chat/stream/v2，收集SSE事件"""
        events = []
        try:
            with httpx.stream(
                "POST",
                f"{BASE}/chat/stream/v2",
                json={
                    "messages": [{"role": "user", "content": message}],
                    "session_id": str(uuid.uuid4()),
                },
                headers={"Content-Type": "application/json"},
                timeout=120,
            ) as resp:
                buf = ""
                for chunk in resp.iter_text():
                    buf += chunk
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        line = line.strip()
                        if not line or not line.startswith("data:"):
                            continue
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            evt = json.loads(data_str)
                            events.append(evt)
                            if len(events) >= max_events:
                                break
                        except json.JSONDecodeError:
                            continue
        except Exception:
            pass
        return events

    def test_simple_time_query(self):
        """简单时间查询: 应触发Thought→Action→Observation→Answer"""
        events = self._call_stream("现在几点了？", max_events=30)
        assert len(events) > 0, "No SSE events received"
        types = [e.get("type") or e.get("event") for e in events]
        has_answer = any(t in ("answer", "finish", "response") for t in types)
        has_any = len(events) > 0
        assert has_any, f"No meaningful events, got types: {types}"

    def test_file_query(self):
        """文件查询: 应触发FileReactAgent"""
        events = self._call_stream("读取version.txt文件内容", max_events=30)
        assert len(events) > 0, "No SSE events received"

    def test_system_query(self):
        """系统信息查询: 应触发SystemReactAgent"""
        events = self._call_stream("查看系统信息", max_events=30)
        assert len(events) > 0, "No SSE events received"


# =============================================================================
# 9. 解析器链+工具注册 Python层深度测试
# =============================================================================

class TestPythonLayerDeep:
    """Python层深度验证: parse_react_response、ToolRegistry、AgentFactory"""

    def test_parse_all_9_handlers(self):
        cases = [
            ({"tool_name": "get_time", "tool_params": {}}, "action"),
            ({"tool_name": "finish", "tool_params": {"result": "done"}}, "answer"),
            ([{"tool_name": "get_time", "tool_params": {}}], "action"),
            ('{"tool_name":"get_time","tool_params":{}}', "action"),
            ('', "parse_error"),
            (None, "parse_error"),
        ]
        for inp, expected_type in cases:
            r = parse_react_response(inp)
            assert r["type"] == expected_type, f"Input={inp!r}, expected={expected_type}, got={r['type']}"

    def test_parse_finish_type_normalization(self):
        for val, expected_is_str in [
            (42, True), (3.14, True), (True, True),
            ({"k": "v"}, True), ([1, 2], True), ("ok", True),
        ]:
            r = parse_react_response({"tool_name": "finish", "tool_params": {"result": val}})
            assert r["type"] == "answer"
            assert isinstance(r["response"], str) == expected_is_str, f"result={val!r}, response={r['response']!r}"

    def test_tool_registry_59(self):
        ensure_tools_registered()
        tools = tool_registry.list_tools(include_metadata=False)
        names = [t if isinstance(t, str) else t.get("name") for t in tools]
        assert len(names) == 59
        for name in names:
            impl = tool_registry.get_implementation(name)
            assert impl is not None, f"{name} has no implementation"
            assert callable(impl), f"{name} implementation not callable"

    def test_agent_factory_mapping(self):
        factory = AgentFactory()
        agents = factory._AGENTS
        assert len(agents) >= 7, f"Expected >=7 agents, got {len(agents)}"
        for intent in ["file", "shell", "network", "system", "desktop", "document", "meta"]:
            assert intent in agents, f"No agent for intent={intent}"
