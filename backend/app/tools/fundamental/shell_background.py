# -*- coding: utf-8 -*-
# 2026-11-13 商量 - 新建: bash 后台执行模块。非阻塞 Popen + 输出重定向临时文件 +
#   主循环 run_coroutine_threadsafe 提交等待协程 + 完成通知唤醒(注入/续跑/降级落盘三分叉)
# 2026-11-13 商量 - 后台输出目录改走 get_output_dir()(= project_root/output, 与 download_file/
#   generate_chart 同一单源): 原 %TEMP%\omni_bg_shell 与工具层输出基准割裂, 统一归口
# 编辑历史:
# (初版)
# 2026-11-13 商量 - 三堂会审根治: (1)产物路径单源化 bat_sidecar_path, cmd 启动脚本生成/清理共用,
#   消除 outfile[:-4]+".bat" vs output_file+".bat" 两处推导漂移致 .bat 永不被删; (2)结果清理改"先删产物
#   成功后 pop 注册表", 删除失败保留记录下轮重试, 杜绝 pop 后静默吞 OSError 变永久孤儿; (3)success_codes
#   贯通后台成功判定, 与前台语义一致; (4)完成通知按 完成/失败/超时终止 如实表述, 不再一律"已完成"误导;
#   (5)超时杀进程树 offload 线程池, 不再阻塞主事件循环; (6)保留时长改调用时读配置
# 2026-11-13 商量 - 三堂会审·防卡死根治: (1)后台进程等待改走专用 WorkerPool(_BG_MAX 常驻线程), 与
#   tool-sync 共享池彻底隔离 —— 后台默认无超时, 原 run_in_executor(None) 会让卡死后台永久霸占工具线程池,
#   后台配到 32 时可耗尽全池使文件/网络/DB 工具全部饿死(系统级卡死); (2)等待统一"退出/超时/输出超限"三态,
#   输出文件超 tuning.shell_bg_max_output_mb 即杀进程, 防磁盘写满拖垮整机; (3)新增 kill_all_background 供
#   shutdown 调用, 正常关闭不再遗留孤儿进程; (4)等待 Future 被取消(主循环关闭/协程未跑)时兜底杀进程+还槽,
#   杜绝孤儿进程与信号量永久泄漏; (5)清理失败达上限后放弃记录, 防孙进程持句柄致注册表无限累积
"""
S: shell_background — bash 工具后台执行支撑

职责(SRP): 只管"后台进程生命周期 + 完成后通知唤醒路由"; 通知判定逻辑在
_wait_and_notify, 续跑入口在编排层 resume_session_with_notice。
shell() 保持同步函数, 本模块异步部分经 run_coroutine_threadsafe 提交主事件循环执行。
"""
import asyncio
import functools
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
from app.utils.workers import WorkerPool

# ── 全局态 ──────────────────────────────────────────────
_BG_REGISTRY: Dict[str, dict] = {}   # {shell_id: {proc, output_file, task_id, command, shell_type, status, started_at, notice_id, sem_released}}
_BG_LOCK = threading.Lock()          # 注册表读写锁(工作线程注册 vs 主循环协程更新)
_BG_TASKS: set = set()               # Future 强引用集合, done 回调 discard 防GC(仿 agent_runner._background_tasks)

_MAIN_LOOP: Optional[asyncio.AbstractEventLoop] = None  # 启动时缓存(main.py 启动钩子调 set_main_loop)
_BG_NOTIFY_ROUTER = None  # 完成通知路由回调(services 层启动时注册, 避免 tools→services 越层)

_BG_MAX = max(1, int(get_config().get("tuning.concurrency.shell_max_background", 5)))
_BG_SEM = threading.BoundedSemaphore(_BG_MAX)
_BG_SIDECAR_SUFFIX = ".bat"   # cmd 后台启动脚本后缀(与输出文件同目录同名)
# 专用等待池: 容量=后台并发上限, 常驻线程(WorkerPool 构造期建满, 运行期零 Thread.start)。
#   后台等待默认无超时, 必须与 tool-sync 共享池隔离, 否则卡死后台永久霸占工具线程池拖垮全系统;
#   池大小与 _BG_SEM 同源, 每个在跑后台恰占 1 线程, 一对一不排队。
_BG_WAIT_POOL = WorkerPool(_BG_MAX, "bg-shell-wait")
_BG_CLEANUP_MAX_ATTEMPTS = 5   # 产物删除连续失败上限, 超过则放弃记录防注册表无限增长


