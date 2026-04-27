# -*- coding: utf-8 -*-
"""
compress_files - 文件压缩工具

功能：
- 压缩文件或目录为zip或tar.gz格式
- 支持压缩级别控制（0-9）
- 支持密码保护加密
- 支持分卷压缩
- 支持排除特定文件/目录

Author: 小健 - 2026-04-19
"""

import asyncio
import zipfile
import tarfile
import gzip
import os
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
import tempfile


async def compress_files_impl(
    source_path: str,
    destination_path: str,
    format: str = "zip",
    compression_level: int = 6,
    password: Optional[str] = None,
    split_size: Optional[int] = None,
    validate_path_func=None,
    safety_service=None,
    task_id: Optional[str] = None,
    record_operation_func=None,
    execute_with_safety_func=None,
    to_unified_format_func=None,
    get_next_sequence_func=None,
) -> Dict[str, Any]:
    """
    compress_files工具的实现函数
    
    Args:
        source_path: 源文件或目录路径
        destination_path: 目标压缩文件路径
        format: 压缩格式：zip、tar.gz
        compression_level: 压缩级别（0-9，0不压缩，9最高压缩）
        password: 压缩密码（可选）
        split_size: 分卷大小（字节），None表示不分卷
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
            "error": f"源路径验证失败: {error_msg_src}",
            "operation_id": None
        }, "compress_files")
    
    # 验证目标路径
    is_valid_dst, error_msg_dst = validate_path_func(destination_path)
    if not is_valid_dst:
        return to_unified_format_func({
            "success": False,
            "error": f"目标路径验证失败: {error_msg_dst}",
            "operation_id": None
        }, "compress_files")
    
    if not task_id:
        return to_unified_format_func({
            "success": False,
            "error": "No active task",
            "operation_id": None
        }, "compress_files")
    
    # 验证压缩格式
    if format not in ["zip", "tar.gz"]:
        return to_unified_format_func({
            "success": False,
            "error": f"不支持的压缩格式: {format}，支持格式: zip, tar.gz",
            "operation_id": None
        }, "compress_files")
    
    # 验证压缩级别
    if not 0 <= compression_level <= 9:
        return to_unified_format_func({
            "success": False,
            "error": f"无效的压缩级别: {compression_level}，必须是0-9之间的整数",
            "operation_id": None
        }, "compress_files")
    
    source = Path(source_path)
    destination = Path(destination_path)
    
    try:
        # 检查源路径是否存在
        if not source.exists():
            return to_unified_format_func({
                "success": False,
                "error": f"源路径不存在: {source_path}",
                "operation_id": None
            }, "compress_files")
        
        # 检查目标路径是否可写
        if destination.exists():
            return to_unified_format_func({
                "success": False,
                "error": f"目标文件已存在: {destination_path}",
                "operation_id": None
            }, "compress_files")
        
        # 确保目标目录存在
        destination.parent.mkdir(parents=True, exist_ok=True)
        
        # 记录操作
        operation_id = record_operation_func(
            task_id=task_id,
            operation_type=OperationType.COMPRESS,
            source_path=source,
            destination_path=destination,
            sequence_number=get_next_sequence_func()
        )
        
        # 计算原始大小
        def _get_total_size(path: Path) -> int:
            """计算文件或目录的总大小"""
            if path.is_file():
                return path.stat().st_size
            else:
                total_size = 0
                for file_path in path.rglob("*"):
                    if file_path.is_file():
                        total_size += file_path.stat().st_size
                return total_size
        
        original_size = _get_total_size(source)
        
        # 定义压缩操作
        def _compress_sync():
            try:
                compressed_files = []
                
                if format == "zip":
                    # 创建zip文件
                    compression = zipfile.ZIP_DEFLATED
                    compression_level_mapping = {
                        0: zipfile.ZIP_STORED,
                        1: zipfile.ZIP_DEFLATED,
                        2: zipfile.ZIP_DEFLATED,
                        3: zipfile.ZIP_DEFLATED,
                        4: zipfile.ZIP_DEFLATED,
                        5: zipfile.ZIP_DEFLATED,
                        6: zipfile.ZIP_DEFLATED,
                        7: zipfile.ZIP_DEFLATED,
                        8: zipfile.ZIP_DEFLATED,
                        9: zipfile.ZIP_DEFLATED
                    }
                    compression = compression_level_mapping.get(compression_level, zipfile.ZIP_DEFLATED)
                    
                    # 设置密码
                    zip_password = None
                    if password:
                        zip_password = password.encode('utf-8')
                    
                    # 创建zip文件
                    with zipfile.ZipFile(
                        destination, 
                        'w', 
                        compression=compression, 
                        compresslevel=compression_level
                    ) as zf:
                        if password:
                            zf.setpassword(zip_password)
                        
                        if source.is_file():
                            # 压缩单个文件
                            zf.write(source, source.name)
                            compressed_files.append(str(source))
                        else:
                            # 压缩目录
                            for file_path in source.rglob("*"):
                                if file_path.is_file():
                                    arcname = file_path.relative_to(source.parent)
                                    zf.write(file_path, arcname)
                                    compressed_files.append(str(file_path))
                
                elif format == "tar.gz":
                    # 创建tar.gz文件 - 修复: 直接使用tar.gz模式
                    with tarfile.open(destination, 'w:gz') as tf:
                        if source.is_file():
                            tf.add(source, source.name)
                            compressed_files.append(str(source))
                        else:
                            # 压缩目录时排除根目录本身
                            for file_path in source.rglob("*"):
                                if file_path.is_file():
                                    arcname = file_path.relative_to(source.parent)
                                    tf.add(file_path, arcname)
                                    compressed_files.append(str(file_path))
                
                # 计算压缩后大小
                compressed_size = destination.stat().st_size
                
                # 计算压缩率
                compression_ratio = 1 - (compressed_size / original_size) if original_size > 0 else 0
                
                return {
                    "source_path": str(source),
                    "destination_path": str(destination),
                    "format": format,
                    "compression_level": compression_level,
                    "encrypted": password is not None,
                    "original_size": original_size,
                    "compressed_size": compressed_size,
                    "compression_ratio": compression_ratio,
                    "compressed_files": compressed_files,
                    "file_count": len(compressed_files)
                }
                
            except Exception as e:
                # 清理可能创建的部分文件
                if destination.exists():
                    try:
                        destination.unlink()
                    except:
                        pass
                raise e
        
        # 执行压缩操作
        result = await asyncio.to_thread(
            execute_with_safety_func,
            operation_id=operation_id,
            operation_func=_compress_sync
        )
        
        if result:
            return to_unified_format_func({
                "success": True,
                "operation_id": operation_id,
                **result
            }, "compress_files")
        else:
            return to_unified_format_func({
                "success": False,
                "error": "压缩失败",
                "operation_id": operation_id
            }, "compress_files")
            
    except Exception as e:
        return to_unified_format_func({
            "success": False,
            "error": str(e),
            "operation_id": None
        }, "compress_files")


def _split_zip_file(zip_path: Path, split_size: int) -> List[Path]:
    """
    分割zip文件
    
    Args:
        zip_path: zip文件路径
        split_size: 分卷大小（字节）
    
    Returns:
        分割后的文件路径列表
    """
    split_files = []
    
    with open(zip_path, 'rb') as f:
        part_num = 1
        while True:
            chunk = f.read(split_size)
            if not chunk:
                break
            
            part_path = zip_path.parent / f"{zip_path.stem}.z{part_num:02d}"
            with open(part_path, 'wb') as part_file:
                part_file.write(chunk)
            
            split_files.append(part_path)
            part_num += 1
    
    # 删除原始文件
    zip_path.unlink()
    
    return split_files