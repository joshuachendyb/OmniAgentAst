"""P10-02: 执行无效命令 — mock测试

测试场景: 验证shell工具对无效命令返回合理错误信息
-- 小欧 2026-07-03
"""
import pytest


def test_invalid_command_returns_error():
    from app.tools.fundamental.execute_shell_command import shell

    result = shell("invalid_command_xyz_12345", shell_type="ps7", timeout=15)

    # Check via llm_data status
    llm_data = result.get("llm_data", {})
    status = llm_data.get("status", {})
    exec_code = status.get("exec_code", "")
    data = result.get("data", {})

    stderr = (data.get("data", {}) if isinstance(data, dict) else {}).get("stderr", "")
    stdout = (data.get("data", {}) if isinstance(data, dict) else {}).get("stdout", "")
    error_detail = data.get("error_detail", "") if isinstance(data, dict) else ""
    output = (stderr + stdout + error_detail).lower()

    error_terms = ["找不到", "不是内部或外部命令", "not recognized", "not found", "无法识别", "无效命令", "unknown"]
    found = [t for t in error_terms if t.lower() in output]
    assert len(found) >= 1 or exec_code == "error", \
        f"应返回错误, exec_code={exec_code}, stderr={stderr}, stdout={stdout}"
