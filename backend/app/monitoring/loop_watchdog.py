# -*- coding: utf-8 -*-
# 2026-10-04 - 小欧 - 治理观测(文档[7] §4.4): 事件循环心跳看门狗 — 独立daemon线程检测SSE心跳(:ping)连续缺失,
#   即自动 py-spy dump 全PID落盘留证, 把卡死取证从事后人工变实时; py-spy缺失/无权限时降级为告警(含PID清单+手动命令),
#   不阻断监测线程。挂点: stream_orchestrator 的 stream_reader/journal_reader(activate/beat/deactivate)。
# 2026-10-30 - 小欧 - 停摆判据改用"事件循环独立心跳"(见 _loop_ticker) — 原判据只认 reader 的
#   beat, 客户端背压(reader 卡在 yield)时 beat 同样缺失, 会被误判成停摆并 dump 出无证据的栈;
#   全局"写阻塞计数"方案已否决: 一个僵死客户端会让看门狗对所有 reader 永久失效。
"""
loop_watchdog — 事件循环心跳看门狗

原理: 两条独立证据同时缺失才判停摆 —
      ① reader 的 beat()(SSE 循环在推进);
      ② 事件循环自己的 _loop_ticker()(loop 能调度任意协程)。
      只有 reader beat 缺失而 loop 心跳新鲜 = 客户端背压(reader 挂在 yield 写), 不是停摆。
降级: py-spy 未安装/无权限 → 仅落告警, 不抛异常、不阻断监测线程(§4.4③)。
"""
import asyncio
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import List

from app.config import get_config
from app.logger import logger

_lock = threading.Lock()
_last_beat = 0.0            # 最近一次 reader beat 时间戳(锁保护)
_active = 0                 # 活跃 reader 计数(锁保护)
_dumped = False             # 本次卡死事件是否已dump(beat恢复后重置)
_started = False            # 监视线程只启动一次
_loop_alive_at = 0.0        # 事件循环独立心跳(锁保护); 0=未启动, 判据退回只看 reader beat
_backpressure_logged = False  # 本次背压事件是否已告警(reader 恢复推进后重置)
_ticker_task = None         # 循环心跳任务强引用(防被 GC); None/已结束=需重启

_CHECK_INTERVAL = 10.0      # 巡检周期(秒)
_LOOP_TICK_INTERVAL = 1.0   # 循环心跳周期(秒)


def activate() -> None:
    """reader 进入(有活跃SSE流才需要心跳监管); 首次调用启动监测线程 — 小欧 2026-10-04"""
    global _active, _last_beat, _started
    with _lock:
        if _active <= 0:
            _last_beat = time.time()   # 三堂会审F3修复(2026-10-04 小欧): 0→1监管起点刷新 — 原仅首 ever 置初值,
                                       #   残留旧时间戳会让新reader起步瞬间stale超标 → 误dump; 活跃期activate不重置(防掩盖真停摆)
        _active += 1
        if not _started:
            _started = True
            threading.Thread(target=_watch_loop, daemon=True, name="loop-watchdog").start()
    _ensure_ticker()


def deactivate() -> None:
    """reader 退出(含GeneratorExit断连路径, 必须在finally中调用) — 小欧 2026-10-04"""
    global _active, _backpressure_logged
    with _lock:
        _active = max(0, _active - 1)
        if _active <= 0:
            _backpressure_logged = False   # 全部 reader 退出, 下次事件重新告警



def beat() -> None:
    """事件循环可调度的证据; reader每轮循环调用 — 小欧 2026-10-04"""
    global _last_beat, _dumped
    with _lock:
        _last_beat = time.time()
        if _dumped:
            _dumped = False   # 循环恢复, 允许下次事件再dump


def _ensure_ticker() -> None:
    """有运行中的事件循环时启动 loop 存活心跳 — 小欧 2026-10-30

    为什么需要独立心跳: reader 卡在 yield 写(客户端不读)时 beat() 同样缺失,
      单看 beat 无法区分"客户端背压"与"loop 停摆"。本协程只要能跑就证明 loop 可调度。
    同步上下文(单测/线程)没有 running loop → 不启动, 判据退回只看 reader beat(不改变旧行为)。
    """
    global _ticker_task
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    if _ticker_task is not None and not _ticker_task.done():
        return
    _ticker_task = loop.create_task(_loop_ticker())


