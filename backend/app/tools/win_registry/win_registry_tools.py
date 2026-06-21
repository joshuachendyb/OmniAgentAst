# -*- coding: utf-8 -*-
"""
REGISTRY 工具函数模块 - Windows注册表操作工具
【设计说明 2026-06-17 北京老陈确认】本文件是按工具分类聚合的实现文件，文件大是正常设计。后续审查关注功能逻辑本身的代码10大规范遵守和最优美简洁性，禁止以"文件过大"作为问题提出。

【创建时间】2026-05-02 小沈
【更新时间】2026-06-16 小沈 - 拆分registry_control为registry_read/registry_write/registry_delete
【2026-06-21 小健】Phase 1 builder改造: build_success/error适配新3字段签名

包含:
- registry_read: 读取注册表键值
- registry_write: 写入注册表键值
- registry_delete: 删除注册表键值或子键

Author: 小沈 - 2026-05-02
"""

import os
import subprocess
import tempfile
import time as _time_mod
import winreg
from typing import Optional, Dict, Any, Literal, Callable
from datetime import datetime
from app.constants import (ERR_REG_DELETE_FAILED, ERR_REG_INVALID_PARAM, ERR_REG_PERMISSION_DENIED,
    ERR_REG_READ_FAILED, ERR_REG_UNSUPPORTED_TYPE, ERR_REG_VALIDATE_FAILED, ERR_REG_WRITE_FAILED,
    ERR_SYS_REG_CANNOT_DELETE_ROOT, ERR_SYS_REG_INVALID_ROOT_KEY, ERR_SYS_REG_KEY_NOT_EMPTY,
    ERR_SYS_REG_KEY_NOT_FOUND)

from app.utils.logger import logger

from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import SUBPROCESS_TIMEOUT_DEFAULT, HIVE_MAP


ROOT_KEY_MAP = {
    "HKEY_CLASSES_ROOT": winreg.HKEY_CLASSES_ROOT,
    "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
    "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
    "HKEY_USERS": winreg.HKEY_USERS,
    "HKEY_CURRENT_CONFIG": winreg.HKEY_CURRENT_CONFIG,
}

_registry_session_backup = {}


def _parse_key_path(key_path: str, hive: str = "HKCU") -> tuple:
    """解析key_path,提取根键和子键路径 - 小沈 2026-05-05 修正映射逻辑"""
    for hk_name, full_name in HIVE_MAP.items():
        if key_path.upper().startswith(f"{hk_name}\\"):
            sub = key_path[len(hk_name)+1:]
            return full_name, sub
        if key_path.upper().startswith(f"{full_name}\\"):
            sub = key_path[len(full_name)+1:]
            return full_name, sub
    return HIVE_MAP.get(hive, "HKEY_CURRENT_USER"), key_path


def _backup_registry(root_key: str, sub_key: str, session_id: str) -> str:
    """备份注册表键到临时文件 - 小健 2026-05-19"""
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


def _build_registry_read_llm(exec_code: str, duration_ms: int, key_path: str, value_name: str, value: Any = None, value_type: str = "") -> dict:
    """registry_read的llm_data构建函数 — 小健 2026-06-21"""
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


def _build_registry_write_llm(exec_code: str, duration_ms: int, key_path: str, value_name: str, value: str, value_type: str) -> dict:
    """registry_write的llm_data构建函数 — 小健 2026-06-21"""
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


