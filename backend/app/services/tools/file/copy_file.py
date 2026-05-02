# -*- coding: utf-8 -*-
"""
copy_file - 文件复制工具

功能：
- 复制文件到新位置
- 支持递归复制目录
- 支持覆盖控制

Author: 小健 - 2026-04-19
"""

import asyncio
import shutil
from pathlib import Path
from typing import Dict, Any, Optional


async def copy_file_impl(
    source_path: str,
    destination_path: str,
    recursive: bool,
    overwrite: bool,
    preserve_metadata: bool = True,
    validate_path_func,
    safety_service,
    task_id: Optional[str],
    record_operation_func,
    execute_with_safety_func,
    to_unified_format_func,
    get_next_sequence_func,
) -> Dict[str, Any]:
    """
    copy_file工具的实现函数 - 小健 2026-05-02 增加preserve_metadata
    
    Args:
        source_path: 源文件或目录路径
        destination_path: 目标路径
        recursive: 是否递归复制目录
        overwrite: 是否覆盖已存在的目标
        preserve_metadata: 是否保留文件元数据（时间戳等），默认True
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
    
    # 验证源路径
    is_valid_src, error_msg_src = validate_path_func(source_path)
    if not is_valid_src:
        return to_unified_format_func({
            "success": False,
            "error": f"源路径{error_msg_src}",
            "operation_id": None
        }, "copy_file")
    
    # 验证目标路径
    is_valid_dst, error_msg_dst = validate_path_func(destination_path)
    if not is_valid_dst:
        return to_unified_format_func({
            "success": False,
            "error": f"目标路径{error_msg_dst}",
            "operation_id": None
        }, "copy_file")
    
    if not task_id:
        return to_unified_format_func({
            "success": False,
            "error": "No active task",
            "operation_id": None
        }, "copy_file")
    
    src = Path(source_path)
    dst = Path(destination_path)
    
    try:
        if not src.exists():
            return to_unified_format_func({
                "success": False,
                "error": f"Source not found: {source_path}",
                "operation_id": None
            }, "copy_file")
        
        # 检查目标是否已存在
        if dst.exists() and not overwrite:
            return to_unified_format_func({
                "success": False,
                "error": f"目标路径已存在: {dst}，复制操作已取消。请设置overwrite=True或指定其他路径。",
                "operation_id": None
            }, "copy_file")
        
        # 记录操作
        operation_id = record_operation_func(
            task_id=task_id,
            operation_type=OperationType.COPY,
            source_path=src,
            destination_path=dst,
            sequence_number=get_next_sequence_func()
        )
        
        # 定义复制操作
        def _copy_sync():
            dst.parent.mkdir(parents=True, exist_ok=True)
            
            copy_func = shutil.copy2 if preserve_metadata else shutil.copy
            
            if src.is_file():
                copy_func(str(src), str(dst))
            elif src.is_dir():
                if recursive:
                    if dst.exists():
                        shutil.rmtree(str(dst))
                    if preserve_metadata:
                        shutil.copytree(str(src), str(dst))
                    else:
                        shutil.copytree(str(src), str(dst), copy_function=shutil.copy)
                else:
                    dst.mkdir(exist_ok=True)
            return True
        
        success = await asyncio.to_thread(
            execute_with_safety_func,
            operation_id=operation_id,
            operation_func=_copy_sync
        )
        
        if success:
            return to_unified_format_func({
                "success": True,
                "operation_id": operation_id,
                "source": str(src),
                "destination": str(dst),
                "message": f"Copied: {src.name} -> {dst}"
            }, "copy_file")
        else:
            return to_unified_format_func({
                "success": False,
                "error": "Failed to copy file",
                "operation_id": operation_id
            }, "copy_file")
            
    except Exception as e:
        return to_unified_format_func({
            "success": False,
            "error": str(e),
            "operation_id": None
        }, "copy_file")
