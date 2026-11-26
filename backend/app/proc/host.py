# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-26 - 小欧 - 新建: 通用进程宿主(一命令一连接, Job Object 杀树; 接口只有 argv/cwd/env/timeout, 无业务语义)
# 2026-11-26 - 小欧 - 修正: 补单连接发送锁(并发 send 抛 ValueError)/每实例管道名与随机 authkey/协议版本握手/
#                     槽位排队而非立即拒绝/Job 收编失败 fail-closed/回传真实 returncode/自身装 spawn_gate/日志落文件
# 2026-11-26 - 小欧 - 通用接入: 超时上限收口到 app.proc_host.DEFAULT_TIMEOUT(与客户端同源);
#                     Popen 失败回传 kind(not_found), 供主进程还原 FileNotFoundError 语义。
# 2026-11-26 - 小欧 - 目录归位: 由 app/proc_host 迁入 app/proc 进程域包, 仅改导入路径, 逻辑零变化。
# 2026-11-26 - 小欧 - 排队预算: 槽位等待耗时从命令 timeout 中扣除(对齐现网 _remaining), 防
#   "排队+完整 timeout"超过客户端截止而误杀宿主、连累全场在飞命令; 长排队告警留痕。
# 2026-11-27 - 小欧 - 阶段七/八: 新增后台任务通道 submit/query/terminate 与 _bg_watch 看护线程;
#   background 输出直写文件、超时/超限由宿主单方判定; fire_and_forget 不入 Job; 断连按 mode 分派不杀树。
"""proc_host — 通用进程宿主进程

【为什么独立进程】CreateProcessW 卡在控制台 IOCTL 时不释放 GIL, 同解释器内任何线程
(含看门狗、join 超时)都无法执行。唯一能把"卡住"限制在可抛弃范围的边界是进程边界。

【协议】AF_PIPE + multiprocessing.connection, 一命令一连接(无 id 多路复用):
  首帧 {"proto","argv","cwd","env","timeout"} → 流式 {"type":"out"|"err","data":b} → {"type":"done",...}
  连接断开 = 命令取消。单连接同一时刻只允许一个发送者(见 _send)。

【超时】每子进程挂 Job Object, 超时 TerminateJobObject 杀整棵树(实测 1.02s,
  对比 proc.kill() 5.06s —— 孙进程持管道会让根 kill 无效)。

【创建模式】宿主自身由主进程以 CREATE_NO_WINDOW 拉起; 禁用 DETACHED_PROCESS
  (实测该模式 pwsh/ps5 返回 rc=0 但 stdout 为空, 静默丢输出)。

【命名】管道名与 authkey 由主进程每实例生成, 经握手串(PROC_HANDSHAKE)传入; 不写死常量
  (写死会让开发态/打包态互抢同一管道, 且固定 authkey 等于对本机任意进程开放命令执行)。
"""
import base64
import json
import os
import subprocess
import threading
import time
import uuid
from multiprocessing.connection import Listener

from app.env_keys import PROC_HANDSHAKE
from app.proc.constants import DEFAULT_TIMEOUT, IDLE_JOIN, PROTO  # 协议/预算唯一真源(域常量)
from app.proc.win_job_object import (
    assign_to_job,
    close_job,
    create_kill_on_close_job,
    terminate_job,
)

# ── 后台任务通道(阶段七/八) ─────────────────────────────
# 跨连接共享: 每连接一份会让 submit 断连后任务信息丢失, query/terminate 走独立连接时查不到
_BG_TASKS: dict = {}
_BG_LOCK = threading.Lock()
_BG_MAX = 256
_BG_TASK_SEM = threading.BoundedSemaphore(_BG_MAX)
_BG_RETAIN = 120.0          # 终态记录保留窗: 主进程 query 须在此期间读到终态
_BG_POLL = 2.0              # 看护线程轮询粒度(与现网 _wait_process 的 2s 切片同口径)
_FIRE_FORGET_REAP = 30.0    # fire_and_forget 回收上限: 超时只解除登记, 不杀进程

