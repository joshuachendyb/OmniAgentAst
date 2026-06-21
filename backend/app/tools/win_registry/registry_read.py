# -*- coding: utf-8 -*-
"""
registry_read — 读取Windows注册表键值
【2026-06-22 小健】从 win_registry_tools.py 拆分为独立文件
"""

import os
import subprocess
import tempfile
import time as _time_mod
import winreg
from typing import Optional, Dict, Any

from app.utils.logger import logger
from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import SUBPROCESS_TIMEOUT_DEFAULT, HIVE_MAP
from app.constants import ERR_REG_READ_FAILED

ROOT_KEY_MAP = {
    "HKEY_CLASSES_ROOT": winreg.HKEY_CLASSES_ROOT,
    "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
    "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
    "HKEY_USERS": winreg.HKEY_USERS,
    "HKEY_CURRENT_CONFIG": winreg.HKEY_CURRENT_CONFIG,
}

_registry_session_backup = {}


def _validate_root_key(full_root_key: str):
    """校验根键是否有效 — 小健 2026-05-25"""
    return ROOT_KEY_MAP.get(full_root_key)


def _parse_key_path(key_path: str, hive: str = "HKCU") -> tuple:
    """解析key_path,提取根键和子键路径 — 小沈 2026-05-05"""
    for hk_name, full_name in HIVE_MAP.items():
        if key_path.upper().startswith(f"{hk_name}\\"):
            sub = key_path[len(hk_name)+1:]
            return full_name, sub
        if key_path.upper().startswith(f"{full_name}\\"):
            sub = key_path[len(full_name)+1:]
            return full_name, sub
    return HIVE_MAP.get(hive, "HKEY_CURRENT_USER"), key_path


def _backup_registry(root_key: str, sub_key: str, session_id: str) -> str:
    """备份注册表键到临时文件 — 小健 2026-05-19"""
    backup_key = f"{root_key}\\{sub_key}"
    if backup_key in _registry_session_backup:
        return _registry_session_backup[backup_key]

    backup_dir = tempfile.gettempdir()
    from app.utils.time_utils import timestamp_for_filename
    backup_file = os.path.join(backup_dir, f"reg_backup_{session_id}_{timestamp_for_filename()}.reg")

    try:
        export_key = f"{root_key}\\{sub_key}"
        result = subprocess.run(
            ["reg", "export", export_key, backup_file, "/y"],
            capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT_DEFAULT
        )
        if result.returncode == 0 and os.path.exists(backup_file):
            _registry_session_backup[backup_key] = backup_file
            logger.info(f"[registry] 备份成功: {backup_key} -> {backup_file}")
        else:
            logger.warning(f"[registry] reg export失败(返回码{result.returncode}): {result.stderr.strip()}")
            _registry_session_backup[backup_key] = backup_file
    except FileNotFoundError:
        logger.warning("[registry] reg命令不存在,跳过备份")
        _registry_session_backup[backup_key] = backup_file
    except Exception as e:
        logger.warning(f"[registry] 备份失败: {e}")
        _registry_session_backup[backup_key] = backup_file

    return backup_file


def _build_registry_read_llm_data(exec_code: str, duration_ms: int, key_path: str, value_name: str, value: Any = None, value_type: str = "") -> dict:
    """registry_read的llm_data构建函数 — 小健 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"读取注册表失败: {key_path}",
            "action": {"tool": "registry_read", "tool_zh": "读取注册表", "target": key_path, "params": {"key_path": key_path}},
            "status": {"exec_code": "error", "message": "读取注册表失败", "code": ERR_REG_READ_FAILED, "detail": "", "hint": "请检查键路径和权限"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"读取 {key_path}\\{value_name} = {value}（{value_type}）",
        "action": {"tool": "registry_read", "tool_zh": "读取注册表", "target": key_path, "params": {"key_path": key_path, "value_name": value_name}},
        "status": {"exec_code": "success", "message": "读取注册表成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }


def registry_read(key_path: str, value_name: Optional[str] = None, hive: str = "HKCU", output_format: str = "auto") -> dict:
    """读取Windows注册表键值 — 小健 2026-06-22 拆分独立文件"""
    t0 = _time_mod.perf_counter()
    try:
        full_root_key, sub_key = _parse_key_path(key_path, hive)
        hkey = ROOT_KEY_MAP.get(full_root_key)

        if hkey is None:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_registry_read_llm_data("error", duration_ms, key_path, value_name or "")
            return build_error(data={"error_detail": f"无效的根键: {full_root_key}", "params": {"key_path": key_path, "hive": hive}}, llm_data=llm_data)

        with winreg.OpenKey(hkey, sub_key, 0, winreg.KEY_READ) as key:
            value, reg_type = winreg.QueryValueEx(key, value_name)

            value_type_name = {
                winreg.REG_SZ: "REG_SZ", winreg.REG_DWORD: "REG_DWORD", winreg.REG_QWORD: "REG_QWORD",
                winreg.REG_EXPAND_SZ: "REG_EXPAND_SZ", winreg.REG_MULTI_SZ: "REG_MULTI_SZ",
                winreg.REG_BINARY: "REG_BINARY", winreg.REG_NONE: "REG_NONE",
            }.get(reg_type, f"UNKNOWN({reg_type})")

            formatted_value = value
            if output_format == "hex" and isinstance(value, (bytes, bytearray)):
                formatted_value = value.hex()

            result_data = {
                "key_path": f"{full_root_key}\\{sub_key}",
                "value_name": value_name or "(默认)",
                "value": formatted_value,
                "value_type": value_type_name,
            }

            logger.info(f"[registry_read] 成功读取: {full_root_key}\\{sub_key}\\{value_name or '(默认)'}")
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_registry_read_llm_data("success", duration_ms, result_data["key_path"], result_data["value_name"], formatted_value, value_type_name)
            return build_success(data=result_data, llm_data=llm_data)

    except FileNotFoundError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_read_llm_data("error", duration_ms, key_path, value_name or "")
        return build_error(data={"error_detail": f"注册表键或值不存在: {key_path}", "params": {"key_path": key_path, "value_name": value_name}}, llm_data=llm_data)
    except PermissionError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_read_llm_data("error", duration_ms, key_path, value_name or "")
        return build_error(data={"error_detail": f"权限不足: {key_path}", "params": {"key_path": key_path}}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_read_llm_data("error", duration_ms, key_path, value_name or "")
        return build_error(data={"error_detail": str(e), "params": {"key_path": key_path}}, llm_data=llm_data)


__all__ = ["registry_read", "ROOT_KEY_MAP", "_registry_session_backup", "_parse_key_path", "_backup_registry", "_validate_root_key"]