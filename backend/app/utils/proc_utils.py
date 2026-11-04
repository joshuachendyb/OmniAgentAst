# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-04 - 小欧 - 新建: 通用进程树清杀(psutil Win32 API + proc.kill), 零 CreateProcess
# 2026-11-04 - 小欧 - 红队 P20 修复: 删"根已退出就 return"的短路 —— 根死时孙进程可能仍存活并持有
#   输出管道(实证孤儿 ping), Windows 父死子不重挂, 仍可按 pid 枚举后代清杀
# 2026-11-04 - 小欧 - P20 二次修复: 后代枚举改 ppid 全量映射 + BFS(Process(pid).children() 在根退出后抛
#   NoSuchProcess, 映射法不依赖根存活) — 小欧-2026-11-04
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
    pid = getattr(proc, "pid", None)
    # 不因"根已退出"提前 return: 根死时孙进程可能仍在跑并持有输出管道(P20 实证孤儿 ping)。
    # Windows 子进程的 PPID 不重挂(父死仍指向原 pid), 且 Popen 未关句柄时进程对象仍在,
    # 故仍可按 pid 枚举并清杀后代 — 2026-11-04 小欧
    kill_pid_descendants(pid)
    try:
        proc.kill()                     # TerminateProcess, 不建进程; 对已死进程无害
    except Exception as e:
        logger.debug(f"[卡死C11] 根进程kill异常(已死/无权限, 忽略) (pid={pid}): {e}")


def kill_pid_descendants(root_pid: Optional[int]) -> None:
    """枚举并清杀 root 的全部后代(psutil, 零子进程) — 2026-11-04 小欧

    防 pwsh→cmd→ping 这类子树孤儿泄漏; 先叶子后父, 否则父先死会让子脱管。
    【实现】按 ppid 建全量映射再 BFS, 不用 Process(root).children(): 根一旦退出该构造即抛
    NoSuchProcess, 而 Windows 父死子不重挂(子进程 ppid 仍指向已死的根), 映射法照样能枚举(P20 实证)。
    """
    if not root_pid or _psutil is None:
        return
    try:
        children_map: dict = {}
        # 用 process_iter() + p.ppid(): psutil 的 ppid 走系统级快照(实测 22ms);
        # process_iter(["pid","ppid"]) 会逐进程 as_dict, 本机首次高达 3s —— 清理链不允许 — 2026-11-04 小欧
        for p in _psutil.process_iter():
            try:
                children_map.setdefault(p.ppid(), []).append(p.pid)
            except Exception:
                continue
    except Exception:
        return                          # 快照失败 → 无后代可杀, 绝不影响清理链
    order, seen, frontier = [], {root_pid}, [root_pid]
    while frontier:
        nxt = []
        for pid in frontier:
            for child in children_map.get(pid, ()):
                if child in seen:
                    continue
                seen.add(child)
                order.append(child)
                nxt.append(child)
        frontier = nxt
    for pid in reversed(order):         # BFS 逆序 = 先叶子后父
        try:
            _psutil.Process(pid).kill()
        except Exception:
            pass