# 启动握手串(单变量, base64 JSON): 由 client._spawn_host 注入。
_HS = json.loads(base64.b64decode(os.environ[PROC_HANDSHAKE]).decode("utf-8"))
PIPE_NAME = _HS["pipe"]                                       # 形如 \\.\pipe\omni-proc-host-<uuid4hex>
AUTHKEY = bytes.fromhex(_HS["key"])                           # 32 字节随机数
CONCURRENCY = int(_HS.get("concurrency", 12))
_LOG_PATH = _HS.get("log") or os.path.join("logs", "proc_host.log")
try:
    os.makedirs(os.path.dirname(os.path.abspath(_LOG_PATH)), exist_ok=True)
except OSError:
    pass


def _serve_forever() -> None:
    """宿主主循环: 常驻 accept, 每连接一线程。

    单个坏连接(握手失败 AuthenticationError / 对端立刻关闭 EOFError)只丢该连接, 不得让宿主退出:
    AuthenticationError 继承 ProcessError(Exception) 而非 OSError(multiprocessing/context.py:23),
    若只捕 OSError/EOFError 会把一次失败握手升级成"宿主整体死亡"。
    """
    listener = Listener(PIPE_NAME, authkey=AUTHKEY)
    _log(f"listening on {PIPE_NAME}, concurrency={CONCURRENCY}")
    _slots = threading.BoundedSemaphore(CONCURRENCY)
    _bad = 0
    while True:
        try:
            conn = listener.accept()
        except Exception as e:                      # 含 ProcessError/AuthenticationError/OSError
            _bad += 1
            _log(f"accept failed({_bad}): {type(e).__name__}: {e}")
            if _bad >= 50:                          # 连续 50 次仍失败: 管道/句柄已不可用, 退出等主进程重建
                _log("accept 连续失败, 退出由主进程重建")
                return
            time.sleep(0.1)
            continue
        _bad = 0
        threading.Thread(target=_handle, args=(conn, _slots), daemon=True).start()


