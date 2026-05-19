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
import sys
from typing import Optional, Dict, Any, List

from app.utils.logger import logger
from app.services.tools.tool_result_utils import build_next_actions  # 小沈 2026-05-19


def get_env(name: Optional[str] = None, scope: str = "process",
            expand_vars: bool = True, action: str = "get",
            prefix: Optional[str] = None,
            ) -> dict:
    """
    获取或列出环境变量 - 小沈 2026-05-03 | 2026-05-18 合并list_env
    【2026-05-18 小沈】P2: 合并list_env（action="list"），减少LLM工具数

    Args:
        name: 环境变量名称（action="get"时必填）
        scope: 作用域 (process/user/system)
        expand_vars: 是否展开嵌套变量
        action: 操作类型 ("get"|"list")，默认"get"
        prefix: 环境变量名前缀过滤（仅action="list"有效）

    Returns:
        {code, data, message}
    """
    # 【2026-05-18 小沈】action="list"分支：原list_env逻辑
    # 小健 2026-05-19: action值校验
    if action not in ("get", "list"):
        return {"code": "ERR_ENV_INVALID_ACTION", "data": None, "message": f"无效的action: {action}，支持: get/list"}
    if action == "list":
        try:
            env_vars = {}
            # include_system 已从Schema移除，默认False，不读取注册表系统级变量
            for n, v in os.environ.items():
                if prefix is None or n.upper().startswith(prefix.upper()):
                    env_vars[n] = v
            MAX_VAL = 1000
            env_list = []
            truncated_count = 0
            for k, v in sorted(env_vars.items()):
                val = str(v)
                if len(val) > MAX_VAL:
                    val = val[:MAX_VAL] + f"...({len(val)}字符)"
                    truncated_count += 1
                env_list.append({"name": k, "value": val})
            _llm = {
                "总数": len(env_list),
                "截断数": truncated_count,
                "变量列表": [{"name": e["name"], "value": e["value"][:200] + ("..." if len(e["value"]) > 200 else "")} for e in env_list],
            }
            return {
                "code": "SUCCESS",
                "data": {"count": len(env_list), "variables": env_list, "prefix": prefix},
                "message": f"共找到 {len(env_list)} 个环境变量",
                "llm_data": _llm,
                "next_actions": build_next_actions([("set_env", "设置环境变量", "需要修改环境变量时")])
            }
        except Exception as e:
            logger.error(f"[get_env] 列出环境变量失败: {e}")
            return {"code": "ERR_ENV_LIST", "data": None, "message": f"列出环境变量失败: {str(e)}"}

    # action="get"分支：原get_env逻辑
    if action == "get" and not name:
        return {"code": "ERR_ENV_INVALID_NAME", "data": None, "message": "action='get'时name参数必填"}
    
    try:
        value = None

        if scope == "process":
            value = os.environ.get(name)
        elif scope in ("user", "system"):
            try:
                import winreg
                hive = winreg.HKEY_CURRENT_USER if scope == "user" else winreg.HKEY_LOCAL_MACHINE
                key = winreg.OpenKey(
                    hive,
                    r"Environment" if scope == "user" else r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
                    0, winreg.KEY_READ
                )
                try:
                    value, _ = winreg.QueryValueEx(key, name)
                except FileNotFoundError:
                    value = None
                finally:
                    winreg.CloseKey(key)
            except Exception as e:
                logger.warning(f"[get_env] 读取{scope}级环境变量失败: {e}")
                value = os.environ.get(name)

        if value is not None:
            if expand_vars and isinstance(value, str):
                try:
                    expanded = os.path.expandvars(value)
                    value = expanded
                except Exception:
                    pass
            return {
                "code": "SUCCESS",
                "data": {"name": name, "value": value, "exists": True, "scope": scope, "expanded": expand_vars},
                "message": f"成功获取环境变量 {name}（作用域: {scope}）",
                "next_actions": build_next_actions([("set_env", "设置环境变量", "需要修改环境变量时")])
            }
        else:
            return {
                "code": "SUCCESS",
                "data": {"name": name, "value": None, "exists": False, "scope": scope, "expanded": expand_vars},
                "message": f"环境变量 {name} 不存在（作用域: {scope}）",
                "next_actions": build_next_actions([("set_env", "设置环境变量", "需要修改环境变量时")])
            }
    except Exception as e:
        logger.error(f"[get_env] 获取环境变量失败: {e}")
        return {
            "code": "ERR_ENV_GET",
            "data": None,
            "message": f"获取环境变量失败: {str(e)}"
        }


