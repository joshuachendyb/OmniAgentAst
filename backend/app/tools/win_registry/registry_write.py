# -*- coding: utf-8 -*-
"""
registry_write — 写入Windows注册表键值
【2026-06-22 小健】从 win_registry_tools.py 拆分为独立文件
"""
# 2026-07-31 - 小欧 - CRITICAL: auto_detect 对负整数判定错误。value.isdigit() 对 "-1" 返回 False, 导致 -1(0xFFFFFFFF) 被存为 REG_SZ 而非 REG_DWORD。改用 value.lstrip('-').isdigit() 修复
# 2026-08-06 - 小欧 - 核查7/31未实现项[03][02]修复: 新增_to_unsigned(REG_DWORD/QWORD负数转二补码无符号, 超限报错); REG_BINARY支持"0x1F 0x2A"0x前缀逐token清洗
# 2026-08-06 - 小欧 - 三堂会审修复: BUG-1 _to_unsigned加负数下界校验(-2^(bits-1)..-1); BUG-2删_REG_CONVERTERS REG_BINARY死代码; BUG-6 auto_detect超32位正整数改REG_SZ兜底
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import time as _time_mod
import winreg
from typing import Any, Callable, Dict  # 2026-07-31 小欧: 移除未使用 Optional; Dict 实际仍在使用, 已恢复

from app.logger import logger
from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import ERR_REG_WRITE_FAILED, ERR_PARAMETER_INVALID
from app.tools.win_registry.registry_read import _parse_path, _backup_registry, _validate_root_key  # 2026-07-31 小欧: 移除未使用 ROOT_KEY_MAP
from app.tools.validate.registry_path_checker import validate_registry_key

_REG_TYPE_MAP: Dict[str, int] = {
    "REG_SZ": winreg.REG_SZ, "REG_DWORD": winreg.REG_DWORD, "REG_QWORD": winreg.REG_QWORD,
    "REG_EXPAND_SZ": winreg.REG_EXPAND_SZ, "REG_MULTI_SZ": winreg.REG_MULTI_SZ, "REG_BINARY": winreg.REG_BINARY,
}


def _to_unsigned(value: str, bits: int) -> int:
    """按位宽转换整数值: 负数转二补码无符号(REG_DWORD/QWORD存储语义), 超限正/负数均报错 — 小欧 2026-08-06"""
    num = int(value)
    if num < 0:
        min_val = -(1 << (bits - 1))
        if num < min_val:
            raise ValueError(f"值{num}超出{bits}位有符号范围")
        return (1 << bits) + num
    if num >= (1 << bits):
        raise ValueError(f"值{num}超出{bits}位无符号范围")
    return num


def _normalize_hex_input(value: str) -> str:
    """清洗REG_BINARY十六进制输入: 去空白与0x/0X前缀, 支持"0x1F 0x2A"逐token形式 — 小欧 2026-08-06"""
    return "".join(tok[2:] if tok[:2].lower() == "0x" else tok for tok in value.split())


_REG_CONVERTERS: Dict[str, Callable] = {
    "REG_DWORD": lambda v: _to_unsigned(v, 32), "REG_QWORD": lambda v: _to_unsigned(v, 64),
    "REG_EXPAND_SZ": lambda v: v, "REG_MULTI_SZ": lambda v: v.split(";") if isinstance(v, str) else v,
}


def _convert_reg_value(value_type: str, value: str) -> Any:
    """按注册表类型转换值 — 小健 2026-05-25
    小欧 2026-08-05 修复: REG_BINARY 非法hex抛ValueError被通用except捕获返回误导信息,改为单独校验并给准确hint
    小欧 2026-08-06 修复: REG_BINARY 支持"0x1F 0x2A"0x前缀输入(去前缀后统一bytes.fromhex)
    """
    if value_type == "REG_BINARY":
        hex_str = _normalize_hex_input(value)
        try:
            return bytes.fromhex(hex_str)
        except ValueError:
            raise ValueError(f"REG_BINARY的值不是合法十六进制: {value}")
    converter = _REG_CONVERTERS.get(value_type)
    return converter(value) if converter else value