def _handle(conn, slots) -> None:
    """一连接一命令。"""
    # 2026-11-26 - 小欧 - 独立 Job: 禁用 SILENT_BREAKAWAY_OK, 否则孙进程逃离 Job, kill_tree 失效
    #   (实测: SandboxJob 配置下 cmd/c ping 的 ping 残留; 仅 KILL_ON_JOB_CLOSE 时被杀净)
    send_lock = threading.Lock()      # ★ 单连接同一时刻只允许一个发送者, 见 _send
    job = None
    proc = None
    try:
        req = conn.recv()
        # 健康探测帧: 直接回 pong, 不占并发槽位(监护人以 ping/pong 判僵死)
        if isinstance(req, dict) and req.get("cmd") == "ping":
            _send(conn, {"type": "pong"}, send_lock)
            return
        if not isinstance(req, dict) or req.get("proto") != PROTO:
            proto_repr = req.get("proto") if isinstance(req, dict) else req
            _send(conn, {"type": "error", "message": f"协议版本不匹配: {proto_repr!r}"}, send_lock)
            return
        # 阶段七/八 后台通道: 必须在 argv 校验之前分派(query/terminate 不带 argv)
        if isinstance(req, dict) and req.get("cmd") == "submit":
            return _handle_submit(conn, req, send_lock)
        if isinstance(req, dict) and req.get("cmd") == "query":
            return _handle_query(conn, req, send_lock)
        if isinstance(req, dict) and req.get("cmd") == "terminate":
            return _handle_terminate(conn, req, send_lock)
        argv = req.get("argv")
        if not argv or not isinstance(argv, (list, tuple)):
            _send(conn, {"type": "error", "message": "argv 必须是 list/tuple"}, send_lock)
            return
        timeout = req.get("timeout")
        # 2026-11-26 - 小欧 - 排队耗时计入命令预算: 现网 shell 在 acquire 后重算 _remaining,
        #   宿主若用原始 timeout 做 wait, "排队+完整 timeout"会超过客户端 timeout+5 截止,
        #   触发客户端误杀宿主并连累其他会话的在飞命令(真实 case 已复现)。
        t_req = time.monotonic()
        # ★ 排队等待槽位(不是立即拒绝): 与现网 _SHELL_PROC_SEM.acquire(timeout=_remaining) 同语义,
        #   立即拒绝会让"并发 20 条命令"从'排队后全部成功'退化为'一半直接报错'。
        if not slots.acquire(timeout=timeout if timeout else DEFAULT_TIMEOUT):
            _send(conn, {"type": "error", "message": "宿主并发已达上限(排队超时)"}, send_lock)
            return
        try:
            waited = time.monotonic() - t_req
            if waited >= 1.0:                    # 长排队告警: 多会话争抢槽位必须可观测
                _log(f"槽位排队等待 {waited:.1f}s(timeout={timeout}s)")
            budget = (timeout - waited) if timeout else DEFAULT_TIMEOUT
            if budget <= 0:
                _send(conn, {"type": "error", "message":
                             f"排队耗尽命令预算(等待 {waited:.1f}s >= timeout {timeout}s)"}, send_lock)
                return
            t0 = time.monotonic()
            from app.proc.proc_io import isolation_kwargs
            try:
                proc = subprocess.Popen(
                    list(argv), cwd=req.get("cwd"), env=req.get("env"),
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    **isolation_kwargs())
            except (OSError, ValueError) as e:
                # 2026-11-26 - 小欧 - 错误种类回传: 调用方据此还原 FileNotFoundError,
                #   否则"程序不存在"退化成"宿主故障", 现有 catch FileNotFoundError 的分支失效
                kind = "not_found" if isinstance(e, FileNotFoundError) else "spawn_failed"
                _send(conn, {"type": "error", "message": f"{type(e).__name__}: {e}",
                             "kind": kind}, send_lock)
                return
            # ★ Job 收编 fail-closed: 没有 Job 就没有"杀整棵树"的保证, 超时承诺直接失效。
            #   故收编失败 → 杀掉刚起的进程并回 error, 绝不静默降级为 proc.kill()(只杀根, 孙进程残留)。
            #   竞态说明: Python 3.13 的 subprocess 无 CREATE_SUSPENDED 常量、Popen 也不暴露线程句柄,
            #   无法"挂起创建→收编→ResumeThread"; 因此只能"创建后立刻收编"。窗口在微秒级, 而子进程
            #   自身启动需数十毫秒, 实际不产生逃逸; 万一逃逸, close_job 的 KILL_ON_JOB_CLOSE 仍是兜底。
            try:
                job = create_kill_on_close_job()
                assign_to_job(job, proc)
            except OSError as e:
                _log(f"job assign failed pid={proc.pid}: {e} → fail-closed")
                if job is not None:
                    close_job(job)
                    job = None
                try:
                    proc.kill()
                except OSError:
                    pass
                _send(conn, {"type": "error", "message": f"Job 收编失败, 已终止命令: {e}"}, send_lock)
                return

            pumps = [
                threading.Thread(target=_pump, args=(proc.stdout, "out", conn, send_lock), daemon=True),
                threading.Thread(target=_pump, args=(proc.stderr, "err", conn, send_lock), daemon=True),
            ]
            for t in pumps:
                t.start()

            timed_out = False
            try:
                # 2026-11-26 - 小欧 - None 不再等于无限: 与客户端接收截止同源上限, 超时走正常
                #   TimeoutExpired 链路(terminate_job 杀树), 不靠客户端杀宿主来收尾。
                proc.wait(timeout=budget)   # 用扣掉排队后的剩余预算, 总耗时 ≤ timeout
            except subprocess.TimeoutExpired:
                timed_out = True
                terminate_job(job)            # TerminateJobObject, 内核级杀整棵树
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    pass
            for t in pumps:
                t.join(timeout=IDLE_JOIN)

            truncated = any(t.is_alive() for t in pumps)
            if truncated:
                # 根已退出但管道未 EOF(孙进程/后台作业仍持写端): 关 Job 杀净, 语义与
                # proc_io.drain_until_exit 的 truncated=True 一致(调用方补 TRUNCATED_NOTE)
                terminate_job(job)
            _send(conn, {
                "type": "done",
                # ★ 回真实 returncode: 现网超时分支是 kill 后取 proc.returncode, 恒为已终止码而非 -1;
                #   写死 -1 会让调用方拿到的 returncode 与改造前不一致。
                "rc": proc.returncode if proc.returncode is not None else -1,
                "timed_out": timed_out, "truncated": truncated,
                "pid": proc.pid, "elapsed": round(time.monotonic() - t0, 3),
            }, send_lock)
        finally:
            slots.release()
    except Exception as e:
        # 客户端断开(主进程被杀/取消): 杀掉该命令树, 不留孤儿。
        # 注意不能只捕 (EOFError, BrokenPipeError, OSError): 握手失败是 AuthenticationError(ProcessError),
        # 并发发送是 ValueError, 二者都不继承 OSError, 漏捕会让整个线程静默崩掉且槽位不释放。
        _log(f"conn aborted: {type(e).__name__}: {e}")
        if job is not None:
            try:
                terminate_job(job)
            except Exception:
                pass
        elif proc is not None:
            try:
                proc.kill()
            except OSError:
                pass
    finally:
        if job is not None:
            try:
                close_job(job)                # KILL_ON_JOB_CLOSE: 句柄关闭即杀全树, 幂等安全
            except Exception:
                pass
        try:
            conn.close()
        except Exception:
            pass


