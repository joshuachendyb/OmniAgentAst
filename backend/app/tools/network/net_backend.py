# -*- coding: utf-8 -*-
# 2026-11-23 小欧 - 网络检索后端统一调度底座: 错误分类、分级冷却、链级共享预算、尝试轨迹(S2)
# 编辑历史:
# 2026-11-23 小欧 - S2 新建: 调度统一解析各自写的插槽底座 — 只做共性编排, 不含任何 provider 业务逻辑;
#   classify 将网络异常归一为错误码; run_chain 按序尝试后端(跳过冷却→调用→分类→记冷却→记attempts);
#   取消类异常(CancelledError/KeyboardInterrupt/SystemExit)穿透, 不当作后端失败继续打下一家 — 小欧-2026-11-23
# 2026-11-23 小欧 - 三堂会审整改: ①错误码迁 tool_constants 单一真源并统一为 ERR_NET_* 命名(裸常量与全仓风格及
#   status.code 口径不一致); ②classify 增 NETWORK(本地不可达, 不冷却)与 INTERNAL(本侧缺陷, 不冷却), 不再把
#   ConnectError/TypeError 一律当上游故障冷却 120s; ③mark_failure 只冷却分级表内错误码, 冷却记录带原因码,
#   cooldown_left 换 cooldown_info 以便归因; ④run_chain 增链级共享预算 budget_sec, 逐家传剩余时间, 预算耗尽即停
#   —— 原各家硬超时之和(25+25+15×2=80s)会超外层 60s 保险丝, 整链 attempts 与已得结果全部丢失 — 小欧-2026-11-23
# 2026-11-23 小欧 - 真实外网端到端实测补充: anyio.EndOfStream(服务端读完响应头即断开)不是 httpx.HTTPError,
#   原落 INTERNAL 把上游断连谎报成本侧缺陷且不冷却; 增 _TRANSPORT_MODULES 判定归 UPSTREAM_BROKEN,
#   同时异常展示串去空尾巴("EndOfStream: " → "EndOfStream") — 小欧-2026-11-23
"""网络检索后端调度底座 - 只做共性编排，不含任何 provider 业务逻辑。"""
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

from app.logger import logger
from app.tools.tool_constants import (  # 2026-11-23 小欧 - 错误码单一真源, 本模块不再自定义常量
    ERR_NET_BAD_INPUT,
    ERR_NET_INTERNAL,
    ERR_NET_NEED_SETUP,
    ERR_NET_NETWORK,
    ERR_NET_NOT_FOUND,
    ERR_NET_RATE_LIMITED,
    ERR_NET_TIMEOUT,
    ERR_NET_UPSTREAM_BROKEN,
)

# 命中即停：换后端无意义。限流是单 provider 配额，只冷却当前后端后继续降级。
# 阶段一搜索链不产生 BAD_INPUT/NOT_FOUND(HTTP 400/404 归 UPSTREAM_BROKEN 换家)，终止码保留给 fetch 链/阶段二。
FINAL_CODES = frozenset({ERR_NET_BAD_INPUT, ERR_NET_NOT_FOUND})

# 2026-11-23 小欧 - 只有本表内的错误码才记冷却: NETWORK(本地网络)与 INTERNAL(本侧缺陷)不是上游的错,
#   冷却它们会让用户修好网络/重启后仍要干等两分钟
DEFAULT_COOLDOWN_SECONDS = {
    ERR_NET_RATE_LIMITED: 3600,
    ERR_NET_UPSTREAM_BROKEN: 120,
    ERR_NET_TIMEOUT: 60,
    ERR_NET_NEED_SETUP: 60,
}

# 2026-11-23 小欧 - httpx 底层传输栈(top-level 模块名): 这些异常未被 httpx 包装成 HTTPError,
#   真实外网已观测到 anyio.EndOfStream(服务端读完头就断开) 漏到 classify 落成 INTERNAL
_TRANSPORT_MODULES = frozenset({"httpcore", "anyio", "h11", "h2"})


