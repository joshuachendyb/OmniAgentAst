"""
file_encoding — 文件编码检测公用函数
DRY: 从write_text_file/read_text_file/edit_text_file提取 — 小欧 2026-06-30
      新增 safe_read_lines — 小沈 2026-07-05
      2026-08-09 - 小欧 - 新增 read_file_with_encodings(合并 read_text_file/edit_text_file 两份 _try_read_file_with_encodings
      私有实现为公共版, 统一替换符阈值+mojibake检查); _looks_like_mojibake 迁入本模块
      2026-10-21 - 小欧 - read_file_with_encodings 增 max_bytes（读前闸门，防 OOM）：
                  不给=全量读（既有行为不变）；给了=只读前 N 字节，不整文件进内存 — 小欧-2026-10-21
      2026-11-14 - 小欧 - safe_read_lines 流式化重构(8100 grep 假死事故同类处置):
                  编码探测改头部64KB采样(原chardet全量read_bytes超大文件OOM), 逐行yield内存O(行),
                  G级log可查; 整文件统一 errors='replace' 容错流式读取(采样strict验证编码后,
                  中途个别非法字节不抛UnicodeDecodeError, 否则整个grep搜索失败) — 小欧-2026-11-14
"""

import asyncio
import os
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from app.logger import logger
from app.tools.tool_constants import READ_INER_CJK_SAMPLE  # 小欧 2026-08-09: mojibake检测迁入公共
from app.tools.tool_fc_helper import _detect_encoding

_ENCODING_PRIORITY = [
    "utf-8", "gbk", "gb2312", "utf-8-sig",
    "latin-1", "cp1252", "iso-8859-2", "cp1250",
    "gb18030", "big5",
]


_ENCODING_SAMPLE_BYTES = 64 * 1024  # 编码探测采样字节: 编码特征在文件头部, 64KB 足够判定


def _detect_encodings_from_sample(file_path: Path) -> List[str]:
    """头64KB采样探测编码候选列表 — 2026-11-14 小欧
    原实现 chardet 全量 read_bytes, 超大文件(百M/G级log)探测本身就 OOM; 改采样探测, 与文件大小无关。"""
    try:
        with file_path.open("rb") as fb:
            raw = fb.read(_ENCODING_SAMPLE_BYTES)
    except OSError:
        return []
    enc_list = []
    try:
        import chardet as _chardet
        det = _chardet.detect(raw)
        if det and det.get("encoding") and det.get("confidence", 0) > 0.5:
            enc_list.append(det["encoding"])
    except Exception:
        pass
    for enc in _ENCODING_PRIORITY:
        if enc not in enc_list:
            enc_list.append(enc)
    return enc_list


def safe_read_lines(file_path: Path) -> Optional[Iterator[str]]:
    """流式逐行读取,自动编码检测+多编码尝试+replace兜底 — 小沈 2026-07-05
    2026-11-14 小欧 - 流式化重构(不设大小限制也能正常工作):
      原实现 chardet 全量 read_bytes + readlines 全量载入内存, 超大文件 OOM;
      改为: 头64KB采样探测编码 → 严格解码采样选定首个可用编码 → 逐行流式 yield。
      内存占用 O(行), G级 log 可查; 采样严格解码失败自动降级下一候选编码(保持多编码回退语义),
      全部候选失败则以首个候选 errors='replace' 流式兜底。
    Returns:
        行迭代器; 文件不可读返回 None(调用方迭代前判空)
    """
    enc_list = _detect_encodings_from_sample(file_path)
    if not enc_list:
        return None

    def _stream(enc: str) -> Iterator[str]:
        # 2026-11-14 小欧 - 统一 errors='replace' 流式读取(容错): 采样已 strict 验证编码,
        #   整文件用 replace 保证中途个别非法字节不抛 UnicodeDecodeError(否则整个 grep 搜索失败,
        #   原实现 strict 全量失败会降级 replace 兜底, 流式无法回溯故直接 replace 等价兜底)
        with file_path.open("r", encoding=enc, errors="replace") as f:
            yield from f

    # 采样严格解码: 选定首个能无损解码头64KB的编码(整文件解码错误概率与采样一致)
    chosen = None
    try:
        with file_path.open("rb") as fb:
            sample = fb.read(_ENCODING_SAMPLE_BYTES)
    except OSError:
        return None
    for enc in enc_list:
        try:
            sample.decode(enc)
            chosen = enc
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if chosen is not None:
        return _stream(chosen)
    return _stream(enc_list[0])


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
#       行为不一致(edit对preferred也做替换符检查, read对preferred直接返回)。
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
    has_cjk = has_cjk or any('\u4e00' <= c <= '\u9fff' for c in content[:READ_INER_CJK_SAMPLE])
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
    max_bytes: Optional[int] = None,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """统一编码检测 + 同步文件读取 (content, used_encoding, error) — 小欧 2026-08-09
    合并 read_text_file / edit_text_file 两份私有实现(DRY), 取增强版
    - 候选: preferred 指定→优先尝; 否则 auto 探测编码优先+常见中文编码
    - 每个编码统一做替换符阈值检测(>=3个且>3%) + mojibake 检测, 不达标回退下一编码
    返回 (content, used_encoding, error); 调用方据此比 encoding 与 used_encoding 判断是否回退

    2026-10-21 小欧 - max_bytes: **读前闸门**（防 OOM）。不给 = 全量读（既有行为不变）；
    给了 = 只读前 max_bytes 字节（二进制读后解码，尾部半个多字节字符用替换符兜底），
    大文件不再整份进内存。调用方（read 工具）按需传上限。
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
                    if max_bytes is None:
                        with open(path, 'r', encoding=e, errors='replace') as f:
                            return f.read()
                    # 读前闸门：二进制读前 N 字节再解码（不整文件进内存）
                    with open(path, 'rb') as fb:
                        raw = fb.read(max_bytes)
                    return raw.decode(e, errors='replace')
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