def _handle_submit(conn, req, send_lock) -> None:
    """阶段七/八: submit 帧。提交即脱离, 回 submitted 后关闭连接, 进程由注册表托管。"""
    if not _BG_TASK_SEM.acquire(blocking=False):
        _send(conn, {"type": "error", "message": "后台任务并发已达上限"}, send_lock)
        return
    argv = req.get("argv")
    if not argv or not isinstance(argv, (list, tuple)):
        _BG_TASK_SEM.release()
        _send(conn, {"type": "error", "message": "argv 必须是 list/tuple"}, send_lock)
        return
    mode = req.get("mode", "background")
    output_file = req.get("output_file")
    timeout = req.get("timeout")   # None 透传, 不套 DEFAULT_TIMEOUT
    max_bytes = int(req.get("max_output_bytes") or 0)
    task_id = uuid.uuid4().hex[:12]
    job = None
    try:
        from app.proc.proc_io import isolation_kwargs
        if mode == "fire_and_forget":
            # 不建 pump、不建 Job: 输出丢弃; 入 Job 会让收尾时的 KILL_ON_JOB_CLOSE 关掉 explorer 刚打开的窗口
            proc = subprocess.Popen(
                list(argv), cwd=req.get("cwd"), env=req.get("env"),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                **isolation_kwargs())
        else:
            # background: 输出直写文件(与现网同构), 不攒内存
            if output_file is None:
                _BG_TASK_SEM.release()
                _send(conn, {"type": "error", "message": "background mode 需 output_file"}, send_lock)
                return
            fout = open(output_file, "ab")
            try:
                proc = subprocess.Popen(
                    list(argv), cwd=req.get("cwd"), env=req.get("env"),
                    stdout=fout, stderr=subprocess.STDOUT,
                    **isolation_kwargs())
            finally:
                fout.close()
    except (OSError, ValueError) as e:
        _BG_TASK_SEM.release()
        kind = "not_found" if isinstance(e, FileNotFoundError) else "spawn_failed"
        _send(conn, {"type": "error", "message": f"{type(e).__name__}: {e}", "kind": kind}, send_lock)
        return
    if mode != "fire_and_forget":
        # Job 收编 fail-closed: 没有 Job 就没有"杀整棵树"的保证, 超时承诺直接失效
        try:
            job = create_kill_on_close_job()
            assign_to_job(job, proc)
        except OSError as e:
            try:
                proc.kill()
            except OSError:
                pass
            if job is not None:
                try:
                    close_job(job)
                except Exception:
                    pass
            _BG_TASK_SEM.release()
            _send(conn, {"type": "error", "message": f"Job 收编失败: {e}"}, send_lock)
            return
    with _BG_LOCK:
        _BG_TASKS[task_id] = {
            "proc": proc, "job": job, "output_file": output_file,
            "mode": mode, "start_ts": time.monotonic(),
            "timeout": timeout, "max_output_bytes": max_bytes,
            "outcome": "running", "rc": None, "t_end": None,
            "sem_released": False,
        }
    # 提交即脱离: 先交给看护线程, 再回 submitted; 名额归还在 _bg_watch 里做
    threading.Thread(target=_bg_watch, args=(task_id,), daemon=True).start()
    _send(conn, {"type": "submitted", "task_id": task_id, "pid": proc.pid}, send_lock)
    try:
        conn.close()
    except Exception:
        pass


