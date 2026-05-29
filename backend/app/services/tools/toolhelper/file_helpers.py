

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
import time as _time
import time
import tempfile
import filecmp
from pathlib import Path
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, List, Generator, Callable
from dataclasses import dataclass, field
from app.services.tools.toolhelper.hash_helper import select_hasher, compute_file_hash
from app.services.tools._response import build_success, build_error
from app.utils.logger import setup_logger


logger = setup_logger(__name__)


def _is_safe_path(output_dir: str, member_path: str) -> bool:
    """检查解压成员路径是否在output_dir内，防止路径遍历攻击 - 小沈 2026-05-05"""
    target = os.path.normpath(os.path.join(output_dir, member_path))
    return target.startswith(os.path.normpath(output_dir) + os.sep) or target == os.path.normpath(output_dir)


def _resolve_output_dir(archive_path: str, output_dir: Optional[str] = None) -> str:
    """自动推断输出目录。未指定时从basename剥离已知扩展名 — 小健 2026-05-25"""
    if output_dir:
        return os.path.abspath(output_dir)
    archive_path = os.path.abspath(archive_path)
    base_name = os.path.basename(archive_path)
    for ext in ['.zip', '.tar.gz', '.tar.bz2', '.tbz2', '.tgz', '.tar', '.gz', '.bz2']:
        if base_name.lower().endswith(ext):
            base_name = base_name[:-len(ext)]
            break
    return os.path.join(os.path.dirname(archive_path), base_name)


def _extract_zip_archive(archive_path: str, output_dir: str, overwrite: bool,
                         password: Optional[str] = None) -> Dict[str, Any]:
    """解压zip文件（密码+安全路径+覆盖控制）— 小健 2026-05-25"""
    extracted_count, skipped_count = 0, 0
    with zipfile.ZipFile(archive_path, 'r') as zf:
        if password:
            zf.setpassword(password.encode('utf-8'))
        for name in zf.namelist():
            if not _is_safe_path(output_dir, name):
                logger.warning(f"跳过路径遍历成员: {name}")
                skipped_count += 1
                continue
            target_path = os.path.join(output_dir, name)
            if not overwrite and os.path.exists(target_path):
                skipped_count += 1
                continue
            zf.extract(name, output_dir)
            extracted_count += 1
    return {
        "success": True,
        "output_dir": output_dir,
        "extracted_files": extracted_count,
        "skipped_files": skipped_count,
        "format": "zip"
    }


def _extract_tar_archive(archive_path: str, output_dir: str, overwrite: bool,
                         preserve_permissions: bool, mode: str, fmt: str) -> Dict[str, Any]:
    """参数化解压tar文件。mode=r:gz/r:bz2/r, fmt=tar.gz/tar.bz2/tar — 小健 2026-05-25"""
    extracted_count, skipped_count = 0, 0
    with tarfile.open(archive_path, mode) as tf:
        for member in tf.getmembers():
            if not _is_safe_path(output_dir, member.name):
                logger.warning(f"跳过路径遍历成员: {member.name}")
                skipped_count += 1
                continue
            target_path = os.path.join(output_dir, member.name)
            if not overwrite and os.path.exists(target_path):
                skipped_count += 1
                continue
            if member.isfile():
                tf.extract(member, output_dir)
                extracted_count += 1
                if preserve_permissions:
                    try:
                        os.chmod(target_path, member.mode)
                    except Exception as e:
                        logger.warning(f"设置权限失败: {e}")
    return {
        "success": True,
        "output_dir": output_dir,
        "extracted_files": extracted_count,
        "skipped_files": skipped_count,
        "format": fmt
    }


def extract_archive(
    archive_path: str,
    output_dir: Optional[str] = None,
    overwrite: bool = False,
    password: Optional[str] = None,
    preserve_permissions: bool = True,
) -> Dict[str, Any]:
    """
    解压压缩文件 - 小沈 2026-05-02；小健 2026-05-25 重构

    支持 zip、tar、tar.gz、tar.bz2 格式
    """
    try:
        if not os.path.exists(archive_path):
            return build_error(ERR_FILE_EXTRACT, f"压缩文件不存在: {archive_path}")
        out_dir = _resolve_output_dir(archive_path, output_dir)
        os.makedirs(out_dir, exist_ok=True)
        lower_path = archive_path.lower()

        if lower_path.endswith('.zip'):
            result = _extract_zip_archive(archive_path, out_dir, overwrite, password)
        elif lower_path.endswith('.tar.gz') or lower_path.endswith('.tgz'):
            result = _extract_tar_archive(archive_path, out_dir, overwrite, preserve_permissions, 'r:gz', 'tar.gz')
        elif lower_path.endswith('.tar.bz2') or lower_path.endswith('.tbz2'):
            result = _extract_tar_archive(archive_path, out_dir, overwrite, preserve_permissions, 'r:bz2', 'tar.bz2')
        elif lower_path.endswith('.tar'):
            result = _extract_tar_archive(archive_path, out_dir, overwrite, preserve_permissions, 'r', 'tar')
        else:
            return build_error(ERR_FILE_EXTRACT, f"不支持的压缩格式: {archive_path}")
        return build_success(result, f"解压成功: {archive_path}")
    except zipfile.BadZipFile:
        return build_error(ERR_FILE_EXTRACT, "无效的ZIP文件或密码错误")
    except tarfile.TarError as e:
        return build_error(ERR_FILE_EXTRACT, f"TAR文件错误: {str(e)}")
    except Exception as e:
        logger.error(f"[extract_archive] 解压失败: {e}")
        return build_error(ERR_FILE_EXTRACT, str(e))


