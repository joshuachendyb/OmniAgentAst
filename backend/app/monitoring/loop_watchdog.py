# -*- coding: utf-8 -*-
# 2026-10-04 - 小欧 - 治理观测(文档[7] §4.4): 事件循环心跳看门狗 — 独立daemon线程检测SSE心跳(:ping)连续缺失,
#   即自动 py-spy dump 全PID落盘留证, 把卡死取证从事后人工变实时; py-spy缺失/无权限时降级为告警(含PID清单+手动命令),
#   不阻断监测线程。挂点: stream_orchestrator 的 stream_reader/journal_reader(activate/beat/deactivate)。
"""
loop_watchdog — 事件循环心跳看门狗

原理: 活跃SSE reader 每轮循环调 beat()(=事件循环可调度的直接证据);
      活跃reader>0 且超阈值无beat → 判定事件循环停摆 → 自动 py-spy dump 留证。
降级: py-spy 未安装/无权限 → 仅落告警, 不抛异常、不阻断监测线程(§4.4③)。
"""
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
_last_beat = 0.0            # 最近一次 beat 时间戳(锁保护)
_active = 0                 # 活跃 reader 计数(锁保护)
_dumped = False             # 本次卡死事件是否已dump(beat恢复后重置)
_started = False            # 监视线程只启动一次

_CHECK_INTERVAL = 10.0      # 巡检周期(秒)


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


def deactivate() -> None:
    """reader 退出(含GeneratorExit断连路径, 必须在finally中调用) — 小欧 2026-10-04"""
    global _active
    with _lock:
        _active = max(0, _active - 1)


def beat() -> None:
    """事件循环可调度的证据; reader每轮循环调用 — 小欧 2026-10-04"""
    global _last_beat, _dumped
    with _lock:
        _last_beat = time.time()
        if _dumped:
            _dumped = False   # 循环恢复, 允许下次事件再dump


def _threshold() -> float:
    hb = float(get_config().get("tuning.live_front.heartbeat_interval", 25.0))
    return max(3 * hb, 75.0)   # 3个心跳周期且不小于75s, 吸收调度抖动防误报


def _watch_loop() -> None:
    """监测线程主体: 独立于事件循环, 循环停摆时本线程仍可调度 — 小欧 2026-10-04"""
    global _dumped   # P0修复(2026-10-04 小欧): 缺声明则_dumped成局部, 活跃期每轮读即UnboundLocalError
    while True:
        try:
            time.sleep(_CHECK_INTERVAL)   # P1修复(2026-10-04 小欧): sleep入try, F2保护圈不留盲区
            thr = _threshold()            # P2修复(2026-10-04 小欧): config读取移出锁, 防占锁卡beat
            with _lock:
                if _active <= 0 or _dumped:
                    continue
                stale = time.time() - _last_beat
                if stale < thr:
                    continue
                _dumped = True
            _dump_evidence(stale)
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
