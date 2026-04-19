# -*- coding: utf-8 -*-
"""
compare_files - 文件比较工具

功能：
- 比较两个文件的内容、大小或修改时间
- 支持多种比较算法（content、size、mtime）
- 支持大文件分块比较
- 支持二进制和文本文件比较

Author: 小健 - 2026-04-19
"""

import asyncio
import hashlib
import os
from pathlib import Path
from typing import Dict, Any, Optional


async def compare_files_impl(
    file_path1: str,
    file_path2: str,
    algorithm: str = "content",
    chunk_size: int = 8192,
    validate_path_func=None,
    safety_service=None,
    session_id: Optional[str] = None,
    record_operation_func=None,
    execute_with_safety_func=None,
    to_unified_format_func=None,
    get_next_sequence_func=None,
) -> Dict[str, Any]:
    """
    compare_files工具的实现函数
    
    Args:
        file_path1: 第一个文件路径
        file_path2: 第二个文件路径
        algorithm: 比较算法：content（内容）、size（大小）、mtime（修改时间）
        chunk_size: 分块大小（字节），用于大文件比较
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
    for fp in [file_path1, file_path2]:
        is_valid, error_msg = validate_path_func(fp)
        if not is_valid:
            return to_unified_format_func({
                "success": False,
                "error": f"路径验证失败: {error_msg}",
                "operation_id": None
            }, "compare_files")
    
    if not session_id:
        return to_unified_format_func({
            "success": False,
            "error": "No active session",
            "operation_id": None
        }, "compare_files")
    
    path1, path2 = Path(file_path1), Path(file_path2)
    
    try:
        # 检查文件是否存在
        if not path1.exists():
            return to_unified_format_func({
                "success": False,
                "error": f"文件不存在: {file_path1}",
                "operation_id": None
            }, "compare_files")
        
        if not path2.exists():
            return to_unified_format_func({
                "success": False,
                "error": f"文件不存在: {file_path2}",
                "operation_id": None
            }, "compare_files")
        
        # 记录操作
        operation_id = record_operation_func(
            session_id=session_id,
            operation_type=OperationType.COMPARE,
            source_path=path1,
            destination_path=path2,
            sequence_number=get_next_sequence_func()
        )
        
        # 定义比较操作
        def _compare_sync():
            # 获取文件信息
            stat1 = path1.stat()
            stat2 = path2.stat()
            
            size1 = stat1.st_size
            size2 = stat2.st_size
            mtime1 = stat1.st_mtime
            mtime2 = stat2.st_mtime
            
            # 根据算法进行比较
            if algorithm == "size":
                # 只比较大小
                identical = size1 == size2
                size_match = identical
                content_match = None
            elif algorithm == "mtime":
                # 只比较修改时间
                identical = mtime1 == mtime2
                size_match = size1 == size2
                content_match = None
            else:  # content 或默认
                # 比较内容
                if size1 != size2:
                    # 大小不同，内容肯定不同
                    identical = False
                    size_match = False
                    content_match = False
                else:
                    # 大小相同，需要比较内容
                    size_match = True
                    
                    # 对于大文件，使用分块比较
                    if size1 > chunk_size * 10:  # 如果文件较大，使用分块比较
                        identical = _compare_files_by_chunks(path1, path2, chunk_size)
                        content_match = identical
                    else:
                        # 小文件直接读取比较
                        content1 = path1.read_bytes()
                        content2 = path2.read_bytes()
                        identical = content1 == content2
                        content_match = identical
            
            return {
                "file1": str(path1),
                "file2": str(path2),
                "size1": size1,
                "size2": size2,
                "size_match": size_match,
                "mtime1": mtime1,
                "mtime2": mtime2,
                "mtime_match": mtime1 == mtime2,
                "identical": identical,
                "algorithm": algorithm,
                "content_match": content_match if algorithm == "content" else None,
                "comparison_time": None,  # 将在外部计算
            }
        
        # 执行比较操作
        import time
        start_time = time.time()
        
        result = await asyncio.to_thread(
            execute_with_safety_func,
            operation_id=operation_id,
            operation_func=_compare_sync
        )
        
        end_time = time.time()
        result["comparison_time"] = end_time - start_time
        
        if result:
            return to_unified_format_func({
                "success": True,
                "operation_id": operation_id,
                "comparison": result
            }, "compare_files")
        else:
            return to_unified_format_func({
                "success": False,
                "error": "文件比较失败",
                "operation_id": operation_id
            }, "compare_files")
            
    except Exception as e:
        return to_unified_format_func({
            "success": False,
            "error": str(e),
            "operation_id": None
        }, "compare_files")


def _compare_files_by_chunks(path1: Path, path2: Path, chunk_size: int) -> bool:
    """
    分块比较两个大文件的内容
    
    Args:
        path1: 第一个文件路径
        path2: 第二个文件路径
        chunk_size: 分块大小
    
    Returns:
        文件内容是否相同
    """
    # 先比较文件大小
    if path1.stat().st_size != path2.stat().st_size:
        return False
    
    # 使用哈希比较（更高效）
    hash1 = hashlib.md5()
    hash2 = hashlib.md5()
    
    try:
        with open(path1, 'rb') as f1, open(path2, 'rb') as f2:
            while True:
                chunk1 = f1.read(chunk_size)
                chunk2 = f2.read(chunk_size)
                
                # 如果两个文件都读取完毕
                if not chunk1 and not chunk2:
                    break
                
                # 如果只有一个文件读取完毕
                if not chunk1 or not chunk2:
                    return False
                
                # 如果块内容不同
                if chunk1 != chunk2:
                    return False
                
                # 更新哈希
                hash1.update(chunk1)
                hash2.update(chunk2)
        
        # 比较最终哈希值
        return hash1.hexdigest() == hash2.hexdigest()
        
    except Exception:
        # 如果哈希比较失败，回退到逐字节比较
        return _compare_files_byte_by_byte(path1, path2, chunk_size)


def _compare_files_byte_by_byte(path1: Path, path2: Path, chunk_size: int) -> bool:
    """
    逐字节比较两个文件的内容（回退方案）
    
    Args:
        path1: 第一个文件路径
        path2: 第二个文件路径
        chunk_size: 分块大小
    
    Returns:
        文件内容是否相同
    """
    try:
        with open(path1, 'rb') as f1, open(path2, 'rb') as f2:
            while True:
                chunk1 = f1.read(chunk_size)
                chunk2 = f2.read(chunk_size)
                
                if not chunk1 and not chunk2:
                    return True
                
                if not chunk1 or not chunk2:
                    return False
                
                if chunk1 != chunk2:
                    return False
    except Exception:
        return False