def _handle_query(conn, req, send_lock) -> None:
    """查询后台任务状态。单一真源是 outcome(看护线程/terminate 写定), 不拿 proc.poll() 另算一份。"""
    task_id = req.get("task_id")
    info = _BG_TASKS.get(task_id)
    if info is None:
        _send(conn, {"type": "error", "message": f"未知任务 {task_id}"}, send_lock)
        return
    outcome = info.get("outcome") or "running"
    running = outcome == "running"
    rc = None if running else info.get("rc")
    if not running and rc is None:
        rc = info["proc"].returncode
    _send(conn, {
        "type": "status", "task_id": task_id,
        "running": running, "rc": rc,
        "outcome": outcome,
        "output_file": info.get("output_file"),
        "mode": info.get("mode"),
    }, send_lock)


def _handle_terminate(conn, req, send_lock) -> None:
    """按 task_id 杀树。终态先写定, 看护线程只做收尾(不覆盖 terminated)。"""
    task_id = req.get("task_id")
    info = _BG_TASKS.get(task_id)
    if info is None:
        _send(conn, {"type": "error", "message": f"未知任务 {task_id}"}, send_lock)
        return
    with _BG_LOCK:
        if info.get("outcome") == "running":
            info["outcome"] = "terminated"
            info["t_end"] = time.monotonic()
    job = info.get("job")
    if job is not None:
        try:
            terminate_job(job)   # TerminateJobObject, 内核级杀整棵树
        except Exception:
            pass
    try:
        info["proc"].kill()      # fire_and_forget 无 Job, 只能杀根
    except OSError:
        pass
    _send(conn, {"type": "terminated", "task_id": task_id}, send_lock)


def _bg_watch(task_id: str) -> None:
    """后台任务看护线程: 执行 timeout/oversize、写终态、关 Job、归还名额、保留后弹出。

    判据只此一份: 主进程只读 query 的 outcome, 不再自行判超时/超限(否则重复杀进程、rc 退化成 -1)。
    """
    info = _BG_TASKS.get(task_id)
    if info is None:
        return
    proc = info["proc"]
    timeout = info.get("timeout")
    max_bytes = info.get("max_output_bytes") or 0
    deadline = (time.monotonic() + timeout) if timeout else None
    outcome, rc = "exited", None
    if info.get("mode") == "fire_and_forget":
        # 不入 Job、不杀树: 回收上限到了只解除登记, 进程交 OS 收尾
        try:
            proc.wait(timeout=_FIRE_FORGET_REAP)
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            rc = None
    else:
        while True:
            try:
                rc = proc.wait(timeout=_BG_POLL)
                break
            except subprocess.TimeoutExpired:
                pass
            if max_bytes > 0:
                try:
                    if os.path.getsize(info["output_file"]) > max_bytes:
                        outcome, rc = "oversize", -1
                        break
                except OSError:
                    pass
            if deadline is not None and time.monotonic() >= deadline:
                outcome, rc = "timeout", -1
                break
        if outcome != "exited":
            try:
                terminate_job(info["job"])   # 杀整棵树, 不留孙进程
            except Exception:
                pass
        # KILL_ON_JOB_CLOSE: 句柄关闭即杀净仍持写端的孙进程(根已退出/hung 都覆盖)
        if info.get("job") is not None:
            try:
                close_job(info["job"])
            except Exception:
                pass
            info["job"] = None
    with _BG_LOCK:
        if info.get("outcome") == "running":      # terminate 已写定则不覆盖
            info["outcome"] = outcome
            info["rc"] = rc
        info["t_end"] = info.get("t_end") or time.monotonic()
        sem_released = info.get("sem_released")
        info["sem_released"] = True
    if not sem_released:
        _BG_TASK_SEM.release()                    # ★ 名额守恒: 成功路径也必须归还
    time.sleep(_BG_RETAIN)                        # 终态留给主进程 query 读取
    with _BG_LOCK:
        _BG_TASKS.pop(task_id, None)


