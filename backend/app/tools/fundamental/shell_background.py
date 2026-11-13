# -*- coding: utf-8 -*-
# 2026-11-13 商量 - 新建: bash 后台执行模块。非阻塞 Popen + 输出重定向临时文件 +
#   主循环 run_coroutine_threadsafe 提交等待协程 + 完成通知唤醒(注入/续跑/降级落盘三分叉)
# 2026-11-13 商量 - 后台输出目录改走 get_output_dir()(= project_root/output, 与 download_file/
#   generate_chart 同一单源): 原 %TEMP%\omni_bg_shell 与工具层输出基准割裂, 统一归口
# 编辑历史:
# (初版)
"""
S: shell_background — bash 工具后台执行支撑

职责(SRP): 只管"后台进程生命周期 + 完成后通知唤醒路由"; 通知判定逻辑在
_wait_and_notify, 续跑入口在编排层 resume_session_with_notice。
shell() 保持同步函数, 本模块异步部分经 run_coroutine_threadsafe 提交主事件循环执行。
"""
import asyncio
import os
import subprocess
import threading
import time
import uuid
from typing import Any, Dict, Optional

from app.config import get_config
from app.logger import logger
from app.tools.tool_constants import ERR_SHELL_EXCEPTION
from app.tools.tool_response import build_error, build_success

# ── 全局态 ──────────────────────────────────────────────
_BG_REGISTRY: Dict[str, dict] = {}   # {shell_id: {proc, output_file, task_id, command, shell_type, status, started_at, notice_id, sem_released}}
_BG_LOCK = threading.Lock()          # 注册表读写锁(工作线程注册 vs 主循环协程更新)
_BG_TASKS: set = set()               # Future 强引用集合, done 回调 discard 防GC(仿 agent_runner._background_tasks)

_MAIN_LOOP: Optional[asyncio.AbstractEventLoop] = None  # 启动时缓存(main.py 启动钩子调 set_main_loop)
_BG_NOTIFY_ROUTER = None  # 完成通知路由回调(services 层启动时注册, 避免 tools→services 越层)

_BG_MAX = int(get_config().get("tuning.concurrency.shell_max_background", 5))
_BG_SEM = threading.BoundedSemaphore(_BG_MAX)
_BG_RESULT_RETAIN_HOURS = int(get_config().get("tuning.shell_bg_result_retain_hours", 24))


def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    """main.py 启动时缓存主事件循环引用(供工作线程 run_coroutine_threadsafe 提交)"""
    global _MAIN_LOOP
    _MAIN_LOOP = loop


def set_notify_router(router) -> None:
    """注册完成通知路由回调(services 层实现, main 启动时注入) — 商量 2026-11-13

    分层: tools 层只产生"后台完成"事实, 注入/续跑/落库属业务编排, 由 services 层处理;
    避免 tools→services 越层 import。回调签名:
      async router(*, shell_id, task_id, notice_id, text, output_file) -> None
    """
    global _BG_NOTIFY_ROUTER
    _BG_NOTIFY_ROUTER = router


def _new_shell_id() -> str:
    return f"bgsh_{uuid.uuid4().hex[:12]}"


def _bg_output_dir() -> str:
    # 2026-11-13 商量: 输出目录单源 get_output_dir()(= project_root/output),
    #   与 download_file/generate_chart 同基准, 不再落 %TEMP%
    from app.utils.path_utils import get_output_dir
    d = get_output_dir()
    os.makedirs(d, exist_ok=True)
    return d


def _bg_error(command: str, cmd_short: str, detail: str, hint: str) -> Dict[str, Any]:
    return build_error(data={}, llm_data={
        "summary": f"执行Shell命令{cmd_short}，失败",
        "action": {"tool": "bash", "tool_zh": "执行", "params": {"command": command, "background": True}},
        "status": {"exec_code": "error", "message": "失败", "code": ERR_SHELL_EXCEPTION,
                   "detail": detail, "hint": hint},
        "duration_ms": 0, "metrics": {}})


