"""P10-01: 路径权限拒绝场景 — mock测试

测试场景: 验证路径安全校验能拦截受保护系统路径
-- 小欧 2026-07-03
编辑历史: 2026-08-11 小欧 对齐validate_path 3元组协议(v1.43 P3): 2元组解包补第3元素category, 消除not enough values to unpack
"""
import pytest


def test_forbidden_system_file_rejected():
    from app.services.safety.path_safe_check import validate_path

    protected_path = r"C:\Windows\System32\config\SAM"
    is_valid, msg, _ = validate_path(protected_path)
    assert not is_valid, f"SAM文件应被拒绝, validate_path返回({is_valid}, {msg})"
    assert msg is not None and "禁止" in str(msg), f"应提示'禁止访问', 但消息为: {msg}"


def test_forbidden_system_dir_rejected():
    from app.services.safety.path_safe_check import validate_path

    protected_dir = r"C:\Windows\System32\config"
    is_valid, msg, _ = validate_path(protected_dir)
    assert not is_valid, f"config目录应被拒绝, validate_path返回({is_valid}, {msg})"
    assert msg is not None and "禁止" in str(msg), f"应提示'禁止访问', 但消息为: {msg}"


def test_allowed_drive_path_accepted():
    from app.services.safety.path_safe_check import validate_path

    safe_path = r"E:\test_dir\test.txt"
    is_valid, msg, _ = validate_path(safe_path)
    assert is_valid, f"E盘路径应放行, validate_path返回({is_valid}, {msg})"