def _pump(stream, kind, conn, send_lock) -> None:
    """流式读一路输出并回传; 连接断开即停止(调用方已死, 无需继续攒数据)。"""
    while True:
        try:
            chunk = stream.read(8192)
        except (ValueError, OSError):
            return
        if not chunk:
            return
        if not _send(conn, {"type": kind, "data": chunk}, send_lock):
            return


def _send(conn, obj, send_lock) -> bool:
    """串行发送: PipeConnection._send_bytes 用 _send_ov 标记在途, 并发调用直接抛 ValueError。

    两条 pump 线程 + 主线程的 done 共三个发送者, 必须由同一把锁串行化。
    """
    try:
        with send_lock:
            conn.send(obj)
        return True
    except Exception:      # 对端已关: BrokenPipeError/OSError/EOFError; 并发误用: ValueError
        return False


def _log(msg: str) -> None:
    """宿主日志: 必须落文件。主进程以 stdout/stderr=DEVNULL 拉起宿主, print 等于丢弃。"""
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} [proc_host] {msg}"
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _watch_parent(parent_pid: int) -> None:
    """生命周期看门狗: 主进程消失即自杀, 不留孤儿。

    为什么不用"空闲 10 分钟自退": 宿主一退出, 下一条命令就得在主进程请求路径上重新 Popen 宿主,
    等于把 CreateProcessW 又搬回主进程。所以只在"父进程真的没了"时退出。
    为什么不用 Job 继承兜底: run_server.py 只在 is_frozen 时给主进程挂 KILL_ON_JOB_CLOSE,
    源码态(dev/E2E)没有, 靠 Job 继承在 dev 下不成立。
    """
    import ctypes
    k32 = ctypes.windll.kernel32
    SYNCHRONIZE, WAIT_OBJECT_0 = 0x00100000, 0
    while True:
        time.sleep(5.0)
        h = k32.OpenProcess(SYNCHRONIZE, False, parent_pid)
        if not h:
            _log(f"parent {parent_pid} gone (OpenProcess failed), exit")
            os._exit(0)
        try:
            if k32.WaitForSingleObject(h, 0) == WAIT_OBJECT_0:
                _log(f"parent {parent_pid} exited, exit")
                os._exit(0)
        finally:
            k32.CloseHandle(h)


def main() -> None:
    """宿主入口。frozen 时由 run_server.main() 按 --proc-host 直接调用。"""
    # ★ spawn_gate 只在主服务 app/main.py 装过一次, 宿主是另一个进程, 不装就没有任何闸门保护
    from app.proc.spawn_gate import install_spawn_gate
    install_spawn_gate()
    parent_pid = int(_HS.get("parent_pid", 0) or 0)
    if parent_pid:
        threading.Thread(target=_watch_parent, args=(parent_pid,), daemon=True).start()
    try:
        _serve_forever()
    except Exception as e:
        _log(f"fatal: {type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    main()