def get_file_hash(
    file_path: str,
    algorithm: str = "sha256",
) -> Dict[str, Any]:
    """
    计算文件哈希值 - 小沈 2026-05-02
    
    支持 md5、sha1、sha256、sha512
    使用 compute_file_hash 统一核心逻辑
    """
    try:
        file_path = os.path.abspath(file_path)

        if not os.path.exists(file_path):
            return build_error(ERR_FILE_HASH, f"文件不存在: {file_path}")

        if not os.path.isfile(file_path):
            return build_error(ERR_FILE_HASH, f"不是文件: {file_path}")

        # 使用统一的哈希计算函数
        hash_value = compute_file_hash(file_path, algorithm)
        file_size = os.path.getsize(file_path)

        return build_success({
            "file_path": file_path,
            "algorithm": algorithm,
            "hash": hash_value,
            "file_size": file_size
        }, "哈希计算成功")

    except ValueError as e:
        # 算法不支持错误
        return build_error(ERR_FILE_HASH, str(e))
    except Exception as e:
        logger.error(f"[get_file_hash] 计算哈希失败: {e}")
        return build_error(ERR_FILE_HASH, str(e))


def ensure_directory_exists(dir_path: str) -> Dict[str, Any]:
    """
    确保目录存在，不存在则创建 - 小沈 2026-05-02
    """
    try:
        dir_path = os.path.abspath(dir_path)
        
        if os.path.exists(dir_path):
            if os.path.isdir(dir_path):
                return build_success({"path": dir_path, "created": False}, "目录已存在")
            else:
                return build_error(ERR_FILE_PATH_NOT_DIR, f"路径存在但不是目录: {dir_path}")
        
        os.makedirs(dir_path, exist_ok=True)
        
        return build_success({"path": dir_path, "created": True}, "目录创建成功")
    
    except Exception as e:
        logger.error(f"[ensure_directory_exists] 创建目录失败: {e}")
        return build_error(ERR_FILE_CREATE_DIR, str(e))


def check_write_permission(path: str) -> Dict[str, Any]:
    """
    检查写权限 - 小沈 2026-05-02
    """
    try:
        path = os.path.abspath(path)
        
        if os.path.isfile(path):
            writable = os.access(path, os.W_OK)
            return build_success({"path": path, "writable": writable, "type": "file"}, "写权限检查完成")
        
        elif os.path.isdir(path):
            writable = os.access(path, os.W_OK)
            return build_success({"path": path, "writable": writable, "type": "directory"}, "写权限检查完成")
        
        else:
            parent = os.path.dirname(path)
            if parent and os.path.exists(parent):
                writable = os.access(parent, os.W_OK)
                return build_success({"path": path, "writable": writable, "type": "new_file"}, "写权限检查完成")
            else:
                return build_success({"path": path, "writable": False, "type": "new_file"}, "写权限检查完成")
    
    except Exception as e:
        logger.error(f"[check_write_permission] 检查权限失败: {e}")
        return build_error(ERR_FILE_CHECK_PERMISSION, str(e))


def check_read_permission(path: str) -> Dict[str, Any]:
    """
    检查读权限 - 小沈 2026-05-02
    """
    try:
        path = os.path.abspath(path)
        
        if not os.path.exists(path):
            return build_success({"path": path, "readable": False, "exists": False}, "读权限检查完成")
        
        readable = os.access(path, os.R_OK)
        path_type = "file" if os.path.isfile(path) else "directory"
        
        return build_success({"path": path, "readable": readable, "exists": True, "type": path_type}, "读权限检查完成")
    
    except Exception as e:
        logger.error(f"[check_read_permission] 检查权限失败: {e}")
        return build_error(ERR_FILE_CHECK_PERMISSION, str(e))


def get_file_encoding(file_path: str) -> Dict[str, Any]:
    """
    检测文件编码 - 小沈 2026-05-02
    """
    try:
        file_path = os.path.abspath(file_path)
        if not os.path.exists(file_path):
            return build_error(ERR_FILE_ENCODING, f"文件不存在: {file_path}")

        common_encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'big5', 'utf-16', 'utf-16-le', 'utf-16-be', 'latin-1']

        with open(file_path, 'rb') as f:
            raw_data = f.read(10000)

        if raw_data.startswith(b'\xef\xbb\xbf'):
            return build_success({"file_path": file_path, "encoding": "utf-8-sig", "confidence": 1.0}, "编码检测完成")

        if raw_data.startswith(b'\xff\xfe'):
            return build_success({"file_path": file_path, "encoding": "utf-16-le", "confidence": 1.0}, "编码检测完成")

        if raw_data.startswith(b'\xfe\xff'):
            return build_success({"file_path": file_path, "encoding": "utf-16-be", "confidence": 1.0}, "编码检测完成")

        for encoding in common_encodings:
            try:
                raw_data.decode(encoding)
                return build_success({"file_path": file_path, "encoding": encoding, "confidence": 0.9}, "编码检测完成")
            except UnicodeDecodeError:
                continue

        return build_success({"file_path": file_path, "encoding": "utf-8", "confidence": 0.5}, "编码检测完成(低置信度)")

    except Exception as e:
        logger.error(f"[get_file_encoding] 检测编码失败: {e}")
        return build_error(ERR_FILE_ENCODING, str(e))


def get_mime_type(file_path: str) -> Dict[str, Any]:
    """
    获取文件MIME类型 - 小沈 2026-05-02
    """
    try:
        file_path = os.path.abspath(file_path)
        
        if not os.path.exists(file_path):
            return build_error(ERR_FILE_NOT_FOUND, f"文件不存在: {file_path}")
        
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
        
        return build_success({
            "file_path": file_path,
            "mime_type": mime_type,
            "encoding": encoding
        }, "MIME类型获取成功")
    
    except Exception as e:
        logger.error(f"[get_mime_type] 获取MIME类型失败: {e}")
        return build_error(ERR_FILE_MIME_TYPE, str(e))


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
            return build_error(ERR_FILE_BACKUP, f"文件不存在: {file_path}")

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

        return build_success({
            "original_path": file_path,
            "backup_path": backup_path,
            "backup_size": os.path.getsize(backup_path)
        }, f"备份成功: {backup_path}")

    except Exception as e:
        logger.error(f"[backup_file] 备份失败: {e}")
        return build_error(ERR_FILE_BACKUP, str(e))


