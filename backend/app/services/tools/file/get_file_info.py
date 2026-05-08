# -*- coding: utf-8 -*-
"""
get_file_info - 文件信息获取工具

功能：
- 获取文件元数据
- 获取文件大小、修改时间、权限等
- 检查文件是否存在

Author: 小健 - 2026-04-19
"""

import asyncio
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


async def get_file_info_impl(
    file_path: str,
    validate_path_func,
    to_unified_format_func,
    follow_symlinks: bool = True,
) -> Dict[str, Any]:
    """获取文件信息 - 小健 2026-05-02 增加follow_symlinks"""
    is_valid, error_msg = validate_path_func(file_path)
    if not is_valid:
        return to_unified_format_func({
            "success": False,
            "error": error_msg
        }, "get_file_info")
    
    path = Path(file_path)
    
    try:
        if not path.exists():
            return to_unified_format_func({
                "success": False,
                "error": f"File not found: {file_path}"
            }, "get_file_info")
        
        def _get_info_sync():
            stat = path.stat(follow_symlinks=follow_symlinks)
            info = {
                "path": str(path.absolute()),
                "name": path.name,
                "type": "directory" if path.is_dir() else "file",
                "size": stat.st_size,
                "created_time": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "accessed_time": datetime.fromtimestamp(stat.st_atime).isoformat(),
                "is_readable": os.access(path, os.R_OK),
                "is_writable": os.access(path, os.W_OK),
                "is_executable": os.access(path, os.X_OK),
            }
            
            if not follow_symlinks and path.is_symlink():
                info["is_symlink"] = True
                try:
                    info["symlink_target"] = str(os.readlink(path))
                except OSError:
                    info["symlink_target"] = None
            else:
                info["is_symlink"] = path.is_symlink()
            
            if path.is_file():
                info["extension"] = path.suffix
                info["parent_directory"] = str(path.parent)
            elif path.is_dir():
                try:
                    file_count = sum(1 for _ in path.rglob("*") if _.is_file())
                    dir_count = sum(1 for _ in path.rglob("*") if _.is_dir())
                    info["file_count"] = file_count
                    info["dir_count"] = dir_count
                except (OSError, PermissionError):
                    info["file_count"] = None
                    info["dir_count"] = None
            
            return info
        
        info = await asyncio.to_thread(_get_info_sync)
        
        return to_unified_format_func({
            "success": True,
            "info": info
        }, "get_file_info")
        
    except Exception as e:
        return to_unified_format_func({
            "success": False,
            "error": str(e)
        }, "get_file_info")
