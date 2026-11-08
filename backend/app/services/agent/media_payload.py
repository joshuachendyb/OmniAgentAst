# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-08 小欧 新建: 媒体附件 → 请求 part 唯一构造点(视觉通道原内联逻辑迁入) — 小欧-2026-11-08

"""services.agent.media_payload — 媒体附件 → 请求 content part 的唯一构造点。

设计边界:
  1. 当前只实现内联通道(base64 data URI); 厂商要求外链/预上传时在本模块扩展, 调用方不变;
  2. 失败一律返回 (None, 原因), 由调用方退化为一行文字, 不抛异常断轮;
  3. base64 按 (路径, mime) 复用: 同一任务多轮调用不重复编码, 最多 8 份(内存上限约 22MB)。
"""
import asyncio
import base64
from typing import Any, Dict, Optional, Tuple

from app.logger import logger

# 单文件内联上限: base64 膨胀 4/3, 2MB 原图 → ~2.7MB 文本, 再大既慢又易撞窗口
INLINE_MAX_BYTES = 2 * 1024 * 1024
_DATA_URL_MAX = 8
_data_url_cache: Dict[Tuple[str, str], str] = {}


async def _data_url(stored_path: str, mime: str) -> str:
    """读文件 + base64 编码, 经 asyncio.to_thread 卸载出事件循环(原同步 open 阻塞)。"""
    key = (stored_path, mime)
    cached = _data_url_cache.get(key)
    if cached:
        return cached

    def _read_and_encode() -> str:
        with open(stored_path, "rb") as fh:
            return f"data:{mime};base64,{base64.b64encode(fh.read()).decode('ascii')}"

    url = await asyncio.to_thread(_read_and_encode)
    if len(_data_url_cache) >= _DATA_URL_MAX:
        _data_url_cache.pop(next(iter(_data_url_cache)), None)  # 最旧淘汰
    _data_url_cache[key] = url
    return url


async def build_media_part(kind: str, attachment: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], str]:
    """附件 → content part; 不可内联时返回 (None, 原因)。

    kind=image 产出 OpenAI image_url part(url 为 data URI); file/video 待线格式接入后在此扩展。
    """
    if kind != "image":
        return None, "该类型尚未接入请求体"
    size = int(attachment.get("size") or 0)
    if size > INLINE_MAX_BYTES:
        return None, f"文件超过 {INLINE_MAX_BYTES // (1024 * 1024)}MB 未随消息发送"
    try:
        url = await _data_url(attachment["stored_path"], attachment.get("mime") or "image/png")
    except OSError as e:
        logger.warning(f"[media] 读文件失败 path={attachment.get('stored_path')} err={e}")
        return None, "文件不可读"
    return {"type": "image_url", "image_url": {"url": url}}, ""