def move_to_trash(file_path: str) -> Dict[str, Any]:
    """
    移动文件到回收站 - 小沈 2026-05-02
    """
    file_path = os.path.abspath(file_path)
    
    if not os.path.exists(file_path):
        return build_error(ERR_FILE_NOT_FOUND, f"文件不存在: {file_path}")
    
    try:
        import send2trash
        send2trash.send2trash(file_path)
        return build_success({"path": file_path, "action": "moved_to_trash"}, "文件已移动到回收站")
    except ImportError:
        logger.warning("send2trash未安装，无法移动到回收站")
        return build_error(ERR_FILE_MOVE_TRASH, "send2trash未安装，请先安装: pip install send2trash")
    except Exception as e:
        logger.error(f"[move_to_trash] 移动到回收站失败: {e}")
        return build_error(ERR_FILE_MOVE_TRASH, str(e))


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
        
        return build_success({
            "command": command,
            "safe": safe,
            "is_dangerous": is_dangerous or is_dangerous_cmd,
            "matched_pattern": matched_pattern,
            "base_command": base_command
        }, "命令验证完成")
    
    except Exception as e:
        logger.error(f"[validate_command] 验证命令失败: {e}")
        return build_error(ERR_SHELL_VALIDATE_COMMAND, str(e))


def check_shell_running(shell_id: str, background_shells: Dict) -> Dict[str, Any]:
    """
    检查Shell是否运行 - 小沈 2026-05-02
    """
    try:
        if shell_id not in background_shells:
            return build_success({"shell_id": shell_id, "exists": False, "running": False}, "Shell状态检查完成")
        
        shell_info = background_shells[shell_id]
        process = shell_info.get("process")
        
        if process is None:
            return build_success({"shell_id": shell_id, "exists": True, "running": False}, "Shell状态检查完成")
        
        is_running = process.poll() is None
        
        return build_success({
            "shell_id": shell_id,
            "exists": True,
            "running": is_running,
            "returncode": process.returncode if not is_running else None
        }, "Shell状态检查完成")
    
    except Exception as e:
        logger.error(f"[check_shell_running] 检查Shell状态失败: {e}")
        return build_error(ERR_SHELL_CHECK_RUNNING, str(e))


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
    try:
        file_path = os.path.abspath(file_path)
        path = Path(file_path)

        if not path.exists():
            return build_error(ERR_FILE_METADATA, f"文件不存在: {file_path}")

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

        return build_success({"metadata": metadata}, "元数据获取成功")

    except Exception as e:
        logger.error(f"[get_file_metadata] 获取元数据失败: {e}")
        return build_error(ERR_FILE_METADATA, str(e))




# ================================================================================
# 以下6个impl函数从已删除的file/模块迁移而来 - 小沈 2026-05-18
# ================================================================================

def _classify_size_dist(size: int) -> str:
    """文件大小分桶，返回桶名 - 小健 2026-05-25

    使用场景: _StatsCollector和list_directory共用尺寸分类
    使用示例: _classify_size_dist(500) → "0-1KB"; _classify_size_dist(5_000_000) → "1MB-10MB"
    返回数据说明: 返回6级桶名之一: "0-1KB"|"1KB-1MB"|"1MB-10MB"|"10MB-100MB"|"100MB-1GB"|"1GB+"
    """
    if size < 1024:
        return "0-1KB"
    if size < 1048576:
        return "1KB-1MB"
    if size < 10485760:
        return "1MB-10MB"
    if size < 104857600:
        return "10MB-100MB"
    if size < 1073741824:
        return "100MB-1GB"
    return "1GB+"


def _walk_with_timeout(
    path: Path, deadline: float, pattern: str = "*",
    callback: Optional[Callable[[Path, Any, int], None]] = None,
    recursive: bool = True, max_depth: int = 100000,
    filters: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Path], bool]:
    """通用目录遍历器，支持超时+深度+过滤 - 小健 2026-05-25

    使用场景: _collect_files/_compress_entries/_scan_stats_directory三处复用
    使用示例: _walk_with_timeout(Path("/src"), deadline, callback=collector.record_file)
    返回数据说明: (文件列表, 是否超时)
    """
    results: List[Path] = []
    timed_out = False

    def _walk(current: Path, depth: int):
        nonlocal timed_out
        if depth > max_depth or timed_out:
            return
        if time.monotonic() > deadline:
            timed_out = True
            return
        try:
            for item in current.iterdir():
                if timed_out or time.monotonic() > deadline:
                    timed_out = True
                    return
                try:
                    if not _apply_filters(item, filters):
                        continue
                    if item.is_file():
                        st = item.stat()
                        results.append(item)
                        if callback:
                            callback(item, st, depth)
                    elif item.is_dir() and recursive:
                        if callback:
                            callback(item, None, depth)
                        _walk(item, depth + 1)
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError):
            pass

    if path.is_file():
        st = path.stat()
        results.append(path)
        if callback:
            callback(path, st, 0)
    else:
        _walk(path, 0)

    return results, timed_out


async def _collect_files(
    dir_path: Path, recursive: bool,
    deadline: Optional[float] = None, pattern: Optional[str] = None,
) -> Tuple[List[Path], bool]:
    """收集目录下文件列表，支持超时 - 小健 2026-05-25"""
    def _sync_collect() -> Tuple[List[Path], bool]:
        result: List[Path] = []
        iterator = dir_path.rglob(pattern or "*") if recursive else dir_path.glob(pattern or "*")
        for fpath in iterator:
            if deadline and time.monotonic() > deadline:
                logger.warning(f"[_collect_files] 超时，已收集{len(result)}个文件")
                return result, True
            if fpath.is_file():
                result.append(fpath)
        return result, False
    files, timed_out = await asyncio.to_thread(_sync_collect)
    if timed_out:
        logger.warning(f"[_collect_files] 文件收集超时，仅处理已收集的{len(files)}个文件")
    return files, timed_out


