# -*- coding: utf-8 -*-
"""
create_directory - 目录创建工具

功能：
- 创建新目录
- 支持创建父目录
- 支持已存在检查

Author: 小健 - 2026-04-19
"""

import asyncio
from pathlib import Path
from typing import Dict, Any, Optional


async def create_directory_impl(
    dir_path: str,
    parents: bool,
    exist_ok: bool,
    validate_path_func,
    safety_service,
    task_id: Optional[str],
    record_operation_func,
    execute_with_safety_func,
    to_unified_format_func,
    get_next_sequence_func,
) -> Dict[str, Any]:
    """
    create_directory工具的实现函数
    
    Args:
        dir_path: 要创建的目录路径
        parents: 是否创建父目录
        exist_ok: 如果目录已存在是否报错
        validate_path_func: 路径验证函数
        safety_service: 安全服务
        task_id: 任务ID
        record_operation_func: 记录操作函数
        execute_with_safety_func: 安全执行函数
        to_unified_format_func: 统一格式转换函数
        get_next_sequence_func: 获取下一个序列号函数
    
    Returns:
        统一格式的结果字典
    """
    from app.services.safety.file.file_safety import OperationType
    
    # 验证路径
    is_valid, error_msg = validate_path_func(dir_path)
    if not is_valid:
        return to_unified_format_func({
            "success": False,
            "error": error_msg,
            "operation_id": None
        }, "create_directory")
    
    if not task_id:
        return to_unified_format_func({
            "success": False,
            "error": "No active task",
            "operation_id": None
        }, "create_directory")
    
    path = Path(dir_path)
    
    try:
        # 检查目录是否已存在
        if path.exists():
            if not exist_ok:
                return to_unified_format_func({
                    "success": False,
                    "error": f"Directory already exists: {dir_path}",
                    "operation_id": None
                }, "create_directory")
            else:
                # 目录已存在且允许存在，直接返回成功
                return to_unified_format_func({
                    "success": True,
                    "operation_id": None,
                    "directory": str(path),
                    "message": f"Directory already exists: {path}"
                }, "create_directory")
        
        # 记录操作
        operation_id = record_operation_func(
            task_id=task_id,
            operation_type=OperationType.CREATE,
            destination_path=path,
            sequence_number=get_next_sequence_func()
        )
        
        # 定义创建操作
        def _create_sync():
            if parents:
                # 创建父目录
                path.mkdir(parents=True, exist_ok=True)
            else:
                # 不创建父目录，如果父目录不存在会报错
                path.mkdir(exist_ok=False)
            return True
        
        success = await asyncio.to_thread(
            execute_with_safety_func,
            operation_id=operation_id,
            operation_func=_create_sync
        )
        
        if success:
            return to_unified_format_func({
                "success": True,
                "operation_id": operation_id,
                "directory": str(path),
                "message": f"Directory created: {path}"
            }, "create_directory")
        else:
            return to_unified_format_func({
                "success": False,
                "error": "Failed to create directory",
                "operation_id": operation_id
            }, "create_directory")
            
    except Exception as e:
        return to_unified_format_func({
            "success": False,
            "error": str(e),
            "operation_id": None
        }, "create_directory")