def run_shell_background(command: str, shell_type: str, cwd: Optional[str],
                          task_id: str, cmd_short: str,
                          popen_factory, timeout: Optional[int] = None) -> Dict[str, Any]:
    """启动后台命令并立即返回。popen_factory: 由调用方注入(Popen 构造, 复用 shell() 各
    shell_type 的启动参数装配, 避免本模块重复实现四种 shell 的命令行拼装 DRY)。
    返回 build_success 标准格式, data={shell_id, output_file, status:"running"}。"""
    if _MAIN_LOOP is None:
        return _bg_error(command, cmd_short,
                         "主事件循环未初始化, 后台执行不可用", "服务启动中, 请稍后重试")
    if not _BG_SEM.acquire(blocking=False):
        return _bg_error(command, cmd_short,
                         f"后台并发已达上限({_BG_MAX}), 请等待现有后台命令结束",
                         "属容量管理, 非命令本身错误")
    shell_id = ""
    try:
        shell_id = _new_shell_id()
        output_file = os.path.join(_bg_output_dir(), f"{shell_id}.log")
        # stdout/stderr 合流写文件(2>&1 语义); 进程写端只管追加, 结果文件按保留时长惰性清理
        with open(output_file, "ab"):
            pass
        proc = popen_factory(command, cwd, output_file)
        if proc is None:
            _BG_SEM.release()
            return _bg_error(command, cmd_short, "后台进程启动失败", "请检查命令与解释器")
        with _BG_LOCK:
            _BG_REGISTRY[shell_id] = {
                "proc": proc, "output_file": output_file, "task_id": task_id,
                "command": command, "shell_type": shell_type,
                "status": "running", "started_at": time.time(),
                "timeout": timeout,
                "notice_id": f"{shell_id}_done",   # 通知追踪ID(仅日志留痕; 同 shell_id 通知只发一次由 _wait_and_notify 单次执行保证)
                "sem_released": False,
            }
        # 跨线程提交: shell() 在 _SHELL_EXECUTOR 工作线程执行, 线程内无事件循环,
        # asyncio.create_task 直接调用必炸 → run_coroutine_threadsafe 提交主循环
        # 2026-11-13 商量(复核修正): 提交失败(主循环已关)必须杀进程+清注册+还槽, 不留孤儿
        try:
            fut = asyncio.run_coroutine_threadsafe(_wait_and_notify(shell_id), _MAIN_LOOP)
        except Exception as _sub_e:
            from app.utils.proc_utils import kill_process_tree
            with _BG_LOCK:
                _BG_REGISTRY.pop(shell_id, None)
            try:
                kill_process_tree(proc)
            except Exception:
                pass
            _BG_SEM.release()
            logger.error(f"[bg_shell] {shell_id} 等待协程提交失败(主循环不可用), 进程已终结: {_sub_e}")
            return _bg_error(command, cmd_short,
                             f"等待协程提交失败: {_sub_e}", "服务正在关闭, 请稍后重试")
        _BG_TASKS.add(fut)
        fut.add_done_callback(_BG_TASKS.discard)
        return build_success(
            data={"shell_id": shell_id, "output_file": output_file, "status": "running"},
            llm_data={
                "summary": f"执行Shell命令{cmd_short}，已转后台",
                "action": {"tool": "bash", "tool_zh": "执行",
                           "params": {"command": command, "background": True}},
                "status": {"exec_code": "success", "message": "已转后台运行",
                           "code": "", "detail": "",
                           "hint": "完成时会自动收到系统通知并自动继续处理, 不要轮询等待; "
                                   "期间可继续其他工作或直接结束回答"},
                "duration_ms": 0,
                "metrics": {"shell_id": {"value": shell_id, "text": f"后台ID {shell_id}"},
                            "output_file": {"value": output_file, "text": "输出文件"}}})
    except Exception as e:
        with _BG_LOCK:
            _info = _BG_REGISTRY.get(shell_id)
            if _info is not None:
                _info["sem_released"] = True
        _BG_SEM.release()
        logger.error(f"[bg_shell] 后台启动异常: {e}", exc_info=True)
        return _bg_error(command, cmd_short, str(e), "后台启动异常")


def _release_slot(shell_id: str) -> None:
    """信号量只还一次(锁内标记, 防 wait/kill 竞争双释放 BoundedSemaphore) — 商量 2026-11-13"""
    with _BG_LOCK:
        info = _BG_REGISTRY.get(shell_id)
        if info is None or info.get("sem_released"):
            return
        info["sem_released"] = True
    _BG_SEM.release()


