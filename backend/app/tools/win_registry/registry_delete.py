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

from app.utils.logger import logger
from app.tools.tool_response import build_success, build_error
from app.constants import ERR_REG_DELETE_FAILED
from app.tools.win_registry.registry_read import ROOT_KEY_MAP, _parse_key_path, _backup_registry


def _build_registry_delete_llm_data(exec_code: str, duration_ms: int, key_path: str, action: str) -> dict:
    """registry_delete的llm_data构建函数 — 小健 2026-06-22"""
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


def registry_delete(key_path: str, value_name: Optional[str] = None, backup_before_delete: bool = True, recursive: bool = False, hive: str = "HKCU") -> dict:
    """删除Windows注册表键值或子键 — 小健 2026-06-22 拆分独立文件"""
    t0 = _time_mod.perf_counter()
    try:
        full_root_key, sub_key = _parse_key_path(key_path)
        hkey = ROOT_KEY_MAP.get(full_root_key)

        if hkey is None:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_registry_delete_llm_data("error", duration_ms, key_path, "")
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
                            llm_data = _build_registry_delete_llm_data("error", duration_ms, key_path, "")
                            return build_error(data={"error_detail": f"键不为空({i}个子键),使用 recursive=True 强制删除", "params": {"key_path": f"{full_root_key}\\{sub_key}", "subkey_count": i}}, llm_data=llm_data)
                except FileNotFoundError:
                    pass

            parent_key = "\\".join(sub_key.split("\\")[:-1])
            key_name = sub_key.split("\\")[-1]

            if not parent_key:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_registry_delete_llm_data("error", duration_ms, key_path, "")
                return build_error(data={"error_detail": "不能直接删除根键下的子键", "params": {"key_path": key_path}}, llm_data=llm_data)

            with winreg.OpenKey(hkey, parent_key, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteKey(key, key_name)

            result_data = {"key_path": f"{full_root_key}\\{sub_key}", "action": "deleted_key", "recursive": recursive}
            logger.info(f"[registry_delete] 成功删除子键: {full_root_key}\\{sub_key}")

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_delete_llm_data("success", duration_ms, result_data["key_path"], result_data["action"])
        return build_success(data=result_data, llm_data=llm_data)

    except FileNotFoundError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_delete_llm_data("error", duration_ms, key_path, "")
        return build_error(data={"error_detail": f"注册表键或值不存在: {key_path}", "params": {"key_path": key_path, "value_name": value_name}}, llm_data=llm_data)
    except PermissionError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_delete_llm_data("error", duration_ms, key_path, "")
        return build_error(data={"error_detail": f"权限不足: {key_path}", "params": {"key_path": key_path}}, llm_data=llm_data)
    except OSError as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_delete_llm_data("error", duration_ms, key_path, "")
        return build_error(data={"error_detail": f"删除失败(可能子键不为空): {e}", "params": {"key_path": key_path}}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_delete_llm_data("error", duration_ms, key_path, "")
        return build_error(data={"error_detail": str(e), "params": {"key_path": key_path}}, llm_data=llm_data)


__all__ = ["registry_delete"]