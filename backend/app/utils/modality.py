# -*- coding: utf-8 -*-
"""模态词归一(无依赖纯函数) — 供 model_service 与 capability 共用, 消除双向延迟导入。

设计: 归一是纯词汇变换, 不属于任何重模块; 下沉到 utils 后两方顶层 import, 依赖单向 — 小欧 2026-11-20
"""
from typing import Any, List

_MODALITY_PREFIX = (("image/", "image"), ("audio/", "audio"), ("video/", "video"), ("text/", "text"))
_MODALITY_ALIAS = {"pdf": "file", "application/pdf": "file"}


def normalize_modalities(values: Any) -> List[str]:
    """模态词归一: MIME 级值与脏值收敛到 {text,image,audio,video,file}, 未知值保序保留不丢能力。"""
    out: List[str] = []
    for v in values if isinstance(values, list) else []:
        if not isinstance(v, str):
            continue
        s = v.strip()
        if not s:
            continue
        low = s.lower()
        canon = _MODALITY_ALIAS.get(low)
        if canon is None:
            canon = next((c for pfx, c in _MODALITY_PREFIX if low.startswith(pfx)), s)
        if canon not in out:
            out.append(canon)
    return out
