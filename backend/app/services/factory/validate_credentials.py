# -*- coding: utf-8 -*-
"""
validate_credentials — 从 factory.py 拷出

拷贝来源: factory.py 第147-161行
"""

from typing import Tuple, List


def validate_credentials(ai_config: dict, final_provider: str) -> Tuple[list, list]:
    """拷贝自 factory.py 第147-161行"""
    errors = []
    warnings = []
    selected_provider_config = ai_config.get(final_provider, {})
    api_key = selected_provider_config.get("api_key")
    if not api_key:
        errors.append(f"provider '{final_provider}' 缺少 api_key 配置")
    elif not isinstance(api_key, str) or api_key.strip() == "":
        errors.append(f"provider '{final_provider}' 的 api_key 为空")
    api_base = selected_provider_config.get("api_base")
    if not api_base:
        warnings.append(f"provider '{final_provider}' 未配置 api_base，将使用默认值")
    return errors, warnings
