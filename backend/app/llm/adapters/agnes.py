# -*- coding: utf-8 -*-
"""agnes 厂商适配器 — 生图/生视频请求体方言 — 小欧 2026-11-20

承载 agnes-image-2.x / agnes-video-2.5 的厂商特有方言(相对 general 基类):
  生图 size 档位+ratio、return_base64 顶层、response_format 放 extra_body; image 单串/多数组。
  基类只放通用字段, agnes 方言全在本 adapter — 小欧 2026-11-20
"""
from typing import Dict, Optional

from app.llm.adapters.base import ProviderAdapter


class AgnesAdapter(ProviderAdapter):
    """agnes 生成方言适配器 — 小欧 2026-11-20"""

    @staticmethod
    def prepare_image_body(body: Dict, *, size: Optional[str] = None,
                           ratio: Optional[str] = None,
                           image_refs: Optional[list] = None,
                           return_base64: bool = False,
                           response_format: Optional[str] = None) -> Dict:
        """agnes 生图方言: 档位 size+ratio, image 单串/多数组, return_base64 顶层, response_format 入 extra_body。"""
        if size:
            body["size"] = size
            if ratio:
                body["ratio"] = ratio
        if image_refs:
            body["image"] = image_refs[0] if len(image_refs) == 1 else image_refs
        if return_base64:
            body["return_base64"] = True
        if response_format:
            body.setdefault("extra_body", {})["response_format"] = response_format
        return body
