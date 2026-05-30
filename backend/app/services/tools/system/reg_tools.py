# -*- coding: utf-8 -*-
"""
REGISTRY 工具函数模块 - Windows注册表操作工具

【创建时间】2026-05-02 小沈
【更新时间】2026-05-03 小沈
【规范】按文档7.2节参数定义更新

【重要】新函数增加规范 - 小沈 2026-05-04
新增函数时必须同步修改以下3个文件：
1. *_tools.py: 函数实现（必须有详细注释）
2. *_schema.py: Pydantic 模型（输入参数定义）
3. *_register.py: 显式注册（description + examples + input_model）

包含：
- registry_control: 注册表统一控制入口（action="read"|"write"|"delete"）
- reg_read: 读取注册表键值（内部函数）
- reg_write: 写入注册表键值（内部函数）
- reg_delete: 删除注册表键值（内部函数）

返回格式：统一 {code, data, message} 格式

Author: 小沈 - 2026-05-02
"""

import os
import subprocess
import tempfile
import winreg
from typing import Optional, Dict, Any, Literal, Callable
from datetime import datetime
from app.constants import (ERR_REG_DELETE_FAILED, ERR_REG_INVALID_PARAM, ERR_REG_PERMISSION_DENIED,
    ERR_REG_READ_FAILED, ERR_REG_UNSUPPORTED_TYPE, ERR_REG_VALIDATE_FAILED, ERR_REG_WRITE_FAILED,
    ERR_SYS_REG_CANNOT_DELETE_ROOT, ERR_SYS_REG_INVALID_ROOT_KEY, ERR_SYS_REG_KEY_NOT_EMPTY,
    ERR_SYS_REG_KEY_NOT_FOUND)

from app.utils.logger import logger
from app.utils.tool_result_formatter import build_next_actions  # 小沈 2026-05-19
from app.services.tools._response import build_success, build_error





# 文档定义的参数映射：简称 -> Windows注册表常量
HIVE_MAP = {
    "HKCU": "HKEY_CURRENT_USER",
    "HKLM": "HKEY_LOCAL_MACHINE",
    "HKCR": "HKEY_CLASSES_ROOT",
    "HKU": "HKEY_USERS",
    "HKCC": "HKEY_CURRENT_CONFIG",
}

ROOT_KEY_MAP = {
    "HKEY_CLASSES_ROOT": winreg.HKEY_CLASSES_ROOT,
    "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
    "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
    "HKEY_USERS": winreg.HKEY_USERS,
    "HKEY_CURRENT_CONFIG": winreg.HKEY_CURRENT_CONFIG,
}

# 会话级备份存储
_registry_session_backup = {}


def _parse_key_path(key_path: str, hive: str = "HKCU") -> tuple:
    """解析key_path，提取根键和子键路径 - 小沈 2026-05-05 修正映射逻辑
    
    Args:
        key_path: 完整键路径，可能含根键前缀
        hive: 默认根键
    
    Returns:
        (root_key_name, sub_key_path)
    """
    for hk_name, full_name in HIVE_MAP.items():
        if key_path.upper().startswith(f"{hk_name}\\"):
            sub = key_path[len(hk_name)+1:]
            return full_name, sub
        if key_path.upper().startswith(f"{full_name}\\"):
            sub = key_path[len(full_name)+1:]
            return full_name, sub
    
    return HIVE_MAP.get(hive, "HKEY_CURRENT_USER"), key_path


