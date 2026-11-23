# -*- coding: utf-8 -*-
# 2026-11-23 小欧 - 网络检索后端统一调度底座: 错误分类、分级冷却、尝试轨迹(S2)
# 编辑历史:
# 2026-11-23 小欧 - S2 新建: 调度统一解析各自写的插槽底座 — 只做共性编排, 不含任何 provider 业务逻辑;
#   classify 将网络异常归一为六类错误码; run_chain 按序尝试后端(跳过冷却→调用→分类→记冷却→记attempts);
#   取消类异常(CancelledError/KeyboardInterrupt/SystemExit)穿透, 不当作后端失败继续打下一家 — 小欧-2026-11-23
"""网络检索后端调度底座 - 只做共性编排，不含任何 provider 业务逻辑。"""

import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

BAD_INPUT = "BAD_INPUT"
RATE_LIMITED = "RATE_LIMITED"
UPSTREAM_BROKEN = "UPSTREAM_BROKEN"
TIMEOUT = "TIMEOUT"
NOT_FOUND = "NOT_FOUND"
NEED_SETUP = "NEED_SETUP"

# 命中即停：换后端无意义。限流是单 provider 配额，只冷却当前后端后继续降级。
# 阶段一搜索链不产生 BAD_INPUT/NOT_FOUND(HTTP 400/404 归 UPSTREAM_BROKEN 换家)，终止码保留给 fetch 链/阶段二。
FINAL_CODES = frozenset({BAD_INPUT, NOT_FOUND})

DEFAULT_COOLDOWN_SECONDS = {
    RATE_LIMITED: 3600,
    UPSTREAM_BROKEN: 120,
    TIMEOUT: 60,
    NEED_SETUP: 60,
}


class NetError(Exception):
    """带统一错误码与重试等待的后端异常。"""

    def __init__(self, code: str, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retry_after = retry_after


def _retry_after_seconds(value: Optional[str]) -> Optional[float]:
    """Retry-After 支持秒数与 HTTP-date，无法解析返回 None。"""
    if not value or not value.strip():
        return None
    try:
        return max(0.0, float(value.strip()))
    except ValueError:
        pass
    try:
        from datetime import timezone

        when = parsedate_to_datetime(value.strip())
        if when is None:
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return max(0.0, when.timestamp() - time.time())
    except (TypeError, ValueError, OverflowError):
        return None


def classify(exc: BaseException) -> NetError:
    """把任意后端异常归一为 NetError。"""
    if isinstance(exc, NetError):
        return exc
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 429:
            return NetError(RATE_LIMITED, "HTTP 429", _retry_after_seconds(exc.response.headers.get("retry-after")))
        if status in (401, 403):
            return NetError(NEED_SETUP, f"HTTP {status}")
        # 400/404 是该 provider 对请求/端点的意见, 不代表别家也不行, 一律冷却换家重试
        return NetError(UPSTREAM_BROKEN, f"HTTP {status}")
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return NetError(TIMEOUT, "请求超时")
    if isinstance(exc, httpx.ConnectError):
        return NetError(UPSTREAM_BROKEN, "连接失败")
    return NetError(UPSTREAM_BROKEN, f"{type(exc).__name__}: {exc}")


@dataclass(frozen=True)
class Backend:
    id: str
    call: Callable[..., Any]


# 2026-11-23 小欧 - 默认单进程内存冷却；多 worker 部署时替换为落盘 + 文件锁
_COOLDOWNS: Dict[Tuple[str, str], float] = {}


def cooldown_left(kind: str, backend_id: str) -> float:
    """返回剩余冷却秒数，未冷却或已过期返回 0。"""
    key = (kind, backend_id)
    until = _COOLDOWNS.get(key)
    if until is None:
        return 0.0
    if until <= time.monotonic():
        _COOLDOWNS.pop(key, None)
        return 0.0
    return until - time.monotonic()


def mark_failure(kind: str, backend_id: str, error: NetError) -> None:
    """按错误码记录冷却；Retry-After 优先于分级缺省。"""
    seconds = error.retry_after
    if seconds is None:
        seconds = DEFAULT_COOLDOWN_SECONDS.get(error.code, 60)
    _COOLDOWNS[(kind, backend_id)] = time.monotonic() + seconds


async def run_chain(kind: str, chain: Tuple[Backend, ...], args: Tuple[Any, ...]) -> Dict[str, Any]:
    """按序尝试后端；返回 items/backend/attempts/error，不向外抛业务异常（取消类异常穿透）。"""
    attempts: List[dict] = []
    last_error: Optional[NetError] = None
    cooled_all = True
    for backend in chain:
        left = cooldown_left(kind, backend.id)
        if left > 0:
            attempts.append({"backend": backend.id, "result": "SKIPPED", "retry_after_seconds": int(left)})
            continue
        cooled_all = False
        try:
            items = await backend.call(*args)
        except Exception as exc:
            # 只捕 Exception: CancelledError/KeyboardInterrupt/SystemExit 必须穿透,
            # 请求取消不能被当成后端失败继续打下一家
            error = classify(exc)
            attempts.append({"backend": backend.id, "result": error.code, "message": error.message})
            if error.code in FINAL_CODES:
                return {"items": [], "backend": None, "attempts": attempts, "error": error}
            mark_failure(kind, backend.id, error)
            last_error = error
            continue
        if not items:
            attempts.append({"backend": backend.id, "result": "EMPTY"})
            continue
        return {"items": list(items), "backend": backend.id, "attempts": attempts, "error": None}
    if last_error is not None:
        return {"items": [], "backend": None, "attempts": attempts, "error": last_error}
    if cooled_all:
        return {"items": [], "backend": None, "attempts": attempts,
                "error": NetError(RATE_LIMITED, "所有搜索引擎冷却中")}
    # 全部后端无异常但均无结果: 不算错误, 保持 success 0 条的现状语义(禁止把空结果升级为 error)
    return {"items": [], "backend": None, "attempts": attempts, "error": None}
