# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-15 - 小欧 - 新建: 子进程创建唯一出口; 隔离参数自 execute_shell_command 迁入(DRY)
"""proc_spawn — 子进程创建唯一出口 — 小欧 2026-11-15

唯一职责: 给所有 Popen 注入同一组"不继承父控制台"的参数, 并提供唯一的 spawn 包装
(留统一日志与指标)。新增子进程调用一律走 spawn(), 不得再直接 subprocess.Popen。
"""
import subprocess
import sys
from typing import Any, Dict

from app.logger import logger

__all__ = ["isolation_kwargs", "spawn"]


def isolation_kwargs() -> Dict[str, Any]:
    """子进程不继承父控制台的 Popen 公共参数(仅 Windows 非空)。

    1) CREATE_NO_WINDOW: 不显示窗口(仍会分配隐藏控制台, 故只是必要条件不是充分条件);
    2) stdin=DEVNULL: 不继承控制台输入句柄(输入缓冲区串行独占, 读到即挂);
    3) STARTF_USESTDHANDLES: 标准句柄只认调用方给的管道/NUL, 不回落父控制台。
    父进程无控制台(P0/P1)时这组参数退化为普通创建, 无副作用。
    """
    if sys.platform != "win32":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESTDHANDLES
    return {
        "stdin": subprocess.DEVNULL,
        "creationflags": subprocess.CREATE_NO_WINDOW,
        "startupinfo": startupinfo,
    }


def spawn(args, **kwargs):
    """唯一 Popen 出口: 自动补齐隔离参数, 其余参数原样透传。"""
    merged = isolation_kwargs()
    merged.update(kwargs)              # 调用方显式参数优先(如自己的 creationflags)
    logger.debug(f"[proc_spawn] {args!r}")
    return subprocess.Popen(args, **merged)