def _resolve_name_conflict(
    new_path: Path, strategy: str, max_attempts: int = 100,
) -> Tuple[Path, bool]:
    """解决文件名冲突，返回(最终路径, 是否解决) - 小健 2026-05-25"""
    if not new_path.exists():
        return new_path, True
    if strategy == "skip":
        return new_path, False
    if strategy == "overwrite":
        return new_path, True
    final_path = new_path
    counter = 1
    while final_path.exists() and counter <= max_attempts:
        name_parts = new_path.stem.split('.')
        if len(name_parts) > 1:
            base_name = '.'.join(name_parts[:-1])
            extension = new_path.suffix
            final_path = new_path.parent / f"{base_name}_{counter}{extension}"
        else:
            final_path = new_path.parent / f"{new_path.stem}_{counter}"
        counter += 1
    if counter > max_attempts:
        logger.error(f"冲突解决失败，超过{max_attempts}次尝试")
        return final_path, False
    return final_path, True


def _rename_file_sync(src: Path, dst: Path, conflict_strategy: str):
    """同步执行单文件重命名 - 小健 2026-05-25"""
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if conflict_strategy == "overwrite" and dst.exists():
            dst.unlink()
        shutil.move(str(src), str(dst))
        return True
    except Exception as e:
        return str(e)


@dataclass
class RenameContext:
    """批量重命名上下文 — 13参数→1参数封装 — 小健 2026-05-29"""
    directory: str
    pattern: str
    replacement: str
    recursive: bool = False
    preview: bool = False
    conflict_strategy: str = "skip"
    validate_path_func: Optional[Callable] = None
    safety_service: Optional[Any] = None
    task_id: Optional[str] = None
    record_operation_func: Optional[Callable] = None
    execute_with_safety_func: Optional[Callable] = None
    get_next_sequence_func: Optional[Callable] = None
    _regex: Optional[Any] = field(init=False, repr=False, default=None)
    _use_regex: bool = field(init=False, repr=False, default=False)

    def __post_init__(self):
        if self.pattern:
            try:
                self._regex = re.compile(self.pattern)
                self._use_regex = True
            except re.error:
                self._regex = None
                self._use_regex = False


async def _process_single_rename(
    ctx: RenameContext,
    file_path: Path, new_name: str, original_name: str,
) -> Tuple[Dict[str, Any], int, int, int]:
    """处理单个文件重命名，返回(op_dict, renamed_delta, skipped_delta, failed_delta) — 小健 2026-05-29 SRP-008"""
    from app.db.models.operation_enums import OperationType
    if new_name == original_name:
        return {"file": str(file_path), "original_name": original_name, "new_name": new_name,
                "status": "skipped", "reason": "文件名未变化", "operation_id": None}, 0, 1, 0
    new_path = file_path.parent / new_name
    conflict_resolved = False
    final_new_path = new_path
    if new_path.exists():
        if ctx.conflict_strategy == "skip":
            return {"file": str(file_path), "original_name": original_name, "new_name": new_name,
                    "status": "skipped", "reason": "目标文件已存在（跳过）", "operation_id": None}, 0, 1, 0
        resolved_path, resolved = _resolve_name_conflict(new_path, ctx.conflict_strategy)
        if not resolved and ctx.conflict_strategy != "overwrite":
            return {"file": str(file_path), "original_name": original_name, "new_name": new_name,
                    "status": "skipped", "reason": f"冲突解决失败: {ctx.conflict_strategy}", "operation_id": None}, 0, 1, 0
        final_new_path = resolved_path
        conflict_resolved = resolved
    operation_id = None
    if ctx.record_operation_func:
        operation_id = ctx.record_operation_func(
            task_id=ctx.task_id, operation_type=OperationType.RENAME,
            source_path=file_path, destination_path=final_new_path,
            sequence_number=ctx.get_next_sequence_func())
    if not ctx.preview:
        rename_result = await asyncio.to_thread(
            ctx.execute_with_safety_func, operation_id=operation_id,
            operation_func=lambda _s=file_path, _d=final_new_path: _rename_file_sync(_s, _d, ctx.conflict_strategy))
        if rename_result is True:
            return {"file": str(file_path), "original_name": original_name, "new_name": final_new_path.name,
                    "new_path": str(final_new_path), "status": "renamed", "operation_id": operation_id,
                    "conflict_resolved": conflict_resolved}, 1, 0, 0
        else:
            return {"file": str(file_path), "original_name": original_name, "new_name": new_name,
                    "status": "failed", "error": str(rename_result), "operation_id": operation_id}, 0, 0, 1
    else:
        return {"file": str(file_path), "original_name": original_name, "new_name": final_new_path.name,
                "new_path": str(final_new_path), "status": "planned", "conflict_resolved": conflict_resolved,
                "operation_id": None}, 1, 0, 0