def _backup_registry(root_key: str, sub_key: str, session_id: str) -> str:
    """备份注册表键到临时文件 - 小健 2026-05-19 实现真实备份(原为空壳)
    使用Windows reg export命令导出注册表键到.reg文件
    """
    backup_key = f"{root_key}\\{sub_key}"
    if backup_key in _registry_session_backup:
        return _registry_session_backup[backup_key]
    
    backup_dir = tempfile.gettempdir()
    backup_file = os.path.join(backup_dir, f"reg_backup_{session_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.reg")
    
    try:
        export_key = f"{root_key}\\{sub_key}"
        result = subprocess.run(
            ["reg", "export", export_key, backup_file, "/y"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and os.path.exists(backup_file):
            _registry_session_backup[backup_key] = backup_file
            logger.info(f"[registry] 备份成功: {backup_key} -> {backup_file}")
        else:
            logger.warning(f"[registry] reg export失败(返回码{result.returncode}): {result.stderr.strip()}")
            _registry_session_backup[backup_key] = backup_file
    except FileNotFoundError:
        logger.warning("[registry] reg命令不存在，跳过备份")
        _registry_session_backup[backup_key] = backup_file
    except Exception as e:
        logger.warning(f"[registry] 备份失败: {e}")
        _registry_session_backup[backup_key] = backup_file
    
    return backup_file


def reg_read(key_path: str, value_name: Optional[str] = None, hive: str = "HKCU", output_format: str = "auto") -> dict:
    """读取注册表键值
    
    按文档7.2节参数定义：
    - key_path: 注册表键路径
    - value_name: 值名称（可选），默认None
    - hive: 根键（可选），默认HKCU
    - output_format: 输出格式（可选），默认auto
    
    Args:
        key_path: 注册表键路径
        value_name: 值名称（可选）
        hive: 根键（可选）
        output_format: 输出格式（可选）
    
    Returns:
        {code, data, message}
    """
    try:
        # 解析key_path，提取root_key和sub_key
        full_root_key, sub_key = _parse_key_path(key_path, hive)
        hkey = ROOT_KEY_MAP.get(full_root_key)
        
        if hkey is None:
            return build_error(ERR_SYS_REG_INVALID_ROOT_KEY, f"无效的根键: {full_root_key}")

        with winreg.OpenKey(hkey, sub_key, 0, winreg.KEY_READ) as key:
            value, reg_type = winreg.QueryValueEx(key, value_name)
            
            value_type_name = {
                winreg.REG_SZ: "REG_SZ",
                winreg.REG_DWORD: "REG_DWORD",
                winreg.REG_QWORD: "REG_QWORD",
                winreg.REG_EXPAND_SZ: "REG_EXPAND_SZ",
                winreg.REG_MULTI_SZ: "REG_MULTI_SZ",
                winreg.REG_BINARY: "REG_BINARY",
                winreg.REG_NONE: "REG_NONE",
            }.get(reg_type, f"UNKNOWN({reg_type})")

            # 根据output_format格式化输出
            formatted_value = value
            if output_format == "hex" and isinstance(value, (bytes, bytearray)):
                formatted_value = value.hex()
            elif output_format == "raw":
                formatted_value = value
            
            result_data = {
                "key_path": f"{full_root_key}\\{sub_key}",
                "value_name": value_name or "(默认)",
                "value": formatted_value,
                "value_type": value_type_name,
            }

            logger.info(f"[reg_read] 成功读取: {full_root_key}\\{sub_key}\\{value_name or '(默认)'}")
            return build_success(result_data, "读取成功")

    except FileNotFoundError:
        error_msg = f"注册表键或值不存在: {key_path}"
        logger.warning(f"[reg_read] {error_msg}")
        return build_error(ERR_SYS_REG_KEY_NOT_FOUND, error_msg)
    except PermissionError:
        error_msg = f"权限不足，无法访问: {key_path}"
        logger.error(f"[reg_read] {error_msg}")
        return build_error(ERR_REG_PERMISSION_DENIED, error_msg)
    except Exception as e:
        error_msg = f"读取注册表失败: {str(e)}"
        logger.error(f"[reg_read] {error_msg}")
        return build_error(ERR_REG_READ_FAILED, error_msg)


# 【24.3.4 组件1】_REG_TYPE_MAP 移至模块级(消除每次调用重建)
_REG_TYPE_MAP: Dict[str, int] = {
    "REG_SZ": winreg.REG_SZ,
    "REG_DWORD": winreg.REG_DWORD,
    "REG_QWORD": winreg.REG_QWORD,
    "REG_EXPAND_SZ": winreg.REG_EXPAND_SZ,
    "REG_MULTI_SZ": winreg.REG_MULTI_SZ,
    "REG_BINARY": winreg.REG_BINARY,
}


# 【24.3.4 组件2】统一根键校验(消除 H1 重复)
def _validate_root_key(full_root_key: str) -> Optional[int]:
    """校验根键是否有效，返回 hkey 或 None — 小健 2026-05-25"""
    hkey = ROOT_KEY_MAP.get(full_root_key)
    if hkey is None:
        return None
    return hkey


# 【24.3.4 组件3】统一值类型转换(消除 V1a-V1f 6 路 elif)
_REG_CONVERTERS: Dict[str, Callable] = {
    "REG_DWORD": lambda v: int(v),
    "REG_QWORD": lambda v: int(v),
    "REG_EXPAND_SZ": lambda v: v,
    "REG_BINARY": lambda v: bytes.fromhex(v.replace(" ", "")),
    "REG_MULTI_SZ": lambda v: v.split(";") if isinstance(v, str) else v,
}


def _convert_reg_value(value_type: str, value: str) -> Any:
    """按注册表类型转换值 — 小健 2026-05-25"""
    converter = _REG_CONVERTERS.get(value_type)
    return converter(value) if converter else value


def reg_write(key_path: str, value_name: str, value: str, value_type: str = "auto_detect", backup_before_write: bool = True, dry_run: bool = False, hive: str = "HKCU") -> dict:
    """写入注册表键值
    
    按文档7.2节参数定义：
    - key_path: 注册表键路径
    - value_name: 值名称
    - value: 值数据
    - value_type: 值类型（可选），默认auto_detect
    - backup_before_write: 写入前备份（可选），默认true
    - dry_run: 预演模式（可选），默认false
    
    Args:
        key_path: 注册表键路径
        value_name: 值名称
        value: 值数据
        value_type: 值类型
        backup_before_write: 是否备份
        dry_run: 预演模式
    
    Returns:
        {code, data, message}
    """
    # 【24.3.4 重构后主函数】~55行骨架
    full_root_key, sub_key = _parse_key_path(key_path, hive)
    hkey = _validate_root_key(full_root_key)
    if hkey is None:
        return build_error(ERR_SYS_REG_INVALID_ROOT_KEY, f"无效的根键: {full_root_key}")

    if dry_run:
        try:
            with winreg.OpenKey(hkey, sub_key, 0, winreg.KEY_READ):
                pass
            return build_success({"key_path": key_path, "dry_run": True}, "键路径有效，可以写入")
        except FileNotFoundError:
            return build_error(ERR_SYS_REG_KEY_NOT_FOUND, f"键路径不存在: {key_path}")
        except Exception as e:
            return build_error(ERR_REG_VALIDATE_FAILED, f"校验失败: {e}")

    try:
        if backup_before_write:
            _backup_registry(full_root_key, sub_key, "reg_write")

        actual_type = value_type
        if value_type == "auto_detect":
            actual_type = "REG_DWORD" if value.isdigit() else "REG_SZ"

        if actual_type not in _REG_TYPE_MAP:
            return build_error(ERR_REG_UNSUPPORTED_TYPE, f"不支持的类型: {value_type}")

        converted = _convert_reg_value(actual_type, value)
        with winreg.CreateKey(hkey, sub_key) as key:
            winreg.SetValueEx(key, value_name, 0, _REG_TYPE_MAP[actual_type], converted)

        logger.info(f"[reg_write] 写入成功: {full_root_key}\\{sub_key}\\{value_name}")
        return build_success({"key_path": f"{full_root_key}\\{sub_key}", "value_name": value_name,
                              "value": value, "value_type": actual_type}, "写入成功")
    except PermissionError:
        logger.error(f"[reg_write] 权限不足: {key_path}")
        return build_error(ERR_REG_PERMISSION_DENIED, f"权限不足: {key_path}")
    except Exception as e:
        logger.error(f"[reg_write] 写入失败: {e}")
        return build_error(ERR_REG_WRITE_FAILED, f"写入注册表失败: {e}")


def reg_delete(key_path: str, value_name: Optional[str] = None, backup_before_delete: bool = True, recursive: bool = False, hive: str = "HKCU") -> dict:
    """删除注册表键值或子键
    
    按文档7.2节参数定义：
    - key_path: 注册表键路径
    - value_name: 值名称（可选），默认None
    - backup_before_delete: 删除前备份（可选），默认true
    - recursive: 递归删除（可选），默认false
    
    Args:
        key_path: 注册表键路径
        value_name: 值名称（可选）
        backup_before_delete: 是否备份
        recursive: 是否递归删除
    
    Returns:
        {code, data, message}
    """
    try:
        # 解析key_path（所有模式都需要）
        full_root_key, sub_key = _parse_key_path(key_path)
        hkey = ROOT_KEY_MAP.get(full_root_key)
        
        if hkey is None:
            return build_error(ERR_SYS_REG_INVALID_ROOT_KEY, f"无效的根键: {full_root_key}")

        # 备份
        if backup_before_delete:
            session_id = "reg_delete"
            _backup_registry(full_root_key, sub_key, session_id)

        if value_name is not None:
            # 仅删除值
            with winreg.OpenKey(hkey, sub_key, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, value_name)
            
            result_data = {
                "key_path": f"{full_root_key}\\{sub_key}",
                "value_name": value_name,
                "action": "deleted_value"
            }
            logger.info(f"[reg_delete] 成功删除值: {full_root_key}\\{sub_key}\\{value_name}")
        else:
            # 删除整个键
            if not recursive:
                # 非递归模式：检查键是否为空
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
                            return build_error(ERR_SYS_REG_KEY_NOT_EMPTY, f"键不为空（{i}个子键），使用 recursive=True 强制删除")
                except FileNotFoundError:
                    pass
            
            # 删除键
            parent_key = "\\".join(sub_key.split("\\")[:-1])
            key_name = sub_key.split("\\")[-1]
            
            if not parent_key:
                return build_error(ERR_SYS_REG_CANNOT_DELETE_ROOT, "不能直接删除根键下的子键")

            with winreg.OpenKey(hkey, parent_key, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteKey(key, key_name)
            
            result_data = {
                "key_path": f"{full_root_key}\\{sub_key}",
                "action": "deleted_key",
                "recursive": recursive
            }
            logger.info(f"[reg_delete] 成功删除子键: {full_root_key}\\{sub_key}")

        return build_success(result_data, "删除成功")

    except FileNotFoundError:
        error_msg = f"注册表键或值不存在: {key_path}"
        logger.warning(f"[reg_delete] {error_msg}")
        return build_error(ERR_SYS_REG_KEY_NOT_FOUND, error_msg)
    except PermissionError:
        error_msg = f"权限不足，无法删除: {key_path}"
        logger.error(f"[reg_delete] {error_msg}")
        return build_error(ERR_REG_PERMISSION_DENIED, error_msg)
    except OSError as e:
        error_msg = f"删除失败（可能子键不为空）: {str(e)}"
        logger.error(f"[reg_delete] {error_msg}")
        return build_error(ERR_REG_DELETE_FAILED, error_msg)
    except Exception as e:
        error_msg = f"删除注册表失败: {str(e)}"
        logger.error(f"[reg_delete] {error_msg}")
        return build_error(ERR_REG_DELETE_FAILED, error_msg)


def registry_control(
    key_path: str,
    action: Literal["read", "write", "delete"],
    value_name: Optional[str] = None,
    value: Optional[str] = None,
    value_type: str = "auto_detect",
    hive: str = "HKCU",
    recursive: bool = False,
) -> dict:
    """注册表统一控制入口 - 小沈 2026-05-19 参数精简11→7
    合并 reg_read + reg_write + reg_delete，通过action参数路由
    【2026-05-18 小沈】P11统一入口+P2相似整合
    【2026-05-19 小沈】砍4参数：output_format/backup_before_write/backup_before_delete/dry_run

    Args:
        action: 操作类型 "read"|"write"|"delete"，默认"read"
        key_path: 注册表键路径（必填）
        value_name: 值名称（read/delete时可选，write时必填）
        value: 值数据（仅write时使用）
        value_type: 值类型（仅write时使用），默认auto_detect
        hive: 根键，默认HKCU
        recursive: 递归删除（仅delete时使用），默认False

    Returns:
        {code, data, message}
    """
    # ⚠️ 警告: 以下参数已从Schema移除，硬编码默认值，后续视需求决定是否恢复
    output_format: str = "auto"
    backup_before_write: bool = True
    backup_before_delete: bool = True
    dry_run: bool = False
    if not key_path:
        return build_error(ERR_REG_INVALID_PARAM, "key_path不能为空")

    if action == "read":
        result = reg_read(key_path=key_path, value_name=value_name, hive=hive, output_format=output_format)
    elif action == "write":
        if not value_name:
            return build_error(ERR_REG_INVALID_PARAM, "action='write'时value_name必填")
        if value is None:
            return build_error(ERR_REG_INVALID_PARAM, "action='write'时value必填")
        result = reg_write(key_path=key_path, value_name=value_name, value=value,
                        value_type=value_type, backup_before_write=backup_before_write,
                        dry_run=dry_run, hive=hive)
    elif action == "delete":
        result = reg_delete(key_path=key_path, value_name=value_name,
                         backup_before_delete=backup_before_delete, recursive=recursive, hive=hive)
    else:
        return build_error(ERR_REG_INVALID_PARAM, f"无效的action: {action}，支持: read/write/delete")

    if result.get("code") == "SUCCESS":
        result["next_actions"] = build_next_actions([("registry_control", "验证注册表操作", "需要确认操作结果时")])
    return result
