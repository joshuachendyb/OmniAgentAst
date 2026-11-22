# -*- coding: utf-8 -*-
"""sensenova 厂商适配器 — 生图/生视频请求体方言 — 小欧 2026-11-20

职责: 承载 sensenova 相对 OpenAI/agnes 协议的生成方言差异, 只覆写生成钩子, 其余继承基类。
  生图 size 用 WIDTHxHEIGHT(32倍数, 512~4096)而非档位; 无 ratio 字段(比例隐含在尺寸里);
  有参考图(i2i)走 /images/edits 端点且用 images:[{image_url:...}] 方言(image 传字符串会 RemoteProtocolError)。
  视频方言当前与 agnes 一致(继承基类)。
编辑历史: 2026-11-20 小欧 新建: prepare_image_body 覆写(档位→像素换算+4K钳制到4096上限) — 小欧-2026-11-20
编辑历史: 2026-11-22 小欧 加 image_endpoint 覆写(有参考图→/images/edits); prepare_image_body 有参考图改 images:[{image_url}] 方言 — 小欧-2026-11-22
"""
from typing import Dict, Optional

from app.llm.adapters.base import ProviderAdapter

# 档位×宽高比→像素(sensenova 用)。各值为 32 倍数。4K 非1:1 超 4096 上限 → 钳制到 4096(见 _clamp)。
_SENSENOVA_TIER_PIXELS = {
    "1K": {"1:1": "1024x1024", "3:4": "864x1152", "4:3": "1152x864", "16:9": "1312x736",
           "9:16": "736x1312", "2:3": "832x1248", "3:2": "1248x832", "21:9": "1568x672"},
    "2K": {"1:1": "2048x2048", "3:4": "1728x2304", "4:3": "2304x1728", "16:9": "2624x1472",
           "9:16": "1472x2624", "2:3": "1664x2496", "3:2": "2496x1664", "21:9": "3136x1344"},
    "3K": {"1:1": "3072x3072", "3:4": "2592x3456", "4:3": "3456x2592", "16:9": "3936x2208",
           "9:16": "2208x3936", "2:3": "2496x3744", "3:2": "3744x2496", "21:9": "4704x2016"},
    "4K": {"1:1": "4096x4096", "3:4": "3456x4608", "4:3": "4608x3456", "16:9": "5248x2944",
           "9:16": "2944x5248", "2:3": "3328x4992", "3:2": "4992x3328", "21:9": "6272x2688"},
}
_SENSENOVA_MAX_EDGE = 4096  # 厂商文档: 宽高均在 [512, 4096]


class SensenovaAdapter(ProviderAdapter):
    """sensenova 生成方言适配器 — 小欧 2026-11-20"""

    @staticmethod
    def image_endpoint(has_refs: bool) -> str:
        """sensenova 端点方言: 带参考图=图片编辑走 /images/edits, 否则继承基类 generations — 小欧-2026-11-22"""
        return "/images/edits" if has_refs else ProviderAdapter.image_endpoint(has_refs)

    @staticmethod
    def _clamp_size(pixel: str) -> str:
        """把 WIDTHxHEIGHT 的每边钳制到 4096 上限, 并按 32 倍数取整(sensenova 硬性要求)。"""
        try:
            w, h = (int(x) for x in pixel.lower().split("x"))
        except (ValueError, AttributeError):
            return pixel  # 非 WIDTHxHEIGHT 写法原样交厂商判
        w = min(w, _SENSENOVA_MAX_EDGE)
        h = min(h, _SENSENOVA_MAX_EDGE)
        w = max(512, (w // 32) * 32)
        h = max(512, (h // 32) * 32)
        return f"{w}x{h}"

    @staticmethod
    def prepare_image_body(body: Dict, *, size: Optional[str] = None,
                           ratio: Optional[str] = None,
                           image_refs: Optional[list] = None,
                           return_base64: bool = False,
                           response_format: Optional[str] = None) -> Dict:
        """sensenova 生图方言: 档位→WIDTHxHEIGHT(钳制4096), 无 ratio; 有参考图走 images:[{image_url}] 方言。"""
        if size:
            tier = _SENSENOVA_TIER_PIXELS.get(size.upper())
            pixel = None
            if tier:
                pixel = tier.get(ratio) or tier.get("1:1")
            body["size"] = SensenovaAdapter._clamp_size(pixel) if pixel else size
            # 注意: sensenova 没有 ratio 字段, 比例已隐含在 WIDTHxHEIGHT 中, 不下发 ratio
        if image_refs:
            # 有参考图=图片编辑(/images/edits): sensenova 只认 images:[{image_url:...}], 非 image 数组 — 小欧-2026-11-22
            body["images"] = [{"image_url": ref} for ref in image_refs]
        # sensenova 的 b64 通过 response_format=b64_json(放 extra_body)控制; return_base64 非其字段, 忽略
        if response_format:
            body.setdefault("extra_body", {})["response_format"] = response_format
        elif return_base64:
            body.setdefault("extra_body", {})["response_format"] = "b64_json"
        return body