def _max_output_bytes() -> int:
    """单条后台命令输出文件大小上限(字节), 0=不限制; 调用时读配置。
    默认 512MB: 并发上限 5 时峰值 2.5GB, 守住"单条日志狂写不拖垮整机"红线。"""
    return max(0, int(get_config().get("tuning.shell_bg_max_output_mb", 512))) * 1024 * 1024


def bat_sidecar_path(output_file: str) -> str:
    """cmd 后台启动脚本路径。生成(execute_shell_command)与清理共用此单源, 杜绝两处推导漂移。"""
    return output_file + _BG_SIDECAR_SUFFIX


def _retain_seconds() -> int:
    """结果文件保留时长秒数(调用时读配置, 改配置无需重启)。"""
    return int(get_config().get("tuning.shell_bg_result_retain_hours", 24)) * 3600


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
                          popen_factory, timeout: Optional[int] = None,
                          success_codes: Optional[list[int]] = None) -> Dict[str, Any]:
    """启动后台命令并立即返回。popen_factory: 由调用方注入(Popen 构造, 复用 shell() 各
    shell_type 的启动参数装配, 避免本模块重复实现四种 shell 的命令行拼装 DRY)。
    返回 build_success 标准格式, data={shell_id, output_file, status:"running"}。"""
    if _MAIN_LOOP is None:
        return _bg_error(command, cmd_short,
                         "主事件循环未初始化, 后台执行不可用", "服务启动中, 请稍后重试")
    # 新后台命令启动时顺带清理过期结果(与设置项说明一致, 也给上轮删除失败项重试机会)
    _schedule_result_cleanup()
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
                "success_codes": success_codes or [],
                "timed_out": False,
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
        fut.add_done_callback(lambda f: _on_wait_future_done(shell_id, f))
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


def _on_wait_future_done(shell_id: str, fut) -> None:
    """等待 Future 结束回调: 正常完成仅解除引用; 被取消(主循环关闭/协程未跑)则兜底杀进程+还槽,
    杜绝孤儿进程与 BoundedSemaphore 永久泄漏(协程没机会进 finally 的窗口)。"""
    _BG_TASKS.discard(fut)
    if not fut.cancelled():
        return
    info = _BG_REGISTRY.get(shell_id)
    if info is None or info.get("status") != "running":
        return
    from app.utils.proc_utils import kill_process_tree
    try:
        kill_process_tree(info["proc"])
    except Exception as e:
        logger.debug(f"[bg_shell] 取消兜底杀进程异常(忽略) {shell_id}: {e}")
    with _BG_LOCK:
        if info.get("status") == "running":
            info["status"] = "killed"
            info["finished_at"] = time.time()
    _release_slot(shell_id)
    logger.warning(f"[bg_shell] 等待协程被取消, 已兜底杀进程并还槽: {shell_id}")


def _file_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def _wait_process(proc: subprocess.Popen, timeout: Optional[float],
                  output_file: str, max_bytes: int):
    """线程池阻塞等待, 返回 (rc, reason); reason=None 正常退出, "oversize" 输出超限。
    timeout 命中抛 subprocess.TimeoutExpired。无超时且无大小上限时一次阻塞到底(零轮询)。
    轮询期间每 2s 检查一次输出文件大小, 超限提前返回, 防磁盘写满拖垮整机。"""
    if timeout is None and not max_bytes:
        return proc.wait(None), None
    deadline = time.monotonic() + timeout if timeout else None
    while True:
        if deadline is None:
            slice_ = 2.0
        else:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(proc.args, timeout)
            slice_ = min(remaining, 2.0)
        try:
            return proc.wait(slice_), None
        except subprocess.TimeoutExpired:
            if deadline is not None and time.monotonic() >= deadline:
                raise
            if max_bytes and _file_size(output_file) > max_bytes:
                return None, "oversize"


