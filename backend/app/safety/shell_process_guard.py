# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-16 - 小欧 - 新建: shell 进程防护快照组装(无状态纯函数)。
#   本体自 app/safety/tool_safety_checker.py:162-196 逐字搬迁，只改两处:
#   收 pool_pids 参数、_protected_pids 内部自拼改由上游调用方递入。
#   零 import 工具层；不建注册表、不存量（见 [36] 第四章）。
"""shell 进程防护快照组装 — 安全层无状态纯函数（零 import 工具层）"""
import os
from typing import Optional

from app.logger import logger


def build_protected_pids(pool_pids: Optional[set] = None) -> set:
    """宿主关键进程 PID 集合（后端自身+父进程+传入的 shell 池快照）— 小欧 2026-10-16

    pool_pids=None 退化为仅自身+父进程，不崩；退化必打 warning 留痕（静默退化=池失护）。
    """
    pids = {os.getpid(), os.getppid()}  # uvicorn --reload 父子双进程，getppid 必带
    if pool_pids:
        pids |= set(pool_pids)
    elif pool_pids is None:  # 三堂会审补：None=上游未递入（留痕）；空集=池空闲（常态，不留痕）
        logger.warning("[shell_process_guard] 未递入池快照，退化为仅自身+父进程")
    return pids


def build_protected_names(pids: set) -> set:
    """受保护进程名集合（由 PID 反查名，防按名杀）— 小欧 2026-10-16

    psutil 不可用/进程已退出时降级为空集（退化为仅 PID 口径），不拖垮安全判定。
    """
    names = set()
    try:
        import psutil
    except ImportError:
        return names
    for pid in pids:
        try:
            names.add(psutil.Process(pid).name())
        except Exception:
            continue
    return names
