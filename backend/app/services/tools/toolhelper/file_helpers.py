# -*- coding: utf-8 -*-
"""
文件辅助函数模块 - 纯内部辅助函数（不暴露给LLM）

【创建时间】2026-05-02 小沈
【更新时间】2026-05-02 小沈

================================================================================
一、模块性质（纯内部辅助函数）
================================================================================
本模块的函数 **仅作为内部辅助函数**，具有以下特点：

1. **不注册到tool_registry** - 无@register_tool装饰器
2. **不暴露给LLM** - LLM无法直接调用这些函数
3. **仅供其他Tool函数内部调用** - 作为公共基础设施

【对比db_helper/】
- db_helper/: 双重身份（公共函数 + LLM可调用Tool），有@register_tool
- toolhelper/: 纯内部辅助函数，无@register_tool，不暴露给LLM

================================================================================
二、包含函数（10个）
================================================================================
- extract_archive: 解压文件（zip/tar/tar.gz/tar.bz2）
- get_file_hash: 计算文件哈希（MD5/SHA1/SHA256）
- ensure_directory_exists: 确保目录存在
- check_write_permission: 检查写权限
- check_read_permission: 检查读权限
- get_file_encoding: 检测文件编码
- get_mime_type: 获取MIME类型
- backup_file: 备份文件
- move_to_trash: 移动到回收站
- validate_command: 验证命令安全性
- check_shell_running: 检查Shell是否运行

================================================================================
三、调用关系示例
================================================================================
```
# 其他Tool内部调用示例
def write_file(file_path, content):
    # 内部调用公共辅助函数
    if not check_write_permission(file_path):
        return {"error": "无写权限"}
    backup_file(file_path)  # 先备份
    # 执行写入...

# LLM无法直接调用这些函数
用户: "帮我检测文件编码"
LLM: 无法调用get_file_encoding，需调用read_file等Tool
```

Author: 小沈 - 2026-05-02
"""

import os
import re
import shutil
import zipfile
import tarfile
import hashlib
import mimetypes
import subprocess
import asyncio
import json
import csv
import io
import time
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, List
import logging

logger = logging.getLogger(__name__)


def _is_safe_path(output_dir: str, member_path: str) -> bool:
    """检查解压成员路径是否在output_dir内，防止路径遍历攻击 - 小沈 2026-05-05"""
    target = os.path.normpath(os.path.join(output_dir, member_path))
    return target.startswith(os.path.normpath(output_dir) + os.sep) or target == os.path.normpath(output_dir)


def extract_archive(
    archive_path: str,
    output_dir: Optional[str] = None,
    overwrite: bool = False,
    password: Optional[str] = None,
    preserve_permissions: bool = True,
) -> Dict[str, Any]:
    """
    解压压缩文件 - 小沈 2026-05-02
    
    支持 zip、tar、tar.gz、tar.bz2 格式
    """
    try:
        archive_path = os.path.abspath(archive_path)
        
        if not os.path.exists(archive_path):
            return {"success": False, "error": f"压缩文件不存在: {archive_path}"}
        
        if output_dir is None:
            base_name = os.path.basename(archive_path)
            for ext in ['.zip', '.tar.gz', '.tar.bz2', '.tar', '.gz', '.bz2']:
                if base_name.lower().endswith(ext):
                    base_name = base_name[:-len(ext)]
                    break
            output_dir = os.path.join(os.path.dirname(archive_path), base_name)
        
        output_dir = os.path.abspath(output_dir)
        os.makedirs(output_dir, exist_ok=True)
        
        lower_path = archive_path.lower()
        
        if lower_path.endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as zf:
                if password:
                    zf.setpassword(password.encode('utf-8'))
                
                members = zf.namelist()
                extracted = []
                skipped = []
                
                for member in members:
                    if not _is_safe_path(output_dir, member):
                        logger.warning(f"跳过路径遍历成员: {member}")
                        skipped.append(member)
                        continue
                    
                    target_path = os.path.join(output_dir, member)
                    
                    if not overwrite and os.path.exists(target_path):
                        skipped.append(member)
                        continue
                    
                    zf.extract(member, output_dir)
                    extracted.append(member)
                
                return {
                    "success": True,
                    "output_dir": output_dir,
                    "extracted_files": len(extracted),
                    "skipped_files": len(skipped),
                    "format": "zip"
                }
        
        elif lower_path.endswith('.tar.gz') or lower_path.endswith('.tgz'):
            with tarfile.open(archive_path, 'r:gz') as tf:
                members = tf.getmembers()
                extracted = []
                skipped = []
                
                for member in members:
                    if not _is_safe_path(output_dir, member.name):
                        logger.warning(f"跳过路径遍历成员: {member.name}")
                        skipped.append(member.name)
                        continue
                    
                    target_path = os.path.join(output_dir, member.name)
                    
                    if not overwrite and os.path.exists(target_path):
                        skipped.append(member.name)
                        continue
                    
                    tf.extract(member, output_dir)
                    
                    if preserve_permissions:
                        try:
                            os.chmod(target_path, member.mode)
                        except Exception as e:
                            logger.warning(f"设置权限失败: {e}")
                    
                    extracted.append(member.name)
                
                return {
                    "success": True,
                    "output_dir": output_dir,
                    "extracted_files": len(extracted),
                    "skipped_files": len(skipped),
                    "format": "tar.gz"
                }
        
        elif lower_path.endswith('.tar.bz2') or lower_path.endswith('.tbz2'):
            with tarfile.open(archive_path, 'r:bz2') as tf:
                members = tf.getmembers()
                extracted = []
                skipped = []
                
                for member in members:
                    if not _is_safe_path(output_dir, member.name):
                        logger.warning(f"跳过路径遍历成员: {member.name}")
                        skipped.append(member.name)
                        continue
                    
                    target_path = os.path.join(output_dir, member.name)
                    
                    if not overwrite and os.path.exists(target_path):
                        skipped.append(member.name)
                        continue
                    
                    tf.extract(member, output_dir)
                    
                    if preserve_permissions:
                        try:
                            os.chmod(target_path, member.mode)
                        except Exception as e:
                            logger.warning(f"设置权限失败: {e}")
                    
                    extracted.append(member.name)
                
                return {
                    "success": True,
                    "output_dir": output_dir,
                    "extracted_files": len(extracted),
                    "skipped_files": len(skipped),
                    "format": "tar.bz2"
                }
        
        elif lower_path.endswith('.tar'):
            with tarfile.open(archive_path, 'r') as tf:
                members = tf.getmembers()
                extracted = []
                skipped = []
                
                for member in members:
                    if not _is_safe_path(output_dir, member.name):
                        logger.warning(f"跳过路径遍历成员: {member.name}")
                        skipped.append(member.name)
                        continue
                    
                    target_path = os.path.join(output_dir, member.name)
                    
                    if not overwrite and os.path.exists(target_path):
                        skipped.append(member.name)
                        continue
                    
                    tf.extract(member, output_dir)
                    
                    if preserve_permissions:
                        try:
                            os.chmod(target_path, member.mode)
                        except Exception as e:
                            logger.warning(f"设置权限失败: {e}")
                    
                    extracted.append(member.name)
                
                return {
                    "success": True,
                    "output_dir": output_dir,
                    "extracted_files": len(extracted),
                    "skipped_files": len(skipped),
                    "format": "tar"
                }
        
        else:
            return {"success": False, "error": f"不支持的压缩格式: {archive_path}"}
    
    except zipfile.BadZipFile:
        return {"success": False, "error": "无效的ZIP文件或密码错误"}
    except tarfile.TarError as e:
        return {"success": False, "error": f"TAR文件错误: {str(e)}"}
    except Exception as e:
        logger.error(f"[extract_archive] 解压失败: {e}")
        return {"success": False, "error": str(e)}


