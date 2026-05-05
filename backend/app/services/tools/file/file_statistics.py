# -*- coding: utf-8 -*-
"""
file_statistics - 统计文件信息

功能：
- 统计目录中的文件数量、大小、类型等信息
- 支持递归统计子目录
- 支持按文件类型、大小、修改时间过滤
- 支持多种输出格式（JSON、CSV、文本）

Author: 小健 - 2026-04-19
"""

import asyncio
import json
import csv
import io
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta


async def file_statistics_impl(
    directory: str,
    recursive: bool = True,
    max_depth: int = 100000,
    filters: Optional[Dict[str, Any]] = None,
    output_format: str = "json",
    validate_path_func=None,
    safety_service=None,
    task_id: Optional[str] = None,
    record_operation_func=None,
    execute_with_safety_func=None,
    to_unified_format_func=None,
    get_next_sequence_func=None,
) -> Dict[str, Any]:
    """
    file_statistics工具的实现函数
    
    Args:
        directory: 统计目录路径
        recursive: 是否递归统计子目录
        max_depth: 最大递归深度
        filters: 过滤条件字典
        output_format: 输出格式：json、csv、text
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
    is_valid, error_msg = validate_path_func(directory)
    if not is_valid:
        return to_unified_format_func({
            "success": False,
            "error": f"目录路径验证失败: {error_msg}",
            "operation_id": None
        }, "file_statistics")
    
    if not task_id:
        return to_unified_format_func({
            "success": False,
            "error": "No active task",
            "operation_id": None
        }, "file_statistics")
    
    # 验证输出格式
    if output_format not in ["json", "csv", "text"]:
        return to_unified_format_func({
            "success": False,
            "error": f"不支持的输出格式: {output_format}，支持格式: json, csv, text",
            "operation_id": None
        }, "file_statistics")
    
    dir_path = Path(directory)
    
    try:
        # 检查目录是否存在
        if not dir_path.exists():
            return to_unified_format_func({
                "success": False,
                "error": f"目录不存在: {directory}",
                "operation_id": None
            }, "file_statistics")
        
        if not dir_path.is_dir():
            return to_unified_format_func({
                "success": False,
                "error": f"路径不是目录: {directory}",
                "operation_id": None
            }, "file_statistics")
        
        # 记录操作
        operation_id = record_operation_func(
            task_id=task_id,
            operation_type=OperationType.STATISTICS,
            source_path=dir_path,
            destination_path=None,
            sequence_number=get_next_sequence_func()
        )
        
        # 定义统计操作
        def _statistics_sync():
            import time
            start_time = time.time()
            
            # 收集文件统计信息
            stats = {
                "directory": str(dir_path),
                "total_files": 0,
                "total_directories": 0,
                "total_size": 0,
                "file_types": {},
                "size_distribution": {
                    "0-1KB": 0,
                    "1KB-1MB": 0,
                    "1MB-10MB": 0,
                    "10MB-100MB": 0,
                    "100MB-1GB": 0,
                    "1GB+": 0
                },
                "modification_time_distribution": {
                    "today": 0,
                    "this_week": 0,
                    "this_month": 0,
                    "this_year": 0,
                    "older": 0
                },
                "depth_distribution": {},
                "files": [],
                "scan_time": 0
            }
            
            # 遍历目录
            def _scan_directory(current_path: Path, current_depth: int):
                if current_depth > max_depth:
                    return
                
                try:
                    for item in current_path.iterdir():
                        try:
                            # 检查过滤条件
                            if not _apply_filters(item, filters):
                                continue
                            
                            if item.is_file():
                                # 文件统计
                                stat = item.stat()
                                file_size = stat.st_size
                                mtime = stat.st_mtime
                                
                                stats["total_files"] += 1
                                stats["total_size"] += file_size
                                
                                # 文件类型统计
                                ext = item.suffix.lower()
                                if ext:
                                    stats["file_types"][ext] = stats["file_types"].get(ext, 0) + 1
                                else:
                                    stats["file_types"]["no_extension"] = stats["file_types"].get("no_extension", 0) + 1
                                
                                # 大小分布统计
                                if file_size < 1024:  # < 1KB
                                    stats["size_distribution"]["0-1KB"] += 1
                                elif file_size < 1024 * 1024:  # < 1MB
                                    stats["size_distribution"]["1KB-1MB"] += 1
                                elif file_size < 10 * 1024 * 1024:  # < 10MB
                                    stats["size_distribution"]["1MB-10MB"] += 1
                                elif file_size < 100 * 1024 * 1024:  # < 100MB
                                    stats["size_distribution"]["10MB-100MB"] += 1
                                elif file_size < 1024 * 1024 * 1024:  # < 1GB
                                    stats["size_distribution"]["100MB-1GB"] += 1
                                else:  # >= 1GB
                                    stats["size_distribution"]["1GB+"] += 1
                                
                                # 修改时间分布统计
                                now = time.time()
                                time_diff = now - mtime
                                
                                if time_diff < 24 * 60 * 60:  # 今天
                                    stats["modification_time_distribution"]["today"] += 1
                                elif time_diff < 7 * 24 * 60 * 60:  # 本周
                                    stats["modification_time_distribution"]["this_week"] += 1
                                elif time_diff < 30 * 24 * 60 * 60:  # 本月
                                    stats["modification_time_distribution"]["this_month"] += 1
                                elif time_diff < 365 * 24 * 60 * 60:  # 今年
                                    stats["modification_time_distribution"]["this_year"] += 1
                                else:  # 更早
                                    stats["modification_time_distribution"]["older"] += 1
                                
                                # 深度分布统计
                                depth_key = f"depth_{current_depth}"
                                stats["depth_distribution"][depth_key] = stats["depth_distribution"].get(depth_key, 0) + 1
                                
                                # 文件详细信息（限制数量避免内存过大）
                                if len(stats["files"]) < 1000:  # 最多记录1000个文件
                                    stats["files"].append({
                                        "path": str(item),
                                        "name": item.name,
                                        "size": file_size,
                                        "extension": ext if ext else "",
                                        "modified_time": mtime,
                                        "depth": current_depth
                                    })
                                
                            elif item.is_dir():
                                # 目录统计
                                stats["total_directories"] += 1
                                
                                # 递归扫描子目录
                                if recursive:
                                    _scan_directory(item, current_depth + 1)
                                    
                        except (PermissionError, OSError):
                            # 跳过无法访问的文件/目录
                            continue
                            
                except (PermissionError, OSError):
                    # 跳过无法访问的目录
                    pass
            
            # 开始扫描
            _scan_directory(dir_path, 0)
            
            # 计算平均文件大小
            if stats["total_files"] > 0:
                stats["average_file_size"] = stats["total_size"] / stats["total_files"]
            else:
                stats["average_file_size"] = 0
            
            # 计算扫描时间
            stats["scan_time"] = time.time() - start_time
            
            # 按文件类型排序
            stats["file_types"] = dict(sorted(
                stats["file_types"].items(),
                key=lambda x: x[1],
                reverse=True
            ))
            
            # 格式化输出
            if output_format == "json":
                stats["output"] = json.dumps(stats, indent=2, ensure_ascii=False)
            elif output_format == "csv":
                # 生成CSV格式
                output = io.StringIO()
                writer = csv.writer(output)
                
                # 写入基本信息
                writer.writerow(["统计项", "值"])
                writer.writerow(["目录", stats["directory"]])
                writer.writerow(["总文件数", stats["total_files"]])
                writer.writerow(["总目录数", stats["total_directories"]])
                writer.writerow(["总大小(字节)", stats["total_size"]])
                writer.writerow(["平均文件大小(字节)", stats["average_file_size"]])
                writer.writerow(["扫描时间(秒)", stats["scan_time"]])
                writer.writerow([])
                
                # 写入文件类型分布
                writer.writerow(["文件类型分布"])
                writer.writerow(["文件类型", "数量"])
                for ext, count in stats["file_types"].items():
                    writer.writerow([ext, count])
                writer.writerow([])
                
                # 写入大小分布
                writer.writerow(["大小分布"])
                writer.writerow(["大小范围", "数量"])
                for size_range, count in stats["size_distribution"].items():
                    writer.writerow([size_range, count])
                writer.writerow([])
                
                # 写入修改时间分布
                writer.writerow(["修改时间分布"])
                writer.writerow(["时间范围", "数量"])
                for time_range, count in stats["modification_time_distribution"].items():
                    writer.writerow([time_range, count])
                
                stats["output"] = output.getvalue()
                
            elif output_format == "text":
                # 生成文本格式
                lines = []
                lines.append(f"目录统计: {stats['directory']}")
                lines.append(f"总文件数: {stats['total_files']}")
                lines.append(f"总目录数: {stats['total_directories']}")
                lines.append(f"总大小: {stats['total_size']:,} 字节")
                lines.append(f"平均文件大小: {stats['average_file_size']:,.2f} 字节")
                lines.append(f"扫描时间: {stats['scan_time']:.2f} 秒")
                lines.append("")
                
                lines.append("文件类型分布:")
                for ext, count in stats["file_types"].items():
                    lines.append(f"  {ext}: {count}")
                lines.append("")
                
                lines.append("大小分布:")
                for size_range, count in stats["size_distribution"].items():
                    lines.append(f"  {size_range}: {count}")
                lines.append("")
                
                lines.append("修改时间分布:")
                for time_range, count in stats["modification_time_distribution"].items():
                    lines.append(f"  {time_range}: {count}")
                lines.append("")
                
                lines.append("深度分布:")
                for depth, count in sorted(stats["depth_distribution"].items()):
                    lines.append(f"  {depth}: {count}")
                
                stats["output"] = "\n".join(lines)
            
            return stats
        
        # 执行统计操作
        result = await asyncio.to_thread(
            execute_with_safety_func,
            operation_id=operation_id,
            operation_func=_statistics_sync
        )
        
        if result:
            return to_unified_format_func({
                "success": True,
                "operation_id": operation_id,
                **result
            }, "file_statistics")
        else:
            return to_unified_format_func({
                "success": False,
                "error": "文件统计失败",
                "operation_id": operation_id
            }, "file_statistics")
            
    except Exception as e:
        return to_unified_format_func({
            "success": False,
            "error": str(e),
            "operation_id": None
        }, "file_statistics")


def _apply_filters(path: Path, filters: Optional[Dict[str, Any]]) -> bool:
    """
    应用过滤条件
    
    Args:
        path: 文件路径
        filters: 过滤条件字典
    
    Returns:
        是否通过过滤
    """
    if not filters:
        return True
    
    # 文件类型过滤
    if "file_type" in filters:
        file_type = filters["file_type"]
        if not path.suffix.lower().endswith(file_type.lower()):
            return False
    
    # 只处理文件（目录总是通过）
    if path.is_file():
        try:
            stat = path.stat()
            
            # 文件大小过滤
            if "min_size" in filters and stat.st_size < filters["min_size"]:
                return False
            if "max_size" in filters and stat.st_size > filters["max_size"]:
                return False
            
            # 修改时间过滤
            if "modified_after" in filters:
                modified_after = filters["modified_after"]
                if isinstance(modified_after, (int, float)):
                    # 时间戳
                    if stat.st_mtime < modified_after:
                        return False
                elif isinstance(modified_after, str):
                    # 日期字符串，尝试解析
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(modified_after.replace('Z', '+00:00'))
                        if stat.st_mtime < dt.timestamp():
                            return False
                    except (ValueError, TypeError):
                        pass
            
            if "modified_before" in filters:
                modified_before = filters["modified_before"]
                if isinstance(modified_before, (int, float)):
                    # 时间戳
                    if stat.st_mtime > modified_before:
                        return False
                elif isinstance(modified_before, str):
                    # 日期字符串，尝试解析
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(modified_before.replace('Z', '+00:00'))
                        if stat.st_mtime > dt.timestamp():
                            return False
                    except (ValueError, TypeError):
                        pass
        
        except (OSError, PermissionError):
            # 无法获取文件信息，跳过
            return False
    
    return True
