# -*- coding: utf-8 -*-
"""
registry_write — 写入Windows注册表键值
【2026-06-22 小健】从 win_registry_tools.py 拆分为独立文件
"""

import time as _time_mod
import winreg
from typing import Optional, Dict, Any, Callable

from app.utils.logger import logger
from app.tools.tool_response import build_success, build_error
from app.constants import ERR_REG_WRITE_FAILED
from app.tools.win_registry.registry_read import ROOT_KEY_MAP, _parse_key_path, _backup_registry, _validate_root_key

_REG_TYPE_MAP: Dict[str, int] = {
    "REG_SZ": winreg.REG_SZ, "REG_DWORD": winreg.REG_DWORD, "REG_QWORD": winreg.REG_QWORD,
    "REG_EXPAND_SZ": winreg.REG_EXPAND_SZ, "REG_MULTI_SZ": winreg.REG_MULTI_SZ, "REG_BINARY": winreg.REG_BINARY,
}

_REG_CONVERTERS: Dict[str, Callable] = {
    "REG_DWORD": lambda v: int(v), "REG_QWORD": lambda v: int(v),
    "REG_EXPAND_SZ": lambda v: v, "REG_BINARY": lambda v: bytes.fromhex(v.replace(" ", "")),
    "REG_MULTI_SZ": lambda v: v.split(";") if isinstance(v, str) else v,
}


def _convert_reg_value(value_type: str, value: str) -> Any:
    """按注册表类型转换值 — 小健 2026-05-25"""
    converter = _REG_CONVERTERS.get(value_type)
    return converter(value) if converter else value


def _build_registry_write_llm_data(exec_code: str, duration_ms: int, key_path: str, value_name: str, value: str, value_type: str) -> dict:
    """registry_write的llm_data构建函数 — 小健 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"写入注册表失败: {key_path}",
            "action": {"tool": "registry_write", "tool_zh": "写入注册表", "target": key_path, "params": {"key_path": key_path, "value_name": value_name}},
            "status": {"exec_code": "error", "message": "写入注册表失败", "code": ERR_REG_WRITE_FAILED, "detail": "", "hint": "请检查权限"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"写入 {key_path}\\{value_name} = {value}（{value_type}）",
        "action": {"tool": "registry_write", "tool_zh": "写入注册表", "target": key_path, "params": {"key_path": key_path, "value_name": value_name}},
        "status": {"exec_code": "success", "message": "写入注册表成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }


def registry_write(key_path: str, value_name: str, value: str, value_type: str = "auto_detect", backup_before_write: bool = True, dry_run: bool = False, hive: str = "HKCU") -> dict:
    """写入Windows注册表键值 — 小健 2026-06-22 拆分独立文件"""
    t0 = _time_mod.perf_counter()
    full_root_key, sub_key = _parse_key_path(key_path, hive)
    hkey = _validate_root_key(full_root_key)
    if hkey is None:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_write_llm_data("error", duration_ms, key_path, value_name, value, value_type)
        return build_error(data={"error_detail": f"无效的根键: {full_root_key}", "params": {"key_path": key_path, "hive": hive}}, llm_data=llm_data)

    if dry_run:
        try:
            with winreg.OpenKey(hkey, sub_key, 0, winreg.KEY_READ):
                pass
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_registry_write_llm_data("success", duration_ms, key_path, value_name, value, "dry_run")
            return build_success(data={"key_path": key_path, "dry_run": True}, llm_data=llm_data)
        except FileNotFoundError:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_registry_write_llm_data("error", duration_ms, key_path, value_name, value, value_type)
            return build_error(data={"error_detail": f"键路径不存在: {key_path}", "params": {"key_path": key_path}}, llm_data=llm_data)
        except Exception as e:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_registry_write_llm_data("error", duration_ms, key_path, value_name, value, value_type)
            return build_error(data={"error_detail": str(e), "params": {"key_path": key_path}}, llm_data=llm_data)

    try:
        if backup_before_write:
            _backup_registry(full_root_key, sub_key, "reg_write")

        actual_type = value_type
        if value_type == "auto_detect":
            actual_type = "REG_DWORD" if value.isdigit() else "REG_SZ"

        if actual_type not in _REG_TYPE_MAP:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_registry_write_llm_data("error", duration_ms, key_path, value_name, value, value_type)
            return build_error(data={"error_detail": f"不支持的类型: {value_type}", "params": {"key_path": key_path, "value_type": value_type}}, llm_data=llm_data)

        converted = _convert_reg_value(actual_type, value)
        with winreg.CreateKey(hkey, sub_key) as key:
            winreg.SetValueEx(key, value_name, 0, _REG_TYPE_MAP[actual_type], converted)

        logger.info(f"[registry_write] 写入成功: {full_root_key}\\{sub_key}\\{value_name}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"key_path": f"{full_root_key}\\{sub_key}", "value_name": value_name, "value": value, "value_type": actual_type}
        llm_data = _build_registry_write_llm_data("success", duration_ms, data["key_path"], value_name, value, actual_type)
        return build_success(data=data, llm_data=llm_data)
    except PermissionError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_write_llm_data("error", duration_ms, key_path, value_name, value, value_type)
        return build_error(data={"error_detail": f"权限不足: {key_path}", "params": {"key_path": key_path}}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_write_llm_data("error", duration_ms, key_path, value_name, value, value_type)
        return build_error(data={"error_detail": str(e), "params": {"key_path": key_path}}, llm_data=llm_data)


__all__ = ["registry_write"]