def set_env(name: str, value: Optional[str] = None, scope: str = "process",
            append_mode: bool = False, action: str = "set",
            ) -> dict:
    """
    设置或删除环境变量 - 小沈 2026-05-03 增加append_mode支持
    【2026-05-17 小沈】P1-5: 合并delete_env（action="delete"），增加exist_ok幂等

    注意：
    - action="set": 设置变量（默认行为）
    - action="delete": 删除变量（原delete_env逻辑）
    - scope="process": 仅当前进程生效（推荐）
    - scope="user": 需要写入用户环境（需要权限，可能需要重启shell生效）
    - scope="system": 需要管理员权限（写入系统环境，不推荐）
    - append_mode=True: 追加而非覆盖，自动去重和选择分隔符

    Args:
        name: 环境变量名称
        value: 环境变量值（action="set"时必填，action="delete"时忽略）
        scope: 作用域 (process/user/system)
        append_mode: 追加模式（默认False覆盖）
        action: 操作类型 ("set"|"delete")，默认"set"

    Returns:
        {code, data, message}
    """
    try:
        if not name or not name.strip():
            return {
                "code": "ERR_ENV_INVALID_NAME",
                "data": None,
                "message": "环境变量名称不能为空"
            }

        # 【2026-05-17 小沈】action="delete"分支：原delete_env逻辑
        # 小健 2026-05-19: action值校验
        if action not in ("set", "delete"):
            return {"code": "ERR_ENV_INVALID_ACTION", "data": None, "message": f"无效的action: {action}，支持: set/delete"}
        if action == "delete":
            if scope == "process":
                if name in os.environ:
                    del os.environ[name]
                    return {"code": "SUCCESS", "data": {"name": name, "deleted": True, "scope": scope},
                            "message": f"已删除: {name}",
                            "next_actions": build_next_actions([("get_env", "验证变量已设置", "需要确认设置结果时")])}
                return {"code": "SUCCESS", "data": {"name": name, "deleted": False, "scope": scope},
                        "message": f"不存在: {name}",
                        "next_actions": build_next_actions([("get_env", "验证变量已设置", "需要确认设置结果时")])}

            import winreg
            if scope == "user":
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_SET)
                try:
                    winreg.DeleteValue(key, name)
                    if name in os.environ:
                        del os.environ[name]
                    return {"code": "SUCCESS", "data": {"name": name, "scope": "user", "deleted": True},
                            "message": f"已删除: {name}",
                            "next_actions": build_next_actions([("get_env", "验证变量已设置", "需要确认设置结果时")])}
                except FileNotFoundError:
                    return {"code": "SUCCESS", "data": {"name": name, "deleted": False, "scope": scope},
                            "message": f"不存在: {name}",
                            "next_actions": build_next_actions([("get_env", "验证变量已设置", "需要确认设置结果时")])}
                finally:
                    winreg.CloseKey(key)
            else:
                # 【2026-05-18 小沈】system scope delete降级为process（与set行为一致）
                if name in os.environ:
                    del os.environ[name]
                    return {"code": "SUCCESS", "data": {"name": name, "deleted": True, "scope": "system→process(降级)"},
                            "message": f"已删除(降级为process): {name}",
                            "next_actions": build_next_actions([("get_env", "验证变量已设置", "需要确认设置结果时")])}
                return {"code": "SUCCESS", "data": {"name": name, "deleted": False, "scope": "system→process(降级)"},
                        "message": f"不存在(降级为process): {name}",
                        "next_actions": build_next_actions([("get_env", "验证变量已设置", "需要确认设置结果时")])}

        # action="set"分支：原set_env逻辑
        if value is None:
            return {
                "code": "ERR_ENV_INVALID_VALUE",
                "data": None,
                "message": "环境变量值不能为None（action='set'时value必填）"
            }

        # 【2026-05-17 小沈】exist_ok幂等增强（硬编码为True，已从Schema移除）
        # 小健 2026-05-19: scope=user/system时需从注册表读取当前值,而非os.environ
        if value is not None:
            if scope == "process":
                existing = os.environ.get(name)
            else:
                existing = None
                try:
                    import winreg
                    hive = winreg.HKEY_CURRENT_USER if scope == "user" else winreg.HKEY_LOCAL_MACHINE
                    reg_path = r"Environment" if scope == "user" else r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
                    key = winreg.OpenKey(hive, reg_path, 0, winreg.KEY_READ)
                    try:
                        existing, _ = winreg.QueryValueEx(key, name)
                    except FileNotFoundError:
                        existing = None
                    finally:
                        winreg.CloseKey(key)
                except Exception:
                    existing = os.environ.get(name)
            if existing == value:
                return {
                    "code": "SUCCESS",
                    "data": {"name": name, "value": value, "scope": scope, "append_mode": append_mode},
                    "message": f"环境变量已存在且值相同: {name}={value[:50]}{'...' if len(value) > 50 else ''}",
                    "next_actions": build_next_actions([("get_env", "验证变量已设置", "需要确认设置结果时")])
                }

        if append_mode:
            existing = os.environ.get(name, "")
            separator = ";" if sys.platform == "win32" else ":"
            if existing:
                parts = [p.strip() for p in existing.split(separator) if p.strip()]
                new_value_stripped = value.strip()
                if new_value_stripped not in parts:
                    parts.append(new_value_stripped)
                effective_value = separator.join(parts)
            else:
                effective_value = value
        else:
            effective_value = value

        if scope == "process":
            os.environ[name] = effective_value
            return {
                "code": "SUCCESS",
                "data": {"name": name, "value": effective_value, "scope": scope, "append_mode": append_mode},
                "message": f"已设置环境变量（当前进程）: {name}={effective_value}",
                "next_actions": build_next_actions([("get_env", "验证变量已设置", "需要确认设置结果时")])
            }

        elif scope == "user":
            import subprocess
            result = subprocess.run(
                ["setx", name, effective_value],
                capture_output=True,
                text=True,
                shell=True
            )
            if result.returncode == 0:
                os.environ[name] = effective_value
                return {
                    "code": "SUCCESS",
                    "data": {"name": name, "value": effective_value, "scope": scope, "append_mode": append_mode},
                    "message": f"已设置环境变量（用户级）: {name}={effective_value}，需要重启终端生效",
                    "next_actions": build_next_actions([("get_env", "验证变量已设置", "需要确认设置结果时")])
                }
            else:
                logger.warning(f"[set_env] setx失败，降级为process: {result.stderr}")
                os.environ[name] = effective_value
                return {
                    "code": "SUCCESS",
                    "data": {"name": name, "value": effective_value, "scope": "process", "append_mode": append_mode},
                    "message": f"设置用户环境变量失败，已降级为进程级: {name}={effective_value}",
                    "next_actions": build_next_actions([("get_env", "验证变量已设置", "需要确认设置结果时")])
                }

        elif scope == "system":
            logger.warning("[set_env] system scope需管理员权限，降级为process")
            os.environ[name] = effective_value
            return {
                "code": "SUCCESS",
                "data": {"name": name, "value": effective_value, "scope": "process", "append_mode": append_mode},
                "message": f"系统级需管理员权限，已降级为进程级: {name}={effective_value}",
                "next_actions": build_next_actions([("get_env", "验证变量已设置", "需要确认设置结果时")])
            }

        else:
            return {
                "code": "ERR_ENV_INVALID_SCOPE",
                "data": None,
                "message": f"无效的作用域: {scope}，必须是 process/user/system 之一"
            }

    except Exception as e:
        logger.error(f"[set_env] 设置环境变量失败: {e}")
        return {
            "code": "ERR_ENV_SET",
            "data": None,
            "message": f"设置环境变量失败: {str(e)}"
        }


