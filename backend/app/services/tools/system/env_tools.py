# -*- coding: utf-8 -*-
"""
ENV 工具函数模块 - 环境变量工具

【创建时间】2026-04-29 小沈
【规范】按新规范使用 Pydantic 模型注册

【重要】新函数增加规范 - 小沈 2026-05-04
新增函数时必须同步修改以下3个文件：
1. *_tools.py: 函数实现（必须有详细注释）
2. *_schema.py: Pydantic 模型（输入参数定义）
3. *_register.py: 显式注册（description + examples + input_model）

包含：
- get_env: 获取/列出环境变量（action="get"|"list"）
- set_env: 设置/删除环境变量（action="set"|"delete"）

返回格式：统一 {code, data, message} 格式

Author: 小沈 - 2026-04-29
"""

import os
import subprocess
import sys
from typing import Optional, Dict, Any, List, Tuple

from app.utils.logger import logger
from app.services.tools.tool_result_utils import build_next_actions  # 小沈 2026-05-19
from app.services.tools._response import build_success, build_error


def _list_env_vars(prefix: Optional[str] = None) -> dict:
    """列出环境变量（原 list_env 逻辑，独立方法）

    小沈 2026-05-25 重构拆分
    """
    try:
        raw = {n: v for n, v in os.environ.items()
               if prefix is None or n.upper().startswith(prefix.upper())}
        MAX_VAL = 1000
        env_list, truncated_count = [], 0
        for k, v in sorted(raw.items()):
            val = str(v)
            if len(val) > MAX_VAL:
                val = val[:MAX_VAL] + f"...({len(val)}字符)"
                truncated_count += 1
            env_list.append({"name": k, "value": val})
        _llm = {"总数": len(env_list), "截断数": truncated_count}
        return build_success(
            {"count": len(env_list), "variables": env_list, "prefix": prefix},
            f"共找到 {len(env_list)} 个环境变量",
            llm_data=_llm,
            next_actions=build_next_actions([("set_env", "设置环境变量", "需要修改环境变量时")]))
    except Exception as e:
        logger.error(f"[list_env] 列出环境变量失败: {e}")
        return build_error("ERR_SYS_ENV_LIST", f"列出环境变量失败: {str(e)}")


def _get_env_by_scope(name: str, scope: str) -> Optional[str]:
    """按 scope 读取环境变量值，注册表失败回退 os.environ

    小沈 2026-05-25 重构拆分（修复 26.2-1🟡 scope 合法性校验）
    """
    if scope == "process":
        return os.environ.get(name)
    if scope not in ("user", "system"):      # 小沈 2026-05-25: 校验scope合法性
        return os.environ.get(name)          # 未知 scope 回退进程环境变量
    try:
        import winreg
        hive = winreg.HKEY_CURRENT_USER if scope == "user" else winreg.HKEY_LOCAL_MACHINE
        subkey = r"Environment" if scope == "user" else r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
        with winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ) as key:
            try:
                val, _ = winreg.QueryValueEx(key, name)
                return val
            except FileNotFoundError:
                return None
    except Exception:
        return os.environ.get(name)


def get_env(name: Optional[str] = None, scope: str = "process",
            expand_vars: bool = True, action: str = "get",
            prefix: Optional[str] = None,
            ) -> dict:
    """
    获取或列出环境变量 - 小沈 2026-05-03 | 2026-05-18 合并list_env
    【2026-05-25 小沈重构】拆分 list 分支为 _list_env_vars，scope 分派为 _get_env_by_scope

    Args:
        name: 环境变量名称（action="get"时必填）
        scope: 作用域 (process/user/system)
        expand_vars: 是否展开嵌套变量
        action: 操作类型 ("get"|"list")，默认"get"
        prefix: 环境变量名前缀过滤（仅action="list"有效）

    Returns:
        {code, data, message}
    """
    if action not in ("get", "list"):
        return build_error("ERR_SYS_ENV_INVALID_ACTION", f"无效的action: {action}，支持: get/list")
    if action == "list":
        return _list_env_vars(prefix)

    if not name:
        return build_error("ERR_SYS_ENV_INVALID_NAME", "action='get'时name参数必填")

    try:
        value = _get_env_by_scope(name, scope)
        if value is not None and expand_vars and isinstance(value, str):
            try:
                value = os.path.expandvars(value)
            except Exception:
                pass

        return build_success(
            {"name": name, "value": value, "exists": value is not None,
             "scope": scope, "expanded": expand_vars},
            f"环境变量 {name} ({'存在' if value is not None else '不存在'})",
            next_actions=build_next_actions([("set_env", "设置环境变量", "需要修改环境变量时")]))

    except Exception as e:
        logger.error(f"[get_env] 获取环境变量失败: {e}")
        return build_error("ERR_SYS_ENV_GET", f"获取环境变量失败: {str(e)}")


