# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-04 - 小欧 - 新建: 零线程子进程管道读取(非阻塞 fd + poll), 取代 Popen.communicate 的 _readerthread
# 2026-11-04 - 小欧 - 红队 P03/P04/P05 修复: timeout=None→inf(原 TypeError); text 模式流取 .buffer
#   (原 read 返回 str 与 b"" 判断错位→死循环); 子进程退出后收尾窗口 0.2s→2.5s 且截断必告警
#   (原静默丢孙进程晚到输出, 与 communicate 的 EOF 语义不一致)
# 2026-11-04 - 小欧 - 红队 P21/P23 修复: drain_until_exit 增 truncated 回传 + TRUNCATED_NOTE(截断对调用方可见,
#   4s 晚到输出不再静默丢); 已关闭流(ValueError)按 EOF 处理(清理链不得因句柄提前关闭而中断)
# 2026-11-15 - 小欧 - run() 增 creationflags 透传(与 subprocess.run 同名同义): 调用方可在零线程读取下
#   继续用 CREATE_NO_WINDOW 防打包版闪黑窗, 无需退回 subprocess.run 的 _readerthread 建线程路径
# 2026-11-16 - 小欧 - proc_spawn.py 并入: isolation_kwargs 迁入本模块(proc_io 本是其调用方, 单函数独立模块
#   违反 KISS); 消掉 run() 内函数级 import 绕路; 5 处调用方统一 from app.utils.proc_io import isolation_kwargs
# 2026-11-26 - 小欧 - 进程宿主复用: logger 改截断告警处惰性导入, 本模块 import 零副作用
#   (宿主/轻量进程导入不拉起 app.logger 控制台线程、不读配置)。逻辑零变化。

"""proc_io — 零线程子进程管道 I/O — 小欧 2026-11-04

【为什么自研】`Popen.communicate()` 每次调用都会 `Thread.start()` 1~3 条 `_readerthread`
(`subprocess.py::_communicate` 的 stdout/stderr 读线程)。Windows 上新建线程的原生启动
(DLL_THREAD_ATTACH/LdrpInitializeThread)要 loader lock, 与 `CreateProcessW` 并发即互锁。

【事故 2026-11-04 11:28】`shell-exec-17` 在 `communicate()` 里等新线程 bootstrap 永不返回,
把当时的闸门 RLock 焊死, 后续 8 条 shell-exec 堵在等锁、AnyIO 线程池被抽干、/health 也超时。
⇒ 运行期建线程必须清零, 管道读取改"非阻塞 fd + poll 轮询", 全程零建线程且可超时中断。

【分工】只负责"读"和"等到退出", 不负责杀: 超时后由调用方走 `kill_process_tree`(零建进程),
再调 `drain_after_exit` 收残存输出。杀/读分离, 避免把清理链塞进额外等待(SRP)。
"""
import locale
import os
import subprocess
import sys
import time
from typing import Any, Dict, Optional, Tuple

__all__ = ["drain_until_exit", "drain_after_exit", "run", "isolation_kwargs"]

POLL_MIN = 0.001        # 有数据时的下一次轮询间隔(秒)
POLL_MAX = 0.05         # 无数据时退避上限(秒), 防忙轮询吃 CPU
IDLE_AFTER_EXIT = 2.5   # 进程已退出但管道未 EOF(孙进程/后台作业持写端)时的收尾等待(秒): 覆盖 `start /b` 惯常延迟, 再长则截断并告警
# 截断留痕: 有界等待必然丢掉"晚到输出", 必须让调用方/模型看见, 不得只写日志 — 2026-11-04 小欧
TRUNCATED_NOTE = "\n[proc_io] 管道未EOF(后台/孙进程仍持写端), 已截断残留输出\n".encode("utf-8")