async def _loop_ticker() -> None:
    """事件循环存活心跳: 每秒推进一次; loop 真停摆时本协程同样得不到调度 — 小欧 2026-10-30"""
    # 2026-10-30 小欧: 必须同时声明 _dumped —— 漏声明时它在本函数内被判为局部名,
    #   首拍读即 UnboundLocalError, 协程当场死掉 → 双证据判据退化成只看 reader beat(等于没改),
    #   且无任何日志痕迹。
    global _loop_alive_at, _dumped
    while True:
        try:
            with _lock:
                _loop_alive_at = time.time()
                if _dumped:
                    _dumped = False   # 循环已恢复, 允许下次真停摆再留证
                if _active <= 0:
                    return            # 无活跃 reader 时退出, 下次 activate 重启
        except asyncio.CancelledError:
            raise
        except Exception as _e:  # noqa: BLE001 - 心跳协程静默死亡=判据静默退化, 必须留痕并续跑
            logger.warning(f"[观测] loop 心跳异常(协程继续): {type(_e).__name__}: {_e}")
        await asyncio.sleep(_LOOP_TICK_INTERVAL)


def _threshold() -> float:
    hb = float(get_config().get("tuning.live_front.heartbeat_interval", 25.0))
    return max(3 * hb, 75.0)   # 3个心跳周期且不小于75s, 吸收调度抖动防误报


def _watch_loop() -> None:
    """监测线程主体: 独立于事件循环, 循环停摆时本线程仍可调度 — 小欧 2026-10-04"""
    global _dumped, _backpressure_logged   # P0修复(2026-10-04 小欧): 缺声明则_dumped成局部, 活跃期每轮读即UnboundLocalError
    while True:
        try:
            time.sleep(_CHECK_INTERVAL)   # P1修复(2026-10-04 小欧): sleep入try, F2保护圈不留盲区
            thr = _threshold()            # P2修复(2026-10-04 小欧): config读取移出锁, 防占锁卡beat
            stale = 0.0
            _action = None
            with _lock:
                if _active <= 0 or _dumped:
                    _action = "idle"
                else:
                    _now = time.time()
                    stale = _now - _last_beat
                    if stale < thr:
                        _backpressure_logged = False   # reader 已恢复推进
                        _action = "fresh"
                    # 2026-10-30 小欧 - reader 心跳缺失但事件循环仍在调度(独立心跳新鲜)
                    #   → 客户端背压(reader 挂在 yield 写), 不是停摆, 不 dump 误导证据
                    elif _loop_alive_at > 0 and (_now - _loop_alive_at) < thr:
                        _action = "backpressure"
                    else:
                        _dumped = True
                        _action = "stall"
            if _action == "stall":
                _dump_evidence(stale)
            elif _action == "backpressure" and not _backpressure_logged:
                _backpressure_logged = True
                logger.warning(
                    f"[观测] reader 心跳缺失{stale:.0f}s 但事件循环仍在调度 → 判定客户端背压(不dump)")
        except Exception as _e:
            # 三堂会审F2修复(2026-10-04 小欧): 单轮异常(如config读取失败)若逃逸会致本线程静默死亡,
            #   而 _started=True 永不重启 → 看门狗永久失效; 捕获后告警并继续下轮巡检(设计§4.4③: 不阻断监测线程)
            logger.warning(f"[观测] 看门狗巡检异常(线程不退出, 下轮继续): {type(_e).__name__}: {_e}")


def _dump_evidence(stale: float) -> None:
    """py-spy dump 全PID留证; py-spy不可用时降级告警(§4.4③) — 小欧 2026-10-04"""
    pids: List[int] = [os.getpid(), os.getppid()]
    pid_txt = ",".join(str(p) for p in pids)
    py_spy = shutil.which("py-spy")
    if not py_spy:
        logger.warning(f"[观测] 事件循环疑似停摆(心跳缺失{stale:.0f}s>{_threshold():.0f}s), py-spy不可用 → 手动取证: py-spy dump --pid {pid_txt}")
        return
    out_dir = Path(__file__).resolve().parents[2] / "logs" / "pyspy"
    ts = time.strftime("%Y%m%d_%H%M%S")
    dumped = False
    for pid in pids:
        try:
            r = subprocess.run(
                [py_spy, "dump", "--pid", str(pid)],
                capture_output=True, text=True, timeout=30,
                encoding="utf-8", errors="replace")
        except Exception as _e:
            logger.warning(f"[观测] py-spy dump pid={pid}异常({_e}) → 手动: py-spy dump --pid {pid}")
            continue
        if r.returncode != 0:
            logger.warning(f"[观测] py-spy dump pid={pid}失败(rc={r.returncode}): {(r.stderr or r.stdout or '')[:300]} → 手动: py-spy dump --pid {pid}")
            continue
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            fp = out_dir / f"pyspy_{pid}_{ts}.txt"
            fp.write_text(r.stdout or "", encoding="utf-8")
            logger.warning(f"[观测] 事件循环停摆(心跳缺失{stale:.0f}s) → py-spy dump已留证 pid={pid} → {fp}")
            dumped = True
        except OSError as _e:
            logger.warning(f"[观测] py-spy dump落盘失败({_e}) → 手动: py-spy dump --pid {pid}")
    if not dumped:
        logger.warning(f"[观测] 事件循环停摆(心跳缺失{stale:.0f}s) 但dump全部失败 → 手动: py-spy dump --pid {pid_txt}")