def _env_success(name: str, value: Any, scope: str, deleted: bool = False,
                  append_mode: bool = False, msg: str = "") -> dict:
    """统一构建 env 操作的成功响应 — 小沈 2026-05-25"""
    return build_success(
        {"name": name, "value": value, "scope": scope, "deleted": deleted, "append_mode": append_mode},
        msg or f"已{'删除' if deleted else '设置'}: {name}",
        next_actions=build_next_actions([("get_env", "验证变量已设置", "需要确认设置结果时")])
    )


def _delete_env(name: str, scope: str) -> dict:
    """删除环境变量，3种scope。统一构建success — 小沈 2026-05-25"""
    if scope == "process":
        exists = name in os.environ
        if exists:
            del os.environ[name]
        return _env_success(name, None, scope, deleted=exists, msg=f"已{'删除' if exists else '不存在'}: {name}")
    if scope == "user":
        import winreg
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_SET)
            winreg.DeleteValue(key, name)
            winreg.CloseKey(key)
            os.environ.pop(name, None)
            return _env_success(name, None, scope, deleted=True, msg=f"已删除(用户): {name}")
        except FileNotFoundError:
            winreg.CloseKey(key)
            return _env_success(name, None, scope, deleted=False, msg=f"不存在: {name}")
    exists = name in os.environ
    if exists:
        del os.environ[name]
    return _env_success(name, None, "system→process(降级)", deleted=exists,
                         msg=f"已{'删除' if exists else '不存在'}(降级为process): {name}")


def _read_env(name: str, scope: str = "process") -> Optional[str]:
    """读取环境变量值：process从os.environ，user/system从注册表(fallback os.environ) — 小沈 2026-05-25"""
    if scope == "process":
        return os.environ.get(name)
    try:
        import winreg
        hive = winreg.HKEY_CURRENT_USER if scope == "user" else winreg.HKEY_LOCAL_MACHINE
        path = r"Environment" if scope == "user" else r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
        key = winreg.OpenKey(hive, path, 0, winreg.KEY_READ)
        try:
            val, _ = winreg.QueryValueEx(key, name)
            return val
        except FileNotFoundError:
            return None
        finally:
            winreg.CloseKey(key)
    except Exception:
        return os.environ.get(name)


def _set_scope(name: str, value: str, scope: str) -> Tuple[str, str]:
    """写入指定scope，返回(实际_scope, 消息) — 小沈 2026-05-25"""
    if scope == "process":
        os.environ[name] = value
        return scope, f"已设置(进程级): {name}"
    if scope == "user":
        result = subprocess.run(["setx", name, value], capture_output=True, text=True, shell=True)
        if result.returncode == 0:
            os.environ[name] = value
            return "user", f"已设置(用户级): {name}，需重启终端生效"
        logger.warning(f"[set_env] setx失败: {result.stderr}")
    os.environ[name] = value
    return "process", "系统级需管理员权限/设置失败，已降级为进程级: {name}"


def set_env(name: str, value: Optional[str] = None, scope: str = "process",
             append_mode: bool = False, action: str = "set") -> dict:
    """设置/删除环境变量 — 小沈 2026-05-25 重构

    - action="delete": 删除变量
    - scope="process": 仅当前进程生效
    - scope="user": 需要写入用户环境
    - scope="system": 需要管理员权限
    - append_mode=True: 追加而非覆盖

    Args:
        name: 环境变量名称
        value: 环境变量值（action="set"时必填）
        scope: 作用域 (process/user/system)
        append_mode: 追加模式
        action: 操作类型

    Returns:
        {code, data, message}
    """
    if not name or not name.strip():
        return build_error("ERR_SYS_ENV_INVALID_NAME", "环境变量名称不能为空")
    if action not in ("set", "delete"):
        return build_error("ERR_SYS_ENV_INVALID_ACTION", f"无效的action: {action}")
    if action == "delete":
        return _delete_env(name, scope)
    if value is None:
        return build_error("ERR_SYS_ENV_INVALID_VALUE", "环境变量值不能为None")
    if scope not in ("process", "user", "system"):
        return build_error("ERR_SYS_ENV_INVALID_SCOPE", f"无效的作用域: {scope}")

    existing = _read_env(name, scope)
    if existing == value:
        return _env_success(name, value, scope, msg=f"值相同(幂等): {name}")

    separator = ";" if sys.platform == "win32" else ":"
    if append_mode:
        existing_val = os.environ.get(name, "")
        if existing_val:
            parts = [p.strip() for p in existing_val.split(separator) if p.strip()]
            if value.strip() not in parts:
                parts.append(value.strip())
            effective = separator.join(parts)
        else:
            effective = value
    else:
        effective = value

    actual_scope, msg = _set_scope(name, effective, scope)
    return _env_success(name, effective, actual_scope, append_mode=append_mode, msg=msg)


