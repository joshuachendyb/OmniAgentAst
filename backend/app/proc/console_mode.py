# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-15 - 小欧 - 新建: frozen 启动即 FreeConsole + stdio 重定向, 取消父进程持有控制台这一前提
# 2026-11-16 小欧 - 新增 _detached 标志与 is_console_detached(): 供 console_writer 探测"是否已无真实控制台"。原 stdio 重定向到 boot 日志后, sys.stdout 仍是可写文件对象, _probe_console 误判为有效控制台 → 控制台镜像把 app 运行日志全灌进 boot 日志(污染, 含整段会话历史); 现由本标志唯一判定, detach 后镜像整体旁路 — 小欧-2026-11-16
# 2026-11-26 - 小欧 - 目录归位: 由 app/utils 迁入 app/proc 进程域包, 仅改导入路径, 逻辑零变化。
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
直接返回, 幂等无副作用。环境变量 OMNI_DEBUG_KEEP_CONSOLE=1 可关闭本行为(排障用)。
"""
import ctypes
import os
import sys
import time
from pathlib import Path

from app.env_keys import DEBUG_KEEP_CONSOLE

_applied = False
_detached = False


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
    global _applied, _detached
    if _applied or sys.platform != "win32":
        return
    _applied = True
    if not getattr(sys, "frozen", False):
        return
    if os.environ.get(DEBUG_KEEP_CONSOLE) == "1":
        return
    if not ctypes.windll.kernel32.FreeConsole():
        return      # 本来就没有控制台(或已脱离): 不碰 stdio
    _redirect_stdio()
    _detached = True
    print("[console_mode] 已脱离父控制台, stdio 重定向到 boot 日志", flush=True)
    print(f"[console_mode] path={_boot_log_path()}", flush=True)


def is_console_detached() -> bool:
    """是否已脱离控制台并把 stdio 重定向到 boot 日志 — 小欧-2026-11-16

    供 console_writer._probe_console 判定"当前无真实控制台": stdio 虽被换成可写文件对象,
    但那只是 boot 日志, 控制台镜像若继续写只会污染 boot 日志, 故 detach 后镜像整体旁路。
    非 frozen / OMNI_DEBUG_KEEP_CONSOLE=1 / 未 detach 时恒 False(控制台仍有效)。
    """
    return _detached