def _exc_text(exc: BaseException) -> str:
    """异常展示串：无 message 的异常(如 anyio.EndOfStream)只给类名，避免出现 "EndOfStream: " 空尾巴。"""
    detail = str(exc).strip()
    return f"{type(exc).__name__}: {detail}" if detail else type(exc).__name__


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
    """把任意后端异常归一为 NetError。

    分类口径(2026-11-23 小欧 整改):
      HTTP 429 → RATE_LIMITED(带 Retry-After) / 401·403 → NEED_SETUP / 其余状态码 → UPSTREAM_BROKEN
      ConnectError·ConnectTimeout → NETWORK —— 连不上是本地网络问题, 换家但不冷却
      TimeoutException → TIMEOUT
      其余 httpx 传输/协议异常 → UPSTREAM_BROKEN —— 上游响应确实坏了, 冷却换家
      httpx 未包装的底层传输异常(httpcore.*/anyio.EndOfStream 等) → UPSTREAM_BROKEN —— 连接级故障同上
      非 httpx 异常 → INTERNAL —— 本侧代码缺陷, 不冷却(冷却等于把 bug 藏起来)
    """
    if isinstance(exc, NetError):
        return exc
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 429:
            return NetError(ERR_NET_RATE_LIMITED, "HTTP 429 限流",
                            _retry_after_seconds(exc.response.headers.get("retry-after")))
        if status in (401, 403):
            return NetError(ERR_NET_NEED_SETUP, f"HTTP {status} 鉴权失败")
        # 400/404 是该 provider 对请求/端点的意见, 不代表别家也不行, 一律冷却换家重试
        return NetError(ERR_NET_UPSTREAM_BROKEN, f"HTTP {status}")
    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
        return NetError(ERR_NET_NETWORK, "连接失败")
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return NetError(ERR_NET_TIMEOUT, "请求超时")
    if isinstance(exc, httpx.HTTPError):
        return NetError(ERR_NET_UPSTREAM_BROKEN, _exc_text(exc))
    # httpx 未包装的底层传输异常(anyio.EndOfStream = 服务端中途断开、httpcore.* 等): 同属连接级故障,
    #   归 UPSTREAM_BROKEN; 落到 INTERNAL 会把上游断连谎报成"本侧代码缺陷"且不记冷却
    if type(exc).__module__.split(".", 1)[0] in _TRANSPORT_MODULES:
        return NetError(ERR_NET_UPSTREAM_BROKEN, _exc_text(exc))
    return NetError(ERR_NET_INTERNAL, _exc_text(exc))


@dataclass(frozen=True)
class Backend:
    """后端描述。call 签名固定为 (*args, remaining_seconds)，remaining 为链级预算剩余(None=不限)。"""

    id: str
    call: Callable[..., Any]


# 2026-11-23 小欧 - 默认单进程内存冷却；多 worker 部署时替换为落盘 + 文件锁。
# 值=(到期 monotonic 时刻, 致冷却的错误码) —— 带原因码才能在"全部冷却"时如实归因
_COOLDOWNS: Dict[Tuple[str, str], Tuple[float, str]] = {}


def cooldown_info(kind: str, backend_id: str) -> Tuple[float, str]:
    """返回(剩余冷却秒数, 致冷却的错误码)；未冷却或已过期返回 (0.0, "")。"""
    key = (kind, backend_id)
    record = _COOLDOWNS.get(key)
    if record is None:
        return 0.0, ""
    until, code = record
    if until <= time.monotonic():
        _COOLDOWNS.pop(key, None)
        return 0.0, ""
    return until - time.monotonic(), code


def mark_failure(kind: str, backend_id: str, error: NetError) -> None:
    """按错误码记录冷却；Retry-After 优先于分级缺省；分级表外码不冷却。"""
    seconds = error.retry_after
    if seconds is None:
        seconds = DEFAULT_COOLDOWN_SECONDS.get(error.code)
    if not seconds or seconds <= 0:
        return
    _COOLDOWNS[(kind, backend_id)] = (time.monotonic() + seconds, error.code)