def _build_registry_write_llm_data(exec_code: str, duration_ms: int, path: str, value_name: str, value: str, value_type: str, err_code: str = None, detail: str = "", hint: str = "") -> dict:
    """registry_write的llm_data构建函数 — 小健 2026-06-22 — 小欧 2026-07-05 新增hint"""
    if exec_code == "error":
        return {
            "summary": f"写入注册表{path}，失败",
            "action": {"tool": "registry_write", "tool_zh": "写入注册表", "target": path, "params": {"path": path, "value_name": value_name}},
            "status": {"exec_code": "error", "message": "写入注册表失败", "code": err_code or ERR_REG_WRITE_FAILED, "detail": detail, "hint": hint if hint else "请检查权限"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"写入注册表{path}，成功: {value_name}={value}（{value_type}）",
        "action": {"tool": "registry_write", "tool_zh": "写入注册表", "target": path, "params": {"path": path, "value_name": value_name}},
        "status": {"exec_code": "success", "message": "写入注册表成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }


def registry_write(path: str, value_name: str, value: str, value_type: str = "auto_detect", backup_before_write: bool = True, dry_run: bool = False, hive: str = "HKCU") -> dict:
    """写入Windows注册表键值 — 小健 2026-06-22 拆分独立文件"""
    # 数值参数(int/bool等)归一为str, 避免后续 auto_detect 的 value.isdigit() 对 int 崩溃 — 小欧 2026-07-12
    if not isinstance(value, str):
        value = str(value)
    is_valid, error_msg, warning_msg = validate_registry_key(path, hive, "write")
    if not is_valid:
        llm_data = _build_registry_write_llm_data("error", 0, path, value_name, value, "auto_detect", err_code=ERR_PARAMETER_INVALID, detail=error_msg, hint="请检查注册表路径和权限")
        return build_error(data={}, llm_data=llm_data)
    if warning_msg:
        logger.warning(f"[registry_write] {warning_msg}")
    t0 = _time_mod.perf_counter()
    full_root_key, sub_key = _parse_path(path, hive)
    hkey = _validate_root_key(full_root_key)
    if hkey is None:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_write_llm_data("error", duration_ms, path, value_name, value, value_type, detail=f"无效的根键: {full_root_key}", hint="请检查根键名称")
        return build_error(data={}, llm_data=llm_data)

    if dry_run:
        try:
            with winreg.OpenKey(hkey, sub_key, 0, winreg.KEY_READ):
                pass
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_registry_write_llm_data("success", duration_ms, path, value_name, value, "dry_run")
            # ---- observation_formatter route -------------------------------------------
            # branch: #21 fallback (key:val) — dry_run path
            # trigger: 无上述20条分支匹配 — path/dry_run 不命中专用分支
            # handler: _format_scalar_data(data) — key | value 单行列表
            # file:    observation_formatter.py:214
            # ------------------------------------------------------------------------------
            return build_success(data={"dry_run": True}, llm_data=llm_data)
        except FileNotFoundError:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_registry_write_llm_data("error", duration_ms, path, value_name, value, value_type, detail=f"键路径不存在: {path}", hint="请检查键路径是否正确")
            return build_error(data={}, llm_data=llm_data)
        except Exception as e:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_registry_write_llm_data("error", duration_ms, path, value_name, value, value_type, detail=str(e), hint="读取注册表异常,请检查权限")
            return build_error(data={}, llm_data=llm_data)

    try:
        if backup_before_write:
            _backup_registry(full_root_key, sub_key, "reg_write")

        actual_type = value_type
        if value_type == "auto_detect":
            # 2026-07-31 小欧 CRITICAL: value.isdigit() 对 "-1" 返回 False, 导致 -1(0xFFFFFFFF) 被存为 REG_SZ 而非 REG_DWORD。改用 value.lstrip('-').isdigit() 修复
            # 2026-08-06 小欧 BUG-6修复: auto_detect 超32位范围默认REG_SZ兜底, 不再误判REG_DWORD致_to_unsigned报错
            num = int(value)
            if -(1 << 31) <= num < (1 << 32):
                actual_type = "REG_DWORD"
            else:
                actual_type = "REG_SZ"

        if actual_type not in _REG_TYPE_MAP:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_registry_write_llm_data("error", duration_ms, path, value_name, value, value_type, detail=f"不支持的类型: {value_type}", hint="请使用支持的值类型(REG_SZ/REG_DWORD等)")
            return build_error(data={}, llm_data=llm_data)

        converted = _convert_reg_value(actual_type, value)
        with winreg.CreateKey(hkey, sub_key) as key:
            winreg.SetValueEx(key, value_name, 0, _REG_TYPE_MAP[actual_type], converted)

        logger.debug(f"[registry_write] 写入成功: {full_root_key}\\{sub_key}\\{value_name}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_write_llm_data("success", duration_ms, path, value_name, value, actual_type)
        # =============================================================================
        # 数据设计：value/value_type 从 data 移除
        # summary 已含全部信息: "写入 HKCU\Software\MyApp\TestValue = Hello World（REG_SZ）"
        # — 小欧 2026-07-06
        # =============================================================================
        # ---- observation_formatter route -------------------------------------------
        # branch: #0 空data
        # trigger: not data → 直接返回 ""
        # file:    observation_formatter.py:74
        # ------------------------------------------------------------------------------
        return build_success(data={}, llm_data=llm_data)
    except PermissionError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_write_llm_data("error", duration_ms, path, value_name, value, value_type, detail=f"权限不足: {path}", hint="请以管理员身份运行")
        return build_error(data={}, llm_data=llm_data)
    except ValueError as e:
        # 2026-08-05 小欧: 区分值转换错误(如REG_BINARY非法hex),给出准确hint而非通用"系统状态"
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_write_llm_data("error", duration_ms, path, value_name, value, value_type, detail=str(e), hint="请检查值内容是否与注册表类型匹配")
        return build_error(data={}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_write_llm_data("error", duration_ms, path, value_name, value, value_type, detail=str(e), hint="写入注册表异常,请检查系统状态")
        return build_error(data={}, llm_data=llm_data)


__all__ = ["registry_write"]