async def _kill_tree(proc: subprocess.Popen) -> None:
    """杀进程树 offload 到专用池(不与 tool-sync 争线程); 清理路径吞异常, 绝不再抛。"""
    from app.utils.proc_utils import kill_process_tree
    try:
        await asyncio.wrap_future(_BG_WAIT_POOL.submit(functools.partial(kill_process_tree, proc)))
    except Exception as e:
        logger.debug(f"[bg_shell] 杀进程树异常(忽略): {e}")


async def _await_process(info: dict):
    """等待进程并归一为 (rc, outcome), outcome ∈ {completed, failed, timeout, oversize}。"""
    proc: subprocess.Popen = info["proc"]
    cf = _BG_WAIT_POOL.submit(functools.partial(
        _wait_process, proc, info.get("timeout") or None,
        info["output_file"], _max_output_bytes()))
    try:
        rc, reason = await asyncio.wrap_future(cf)
    except subprocess.TimeoutExpired:
        await _kill_tree(proc)
        return (proc.returncode if proc.returncode is not None else -1), "timeout"
    if reason == "oversize":
        await _kill_tree(proc)
        return (proc.returncode if proc.returncode is not None else -1), "oversize"
    success_codes = info.get("success_codes") or []
    return rc, ("completed" if (rc == 0 or rc in success_codes) else "failed")


async def _finish_and_notify(shell_id: str, info: dict, rc: int, outcome: str) -> None:
    """收尾: 落状态 + 路由完成通知(取消连带杀则跳过通知, 防取消后复活)。"""
    with _BG_LOCK:
        killed = info.get("status") == "killed"
        if not killed:
            info["status"] = "failed" if outcome != "completed" else "completed"
            info["returncode"] = rc
            info["timed_out"] = (outcome == "timeout")
            info["finished_at"] = time.time()
    if killed:
        # 任务取消连带杀: 进程终结是取消动作的一部分, 不再发完成通知(否则会唤醒续跑, 取消后复活)
        logger.info(f"[bg_shell] {shell_id} 已被任务取消连带杀, 跳过完成通知")
        return

    duration = int(info["finished_at"] - info["started_at"])
    tail = _read_output_tail(info["output_file"], 600)
    if outcome == "timeout":
        head = f"[系统通知] 后台命令超时已被终止(shell_id={shell_id}, 超时{info.get('timeout')}s, 耗时{duration}s)"
        hint = "命令未在限定时间内完成, 已强制终止; 请检查是否需优化或延长 timeout"
    elif outcome == "oversize":
        limit_mb = _max_output_bytes() // (1024 * 1024)
        head = f"[系统通知] 后台命令输出超过{limit_mb}MB已被终止(shell_id={shell_id}, 耗时{duration}s)"
        hint = "输出文件过大, 已强制终止防磁盘写满; 请降低输出量或改用日志裁剪"
    elif outcome == "completed":
        head = f"[系统通知] 后台命令已完成(shell_id={shell_id}, 退出码{rc}, 耗时{duration}s)"
        hint = ""
    else:
        head = f"[系统通知] 后台命令失败(shell_id={shell_id}, 退出码{rc}, 耗时{duration}s)"
        hint = "退出码非成功, 请检查输出尾部定位原因"
    text = (f"{head}\n"
            f"命令: {info['command'][:200]}\n"
            f"输出文件: {info['output_file']}\n"
            + (f"提示: {hint}\n" if hint else "")
            + f"输出尾部:\n{tail}")

    try:
        if _BG_NOTIFY_ROUTER is None:
            logger.warning(f"[bg_shell] {shell_id} 通知路由未注册, 降级落盘: {info['output_file']}")
            return
        await _BG_NOTIFY_ROUTER(
            shell_id=shell_id, task_id=info["task_id"], notice_id=info["notice_id"],
            text=text, output_file=info["output_file"])
    except Exception as e:
        logger.error(f"[bg_shell] 通知路由异常({shell_id}): {e}", exc_info=True)


