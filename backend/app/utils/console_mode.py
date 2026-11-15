# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-15 - 小欧 - 新建: frozen 启动即 FreeConsole + stdio 重定向, 取消父进程持有控制台这一前提
"""console_mode — 运行期控制台调度 — 小欧 2026-11-15

【问题】打包版 console=True 启动即绑定 conhost; 子进程默认继承该控制台句柄,
CreateProcessW 在 GetConsoleMode 的 IOCTL 内可无限阻塞且不释放 GIL(CPython 的
_winapi.CreateProcess 未放开 GIL) —— 解释器整体冻结, 看门狗/心跳一并停摆,
只能杀进程。实测 CREATE_NO_WINDOW 仍会分配隐藏控制台, 不能消除该前提。

【做法】frozen 且本进程仍持有控制台时: FreeConsole() 摘掉关联, 随后把
sys.stdout / sys.stderr 重定向到 logs/boot_YYYY-MM-DD.log, sys.stdin 指向 NUL。
父进程不再持有控制台 → 子进程无从继承 → 该 IOCTL 分支不再被触发。

【边界】FreeConsole 只解除本进程与 conhost 的关联, 不负责结束 conhost 进程;
彻底形态由打包 console=False 承担(P1)。本函数与 P1 叠用时 FreeConsole 返回 0,
直接返回, 幂等无副作用。环境变量 OMNI_KEEP_CONSOLE=1 可关闭本行为(排障用)。
"""
import ctypes
import os
import sys
import time
from pathlib import Path

_applied = False


def _boot_log_path():
    if getattr(sys, "frozen", False):
        logs = Path(sys.executable).resolve().parent / "logs"
    else:
        logs = Path(__file__).resolve().parents[2] / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    return logs / f"boot_{time.strftime('%Y-%m-%d')}.log"


def _redirect_stdio():
    try:
        fp = open(_boot_log_path(), "a", encoding="utf-8", buffering=1)
    except OSError:
        fp = open(os.devnull, "w", encoding="utf-8", buffering=1)
    sys.stdout = fp
    sys.stderr = fp
    sys.stdin = open(os.devnull, "r", encoding="utf-8")


def detach_console_if_needed() -> None:
    """frozen 且有控制台时脱离控制台(幂等); 返回后所有 print 落 boot 日志。"""
    global _applied
    if _applied or sys.platform != "win32":
        return
    _applied = True
    if not getattr(sys, "frozen", False):
        return
    if os.environ.get("OMNI_KEEP_CONSOLE") == "1":
        return
    if not ctypes.windll.kernel32.FreeConsole():
        return      # 本来就没有控制台(或已脱离): 不碰 stdio
    _redirect_stdio()
    print("[console_mode] 已脱离父控制台, stdio 重定向到 boot 日志", flush=True)
    print(f"[console_mode] path={_boot_log_path()}", flush=True)