async def batch_rename_impl(ctx: RenameContext) -> Dict[str, Any]:
    """批量重命名 — 12参数→1参数 — 小健 2026-05-29 SRP-008"""
    is_valid, error_msg = ctx.validate_path_func(ctx.directory)
    if not is_valid:
        return build_error(ERR_PATH_INVALID, f"目录路径验证失败: {error_msg}")
    if not ctx.task_id:
        return build_error(ERR_META_NO_ACTIVE_TASK, "No active task")
    dir_path = Path(ctx.directory)

    try:
        if not dir_path.exists():
            return build_error(ERR_FILE_DIRECTORY_NOT_FOUND, f"目录不存在: {ctx.directory}")
        if not dir_path.is_dir():
            return build_error(ERR_FILE_PATH_NOT_DIR, f"路径不是目录: {ctx.directory}")

        from app.services.tools.tool_config import get_timeout as _get_timeout
        deadline = time.monotonic() + _get_timeout("batch_rename") - 2
        files_to_process, _ = await _collect_files(dir_path, ctx.recursive, deadline)

        operations = []
        renamed_count = skipped_count = failed_count = 0
        for file_path in files_to_process:
            if time.monotonic() > deadline:
                logger.warning(f"[batch_rename] 总超时，已处理{len(operations)}/{len(files_to_process)}个文件")
                break
            original_name = file_path.name
            new_name = ctx._regex.sub(ctx.replacement, original_name) if ctx._use_regex else original_name.replace(ctx.pattern, ctx.replacement)
            op, rd, sd, fd = await _process_single_rename(ctx, file_path, new_name, original_name)
            operations.append(op)
            renamed_count += rd
            skipped_count += sd
            failed_count += fd

        result = {
            "directory": str(dir_path), "pattern": ctx.pattern, "replacement": ctx.replacement,
            "use_regex": ctx._use_regex, "recursive": ctx.recursive, "preview_mode": ctx.preview,
            "conflict_strategy": ctx.conflict_strategy, "total_files": len(files_to_process),
            "renamed_files": renamed_count, "skipped_files": skipped_count,
            "failed_files": failed_count, "operations": operations,
        }
        return build_success(result,
                "批量重命名预览" if ctx.preview else f"批量重命名完成: {renamed_count}个文件已重命名")

    except Exception as e:
        return build_error(ERR_FILE_RENAME_FAILED, f"批量重命名失败: {str(e)}")


class _StatsCollector:
    """目录统计收集器，聚合文件/目录统计 - 小健 2026-05-25"""

    def __init__(self):
        self.total_files = 0
        self.total_dirs = 0
        self.total_size = 0
        self.file_types: Dict[str, int] = {}
        self.size_dist: Dict[str, int] = {
            "0-1KB": 0, "1KB-1MB": 0, "1MB-10MB": 0,
            "10MB-100MB": 0, "100MB-1GB": 0, "1GB+": 0,
        }
        self.mtime_dist: Dict[str, int] = {
            "today": 0, "this_week": 0, "this_month": 0, "this_year": 0, "older": 0,
        }
        self.depth_dist: Dict[str, int] = {}
        self.samples: List[Dict] = []

    def record_file(self, item: Path, st: Any, depth: int) -> None:
        self.total_files += 1
        self.total_size += st.st_size
        ext = item.suffix.lower()
        self.file_types[ext or "no_extension"] = self.file_types.get(ext or "no_extension", 0) + 1
        self.size_dist[_classify_size_dist(st.st_size)] += 1
        td = time.time() - st.st_mtime
        if td < 86400:
            self.mtime_dist["today"] += 1
        elif td < 604800:
            self.mtime_dist["this_week"] += 1
        elif td < 2592000:
            self.mtime_dist["this_month"] += 1
        elif td < 31536000:
            self.mtime_dist["this_year"] += 1
        else:
            self.mtime_dist["older"] += 1
        depth_key = f"depth_{depth}"
        self.depth_dist[depth_key] = self.depth_dist.get(depth_key, 0) + 1
        if len(self.samples) < 1000:
            self.samples.append({
                "path": str(item), "name": item.name, "size": st.st_size,
                "extension": ext if ext else "", "modified_time": st.st_mtime, "depth": depth,
            })

    def record_dir(self, item: Any = None, st: Any = None, depth: int = 0) -> None:
        self.total_dirs += 1

    def to_dict(self, directory: str, scan_time: float) -> Dict[str, Any]:
        avg = self.total_size / self.total_files if self.total_files > 0 else 0
        sorted_types = dict(sorted(self.file_types.items(), key=lambda x: x[1], reverse=True))
        return {
            "directory": directory,
            "total_files": self.total_files,
            "total_directories": self.total_dirs,
            "total_size": self.total_size,
            "average_file_size": avg,
            "file_types": sorted_types,
            "size_distribution": self.size_dist,
            "modification_time_distribution": self.mtime_dist,
            "depth_distribution": self.depth_dist,
            "files": self.samples,
            "scan_time": scan_time,
        }


def _scan_stats_directory(
    dir_path: Path, recursive: bool, max_depth: int,
    deadline: float, filters: Optional[Dict[str, Any]],
) -> _StatsCollector:
    """扫描目录收集统计，支持超时+深度+过滤 - 小健 2026-05-25"""
    collector = _StatsCollector()
    _walk_with_timeout(
        dir_path, deadline, callback=collector.record_file,
        recursive=recursive, max_depth=max_depth, filters=filters,
    )
    return collector


def _format_stats_json(stats: Dict[str, Any]) -> Dict[str, Any]:
    """格式化统计结果为JSON — 小健 2026-05-25

    使用场景:
        _format_stats_output中生成JSON格式输出

    使用示例:
        result = _format_stats_json(stats)

    返回数据说明:
        - 返回Dict，包含output字段（JSON字符串）
    """
    stats["output"] = json.dumps(stats, indent=2, ensure_ascii=False)
    return stats


def _format_stats_csv(stats: Dict[str, Any]) -> Dict[str, Any]:
    """格式化统计结果为CSV — 小健 2026-05-25

    使用场景:
        _format_stats_output中生成CSV格式输出

    使用示例:
        result = _format_stats_csv(stats)

    返回数据说明:
        - 返回Dict，包含output字段（CSV字符串）
    """
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
    return stats


def _format_stats_text(stats: Dict[str, Any]) -> Dict[str, Any]:
    """格式化统计结果为文本 — 小健 2026-05-25

    使用场景:
        _format_stats_output中生成文本格式输出

    使用示例:
        result = _format_stats_text(stats)

    返回数据说明:
        - 返回Dict，包含output字段（文本字符串）
    """
    lines = [
        f"目录统计: {stats['directory']}",
        f"总文件数: {stats['total_files']}",
        f"总目录数: {stats['total_directories']}",
        f"总大小: {stats['total_size']:,} 字节",
        f"平均文件大小: {stats['average_file_size']:,.2f} 字节",
        f"扫描时间: {stats['scan_time']:.2f} 秒",
        "",
        "文件类型分布:",
    ]
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


