# -*- coding: utf-8 -*-
"""
哈希计算公共Helper - 统一哈希算法选择和计算

【创建时间】2026-05-18 小沈
【说明】从 file_helpers.py 的 hash_file_tool 提取公共逻辑，
       供 file_tools.hash_file_tool 和 file_checksum 等复用。
       不注册到tool_registry，不暴露给LLM。

包含函数：
- select_hasher: 统一哈希算法选择（md5/sha1/sha256/sha512）
- compute_file_hash: 核心哈希计算，返回hexdigest字符串
- compute_batch_file_hash: 批量哈希计算

Author: 小沈 - 2026-05-18
"""

import hashlib
import os
from typing import Any, Dict, List


SUPPORTED_ALGORITHMS = {"md5", "sha1", "sha256", "sha512"}


def select_hasher(algorithm: str) -> Any:
    """统一哈希算法选择 - 小沈 2026-05-18

    Args:
        algorithm: 哈希算法名称（md5/sha1/sha256/sha512）

    Returns:
        对应的hashlib哈希对象

    Raises:
        ValueError: 不支持的算法
    """
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
        raise ValueError(f"不支持的哈希算法: {algorithm}，支持: {', '.join(sorted(SUPPORTED_ALGORITHMS))}")


def compute_file_hash(
    file_path: str,
    algorithm: str = "sha256",
    chunk_size: int = 65536,
    timeout_ms: int = None,
) -> str:
    """核心哈希计算，返回hexdigest字符串 - 小沈 2026-05-18

    Args:
        file_path: 文件路径（绝对路径）
        algorithm: 哈希算法（md5/sha1/sha256/sha512）
        chunk_size: 分块大小，默认64KB
        timeout_ms: 超时毫秒数，None表示无超时

    Returns:
        hexdigest字符串

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 不支持的算法
        TimeoutError: 超时（如果timeout_ms不为None）
    """
    import time
    hasher = select_hasher(algorithm)
    start_time = time.time() if timeout_ms is not None else None
    
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
            
            # 检查超时
            if start_time is not None and timeout_ms is not None:
                elapsed_ms = (time.time() - start_time) * 1000
                if elapsed_ms > timeout_ms:
                    raise TimeoutError(f"哈希计算超时（{timeout_ms}毫秒）")
    
    return hasher.hexdigest()


def compute_batch_file_hash(
    file_paths: List[str],
    algorithm: str = "md5",
    chunk_size: int = 65536,
) -> Dict[str, Any]:
    """批量哈希计算 - 小沈 2026-05-18

    Args:
        file_paths: 文件路径列表
        algorithm: 哈希算法，默认md5（批量场景常用md5）
        chunk_size: 分块大小

    Returns:
        {"results": [{"file_path": ..., "hash": ..., "algorithm": ..., "file_size": ...}, ...],
         "total": N, "success": M, "failed": K}
    """
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