async def _wait_and_notify(shell_id: str) -> None:
    """等待后台进程退出并路由通知(主事件循环协程)。
    等待/杀进程树一律走专用 _BG_WAIT_POOL(与工具共享池隔离); 无论成败 finally 必还槽防泄漏。"""
    info = _BG_REGISTRY.get(shell_id)
    if not info:
        return
    try:
        try:
            rc, outcome = await _await_process(info)
        except Exception as e:
            logger.error(f"[bg_shell] 等待异常({shell_id}): {e}", exc_info=True)
            rc, outcome = -1, "failed"
        await _finish_and_notify(shell_id, info, rc, outcome)
    finally:
        _release_slot(shell_id)
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


def kill_all_background(reason: str = "shutdown") -> int:
    """终态收口: 杀全部 running 后台进程树并还槽。服务关闭时调用, 防孤儿进程跨重启存活。
    同步执行(shutdown 路径允许短暂阻塞); 返回终止的进程数。"""
    from app.utils.proc_utils import kill_process_tree
    with _BG_LOCK:
        targets = [(sid, info) for sid, info in _BG_REGISTRY.items()
                   if info.get("status") == "running"]
    n = 0
    for sid, info in targets:
        try:
            kill_process_tree(info["proc"])
            with _BG_LOCK:
                if info.get("status") == "running":
                    info["status"] = "killed"
                    info["finished_at"] = time.time()
            _release_slot(sid)
            n += 1
            logger.info(f"[bg_shell] {reason} 终止后台进程: {sid}")
        except Exception as e:
            logger.warning(f"[bg_shell] {reason} 终止失败({sid}): {e}")
    return n


def _remove_artifacts(output_file: str) -> bool:
    """删除一次后台命令的全部磁盘产物(输出文件本体 + cmd 启动脚本)。
    全部成功(或已不存在)返回 True; 任一删除失败返回 False, 供调用方保留记录重试。"""
    ok = True
    for path in (output_file, bat_sidecar_path(output_file)):
        if not os.path.exists(path):
            continue
        try:
            os.remove(path)
        except FileNotFoundError:
            continue   # 并发清理已被移除, 视为成功
        except OSError as e:
            logger.warning(f"[bg_shell] 结果产物删除失败(保留记录下轮重试) {path}: {e}")
            ok = False
    return ok


def _schedule_result_cleanup() -> None:
    """结果产物延迟清理(默认24h)。KISS: 惰性清理——后台命令完成时顺带扫过期项, 不起定时器(YAGNI)。
    根治: 先删产物, 删净后才 pop 注册表; 删除失败保留记录, 下一轮清理再试, 避免 pop 后静默吞错成永久孤儿。"""
    now = time.time()
    retain = _retain_seconds()
    with _BG_LOCK:
        expired = [(sid, dict(i)) for sid, i in _BG_REGISTRY.items()
                   if i.get("status") not in ("running", None)
                   and now - i.get("finished_at", now) > retain]
    for sid, info in expired:
        if not _remove_artifacts(info["output_file"]):
            give_up = False
            with _BG_LOCK:
                cur = _BG_REGISTRY.get(sid)
                if cur is not None:
                    cur["cleanup_attempts"] = cur.get("cleanup_attempts", 0) + 1
                    give_up = cur["cleanup_attempts"] >= _BG_CLEANUP_MAX_ATTEMPTS
                    if give_up:
                        _BG_REGISTRY.pop(sid, None)
            if give_up:
                logger.warning(f"[bg_shell] 产物连续{_BG_CLEANUP_MAX_ATTEMPTS}次删除失败, "
                               f"放弃记录(文件疑被存活孙进程占用): {sid}")
            continue   # 产物未删净: 保留注册表项, 下轮重试(达上限则已放弃)
        with _BG_LOCK:
            _BG_REGISTRY.pop(sid, None)
