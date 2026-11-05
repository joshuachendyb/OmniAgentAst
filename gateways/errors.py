# -*- coding: utf-8 -*-
"""errors.py — 错误信封与网关异常型。

编写人: 小欧    创建时间: 2026-11-05 08:31:00

编辑历史:
  2026-11-05 GatewayError 收归本文件(原 cli_manager.GateError) -- 小欧
  2026-11-05 Retry-After 收敛为"仅 429 + 整秒"; 原实现任何状态码都带头且可吐出 0.5 -- 小欧
  2026-11-05 注释规范化: 压缩到两行内并统一署名日期 -- 小欧
"""
from __future__ import annotations

# Retry-After 头封顶 30 s: 宿主对带头 429 的等待不封顶, 1 h 冷却绝不能透传。
# 冷却值只在网关内存里给冷却判定用。— 小欧 2026-11-05
RETRY_AFTER_CAP_S = 30.0

# 只这三类计入重启失败; 确定性错误重启不解决, 不计。— 小欧 2026-11-05
RESTARTABLE_TYPES = {"network", "timeout", "server"}


class GatewayError(Exception):
    """网关唯一异常型: 状态码 + 错误类型, 由 gateway 转统一信封。— 小欧 2026-11-05"""

    def __init__(self, status, etype, message, detail="", retry_after_s=None):
        super().__init__(message)
        self.status, self.etype = status, etype
        self.message, self.detail = message, detail
        self.retry_after_s = retry_after_s


def cap_retry_after(seconds):
    """头值封顶 30 s 并取整秒（HTTP 只允许整秒）; ≤0 视为不给头。— 小欧 2026-11-05"""
    if not seconds or seconds <= 0:
        return None
    return max(1, int(round(min(float(seconds), RETRY_AFTER_CAP_S))))


def make_error(status, etype, message, detail="", retry_after_s=None):
    """统一信封: 返回 (status, headers, body); Retry-After 只给 429 且 ≤30 s。— 小欧 2026-11-05"""

    err = {"message": str(message), "type": str(etype)}
    if detail:
        err["detail"] = str(detail)[:500]
    headers = {}
    if int(status) == 429:                     # 只有 429 带此头 — 小欧 2026-11-05
        ra = cap_retry_after(retry_after_s)
        if ra is not None:
            headers["Retry-After"] = str(ra)
    return int(status), headers, {"error": err}


# 下游错误对象解读属下游方言, 由驱动 map_error 承担; 通用层只认统一形状。— 小欧 2026-11-05

