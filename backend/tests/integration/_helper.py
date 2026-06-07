"""
集成测试辅助模块 - 被conftest.py和各测试文件引用
小健 2026-05-21
"""
import pytest
import httpx
import json
import time
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

BASE_URL = "http://127.0.0.1:8000"
TOOL_EXECUTE_URL = f"{BASE_URL}/api/v1/tool/execute"
TOOL_LIST_URL = f"{BASE_URL}/api/v1/tool/list"
DEFAULT_TIMEOUT = 30.0

TEMP_DIR = Path(tempfile.gettempdir()) / "omniagent_test_workspace"


class ToolClient:
    """通过HTTP调用/tool/execute的工具客户端"""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self._available_tools: Optional[set] = None

    def _get_client(self) -> httpx.Client:
        return httpx.Client(timeout=self.timeout)

    def execute(self, tool_name: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        if params is None:
            params = {}
        with self._get_client() as client:
            resp = client.post(
                TOOL_EXECUTE_URL,
                json={"tool_name": tool_name, "parameters": params},
            )
            resp.raise_for_status()
            return resp.json()

    def call(self, tool_name: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        resp = self.execute(tool_name, params)
        if not resp.get("success"):
            pytest.fail(
                f"工具 {tool_name} 调用失败: {resp.get('error', 'unknown error')}"
            )
        return resp["result"]

    def call_expect_error(self, tool_name: str, params: Dict[str, Any] = None) -> str:
        resp = self.execute(tool_name, params)
        if resp.get("success"):
            result = resp.get("result", {})
            code = result.get("code", "UNKNOWN")
            if code != "SUCCESS":
                return result.get("message", "")
            pytest.fail(f"工具 {tool_name} 本应失败但成功了: {result}")
        return resp.get("error", "")

    def is_tool_available(self, tool_name: str) -> bool:
        if self._available_tools is None:
            with self._get_client() as client:
                resp = client.get(TOOL_LIST_URL)
                resp.raise_for_status()
                data = resp.json()
                self._available_tools = {t["name"] for t in data.get("tools", [])}
        return tool_name in self._available_tools

    def check_service(self) -> bool:
        try:
            with self._get_client() as client:
                resp = client.get(f"{BASE_URL}/api/v1/health")
                return resp.status_code == 200
        except Exception:
            return False


def assert_success(result: Dict, msg: str = ""):
    code = result.get("code", "")
    if code != "SUCCESS":
        error_msg = result.get("message", result.get("error", str(result)))
        pytest.fail(f"期望SUCCESS但得到{code}: {error_msg} {msg}")


def assert_error(result: Dict, expected_code_contains: str = "", msg: str = ""):
    code = result.get("code", "")
    if code == "SUCCESS":
        pytest.fail(f"期望错误但得到SUCCESS: {result} {msg}")
    if expected_code_contains:
        assert expected_code_contains in code, (
            f"期望code包含'{expected_code_contains}'但得到'{code}' {msg}"
        )


def assert_data_key(result: Dict, key: str, msg: str = ""):
    data = result.get("data", {})
    assert key in data, f"data中缺少key '{key}', 实际keys: {list(data.keys())} {msg}"


def assert_data_not_empty(result: Dict, msg: str = ""):
    data = result.get("data", {})
    assert data, f"data为空 {msg}"
