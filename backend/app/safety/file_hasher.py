# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-13 - 小沈 - SUPPORTED_ALGORITHMS 改从 app.constants 导入(消除 safety→tools 常量依赖)
# 2026-10-15 北京老陈裁定(名副其实) - hash_helper.py 更名 file_hasher.py:
#   后缀 helper 是最弱的命名约定(意指"什么都往里塞的杂物袋"), 本模块只算文件哈希一件事, 不该挂 helper。
#   命名现与职责一一对应: file(算文件的) + hasher(哈希器), 且是名词短语而非模糊的 helper。
#   函数体一字未改, git mv 保留文件历史。
"""
file_hasher — 文件哈希计算

统一哈希算法选择与文件哈希计算。供 operation_record 记录文件指纹用。
本模块只做哈希, 不含任何其他职责。

【创建时间】2026-05-18 小沈
【迁移】2026-06-22 小欧 从 app/tools/toolhelper 迁移到 app/services/safety

包含函数:
- select_hasher: 统一哈希算法选择(md5/sha1/sha256/sha512)
- compute_file_hash: 核心哈希计算,返回hexdigest字符串
- compute_batch_file_hash: 批量哈希计算

Author: 小沈 - 2026-05-18
"""

import hashlib
import os
import time
from typing import Any, Dict, List, Optional

from app.constants import SUPPORTED_ALGORITHMS  # 从系统常量导入 — 小沈 2026-08-13


def select_hasher(algorithm: str) -> Any:
    """统一哈希算法选择 - 小沈 2026-05-18"""
    algorithm = algorithm.lower()
    if algorithm == "md5":
        return hashlib.md5()
    elif algorithm == "sha1":
        return hashlib.sha1()
    elif algorithm == "sha256":
        return hashlib.sha256()
    elif algorithm == "sha512":
        return hashlib.sha512()
    else:
        raise ValueError(f"不支持的哈希算法: {algorithm},支持: {', '.join(sorted(SUPPORTED_ALGORITHMS))}")


def compute_file_hash(
    file_path: str,
    algorithm: str = "sha256",
    chunk_size: int = 65536,
    timeout_ms: Optional[int] = None,
) -> str:
    """核心哈希计算,返回hexdigest字符串 - 小沈 2026-05-18
    小欧 2026-07-04 修复: 增加None/空路径校验
    """
    if not isinstance(file_path, str) or not file_path.strip():
        raise ValueError("文件路径不能为空")
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    hasher = select_hasher(algorithm)
    start_time = time.time() if timeout_ms is not None else None
    
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
            if start_time is not None and timeout_ms is not None:
                elapsed_ms = (time.time() - start_time) * 1000
                if elapsed_ms > timeout_ms:
                    raise TimeoutError(f"哈希计算超时({timeout_ms}毫秒)")
    
    return hasher.hexdigest()


def compute_batch_file_hash(
    file_paths: List[str],
    algorithm: str = "md5",
    chunk_size: int = 65536,
) -> Dict[str, Any]:
    """批量哈希计算 - 小沈 2026-05-18"""
    results = []
    success_count = 0
    failed_count = 0

    for fp in file_paths:
        try:
            abs_path = os.path.abspath(fp)
            if not os.path.isfile(abs_path):
                results.append({"file_path": fp, "error": "文件不存在或不是文件"})
                failed_count += 1
                continue

            hash_value = compute_file_hash(abs_path, algorithm, chunk_size)
            file_size = os.path.getsize(abs_path)
            results.append({
                "file_path": abs_path,
                "hash": hash_value,
                "algorithm": algorithm,
                "file_size": file_size,
            })
            success_count += 1
        except Exception as e:
            results.append({"file_path": fp, "error": str(e)})
            failed_count += 1

    return {
        "results": results,
        "total": len(file_paths),
        "success": success_count,
        "failed": failed_count,
    }


__all__ = [
    "select_hasher",
    "compute_file_hash",
    "compute_batch_file_hash",
    "SUPPORTED_ALGORITHMS",
]