def get_file_hash(
    file_path: str,
    algorithm: str = "sha256",
) -> Dict[str, Any]:
    """
    计算文件哈希值 - 小沈 2026-05-02
    
    支持 md5、sha1、sha256、sha512
    """
    try:
        file_path = os.path.abspath(file_path)
        
        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}
        
        if not os.path.isfile(file_path):
            return {"success": False, "error": f"不是文件: {file_path}"}
        
        algorithm = algorithm.lower()
        
        if algorithm == "md5":
            hasher = hashlib.md5()
        elif algorithm == "sha1":
            hasher = hashlib.sha1()
        elif algorithm == "sha256":
            hasher = hashlib.sha256()
        elif algorithm == "sha512":
            hasher = hashlib.sha512()
        else:
            return {"success": False, "error": f"不支持的算法: {algorithm}"}
        
        chunk_size = 65536
        file_size = os.path.getsize(file_path)
        
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
        
        return {
            "success": True,
            "file_path": file_path,
            "algorithm": algorithm,
            "hash": hasher.hexdigest(),
            "file_size": file_size
        }
    
    except Exception as e:
        logger.error(f"[get_file_hash] 计算哈希失败: {e}")
        return {"success": False, "error": str(e)}


def ensure_directory_exists(dir_path: str) -> Dict[str, Any]:
    """
    确保目录存在，不存在则创建 - 小沈 2026-05-02
    """
    try:
        dir_path = os.path.abspath(dir_path)
        
        if os.path.exists(dir_path):
            if os.path.isdir(dir_path):
                return {"success": True, "path": dir_path, "created": False}
            else:
                return {"success": False, "error": f"路径存在但不是目录: {dir_path}"}
        
        os.makedirs(dir_path, exist_ok=True)
        
        return {"success": True, "path": dir_path, "created": True}
    
    except Exception as e:
        logger.error(f"[ensure_directory_exists] 创建目录失败: {e}")
        return {"success": False, "error": str(e)}


def check_write_permission(path: str) -> Dict[str, Any]:
    """
    检查写权限 - 小沈 2026-05-02
    """
    try:
        path = os.path.abspath(path)
        
        if os.path.isfile(path):
            writable = os.access(path, os.W_OK)
            return {"success": True, "path": path, "writable": writable, "type": "file"}
        
        elif os.path.isdir(path):
            writable = os.access(path, os.W_OK)
            return {"success": True, "path": path, "writable": writable, "type": "directory"}
        
        else:
            parent = os.path.dirname(path)
            if parent and os.path.exists(parent):
                writable = os.access(parent, os.W_OK)
                return {"success": True, "path": path, "writable": writable, "type": "new_file"}
            else:
                return {"success": True, "path": path, "writable": False, "type": "new_file"}
    
    except Exception as e:
        logger.error(f"[check_write_permission] 检查权限失败: {e}")
        return {"success": False, "error": str(e)}


def check_read_permission(path: str) -> Dict[str, Any]:
    """
    检查读权限 - 小沈 2026-05-02
    """
    try:
        path = os.path.abspath(path)
        
        if not os.path.exists(path):
            return {"success": True, "path": path, "readable": False, "exists": False}
        
        readable = os.access(path, os.R_OK)
        path_type = "file" if os.path.isfile(path) else "directory"
        
        return {"success": True, "path": path, "readable": readable, "exists": True, "type": path_type}
    
    except Exception as e:
        logger.error(f"[check_read_permission] 检查权限失败: {e}")
        return {"success": False, "error": str(e)}


def get_file_encoding(file_path: str) -> Dict[str, Any]:
    """
    检测文件编码 - 小沈 2026-05-02
    """
    try:
        file_path = os.path.abspath(file_path)
        
        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}
        
        common_encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'big5', 'utf-16', 'utf-16-le', 'utf-16-be', 'latin-1']
        
        with open(file_path, 'rb') as f:
            raw_data = f.read(10000)
        
        if raw_data.startswith(b'\xef\xbb\xbf'):
            return {"success": True, "file_path": file_path, "encoding": "utf-8-sig", "confidence": 1.0}
        
        if raw_data.startswith(b'\xff\xfe'):
            return {"success": True, "file_path": file_path, "encoding": "utf-16-le", "confidence": 1.0}
        
        if raw_data.startswith(b'\xfe\xff'):
            return {"success": True, "file_path": file_path, "encoding": "utf-16-be", "confidence": 1.0}
        
        for encoding in common_encodings:
            try:
                raw_data.decode(encoding)
                return {"success": True, "file_path": file_path, "encoding": encoding, "confidence": 0.9}
            except UnicodeDecodeError:
                continue
        
        return {"success": True, "file_path": file_path, "encoding": "utf-8", "confidence": 0.5}
    
    except Exception as e:
        logger.error(f"[get_file_encoding] 检测编码失败: {e}")
        return {"success": False, "error": str(e)}


