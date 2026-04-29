# -*- coding: utf-8 -*-
"""
ENV 工具函数模块 - 环境变量工具

【创建时间】2026-04-29 小沈
【规范】按新规范使用 Pydantic 模型注册

包含：
- get_env: 获取环境变量
- set_env: 设置环境变量
- list_env: 列出环境变量

返回格式：统一 {code, data, message} 格式

Author: 小沈 - 2026-04-29
"""

import os
from typing import Optional, Dict, Any, List

from app.utils.logger import logger


def get_env(name: str, default: Optional[str] = None) -> dict:
    """
    获取环境变量

    Args:
        name: 环境变量名称
        default: 默认值（可选）

    Returns:
        {code, data, message}
    """
    try:
        value = os.environ.get(name)
        if value is not None:
            return {
                "code": "SUCCESS",
                "data": {"name": name, "value": value, "exists": True},
                "message": f"成功获取环境变量 {name}"
            }
        else:
            return {
                "code": "SUCCESS",
                "data": {"name": name, "value": default, "exists": False},
                "message": f"环境变量 {name} 不存在，返回默认值"
            }
    except Exception as e:
        logger.error(f"[get_env] 获取环境变量失败: {e}")
        return {
            "code": "ERR_ENV_GET",
            "data": None,
            "message": f"获取环境变量失败: {str(e)}"
        }


def set_env(name: str, value: str, scope: str = "process") -> dict:
    """
    设置环境变量

    注意：
    - scope="process": 仅当前进程生效（推荐）
    - scope="user": 需要写入用户环境（需要权限，可能需要重启shell生效）
    - scope="system": 需要管理员权限（写入系统环境，不推荐）

    Args:
        name: 环境变量名称
        value: 环境变量值
        scope: 作用域 (process/user/system)

    Returns:
        {code, data, message}
    """
    try:
        # 验证变量名
        if not name or not name.strip():
            return {
                "code": "ERR_ENV_INVALID_NAME",
                "data": None,
                "message": "环境变量名称不能为空"
            }

        # 验证变量值
        if value is None:
            return {
                "code": "ERR_ENV_INVALID_VALUE",
                "data": None,
                "message": "环境变量值不能为None"
            }

        if scope == "process":
            # 仅当前进程
            os.environ[name] = value
            return {
                "code": "SUCCESS",
                "data": {"name": name, "value": value, "scope": scope},
                "message": f"已设置环境变量（当前进程）: {name}={value}"
            }

        elif scope == "user":
            # 需要使用setx写入用户环境
            import subprocess
            result = subprocess.run(
                ["setx", name, value],
                capture_output=True,
                text=True,
                shell=True
            )
            if result.returncode == 0:
                return {
                    "code": "SUCCESS",
                    "data": {"name": name, "value": value, "scope": scope},
                    "message": f"已设置环境变量（用户级）: {name}={value}，需要重启终端生效"
                }
            else:
                return {
                    "code": "ERR_ENV_SET_USER",
                    "data": None,
                    "message": f"设置用户环境变量失败: {result.stderr}"
                }

        elif scope == "system":
            # 需要管理员权限
            return {
                "code": "ERR_ENV_NO_PERMISSION",
                "data": None,
                "message": "设置系统级环境变量需要管理员权限，建议使用 user 作用域或在系统属性中手动设置"
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
                except WindowsError:
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

        # 转换为列表
        env_list = [{"name": k, "value": str(v)} for k, v in sorted(env_vars.items())]

        return {
            "code": "SUCCESS",
            "data": {
                "count": len(env_list),
                "variables": env_list,
                "prefix": prefix,
                "include_system": include_system,
            },
            "message": f"共找到 {len(env_list)} 个环境变量"
        }

    except Exception as e:
        logger.error(f"[list_env] 列出环境变量失败: {e}")
        return {
            "code": "ERR_ENV_LIST",
            "data": None,
            "message": f"列出环境变量失败: {str(e)}"
        }