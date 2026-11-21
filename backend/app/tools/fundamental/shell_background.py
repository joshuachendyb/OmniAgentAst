# -*- coding: utf-8 -*-
# 2026-11-13 商量 - 新建: bash 后台执行模块。非阻塞 Popen + 输出重定向临时文件 +
#   主循环 run_coroutine_threadsafe 提交等待协程 + 完成通知唤醒(注入/续跑/降级落盘三分叉)
# 2026-11-13 商量 - 后台输出目录改走 get_output_dir()(= project_root/output, 与 download_file/
#   generate_chart 同一单源): 原 %TEMP%\omni_bg_shell 与工具层输出基准割裂, 统一归口
# 编辑历史:
# (初版)
# 2026-11-13 商量 - 根治: (1)产物路径单源化 bat_sidecar_path, cmd 启动脚本生成/清理共用,
#   消除 outfile[:-4]+".bat" vs output_file+".bat" 两处推导漂移致 .bat 永不被删; (2)结果清理改"先删产物
#   成功后 pop 注册表", 删除失败保留记录下轮重试, 杜绝 pop 后静默吞 OSError 变永久孤儿; (3)success_codes
#   贯通后台成功判定, 与前台语义一致; (4)完成通知按 完成/失败/超时终止 如实表述, 不再一律"已完成"误导;
#   (5)超时杀进程树 offload 线程池, 不再阻塞主事件循环; (6)保留时长改调用时读配置
# 2026-11-13 商量 - 复核·防卡死根治: (1)后台进程等待改走专用 WorkerPool(_BG_MAX 常驻线程), 与
#   tool-sync 共享池彻底隔离 —— 后台默认无超时, 原 run_in_executor(None) 会让卡死后台永久霸占工具线程池,
#   后台配到 32 时可耗尽全池使文件/网络/DB 工具全部饿死(系统级卡死); (2)等待统一"退出/超时/输出超限"三态,
#   输出文件超 tuning.shell_bg_max_output_mb 即杀进程, 防磁盘写满拖垮整机; (3)新增 kill_all_background 供
#   shutdown 调用, 正常关闭不再遗留孤儿进程; (4)等待 Future 被取消(主循环关闭/协程未跑)时兜底杀进程+还槽,
#   杜绝孤儿进程与信号量永久泄漏; (5)清理失败达上限后放弃记录, 防孙进程持句柄致注册表无限累积
# 2026-11-13 商量 - 10轮复核增量: (1)启动中途异常补杀已启动进程(原只还槽致孤儿); (2)新增
#   cleanup_orphan_artifacts 启动期清理上一世残留产物(重启后注册表为空, 惰性清理覆盖不到, 磁盘泄漏);
#   (3)启动失败不留空 .log 产物; (4)终态语义统一为 outcome 字段(completed/failed/timeout/oversize/killed),
#   原 timed_out 布尔信息量不足致查询无法区分超时/超限/失败; (5)补后台启动与结束 info 日志(成功路径此前无日志)
# 2026-11-21 小欧 三堂会审整改: 启动期孤儿清理改扫全集(_bg_output_dirs): 输出已按会话工作区落盘,
#   只扫当前分配口(启动期无会话快照→项目根/output)会漏掉各会话目录里的上一世 .log/.bat
# 2026-11-21 小欧 计时整改(规范 2.2 不设豁免): run_shell_background 与 _bg_error 的 duration_ms
#   原硬编码 0(真启动进程却报 0 毫秒), 改 t0/_dur 实测启动动作墙钟耗时; 同步订正注册表
#   outcome 初值注释(初值 running=未结束, 终态才写 completed/failed/timeout/oversize/killed) — 小欧-2026-11-21
# 2026-11-21 小欧 删除查询工具配套读口: 后台查询工具删除后, 只被它调用的 get_bg_info /
#   find_bg_by_output_file 无调用方, 一并删除(不留死代码); 注册表仍是后台状态的唯一真源, 仅供本模块内部使用
# 2026-11-21 小欧 完成通知整改: 前缀统一 [后台通知] 后台shell 执行完成/失败/超时已被强制终止/输出超限;
#   t_end_mono 改在"判定结束"瞬间记录(杀进程树耗时不再算进命令耗时, 修"限时1s/耗时4.3s"自相矛盾);
#   _await_process 返回 (rc, outcome, t_end), 输出上限取注册表启动值(通知阈值与强杀判据同源);
#   新增 _fmt_duration/_rc_text/_cmd_display/_start_params: 快命令不再恒显 0.0s、退出码带含义(单源
#   EXIT_CODE_MEANING, success_codes 命中不套失败含义)、负码写"退出码未知"、长命令截断留省略号、
#   启动返回 action.params 补 shell_type/cwd; 输出尾部声明截断、无输出写"(无输出)"、末行加核查提示;
#   kill_background_by_task 补锁内二次校验 outcome(防覆盖等待协程已写的真实终态) — 小欧-2026-11-21
# 2026-11-21 小欧 三堂会审补漏: 拆出 _build_notice_text(纯函数, 只拼文案不发路由) 与 persist_notice_text
#   (路由未注册/异常时把通知正文追加进输出文件, 不再只留一行日志); 超限通知补报实际已写大小;
#   被外部终止(任务取消/服务关闭/等待协程取消)在输出文件尾写终止说明, 不再完全无痕 — 小欧-2026-11-21
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
from pathlib import Path
from typing import Any, Dict, Optional

