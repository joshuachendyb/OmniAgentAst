# -*- coding: utf-8 -*-
"""
REGISTRY 工具函数模块 - Windows注册表操作工具

【创建时间】2026-05-02 小沈
【规范】按新规范使用 Pydantic 模型注册

包含：
- reg_read: 读取注册表键值
- reg_write: 写入注册表键值
- reg_delete: 删除注册表键值

返回格式：统一 {code, data, message} 格式

Author: 小沈 - 2026-05-02
"""

import winreg
import struct
from typing import Optional, Dict, Any

from app.utils.logger import logger


ROOT_KEY_MAP = {
    "HKEY_CLASSES_ROOT": winreg.HKEY_CLASSES_ROOT,
    "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
    "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
    "HKEY_USERS": winreg.HKEY_USERS,
    "HKEY_CURRENT_CONFIG": winreg.HKEY_CURRENT_CONFIG,
}


def reg_read(root_key: str, sub_key: str, value_name: Optional[str] = None) -> dict:
    """
    读取注册表键值

    Args:
        root_key: 根键名称（如 HKEY_LOCAL_MACHINE）
        sub_key: 子键路径
        value_name: 值名称（None表示默认值）

    Returns:
        {code, data, message}
    """
    try:
        hkey = ROOT_KEY_MAP.get(root_key)
        if hkey is None:
            return {"code": 400, "data": None, "message": f"无效的根键: {root_key}"}

        with winreg.OpenKey(hkey, sub_key, 0, winreg.KEY_READ) as key:
            value, value_type = winreg.QueryValueEx(key, value_name)
            
            value_type_name = {
                winreg.REG_SZ: "REG_SZ",
                winreg.REG_DWORD: "REG_DWORD",
                winreg.REG_QWORD: "REG_QWORD",
                winreg.REG_EXPAND_SZ: "REG_EXPAND_SZ",
                winreg.REG_MULTI_SZ: "REG_MULTI_SZ",
                winreg.REG_BINARY: "REG_BINARY",
                winreg.REG_NONE: "REG_NONE",
            }.get(value_type, f"UNKNOWN({value_type})")

            result_data = {
                "root_key": root_key,
                "sub_key": sub_key,
                "value_name": value_name or "(默认)",
                "value": value,
                "value_type": value_type_name,
            }

            logger.info(f"[reg_read] 成功读取: {root_key}\\{sub_key}\\{value_name or '(默认)'}")
            return {"code": 200, "data": result_data, "message": "读取成功"}

    except FileNotFoundError:
        error_msg = f"注册表键或值不存在: {root_key}\\{sub_key}\\{value_name or '(默认)'}"
        logger.warning(f"[reg_read] {error_msg}")
        return {"code": 404, "data": None, "message": error_msg}
    except PermissionError:
        error_msg = f"权限不足，无法访问: {root_key}\\{sub_key}"
        logger.error(f"[reg_read] {error_msg}")
        return {"code": 403, "data": None, "message": error_msg}
    except Exception as e:
        error_msg = f"读取注册表失败: {str(e)}"
        logger.error(f"[reg_read] {error_msg}")
        return {"code": 500, "data": None, "message": error_msg}


