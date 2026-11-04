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
    ② 敏感键集合只此一份, 杜绝逐处手写遮蔽;
    ③ 分流: 落盘出口(日志/落库)调用 redact_* 遮蔽; SSE/HITL 展示走原文(用户本人数据, 不落盘)。
"""
from typing import Any


# 敏感参数键集合 — 全局唯一权威 — 小欧 2026-10-19
#   命中键的值替换为 "***"。仅"落盘"出口(日志/落库)调用遮蔽; SSE/HITL 展示原文(用户本人数据)。
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

    用于所有"落盘"出口: prompt 日志、聊天历史落库(chat_task_steps / chat_stream_events);
    非 dict / 无敏感键时原样返回(不复制, 零开销); 有敏感键时返回浅拷贝, 不改原对象。
    """
    if not isinstance(params, dict):
        return params
    _hits = SENSITIVE_PARAM_KEYS & params.keys()
    if not _hits:
        return params
    return {k: ("***" if k in SENSITIVE_PARAM_KEYS else v) for k, v in params.items()}


def redact_step_params(step: Any) -> Any:
    """step 落盘脱敏: 顶层 params 与 ActionStep tools[].params 的敏感键→"***", 返回副本不改原对象 — 小欧 2026-10-19

    供落库(chat_task_steps.step_json)与 prompt 日志(整份 step)共用;
    仅落盘点调用; SSE/HITL 展示走原文(用户本人数据)。"""
    if not isinstance(step, dict):
        return step
    if "params" not in step and "tools" not in step:
        return step
    out = dict(step)
    if isinstance(out.get("params"), dict):
        out["params"] = redact_sensitive_params(out["params"])
    _tools = out.get("tools")
    if isinstance(_tools, list):
        out["tools"] = [
            ({**t, "params": redact_sensitive_params(t.get("params"))} if isinstance(t, dict) else t)
            for t in _tools
        ]
    return out
