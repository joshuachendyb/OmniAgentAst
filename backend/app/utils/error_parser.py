# -*- coding: utf-8 -*-
"""
error_parser — API错误详情提取

从 error_classifier.py 移出,SRP: 解析与分类分离
Author: 小欧 - 2026-06-08
"""

import re


def extract_api_error_detail(error_message: str) -> str:
    """从API错误JSON中提取message/type/param/code
    
    合并自 error_handler._extract_message_and_type,消除分散逻辑
    """
    if not error_message:
        return ""
    json_match = re.search(r'\{["\']?error["\']?\s*:\s*\{([^}]+)\}', str(error_message), re.IGNORECASE)
    if not json_match:
        return ""
    inner = json_match.group(1)
    parts = []
    for key, pattern in [
        ("message", r'["\']?message["\']?\s*:\s*["\']([^"\']+)["\']'),
        ("type", r'["\']?type["\']?\s*:\s*["\']([^"\']+)["\']'),
        ("param", r'["\']?param["\']?\s*:\s*["\']([^"\']*)["\']'),
        ("code", r'["\']?code["\']?\s*:\s*["\']([^"\']+)["\']'),
    ]:
        m = re.search(pattern, inner, re.IGNORECASE)
        if m and (key != "param" or m.group(1)):
            parts.append(f"{key}={m.group(1)}")
    return ", ".join(parts)


__all__ = ["extract_api_error_detail"]
