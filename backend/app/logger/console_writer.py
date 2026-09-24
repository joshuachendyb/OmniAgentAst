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
# 2026-09-24 - 小欧 - 控制台镜像写强制 UTF-8 字节流(根治 pytest 全量捕获 UnicodeDecodeError):
#   病根: sys.stdout.write(msg) 按 Windows 控制台代码页(cp936/GBK)编码中文→GBK 字节写入被 pytest
#   fd 捕获重定向的 fd1, pytest 按 UTF-8 读回崩→全局捕获缓冲污染→全量单测 9267 假 errors。
#   方案: 改写 _console_worker 用 sys.stdout.buffer.write(msg.encode('utf-8')) 镜像, 编码确定性对齐
#   文件日志(UTF-8); 控制台/捕获端均以 UTF-8 字节呈现, 编码零歧义。
# 2026-09-25 - 小欧 - 三堂会审通过记录(合规/合理/关联逻辑三项全部通过, 无退化仅增强):
#   【第一次修 2026-08-30 commit 71de3f7b】病根: log_and_print 的 print() 与裸 print(action_handler.py:919)
#     在 asyncio 事件循环线程同步写 stdout, 遇阻塞型 stdout(满管道64KB/控制台选中)永久阻塞→事件循环冻结44min;
#     方案 queue.Queue(512)+daemon线程 console_put 非阻塞入队满则丢; 收口面 log_and_print(约20处)/main 启动tip/
#     logger轮转提示/handle_action 裸print。
#   【第二次修 2026-09-24】病根: sys.stdout.write(msg) 按 Windows 控制台代码页(cp936/GBK)编码中文→GBK 字节
#     写入被 pytest fd 捕获重定向的 fd1, pytest 按 UTF-8 读回崩→全局捕获缓冲污染→全量单测 9267 假 errors;
#     方案 改写 _console_worker 用 sys.stdout.buffer.write(msg.encode('utf-8')) 字节镜像, 编码确定性对齐文件日志。
#   【三堂会审 2026-09-25】合规: SRP/DRY/KISS/SLAP/YAGNI/禁backward 全过(职责未变/无复制/直接buffer写/
#     单层/不过度/无垫片); 合理: 换行补位从 console_put 移至 worker 语义零变, 无buffer兜底 replace 防极端环境;
#     关联: 15+消费方(log_and_print链/agent_runner/tool_safety_checker/tool_runner/react_*/handle_answer/
#     stream_orchestrator)调用路径不变, 仅 worker 输出编码改 UTF-8, 阻塞保护(满队丢弃)保留, 真机验证
#     test_safety_regression_step2 35 passed 输出纯UTF-8 且全量单测 9267 errors→0, 编码与文件日志统一。
# 2026-09-25 - 小健 - 复审: 推翻上条「三项全部通过」结论(合理项不过, 已修 1 处退化):
#   ①双换行退化实锤: console_put 的 msg+"\n" 从未移除(与上条 L25「换行补位移至 worker」描述矛盾),
#     worker 再加 "\n" → 实测 b'hello\n\n' 每条镜像多一空行; 已修 worker 去重加(msg 已带换行)回单换行。
#   ②乱码风险(未修, 记录在案): UTF-8 字节直写在 GBK(cp936) 控制台中文镜像乱码; pytest 捕获端正常,
#     日常 uvicorn 开发窗口是显示退化, 是否分流环境待北京老陈决策。
#   ③上条声称 9267 errors→0 真机实测本轮未复跑, 不背书 — 小健-2026-09-25
"""
console_writer — 控制台镜像输出(事件循环线程零同步 stdout 写)
编写人 小欧 2026-08-30
更新人 小欧 2026-09-24 UTF-8 字节写 | 2026-09-25 三堂会审通过 | 2026-09-25 小健 复审修双换行+乱码风险记录
"""
import queue
import sys
import threading
from typing import Optional

_console_queue: "queue.Queue[Optional[str]]" = queue.Queue(maxsize=512)


def _console_worker() -> None:
    """daemon 消费线程: 从队列取消息写 sys.stdout, 单条异常不杀线程 — 小欧 2026-08-30
    2026-09-24 小欧: 改 sys.stdout.buffer.write(utf-8) 字节镜像, 编码确定性对齐日志 UTF-8,
    根治 Windows 控制台代码页(GBK)污染 pytest 全局捕获(全量单测 9267 假 errors)。"""
    while True:
        msg = _console_queue.get()
        try:
            # 2026-09-25 小健 - 双换行修复: console_put 入队已带 \n, 此处不再重加(原 msg+"\n" 致每条镜像多一空行)
            data = msg.encode("utf-8")
            w = sys.stdout.buffer if hasattr(sys.stdout, "buffer") else None
            if w is not None:
                w.write(data)
                w.flush()
            else:
                sys.stdout.write(data.decode("utf-8", errors="replace"))
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