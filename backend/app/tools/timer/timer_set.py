# -*- coding: utf-8 -*-
# 2026-10-04 小欧 - obs方案A: 删action.target(params承载目标)+document params file_path→path
# 编辑历史:
# 2026-07-31 - 小欧 - 新增 CALLBACK_MAX_LENGTH 限制(4096字符), 防止回调内容过长导致执行失败
# 2026-08-05 - 小欧 - 修复: _invoke_timer_callback 外层 except httpx.TimeoutException 在文本提醒(log_message)分支引用未导入的 httpx, 分支异常时触发 UnboundLocalError 掩盖真实错误; 将该 except 移入 http 分支内部(httpx 导入处), 文本分支异常统一由外层 except Exception 捕获
# 2026-08-08 - 小欧 - 全程统一本地时区: 落盘/事件时间戳 astimezone()→本地ISO无Z(L39/L113/L117/L127/L143); trigger_at 改 naive 本地
# 2026-08-21 - 小欧 - 单口径落地(按文档 diff设计落地): _timer_cb 触发状态 UPDATE 与 INSERT OR REPLACE
#   两处 except 静默 pass→logger.error 提级留痕(带 timer_id+失败后果说明), 内存定时器行为零改动, 仅补可追溯性
# 2026-08-21 - 小欧 - 任务计数单口径(按文档 diff设计落地): 两处 db.get_conn("operations")→db.get_conn("timers"),
#   定时器写入切换到 timers.db 独立库(SRP); 文档漏 timer_list.py 同款修改(读者一致性) — 小欧 2026-08-21
# 2026-10-12 小欧 - tool_zh改短名词（北京老陈令）: 设置定时器→设定时器
# 2026-11-25 商量 - 持久调度器(3.5): ①timers 落 session_id(取自 tools/context 发起会话ID), 触发时经注入回调
#   resume_session_with_notice 回会话建任务("到点自己干"), 无 session 或无回调时维持原 log/http; ②抽出 _schedule_handle
#   (call_later 注册+callbacks 登记)供 timer_set 与 rebuild_timers_from_db 共用(DRY); ③新增 rebuild_timers_from_db:
#   启动扫描 status='active' 重建未到期定时器、过期立即补触发(timers 表为跨重启唯一真源); ④新增 set_timer_resume_callback
#   供 app 层注入(tools 层禁 import services, 用回调注入解越层)
# 2026-11-25 小欧 - 三堂会审整改: ①resume 返回 False(会话忙/建任务失败)时补直接投递兜底, 此前该分支回调内容
#   静默丢失(只有 executed_as=resume_task_failed 一个字段, 无日志无投递); ②_schedule_handle 增 created_at 入参,
#   rebuild 透传 DB 原始创建时间(此前重启后定时器列表显示的"创建时间"变成重启时刻); ③非法 trigger_at 行置
#   status='invalid'(此前永久滞留 active, 每次重启重复告警且永不触发); ④重建日志措辞改为"已排入"(补触发是
#   call_later(0) 异步执行, 计数不含投递结果)
"""
timer_set — 设置定时器
【2026-06-22 小健】从 timer_tools.py 拆分为独立文件
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import asyncio
import math
import time as _time_mod
from datetime import datetime, timedelta
from typing import Any, Dict

from app.db import db
from app.logger import logger
from app.tools.context import (
    get_current_session_id,  # 2026-11-25 商量 - 发起会话ID(定时器触发回会话建任务)
)
from app.tools.tool_constants import ERR_TIMER_SET, HTTPX_TIMEOUT_DEFAULT
from app.tools.tool_response import build_error, build_success
from app.utils.time_utils import (
    create_timestamp,
    get_local_iso_timestamp,  # 小欧 2026-08-08 全程统一本地时区
)

_timers: Dict[str, asyncio.TimerHandle] = {}
_timer_counter = 0
_timer_callbacks: Dict[str, Dict[str, Any]] = {}
_timer_events: list[Dict[str, Any]] = []
_timer_lock = asyncio.Lock()
CALLBACK_MAX_LENGTH = 4096
# 定时器触发"到点自己干"回调: 由 app 层(main.py 启动)注入 resume_session_with_notice。
#   tools 层不得 import app.services(架构守护 test_architecture_boundaries), 故用回调注入解越层 — 商量 2026-11-25
_resume_callback = None


def set_timer_resume_callback(cb) -> None:
    """注入"定时器触发→回会话建任务"回调(由 app 层启动时注入 resume_session_with_notice) — 商量 2026-11-25

    tools 层不得 import app.services(架构守护), 故用回调注入解越层; 签名 async (session_id, text) -> bool。
    """
    global _resume_callback
    _resume_callback = cb


async def _invoke_timer_callback(timer_id: str, callback: str, session_id: str = "") -> Dict[str, Any]:
    """定时器回调执行 — 小欧 2026-06-17 — 2026-08-05 小欧: except httpx.TimeoutException 移入 http 分支内修复 UnboundLocalError
    2026-11-25 商量 - 有 session_id 且已注入 resume 回调时走"回会话创建任务"(到点自己干), 否则维持原 log/http 行为
    2026-11-25 小欧 - resume 返回 False(会话忙/建任务失败)时降级直接投递: 此前该分支回调内容静默丢失,
    定时器仍记 triggered, 用户收不到任何提醒"""
    event = {
        "timer_id": timer_id,
        "triggered_at": get_local_iso_timestamp(),  # 小欧 2026-08-08 全程统一本地时区: 本地ISO无Z
        "callback": callback,
        "status": "triggered",
    }
    try:
        delivered = False
        if session_id and _resume_callback is not None:
            # 到点自己干: 复用 resume_session_with_notice 双路(有活跃任务→注入, 无→建新任务), 不直接调 HTTP
            ok = await _resume_callback(session_id, callback)
            event["session_id"] = session_id
            delivered = ok
            if ok:
                event["executed_as"] = "resume_task"
            else:
                # 2026-11-25 小欧 - 降级兜底: 会话忙或建任务失败时不能丢提醒(原实现只记字段, 内容作废)
                event["resume_failed"] = True
                logger.warning(
                    f"[Timer {timer_id}] 回会话建任务失败(session={session_id}), 降级直接投递: {callback[:80]}"
                )
        if not delivered:
            if not callback.strip().startswith("http"):
                logger.info(f"[Timer {timer_id}] 提醒: {callback}")
                event["executed_as"] = "log_message"
            else:
                import httpx
                try:
                    resp = httpx.get(callback, timeout=HTTPX_TIMEOUT_DEFAULT)
                    event["executed_as"] = "http_call"
                    event["http_status"] = resp.status_code
                except httpx.TimeoutException:
                    event["executed_as"] = "http_timeout"
    except Exception as e:
        event["executed_as"] = "callback_failed"
        event["error"] = str(e)
    return event


async def _schedule_handle(timer_id: str, callback: str, session_id: str, delay_sec: float, trigger_at: datetime,
                           created_at: str = "") -> None:
    """注册内存句柄(call_later)并登记 callbacks 表 — timer_set 与 rebuild_timers_from_db 共用(DRY) — 商量 2026-11-25

    触发时置 DB status=triggered; 触发动作经 _invoke_timer_callback 分派(resume/log/http)。
    2026-11-25 小欧 - 增 created_at 入参: 重建方传 DB 原始创建时间, 传空才取当前时刻(此前重建一律覆盖成重启时刻)。
    """
    trigger_at_iso = trigger_at.isoformat()

    async def _timer_cb():
        event = await _invoke_timer_callback(timer_id, callback, session_id)
        async with _timer_lock:
            _timer_events.append(event)
        if event.get("executed_as") in ("callback_failed", "http_timeout"):
            # 2026-11-25 小欧 - 投递失败留痕: 行状态仍是 triggered(定时器确实到点了), 但提醒未送达需可追溯
            logger.error(f"[Timer {timer_id}] 触发投递未成功 executed_as={event.get('executed_as')} "
                         f"error={event.get('error', '')}")
        try:
            with db.get_conn("timers") as conn:
                conn.execute("UPDATE timers SET status='triggered', triggered_at=? WHERE timer_id=?", (get_local_iso_timestamp(), timer_id))
        except Exception as _e:
            logger.error(f"[timer] 触发状态落库失败 timer_id={timer_id}(定时器已触发, 仅DB状态残留active, 可凭此日志追溯): {_e!r}")

    def _safe_cb():
        try:
            loop.create_task(_timer_cb())
        except RuntimeError:
            pass

    loop = asyncio.get_running_loop()
    handle = loop.call_later(max(0.0, delay_sec), _safe_cb)
    async with _timer_lock:
        _timers[timer_id] = handle
        _timer_callbacks[timer_id] = {
            "callback": callback,
            "created_at": created_at or get_local_iso_timestamp(),  # 2026-11-25 小欧 - 优先用调用方给的原始创建时间
            "trigger_at": trigger_at_iso,
            "session_id": session_id,
        }


async def rebuild_timers_from_db() -> Dict[str, int]:
    """启动重建: 把 timers 表中 status='active' 的定时器恢复到内存调度 — 商量 2026-11-25

    持久调度器核心: call_later 句柄重启即丢, timers 表是跨重启唯一真源。
      · 未到期(trigger_at > now) → 按剩余秒数重建 call_later;
      · 已到期(重启期间错过)       → 立即补触发一次(不丢"到点该干"语义), 由 _timer_cb 置 triggered;
      · 非 active 行                → 跳过;
      · 非法 trigger_at 行          → 置 status='invalid' 收口(2026-11-25 小欧: 原实现只跳过, 行永久滞留
        active, 每次重启重复告警且永不触发, 列表里还显示为在跑)。
    由 main.py startup 调用(app 层注入 resume 回调之后)。
    """
    now = datetime.now()
    rebuilt = 0
    fired = 0
    try:
        with db.get_conn("timers") as conn:
            rows = conn.execute(
                "SELECT timer_id, callback, session_id, created_at, trigger_at FROM timers WHERE status='active'"
            ).fetchall()
    except Exception as _e:
        logger.error(f"[timer] 启动重建读取失败(降级为不恢复): {_e!r}")
        return {"rebuilt": 0, "fired": 0}
    for r in rows:
        d = dict(r)
        if d["timer_id"] in _timer_callbacks:
            # 2026-11-25 小欧 - 已在内存调度则跳过: 重复调用 rebuild 不得为同一 timer 挂两个 call_later 句柄(双触发)
            continue
        try:
            trig = datetime.fromisoformat(d["trigger_at"])
        except (ValueError, TypeError):
            logger.warning(f"[timer] 启动重建跳过非法 trigger_at: {d.get('timer_id')} {d.get('trigger_at')!r}")
            # 2026-11-25 小欧 - 非法 trigger_at 行收口为 invalid, 避免反复告警与假"active"
            try:
                with db.get_conn("timers") as conn:
                    conn.execute("UPDATE timers SET status='invalid' WHERE timer_id=?", (d.get("timer_id"),))
            except Exception as _e:
                logger.error(f"[timer] 非法 trigger_at 行置 invalid 失败 timer_id={d.get('timer_id')}: {_e!r}")
            continue
        remaining = (trig - now).total_seconds()
        try:
            await _schedule_handle(d["timer_id"], d["callback"] or "", d["session_id"] or "", max(0.0, remaining),
                                   trig, d.get("created_at") or "")
        except Exception as _e:
            logger.error(f"[timer] 启动重建注册失败 timer_id={d.get('timer_id')}: {_e!r}")
            continue
        if remaining > 0:
            rebuilt += 1
        else:
            fired += 1
    if rows:
        logger.info(f"[timer] 启动重建完成: 未到期重建 {rebuilt} 个, 过期已排入补触发 {fired} 个")
    return {"rebuilt": rebuilt, "fired": fired}


def _build_timer_set_llm_data(exec_code: str, duration_ms: int, timer_id: str, trigger_at: str, delay: float, callback: str = "", detail: str = "", hint: str = "") -> dict:
    """timer_set的llm_data构建函数 — 小健 2026-06-22 — 小欧 2026-07-05 新增hint"""
    _delay_sec = 0 if isinstance(delay, float) and not math.isfinite(delay) else int(delay)
    _act_params = {"delay": delay}
    if callback:
        _act_params["callback"] = callback
    if timer_id:
        _act_params["timer_id"] = timer_id
    if trigger_at:
        _act_params["trigger_at"] = trigger_at
    if exec_code == "error":
        return {
            "summary": f"设定时器{_delay_sec}秒，失败：{detail}",
            "action": {"tool": "timer_set", "tool_zh": "设定时器", "params": _act_params},
            "status": {"exec_code": "error", "message": "失败", "code": ERR_TIMER_SET, "detail": detail, "hint": hint if hint else "请检查延迟时间"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"设定时器{_delay_sec}秒，成功：{timer_id}，{_delay_sec // 60}分钟后触发",  # 2026-10-14 小欧 - summary 统一口径: 动词用 tool_zh(设定时器) — 小欧-2026-10-14
        "action": {"tool": "timer_set", "tool_zh": "设定时器", "params": _act_params},
        "status": {"exec_code": "success", "message": f"成功:{_delay_sec // 60}分钟后触发" if _delay_sec >= 60 else f"成功:{_delay_sec}秒后触发", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"delay": {"value": delay, "text": f"{_delay_sec // 60}分钟"}},
    }


async def timer_set(delay: float, callback: str) -> Dict[str, Any]:
    """设置定时器 — 小健 2026-06-22 拆分独立文件"""
    t0 = _time_mod.perf_counter()
    global _timer_counter
    try:
        if delay <= 0:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_timer_set_llm_data("error", duration_ms, "", "", delay, callback=callback, detail="延迟时间必须大于0", hint="请设置大于0的延迟时间")
            return build_error(data={}, llm_data=llm_data)

        if delay > 86400:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_timer_set_llm_data("error", duration_ms, "", "", delay, callback=callback, detail="延迟时间不能超过24小时", hint="请设置24小时内的延迟时间")  # 2026-10-14 小欧 - hint 修复述: 原样复读 detail, 改给行动 — 小欧-2026-10-14
            return build_error(data={}, llm_data=llm_data)

        if len(callback) > CALLBACK_MAX_LENGTH:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_timer_set_llm_data("error", duration_ms, "", "", delay, callback=callback[:50]+"...", detail=f"回调内容过长({len(callback)}字符)，限制{CALLBACK_MAX_LENGTH}字符", hint=f"回调内容不能超过{CALLBACK_MAX_LENGTH}字符")
            return build_error(data={}, llm_data=llm_data)

        session_id = get_current_session_id() or ""  # 2026-11-25 商量 - 发起会话ID(触发时回该会话建任务)
        async with _timer_lock:
            # 模块级共享状态: _timer_counter / _timer_callbacks / _timers / _timer_events 统一加锁
            # — 小欧 2026-07-10
            _timer_counter += 1
            timer_id = f"timer_{_timer_counter}_{create_timestamp()}"
        trigger_at = datetime.now() + timedelta(seconds=delay)  # 小欧 2026-08-08 全程统一本地时区: naive本地, 后续 isoformat() 无偏移
        created_at = get_local_iso_timestamp()  # 2026-11-25 小欧 - 内存与DB共用同一创建时间, 定时器列表两路口径一致
        # 注册内存句柄(call_later)与 callbacks 表, 与 rebuild_timers_from_db 共用 — 商量 2026-11-25
        await _schedule_handle(timer_id, callback, session_id, delay, trigger_at, created_at)

        try:
            with db.get_conn("timers") as conn:
                conn.execute("INSERT OR REPLACE INTO timers (timer_id, delay, callback, session_id, created_at, trigger_at, status) VALUES (?, ?, ?, ?, ?, ?, 'active')",
                             (timer_id, delay, callback, session_id, created_at, trigger_at.isoformat()))
        except Exception as _e:
            logger.error(f"[timer_set] 定时器落库失败 timer_id={timer_id}(内存定时器仍会触发, 重启后丢失, 可凭此日志追溯): {_e!r}")  # 12.2-Q2: 静默pass→error提级留痕 — 小欧 2026-08-21

        trigger_at_str = trigger_at.strftime("%Y-%m-%d %H:%M:%S")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_timer_set_llm_data("success", duration_ms, timer_id, trigger_at_str, delay, callback=callback)
        # =============================================================================
        # 数据设计：timer_id 从 data 移除（summary 已有: "定时器 timer_1_xxx，5分钟后触发"）
        # trigger_at 保留在 data 中（summary 只有 X 分钟后，无精确触发时间）
        # — 小欧 2026-07-06
        # =============================================================================
        # ---- observation_formatter route -------------------------------------------
        # branch: #21 fallback (key:val) — trigger_at only
        # trigger: 无专用分支匹配
        # handler: _format_scalar_data(data) — key | value 单行列表
        # file:    observation_formatter.py:214
        # ------------------------------------------------------------------------------
        return build_success(data={"trigger_at": trigger_at_str}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_timer_set_llm_data("error", duration_ms, "", "", delay, callback=callback, detail=str(e), hint="设置定时器异常,请重试")
        return build_error(data={}, llm_data=llm_data)


__all__ = ["timer_set", "rebuild_timers_from_db", "set_timer_resume_callback",
           "_timers", "_timer_counter", "_timer_callbacks", "_timer_events", "_timer_lock"]
