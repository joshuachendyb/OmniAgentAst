# -*- coding: utf-8 -*-
"""
batch_rename - 批量重命名文件

功能：
- 根据模式批量重命名目录中的文件
- 支持正则表达式和简单字符串替换
- 支持递归处理子目录
- 支持预览模式
- 支持冲突处理策略（跳过、覆盖、自动重命名）

Author: 小健 - 2026-04-19
"""

import asyncio
import re
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple


async def batch_rename_impl(
    directory: str,
    pattern: str,
    replacement: str,
    recursive: bool = False,
    preview: bool = False,
    conflict_strategy: str = "skip",
    validate_path_func=None,
    safety_service=None,
    session_id: Optional[str] = None,
    record_operation_func=None,
    execute_with_safety_func=None,
    to_unified_format_func=None,
    get_next_sequence_func=None,
) -> Dict[str, Any]:
    """
    batch_rename工具的实现函数
    
    Args:
        directory: 目标目录路径
        pattern: 匹配模式（支持正则表达式）
        replacement: 替换字符串
        recursive: 是否递归处理子目录
        preview: 是否只预览不执行
        conflict_strategy: 冲突处理策略（skip、overwrite、rename）
        validate_path_func: 路径验证函数
        safety_service: 安全服务
        session_id: 会话ID
        record_operation_func: 记录操作函数
        execute_with_safety_func: 安全执行函数
        to_unified_format_func: 统一格式转换函数
        get_next_sequence_func: 获取下一个序列号函数
    
    Returns:
        统一格式的结果字典
    """
    from app.services.safety.file.file_safety import OperationType
    
    # 验证路径
    is_valid, error_msg = validate_path_func(directory)
    if not is_valid:
        return to_unified_format_func({
            "success": False,
            "error": f"目录路径验证失败: {error_msg}",
            "operation_id": None
        }, "batch_rename")
    
    if not session_id:
        return to_unified_format_func({
            "success": False,
            "error": "No active session",
            "operation_id": None
        }, "batch_rename")
    
    dir_path = Path(directory)
    
    try:
        # 检查目录是否存在
        if not dir_path.exists():
            return to_unified_format_func({
                "success": False,
                "error": f"目录不存在: {directory}",
                "operation_id": None
            }, "batch_rename")
        
        if not dir_path.is_dir():
            return to_unified_format_func({
                "success": False,
                "error": f"路径不是目录: {directory}",
                "operation_id": None
            }, "batch_rename")
        
        # 编译正则表达式
        try:
            regex = re.compile(pattern)
            use_regex = True
        except re.error:
            # 如果不是有效的正则表达式，使用简单字符串替换
            use_regex = False
        
        # 收集文件
        files_to_process = []
        if recursive:
            # 递归收集所有文件
            for file_path in dir_path.rglob("*"):
                if file_path.is_file():
                    files_to_process.append(file_path)
        else:
            # 只处理当前目录的文件
            for file_path in dir_path.iterdir():
                if file_path.is_file():
                    files_to_process.append(file_path)
        
        # 处理每个文件
        operations = []
        renamed_count = 0
        skipped_count = 0
        failed_count = 0
        
        for file_path in files_to_process:
            original_name = file_path.name
            
            # 生成新文件名
            if use_regex:
                new_name = regex.sub(replacement, original_name)
            else:
                # 简单字符串替换
                new_name = original_name.replace(pattern, replacement)
            
            # 如果文件名没有变化，跳过
            if new_name == original_name:
                skipped_count += 1
                operations.append({
                    "file": str(file_path),
                    "original_name": original_name,
                    "new_name": new_name,
                    "status": "skipped",
                    "reason": "文件名未变化",
                    "operation_id": None
                })
                continue
            
            new_path = file_path.parent / new_name
            
            # 检查冲突
            conflict_resolved = False
            final_new_path = new_path
            if new_path.exists():
                if conflict_strategy == "skip":
                    skipped_count += 1
                    operations.append({
                        "file": str(file_path),
                        "original_name": original_name,
                        "new_name": new_name,
                        "status": "skipped",
                        "reason": "目标文件已存在（跳过）",
                        "operation_id": None
                    })
                    continue
                elif conflict_strategy == "overwrite":
                    # 覆盖模式，继续处理
                    pass
                elif conflict_strategy == "rename":
                    # 自动重命名，添加序号
                    counter = 1
                    while final_new_path.exists():
                        name_parts = new_path.stem.split('.')
                        if len(name_parts) > 1:
                            # 有扩展名的情况
                            base_name = '.'.join(name_parts[:-1])
                            extension = new_path.suffix
                            final_new_path = new_path.parent / f"{base_name}_{counter}{extension}"
                        else:
                            # 无扩展名的情况
                            final_new_path = new_path.parent / f"{new_path.stem}_{counter}"
                        counter += 1
                    conflict_resolved = True
            
            # 记录操作
            operation_id = None
            if record_operation_func:
                operation_id = record_operation_func(
                    session_id=session_id,
                    operation_type=OperationType.RENAME,
                    source_path=file_path,
                    destination_path=final_new_path,
                    sequence_number=get_next_sequence_func()
                )
            
            if not preview:
                # 执行重命名
                def _rename_sync():
                    try:
                        # 确保目标目录存在
                        final_new_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        # 执行重命名
                        if conflict_strategy == "overwrite" and final_new_path.exists():
                            # 覆盖模式，先删除目标文件
                            final_new_path.unlink()
                        
                        shutil.move(str(file_path), str(final_new_path))
                        return True
                    except Exception as e:
                        # 记录错误但不中断整个操作
                        return str(e)
                
                rename_result = await asyncio.to_thread(
                    execute_with_safety_func,
                    operation_id=operation_id,
                    operation_func=_rename_sync
                )
                
                if rename_result is True:
                    renamed_count += 1
                    operations.append({
                        "file": str(file_path),
                        "original_name": original_name,
                        "new_name": final_new_path.name,
                        "new_path": str(final_new_path),
                        "status": "renamed",
                        "operation_id": operation_id,
                        "conflict_resolved": conflict_resolved
                    })
                else:
                    failed_count += 1
                    operations.append({
                        "file": str(file_path),
                        "original_name": original_name,
                        "new_name": new_name,
                        "status": "failed",
                        "error": str(rename_result),
                        "operation_id": operation_id
                    })
            else:
                # 预览模式，只记录计划
                renamed_count += 1
                operations.append({
                    "file": str(file_path),
                    "original_name": original_name,
                    "new_name": final_new_path.name,
                    "new_path": str(final_new_path),
                    "status": "planned",
                    "conflict_resolved": conflict_resolved,
                    "operation_id": None  # 预览模式没有实际操作ID
                })
        
        # 构建结果
        result = {
            "directory": str(dir_path),
            "pattern": pattern,
            "replacement": replacement,
            "use_regex": use_regex,
            "recursive": recursive,
            "preview_mode": preview,
            "conflict_strategy": conflict_strategy,
            "total_files": len(files_to_process),
            "renamed_files": renamed_count,
            "skipped_files": skipped_count,
            "failed_files": failed_count,
            "operations": operations
        }
        
        return to_unified_format_func({
            "success": True,
            "operation_id": None if preview else (operations[0]["operation_id"] if operations and len(operations) > 0 else None),
            **result
        }, "batch_rename")
            
    except Exception as e:
        return to_unified_format_func({
            "success": False,
            "error": str(e),
            "operation_id": None
        }, "batch_rename")
