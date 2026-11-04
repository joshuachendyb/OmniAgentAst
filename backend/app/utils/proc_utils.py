# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-04 - 小欧 - 新建: 通用进程树清杀(psutil Win32 API + proc.kill), 零 CreateProcess
"""proc_utils — 通用进程工具(零子进程) — 小欧 2026-11-04

【为什么自研】原来树杀靠 `taskkill /T /F` 和 `powershell Get-CimInstance|Stop-Process`,
每次都是一次 `CreateProcessW`。Windows 上 CreateProcessW 调用期持 loader lock 且不释放 GIL,
与任意线程的 `Thread.start()`(等 loader lock, 无超时)并发即永久互锁 → 整个进程停摆。
清理路径本就只在"已经出事"时才走, 再建进程等于往火里浇油(8500 事故: 3 次超时 → 3 个
executor 槽报废, 7 个 pwsh 成孤儿, 清理链一条完成日志都没有)。
⇒ 本模块只用 psutil(直接 Win32 API) + `proc.kill()`(TerminateProcess), 全程零建进程。

【只负责"杀", 不负责"确认"】确认死亡由调用方用 `_poll_pid_exit` 有界轮询 —— 杀与验分离,
避免在清理链里塞进额外等待(SRP)。
"""
import subprocess
from typing import Optional

from app.logger import logger

try:                                    # psutil 缺失时降级为"只杀根进程", 绝不因此中断清理
    import psutil as _psutil
except ImportError:                     # pragma: no cover - 依赖齐全环境不会走到
    _psutil = None

__all__ = ["kill_process_tree", "kill_pid_descendants"]


def kill_process_tree(proc: Optional["subprocess.Popen"]) -> None:
    """终止进程树: 先快照后代再杀根, 全程零子进程 — 2026-11-04 小欧

    顺序不可换: 根一死, 后代被 reparent, 父子链就断了, 之后再也枚举不到。
    幂等; 对已死/无权限进程静默(清理路径不允许再抛异常)。
    """
    if proc is None:
        return
    try:
        if proc.poll() is not None:
            return
    except Exception:
        pass                            # poll 异常=状态未知 → 仍尝试杀, 宁可多杀也不假死
    pid = getattr(proc, "pid", None)
    kill_pid_descendants(pid)
    try:
        proc.kill()                     # TerminateProcess, 不建进程
    except Exception as e:
        logger.debug(f"[卡死C11] 根进程kill异常(已死/无权限, 忽略) (pid={pid}): {e}")


def kill_pid_descendants(root_pid: Optional[int]) -> None:
    """枚举并清杀 root 的全部后代(psutil Win32 API, 零子进程) — 2026-11-04 小欧

    防 pwsh→cmd→ping 这类子树孤儿泄漏; 先叶子后父, 否则父先死会让子脱管。
    """
    if not root_pid or _psutil is None:
        return
    try:
        children = _psutil.Process(root_pid).children(recursive=True)
    except Exception:
        return                          # root 已死/无权限 → 无后代可枚举
    for c in reversed(children):
        try:
            c.kill()
        except Exception:
            pass
