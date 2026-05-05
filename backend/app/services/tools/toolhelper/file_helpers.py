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
import send2trash
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
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
    try:
        file_path = os.path.abspath(file_path)
        
        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}
        
        send2trash.send2trash(file_path)
        
        return {"success": True, "path": file_path, "action": "moved_to_trash"}
    
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
]