from app.config import get_config
from app.logger import logger
from app.tools.tool_constants import ERR_SHELL_EXCEPTION, EXIT_CODE_MEANING
from app.tools.tool_response import build_error, build_success
from app.utils.workers import WorkerPool

# ── 全局态 ──────────────────────────────────────────────
_BG_REGISTRY: Dict[str, dict] = {}   # {shell_id: {proc, output_file, task_id, command, shell_type, outcome, started_at, t0_mono, timeout, notice_id, sem_released}}
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
_NOTICE_TAIL_CHARS = 600       # 完成通知附带的输出尾部字符数(超则只给尾部并在正文声明截断) — 小欧-2026-11-21
_NOTICE_CMD_CHARS = 200        # 完成通知里的命令展示上限(超则加省略号) — 小欧-2026-11-21
_NOTICE_FOOTER = "[结合上下文,核查执行结果]"   # 通知末行: 提醒 LLM 结合上下文核对结果 — 小欧-2026-11-21
HD_Notice = "[后台通知]"                       # 后台完成通知正文前缀(唯一生产者在本模块) — 小欧-2026-11-21


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
    # 2026-11-20 小欧: 后台输出目录改走 get_tool_dir("output")(会话默认目录优先,
    #   兜底项目根), 与 download_file/generate_chart 同一分配口
    from app.utils.path_utils import get_tool_dir
    d = get_tool_dir("output")
    os.makedirs(d, exist_ok=True)
    return d


def _bg_output_dirs() -> list[str]:
    """后台产物目录全集: 当前分配口 + 项目根下各会话工作区的 output/。

    输出已按会话工作区落盘, 启动期没有会话快照(get_tool_dir 回落项目根), 只扫当前分配口会漏掉
    各会话目录里的上一世产物; 会话工作区固定为 {项目根}/{时间戳-会话}/output, 故按目录布局枚举。
    2026-11-21 小欧 - 枚举改走 get_tool_dir_path(只算不建): 本函数唯一调用方是启动期孤儿产物清理,
      属只读扫盘; 原调 get_tool_dir 会在每次启动无快照时把空 output/ 建到用户项目根。
    """
    from app.utils.path_utils import get_tool_dir_path
    dirs = [str(get_tool_dir_path("output"))]
    root = get_config().get_project_root()
    dirs += [str(p) for p in Path(root).glob("*/output") if p.is_dir()]
    return list(dict.fromkeys(dirs))


def _start_params(command: str, shell_type: str, cwd: Optional[str]) -> Dict[str, Any]:
    """异步启动的 action.params: 与前台同口径带 shell_type, cwd 非空才留痕 — 小欧-2026-11-21"""
    p: Dict[str, Any] = {"command": command, "background": True}
    if shell_type:
        p["shell_type"] = shell_type
    if cwd:
        p["cwd"] = cwd
    return p