def _format_stats_output(stats: Dict[str, Any], output_format: str) -> Dict[str, Any]:
    """根据格式(json/csv/text)添加output字段 — 小健 2026-05-25 重构拆分

    使用场景:
        file_statistics_impl中格式化输出

    使用示例:
        result = _format_stats_output(stats, "csv")

    返回数据说明:
        - 返回Dict，包含格式化后的output字段
    """
    formatters = {
        "json": _format_stats_json,
        "csv": _format_stats_csv,
        "text": _format_stats_text,
    }
    formatter = formatters.get(output_format)
    if formatter:
        return formatter(stats)
    return stats


def _validate_compress_params(
    source_path: str, output_path: str, fmt: str,
    overwrite: bool, compression_level: int, task_id: Optional[str],
    validate_path_func,
) -> Optional[Dict[str, Any]]:
    """压缩参数校验链，返回None表示通过或error dict - 小健 2026-05-25"""
    is_valid_src, error_msg_src = validate_path_func(source_path)
    if not is_valid_src:
        return build_error(ERR_PATH_INVALID, f"源路径验证失败: {error_msg_src}")
    is_valid_dst, error_msg_dst = validate_path_func(output_path)
    if not is_valid_dst:
        return build_error(ERR_PATH_INVALID, f"目标路径验证失败: {error_msg_dst}")
    if not overwrite and os.path.exists(output_path):
        return build_error(ERR_FILE_PATH_EXISTS, f"目标文件已存在: {output_path}，可设置overwrite=true覆盖")
    if not task_id:
        return build_error(ERR_META_NO_ACTIVE_TASK, "No active task")
    if fmt not in ("zip", "tar.gz"):
        return build_error(ERR_DOC_FORMAT_NOT_SUPPORTED, f"不支持的压缩格式: {fmt}，支持格式: zip, tar.gz")
    if not 0 <= compression_level <= 9:
        return build_error(ERR_PARAMETER_INVALID, f"无效的压缩级别: {compression_level}，必须是0-9之间的整数")
    return None


def _compress_entries(source: Path, deadline: float) -> Generator[Tuple[Path, str], None, bool]:
    """通用文件遍历生成器，yield(path, arcname) → 返回是否超时 - 小健 2026-05-25"""
    if source.is_file():
        yield source, source.name
        return False
    for item in source.rglob("*"):
        if time.monotonic() > deadline:
            return True
        if item.is_file():
            yield item, str(item.relative_to(source.parent))
    return False


def _write_zip(
    source: Path, destination: Path, compression_level: int,
    password: Optional[str], deadline: float,
) -> Tuple[List[str], bool]:
    """写入zip压缩包，返回(文件列表, 是否超时) - 小健 2026-05-25"""
    compressed_files: List[str] = []
    compression = zipfile.ZIP_STORED if compression_level == 0 else zipfile.ZIP_DEFLATED
    with zipfile.ZipFile(destination, 'w', compression=compression, compresslevel=compression_level) as zf:
        if password:
            zf.setpassword(password.encode('utf-8'))
        for file_path, arcname in _compress_entries(source, deadline):
            zf.write(file_path, arcname)
            compressed_files.append(str(file_path))
    return compressed_files, False


def _write_targz(
    source: Path, destination: Path, deadline: float,
) -> Tuple[List[str], bool]:
    """写入tar.gz压缩包，返回(文件列表, 是否超时) - 小健 2026-05-25"""
    compressed_files: List[str] = []
    with tarfile.open(destination, 'w:gz') as tf:
        for file_path, arcname in _compress_entries(source, deadline):
            tf.add(file_path, arcname)
            compressed_files.append(str(file_path))
    return compressed_files, False


def _build_compress_result(
    source: str, destination: str, fmt: str, compression_level: int,
    password: Optional[str], original_size: int, compressed_size: int,
    compressed_files: List[str],
) -> Dict[str, Any]:
    """构建压缩成功结果dict - 小健 2026-05-25"""
    ratio = 1 - (compressed_size / original_size) if original_size > 0 else 0
    return {
        "source_path": source,
        "destination_path": destination,
        "format": fmt,
        "compression_level": compression_level,
        "encrypted": password is not None,
        "original_size": original_size,
        "compressed_size": compressed_size,
        "compression_ratio": ratio,
        "compressed_files": compressed_files,
        "file_count": len(compressed_files),
    }


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
    """compress_files工具的实现函数 - 小健 2026-05-25 重构"""
    from app.services.safety.file.file_safety import OperationType

    validation_error = _validate_compress_params(
        source_path, output_path, format, overwrite, compression_level, task_id, validate_path_func)
    if validation_error:
        return validation_error

    source = Path(source_path)
    destination = Path(output_path)

    try:
        if not source.exists():
            return build_error(ERR_FILE_NOT_FOUND, f"源路径不存在: {source_path}")

        destination.parent.mkdir(parents=True, exist_ok=True)

        operation_id = record_operation_func(
            task_id=task_id, operation_type=OperationType.COMPRESS,
            source_path=source, destination_path=destination,
            sequence_number=get_next_sequence_func(),
        )

        from app.services.tools.tool_config import get_timeout as _get_timeout
        _cf_deadline = time.monotonic() + _get_timeout("compress_files") - 2

        original_size = _get_total_size_sync(source, _cf_deadline)

        def _compress_sync():
            try:
                if format == "zip":
                    compressed_files, _ = _write_zip(source, destination, compression_level, password, _cf_deadline)
                else:
                    compressed_files, _ = _write_targz(source, destination, _cf_deadline)
                compressed_size = destination.stat().st_size
                return _build_compress_result(
                    str(source), str(destination), format, compression_level,
                    password, original_size, compressed_size, compressed_files)
            except Exception:
                if destination.exists():
                    try:
                        destination.unlink()
                    except OSError:
                        pass
                raise

        result = await asyncio.to_thread(
            execute_with_safety_func, operation_id=operation_id, operation_func=_compress_sync)

        if result:
            return build_success({"operation_id": operation_id, **result},
                    f"压缩完成: {result.get('file_count', 0)}个文件")
        return build_error(ERR_FILE_COMPRESS_FAILED, "压缩失败")

    except Exception as e:
        return build_error(ERR_FILE_COMPRESS_FAILED, f"压缩失败: {str(e)}")


