# -*- coding: utf-8 -*-
"""
file_checksum - 计算文件校验和

功能：
- 计算文件的MD5、SHA1、SHA256、SHA512等校验和
- 支持大文件流式哈希计算
- 支持哈希验证模式
- 支持批量文件哈希计算

Author: 小健 - 2026-04-19
"""

import asyncio
import hashlib
import time
from pathlib import Path
from typing import Dict, Any, Optional, List


async def file_checksum_impl(
    file_path: str,
    algorithm: str = "md5",
    verify_hash: Optional[str] = None,
    chunk_size: int = 65536,
    validate_path_func=None,
    safety_service=None,
    task_id: Optional[str] = None,
    record_operation_func=None,
    execute_with_safety_func=None,
    to_unified_format_func=None,
    get_next_sequence_func=None,
) -> Dict[str, Any]:
    """
    file_checksum工具的实现函数
    
    Args:
        file_path: 文件路径
        algorithm: 哈希算法：md5、sha1、sha256、sha512
        verify_hash: 验证哈希值（如果提供则进行验证）
        chunk_size: 分块大小（字节），用于大文件哈希计算
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
    is_valid, error_msg = validate_path_func(file_path)
    if not is_valid:
        return to_unified_format_func({
            "success": False,
            "error": f"文件路径验证失败: {error_msg}",
            "operation_id": None
        }, "file_checksum")
    
    if not task_id:
        return to_unified_format_func({
            "success": False,
            "error": "No active task",
            "operation_id": None
        }, "file_checksum")
    
    # 验证哈希算法
    supported_algorithms = ["md5", "sha1", "sha256", "sha512"]
    if algorithm.lower() not in supported_algorithms:
        return to_unified_format_func({
            "success": False,
            "error": f"不支持的哈希算法: {algorithm}，支持算法: {', '.join(supported_algorithms)}",
            "operation_id": None
        }, "file_checksum")
    
    # 验证分块大小
    if chunk_size < 1024 or chunk_size > 1048576:  # 1KB to 1MB
        return to_unified_format_func({
            "success": False,
            "error": f"无效的分块大小: {chunk_size}，必须在1024到1048576之间",
            "operation_id": None
        }, "file_checksum")
    
    path = Path(file_path)
    
    try:
        # 检查文件是否存在
        if not path.exists():
            return to_unified_format_func({
                "success": False,
                "error": f"文件不存在: {file_path}",
                "operation_id": None
            }, "file_checksum")
        
        if not path.is_file():
            return to_unified_format_func({
                "success": False,
                "error": f"路径不是文件: {file_path}",
                "operation_id": None
            }, "file_checksum")
        
        # 记录操作
        operation_id = record_operation_func(
            task_id=task_id,
            operation_type=OperationType.CHECKSUM,
            source_path=path,
            destination_path=None,
            sequence_number=get_next_sequence_func()
        )
        
        # 定义哈希计算操作
        def _calculate_checksum_sync():
            import time
            start_time = time.time()
            
            try:
                # 获取文件大小
                file_size = path.stat().st_size
                
                # 选择哈希算法
                algorithm_lower = algorithm.lower()
                if algorithm_lower == "md5":
                    hash_obj = hashlib.md5()
                elif algorithm_lower == "sha1":
                    hash_obj = hashlib.sha1()
                elif algorithm_lower == "sha256":
                    hash_obj = hashlib.sha256()
                elif algorithm_lower == "sha512":
                    hash_obj = hashlib.sha512()
                else:
                    raise ValueError(f"不支持的哈希算法: {algorithm}")
                
                # 计算哈希值
                with open(path, 'rb') as f:
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        hash_obj.update(chunk)
                
                checksum = hash_obj.hexdigest()
                end_time = time.time()
                
                # 验证哈希值（如果提供了验证哈希）
                verification_result = None
                if verify_hash is not None:
                    verification_result = (checksum.lower() == verify_hash.lower())
                
                return {
                    "file_path": str(path),
                    "algorithm": algorithm,
                    "checksum": checksum,
                    "file_size": file_size,
                    "chunk_size": chunk_size,
                    "verification_result": verification_result,
                    "expected_hash": verify_hash if verify_hash else None,
                    "elapsed_time": end_time - start_time,
                    "hash_algorithm": algorithm_lower,
                    "checksum_upper": checksum.upper(),
                    "checksum_lower": checksum.lower()
                }
                
            except Exception as e:
                raise e
        
        # 执行哈希计算操作
        result = await asyncio.to_thread(
            execute_with_safety_func,
            operation_id=operation_id,
            operation_func=_calculate_checksum_sync
        )
        
        if result:
            # 构建最终结果
            final_result = {
                "success": True,
                "operation_id": operation_id,
                **result
            }
            
            # 如果有验证哈希，添加验证信息
            if verify_hash is not None:
                if result["verification_result"]:
                    final_result["verification_status"] = "passed"
                    final_result["message"] = f"哈希验证通过: {algorithm.upper()} 匹配"
                else:
                    final_result["verification_status"] = "failed"
                    final_result["message"] = f"哈希验证失败: {algorithm.upper()} 不匹配"
                    final_result["expected_hash"] = verify_hash
                    final_result["actual_hash"] = result["checksum"]
            else:
                final_result["verification_status"] = "not_verified"
                final_result["message"] = f"哈希计算完成: {algorithm.upper()}"
            
            return to_unified_format_func(final_result, "file_checksum")
        else:
            return to_unified_format_func({
                "success": False,
                "error": "哈希计算失败",
                "operation_id": operation_id
            }, "file_checksum")
            
    except Exception as e:
        return to_unified_format_func({
            "success": False,
            "error": str(e),
            "operation_id": None
        }, "file_checksum")


def _calculate_hash_for_multiple_files(
    file_paths: List[str],
    algorithm: str = "md5",
    chunk_size: int = 65536
) -> Dict[str, Any]:
    """
    批量计算多个文件的哈希值
    
    Args:
        file_paths: 文件路径列表
        algorithm: 哈希算法
        chunk_size: 分块大小
    
    Returns:
        批量哈希计算结果
    """
    results = []
    total_size = 0
    total_time = 0
    
    for file_path in file_paths:
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            results.append({
                "file_path": str(path),
                "success": False,
                "error": "文件不存在或不是文件",
                "checksum": None,
                "file_size": 0,
                "elapsed_time": 0
            })
            continue
        
        try:
            start_time = time.time()
            file_size = path.stat().st_size
            total_size += file_size
            
            # 选择哈希算法
            algorithm_lower = algorithm.lower()
            if algorithm_lower == "md5":
                hash_obj = hashlib.md5()
            elif algorithm_lower == "sha1":
                hash_obj = hashlib.sha1()
            elif algorithm_lower == "sha256":
                hash_obj = hashlib.sha256()
            elif algorithm_lower == "sha512":
                hash_obj = hashlib.sha512()
            else:
                raise ValueError(f"不支持的哈希算法: {algorithm}")
            
            # 计算哈希值
            with open(path, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    hash_obj.update(chunk)
            
            checksum = hash_obj.hexdigest()
            elapsed_time = time.time() - start_time
            total_time += elapsed_time
            
            results.append({
                "file_path": str(path),
                "success": True,
                "checksum": checksum,
                "file_size": file_size,
                "elapsed_time": elapsed_time,
                "algorithm": algorithm
            })
            
        except Exception as e:
            results.append({
                "file_path": str(path),
                "success": False,
                "error": str(e),
                "checksum": None,
                "file_size": 0,
                "elapsed_time": 0
            })
    
    return {
        "files": results,
        "total_files": len(file_paths),
        "successful_files": sum(1 for r in results if r["success"]),
        "failed_files": sum(1 for r in results if not r["success"]),
        "total_size": total_size,
        "total_time": total_time,
        "algorithm": algorithm,
        "chunk_size": chunk_size
    }
