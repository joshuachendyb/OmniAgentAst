# -*- coding: utf-8 -*-
"""
secret_utils — 密钥/敏感值判定的公用函数（全局层）

编辑历史:
  2026-09-26 - 小欧 - [72]第二章(2.4 配套·DRY): 新建。抽出 is_blank_secret() 供两处复用，
    避免第三次出现"key 空白判定"的不一致写法:
      ① lifecycle/validation.py:52 原为 `not isinstance(api_key, str) or api_key.strip() == ""`
      ② model/resolver.py 原为 `(_pv_cfg.get("api_key") or "").strip() or None`
    二者语义完全相同（空/纯空白 = 未配置），此前是两处独立写法 —— 本函数收口为唯一权威。
    依据: AGENTS.md 公用函数规范（先查后建/分层存放/及时更新 FUNCTIONS.md）——
    该判定跨 lifecycle 与 model 两域，故置全局层 app/utils/（非 agent_utils/ 非 toolhelper/）。
"""
from typing import Any


def is_blank_secret(value: Any) -> bool:
    """判定密钥/敏感值是否为"未配置"（空、None、纯空白均算未配置）。

    语义来源 [72]第二章：key 空白就是空白，不得回落、不得用别的 provider 的 key 顶替
    （"key 空白即失败"的一致语义）。调用方据此决定"报错"或"跳过不写"。

    Args:
        value: 待判定的密钥值（任意类型；非字符串按未配置处理）

    Returns:
        True = 未配置（None / 空串 / 纯空白 / 非字符串）
        False = 已配置（非空字符串，strip 后仍有内容）

    Examples:
        >>> is_blank_secret(None)
        True
        >>> is_blank_secret("")
        True
        >>> is_blank_secret("   \\n")
        True
        >>> is_blank_secret("sk-abc")
        False
    """
    if not isinstance(value, str):
        return True
    return value.strip() == ""
