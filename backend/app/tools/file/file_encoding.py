"""
file_encoding — 文件编码检测公用函数
DRY: 从write_text_file/read_text_file/edit_text_file提取 — 小欧 2026-06-30
"""

import os
from pathlib import Path
from typing import Any, Dict

from app.tools.tool_fc_helper import _detect_encoding
from app.utils.logger import logger


def get_file_encoding(file_path: str) -> Dict[str, Any]:
    """统一编码检测 — 返回 {"data": {"encoding": str, "confidence": float}} — 小欧 2026-06-30"""
    try:
        file_path = os.path.abspath(file_path)
        if not os.path.exists(file_path):
            return {"data": {"encoding": "utf-8", "confidence": 0.5}}
        detected = _detect_encoding(Path(file_path))
        if detected in ("utf-8-sig", "utf-16-le", "utf-16-be", "utf-8"):
            confidence = 1.0 if detected != "utf-8" else 0.95
            return {"data": {"encoding": detected, "confidence": confidence}}
        common_encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'big5', 'latin-1']
        with open(file_path, 'rb') as f:
            raw_data = f.read(10000)
        for encoding in common_encodings:
            try:
                raw_data.decode(encoding)
                return {"data": {"encoding": encoding, "confidence": 0.9}}
            except UnicodeDecodeError:
                continue
        return {"data": {"encoding": "utf-8", "confidence": 0.5}}
    except OSError:
        logger.warning(f"[file_encoding] 文件访问失败: {file_path}")
        return {"data": {"encoding": "utf-8", "confidence": 0.5}}
