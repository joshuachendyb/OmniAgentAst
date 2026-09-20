# -*- coding: utf-8 -*-
"""
文件操作公共辅助函数 — 纯文件系统操作，不依赖任何业务层

编辑历史:
  2026-08-13 小沈 P1: 从 tools/file/delete_file.py 复制迁入 remove_readonly,
    消除 safety→tools 实现依赖(safety/operation_maintenance.py 和 operation_rollback.py
    改从本文件导入, tools/file/delete_file.py 同步改从本文件导入)
  2026-08-13 小沈 P5b: 从 tools/tool_fc_helper.py 复制迁入 backup_file,
    消除 services/model/persistence.py→tools 实现依赖
  2026-09-20 小沈 v4.19 9.3.2: 新增 atomic_write（临时文件+os.replace 原子写入）;
    backup_file 改为编号链 backup.1~5 + FIFO（保留原签名兼容，suffix 透传）
"""

import os
import shutil
import tempfile
from typing import Any, Dict, Optional


def remove_readonly(func, path, excinfo):
    """解除只读属性后重试（shutil.rmtree onerror 回调）

    Windows下shutil.rmtree遇到只读文件会[WinError 5]拒绝访问。
    因为备份用的是shutil.copy2，原文件的只读属性被完整保留。
    onerror回调先chmod加写权限再重新执行删除，解决此问题。

    来源: 从 app/tools/file/delete_file.py 复制迁入 — 小沈 2026-08-13
    """
    os.chmod(path, os.stat(path).st_mode | 0o200)
    func(path)


def atomic_write(file_path: str, content: str, encoding: str = "utf-8") -> None:
    """原子写入文本：写同目录临时文件 → fsync → os.replace 整文件替换，绝不半写。

    同目录临时文件保证 replace 不跨文件系统；异常时清临时文件原样抛出。
    小沈 2026-09-20 v4.19 9.3.2
    """
    abs_path = os.path.abspath(file_path)
    parent = os.path.dirname(abs_path) or "."
    fd, tmp_path = tempfile.mkstemp(dir=parent, prefix=".tmp_", suffix=".yaml")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, abs_path)
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise


def backup_file(file_path: str, backup_dir: Optional[str] = None, suffix: str = ".backup",
                keep: int = 5) -> Dict[str, Any]:
    """编号备份链：backup.1（最新）~ backup.N（最旧）+ FIFO 清理（9.2/一.7）。

    轮转：删最旧 backup.{keep}，backup.{i}→backup.{i+1} 顺移，新备份=backup.1。
    返回保持原形状 {original_path, backup_path, backup_size}，加 backup_index=1。
    注意：旧调用方 update_config 验证成功后会删本次 backup.1（原有行为不变）；
    设置页路径（merge_region_patch）保留备份，链满 5 个自动 FIFO。

    小沈 2026-09-20 v4.19 9.3.2: 从时间戳单备份改为编号链 + FIFO
    """
    file_path = os.path.abspath(file_path)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    file_name = os.path.basename(file_path)
    if backup_dir is None:
        backup_dir = os.path.dirname(file_path)
    else:
        backup_dir = os.path.abspath(backup_dir)
        os.makedirs(backup_dir, exist_ok=True)
    for i in range(keep, 1, -1):
        older = os.path.join(backup_dir, f"{file_name}{suffix}.{i}")
        newer_src = os.path.join(backup_dir, f"{file_name}{suffix}.{i - 1}")
        if os.path.exists(older):
            os.remove(older)
        if os.path.exists(newer_src):
            os.rename(newer_src, older)
    backup_path = os.path.join(backup_dir, f"{file_name}{suffix}.1")
    shutil.copy2(file_path, backup_path)
    return {
        "original_path": file_path,
        "backup_path": backup_path,
        "backup_size": os.path.getsize(backup_path),
        "backup_index": 1,
    }
