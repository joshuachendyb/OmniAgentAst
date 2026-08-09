"""
file_encoding — 文件编码检测公用函数
DRY: 从write_text_file/read_text_file/edit_text_file提取 — 小欧 2026-06-30
      新增 safe_read_lines — 小沈 2026-07-05
      2026-08-09 - 小欧 - 新增 read_file_with_encodings(合并 read_text_file/edit_text_file 两份 _try_read_file_with_encodings
      私有实现为公共版, 统一替换符阈值+mojibake检查); _looks_like_mojibake 迁入本模块
"""

import asyncio
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.tools.tool_fc_helper import _detect_encoding
from app.logger import logger
from app.tools.tool_constants import READTEXT_INER_CJK_SAMPLE  # 小欧 2026-08-09: mojibake检测迁入公共


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


# ============================================================
# 统一编码回退读取 — 小欧 2026-08-09 (DRY 合并)
# 病根: read_text_file 与 edit_text_file 各有一份 _try_read_file_with_encodings,
#       行为不一致(edittext对preferred也做替换符检查, readtext对preferred直接返回)。
# 合并为公共 read_file_with_encodings(取"增强"语义): 所有编码统一替换符阈值检查 + mojibake 检测,
# 调用契约不变 (content, used_encoding, error)。
# ============================================================

_REPLACEMENT_CHAR_MIN_COUNT = 3
_REPLACEMENT_CHAR_RATIO = 0.03


def _looks_like_mojibake(content: str, file_path: str = "") -> bool:
    """检测内容是否可能是编码错误造成的乱码 — 小欧 2026-06-30 (2026-08-09 迁入公共 file_encoding)
    GBK字节被误读为UTF-8时，内容中CJK字符极少、Latin-1补充字符极多
    北京老陈 2026-06-30: 文件路径或内容中无中文时不检测，避免误判法文/德文"""
    if not content or len(content) < 10:
        return False
    has_cjk = any('\u4e00' <= c <= '\u9fff' for c in file_path)
    has_cjk = has_cjk or any('\u4e00' <= c <= '\u9fff' for c in content[:READTEXT_INER_CJK_SAMPLE])
    if not has_cjk:
        return False
    total = len(content)
    cjk = sum(1 for c in content if '\u4e00' <= c <= '\u9fff')
    latin1_supp = sum(1 for c in content if '\u0080' <= c <= '\u00ff')
    if cjk / total < 0.05 and latin1_supp / total > 0.30:
        return True
    return False


async def read_file_with_encodings(
    path: Path,
    preferred: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """统一编码检测+同步文件读取 (content, used_encoding, error) — 小欧 2026-08-09
    合并 read_text_file 与 edit_text_file 两份私有实现(DRY), 取增强语义:
    - 候选: preferred 指定→优先尝试+常见中文编码兜底; 否则 auto 探测编码优先+常见中文编码
    - 每个编码统一做替换符阈值检查(>=3且>3%)与 mojibake 检测, 不达标回退下一编码
    返回 (content, used_encoding, error); 调用方据此比较 encoding 与 used_encoding 判断是否回退
    """
    try:
        if preferred:
            encodings_to_try = [preferred]
        else:
            auto = get_file_encoding(str(path))
            encodings_to_try = []
            if auto and auto.get("data", {}).get("encoding"):
                encodings_to_try.append(auto["data"]["encoding"])
        fallbacks = ["utf-8", "gbk", "gb2312", "utf-8-sig"]
        for enc in fallbacks:
            if enc not in encodings_to_try:
                encodings_to_try.append(enc)
        for enc in encodings_to_try:
            if enc is None:
                continue
            try:
                def _read(e=enc):
                    with open(path, 'r', encoding=e, errors='replace') as f:
                        return f.read()
                content = await asyncio.to_thread(_read)
                if '\ufffd' in content:
                    _repl_count = content.count('\ufffd')
                    if _repl_count >= _REPLACEMENT_CHAR_MIN_COUNT and _repl_count > len(content) * _REPLACEMENT_CHAR_RATIO:
                        content = None
                        continue
                if _looks_like_mojibake(content, str(path)):
                    continue
                return content, enc, None
            except Exception:
                continue
        return None, None, f"无法读取文件: {path},已尝试编码: {encodings_to_try}"
    except Exception as e:
        return None, None, str(e)