def _bg_error(command: str, cmd_short: str, detail: str, hint: str,
              duration_ms: int = 0, shell_type: str = "",
              cwd: Optional[str] = None) -> Dict[str, Any]:
    """后台启动失败出口。duration_ms 由调用方按真实耗时传入(规范 2.2 禁硬编码) — 小欧-2026-11-21"""
    return build_error(data={}, llm_data={
        "summary": f"后台执行Shell命令{cmd_short}",
        "action": {"tool": "bash", "tool_zh": "执行",
                   "params": _start_params(command, shell_type, cwd)},
        "status": {"exec_code": "error", "message": "失败", "code": ERR_SHELL_EXCEPTION,
                   "detail": detail, "hint": hint},
        "duration_ms": duration_ms, "metrics": {}})


def run_shell_background(command: str, shell_type: str, cwd: Optional[str],
                          task_id: str, cmd_short: str,
                          popen_factory, timeout: Optional[int] = None,
                          success_codes: Optional[list[int]] = None) -> Dict[str, Any]:
    """启动后台命令并立即返回。popen_factory: 由调用方注入(Popen 构造, 复用 shell() 各
    shell_type 的启动参数装配, 避免本模块重复实现四种 shell 的命令行拼装 DRY)。
    返回 build_success 标准格式, data={}(启动无结果本体; shell_id/output_file 在 llm_data.metrics)。

    duration_ms 为"本次启动动作"的真实墙钟耗时(进程起完即返回, 不等于命令运行时长),
    按规范 2.2 由 t0 计时, 不得硬编码 0 — 小欧-2026-11-21
    """
    t0 = time.perf_counter()

    def _dur() -> int:
        return int((time.perf_counter() - t0) * 1000)

    if _MAIN_LOOP is None:
        return _bg_error(command, cmd_short,
                         "主事件循环未初始化, 后台执行不可用", "服务启动中, 请稍后重试",
                         _dur(), shell_type, cwd)
    # 新后台命令启动时顺带清理过期结果(与设置项说明一致, 也给上轮删除失败项重试机会)
    _schedule_result_cleanup()
    if not _BG_SEM.acquire(blocking=False):
        return _bg_error(command, cmd_short,
                         f"后台并发已达上限({_BG_MAX}), 请等待现有后台命令结束",
                         "属容量管理, 非命令本身错误", _dur(), shell_type, cwd)
    shell_id = ""
    proc = None
    try:
        shell_id = _new_shell_id()
        output_file = os.path.join(_bg_output_dir(), f"{shell_id}.log")
        # stdout/stderr 合流写文件(2>&1 语义); 进程写端只管追加, 结果文件按保留时长惰性清理
        with open(output_file, "ab"):
            pass
        proc = popen_factory(command, cwd, output_file)
        if proc is None:
            _BG_SEM.release()
            try:   # 启动失败不留空产物(无注册表记录 → 惰性清理覆盖不到)
                os.remove(output_file)
            except OSError:
                pass
            return _bg_error(command, cmd_short, "后台进程启动失败", "请检查命令与解释器",
                             _dur(), shell_type, cwd)
        with _BG_LOCK:
            _BG_REGISTRY[shell_id] = {
                "proc": proc, "output_file": output_file, "task_id": task_id,
                "command": command, "shell_type": shell_type, "cwd": cwd or "",
                "started_at": time.time(), "t0_mono": time.monotonic(),
                "timeout": timeout,
                # 启动时定下输出上限, 等待/通知共用同一个值(通知里报的阈值必须与强杀判据一致)
                "max_output_bytes": _max_output_bytes(),
                "success_codes": success_codes or [],
                # 状态单一真源: outcome ∈ running(未结束)/completed/failed/timeout/oversize/killed。
                # 原另存一份 status(少 timeout/oversize 两词) 与 outcome 表达同一件事, 已删 — 小欧-2026-11-21
                "outcome": "running",
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
                             f"等待协程提交失败: {_sub_e}", "服务正在关闭, 请稍后重试",
                             _dur(), shell_type, cwd)
        _BG_TASKS.add(fut)
        fut.add_done_callback(lambda f: _on_wait_future_done(shell_id, f))
        logger.info(f"[bg_shell] 后台已启动 {shell_id} (task={task_id}, type={shell_type}, "
                    f"timeout={timeout}, out={output_file})")
        return build_success(
            # 异步启动没有"结果本体": shell_id/output_file 只是指针, 已进 llm_data.metrics,
            # data 留空防与统计段重复(原三键与 metrics 完全重复, LLM 看到两遍) — 小欧-2026-11-21
            data={},
            llm_data={
                "summary": f"后台执行Shell命令{cmd_short}",
                "action": {"tool": "bash", "tool_zh": "执行",
                           "params": _start_params(command, shell_type, cwd)},
                "status": {"exec_code": "success", "message": "成功",
                           "code": "", "detail": "",
                           "hint": "完成时会自动收到系统通知并自动继续处理, 不要轮询等待; "
                                   "期间可继续其他工作或直接结束回答"},
                "duration_ms": _dur(),
                "metrics": {"shell_id": {"value": shell_id, "text": f"后台ID {shell_id}"},
                            "output_file": {"value": output_file, "text": "输出文件"}}})
    except Exception as e:
        # 启动中途异常: 已启动的进程必须杀掉(否则成孤儿), 且信号量只还一次
        if proc is not None:
            from app.utils.proc_utils import kill_process_tree
            try:
                kill_process_tree(proc)
            except Exception:
                pass
        with _BG_LOCK:
            _info = _BG_REGISTRY.get(shell_id)
            if _info is not None:
                _info["sem_released"] = True
        _BG_SEM.release()
        logger.error(f"[bg_shell] 后台启动异常: {e}", exc_info=True)
        return _bg_error(command, cmd_short, str(e), "后台启动异常", _dur(), shell_type, cwd)