async def _wait_and_notify(shell_id: str) -> None:
    """等待后台进程退出并路由通知(主事件循环协程)。
    进程等待经默认线程池 offload, 零占事件循环; 通知路由委托 services 层注入的回调。"""
    info = _BG_REGISTRY.get(shell_id)
    if not info:
        return
    proc: subprocess.Popen = info["proc"]
    loop = asyncio.get_running_loop()
    timeout = info.get("timeout") or None
    try:
        rc = await loop.run_in_executor(None, lambda: proc.wait(timeout))
        status = "completed" if rc == 0 else "failed"
    except subprocess.TimeoutExpired:
        from app.utils.proc_utils import kill_process_tree
        kill_process_tree(proc)
        rc = proc.returncode if proc.returncode is not None else -1
        status = "failed"
    except Exception as e:
        logger.error(f"[bg_shell] 等待异常({shell_id}): {e}", exc_info=True)
        rc = -1
        status = "failed"

    with _BG_LOCK:
        _killed = info.get("status") == "killed"
        if not _killed:
            info["status"] = status
            info["returncode"] = rc
            info["finished_at"] = time.time()
    _release_slot(shell_id)
    if _killed:
        # 任务取消连带杀: 进程终结是取消动作的一部分, 不再发完成通知(否则会唤醒续跑, 取消后复活)
        logger.info(f"[bg_shell] {shell_id} 已被任务取消连带杀, 跳过完成通知")
        return

    # ── 通知文本(摘要+尾部输出) ──
    duration = int(info["finished_at"] - info["started_at"])
    tail = _read_output_tail(info["output_file"], 600)
    text = (f"[系统通知] 后台命令已完成(shell_id={shell_id}, 退出码{rc}, 耗时{duration}s)\n"
            f"命令: {info['command'][:200]}\n"
            f"输出文件: {info['output_file']}\n"
            f"输出尾部:\n{tail}")

    task_id = info["task_id"]
    try:
        if _BG_NOTIFY_ROUTER is None:
            logger.warning(f"[bg_shell] {shell_id} 通知路由未注册, 降级落盘: {info['output_file']}")
            return
        await _BG_NOTIFY_ROUTER(
            shell_id=shell_id, task_id=task_id, notice_id=info["notice_id"],
            text=text, output_file=info["output_file"])
    except Exception as e:
        logger.error(f"[bg_shell] 通知路由异常({shell_id}): {e}", exc_info=True)
    finally:
        _schedule_result_cleanup()


def _read_output_tail(path: str, max_chars: int) -> str:
    """读输出文件尾部(超限文件读末尾 max_chars)"""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            if size > max_chars * 4:
                f.seek(-max_chars * 4, os.SEEK_END)
            data = f.read()
        return data.decode("utf-8", errors="replace")[-max_chars:]
    except OSError:
        return "(输出文件读取失败)"


def get_bg_info(shell_id: str) -> Optional[dict]:
    with _BG_LOCK:
        return dict(_BG_REGISTRY.get(shell_id) or {})


def kill_background_by_task(task_id: str) -> int:
    """任务 cancelled 连带杀: 终结本 task_id 名下全部后台进程。返回杀掉数。"""
    from app.utils.proc_utils import kill_process_tree
    n = 0
    with _BG_LOCK:
        targets = [sid for sid, i in _BG_REGISTRY.items() if i["task_id"] == task_id]
    for sid in targets:
        info = _BG_REGISTRY.get(sid)
        if info and info["status"] == "running":
            try:
                kill_process_tree(info["proc"])
                with _BG_LOCK:
                    info["status"] = "killed"
                    info["finished_at"] = time.time()
                _release_slot(sid)
                n += 1
                logger.info(f"[bg_shell] 任务取消连带杀后台进程: {sid} (task={task_id})")
            except Exception as e:
                logger.warning(f"[bg_shell] 连带杀失败({sid}): {e}")
    return n


def _schedule_result_cleanup() -> None:
    """结果文件延迟清理(默认24h)。KISS: 惰性清理——新后台命令启动时顺带扫过期项,
    不起定时器(YAGNI)。"""
    now = time.time()
    with _BG_LOCK:
        expired = [sid for sid, i in _BG_REGISTRY.items()
                   if i.get("status") not in ("running", None)
                   and now - i.get("finished_at", now) > _BG_RESULT_RETAIN_HOURS * 3600]
    for sid in expired:
        info = _BG_REGISTRY.pop(sid, None)
        if info:
            for suf in ("", ".bat"):   # .bat=cmd 后台启动脚本(与输出文件同目录同名) — 商量-2026-11-13
                try:
                    os.remove(info["output_file"] + suf)
                except OSError:
                    pass