def get_mime_type(file_path: str) -> Dict[str, Any]:
    """
    获取文件MIME类型 - 小沈 2026-05-02
    """
    try:
        file_path = os.path.abspath(file_path)
        
        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}
        
        mime_type, encoding = mimetypes.guess_type(file_path)
        
        if mime_type is None:
            ext = os.path.splitext(file_path)[1].lower()
            
            common_types = {
                '.py': 'text/x-python',
                '.js': 'application/javascript',
                '.ts': 'application/typescript',
                '.jsx': 'application/javascript',
                '.tsx': 'application/typescript',
                '.json': 'application/json',
                '.yaml': 'application/x-yaml',
                '.yml': 'application/x-yaml',
                '.md': 'text/markdown',
                '.txt': 'text/plain',
                '.log': 'text/plain',
                '.csv': 'text/csv',
                '.xml': 'application/xml',
                '.html': 'text/html',
                '.css': 'text/css',
            }
            
            mime_type = common_types.get(ext, 'application/octet-stream')
        
        return {
            "success": True,
            "file_path": file_path,
            "mime_type": mime_type,
            "encoding": encoding
        }
    
    except Exception as e:
        logger.error(f"[get_mime_type] 获取MIME类型失败: {e}")
        return {"success": False, "error": str(e)}


def backup_file(
    file_path: str,
    backup_dir: Optional[str] = None,
    suffix: str = ".bak",
) -> Dict[str, Any]:
    """
    备份文件 - 小沈 2026-05-02
    """
    try:
        file_path = os.path.abspath(file_path)
        
        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        file_name = os.path.basename(file_path)
        backup_name = f"{file_name}{suffix}_{timestamp}"
        
        if backup_dir is None:
            backup_dir = os.path.dirname(file_path)
        else:
            backup_dir = os.path.abspath(backup_dir)
            os.makedirs(backup_dir, exist_ok=True)
        
        backup_path = os.path.join(backup_dir, backup_name)
        
        shutil.copy2(file_path, backup_path)
        
        return {
            "success": True,
            "original_path": file_path,
            "backup_path": backup_path,
            "backup_size": os.path.getsize(backup_path)
        }
    
    except Exception as e:
        logger.error(f"[backup_file] 备份失败: {e}")
        return {"success": False, "error": str(e)}


def move_to_trash(file_path: str) -> Dict[str, Any]:
    """
    移动文件到回收站 - 小沈 2026-05-02
    """
    file_path = os.path.abspath(file_path)
    
    if not os.path.exists(file_path):
        return {"success": False, "error": f"文件不存在: {file_path}"}
    
    try:
        import send2trash
        send2trash.send2trash(file_path)
        return {"success": True, "path": file_path, "action": "moved_to_trash"}
    except ImportError:
        logger.warning("send2trash未安装，无法移动到回收站")
        return {"success": False, "error": "send2trash未安装，请先安装: pip install send2trash"}
    except Exception as e:
        logger.error(f"[move_to_trash] 移动到回收站失败: {e}")
        return {"success": False, "error": str(e)}


def validate_command(command: str) -> Dict[str, Any]:
    """
    验证命令安全性 - 小沈 2026-05-02
    """
    try:
        dangerous_patterns = [
            r'rm\s+-rf\s+/',
            r'del\s+/\s+',
            r'format\s+',
            r'fdisk\s+',
            r'mkfs\s+',
            r'dd\s+if=',
            r'>\s*/dev/sd',
            r'shutdown\s+',
            r'reboot\s+',
            r'init\s+0',
            r'halt\s+',
            r'poweroff\s+',
        ]
        
        is_dangerous = False
        matched_pattern = None
        
        for pattern in dangerous_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                is_dangerous = True
                matched_pattern = pattern
                break
        
        dangerous_commands = ['format', 'fdisk', 'mkfs', 'dd', 'shutdown', 'reboot', 'halt', 'poweroff', 'init']
        command_parts = command.split()
        base_command = command_parts[0] if command_parts else ''
        
        is_dangerous_cmd = base_command.lower() in dangerous_commands
        
        safe = not is_dangerous and not is_dangerous_cmd
        
        return {
            "success": True,
            "command": command,
            "safe": safe,
            "is_dangerous": is_dangerous or is_dangerous_cmd,
            "matched_pattern": matched_pattern,
            "base_command": base_command
        }
    
    except Exception as e:
        logger.error(f"[validate_command] 验证命令失败: {e}")
        return {"success": False, "error": str(e)}


def check_shell_running(shell_id: str, background_shells: Dict) -> Dict[str, Any]:
    """
    检查Shell是否运行 - 小沈 2026-05-02
    """
    try:
        if shell_id not in background_shells:
            return {"success": True, "shell_id": shell_id, "exists": False, "running": False}
        
        shell_info = background_shells[shell_id]
        process = shell_info.get("process")
        
        if process is None:
            return {"success": True, "shell_id": shell_id, "exists": True, "running": False}
        
        is_running = process.poll() is None
        
        return {
            "success": True,
            "shell_id": shell_id,
            "exists": True,
            "running": is_running,
            "returncode": process.returncode if not is_running else None
        }
    
    except Exception as e:
        logger.error(f"[check_shell_running] 检查Shell状态失败: {e}")
        return {"success": False, "error": str(e)}


__all__ = [
    "extract_archive",
    "get_file_hash",
    "ensure_directory_exists",
    "check_write_permission",
    "check_read_permission",
    "get_file_encoding",
    "get_mime_type",
    "backup_file",
    "move_to_trash",
    "validate_command",
    "check_shell_running",
    "get_file_metadata",
    "calculate_distribution",
    "is_binary_file",
    "is_content_identical",
]