def _release_slot(shell_id: str) -> None:
    """信号量只还一次(锁内标记, 防 wait/kill 竞争双释放 BoundedSemaphore) — 商量 2026-11-13"""
    with _BG_LOCK:
        info = _BG_REGISTRY.get(shell_id)
        if info is None or info.get("sem_released"):
            return
        info["sem_released"] = True
    _BG_SEM.release()


def _elapsed_s(info: dict) -> float:
    """命令运行时长(秒, 不取整): monotonic 起点/终点相减, 不受系统调时间影响; 展示交给 _fmt_duration。
    原实现用 time.time() 差值且 int 截断, 调时间会算出负值/错值 — 小欧-2026-11-21"""
    t0 = info.get("t0_mono")
    t_end = info.get("t_end_mono")
    if t0 is None or t_end is None:
        return 0.0
    return max(t_end - t0, 0.0)


def _fmt_duration(seconds: float) -> str:
    """耗时展示: <1s 两位小数(快命令不再恒显 0.0s), <60s 一位, ≥60s 分秒 — 小欧-2026-11-21"""
    if seconds < 1:
        return f"{seconds:.2f}s"
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{int(seconds // 60)}m{int(seconds % 60)}s"


def _rc_text(rc: int, success: bool = False) -> str:
    """退出码展示: 已知码带含义(单源 EXIT_CODE_MEANING), 未收录只给数字, 负值=无有效退出码。
    success=True 表示 rc 已被 success_codes 判为成功: 此时不套失败含义, 否则"执行完成"里会出现"通用错误"。
    原实现直接写"退出码-1", LLM 会当成真实退出码 — 小欧-2026-11-21"""
    if rc is None or rc < 0:
        return "退出码未知"
    if success and rc != 0:
        return f"退出码{rc}(已按成功码判定)"
    meaning = EXIT_CODE_MEANING.get(rc)
    return f"退出码{rc}({meaning})" if meaning else f"退出码{rc}"


def _cmd_display(command: str, limit: int = _NOTICE_CMD_CHARS) -> str:
    """通知里的命令展示: 超长必须留省略号, 静默截断会让 LLM 对不上自己发的命令 — 小欧-2026-11-21"""
    return command if len(command) <= limit else command[:limit] + "…"


def _fmt_bytes(n: int) -> str:
    """字节数展示: <1KB 给 B, <1MB 给 KB, 其余给 MB。
    原按 //(1024*1024) 取整, 上限配成 512KB 时会显示"上限0MB" — 小欧-2026-11-21"""
    if n < 1024:
        return f"{n}B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f}KB"
    return f"{n / (1024 * 1024):.1f}MB"


def _mark_terminated(info: dict, reason: str) -> None:
    """被外部终止(任务取消/服务关闭/等待协程取消)时在输出文件尾部落一条终止说明。
    这类终止刻意不发完成通知(发了会唤醒续跑, 取消后复活), 但不落痕则事后完全查不到
    这条命令是怎么没的(输出文件停在半截, 注册表重启即丢) — 小欧-2026-11-21"""
    marker = (f"\n{HD_Notice} 后台shell 执行被终止({reason}, 退出码未知, "
              f"实际运行{_fmt_duration(_elapsed_s(info))})\n")
    try:
        with open(info["output_file"], "ab") as f:
            f.write(marker.encode("utf-8"))
    except OSError as e:
        logger.debug(f"[bg_shell] 终止标记写入失败(忽略) {info.get('output_file')}: {e}")


def _on_wait_future_done(shell_id: str, fut) -> None:
    """等待 Future 结束回调: 正常完成仅解除引用; 被取消(主循环关闭/协程未跑)则兜底杀进程+还槽,
    杜绝孤儿进程与 BoundedSemaphore 永久泄漏(协程没机会进 finally 的窗口)。"""
    _BG_TASKS.discard(fut)
    if not fut.cancelled():
        return
    info = _BG_REGISTRY.get(shell_id)
    if info is None or info.get("outcome") != "running":
        return
    from app.utils.proc_utils import kill_process_tree
    try:
        kill_process_tree(info["proc"])
    except Exception as e:
        logger.debug(f"[bg_shell] 取消兜底杀进程异常(忽略) {shell_id}: {e}")
    with _BG_LOCK:
        if info.get("outcome") == "running":
            info["outcome"] = "killed"
            info["finished_at"] = time.time()
            info["t_end_mono"] = time.monotonic()
            info["duration_s"] = _elapsed_s(info)
    _mark_terminated(info, "等待协程被取消")
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
    """等待进程并归一为 (rc, outcome, t_end_mono), outcome ∈ {completed, failed, timeout, oversize}。
    t_end_mono 在"判定结束"那一瞬记录: 杀进程树要几秒, 放到杀完再记会把杀进程时间算进命令耗时。
    输出上限用注册表启动时定下的值, 不重新读配置(否则通知里的阈值与实际强杀判据可能不一致) — 小欧-2026-11-21"""
    proc: subprocess.Popen = info["proc"]
    cf = _BG_WAIT_POOL.submit(functools.partial(
        _wait_process, proc, info.get("timeout") or None,
        info["output_file"], info.get("max_output_bytes") or 0))
    try:
        rc, reason = await asyncio.wrap_future(cf)
    except subprocess.TimeoutExpired:
        t_end = time.monotonic()
        await _kill_tree(proc)
        return (proc.returncode if proc.returncode is not None else -1), "timeout", t_end
    t_end = time.monotonic()
    if reason == "oversize":
        await _kill_tree(proc)
        return (proc.returncode if proc.returncode is not None else -1), "oversize", t_end
    success_codes = info.get("success_codes") or []
    return rc, ("completed" if (rc == 0 or rc in success_codes) else "failed"), t_end


def _build_notice_text(shell_id: str, info: dict, rc: int, outcome: str) -> str:
    """拼完成通知正文(纯函数: 只读注册表快照, 不写状态不发路由, 便于单测) — 小欧-2026-11-21"""
    duration = _fmt_duration(info.get("duration_s") or 0.0)
    tail, truncated = _read_output_tail(info["output_file"], _NOTICE_TAIL_CHARS)
    rc_text = _rc_text(rc, success=(outcome == "completed"))
    if outcome == "timeout":
        head = (f"{HD_Notice} 后台shell 执行超时已被强制终止(shell_id={shell_id}, "
                f"限时{info.get('timeout')}s, 实际运行{duration})")
        hint = "命令未在限定时间内完成, 已强制终止; 请检查是否需优化命令或调大 timeout"
    elif outcome == "oversize":
        limit = info.get("max_output_bytes") or 0
        written = _file_size(info["output_file"])
        head = (f"{HD_Notice} 后台shell 输出达{_fmt_bytes(written)}(上限{_fmt_bytes(limit)})已被强制终止"
                f"(shell_id={shell_id}, {rc_text}, 实际运行{duration})")
        hint = "输出文件过大, 已强制终止防磁盘写满; 请降低输出量或把输出重定向到文件"
    elif outcome == "completed":
        head = f"{HD_Notice} 后台shell 执行完成(shell_id={shell_id}, {rc_text}, 耗时{duration})"
        hint = ""
    else:
        head = f"{HD_Notice} 后台shell 执行失败(shell_id={shell_id}, {rc_text}, 耗时{duration})"
        # 等待环节自身异常时 rc=-1, 此时"退出码非成功"的解释不成立, 不能笼统说去尾部找原因
        hint = ("等待进程时异常, 未能取得退出码, 请检查输出文件判断命令是否已执行"
                if rc < 0 else "非成功退出, 详细原因见输出尾部")
    lines = [head, f"命令: {_cmd_display(info['command'])}"]
    if info.get("cwd"):
        lines.append(f"工作目录: {info['cwd']}")
    if info.get("shell_type"):
        lines.append(f"Shell类型: {info['shell_type']}")
    lines.append(f"输出文件: {info['output_file']}（完整输出可读此文件）")
    if hint:
        lines.append(f"提示: {hint}")
    lines.append(f"输出尾部(仅最后{_NOTICE_TAIL_CHARS}字符):" if truncated else "输出尾部:")
    lines.append(tail or "(无输出)")
    lines.append(_NOTICE_FOOTER)
    return "\n".join(lines)


def persist_notice_text(output_file: str, text: str) -> None:
    """通知投不出去时(无会话归属/inbox满/续跑失败/路由未注册/路由异常)把正文追加到输出文件尾部:
    否则 LLM 永远收不到"命令已结束"这条事实, 磁盘上只剩裸输出 — 小欧-2026-11-21"""
    try:
        with open(output_file, "ab") as f:
            f.write(("\n" + text + "\n").encode("utf-8"))
    except OSError as e:
        logger.warning(f"[bg_shell] 通知落盘失败 {output_file}: {e}")


async def _finish_and_notify(shell_id: str, info: dict, rc: int, outcome: str,
                             t_end_mono: float) -> None:
    """收尾: 落状态 + 路由完成通知(取消连带杀则跳过通知, 防取消后复活)。
    t_end_mono 由调用方在"判定结束"瞬间记录, 杀进程树耗时不计入命令耗时 — 小欧-2026-11-21"""
    with _BG_LOCK:
        killed = info.get("outcome") == "killed"
        if not killed:
            info["outcome"] = outcome
            info["returncode"] = rc
            info["finished_at"] = time.time()
            info["t_end_mono"] = t_end_mono
            info["duration_s"] = _elapsed_s(info)
    if killed:
        # 任务取消连带杀: 进程终结是取消动作的一部分, 不再发完成通知(否则会唤醒续跑, 取消后复活)
        logger.info(f"[bg_shell] {shell_id} 已被任务取消连带杀, 跳过完成通知")
        return

    text = _build_notice_text(shell_id, info, rc, outcome)
    logger.info(f"[bg_shell] 后台已结束 {shell_id} outcome={outcome} rc={rc} "
                f"耗时{_fmt_duration(info['duration_s'])}")
    if _BG_NOTIFY_ROUTER is None:
        logger.warning(f"[bg_shell] {shell_id} 通知路由未注册, 降级落盘: {info['output_file']}")
        persist_notice_text(info["output_file"], text)
        return
    try:
        await _BG_NOTIFY_ROUTER(
            shell_id=shell_id, task_id=info["task_id"], notice_id=info["notice_id"],
            text=text, output_file=info["output_file"])
    except Exception as e:
        logger.error(f"[bg_shell] 通知路由异常({shell_id}): {e}", exc_info=True)
        persist_notice_text(info["output_file"], text)


async def _wait_and_notify(shell_id: str) -> None:
    """等待后台进程退出并路由通知(主事件循环协程)。
    等待/杀进程树一律走专用 _BG_WAIT_POOL(与工具共享池隔离); 无论成败 finally 必还槽防泄漏。"""
    info = _BG_REGISTRY.get(shell_id)
    if not info:
        return
    try:
        try:
            rc, outcome, t_end = await _await_process(info)
        except Exception as e:
            logger.error(f"[bg_shell] 等待异常({shell_id}): {e}", exc_info=True)
            rc, outcome, t_end = -1, "failed", time.monotonic()
        await _finish_and_notify(shell_id, info, rc, outcome, t_end)
    finally:
        _release_slot(shell_id)
        _schedule_result_cleanup()


def _read_output_tail(path: str, max_chars: int) -> tuple[str, bool]:
    """读输出文件尾部, 返回 (文本, 是否被截断)。

    只给尾部却不说截断, LLM 会把尾部当完整输出(真错误在最前面时就会误判"日志里没有错误"),
    故截断标记必须回给调用方写进通知 — 小欧-2026-11-21
    """
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            if size > max_chars * 4:
                f.seek(-max_chars * 4, os.SEEK_END)
            data = f.read()
    except OSError as e:
        # 读不到尾部不等于没输出, 必须留痕: 通知里只能给"读取失败", 排障要看日志 — 小欧-2026-11-21
        logger.warning(f"[bg_shell] 读取输出尾部失败 {path}: {e}")
        return "(输出文件读取失败)", False
    text = data.decode("utf-8", errors="replace")
    return text[-max_chars:], len(text) > max_chars


def kill_background_by_task(task_id: str) -> int:
    """任务 cancelled 连带杀: 终结本 task_id 名下全部后台进程。返回杀掉数。"""
    from app.utils.proc_utils import kill_process_tree
    n = 0
    with _BG_LOCK:
        targets = [sid for sid, i in _BG_REGISTRY.items() if i["task_id"] == task_id]
    for sid in targets:
        info = _BG_REGISTRY.get(sid)
        if info and info.get("outcome") == "running":
            try:
                kill_process_tree(info["proc"])
                with _BG_LOCK:
                    # 锁内二次校验: 锁外判定到加锁之间等待协程可能已写终态(completed/timeout),
                    #   无条件覆盖成 killed 会抹掉真实终态与耗时, 与 kill_all_background 同口径 — 小欧-2026-11-21
                    _killed = info.get("outcome") == "running"
                    if _killed:
                        info["outcome"] = "killed"
                        info["finished_at"] = time.time()
                        info["t_end_mono"] = time.monotonic()
                        info["duration_s"] = _elapsed_s(info)
                if _killed:
                    _mark_terminated(info, "任务取消")
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
                   if info.get("outcome") == "running"]
    n = 0
    for sid, info in targets:
        try:
            kill_process_tree(info["proc"])
            with _BG_LOCK:
                _killed = info.get("outcome") == "running"
                if _killed:
                    info["outcome"] = "killed"
                    info["finished_at"] = time.time()
                    info["t_end_mono"] = time.monotonic()
                    info["duration_s"] = _elapsed_s(info)
            if _killed:
                _mark_terminated(info, reason)
                _release_slot(sid)
                n += 1
                logger.info(f"[bg_shell] {reason} 终止后台进程: {sid}")
        except Exception as e:
            logger.warning(f"[bg_shell] {reason} 终止失败({sid}): {e}")
    return n


def cleanup_orphan_artifacts(not_after: float) -> int:
    """启动期清理孤儿产物(服务重启收口)。返回删除文件数。

    背景: 结果文件惰性清理只走注册表, 服务重启后注册表为空 → 上一世的后台 .log/.bat
    永不被清理, 长期残留吃磁盘。此处一次性收口。
    安全: 只删 (a) 本模块命名空间 bgsh_* 前缀 (b) mtime 早于 not_after(启动时刻) 的文件;
    活跃进程仍在追加写的文件 mtime 会刷新, 不会被误删; 其他工具的产物一律不动。"""
    import glob
    n = 0
    for d in _bg_output_dirs():
        for pattern in (f"bgsh_*{_BG_SIDECAR_SUFFIX}", "bgsh_*.log"):
            for path in glob.glob(os.path.join(d, pattern)):
                try:
                    if os.path.getmtime(path) >= not_after:
                        continue
                    os.remove(path)
                    n += 1
                except OSError as e:
                    logger.warning(f"[bg_shell] 启动期孤儿产物删除失败 {path}: {e}")
    if n:
        logger.info(f"[bg_shell] 启动期清理孤儿结果产物 {n} 个(上一世后台命令残留)")
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
                   if i.get("outcome") not in ("running", None)
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
