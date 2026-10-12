# -*- coding: utf-8 -*-
# 模块说明: provider 适配层导出 — 一 provider 一文件注册表 — 小欧 2026-09-23
#   新 provider 接入 = 在本文件 _ADAPTERS 加一行 + adapters/ 加其定制文件; 其余代码零改动。
# 编辑历史: 2026-09-23 小欧 新建
# 编辑历史: 2026-10-11 小欧 键名 opencodeZen→ZenFree(与 config 模板/前端对齐); get_provider_adapter
#   加固: is not None 判空 + 回落告警去歧义/同名去重(防假值对象/大小写漂移静默吞掉 + 防刷屏) — 小欧-2026-10-11

from typing import Dict, Set

from app.logger import logger
from app.llm.adapters.base import ProviderAdapter
from app.llm.adapters.opencodeZen import OpencodeZenAdapter

# 模块级默认实例: 未注册 provider 复用同一实例(行为==现状), 避免每次 new — 小欧 2026-09-23
_DEFAULT_ADAPTER: ProviderAdapter = ProviderAdapter()

_ADAPTERS: Dict[str, ProviderAdapter] = {
    "ZenFree": OpencodeZenAdapter(),
}

# 已告警过的无专属适配器厂商(同名只警告一次, 防刷屏) — 小欧 2026-10-11
_warned_providers: Set[str] = set()


def get_provider_adapter(provider: str) -> ProviderAdapter:
    """按 provider 名返回适配实例; 无专属适配器则用通用基类(行为==现状) — 小欧 2026-09-23

    Args:
        provider: Provider 名称(大小写敏感, 须与 config.yaml providers 键名一致)
    Returns:
        _ADAPTERS 中注册的专属适配实例; 未注册则返回 _DEFAULT_ADAPTER
    """
    adapter = _ADAPTERS.get(provider)
    if adapter is not None:
        return adapter
    # 2026-10-11 小欧(北京老陈) - 文案去歧义 + 同名去重: 原"未注册 X, 回落默认基类(已注册: ...)"
    #   易读成"基类也是已注册的"; 改措辞区分"无专属适配器/已有专属适配器的厂商"。且按 provider
    #   名去重, 每名只警告一次 — 未适配厂商是常态(通用基类本就支持), 每次调用刷屏成噪音。
    if provider not in _warned_providers:
        _warned_providers.add(provider)
        logger.warning(
            "[provider] '%s' 无专属适配器, 使用通用基类; 已有专属适配器的厂商: %s",
            provider, list(_ADAPTERS.keys())
        )
    return _DEFAULT_ADAPTER