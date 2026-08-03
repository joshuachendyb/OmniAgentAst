"""
file_encoding — 文件编码检测公用函数
DRY: 从write_text_file/read_text_file/edit_text_file提取 — 小欧 2026-06-30
      新增 safe_read_lines — 小沈 2026-07-05
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.tools.tool_fc_helper import _detect_encoding
from app.logger import logger


_ENCODING_PRIORITY = [
    "utf-8", "gbk", "gb2312", "utf-8-sig",
    "latin-1", "cp1252", "iso-8859-2", "cp1250",
    "gb18030", "big5",
]


def safe_read_lines(file_path: Path, max_size: int = 0) -> Optional[List[str]]:
    """安全读取文件行,自动编码检测+多编码尝试+replace兜底 — 小沈 2026-07-05
    Args:
        file_path: 文件路径
        max_size: 最大文件字节数(0=不限制)
    Returns:
        文件行列表,读取失败返回 None
    """
    try:
        if max_size and file_path.stat().st_size > max_size:
            return None
    except OSError:
        return None

    # chardet 自动检测
    detected_enc = None
    try:
        import chardet as _chardet
        raw = file_path.read_bytes()
        det = _chardet.detect(raw)
        if det and det.get("encoding") and det.get("confidence", 0) > 0.5:
            detected_enc = det["encoding"]
    except Exception:
        pass

    # 构建编码列表: chardet 结果优先
    enc_list = []
    if detected_enc:
        enc_list.append(detected_enc)
    for enc in _ENCODING_PRIORITY:
        if enc not in enc_list:
            enc_list.append(enc)

    # 精确解码
    for enc in enc_list:
        try:
            with file_path.open("r", encoding=enc) as f:
                return f.readlines()
        except (UnicodeDecodeError, LookupError):
            continue

    # replace 兜底 + 质量检查(替换率 >5% 则跳过)
    for enc in enc_list:
        try:
            with file_path.open("r", encoding=enc, errors="replace") as f:
                lines = f.readlines()
            total_chars = sum(len(line) for line in lines)
            if total_chars > 0:
                replace_count = sum(line.count("\ufffd") for line in lines)
                if replace_count / total_chars > 0.05:
                    continue
            return lines
        except (UnicodeDecodeError, LookupError):
            continue
    return None


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
        first_success = None
        for encoding in common_encodings:
            try:
                raw_data.decode(encoding)
                first_success = encoding
                break
            except UnicodeDecodeError:
                continue
        if first_success is None:
            return {"data": {"encoding": "utf-8", "confidence": 0.5}}
        if first_success == 'utf-8':
            try:
                gbk_decoded = raw_data.decode('gbk')
                utf8_decoded = raw_data.decode('utf-8')
                cjk_gbk = sum(1 for c in gbk_decoded if '\u4e00' <= c <= '\u9fff')
                cjk_utf8 = sum(1 for c in utf8_decoded if '\u4e00' <= c <= '\u9fff')
                if cjk_gbk > cjk_utf8:
                    return {"data": {"encoding": "gbk", "confidence": 0.85}}
            except UnicodeDecodeError:
                pass
        return {"data": {"encoding": first_success, "confidence": 0.9}}
    except OSError:
        logger.warning(f"[file_encoding] 文件访问失败: {file_path}")
        return {"data": {"encoding": "utf-8", "confidence": 0.5}}
