# -*- coding: utf-8 -*-
# 模块说明: provider 适配层导出 — 一 provider 一文件注册表 — 小欧 2026-09-23
#   新 provider 接入 = 在本文件 _ADAPTERS 加一行 + adapters/ 加其定制文件; 其余代码零改动。
# 编辑历史: 2026-09-23 小欧 新建

from typing import Dict

from app.llm.adapters.base import ProviderAdapter
from app.llm.adapters.opencodeZen import OpencodeZenAdapter

# 模块级默认实例: 未注册 provider 复用同一实例(行为==现状), 避免每次 new — 小欧 2026-09-23
_DEFAULT_ADAPTER: ProviderAdapter = ProviderAdapter()

_ADAPTERS: Dict[str, ProviderAdapter] = {
    "opencodeZen": OpencodeZenAdapter(),
}


def get_provider_adapter(provider: str) -> ProviderAdapter:
    """按 provider 名返回适配实例; 未注册(无特殊握手)返回默认基类(行为==现状) — 小欧 2026-09-23"""
    return _ADAPTERS.get(provider) or _DEFAULT_ADAPTER