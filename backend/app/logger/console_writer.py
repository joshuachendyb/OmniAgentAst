# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-30 - 小欧 - 新增 console_writer: 控制台镜像输出离线化(根治 App_2026-08-30.log:20790~20801 case09 挂起)
#   病根: log_and_print(约20处: react_cycle/action_handler/tool_safety_checker等) 与裸print(action_handler.py:919)
#         在 asyncio 事件循环线程同步写 stdout, 遇阻塞型 stdout(满管道64KB缓冲/Windows控制台选中)永久阻塞,
#         事件循环冻结44min, 全服务停摆.
#   方案: 全局单例 queue.Queue(maxsize=512) + daemon 写线程, console_put(msg) 非阻塞入队;
#         stdout 阻塞时队列满则丢弃新消息(控制台仅镜像, 权威日志在文件), 事件循环永不被占.
#   10规范: SRP(只做控制台镜像) / DRY(log_and_print复用) / KISS-DIRECT(queue+线程模型最简) /
#           SLAP(console_put单层入队) / YAGNI(不加优雅退出/多消费者) / 禁止backward(直接替换print)
"""
console_writer — 控制台镜像输出(事件循环线程零同步 stdout 写)
编写人 小欧 2026-08-30
"""
import queue
import sys
import threading
from typing import Optional

_console_queue: "queue.Queue[Optional[str]]" = queue.Queue(maxsize=512)


def _console_worker() -> None:
    """daemon 消费线程: 从队列取消息写 sys.stdout, 单条异常不杀线程 — 小欧 2026-08-30"""
    while True:
        msg = _console_queue.get()
        try:
            sys.stdout.write(msg)
            sys.stdout.flush()
        except Exception:
            pass
        finally:
            _console_queue.task_done()


_console_thread = threading.Thread(
    target=_console_worker, name="console-writer", daemon=True,
)
_console_thread.start()


def console_put(msg: str) -> None:
    """控制台镜像写(非阻塞): stdout 阻塞时队列满则丢弃新消息, 绝不阻塞调用线程 — 小欧 2026-08-30
    语义对齐原 print(): msg 追加换行写进程 stdout; 文件日志留痕走 logger, 两者互不阻塞.
    """
    try:
        _console_queue.put_nowait(msg + "\n")
    except queue.Full:
        pass