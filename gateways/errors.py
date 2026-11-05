# -*- coding: utf-8 -*-
"""errors.py — 错误信封（纯函数）。对齐: 4.7 错误模型 / 4.8.4 信封纪律。

编写人: 小欧    创建时间: 2026-11-05 08:31:00
"""
from __future__ import annotations

# 头里的 Retry-After 一律封顶 30 s（4.7 规则 3: 宿主对带头 429 的等待不封顶,
# free-limit 冷却约 1 h 绝不能透传到头; 冷却值只在网关内存里给 R5 用）。
RETRY_AFTER_CAP_S = 30.0

# R4 计数只认这三类（7.2.2: 确定性错误 region/auth/model-not-found/context-too-long
# 重启不解决, 不计失败）
RESTARTABLE_TYPES = {"network", "timeout", "server"}


def cap_retry_after(seconds):
    """头值封顶; ≤0 视为不给头。"""
    if not seconds or seconds <= 0:
        return None
    return round(min(float(seconds), RETRY_AFTER_CAP_S), 1)


def make_error(status, etype, message, detail="", retry_after_s=None):
    """4.8.4 统一信封: {"error":{"message","type"[,"detail"]}}。

    返回 (status, headers, body)。要求:
      - message 必含可执行信息, 禁"模型报错"空话（4.7 硬性要求）;
      - detail 收下游原文, 截 500 字（宿主不单独读, 但整包错误体会被其记日志排障）;
      - Retry-After 只给 429 且值 ≤ 30 s。
    """
    err = {"message": str(message), "type": str(etype)}
    if detail:
        err["detail"] = str(detail)[:500]
    headers = {}
    ra = cap_retry_after(retry_after_s)
    if ra is not None:
        headers["Retry-After"] = str(int(ra)) if ra == int(ra) else str(ra)
    return int(status), headers, {"error": err}


# 下游错误对象 → 统一分派 dict 的解读（from_downstream）属下游方言, v6.7 起
# 下沉到 vendor\opencode\driver.map_error（4.7 表映射纪律原文随驱动走, 9.1.5）;
# 通用层只认驱动返回的 {"status","type","message","detail",
# "internal_cooldown_ms"} 形状 —— errors.py 对具体错误形状零知识（3.5 SPI/D25）。

