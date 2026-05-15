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
- get_env: 获取环境变量
- set_env: 设置环境变量
- list_env: 列出环境变量

返回格式：统一 {code, data, message} 格式

Author: 小沈 - 2026-04-29
"""

import os
import sys
from typing import Optional, Dict, Any, List

from app.utils.logger import logger


def get_env(name: str, default: Optional[str] = None, scope: str = "process", expand_vars: bool = True) -> dict:
    """
    获取环境变量 - 小沈 2026-05-03 增加scope+expand_vars支持

    Args:
        name: 环境变量名称
        default: 默认值（可选）
        scope: 作用域 (process/user/system)
        expand_vars: 是否展开嵌套变量

    Returns:
        {code, data, message}
    """
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
            original_value = value
            if expand_vars and isinstance(value, str):
                try:
                    expanded = os.path.expandvars(value)
                    value = expanded
                except Exception:
                    pass
            return {
                "code": "SUCCESS",
                "data": {"name": name, "value": value, "exists": True, "scope": scope, "expanded": expand_vars},
                "message": f"成功获取环境变量 {name}（作用域: {scope}）"
            }
        else:
            return {
                "code": "SUCCESS",
                "data": {"name": name, "value": default, "exists": False, "scope": scope, "expanded": expand_vars},
                "message": f"环境变量 {name} 不存在（作用域: {scope}），返回默认值"
            }
    except Exception as e:
        logger.error(f"[get_env] 获取环境变量失败: {e}")
        return {
            "code": "ERR_ENV_GET",
            "data": None,
            "message": f"获取环境变量失败: {str(e)}"
        }


def set_env(name: str, value: str, scope: str = "process", append_mode: bool = False) -> dict:
    """
    设置环境变量 - 小沈 2026-05-03 增加append_mode支持

    注意：
    - scope="process": 仅当前进程生效（推荐）
    - scope="user": 需要写入用户环境（需要权限，可能需要重启shell生效）
    - scope="system": 需要管理员权限（写入系统环境，不推荐）
    - append_mode=True: 追加而非覆盖，自动去重和选择分隔符

    Args:
        name: 环境变量名称
        value: 环境变量值
        scope: 作用域 (process/user/system)
        append_mode: 追加模式（默认False覆盖）

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

        if value is None:
            return {
                "code": "ERR_ENV_INVALID_VALUE",
                "data": None,
                "message": "环境变量值不能为None"
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
                "message": f"已设置环境变量（当前进程）: {name}={effective_value}"
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
                    "message": f"已设置环境变量（用户级）: {name}={effective_value}，需要重启终端生效"
                }
            else:
                logger.warning(f"[set_env] setx失败，降级为process: {result.stderr}")
                os.environ[name] = effective_value
                return {
                    "code": "SUCCESS",
                    "data": {"name": name, "value": effective_value, "scope": "process", "append_mode": append_mode},
                    "message": f"设置用户环境变量失败，已降级为进程级: {name}={effective_value}"
                }

        elif scope == "system":
            logger.warning("[set_env] system scope需管理员权限，降级为process")
            os.environ[name] = effective_value
            return {
                "code": "SUCCESS",
                "data": {"name": name, "value": effective_value, "scope": "process", "append_mode": append_mode},
                "message": f"系统级需管理员权限，已降级为进程级: {name}={effective_value}"
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


def list_env(prefix: Optional[str] = None, include_system: bool = False) -> dict:
    """
    列出环境变量

    Args:
        prefix: 环境变量名前缀过滤（可选）
        include_system: 是否包含系统级环境变量

    Returns:
        {code, data, message}
    """
    try:
        env_vars = {}

        # 收集环境变量
        if include_system:
            # 包含系统级环境变量（需要特殊处理）
            try:
                import winreg
                system_vars = []
                # 读取系统环境变量
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment", 0, winreg.KEY_READ)
                try:
                    i = 0
                    while True:
                        name, value, _ = winreg.EnumValue(key, i)
                        system_vars.append((name, value))
                        i += 1
                except OSError:
                    pass
                finally:
                    winreg.CloseKey(key)

                for name, value in system_vars:
                    if prefix is None or name.upper().startswith(prefix.upper()):
                        env_vars[name] = value
            except Exception as e:
                logger.warning(f"[list_env] 读取系统环境变量失败: {e}")

        # 添加当前进程环境变量
        for name, value in os.environ.items():
            if prefix is None or name.upper().startswith(prefix.upper()):
                env_vars[name] = value

        # 转换为列表，截断超长变量值 小沈-2026-05-15
        MAX_VAL = 1000
        env_list = []
        truncated_count = 0
        for k, v in sorted(env_vars.items()):
            val = str(v)
            if len(val) > MAX_VAL:
                val = val[:MAX_VAL] + f"...({len(val)}字符)"
                truncated_count += 1
            env_list.append({"name": k, "value": val})

        # 【优化 小沈 2026-05-15】llm_data精简摘要
        _llm = {
            "总数": len(env_list),
            "截断数": truncated_count,
            "变量列表": [{"name": e["name"], "value": e["value"][:200] + ("..." if len(e["value"]) > 200 else "")} for e in env_list],
        }

        return {
            "code": "SUCCESS",
            "data": {
                "count": len(env_list),
                "variables": env_list,
                "prefix": prefix,
                "include_system": include_system,
            },
            "message": f"共找到 {len(env_list)} 个环境变量",
            "llm_data": _llm
        }

    except Exception as e:
        logger.error(f"[list_env] 列出环境变量失败: {e}")
        return {
            "code": "ERR_ENV_LIST",
            "data": None,
            "message": f"列出环境变量失败: {str(e)}"
        }

def delete_env(name: str, scope: str = "process") -> dict:
    """删除环境变量 - 小沈 2026-05-04"""
    try:
        if not name or not name.strip():
            return {"code": "ERR_ENV_INVALID_NAME", "data": None, "message": "名称为空"}

        if scope == "process":
            if name in os.environ:
                del os.environ[name]
                return {"code": "SUCCESS", "data": {"name": name, "deleted": True}, "message": f"已删除: {name}"}
            return {"code": "SUCCESS", "data": {"name": name, "deleted": False}, "message": f"不存在: {name}"}

        import winreg
        if scope == "user":
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_SET)
            try:
                winreg.DeleteValue(key, name)
                if name in os.environ:
                    del os.environ[name]
                return {"code": "SUCCESS", "data": {"name": name, "scope": "user", "deleted": True}, "message": f"已删除: {name}"}
            except FileNotFoundError:
                return {"code": "SUCCESS", "data": {"name": name, "deleted": False}, "message": f"不存在: {name}"}
            finally:
                winreg.CloseKey(key)
        else:
            return {"code": "ERR_ENV_PERMISSION", "data": None, "message": "需要管理员权限"}
    except Exception as e:
        return {"code": "ERR_ENV_DELETE", "data": None, "message": str(e)}


def exists_env(name: str, scope: str = "process") -> dict:
    """检查环境变量是否存在 - 小沈 2026-05-04"""
    try:
        if not name or not name.strip():
            return {"code": "ERR_ENV_INVALID_NAME", "data": None, "message": "名称为空"}

        if scope == "process":
            exists = name in os.environ
            value = os.environ.get(name) if exists else None
            return {"code": "SUCCESS", "data": {"name": name, "exists": exists, "value": value}, "message": f"{'存在' if exists else '不存在'}"}

        import winreg
        hive = winreg.HKEY_CURRENT_USER if scope == "user" else winreg.HKEY_LOCAL_MACHINE
        path = r"Environment" if scope == "user" else r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
        key = winreg.OpenKey(hive, path, 0, winreg.KEY_READ)
        try:
            value, _ = winreg.QueryValueEx(key, name)
            return {"code": "SUCCESS", "data": {"name": name, "exists": True, "value": value}, "message": "存在"}
        except FileNotFoundError:
            return {"code": "SUCCESS", "data": {"name": name, "exists": False, "value": None}, "message": "不存在"}
        finally:
            winreg.CloseKey(key)
    except Exception as e:
        return {"code": "ERR_ENV_EXISTS", "data": None, "message": str(e)}
