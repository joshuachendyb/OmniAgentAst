# -*- coding: utf-8 -*-
"""
secret_utils — 密钥/敏感值判定的公用函数（全局层）

编辑历史:
  2026-09-26 - 小欧 - 新建(DRY 配套): 抽出 is_blank_secret() 供两处复用，
    避免第三次出现"key 空白判定"的不一致写法:
      ① lifecycle/validation.py 原为 `not isinstance(api_key, str) or api_key.strip() == ""`
      ② model/resolver.py 原为 `(_pv_cfg.get("api_key") or "").strip() or None`
    二者语义完全相同（空/纯空白 = 未配置），此前是两处独立写法 —— 本函数收口为唯一权威。
    依据: AGENTS.md 公用函数规范（先查后建/分层存放/及时更新 FUNCTIONS.md）——
    该判定跨 lifecycle 与 model 两域，故置全局层 app/utils/（非 agent_utils/ 非 toolhelper/）。
  2026-10-19 - 小欧 - 敏感参数脱敏升格为系统级单一真相源:
    ① 新增 SENSITIVE_PARAM_KEYS(全局层权威集合) 与 redact_sensitive_params();
    ② 日志/ActionStep(SSE+落库)/HITL 确认参数统一调用同一函数, 杜绝逐处手写遮蔽;
    ③ tool_constants.SENSITIVE_FIELDS 改为派生自本集合(单向依赖 tools→utils, 不反向)。
"""
from typing import Any


# 敏感参数键集合 — 全局唯一权威 — 小欧 2026-10-19
#   mask = 就地替换为 "***"（适用日志/SSE/落库/HITL 展示, 值不落明文）
#   HITL 对其中"非目标定位键"(password/token 等)仍按 SENSITIVE_FIELDS 丢弃,
#   connection_string 因需保留"连的是哪个库"的可见性, 只遮蔽不清除。
SENSITIVE_PARAM_KEYS: frozenset = frozenset({
    "password", "token", "api_key", "secret", "authorization", "credential",
    "connection_string",
})


def is_blank_secret(value: Any) -> bool:
    """判定密钥/敏感值是否为"未配置"（空、None、纯空白均算未配置）。

    语义: key 空白就是空白，不得回落、不得用别的 provider 的 key 顶替
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


def redact_sensitive_params(params: Any) -> Any:
    """敏感参数脱敏: SENSITIVE_PARAM_KEYS 中的键值统一替换为 "***" — 小欧 2026-10-19

    用于所有"参数离开内存"的出口: 日志、SSE、聊天历史落库、HITL 确认弹窗;
    非 dict / 无敏感键时原样返回(不复制, 零开销); 有敏感键时返回浅拷贝, 不改原对象。
    """
    if not isinstance(params, dict):
        return params
    _hits = SENSITIVE_PARAM_KEYS & params.keys()
    if not _hits:
        return params
    return {k: ("***" if k in SENSITIVE_PARAM_KEYS else v) for k, v in params.items()}
