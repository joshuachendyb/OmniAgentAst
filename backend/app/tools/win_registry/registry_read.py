# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-25 - 小欧 - 不存在的键reg export失败日志WARNING→INFO(正常业务场景不应报WARNING)
# 2026-07-31 - 小欧 - CRITICAL: _backup_registry 失败路径不缓存备份路径(原在 returncode!=0/FileNotFoundError/Exception 3 处均缓存)。失败后续操作命中缓存跳过备份, 导致 registry_write/delete 丢失安全保障
# 2026-09-20 - 小欧 - P2 X4锁+备份三原则(A-4/D-6/E-5)+D-7(红case A-4/D-6/D-7/E-5 驱动):
#   ①X4: 新增 threading.Lock 保护 _registry_session_backup(多会话并行竞态);
#   ②A-4: 缓存键含 session_id → 跨会话备份隔离, 不误复用它会话快照;
#   ③D-6: 文件名加 uuid4 唯一后缀 → 同秒/同会话不再撞名互覆;
#   ④E-5: 去掉"缓存命中即返回"短路 → 每次调用重新导出(备份=写前最新快照);
#   ⑤D-7: 失败显式返回 None → 调用方据 None 中止危险操作, 杜绝"误以为已备份"。
#   compliance: SRP/禁止backward
# 2026-09-20 - 小欧 - 三堂会审BUG-14修复: _backup_registry新建备份前清理同key旧备份文件(防temp目录磁盘泄漏)
# 2026-09-20 - 小欧 - E-2修复(写失败回滚安全网): 新增 _restore_registry_from_backup(reg import 恢复), 供
#   registry_write 在写失败(PermissionError/ValueError/Exception)分支回滚; _backup_registry 返回值缓存到
#   _backup_file 供恢复定位。compliance: SRP(恢复职责归属读取侧备份)+禁止backward
"""
registry_read — 读取Windows注册表键值
【2026-06-22 小健】从 win_registry_tools.py 拆分为独立文件
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import os
import threading  # 2026-09-20 小欧 X4: 多会话并行时 _registry_session_backup 跨任务读写竞态 — 小欧-2026-09-20
import subprocess
import tempfile
import time as _time_mod
import winreg
from uuid import uuid4  # 2026-09-20 小欧 D-6: 备份文件名唯一后缀 — 小欧-2026-09-20
from app.utils.time_utils import timestamp_for_filename
from typing import Optional, Any  # 2026-07-31 小欧: 移除未使用 Dict

from app.logger import logger
from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import SUBPROCESS_TIMEOUT_DEFAULT, HIVE_MAP
from app.tools.validate.registry_path_checker import validate_registry_key
from app.tools.tool_constants import ERR_REG_READ_FAILED, ERR_PARAMETER_INVALID

ROOT_KEY_MAP = {
    "HKEY_CLASSES_ROOT": winreg.HKEY_CLASSES_ROOT,
    "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
    "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
    "HKEY_USERS": winreg.HKEY_USERS,
    "HKEY_CURRENT_CONFIG": winreg.HKEY_CURRENT_CONFIG,
}

_registry_session_backup = {}
_registry_backup_lock = threading.Lock()  # 2026-09-20 小欧 X4: 保护备份缓存 — 小欧-2026-09-20


def _validate_root_key(full_root_key: str):
    """校验根键是否有效 — 小健 2026-05-25"""
    return ROOT_KEY_MAP.get(full_root_key)


def _parse_path(path: str, hive: str = "HKCU") -> tuple:
    """解析path,提取根键和子键路径 — 小沈 2026-05-05"""
    for hk_name, full_name in HIVE_MAP.items():
        if path.upper().startswith(f"{hk_name}\\"):
            sub = path[len(hk_name)+1:]
            return full_name, sub
        if path.upper().startswith(f"{full_name}\\"):
            sub = path[len(full_name)+1:]
            return full_name, sub
    return HIVE_MAP.get(hive, "HKEY_CURRENT_USER"), path


def _backup_registry(root_key: str, sub_key: str, session_id: str) -> Optional[str]:
    """备份注册表键到临时文件 — 小健 2026-05-19
    2026-09-20 小欧 备份三原则(A-4/D-6/E-5)+D-7 同源收敛(红case A-4/D-6/D-7/E-5 驱动):
      A-4 缓存键含 session_id → 跨会话备份隔离, 不误复用它会话快照;
      D-6 文件名加 uuid4 唯一后缀 → 同秒/同会话不再撞名互覆;
      E-5 去掉"缓存命中即返回"短路 → 每次调用重新导出, 缓存仅登记供校验, 备份=写前最新快照;
      D-7 失败显式返回 None → 调用方据 None 中止危险操作, 杜绝"误以为已备份"。
    BUG-14修复(小欧 2026-09-20): 新建备份前清理同key旧备份文件, 防temp目录磁盘泄漏。
    """
    backup_key = f"{session_id}::{root_key}\\{sub_key}"  # A-4: 会话级缓存键
    backup_dir = tempfile.gettempdir()

    # BUG-14修复: 清理同key旧备份文件, 防磁盘泄漏
    with _registry_backup_lock:
        old_file = _registry_session_backup.get(backup_key)
    if old_file and os.path.exists(old_file):
        try:
            os.unlink(old_file)
        except OSError:
            pass

    backup_file = os.path.join(
        backup_dir,
        f"reg_backup_{session_id}_{timestamp_for_filename()}_{uuid4().hex[:8]}.reg",  # D-6: 唯一文件名
    )

    try:
        export_key = f"{root_key}\\{sub_key}"
        result = subprocess.run(
            ["reg", "export", export_key, backup_file, "/y"],
            capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT_DEFAULT
        )
        if result.returncode == 0 and os.path.exists(backup_file):
            with _registry_backup_lock:  # X4
                _registry_session_backup[backup_key] = backup_file
            logger.info(f"[registry] 备份成功: {backup_key} -> {backup_file}")
            return backup_file
        logger.info(f"[registry] reg export失败(返回码{result.returncode}): {result.stderr.strip()}")
        # 2026-09-20 小欧 D-7: 失败显式返回 None, 不返回不可用路径(调用方据此中止)
        return None
    except FileNotFoundError:
        logger.warning("[registry] reg命令不存在,跳过备份")
        return None
    except Exception as e:
        logger.warning(f"[registry] 备份失败: {e}")
        return None


def _restore_registry_from_backup(backup_file: str) -> Optional[str]:
    """从备份恢复注册表键(reg import) — 小欧 2026-09-20 E-2修复(红case E2 驱动):
    与 _backup_registry 对称的写回滚操作, 供 registry_write/registry_delete 写失败时恢复原值,
    杜绝"写完失败/半改"留下不可逆破损。返回 None=恢复成功或无可恢复文件; 返回错误文本=恢复失败。
    """
    if not backup_file or not os.path.exists(backup_file):
        return None
    try:
        result = subprocess.run(
            ["reg", "import", backup_file],
            capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT_DEFAULT
        )
        if result.returncode == 0:
            logger.info(f"[registry] 回滚成功: {backup_file}")
            return None
        logger.warning(f"[registry] reg import 回滚失败(返回码{result.returncode}): {result.stderr.strip()}")
        return result.stderr.strip() or f"reg import 返回码 {result.returncode}"
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[registry] 回滚异常: {e}")
        return str(e)


def _build_registry_read_llm_data(exec_code: str, duration_ms: int, path: str, value_name: str, value: Any = None, value_type: str = "", err_code: str = None, detail: str = "", hint: str = "") -> dict:
    """registry_read的llm_data构建函数 — 小健 2026-06-22 — 小欧 2026-07-05 新增hint"""
    _act_params = {"path": path}
    if value_name:
        _act_params["value_name"] = value_name
    if exec_code == "error":
        return {
            "summary": f"读取注册表{path}，失败",
            "action": {"tool": "registry_read", "tool_zh": "读取注册表", "target": path, "params": _act_params},
            "status": {"exec_code": "error", "message": "读取注册表失败", "code": err_code or ERR_REG_READ_FAILED, "detail": detail, "hint": hint if hint else "请检查键路径和权限"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"读取注册表{path}，成功: {value_name}={value}（{value_type}）",
        "action": {"tool": "registry_read", "tool_zh": "读取注册表", "target": path, "params": _act_params},
        "status": {"exec_code": "success", "message": "读取注册表成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }


def registry_read(path: str, value_name: Optional[str] = None, hive: str = "HKCU", output_format: str = "auto") -> dict:
    """读取Windows注册表键值 — 小健 2026-06-22 拆分独立文件"""
    is_valid, error_msg, warning_msg = validate_registry_key(path, hive, "read")
    if not is_valid:
        llm_data = _build_registry_read_llm_data("error", 0, path, value_name or "", err_code=ERR_PARAMETER_INVALID, detail=error_msg, hint="请检查注册表路径和权限")
        return build_error(data={}, llm_data=llm_data)
    if warning_msg:
        logger.warning(f"[registry_read] {warning_msg}")
    t0 = _time_mod.perf_counter()
    key_opened = False
    try:
        full_root_key, sub_key = _parse_path(path, hive)
        hkey = ROOT_KEY_MAP.get(full_root_key)

        if hkey is None:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_registry_read_llm_data("error", duration_ms, path, value_name or "", detail=f"无效的根键: {full_root_key}", hint="请检查根键名称")
            return build_error(data={}, llm_data=llm_data)

        with winreg.OpenKey(hkey, sub_key, 0, winreg.KEY_READ) as key:
            key_opened = True
            if value_name is None:
                # 枚举所有命名值（未指定value_name时列出全部）— 小欧 2026-07-08
                values_dict = {}
                i = 0
                while True:
                    try:
                        v_name, v_value, v_type = winreg.EnumValue(key, i)
                        if output_format == "hex" and isinstance(v_value, (bytes, bytearray)):
                            v_value = v_value.hex()
                        values_dict[v_name] = v_value
                        i += 1
                    except OSError:
                        break
                if not values_dict:
                    raise FileNotFoundError(f"注册表键 {path} 没有值")
                formatted_value = values_dict
                llm_value_name = "(所有值)"
                value_type_name = f"REG_ENUM({len(values_dict)} values)"
                logger.debug(f"[registry_read] 枚举 {len(values_dict)} 个值: {full_root_key}\\{sub_key}")
            else:
                value, reg_type = winreg.QueryValueEx(key, value_name)
                value_type_name = {
                    winreg.REG_SZ: "REG_SZ", winreg.REG_DWORD: "REG_DWORD", winreg.REG_QWORD: "REG_QWORD",
                    winreg.REG_EXPAND_SZ: "REG_EXPAND_SZ", winreg.REG_MULTI_SZ: "REG_MULTI_SZ",
                    winreg.REG_BINARY: "REG_BINARY", winreg.REG_NONE: "REG_NONE",
                }.get(reg_type, f"UNKNOWN({reg_type})")
                formatted_value = value
                if output_format == "hex" and isinstance(value, (bytes, bytearray)):
                    formatted_value = value.hex()
                llm_value_name = value_name or "(默认)"
                logger.debug(f"[registry_read] 成功读取: {full_root_key}\\{sub_key}\\{value_name or '(默认)'}")

            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_registry_read_llm_data("success", duration_ms, f"{full_root_key}\\{sub_key}", llm_value_name, formatted_value, value_type_name)
            # =============================================================================
            # 数据设计：path/value_name/value/value_type 全部从 data 移除
            # summary 已含全部信息: "读取 HKCU\Software\MyApp\Version = 1.0（REG_SZ）"
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
        if key_opened:
            # OpenKey成功 → 键存在，FileNotFoundError来自QueryValueEx或显式raise
            if value_name:
                detail = f"值不存在: {path}\\{value_name}"
                hint = "请检查值名称是否正确"
            else:
                detail = f"注册表键 {path} 没有值"
                hint = "该键下没有可读取的值"
        else:
            detail = f"注册表键不存在: {path}"
            hint = "请检查键路径是否正确"
        llm_data = _build_registry_read_llm_data("error", duration_ms, path, value_name or "", detail=detail, hint=hint)
        return build_error(data={}, llm_data=llm_data)
    except PermissionError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_read_llm_data("error", duration_ms, path, value_name or "", detail=f"权限不足: {path}", hint="请以管理员身份运行")
        return build_error(data={}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_registry_read_llm_data("error", duration_ms, path, value_name or "", detail=str(e), hint="读取注册表异常,请检查系统状态")
        return build_error(data={}, llm_data=llm_data)


__all__ = ["registry_read", "ROOT_KEY_MAP", "_registry_session_backup", "_parse_path", "_backup_registry", "_validate_root_key"]