def isolation_kwargs() -> Dict[str, Any]:
    """子进程不继承父控制台的 Popen 公共参数(仅 Windows 非空) — 2026-11-15 小欧, 原 proc_spawn.py

    1) CREATE_NO_WINDOW: 不显示窗口(仍会分配隐藏控制台, 故只是必要条件不是充分条件);
    2) stdin=DEVNULL: 不继承控制台输入句柄(输入缓冲区串行独占, 读到即挂);
    3) STARTF_USESTDHANDLES: 标准句柄只认调用方给的管道/NUL, 不回落父控制台。
    父进程无控制台(P0/P1)时这组参数退化为普通创建, 无副作用。
    新增子进程调用必须带 **isolation_kwargs(), 不得再裸调 subprocess.Popen。
    (注: 曾设计 spawn() 统一包装, 因暂无调用方按 YAGNI 删除; 首个新调用方出现时再引入)
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



def _raw_stream(stream):
    """text 模式(TextIOWrapper)取底层 BytesIO: 否则 read 返回 str, 与 bytes 判断/拼接全部错位 — 2026-11-04 小欧"""
    buf = getattr(stream, "buffer", None)
    return buf if buf is not None else stream


def _make_nonblocking(stream) -> None:
    try:
        os.set_blocking(stream.fileno(), False)
    except (OSError, ValueError):
        pass                # 非管道/已关闭: 后续 read 走异常分支, 不影响主流程


def _read_available(stream) -> Tuple[bool, bytes]:
    """非阻塞读尽当前可读数据; 返回 (是否 EOF, 本次读到的字节) — 2026-11-04 小欧

    入参必须是二进制流(_raw_stream 已剥离 TextIOWrapper); None 表示"暂无数据"(非 EOF)。
    已关闭的流按 EOF 处理: 清理链(超时杀树后读残存)不允许因句柄被提前关闭而抛异常。
    """
    chunks = []
    while True:
        try:
            chunk = stream.read(65536)
        except (BlockingIOError, OSError):
            return False, b"".join(chunks)
        except ValueError:          # read of closed file: 流已被调用方关闭
            return True, b"".join(chunks)
        if chunk is None:           # 非阻塞无数据(CPython 约定), 不是 EOF
            return False, b"".join(chunks)
        if chunk == b"":            # 写端全关 = EOF
            return True, b"".join(chunks)
        chunks.append(chunk)


def drain_until_exit(proc, timeout: Optional[float]) -> Tuple[bytes, bytes, bool, bool]:
    """轮询读 stdout/stderr 直到"进程退出 + 管道 EOF" — 2026-11-04 小欧

    返回 (out, err, timed_out, truncated):
      timed_out=True  —— 到 timeout 仍未见 EOF(含进程未退出/管道被占), 调用方负责杀;
      truncated=True  —— 进程已退出但管道被孙进程/后台作业持有, 有界静默后放弃残留输出。
    零建线程(不用 communicate), 可被 timeout 硬中断; 超时不杀进程, 由调用方杀后调 drain_after_exit。
    timeout=None 语义等同 subprocess: 不限时(内部按 inf 处理, 不得因 None 抛 TypeError)。
    """
    if timeout is None:
        timeout = float("inf")
    out_buf, err_buf = bytearray(), bytearray()
    out_stream = None if proc.stdout is None else _raw_stream(proc.stdout)
    err_stream = None if proc.stderr is None else _raw_stream(proc.stderr)
    out_eof = out_stream is None
    err_eof = err_stream is None
    if not out_eof:
        _make_nonblocking(out_stream)
    if not err_eof:
        _make_nonblocking(err_stream)

    deadline = time.monotonic() + timeout
    last_data = time.monotonic()
    poll = POLL_MIN
    truncated = False
    while True:
        got = False
        if not out_eof:
            out_eof, data = _read_available(out_stream)
            if data:
                out_buf.extend(data)
                got = True
        if not err_eof:
            err_eof, data = _read_available(err_stream)
            if data:
                err_buf.extend(data)
                got = True
        if out_eof and err_eof:
            break
        now = time.monotonic()
        if got:
            last_data = now
            poll = POLL_MIN
            continue                # 有数据立即再读, 防子进程写满管道阻塞
        if proc.poll() is not None and now - last_data >= IDLE_AFTER_EXIT:
            # 已退出但管道未 EOF: 孙进程/后台作业仍持写端。旧 communicate 会一直等到超时才放弃,
            # 本实现有界静默后截断 —— 绝不静默丢数据: 告警 + truncated=True 交给调用方标注。
            from app.logger import logger  # 惰性导入: 保持本模块 import 零副作用(2026-11-26 小欧)
            logger.warning(
                f"[proc_io] 进程 {proc.pid} 已退出但管道未 EOF(疑孙进程持写端), "
                f"静默 {IDLE_AFTER_EXIT}s 后截断; 已读 out={len(out_buf)}B err={len(err_buf)}B")
            truncated = True
            break
        if now >= deadline:
            return bytes(out_buf), bytes(err_buf), True, False
        poll = min(poll * 2, POLL_MAX)
        time.sleep(min(poll, max(0.0, deadline - now)))

    if proc.poll() is None:
        try:
            proc.wait(timeout=1.0)
        except Exception:
            pass                    # 已退出/被外部杀掉: 收尾失败不影响已读到的输出
    return bytes(out_buf), bytes(err_buf), False, truncated


def drain_after_exit(proc, wait: float = 0.5) -> Tuple[bytes, bytes]:
    """进程已结束(或刚被杀)后读残存管道: 非阻塞读到 EOF 或 wait 秒截止 — 2026-11-04 小欧"""
    out, err, _timed, _trunc = drain_until_exit(proc, wait)
    return out, err


def _decode(data: bytes, encoding, errors):
    if encoding is None:
        return data
    return data.decode(encoding, errors or "strict")


def run(args, *, timeout=None, cwd=None, env=None, shell=False,
        encoding=None, errors=None, text=False, capture_output=True, creationflags=0):
    """`subprocess.run` 的零线程等价(只覆盖本库实际用到的参数) — 2026-11-04 小欧

    capture_output 仅为签名兼容(恒为 True: 本函数的价值就是接管管道读取)。
    超时语义与 subprocess.run 一致: 杀进程树后抛 TimeoutExpired(携带已读输出)。
    creationflags 透传(如 CREATE_NO_WINDOW), 与 subprocess.run 同名同义 — 2026-11-15 小欧
    """
    if text and encoding is None:
        encoding = locale.getpreferredencoding(False)
    # 2026-11-16 小欧 - isolation_kwargs 已并入本模块([42] P4); 调用方显式 creationflags 优先
    spawn_kwargs = isolation_kwargs()
    flags = creationflags or spawn_kwargs.pop("creationflags", 0)
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            cwd=cwd, env=env, shell=shell, creationflags=flags,
                            **spawn_kwargs)
    out_b, err_b, timed_out, truncated = drain_until_exit(
        proc, timeout if timeout is not None else float("inf"))
    if truncated:
        err_b += TRUNCATED_NOTE     # 截断必须对调用方可见(subprocess.run 不会静默丢)
    if timed_out:
        from app.utils.proc_utils import (
            kill_process_tree,  # 局部导入: proc_utils 只依赖 logger, 无循环风险
        )
        kill_process_tree(proc)
        _tail_out, _tail_err = drain_after_exit(proc, 1.0)
        out_b += _tail_out
        err_b += _tail_err
        raise subprocess.TimeoutExpired(args, timeout,
                                        output=_decode(out_b, encoding, errors),
                                        stderr=_decode(err_b, encoding, errors))
    return subprocess.CompletedProcess(args, proc.returncode,
                                       stdout=_decode(out_b, encoding, errors),
                                       stderr=_decode(err_b, encoding, errors))
