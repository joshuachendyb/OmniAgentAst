# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-26 - 小欧 - 新建: 进程宿主客户端(自愈重建, run() 与 drain 语义对齐)
# 2026-11-26 - 小欧 - 修正: 补启动期 ensure_host(请求期零 Popen)/连接与接收真实截止时间/
#                     每实例管道名与 authkey/协议版本握手/单飞重建
# 2026-11-26 - 小欧 - 阶段零/一整改([66]): 宿主 Popen 显式 cwd/PYTHONPATH(修复非 backend 目录
#                     启动 ModuleNotFoundError); 注入 OMNI_PROC_HOST_CONCURRENCY(外部已设优先,
#                     否则 max(12, shell_max_processes), 宿主不得比主进程闸门更紧); 连接失败/超时
#                     且期间无人替换宿主时杀旧宿主重建(卡死宿主旧管道不销毁会让辅助线程永久阻塞)
# 2026-11-26 - 小欧 - 阶段H底座加固([65] 6.4): ①_spawn_host 合并 isolation_kwargs(宿主不继承控制台,
#                     消除 CreateProcessW 卡 conhost 诱因); ②熔断/退避(0.5→30s 封顶, 连败 5 次开、
#                     冷却 30s、半开探测、同因日志 60s 去重); ③请求路径 _connect 零创建(只连 + 有界
#                     等待监护人重建, 熔断期间快速失败); ④后台监护人 daemon 线程每 5s ping/pong
#                     判死并在退避内重建; ⑥run 输出总量上限(OMNI_PROC_HOST_MAX_OUTPUT, 默认 64MB,
#                     超限置 truncated + 追加 TRUNCATED_NOTE, 防 OOM)。⑤宿主 ping/pong 见 host.py。
"""client — 与 drain_until_exit 语义对齐的宿主调用层

对外两个入口:
  ensure_host()  启动期调用, 拉起宿主并等就绪 + 启动后台监护人; 请求路径不再创建进程。
  run()          返回五元组 (stdout_b, stderr_b, timed_out, truncated, rc)。

生命周期模型(阶段二):
  - 后台监护人(daemon)是运行期唯一的"创建/重建"发起者: 每 5s ping, 判死即按熔断退避重建。
  - 请求路径零创建: _connect 只连接; 宿主不可用时向监护人发唤醒并在有界预算内等其重建,
    仍不可用则快速 HostError。熔断打开期间不等待, 立即失败。
  - 自愈: 宿主被外部杀/崩溃 → 监护人在退避内重建; 在飞命令显式 HostError, 后续命令恢复。
降级: OMNI_PROC_HOST=0 时抛 Disabled(仅验证期存在的应急开关)。
"""
import os
import subprocess
import sys
import threading
import time
import uuid
from multiprocessing.connection import Client
from typing import Optional, Tuple

from app.proc_host import PROTO  # 协议版本唯一真源(包 __init__), 与宿主必须一致

_CONNECT_TIMEOUT = 3.0      # 单次连接尝试上限
_START_WAIT = 5.0           # 拉起宿主后等其就绪的上限
_RECV_SLACK = 5.0           # 接收截止 = 命令 timeout + 本余量(覆盖杀树/收尾/时钟抖动)
_CHUNK_WAIT = 0.2           # 单次 poll 粒度
_PING_INTERVAL = 5.0        # 监护人巡检间隔
_PING_TIMEOUT = 3.0         # 单次 ping 等 pong 上限(超过判僵死)
_BACKOFF = (0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 30.0)  # 重建退避阶梯(秒, 封顶 30)
_BREAKER_THRESHOLD = 5      # 连续启动失败达到该值即熔断
_BREAKER_COOLDOWN = 30.0    # 熔断冷却(秒); 冷却后半开探测
_START_RETRY_DELAYS = (0.5, 1.0, 2.0)             # ensure_host 启动期重试间隔
_DEFAULT_MAX_OUTPUT = 64 * 1024 * 1024            # 单命令输出总量上限(字节)
_LOG_THROTTLE = 60.0        # 同因日志去重窗口(秒)

_pipe_name: Optional[str] = None
_authkey: Optional[bytes] = None
_host_proc: Optional[subprocess.Popen] = None
_host_lock = threading.Lock()          # 保护 _host_proc 的创建/替换(单飞)
_guardian_lock = threading.Lock()
_guardian_thread: Optional[threading.Thread] = None
_wake_event = threading.Event()        # 请求路径唤醒监护人立即巡检/重建