def _get_total_size_sync(path: Path, deadline: float) -> int:
    """同步计算源路径总大小，支持超时 - 小健 2026-05-25"""
    if path.is_file():
        return path.stat().st_size
    total_size = 0
    for file_path in path.rglob("*"):
        if time.monotonic() > deadline:
            logger.warning("[_get_total_size_sync] 超时自检触发，提前返回")
            break
        if file_path.is_file():
            total_size += file_path.stat().st_size
    return total_size


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
        return build_error(ERR_PATH_INVALID, f"源路径{error_msg_src}")
    
    is_valid_dst, error_msg_dst = validate_path_func(destination_path)
    if not is_valid_dst:
        return build_error(ERR_PATH_INVALID, f"目标路径{error_msg_dst}")
    
    if not task_id:
        return build_error(ERR_META_NO_ACTIVE_TASK, "No active task")
    
    src = Path(source_path)
    dst = Path(destination_path)
    
    try:
        if not src.exists():
            return build_error(ERR_FILE_NOT_FOUND, f"Source not found: {source_path}")
        
        if dst.exists() and not overwrite:
            return build_error(ERR_FILE_PATH_EXISTS, f"目标路径已存在: {dst}，复制操作已取消。请设置overwrite=True或指定其他路径。")
        
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
            return build_success({"operation_id": operation_id, "source": str(src), "destination": str(dst)}, f"Copied: {src.name} -> {dst}")
        else:
            return build_error(ERR_FILE_COPY_FAILED, "Failed to copy file")
            
    except Exception as e:
        return build_error(ERR_FILE_COPY_FAILED, str(e))


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
    """file_statistics工具的实现函数 - 小健 2026-05-25 重构"""
    from app.services.safety.file.file_safety import OperationType

    is_valid, error_msg = validate_path_func(directory)
    if not is_valid:
        return build_error(ERR_PATH_INVALID, f"目录路径验证失败: {error_msg}")
    if not task_id:
        return build_error(ERR_META_NO_ACTIVE_TASK, "No active task")
    if output_format not in ("json", "csv", "text"):
        return build_error(ERR_DOC_FORMAT_NOT_SUPPORTED, f"不支持的输出格式: {output_format}，支持格式: json, csv, text")

    dir_path = Path(directory)

    try:
        if not dir_path.exists():
            return build_error(ERR_FILE_DIRECTORY_NOT_FOUND, f"目录不存在: {directory}")
        if not dir_path.is_dir():
            return build_error(ERR_FILE_PATH_NOT_DIR, f"路径不是目录: {directory}")

        operation_id = record_operation_func(
            task_id=task_id, operation_type=OperationType.STATISTICS,
            source_path=dir_path, destination_path=None,
            sequence_number=get_next_sequence_func(),
        )

        from app.services.tools.tool_config import get_timeout as _get_timeout
        _stat_deadline = time.monotonic() + _get_timeout("file_statistics") - 2

        def _statistics_sync():
            start_time = time.time()
            collector = _scan_stats_directory(dir_path, recursive, max_depth, _stat_deadline, filters)
            scan_time = time.time() - start_time
            stats = collector.to_dict(str(dir_path), scan_time)
            return _format_stats_output(stats, output_format)

        result = await asyncio.to_thread(
            execute_with_safety_func, operation_id=operation_id, operation_func=_statistics_sync)

        if result:
            return build_success({"operation_id": operation_id, **result},
                    f"文件统计完成: {result.get('total_files', 0)}个文件, {result.get('total_directories', 0)}个目录")
        return build_error(ERR_STATISTICS_FAILED, "文件统计失败")

    except Exception as e:
        return build_error(ERR_STATISTICS_FAILED, f"文件统计失败: {str(e)}")


def _parse_date_filter(date_value: Any) -> Optional[float]:
    """解析日期过滤器值 — 小健 2026-05-25 重构拆分

    使用场景:
        _apply_filters中解析modified_after/modified_before

    使用示例:
        timestamp = _parse_date_filter("2024-01-01")

    返回数据说明:
        - 返回Optional[float]，解析失败返回None
    """
    if isinstance(date_value, (int, float)):
        return date_value
    elif isinstance(date_value, str):
        try:
            dt = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
            return dt.timestamp()
        except (ValueError, TypeError):
            return None
    return None


