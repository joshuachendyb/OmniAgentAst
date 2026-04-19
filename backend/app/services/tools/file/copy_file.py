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
from typing import Dict, Any

from app.services.tools.file.file_tools import (
    register_tool,
    _to_unified_format,
    OperationType,
)


class CopyFileInput:
    """copy_file工具的输入参数Schema"""
    
    def __init__(self):
        from pydantic import BaseModel, Field
        from typing import Optional
        
        class _CopyFileInput(BaseModel):
            source_path: str = Field(
                description="源文件或目录的完整路径（必须是绝对路径）"
            )
            destination_path: str = Field(
                description="目标路径（可以是新文件名或新目录位置）"
            )
            recursive: bool = Field(
                default=False,
                description="是否递归复制目录，仅当源路径是目录时有效，默认为False"
            )
            overwrite: bool = Field(
                default=False,
                description="是否覆盖已存在的目标文件，默认为False（不覆盖）"
            )
        
        self.schema = _CopyFileInput


@register_tool(
    name="copy_file",
    description="""复制文件或目录到新位置。

使用场景：
- 当用户想要复制文件时使用此工具
- 当用户想要备份文件时使用
- 当用户说"复制文件"、"拷贝文件"、"备份文件"时使用

参数说明：
- source_path: 源文件或目录的完整路径（必须是绝对路径）
- destination_path: 目标路径（可以是新文件名或新目录位置）
- recursive: 是否递归复制目录，仅当源路径是目录时有效，默认为False
- overwrite: 是否覆盖已存在的目标文件，默认为False

【重要】必须使用 source_path 和 destination_path 作为参数名。
正确示例: {"source_path": "C:/Users/file.txt", "destination_path": "D:/backup/file.txt"}""",
    input_model=CopyFileInput().schema,
    examples=[
        {
            "source_path": "C:/Users/用户名/Documents/file.txt",
            "destination_path": "D:/backup/file.txt"
        },
        {
            "source_path": "C:/Users/用户名/Documents/folder",
            "destination_path": "D:/backup/folder",
            "recursive": True
        }
    ]
)
async def copy_file(
    self,
    source_path: str,
    destination_path: str,
    recursive: bool = False,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """复制文件或目录"""
    # 验证源路径
    is_valid_src, error_msg_src = self._validate_path(source_path)
    if not is_valid_src:
        return _to_unified_format({
            "success": False,
            "error": f"源路径{error_msg_src}",
            "operation_id": None
        }, "copy_file")
    
    # 验证目标路径
    is_valid_dst, error_msg_dst = self._validate_path(destination_path)
    if not is_valid_dst:
        return _to_unified_format({
            "success": False,
            "error": f"目标路径{error_msg_dst}",
            "operation_id": None
        }, "copy_file")
    
    if not self.session_id:
        return _to_unified_format({
            "success": False,
            "error": "No active session",
            "operation_id": None
        }, "copy_file")
    
    src = Path(source_path)
    dst = Path(destination_path)
    
    try:
        if not src.exists():
            return _to_unified_format({
                "success": False,
                "error": f"Source not found: {source_path}",
                "operation_id": None
            }, "copy_file")
        
        # 检查目标是否已存在
        if dst.exists() and not overwrite:
            return _to_unified_format({
                "success": False,
                "error": f"目标路径已存在: {dst}，复制操作已取消。请设置overwrite=True或指定其他路径。",
                "operation_id": None
            }, "copy_file")
        
        # 记录操作
        operation_id = self.safety.record_operation(
            session_id=self.session_id,
            operation_type=OperationType.COPY,
            source_path=src,
            destination_path=dst,
            sequence_number=self._get_next_sequence()
        )
        
        # 定义复制操作
        def _copy_sync():
            # 确保目标父目录存在
            dst.parent.mkdir(parents=True, exist_ok=True)
            
            if src.is_file():
                # 复制文件
                shutil.copy2(str(src), str(dst))
            elif src.is_dir():
                if recursive:
                    # 递归复制目录
                    if dst.exists():
                        shutil.rmtree(str(dst))
                    shutil.copytree(str(src), str(dst))
                else:
                    # 非递归复制目录（只复制目录本身，不复制内容）
                    dst.mkdir(exist_ok=True)
            return True
        
        success = await asyncio.to_thread(
            self.safety.execute_with_safety,
            operation_id=operation_id,
            operation_func=_copy_sync
        )
        
        if success:
            return _to_unified_format({
                "success": True,
                "operation_id": operation_id,
                "source": str(src),
                "destination": str(dst),
                "message": f"Copied: {src.name} -> {dst}"
            }, "copy_file")
        else:
            return _to_unified_format({
                "success": False,
                "error": "Failed to copy file",
                "operation_id": operation_id
            }, "copy_file")
            
    except Exception as e:
        return _to_unified_format({
            "success": False,
            "error": str(e),
            "operation_id": None
        }, "copy_file")