_fail_count = 0                # 连续启动失败计数
_next_attempt_ts = 0.0         # 退避: 早于该时刻不重建(monotonic)
_breaker_open = False          # 熔断是否打开
_breaker_until = 0.0           # 熔断冷却截止(monotonic)
_last_log_key: Optional[str] = None
_last_log_ts = 0.0


class Disabled(RuntimeError):
    """宿主被配置关闭; 调用方按降级策略处理(仅验证期)。"""


class HostError(RuntimeError):
    """宿主不可用(启动失败/中途死亡/无响应)。"""


def _enabled() -> bool:
    return os.environ.get("OMNI_PROC_HOST", "1") != "0"


def _identity() -> Tuple[str, bytes]:
    """本实例的管道名与 authkey: 每进程唯一, 由本进程生成后经环境变量传给宿主。

    写死常量的两个后果: ①开发态与打包态、两个用户会话互抢同一管道; ②固定 authkey
    等于对本机任意进程开放"执行任意命令"的能力。
    """
    global _pipe_name, _authkey
    if _pipe_name is None:
        _pipe_name = rf"\\.\pipe\omni-proc-host-{uuid.uuid4().hex}"
        _authkey = os.urandom(32)
    return _pipe_name, _authkey


def _app_root() -> str:
    """应用根: frozen=exe 同级, 源码=backend 目录。宿主以 -m 拉起时须以此为 cwd/PYTHONPATH。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _default_log_path() -> str:
    """宿主日志绝对路径(与 app.logger 的 LOG_DIR 同源): frozen=exe同级/logs, 源码=backend/logs。"""
    return os.path.join(_app_root(), "logs", "proc_host.log")


def _host_concurrency() -> int:
    """宿主并发上限: 外部已设优先; 否则 max(12, 主进程 shell_max_processes)。

    宿主不得比主进程 _SHELL_PROC_SEM 更紧, 否则配置调大后宿主先限流、两级排队口径冲突([66] 问题四)。
    """
    env_val = os.environ.get("OMNI_PROC_HOST_CONCURRENCY")
    if env_val:
        try:
            return max(1, int(env_val))
        except ValueError:
            pass
    try:
        from app.config import get_config
        shell_max = int(get_config().get("tuning.concurrency.shell_max_processes", 10))
    except Exception:
        shell_max = 10
    return max(12, shell_max)


def _max_output() -> int:
    """单命令输出总量上限: OMNI_PROC_HOST_MAX_OUTPUT(字节), 默认 64MB, 下限 1KB。"""
    try:
        return max(1024, int(os.environ.get("OMNI_PROC_HOST_MAX_OUTPUT", str(_DEFAULT_MAX_OUTPUT))))
    except (TypeError, ValueError):
        return _DEFAULT_MAX_OUTPUT


def _log_event(key: str, msg: str, throttle: float = _LOG_THROTTLE) -> None:
    """按 key 去重的告警日志(同因 60s 内只落一条), 降噪而不是丢失。"""
    global _last_log_key, _last_log_ts
    now = time.monotonic()
    if throttle > 0 and key == _last_log_key and now - _last_log_ts < throttle:
        return
    _last_log_key = key
    _last_log_ts = now
    try:
        from app.logger import logger
        logger.warning(f"[proc_host] {msg}")
    except Exception:
        pass


def _note_failure(cause: str) -> None:
    """登记一次启动失败: 推进退避阶梯, 达阈值打开熔断。"""
    global _fail_count, _next_attempt_ts, _breaker_open, _breaker_until
    _fail_count += 1
    _next_attempt_ts = time.monotonic() + _BACKOFF[min(_fail_count - 1, len(_BACKOFF) - 1)]
    if _fail_count >= _BREAKER_THRESHOLD and not _breaker_open:
        _breaker_open = True
        _breaker_until = time.monotonic() + _BREAKER_COOLDOWN
        _log_event(
            "breaker",
            f"熔断开启: 连续 {_fail_count} 次启动失败, 冷却 {_BREAKER_COOLDOWN:.0f}s; 末次原因: {cause}",
            throttle=0.0,
        )
    else:
        _log_event("spawn-fail", f"宿主启动失败({_fail_count}/{_BREAKER_THRESHOLD}): {cause}")


def _note_success() -> None:
    """宿主健康: 清零失败计数并关闭熔断。"""
    global _fail_count, _next_attempt_ts, _breaker_open, _breaker_until
    if _breaker_open:
        _log_event("breaker-close", "熔断关闭: 宿主已恢复", throttle=0.0)
    _fail_count = 0
    _next_attempt_ts = 0.0
    _breaker_open = False
    _breaker_until = 0.0


def _can_attempt_spawn(ignore_backoff: bool = False) -> bool:
    """是否允许发起一次重建: 熔断冷却期内否; 冷却后半开放行一次探测;
    ignore_backoff=True 时忽略退避阶梯(用于僵死宿主杀后立即重建), 但仍受熔断约束。"""
    now = time.monotonic()
    if _breaker_open:
        return now >= _breaker_until
    if ignore_backoff:
        return True
    return now >= _next_attempt_ts


def _client_with_deadline(deadline: float):
    """在截止时间内完成连接。

    AF_PIPE 的 Client() 内部是 WaitNamedPipe(1s)/20s 上限的轮询, 宿主活着但不 accept 时
    仍会阻塞远超命令预算, 等于把"宿主卡死"传导成"主进程线程长阻塞", 与 E1 目标相反。
    故把连接放进辅助线程, 主线程只做有界 join。
    """
    box = {}
    name, key = _identity()

    def _do():
        try:
            box["conn"] = Client(name, authkey=key)
        except Exception as e:      # AuthenticationError/OSError/EOFError
            box["err"] = e

    t = threading.Thread(target=_do, daemon=True)
    t.start()
    t.join(max(0.0, deadline - time.monotonic()))
    if t.is_alive():
        raise HostError("连接宿主超时(宿主可能卡死)")
    if "err" in box:
        raise box["err"]
    return box["conn"]


def _kill_host() -> None:
    """杀掉宿主进程后清空状态; 重建由监护人发起。

    宿主卡在 CreateProcessW 时不响应, 只能从外部杀。TerminateProcess 不需要宿主配合,
    因此这里不会因为宿主卡死而卡住。锁自由: 仅替换全局引用(原子), 避免与 _spawn_host
    (持 _host_lock)在"宿主启动超时"路径上自嵌套死锁。
    """
    global _host_proc
    p = _host_proc
    _host_proc = None
    if p is None:
        return
    try:
        p.kill()
        p.wait(timeout=5)
    except Exception:
        pass


def _spawn_host() -> None:
    """拉起宿主(调用方须持 _host_lock)。用 isolation_kwargs 切断控制台继承。"""
    global _host_proc
    pipe_name, authkey = _identity()
    root = _app_root()
    if getattr(sys, "frozen", False):
        argv = [sys.executable, "--proc-host"]
    else:
        argv = [sys.executable, "-m", "app.proc_host.host"]
    env = dict(os.environ)
    env["OMNI_PROC_HOST_PIPE"] = pipe_name
    env["OMNI_PROC_HOST_KEY"] = authkey.hex()
    env["OMNI_PROC_HOST_PARENT_PID"] = str(os.getpid())
    env["OMNI_PROC_HOST_LOG"] = _default_log_path()
    env["OMNI_PROC_HOST_CONCURRENCY"] = str(_host_concurrency())
    if not getattr(sys, "frozen", False):
        # -m 依赖 sys.path 含 backend 根: 显式注入 cwd/PYTHONPATH, 不再依赖调用方 cwd([66] 问题五)
        prev = env.get("PYTHONPATH")
        env["PYTHONPATH"] = root if not prev else root + os.pathsep + prev
    # ★ 不继承父控制台: CREATE_NO_WINDOW + stdin=DEVNULL + STARTF_USESTDHANDLES。
    #   宿主自身再起命令时也走同一 isolation_kwargs, 从源头消除 conhost 卡死诱因(阶段二-①)。
    try:
        from app.utils.proc_io import isolation_kwargs
        spawn_kwargs = isolation_kwargs()
    except Exception:
        spawn_kwargs = {}
    creationflags = spawn_kwargs.pop("creationflags", 0) or (
        subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    stdin = spawn_kwargs.pop("stdin", subprocess.DEVNULL)
    startupinfo = spawn_kwargs.pop("startupinfo", None)
    _host_proc = subprocess.Popen(
        argv, stdin=stdin, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, creationflags=creationflags,
        startupinfo=startupinfo, close_fds=True, env=env, cwd=root)
    # 等管道可用(只探测可连, 不发业务帧)
    deadline = time.monotonic() + _START_WAIT
    while time.monotonic() < deadline:
        if _host_proc.poll() is not None:
            rc = _host_proc.returncode
            _kill_host()
            raise HostError(f"宿主启动即退出 rc={rc}")
        try:
            _client_with_deadline(min(deadline, time.monotonic() + 0.5)).close()
            return
        except HostError:
            _kill_host()
            raise
        except Exception:
            time.sleep(0.05)
    _kill_host()
    raise HostError("宿主启动超时")


def _rebuild(respect_backoff: bool = True) -> bool:
    """重建宿主(调用方不持锁)。返回是否最终有活宿主。"""
    if not _can_attempt_spawn(ignore_backoff=not respect_backoff):
        return False
    with _host_lock:
        if _host_proc is not None and _host_proc.poll() is None:
            return True
        try:
            _spawn_host()
            _note_success()
            return True
        except Exception as e:
            _note_failure(f"{type(e).__name__}: {e}")
            return False


def _ping_host() -> bool:
    """发一帧 ping 等 pong(带连接与接收双截止); 任一超时/异常判 False。"""
    try:
        conn = _client_with_deadline(time.monotonic() + _CONNECT_TIMEOUT)
    except Exception:
        return False
    try:
        conn.send({"cmd": "ping"})
        deadline = time.monotonic() + _PING_TIMEOUT
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            if conn.poll(min(_CHUNK_WAIT, remaining)):
                msg = conn.recv()
                return isinstance(msg, dict) and msg.get("type") == "pong"
    except Exception:
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _guardian_tick() -> None:
    """一次巡检: 宿主不在→按退避重建; 在但 ping 不通→判僵死, 杀旧立即重建。"""
    host_at_start = _host_proc
    if host_at_start is None or host_at_start.poll() is not None:
        _rebuild(respect_backoff=True)
        return
    if _ping_host():
        _note_success()
        return
    _log_event("ping-fail", "宿主 ping 超时(疑似僵死), 杀旧重建")
    with _host_lock:
        if _host_proc is host_at_start:
            _kill_host()
    _rebuild(respect_backoff=False)


def _guardian_loop() -> None:
    """后台监护人 daemon: 每 5s 巡检, 或在请求路径唤醒时立即巡检。"""
    while True:
        try:
            _wake_event.wait(_PING_INTERVAL)
            _wake_event.clear()
            if not _enabled():
                continue
            _guardian_tick()
        except Exception as e:
            _log_event("guardian-error", f"监护人异常: {type(e).__name__}: {e}")
            time.sleep(1.0)


def _ensure_guardian() -> None:
    """启动监护线程(幂等)。"""
    global _guardian_thread
    with _guardian_lock:
        if _guardian_thread is not None and _guardian_thread.is_alive():
            return
        _guardian_thread = threading.Thread(
            target=_guardian_loop, name="proc-host-guardian", daemon=True)
        _guardian_thread.start()


def ensure_host() -> None:
    """启动期调用: 拉起宿主(最多重试 3 次)并启动监护人; 请求路径不再创建进程。

    失败按 0.5 / 1 / 2s 退避重试; 仍失败则记录熔断状态并抛 HostError, 由已启动的监护人
    在后台继续按退避恢复(调用方仅告警, 不阻断启动)。
    """
    if not _enabled():
        return
    _ensure_guardian()
    last: Optional[Exception] = None
    for attempt in range(len(_START_RETRY_DELAYS) + 1):
        with _host_lock:
            if _host_proc is not None and _host_proc.poll() is None:
                _note_success()
                return
            try:
                _spawn_host()
                _note_success()
                return
            except Exception as e:
                last = e
                _note_failure(f"{type(e).__name__}: {e}")
        if attempt < len(_START_RETRY_DELAYS):
            time.sleep(_START_RETRY_DELAYS[attempt])
    raise HostError(
        f"启动期宿主拉起失败(已重试 {len(_START_RETRY_DELAYS)} 次, 监护人后台继续): {last}")


def _recovery_wait_budget() -> float:
    """请求路径等待监护人重建的预算: 熔断打开期=0(快速失败); 退避期=剩余退避;
    正常=连接超时+启动就绪上限。"""
    now = time.monotonic()
    if _breaker_open and now < _breaker_until:
        return 0.0
    if not _breaker_open and now < _next_attempt_ts:
        return min(_next_attempt_ts - now, _CONNECT_TIMEOUT + _START_WAIT)
    return _CONNECT_TIMEOUT + _START_WAIT


def _connect():
    """连接宿主。请求路径零创建: 只连接; 不可用则唤醒监护人并在预算内等其重建。"""
    try:
        return _client_with_deadline(time.monotonic() + _CONNECT_TIMEOUT)
    except Exception as first:
        last: Exception = first
    _wake_event.set()
    deadline = time.monotonic() + _recovery_wait_budget()
    while time.monotonic() < deadline:
        time.sleep(0.1)
        try:
            return _client_with_deadline(min(deadline, time.monotonic() + _CONNECT_TIMEOUT))
        except Exception as e:
            last = e
    raise HostError(
        f"宿主不可用(请求路径不创建, 待监护人重建): {type(last).__name__}: {last}") from last


def run(argv, cwd=None, env=None, timeout=None):
    """执行一条命令, 返回五元组 (stdout_b, stderr_b, timed_out, truncated, rc)。

    rc = 子进程真实退出码(宿主回传; 取不到才为 -1)。比 drain_until_exit 多带一个 rc,
    是因为 drain_until_exit 从 proc 对象上取 returncode, 而宿主路径下调用方拿不到 proc。
    调用方改造时: returncode = rc, 其余四项语义与 drain_until_exit 完全一致。
    输出总量超 OMNI_PROC_HOST_MAX_OUTPUT 时丢弃后续 chunk、继续 drain 到 done(不让宿主反压),
    置 truncated=True 并追加 TRUNCATED_NOTE(与 proc_io.drain_until_exit 语义一致)。
    宿主异常时抛 HostError(继承 RuntimeError), 调用方按 error 结构返回, 不静默。
    """
    if not _enabled():
        raise Disabled("OMNI_PROC_HOST=0")
    _ensure_guardian()          # 兜底: 未经启动期 ensure_host 也能由监护人自愈(不在此创建进程)
    conn = _connect()
    out, err = [], []
    timed_out = truncated = False
    rc = -1
    total = 0
    cap = _max_output()
    deadline = time.monotonic() + (timeout if timeout else 600) + _RECV_SLACK
    try:
        conn.send({"proto": PROTO, "argv": list(argv), "cwd": cwd,
                   "env": env, "timeout": timeout})
        while True:
            # ★ 接收必须有截止时间: recv() 本身无超时参数, 宿主卡死时会永远等下去,
            #   于是"命令超时"退化成"工具调用永不返回"(比卡死更糟, 上层无从判定)。
            if not conn.poll(min(_CHUNK_WAIT, max(0.0, deadline - time.monotonic()))):
                if time.monotonic() >= deadline:
                    _kill_host()
                    raise HostError(f"宿主接收超时(>{timeout}s), 已杀宿主等待重建")
                continue
            msg = conn.recv()
            t = msg["type"]
            if t == "out" or t == "err":
                data = msg["data"]
                room = cap - total
                if room > 0:
                    chunk = data if len(data) <= room else data[:room]
                    (out if t == "out" else err).append(chunk)
                    total += len(chunk)
                if len(data) > room:
                    truncated = True
            elif t == "error":
                raise HostError(msg["message"])
            elif t == "done":
                rc = msg["rc"]
                timed_out = msg["timed_out"]
                truncated = truncated or bool(msg.get("truncated"))
                break
    except (EOFError, BrokenPipeError, OSError) as e:
        # 宿主中途死亡: 视为该次执行失败, 上层按 error 处理, 下次调用自愈
        _kill_host()
        raise HostError(f"宿主通信中断: {type(e).__name__}: {e}") from e
    finally:
        try:
            conn.close()
        except Exception:
            pass
    if truncated:
        from app.utils.proc_io import TRUNCATED_NOTE
        err.append(TRUNCATED_NOTE)
    return b"".join(out), b"".join(err), timed_out, truncated, rc