def _apply_filters(path: Path, filters: Optional[Dict[str, Any]]) -> bool:
    """
    应用过滤条件 - 小沈 2026-05-18 从file_statistics.py迁移，小健 2026-05-25 重构

    使用场景:
        file_statistics/_walk_with_timeout中过滤文件

    使用示例:
        if _apply_filters(file_path, {"min_size": 1024}):
            process(file_path)

    返回数据说明:
        - 返回bool，是否通过过滤
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
                modified_after = _parse_date_filter(filters["modified_after"])
                if modified_after is not None and stat.st_mtime < modified_after:
                    return False

            if "modified_before" in filters:
                modified_before = _parse_date_filter(filters["modified_before"])
                if modified_before is not None and stat.st_mtime > modified_before:
                    return False

        except (OSError, PermissionError):
            return False

    return True


def _build_checksum_result(
    checksum: str, algorithm: str, file_path: str,
    file_size: int, elapsed_ms: int,
    verify_hash: Optional[str] = None,
) -> Dict[str, Any]:
    """构建校验和返回结果。

    小沈 2026-05-25 重构拆分
    YAGNI: 不再输出 hash_algorithm/checksum_upper/checksum_lower 派生字段。
    消除 verify 3 条路径(msg+data构建)的重复。
    """
    data = {
        "checksum": checksum,
        "algorithm": algorithm,
        "file_path": file_path,
        "file_size": file_size,
        "elapsed_ms": elapsed_ms,
    }
    if verify_hash:
        matched = checksum.lower() == verify_hash.lower()
        data["verify_result"] = matched
        message = f"校验和{'匹配' if matched else '不匹配'}" \
                  f"(输入: {verify_hash}, 计算: {checksum})"
    else:
        message = f"{algorithm.upper()} 校验和: {checksum}"

    from app.services.tools._response import build_success
    return build_success(data, message,
        llm_data={"校验算法": algorithm, "校验值": checksum, "验证结果": data.get("verify_result")},
    )


def _calculate_checksum_sync(
    path: Path, algorithm: str, chunk_size: int, timeout: int,
) -> str:
    """同步分块哈希计算（含超时）。

    小沈 2026-05-25 重构拆分
    使用统一的 compute_file_hash 函数。
    """
    return compute_file_hash(
        file_path=str(path),
        algorithm=algorithm,
        chunk_size=chunk_size,
        timeout_ms=timeout
    )


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
        return build_error(ERR_PATH_INVALID, f"文件路径验证失败: {error_msg}")

    if not task_id:
        return build_error(ERR_META_NO_ACTIVE_TASK, "No active task")

    supported_algorithms = ["md5", "sha1", "sha256", "sha512"]
    if algorithm.lower() not in supported_algorithms:
        return build_error(ERR_DOC_FORMAT_NOT_SUPPORTED, f"不支持的哈希算法: {algorithm}，支持算法: {', '.join(supported_algorithms)}")

    if chunk_size < 1024 or chunk_size > 1048576:
        return build_error(ERR_PARAMETER_INVALID, f"无效的分块大小: {chunk_size}，必须在1024到1048576之间")

    path = Path(file_path)

    try:
        if not path.exists():
            return build_error(ERR_FILE_NOT_FOUND, f"文件不存在: {file_path}")

        if not path.is_file():
            return build_error(ERR_FILE_PATH_NOT_FILE, f"路径不是文件: {file_path}")

        operation_id = record_operation_func(
            task_id=task_id,
            operation_type=OperationType.CHECKSUM,
            source_path=path,
            destination_path=None,
            sequence_number=get_next_sequence_func()
        )

        start = time.perf_counter()
        try:
            checksum = await asyncio.to_thread(
                execute_with_safety_func,
                operation_id=operation_id,
                operation_func=lambda: _calculate_checksum_sync(path, algorithm, chunk_size, timeout),
            )
        except TimeoutError:
            return build_error(ERR_FILE_CHECKSUM_TIMEOUT, f"计算超时({timeout}ms")
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return _build_checksum_result(checksum, algorithm, str(path),
                                       path.stat().st_size, elapsed_ms, verify_hash)

    except Exception as e:
        return build_error(ERR_FILE_CHECKSUM_FAILED, f"哈希计算失败: {str(e)}")

async def get_file_info_impl(
    file_path: str,
    validate_path_func,
    follow_symlinks: bool = True,
) -> Dict[str, Any]:
    """获取文件信息 - 小健 2026-05-02 增加follow_symlinks; 格式统一 - 小沈 2026-05-21"""
    is_valid, error_msg = validate_path_func(file_path)
    if not is_valid:
        return build_error(ERR_PATH_INVALID, error_msg)
    
    path = Path(file_path)
    
    try:
        if not path.exists():
            return build_error(ERR_FILE_NOT_FOUND, f"File not found: {file_path}")
        
        def _get_info_sync():
            meta_result = get_file_metadata(file_path, follow_symlinks)
            if meta_result.get("code") != "SUCCESS":
                raise RuntimeError(meta_result.get("message", "获取文件元数据失败"))
            info = meta_result["data"]["metadata"]
            
            if path.is_dir():
                try:
                    from app.services.tools.tool_config import get_timeout as _get_timeout
                    _gi_deadline = _time.monotonic() + _get_timeout("get_file_info") - 2
                    _fc = 0
                    _dc = 0
                    for _p in path.rglob("*"):
                        if _time.monotonic() > _gi_deadline:
                            logger.warning(f"[get_file_info] 超时自检触发，提前返回 file_count={_fc}, dir_count={_dc}")

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
        
        return build_success({"info": info}, "获取文件信息成功")
        
    except Exception as e:
        return build_error(ERR_FILE_INFO, f"获取文件信息失败: {str(e)}")
from app.constants import (
    ERR_DOC_FORMAT_NOT_SUPPORTED,
    ERR_FILE_BACKUP,
    ERR_FILE_CALCULATE_DISTRIBUTION,
    ERR_FILE_CHECKSUM_FAILED,
    ERR_FILE_CHECKSUM_TIMEOUT,
    ERR_FILE_CHECK_PERMISSION,
    ERR_FILE_COMPRESS_FAILED,
    ERR_FILE_COPY_FAILED,
    ERR_FILE_CREATE_DIR,
    ERR_FILE_DIRECTORY_NOT_FOUND,
    ERR_FILE_ENCODING,
    ERR_FILE_EXTRACT,
    ERR_FILE_HASH,
    ERR_FILE_INFO,
    ERR_FILE_METADATA,
    ERR_FILE_MIME_TYPE,
    ERR_FILE_MOVE_TRASH,
    ERR_FILE_NOT_FOUND,
    ERR_FILE_PATH_EXISTS,
    ERR_FILE_PATH_NOT_DIR,
    ERR_FILE_PATH_NOT_FILE,
    ERR_FILE_RENAME_FAILED,
    ERR_META_NO_ACTIVE_TASK,
    ERR_PARAMETER_INVALID,
    ERR_PATH_INVALID,
    ERR_SHELL_CHECK_RUNNING,
    ERR_SHELL_VALIDATE_COMMAND,
    ERR_STATISTICS_FAILED,
)