def _build_registry_delete_llm(exec_code: str, duration_ms: int, key_path: str, action: str) -> dict:
    """registry_delete的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": f"删除注册表失败: {key_path}",
            "action": {"tool": "registry_delete", "tool_zh": "删除注册表", "target": key_path, "params": {"key_path": key_path}},
            "status": {"exec_code": "error", "message": "删除注册表失败", "code": ERR_REG_DELETE_FAILED, "detail": "", "hint": "请检查键路径和权限"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"已删除注册表 {key_path}（{action}）",
        "action": {"tool": "registry_delete", "tool_zh": "删除注册表", "target": key_path, "params": {"key_path": key_path}},
        "status": {"exec_code": "success", "message": "删除注册表成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }


def registry_read(key_path: str, value_name: Optional[str] = None, hive: str = "HKCU", output_format: str = "auto") -> dict:
    """读取Windows注册表键值 — 小健 2026-06-21 builder改造"""
    t0 = _time_mod.perf_counter()
    try:
        full_root_key, sub_key = _parse_key_path(key_path, hive)
        hkey = ROOT_KEY_MAP.get(full_root_key)

        if hkey is None:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_registry_read_llm("error", duration_ms, key_path, value_name or "")
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
            llm_data = _build_registry_read_llm("success", duration_ms, result_data["key_path"], result_data["value_name"], formatted_value, value_type_name)
            return build_success(data=result_data, llm_data=llm_data)

    except FileNotFoundError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_read_llm("error", duration_ms, key_path, value_name or "")
        return build_error(data={"error_detail": f"注册表键或值不存在: {key_path}", "params": {"key_path": key_path, "value_name": value_name}}, llm_data=llm_data)
    except PermissionError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_read_llm("error", duration_ms, key_path, value_name or "")
        return build_error(data={"error_detail": f"权限不足: {key_path}", "params": {"key_path": key_path}}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_read_llm("error", duration_ms, key_path, value_name or "")
        return build_error(data={"error_detail": str(e), "params": {"key_path": key_path}}, llm_data=llm_data)


_REG_TYPE_MAP: Dict[str, int] = {
    "REG_SZ": winreg.REG_SZ, "REG_DWORD": winreg.REG_DWORD, "REG_QWORD": winreg.REG_QWORD,
    "REG_EXPAND_SZ": winreg.REG_EXPAND_SZ, "REG_MULTI_SZ": winreg.REG_MULTI_SZ, "REG_BINARY": winreg.REG_BINARY,
}


def _validate_root_key(full_root_key: str) -> Optional[int]:
    """校验根键是否有效 — 小健 2026-05-25"""
    return ROOT_KEY_MAP.get(full_root_key)


_REG_CONVERTERS: Dict[str, Callable] = {
    "REG_DWORD": lambda v: int(v), "REG_QWORD": lambda v: int(v),
    "REG_EXPAND_SZ": lambda v: v, "REG_BINARY": lambda v: bytes.fromhex(v.replace(" ", "")),
    "REG_MULTI_SZ": lambda v: v.split(";") if isinstance(v, str) else v,
}


def _convert_reg_value(value_type: str, value: str) -> Any:
    """按注册表类型转换值 — 小健 2026-05-25"""
    converter = _REG_CONVERTERS.get(value_type)
    return converter(value) if converter else value


def registry_write(key_path: str, value_name: str, value: str, value_type: str = "auto_detect", backup_before_write: bool = True, dry_run: bool = False, hive: str = "HKCU") -> dict:
    """写入Windows注册表键值 — 小健 2026-06-21 builder改造"""
    t0 = _time_mod.perf_counter()
    full_root_key, sub_key = _parse_key_path(key_path, hive)
    hkey = _validate_root_key(full_root_key)
    if hkey is None:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_write_llm("error", duration_ms, key_path, value_name, value, value_type)
        return build_error(data={"error_detail": f"无效的根键: {full_root_key}", "params": {"key_path": key_path, "hive": hive}}, llm_data=llm_data)

    if dry_run:
        try:
            with winreg.OpenKey(hkey, sub_key, 0, winreg.KEY_READ):
                pass
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_registry_write_llm("success", duration_ms, key_path, value_name, value, "dry_run")
            return build_success(data={"key_path": key_path, "dry_run": True}, llm_data=llm_data)
        except FileNotFoundError:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_registry_write_llm("error", duration_ms, key_path, value_name, value, value_type)
            return build_error(data={"error_detail": f"键路径不存在: {key_path}", "params": {"key_path": key_path}}, llm_data=llm_data)
        except Exception as e:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_registry_write_llm("error", duration_ms, key_path, value_name, value, value_type)
            return build_error(data={"error_detail": str(e), "params": {"key_path": key_path}}, llm_data=llm_data)

    try:
        if backup_before_write:
            _backup_registry(full_root_key, sub_key, "reg_write")

        actual_type = value_type
        if value_type == "auto_detect":
            actual_type = "REG_DWORD" if value.isdigit() else "REG_SZ"

        if actual_type not in _REG_TYPE_MAP:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_registry_write_llm("error", duration_ms, key_path, value_name, value, value_type)
            return build_error(data={"error_detail": f"不支持的类型: {value_type}", "params": {"key_path": key_path, "value_type": value_type}}, llm_data=llm_data)

        converted = _convert_reg_value(actual_type, value)
        with winreg.CreateKey(hkey, sub_key) as key:
            winreg.SetValueEx(key, value_name, 0, _REG_TYPE_MAP[actual_type], converted)

        logger.info(f"[registry_write] 写入成功: {full_root_key}\\{sub_key}\\{value_name}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"key_path": f"{full_root_key}\\{sub_key}", "value_name": value_name, "value": value, "value_type": actual_type}
        llm_data = _build_registry_write_llm("success", duration_ms, data["key_path"], value_name, value, actual_type)
        return build_success(data=data, llm_data=llm_data)
    except PermissionError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_write_llm("error", duration_ms, key_path, value_name, value, value_type)
        return build_error(data={"error_detail": f"权限不足: {key_path}", "params": {"key_path": key_path}}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_write_llm("error", duration_ms, key_path, value_name, value, value_type)
        return build_error(data={"error_detail": str(e), "params": {"key_path": key_path}}, llm_data=llm_data)


def registry_delete(key_path: str, value_name: Optional[str] = None, backup_before_delete: bool = True, recursive: bool = False, hive: str = "HKCU") -> dict:
    """删除Windows注册表键值或子键 — 小健 2026-06-21 builder改造"""
    t0 = _time_mod.perf_counter()
    try:
        full_root_key, sub_key = _parse_key_path(key_path)
        hkey = ROOT_KEY_MAP.get(full_root_key)

        if hkey is None:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_registry_delete_llm("error", duration_ms, key_path, "")
            return build_error(data={"error_detail": f"无效的根键: {full_root_key}", "params": {"key_path": key_path, "hive": hive}}, llm_data=llm_data)

        if backup_before_delete:
            _backup_registry(full_root_key, sub_key, "reg_delete")

        if value_name is not None:
            with winreg.OpenKey(hkey, sub_key, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, value_name)

            result_data = {"key_path": f"{full_root_key}\\{sub_key}", "value_name": value_name, "action": "deleted_value"}
            logger.info(f"[registry_delete] 成功删除值: {full_root_key}\\{sub_key}\\{value_name}")
        else:
            if not recursive:
                try:
                    with winreg.OpenKey(hkey, sub_key, 0, winreg.KEY_READ) as key:
                        i = 0
                        try:
                            while True:
                                winreg.EnumKey(key, i)
                                i += 1
                        except OSError:
                            pass
                        if i > 0:
                            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                            llm_data = _build_registry_delete_llm("error", duration_ms, key_path, "")
                            return build_error(data={"error_detail": f"键不为空({i}个子键),使用 recursive=True 强制删除", "params": {"key_path": f"{full_root_key}\\{sub_key}", "subkey_count": i}}, llm_data=llm_data)
                except FileNotFoundError:
                    pass

            parent_key = "\\".join(sub_key.split("\\")[:-1])
            key_name = sub_key.split("\\")[-1]

            if not parent_key:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_registry_delete_llm("error", duration_ms, key_path, "")
                return build_error(data={"error_detail": "不能直接删除根键下的子键", "params": {"key_path": key_path}}, llm_data=llm_data)

            with winreg.OpenKey(hkey, parent_key, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteKey(key, key_name)

            result_data = {"key_path": f"{full_root_key}\\{sub_key}", "action": "deleted_key", "recursive": recursive}
            logger.info(f"[registry_delete] 成功删除子键: {full_root_key}\\{sub_key}")

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_delete_llm("success", duration_ms, result_data["key_path"], result_data["action"])
        return build_success(data=result_data, llm_data=llm_data)

    except FileNotFoundError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_delete_llm("error", duration_ms, key_path, "")
        return build_error(data={"error_detail": f"注册表键或值不存在: {key_path}", "params": {"key_path": key_path, "value_name": value_name}}, llm_data=llm_data)
    except PermissionError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_delete_llm("error", duration_ms, key_path, "")
        return build_error(data={"error_detail": f"权限不足: {key_path}", "params": {"key_path": key_path}}, llm_data=llm_data)
    except OSError as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_delete_llm("error", duration_ms, key_path, "")
        return build_error(data={"error_detail": f"删除失败(可能子键不为空): {e}", "params": {"key_path": key_path}}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_delete_llm("error", duration_ms, key_path, "")
        return build_error(data={"error_detail": str(e), "params": {"key_path": key_path}}, llm_data=llm_data)