async def run_chain(
    kind: str,
    chain: Tuple[Backend, ...],
    args: Tuple[Any, ...],
    budget_sec: Optional[float] = None,
) -> Dict[str, Any]:
    """按序尝试后端；返回 items/backend/attempts/failures/error/budget_exhausted，不向外抛业务异常(取消类穿透)。

    budget_sec: 链级共享预算(秒)。每家拿到"剩余预算"作为自己的硬超时, 预算耗尽立即停 ——
      保证内层降级链跑在一条统一时间线内, 不会被外层保险丝从中截断而丢失 attempts 与已得结果。
    """
    deadline = time.monotonic() + budget_sec if budget_sec and budget_sec > 0 else None
    attempts: List[dict] = []
    failures: List[dict] = []
    skipped: List[Tuple[float, str, str]] = []
    last_error: Optional[NetError] = None
    budget_exhausted = False

    for backend in chain:
        left, cool_code = cooldown_info(kind, backend.id)
        if left > 0:
            attempts.append({"backend": backend.id, "result": "SKIPPED", "code": cool_code,
                             "retry_after_seconds": int(left)})
            skipped.append((left, cool_code, backend.id))
            continue

        remaining = None if deadline is None else deadline - time.monotonic()
        if remaining is not None and remaining <= 0:
            attempts.append({"backend": backend.id, "result": "BUDGET_EXHAUSTED"})
            last_error = NetError(ERR_NET_TIMEOUT, f"搜索总预算{budget_sec:.0f}秒已耗尽")
            budget_exhausted = True
            break

        t0 = time.monotonic()
        try:
            items = await backend.call(*args, remaining)
        except Exception as exc:  # noqa: BLE001 — 只捕 Exception: 取消类必须穿透
            # CancelledError/KeyboardInterrupt/SystemExit 是 BaseException 子类, 天然不在此处,
            # 请求取消不能被当成后端失败继续打下一家
            error = classify(exc)
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            attempts.append({"backend": backend.id, "result": error.code, "code": error.code,
                             "message": error.message[:200], "elapsed_ms": elapsed_ms})
            if error.code in FINAL_CODES:
                return {"items": [], "backend": None, "attempts": attempts, "failures": failures,
                        "error": error, "budget_exhausted": False}
            mark_failure(kind, backend.id, error)
            logger.warning(f"[net_chain:{kind}] 后端 {backend.id} 失败 {error.code}: {error.message[:160]}")
            failures.append({"backend": backend.id, "code": error.code, "message": error.message[:200]})
            last_error = error
            continue

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        if not items:
            attempts.append({"backend": backend.id, "result": "EMPTY", "elapsed_ms": elapsed_ms})
            continue
        # 成功也入轨迹: 原来成功后端不进 attempts, 线上无法回答"这次是谁给的"
        attempts.append({"backend": backend.id, "result": "OK", "items": len(items), "elapsed_ms": elapsed_ms})
        return {"items": list(items), "backend": backend.id, "attempts": attempts,
                "failures": failures, "error": None, "budget_exhausted": False}

    if budget_exhausted:
        return {"items": [], "backend": None, "attempts": attempts, "failures": failures,
                "error": last_error, "budget_exhausted": True}
    # 一条结果都没有, 且存在失败或冷却 → 必须报真实原因, 不能给用户"成功 0 条"
    #   (原实现只在"全失败"时报警, 一家失败+一家空结果就退化成 success 0, 故障被静默吞掉)
    if failures or skipped:
        error = last_error
        if error is None:
            soonest_left, soonest_code, _ = min(skipped)
            error = NetError(soonest_code, f"全部后端冷却中({soonest_code})", soonest_left)
        return {"items": [], "backend": None, "attempts": attempts, "failures": failures,
                "error": error, "budget_exhausted": False}
    # 全链无异常但均无结果 → 不算错误, 保持 success 0 条语义
    return {"items": [], "backend": None, "attempts": attempts, "failures": failures,
            "error": None, "budget_exhausted": False}
