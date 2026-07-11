# -*- coding: utf-8 -*-
"""
registry_delete — 删除Windows注册表键值或子键
【2026-06-22 小健】从 win_registry_tools.py 拆分为独立文件
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import time as _time_mod
import winreg
from typing import Optional, Dict, Any

from app.logger import logger
from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import ERR_REG_DELETE_FAILED, ERR_PARAMETER_INVALID, SUBPROCESS_TIMEOUT_DEFAULT
from app.tools.win_registry.registry_read import ROOT_KEY_MAP, _parse_key_path, _backup_registry
from app.tools.validate.registry_path_checker import validate_delete_safety

# hkey(int) -> 根键名 反向映射, 供 reg.exe 拼接完整键路径 — 小欧 2026-07-12
ROOT_KEY_MAP_REVERSE = {v: k for k, v in ROOT_KEY_MAP.items()}


def _build_registry_delete_llm_data(exec_code: str, duration_ms: int, key_path: str, action: str, err_code: str = None, detail: str = "", hint: str = "") -> dict:
    """registry_delete的llm_data构建函数 — 小健 2026-06-22 — 小欧 2026-07-05 新增hint"""
    if exec_code == "error":
        return {
            "summary": f"删除注册表{key_path}，失败",
            "action": {"tool": "registry_delete", "tool_zh": "删除注册表", "target": key_path, "params": {"key_path": key_path}},
            "status": {"exec_code": "error", "message": "删除注册表失败", "code": err_code or ERR_REG_DELETE_FAILED, "detail": detail, "hint": hint if hint else "请检查键路径和权限"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"删除注册表{key_path}，成功: {action}",
        "action": {"tool": "registry_delete", "tool_zh": "删除注册表", "target": key_path, "params": {"key_path": key_path}},
        "status": {"exec_code": "success", "message": "删除注册表成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }


def _delete_registry_recursive(hkey, sub_key):
    """递归删除注册表键及其所有子键 — 小欧 2026-06-27

    主路径用系统 reg.exe 原子级递归删除(规避 winreg 父句柄枚举视图不刷新导致
    的嵌套子键死循环挂起, 详见 test_delete_nonempty_key_recursive_true_still_fails) — 小欧 2026-07-12
    """
    import subprocess
    full_key = f"{ROOT_KEY_MAP_REVERSE.get(hkey, 'HKEY_CURRENT_USER')}\\{sub_key}"
    try:
        result = subprocess.run(
            ["reg", "delete", full_key, "/f"],
            capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT_DEFAULT,
        )
        if result.returncode == 0:
            return
        logger.warning(f"[registry_delete] reg.exe递归删除失败(返回码{result.returncode}), 回退winreg: {result.stderr.strip()}")
    except Exception as e:
        logger.warning(f"[registry_delete] reg.exe递归删除异常, 回退winreg: {e}")

    # 回退: winreg 递归(单层子键有效, 嵌套场景可能受枚举视图影响)
    with winreg.OpenKey(hkey, sub_key, 0, winreg.KEY_ALL_ACCESS) as key:
        while True:
            try:
                subkey_name = winreg.EnumKey(key, 0)
            except OSError:
                break
            _delete_registry_recursive(hkey, f"{sub_key}\\{subkey_name}")
        while True:
            try:
                value_name = winreg.EnumValue(key, 0)[0]
                winreg.DeleteValue(key, value_name)
            except OSError:
                break


def registry_delete(key_path: str, value_name: Optional[str] = None, backup_before_delete: bool = True, recursive: bool = False, hive: str = "HKCU") -> dict:
    """删除Windows注册表键值或子键 — 小健 2026-06-22 拆分独立文件"""
    is_valid, error_msg, warning_msg = validate_delete_safety(key_path, value_name, hive, recursive)
    if not is_valid:
        llm_data = _build_registry_delete_llm_data("error", 0, key_path, "", err_code=ERR_PARAMETER_INVALID, detail=error_msg, hint="请检查注册表路径和权限")
        return build_error(data={}, llm_data=llm_data)
    if warning_msg:
        logger.warning(f"[registry_delete] {warning_msg}")
    t0 = _time_mod.perf_counter()
    try:
        full_root_key, sub_key = _parse_key_path(key_path, hive=hive)
        hkey = ROOT_KEY_MAP.get(full_root_key)

        if hkey is None:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_registry_delete_llm_data("error", duration_ms, key_path, "", detail=f"无效的根键: {full_root_key}", hint="请检查根键名称")
            return build_error(data={}, llm_data=llm_data)

        if backup_before_delete:
            _backup_registry(full_root_key, sub_key, "reg_delete")

        if value_name is not None:
            with winreg.OpenKey(hkey, sub_key, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, value_name)

            logger.debug(f"[registry_delete] 成功删除值: {full_root_key}\\{sub_key}\\{value_name}")
        else:
            # 非空键且recursive=False 已在 validate_delete_safety 拦截; 此处仅处理已放行(空键)或recursive=True 的删除 — 小欧 2026-07-12
            parent_key = "\\".join(sub_key.split("\\")[:-1])
            key_name = sub_key.split("\\")[-1]

            if not parent_key:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_registry_delete_llm_data("error", duration_ms, key_path, "", detail="不能直接删除根键下的子键", hint="不能直接删除根键下的子键")
                return build_error(data={}, llm_data=llm_data)

            if recursive:
                _delete_registry_recursive(hkey, sub_key)
                # reg.exe递归删除已原子删掉整棵子树(含本键), 再删父键下的本键会FileNotFoundError — 小欧 2026-07-12
                try:
                    with winreg.OpenKey(hkey, sub_key, 0, winreg.KEY_READ):
                        pass
                except FileNotFoundError:
                    logger.debug(f"[registry_delete] reg递归删除已移除整键: {full_root_key}\\{sub_key}")
                    action = "子键已删除"
                    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                    llm_data = _build_registry_delete_llm_data("success", duration_ms, key_path, action)
                    return build_success(data={}, llm_data=llm_data)

            with winreg.OpenKey(hkey, parent_key, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteKey(key, key_name)

            logger.debug(f"[registry_delete] 成功删除子键: {full_root_key}\\{sub_key}")

        action = "值已删除" if value_name is not None else "子键已删除"
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_delete_llm_data("success", duration_ms, key_path, action)
        # =============================================================================
        # 数据设计：action 从 data 移除
        # summary 已含全部信息: "已删除注册表 HKCU\Software\MyApp\TestValue（deleted_value）"
        # — 小欧 2026-07-06
        # =============================================================================
        # ---- observation_formatter route -------------------------------------------
        # branch: #0 空data
        # trigger: not data → 直接返回 ""
        # file:    observation_formatter.py:74
        # ------------------------------------------------------------------------------
        return build_success(data={}, llm_data=llm_data)

    except FileNotFoundError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_delete_llm_data("error", duration_ms, key_path, "", detail=f"注册表键或值不存在: {key_path}", hint="请检查键路径是否正确")
        return build_error(data={}, llm_data=llm_data)
    except PermissionError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_delete_llm_data("error", duration_ms, key_path, "", detail=f"权限不足: {key_path}", hint="请以管理员身份运行")
        return build_error(data={}, llm_data=llm_data)
    except OSError as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_delete_llm_data("error", duration_ms, key_path, "", detail=f"删除失败: {e}", hint="删除失败,请检查键是否为空")
        return build_error(data={}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_delete_llm_data("error", duration_ms, key_path, "", detail=str(e), hint="删除注册表异常,请检查系统状态")
        return build_error(data={}, llm_data=llm_data)


__all__ = ["registry_delete"]