def get_file_metadata(file_path: str, follow_symlinks: bool = True) -> Dict[str, Any]:
    """
    获取文件元数据 - 小沈 2026-05-18
    
    合并 get_file_info + get_file_hash 的元数据部分，供其他工具内部调用。
    不作为LLM工具暴露，由各工具的P15返回值承载。
    
    Args:
        file_path: 文件路径
        follow_symlinks: 是否跟随符号链接
    
    Returns:
        包含完整元数据的字典
    """
    from datetime import datetime
    
    try:
        file_path = os.path.abspath(file_path)
        path = Path(file_path)
        
        if not path.exists():
            return {"success": False, "error": f"文件不存在: {file_path}"}
        
        stat = path.stat(follow_symlinks=follow_symlinks)
        
        metadata = {
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
            metadata["is_symlink"] = True
            try:
                metadata["symlink_target"] = str(os.readlink(path))
            except OSError:
                metadata["symlink_target"] = None
        else:
            metadata["is_symlink"] = path.is_symlink()
        
        if path.is_file():
            metadata["extension"] = path.suffix
            metadata["parent_directory"] = str(path.parent)
        elif path.is_dir():
            try:
                file_count = 0
                dir_count = 0
                for p in path.rglob("*"):
                    if p.is_file():
                        file_count += 1
                    elif p.is_dir():
                        dir_count += 1
                metadata["file_count"] = file_count
                metadata["dir_count"] = dir_count
            except (OSError, PermissionError):
                metadata["file_count"] = None
                metadata["dir_count"] = None
        
        return {"success": True, "metadata": metadata}
    
    except Exception as e:
        logger.error(f"[get_file_metadata] 获取元数据失败: {e}")
        return {"success": False, "error": str(e)}


def calculate_distribution(
    entries: list,
    filters: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    计算文件类型/大小/深度分布 - 小沈 2026-05-18
    
    原file_statistics核心逻辑，合入list_directory P15增强返回值。
    
    Args:
        entries: 文件条目列表，每项需含 name/size/type 字段
        filters: 过滤条件（如 {"min_size": 1024, "extensions": [".py"]}）
    
    Returns:
        包含 file_types/size_distribution/depth_distribution 的字典
    """
    from collections import Counter
    
    try:
        if filters:
            min_size = filters.get("min_size", 0)
            extensions = filters.get("extensions", [])
            
            filtered_entries = []
            for entry in entries:
                if entry.get("size", 0) < min_size:
                    continue
                if extensions:
                    ext = os.path.splitext(entry.get("name", ""))[1].lower()
                    if ext not in extensions:
                        continue
                filtered_entries.append(entry)
            entries = filtered_entries
        
        file_types = Counter()
        size_distribution = Counter()
        depth_distribution = Counter()
        
        for entry in entries:
            if entry.get("type") == "file":
                name = entry.get("name", "")
                size = entry.get("size", 0)
                
                ext = os.path.splitext(name)[1].lower()
                if ext:
                    file_types[ext] += 1
                else:
                    file_types["<no_ext>"] += 1
                
                if size < 1024:
                    size_distribution["<1KB"] += 1
                elif size < 10240:
                    size_distribution["1KB-10KB"] += 1
                elif size < 1024 * 1024:
                    size_distribution["10KB-1MB"] += 1
                else:
                    size_distribution[">1MB"] += 1
            
            path = entry.get("path", entry.get("name", ""))
            depth = path.count(os.sep) if path else 0
            depth_distribution[f"depth_{depth}"] += 1
        
        return {
            "success": True,
            "file_types": dict(file_types),
            "size_distribution": dict(size_distribution),
            "depth_distribution": dict(depth_distribution),
            "total_files": sum(1 for e in entries if e.get("type") == "file"),
            "total_dirs": sum(1 for e in entries if e.get("type") == "directory"),
        }
    
    except Exception as e:
        logger.error(f"[calculate_distribution] 计算分布失败: {e}")
        return {"success": False, "error": str(e)}


def is_binary_file(file_path: str) -> bool:
    """
    检测文件是否为二进制文件 - 小沈 2026-05-18
    
    Args:
        file_path: 文件路径
    
    Returns:
        True表示二进制文件，False表示文本文件
    """
    try:
        file_path = os.path.abspath(file_path)
        
        if not os.path.exists(file_path):
            return False
        
        if not os.path.isfile(file_path):
            return False
        
        text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})
        
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)
            if not chunk:
                return False
            
            return bool(chunk.translate(None, text_chars))
    
    except Exception as e:
        logger.error(f"[is_binary_file] 检测失败: {e}")
        return False


def is_content_identical(
    src: str,
    dst: str,
    strict: bool = False,
    threshold_mb: int = 1
) -> bool:
    """
    判断两文件内容是否一致 - 小沈 2026-05-18
    
    支持幂等性设计（P16）：
    - 小文件（<1MB）：完整字节对比
    - 大文件（≥1MB）：size + mtime 快速判断
    - strict模式：强制计算checksum对比
    
    Args:
        src: 源文件路径
        dst: 目标文件路径
        strict: 是否严格模式（强制checksum对比）
        threshold_mb: 大文件阈值（MB）
    
    Returns:
        True表示内容一致
    """
    import filecmp
    
    try:
        src_path = os.path.abspath(src)
        dst_path = os.path.abspath(dst)
        
        if not os.path.exists(src_path) or not os.path.exists(dst_path):
            return False
        
        src_stat = os.stat(src_path)
        dst_stat = os.stat(dst_path)
        
        if src_stat.st_size != dst_stat.st_size:
            return False
        
        threshold_bytes = threshold_mb * 1024 * 1024
        
        if src_stat.st_size >= threshold_bytes and not strict:
            return src_stat.st_mtime == dst_stat.st_mtime
        
        return filecmp.cmp(src_path, dst_path, shallow=False)
    
    except Exception as e:
        logger.error(f"[is_content_identical] 判断失败: {e}")
        return False


# ================================================================================
# 以下6个impl函数从已删除的file/模块迁移而来 - 小沈 2026-05-18
# ================================================================================

async def batch_rename_impl(
    directory: str,
    pattern: str,
    replacement: str,
    recursive: bool = False,
    preview: bool = False,
    conflict_strategy: str = "skip",
    validate_path_func=None,
    safety_service=None,
    task_id: Optional[str] = None,
    record_operation_func=None,
    execute_with_safety_func=None,
    get_next_sequence_func=None,
) -> Dict[str, Any]:
    """
    batch_rename工具的实现函数 - 格式统一 - 小沈 2026-05-21
    
    Args:
        directory: 目标目录路径
        pattern: 匹配模式（支持正则表达式）
        replacement: 替换字符串
        recursive: 是否递归处理子目录
        preview: 是否只预览不执行
        conflict_strategy: 冲突处理策略（skip、overwrite、rename）
        validate_path_func: 路径验证函数
        safety_service: 安全服务
        task_id: 任务ID
        record_operation_func: 记录操作函数
        execute_with_safety_func: 安全执行函数
        get_next_sequence_func: 获取下一个序列号函数
    
    Returns:
        统一格式的结果字典
    """
    from app.services.safety.file.file_safety import OperationType
    
    is_valid, error_msg = validate_path_func(directory)
    if not is_valid:
        return {"code": "ERR_PATH_INVALID", "data": None, "message": f"目录路径验证失败: {error_msg}"}
    
    if not task_id:
        return {"code": "ERR_NO_TASK", "data": None, "message": "No active task"}
    
    dir_path = Path(directory)
    
    try:
        if not dir_path.exists():
            return {"code": "ERR_DIR_NOT_FOUND", "data": None, "message": f"目录不存在: {directory}"}
        
        if not dir_path.is_dir():
            return {"code": "ERR_PATH_NOT_DIR", "data": None, "message": f"路径不是目录: {directory}"}
        
        try:
            regex = re.compile(pattern)
            use_regex = True
        except re.error:
            use_regex = False
        
        import time as _time
        from app.services.tools.tool_meta import get_timeout as _get_timeout
        _br_deadline = _time.monotonic() + _get_timeout("batch_rename") - 2
        _br_timed_out = False

        def _collect_sync():
            nonlocal _br_timed_out
            result = []
            if recursive:
                for file_path in dir_path.rglob("*"):
                    if _time.monotonic() > _br_deadline:
                        _br_timed_out = True
                        import logging; logging.getLogger(__name__).warning(f"[batch_rename] 超时自检触发，已收集{len(result)}个文件，提前返回")
                        break
                    if file_path.is_file():
                        result.append(file_path)
            else:
                for file_path in dir_path.iterdir():
                    if file_path.is_file():
                        result.append(file_path)
            return result

        files_to_process = await asyncio.to_thread(_collect_sync)
        
        operations = []
        renamed_count = 0
        skipped_count = 0
        failed_count = 0
        
        for file_path in files_to_process:
            original_name = file_path.name
            
            if use_regex:
                new_name = regex.sub(replacement, original_name)
            else:
                new_name = original_name.replace(pattern, replacement)
            
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
                    pass
                elif conflict_strategy == "rename":
                    counter = 1
                    while final_new_path.exists():
                        name_parts = new_path.stem.split('.')
                        if len(name_parts) > 1:
                            base_name = '.'.join(name_parts[:-1])
                            extension = new_path.suffix
                            final_new_path = new_path.parent / f"{base_name}_{counter}{extension}"
                        else:
                            final_new_path = new_path.parent / f"{new_path.stem}_{counter}"
                        counter += 1
                    conflict_resolved = True
            
            operation_id = None
            if record_operation_func:
                operation_id = record_operation_func(
                    task_id=task_id,
                    operation_type=OperationType.RENAME,
                    source_path=file_path,
                    destination_path=final_new_path,
                    sequence_number=get_next_sequence_func()
                )
            
            if not preview:
                def _rename_sync(_src=file_path, _dst=final_new_path):
                    try:
                        _dst.parent.mkdir(parents=True, exist_ok=True)
                        
                        if conflict_strategy == "overwrite" and _dst.exists():
                            _dst.unlink()
                        
                        shutil.move(str(_src), str(_dst))
                        return True
                    except Exception as e:
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
                renamed_count += 1
                operations.append({
                    "file": str(file_path),
                    "original_name": original_name,
                    "new_name": final_new_path.name,
                    "new_path": str(final_new_path),
                    "status": "planned",
                    "conflict_resolved": conflict_resolved,
                    "operation_id": None
                })
        
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
        
        return {"code": "SUCCESS", "data": result, "message": "批量重命名预览" if preview else f"批量重命名完成: {renamed_count}个文件已重命名"}
            
    except Exception as e:
        return {"code": "ERR_RENAME_FAILED", "data": None, "message": f"批量重命名失败: {str(e)}"}


async def compress_files_impl(
    source_path: str,
    output_path: str,
    format: str = "zip",
    exclude_patterns: Optional[List[str]] = None,
    compression_level: int = 6,
    overwrite: bool = False,
    password: Optional[str] = None,
    split_size: Optional[int] = None,
    validate_path_func=None,
    safety_service=None,
    task_id: Optional[str] = None,
    record_operation_func=None,
    execute_with_safety_func=None,
    get_next_sequence_func=None,
) -> Dict[str, Any]:
    """
    compress_files工具的实现函数 - 小沈 2026-05-03 修正; 格式统一 - 小沈 2026-05-21
    
    Args:
        source_path: 源文件或目录路径（必填）
        output_path: 输出压缩文件路径（必填）
        format: 压缩格式：zip、tar.gz（可选），默认zip
        exclude_patterns: 排除的文件/目录模式数组（可选）
        compression_level: 压缩级别0-9（可选），默认6
        overwrite: 是否覆盖已存在的目标文件（可选），默认false
        password: 压缩密码（可选），用于加密压缩文件
        split_size: 分卷大小字节（可选），None表示不分卷
        validate_path_func: 路径验证函数
        safety_service: 安全服务
        task_id: 任务ID
        record_operation_func: 记录操作函数
        execute_with_safety_func: 安全执行函数
        get_next_sequence_func: 获取下一个序列号函数
    
    Returns:
        统一格式的结果字典
    """
    from app.services.safety.file.file_safety import OperationType
    
    is_valid_src, error_msg_src = validate_path_func(source_path)
    if not is_valid_src:
        return {"code": "ERR_PATH_INVALID", "data": None, "message": f"源路径验证失败: {error_msg_src}"}
    
    destination_path = output_path
    
    is_valid_dst, error_msg_dst = validate_path_func(destination_path)
    if not is_valid_dst:
        return {"code": "ERR_PATH_INVALID", "data": None, "message": f"目标路径验证失败: {error_msg_dst}"}
    
    if not overwrite and os.path.exists(destination_path):
        return {"code": "ERR_FILE_EXISTS", "data": None, "message": f"目标文件已存在: {destination_path}，可设置overwrite=true覆盖"}
    
    if not task_id:
        return {"code": "ERR_NO_TASK", "data": None, "message": "No active task"}
    
    if format not in ["zip", "tar.gz"]:
        return {"code": "ERR_UNSUPPORTED_FORMAT", "data": None, "message": f"不支持的压缩格式: {format}，支持格式: zip, tar.gz"}
    
    if not 0 <= compression_level <= 9:
        return {"code": "ERR_INVALID_PARAM", "data": None, "message": f"无效的压缩级别: {compression_level}，必须是0-9之间的整数"}
    
    source = Path(source_path)
    destination = Path(output_path)
    
    try:
        if not source.exists():
            return {"code": "ERR_FILE_NOT_FOUND", "data": None, "message": f"源路径不存在: {source_path}"}
        
        if destination.exists() and not overwrite:
            return {"code": "ERR_FILE_EXISTS", "data": None, "message": f"目标文件已存在: {output_path}，可设置overwrite=true覆盖"}
        
        destination.parent.mkdir(parents=True, exist_ok=True)
        
        operation_id = record_operation_func(
            task_id=task_id,
            operation_type=OperationType.COMPRESS,
            source_path=source,
            destination_path=destination,
            sequence_number=get_next_sequence_func()
        )
        
        import time as _time
        from app.services.tools.tool_meta import get_timeout as _get_timeout
        _cf_deadline = _time.monotonic() + _get_timeout("compress_files") - 2

        def _get_total_size(path: Path) -> int:
            if path.is_file():
                return path.stat().st_size
            else:
                total_size = 0
                for file_path in path.rglob("*"):
                    if _time.monotonic() > _cf_deadline:
                        import logging; logging.getLogger(__name__).warning(f"[compress_files._get_total_size] 超时自检触发，提前返回")
                        break
                    if file_path.is_file():
                        total_size += file_path.stat().st_size
                return total_size
        
        original_size = _get_total_size(source)
        
        def _compress_sync():
            try:
                compressed_files = []
                
                if format == "zip":
                    compression = zipfile.ZIP_STORED if compression_level == 0 else zipfile.ZIP_DEFLATED
                    
                    zip_password = None
                    password_warning = None
                    if password:
                        zip_password = password.encode('utf-8')
                        password_warning = "注意：Python zipfile不支持写入加密，密码仅对解压验证有效"
                    
                    with zipfile.ZipFile(
                        destination, 
                        'w', 
                        compression=compression, 
                        compresslevel=compression_level
                    ) as zf:
                        if password:
                            zf.setpassword(zip_password)
                        
                        if source.is_file():
                            zf.write(source, source.name)
                            compressed_files.append(str(source))
                        else:
                            for file_path in source.rglob("*"):
                                if _time.monotonic() > _cf_deadline:
                                    import logging; logging.getLogger(__name__).warning(f"[compress_files] 超时自检触发，已压缩{len(compressed_files)}个文件，提前返回")
                                    break
                                if file_path.is_file():
                                    arcname = file_path.relative_to(source.parent)
                                    zf.write(file_path, arcname)
                                    compressed_files.append(str(file_path))
                
                elif format == "tar.gz":
                    with tarfile.open(destination, 'w:gz') as tf:
                        if source.is_file():
                            tf.add(source, source.name)
                            compressed_files.append(str(source))
                        else:
                            for file_path in source.rglob("*"):
                                if _time.monotonic() > _cf_deadline:
                                    import logging; logging.getLogger(__name__).warning(f"[compress_files] 超时自检触发(tar.gz)，已压缩{len(compressed_files)}个文件，提前返回")
                                    break
                                if file_path.is_file():
                                    arcname = file_path.relative_to(source.parent)
                                    tf.add(file_path, arcname)
                                    compressed_files.append(str(file_path))
                
                compressed_size = destination.stat().st_size
                
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
                if destination.exists():
                    try:
                        destination.unlink()
                    except OSError:
                        pass
                raise
        
        result = await asyncio.to_thread(
            execute_with_safety_func,
            operation_id=operation_id,
            operation_func=_compress_sync
        )
        
        if result:
            return {"code": "SUCCESS", "data": {"operation_id": operation_id, **result}, "message": f"压缩完成: {result.get('file_count', 0)}个文件"}
        else:
            return {"code": "ERR_COMPRESS_FAILED", "data": None, "message": "压缩失败"}
            
    except Exception as e:
        return {"code": "ERR_COMPRESS_FAILED", "data": None, "message": f"压缩失败: {str(e)}"}


def _split_zip_file(zip_path: Path, split_size: int) -> List[Path]:
    """
    分割zip文件 - 小沈 2026-05-18 从compress_files.py迁移
    
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
    
    zip_path.unlink()
    
    return split_files


async def copy_file_impl(
    source_path: str,
    destination_path: str,
    recursive: bool,
    overwrite: bool,
    validate_path_func,
    safety_service,
    task_id: Optional[str],
    record_operation_func,
    execute_with_safety_func,
    get_next_sequence_func,
    preserve_metadata: bool = True,
) -> Dict[str, Any]:
    """
    copy_file工具的实现函数 - 小健 2026-05-02 增加preserve_metadata; 格式统一 - 小沈 2026-05-21
    
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
        get_next_sequence_func: 获取下一个序列号函数
    
    Returns:
        统一格式的结果字典
    """
    from app.services.safety.file.file_safety import OperationType
    
    is_valid_src, error_msg_src = validate_path_func(source_path)
    if not is_valid_src:
        return {"code": "ERR_PATH_INVALID", "data": None, "message": f"源路径{error_msg_src}"}
    
    is_valid_dst, error_msg_dst = validate_path_func(destination_path)
    if not is_valid_dst:
        return {"code": "ERR_PATH_INVALID", "data": None, "message": f"目标路径{error_msg_dst}"}
    
    if not task_id:
        return {"code": "ERR_NO_TASK", "data": None, "message": "No active task"}
    
    src = Path(source_path)
    dst = Path(destination_path)
    
    try:
        if not src.exists():
            return {"code": "ERR_FILE_NOT_FOUND", "data": None, "message": f"Source not found: {source_path}"}
        
        if dst.exists() and not overwrite:
            return {"code": "ERR_FILE_EXISTS", "data": None, "message": f"目标路径已存在: {dst}，复制操作已取消。请设置overwrite=True或指定其他路径。"}
        
        operation_id = record_operation_func(
            task_id=task_id,
            operation_type=OperationType.COPY,
            source_path=src,
            destination_path=dst,
            sequence_number=get_next_sequence_func()
        )
        
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
            return {"code": "SUCCESS", "data": {"operation_id": operation_id, "source": str(src), "destination": str(dst)}, "message": f"Copied: {src.name} -> {dst}"}
        else:
            return {"code": "ERR_COPY_FAILED", "data": None, "message": "Failed to copy file"}
            
    except Exception as e:
        return {"code": "ERR_COPY_FAILED", "data": None, "message": str(e)}


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
    get_next_sequence_func=None,
) -> Dict[str, Any]:
    """
    file_statistics工具的实现函数 - 格式统一 - 小沈 2026-05-21
    
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
        get_next_sequence_func: 获取下一个序列号函数
    
    Returns:
        统一格式的结果字典
    """
    from app.services.safety.file.file_safety import OperationType
    
    is_valid, error_msg = validate_path_func(directory)
    if not is_valid:
        return {"code": "ERR_PATH_INVALID", "data": None, "message": f"目录路径验证失败: {error_msg}"}
    
    if not task_id:
        return {"code": "ERR_NO_TASK", "data": None, "message": "No active task"}
    
    if output_format not in ["json", "csv", "text"]:
        return {"code": "ERR_UNSUPPORTED_FORMAT", "data": None, "message": f"不支持的输出格式: {output_format}，支持格式: json, csv, text"}
    
    dir_path = Path(directory)
    
    try:
        if not dir_path.exists():
            return {"code": "ERR_DIR_NOT_FOUND", "data": None, "message": f"目录不存在: {directory}"}
        
        if not dir_path.is_dir():
            return {"code": "ERR_PATH_NOT_DIR", "data": None, "message": f"路径不是目录: {directory}"}
        
        operation_id = record_operation_func(
            task_id=task_id,
            operation_type=OperationType.STATISTICS,
            source_path=dir_path,
            destination_path=None,
            sequence_number=get_next_sequence_func()
        )
        
        def _statistics_sync():
            import time
            start_time = time.time()
            
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
            
            from app.services.tools.tool_meta import get_timeout as _get_timeout
            _stat_deadline = time.monotonic() + _get_timeout("file_statistics") - 2
            _stat_timed_out = False

            def _scan_directory(current_path: Path, current_depth: int):
                nonlocal _stat_timed_out
                if current_depth > max_depth:
                    return
                if _stat_timed_out:
                    return
                if time.monotonic() > _stat_deadline:
                    _stat_timed_out = True
                    logger.warning(f"[file_statistics] 超时自检触发，已统计{stats['total_files']}个文件，提前返回")
                    return
                
                try:
                    for item in current_path.iterdir():
                        if _stat_timed_out:
                            return
                        try:
                            if not _apply_filters(item, filters):
                                continue
                            
                            if item.is_file():
                                stat = item.stat()
                                file_size = stat.st_size
                                mtime = stat.st_mtime
                                
                                stats["total_files"] += 1
                                stats["total_size"] += file_size
                                
                                ext = item.suffix.lower()
                                if ext:
                                    stats["file_types"][ext] = stats["file_types"].get(ext, 0) + 1
                                else:
                                    stats["file_types"]["no_extension"] = stats["file_types"].get("no_extension", 0) + 1
                                
                                if file_size < 1024:
                                    stats["size_distribution"]["0-1KB"] += 1
                                elif file_size < 1024 * 1024:
                                    stats["size_distribution"]["1KB-1MB"] += 1
                                elif file_size < 10 * 1024 * 1024:
                                    stats["size_distribution"]["1MB-10MB"] += 1
                                elif file_size < 100 * 1024 * 1024:
                                    stats["size_distribution"]["10MB-100MB"] += 1
                                elif file_size < 1024 * 1024 * 1024:
                                    stats["size_distribution"]["100MB-1GB"] += 1
                                else:
                                    stats["size_distribution"]["1GB+"] += 1
                                
                                now = time.time()
                                time_diff = now - mtime
                                
                                if time_diff < 24 * 60 * 60:
                                    stats["modification_time_distribution"]["today"] += 1
                                elif time_diff < 7 * 24 * 60 * 60:
                                    stats["modification_time_distribution"]["this_week"] += 1
                                elif time_diff < 30 * 24 * 60 * 60:
                                    stats["modification_time_distribution"]["this_month"] += 1
                                elif time_diff < 365 * 24 * 60 * 60:
                                    stats["modification_time_distribution"]["this_year"] += 1
                                else:
                                    stats["modification_time_distribution"]["older"] += 1
                                
                                depth_key = f"depth_{current_depth}"
                                stats["depth_distribution"][depth_key] = stats["depth_distribution"].get(depth_key, 0) + 1
                                
                                if len(stats["files"]) < 1000:
                                    stats["files"].append({
                                        "path": str(item),
                                        "name": item.name,
                                        "size": file_size,
                                        "extension": ext if ext else "",
                                        "modified_time": mtime,
                                        "depth": current_depth
                                    })
                                
                            elif item.is_dir():
                                stats["total_directories"] += 1
                                
                                if recursive:
                                    _scan_directory(item, current_depth + 1)
                                    if _stat_timed_out:
                                        return
                                    
                        except (PermissionError, OSError):
                            continue
                            
                except (PermissionError, OSError):
                    pass
            
            _scan_directory(dir_path, 0)
            
            if stats["total_files"] > 0:
                stats["average_file_size"] = stats["total_size"] / stats["total_files"]
            else:
                stats["average_file_size"] = 0
            
            stats["scan_time"] = time.time() - start_time
            
            stats["file_types"] = dict(sorted(
                stats["file_types"].items(),
                key=lambda x: x[1],
                reverse=True
            ))
            
            if output_format == "json":
                stats["output"] = json.dumps(stats, indent=2, ensure_ascii=False)
            elif output_format == "csv":
                output = io.StringIO()
                writer = csv.writer(output)
                
                writer.writerow(["统计项", "值"])
                writer.writerow(["目录", stats["directory"]])
                writer.writerow(["总文件数", stats["total_files"]])
                writer.writerow(["总目录数", stats["total_directories"]])
                writer.writerow(["总大小(字节)", stats["total_size"]])
                writer.writerow(["平均文件大小(字节)", stats["average_file_size"]])
                writer.writerow(["扫描时间(秒)", stats["scan_time"]])
                writer.writerow([])
                
                writer.writerow(["文件类型分布"])
                writer.writerow(["文件类型", "数量"])
                for ext, count in stats["file_types"].items():
                    writer.writerow([ext, count])
                writer.writerow([])
                
                writer.writerow(["大小分布"])
                writer.writerow(["大小范围", "数量"])
                for size_range, count in stats["size_distribution"].items():
                    writer.writerow([size_range, count])
                writer.writerow([])
                
                writer.writerow(["修改时间分布"])
                writer.writerow(["时间范围", "数量"])
                for time_range, count in stats["modification_time_distribution"].items():
                    writer.writerow([time_range, count])
                
                stats["output"] = output.getvalue()
                
            elif output_format == "text":
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
        
        result = await asyncio.to_thread(
            execute_with_safety_func,
            operation_id=operation_id,
            operation_func=_statistics_sync
        )
        
        if result:
            return {"code": "SUCCESS", "data": {"operation_id": operation_id, **result}, "message": f"文件统计完成: {result.get('total_files', 0)}个文件, {result.get('total_directories', 0)}个目录"}
        else:
            return {"code": "ERR_STATISTICS_FAILED", "data": None, "message": "文件统计失败"}
            
    except Exception as e:
        return {"code": "ERR_STATISTICS_FAILED", "data": None, "message": f"文件统计失败: {str(e)}"}


def _apply_filters(path: Path, filters: Optional[Dict[str, Any]]) -> bool:
    """
    应用过滤条件 - 小沈 2026-05-18 从file_statistics.py迁移
    
    Args:
        path: 文件路径
        filters: 过滤条件字典
    
    Returns:
        是否通过过滤
    """
    if not filters:
        return True
    
    if "file_type" in filters:
        file_type = filters["file_type"]
        if not path.suffix.lower().endswith(file_type.lower()):
            return False
    
    if path.is_file():
        try:
            stat = path.stat()
            
            if "min_size" in filters and stat.st_size < filters["min_size"]:
                return False
            if "max_size" in filters and stat.st_size > filters["max_size"]:
                return False
            
            if "modified_after" in filters:
                modified_after = filters["modified_after"]
                if isinstance(modified_after, (int, float)):
                    if stat.st_mtime < modified_after:
                        return False
                elif isinstance(modified_after, str):
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
                    if stat.st_mtime > modified_before:
                        return False
                elif isinstance(modified_before, str):
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(modified_before.replace('Z', '+00:00'))
                        if stat.st_mtime > dt.timestamp():
                            return False
                    except (ValueError, TypeError):
                        pass
        
        except (OSError, PermissionError):
            return False
    
    return True


async def file_checksum_impl(
    file_path: str,
    algorithm: str = "sha256",
    verify_hash: Optional[str] = None,
    chunk_size: int = 65536,
    timeout: int = 30000,
    validate_path_func=None,
    safety_service=None,
    task_id: Optional[str] = None,
    record_operation_func=None,
    execute_with_safety_func=None,
    get_next_sequence_func=None,
) -> Dict[str, Any]:
    """
    file_checksum工具的实现函数 - 小沈 2026-05-03 修正; 格式统一 - 小沈 2026-05-21
    
    Args:
        file_path: 要计算哈希的文件路径（必填）
        algorithm: 哈希算法（可选），默认sha256。可选值：md5、sha1、sha256、sha512
        verify_hash: 验证哈希值（可选），若提供则自动比对并返回verified状态
        chunk_size: 分块大小（字节），默认65536，用于大文件流式计算
        timeout: 超时毫秒数（可选），默认30000，Agent根据文件大小动态调整
        validate_path_func: 路径验证函数
        safety_service: 安全服务
        task_id: 任务ID
        record_operation_func: 记录操作函数
        execute_with_safety_func: 安全执行函数
        get_next_sequence_func: 获取下一个序列号函数
    
    Returns:
        统一格式的结果字典：{ code, data, message }
    """
    from app.services.safety.file.file_safety import OperationType
    
    is_valid, error_msg = validate_path_func(file_path)
    if not is_valid:
        return {"code": "ERR_PATH_INVALID", "data": None, "message": f"文件路径验证失败: {error_msg}"}
    
    if not task_id:
        return {"code": "ERR_NO_TASK", "data": None, "message": "No active task"}
    
    supported_algorithms = ["md5", "sha1", "sha256", "sha512"]
    if algorithm.lower() not in supported_algorithms:
        return {"code": "ERR_UNSUPPORTED_FORMAT", "data": None, "message": f"不支持的哈希算法: {algorithm}，支持算法: {', '.join(supported_algorithms)}"}
    
    if chunk_size < 1024 or chunk_size > 1048576:
        return {"code": "ERR_INVALID_PARAM", "data": None, "message": f"无效的分块大小: {chunk_size}，必须在1024到1048576之间"}
    
    path = Path(file_path)
    
    try:
        if not path.exists():
            return {"code": "ERR_FILE_NOT_FOUND", "data": None, "message": f"文件不存在: {file_path}"}
        
        if not path.is_file():
            return {"code": "ERR_PATH_NOT_FILE", "data": None, "message": f"路径不是文件: {file_path}"}
        
        operation_id = record_operation_func(
            task_id=task_id,
            operation_type=OperationType.CHECKSUM,
            source_path=path,
            destination_path=None,
            sequence_number=get_next_sequence_func()
        )
        
        def _calculate_checksum_sync():
            start_time = time.time()
            timeout_sec = timeout / 1000.0
            
            try:
                file_size = path.stat().st_size
                
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
                
                with open(path, 'rb') as f:
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        hash_obj.update(chunk)
                        if time.time() - start_time > timeout_sec:
                            raise TimeoutError(f"哈希计算超时（{timeout}毫秒）")
                
                checksum = hash_obj.hexdigest()
                end_time = time.time()
                
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
                
            except Exception:
                raise
        
        result = await asyncio.to_thread(
            execute_with_safety_func,
            operation_id=operation_id,
            operation_func=_calculate_checksum_sync
        )
        
        if result:
            data = {"operation_id": operation_id, **result}
            if verify_hash is not None:
                if result["verification_result"]:
                    msg = f"哈希验证通过: {algorithm.upper()} 匹配"
                else:
                    msg = f"哈希验证失败: {algorithm.upper()} 不匹配"
                    data["expected_hash"] = verify_hash
                    data["actual_hash"] = result["checksum"]
            else:
                msg = f"哈希计算完成: {algorithm.upper()}"
            return {"code": "SUCCESS", "data": data, "message": msg}
        else:
            return {"code": "ERR_CHECKSUM_FAILED", "data": None, "message": "哈希计算失败"}
            
    except Exception as e:
        return {"code": "ERR_CHECKSUM_FAILED", "data": None, "message": f"哈希计算失败: {str(e)}"}


def _calculate_hash_for_multiple_files(
    file_paths: List[str],
    algorithm: str = "sha256",
    chunk_size: int = 65536
) -> Dict[str, Any]:
    """
    批量计算多个文件的哈希值 - 小沈 2026-05-18 从file_checksum.py迁移
    
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


async def get_file_info_impl(
    file_path: str,
    validate_path_func,
    follow_symlinks: bool = True,
) -> Dict[str, Any]:
    """获取文件信息 - 小健 2026-05-02 增加follow_symlinks; 格式统一 - 小沈 2026-05-21"""
    is_valid, error_msg = validate_path_func(file_path)
    if not is_valid:
        return {"code": "ERR_PATH_INVALID", "data": None, "message": error_msg}
    
    path = Path(file_path)
    
    try:
        if not path.exists():
            return {"code": "ERR_FILE_NOT_FOUND", "data": None, "message": f"File not found: {file_path}"}
        
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
                    import time as _time
                    from app.services.tools.tool_meta import get_timeout as _get_timeout
                    _gi_deadline = _time.monotonic() + _get_timeout("get_file_info") - 2
                    _fc = 0; _dc = 0
                    for _p in path.rglob("*"):
                        if _time.monotonic() > _gi_deadline:
                            import logging; logging.getLogger(__name__).warning(f"[get_file_info] 超时自检触发，提前返回 file_count={_fc}, dir_count={_dc}")
                            break
                        if _p.is_file():
                            _fc += 1
                        elif _p.is_dir():
                            _dc += 1
                    info["file_count"] = _fc
                    info["dir_count"] = _dc
                except (OSError, PermissionError):
                    info["file_count"] = None
                    info["dir_count"] = None
            
            return info
        
        info = await asyncio.to_thread(_get_info_sync)
        
        return {"code": "SUCCESS", "data": {"info": info}, "message": "获取文件信息成功"}
        
    except Exception as e:
        return {"code": "ERR_FILE_INFO", "data": None, "message": f"获取文件信息失败: {str(e)}"}