def reg_write(root_key: str, sub_key: str, value_data: str, value_name: Optional[str] = None, value_type: str = "REG_SZ") -> dict:
    """
    写入注册表键值

    Args:
        root_key: 根键名称
        sub_key: 子键路径
        value_data: 要写入的数据
        value_name: 值名称（None表示默认值）
        value_type: 值类型（REG_SZ/REG_DWORD/REG_QWORD/REG_EXPAND_SZ/REG_MULTI_SZ/REG_BINARY）

    Returns:
        {code, data, message}
    """
    try:
        hkey = ROOT_KEY_MAP.get(root_key)
        if hkey is None:
            return {"code": 400, "data": None, "message": f"无效的根键: {root_key}"}

        type_map = {
            "REG_SZ": winreg.REG_SZ,
            "REG_DWORD": winreg.REG_DWORD,
            "REG_QWORD": winreg.REG_QWORD,
            "REG_EXPAND_SZ": winreg.REG_EXPAND_SZ,
            "REG_MULTI_SZ": winreg.REG_MULTI_SZ,
            "REG_BINARY": winreg.REG_BINARY,
        }
        
        reg_type = type_map.get(value_type)
        if reg_type is None:
            return {"code": 400, "data": None, "message": f"不支持的值类型: {value_type}"}

        converted_value = value_data
        if value_type == "REG_DWORD":
            converted_value = int(value_data)
        elif value_type == "REG_QWORD":
            converted_value = int(value_data)
        elif value_type == "REG_BINARY":
            if isinstance(value_data, str):
                converted_value = bytes.fromhex(value_data.replace(" ", ""))
        elif value_type == "REG_MULTI_SZ":
            if isinstance(value_data, str):
                converted_value = value_data.split(";")

        with winreg.CreateKey(hkey, sub_key) as key:
            winreg.SetValueEx(key, value_name, 0, reg_type, converted_value)

        result_data = {
            "root_key": root_key,
            "sub_key": sub_key,
            "value_name": value_name or "(默认)",
            "value": value_data,
            "value_type": value_type,
        }

        logger.info(f"[reg_write] 成功写入: {root_key}\\{sub_key}\\{value_name or '(默认)'}")
        return {"code": 200, "data": result_data, "message": "写入成功"}

    except PermissionError:
        error_msg = f"权限不足，无法写入: {root_key}\\{sub_key}"
        logger.error(f"[reg_write] {error_msg}")
        return {"code": 403, "data": None, "message": error_msg}
    except Exception as e:
        error_msg = f"写入注册表失败: {str(e)}"
        logger.error(f"[reg_write] {error_msg}")
        return {"code": 500, "data": None, "message": error_msg}


def reg_delete(root_key: str, sub_key: str, value_name: Optional[str] = None) -> dict:
    """
    删除注册表键值或子键

    Args:
        root_key: 根键名称
        sub_key: 子键路径
        value_name: 值名称（None表示删除整个子键）

    Returns:
        {code, data, message}
    """
    try:
        hkey = ROOT_KEY_MAP.get(root_key)
        if hkey is None:
            return {"code": 400, "data": None, "message": f"无效的根键: {root_key}"}

        if value_name is not None:
            with winreg.OpenKey(hkey, sub_key, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, value_name)
            
            result_data = {
                "root_key": root_key,
                "sub_key": sub_key,
                "value_name": value_name,
                "action": "deleted_value"
            }
            logger.info(f"[reg_delete] 成功删除值: {root_key}\\{sub_key}\\{value_name}")
        else:
            parent_key = "\\".join(sub_key.split("\\")[:-1])
            key_name = sub_key.split("\\")[-1]
            
            if not parent_key:
                return {"code": 400, "data": None, "message": "不能直接删除根键下的子键"}

            with winreg.OpenKey(hkey, parent_key, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteKey(key, key_name)
            
            result_data = {
                "root_key": root_key,
                "sub_key": sub_key,
                "action": "deleted_key"
            }
            logger.info(f"[reg_delete] 成功删除子键: {root_key}\\{sub_key}")

        return {"code": 200, "data": result_data, "message": "删除成功"}

    except FileNotFoundError:
        error_msg = f"注册表键或值不存在: {root_key}\\{sub_key}\\{value_name or '(整个子键)'}"
        logger.warning(f"[reg_delete] {error_msg}")
        return {"code": 404, "data": None, "message": error_msg}
    except PermissionError:
        error_msg = f"权限不足，无法删除: {root_key}\\{sub_key}"
        logger.error(f"[reg_delete] {error_msg}")
        return {"code": 403, "data": None, "message": error_msg}
    except OSError as e:
        error_msg = f"删除失败（可能子键不为空）: {str(e)}"
        logger.error(f"[reg_delete] {error_msg}")
        return {"code": 500, "data": None, "message": error_msg}
    except Exception as e:
        error_msg = f"删除注册表失败: {str(e)}"
        logger.error(f"[reg_delete] {error_msg}")
        return {"code": 500, "data": None, "message": error_msg}
