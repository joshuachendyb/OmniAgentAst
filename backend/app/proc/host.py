# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-26 - 小欧 - 新建: 通用进程宿主(一命令一连接, Job Object 杀树; 接口只有 argv/cwd/env/timeout, 无业务语义)
# 2026-11-26 - 小欧 - 修正: 补单连接发送锁(并发 send 抛 ValueError)/每实例管道名与随机 authkey/协议版本握手/
#                     槽位排队而非立即拒绝/Job 收编失败 fail-closed/回传真实 returncode/自身装 spawn_gate/日志落文件
# 2026-11-26 - 小欧 - 通用接入: 超时上限收口到 app.proc_host.DEFAULT_TIMEOUT(与客户端同源);
#                     Popen 失败回传 kind(not_found), 供主进程还原 FileNotFoundError 语义。
# 2026-11-26 - 小欧 - 目录归位: 由 app/proc_host 迁入 app/proc 进程域包, 仅改导入路径, 逻辑零变化。
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

【命名】管道名与 authkey 由主进程每实例生成, 经环境变量传入; 不写死常量
  (写死会让开发态/打包态互抢同一管道, 且固定 authkey 等于对本机任意进程开放命令执行)。
"""
import os
import subprocess
import threading
import time
from multiprocessing.connection import Listener

from app.proc.constants import DEFAULT_TIMEOUT, PROTO  # 协议版本与超时上限唯一真源(域常量)

PIPE_NAME = os.environ["OMNI_PROC_HOST_PIPE"]                 # 形如 \\.\pipe\omni-proc-host-<uuid4hex>
AUTHKEY = bytes.fromhex(os.environ["OMNI_PROC_HOST_KEY"])     # 32 字节随机数
CONCURRENCY = int(os.environ.get("OMNI_PROC_HOST_CONCURRENCY", "12"))
_IDLE_JOIN = 3.0        # pump 线程收尾等待(秒): 与 proc_io.IDLE_AFTER_EXIT(2.5) 同量级, 超时即判 truncated
_LOG_PATH = os.environ.get("OMNI_PROC_HOST_LOG") or os.path.join("logs", "proc_host.log")
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
    from app.proc.win_job_object import (
        assign_to_job,
        close_job,
        create_kill_on_close_job,
        terminate_job,
    )
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
        argv = req.get("argv")
        if not argv or not isinstance(argv, (list, tuple)):
            _send(conn, {"type": "error", "message": "argv 必须是 list/tuple"}, send_lock)
            return
        timeout = req.get("timeout")
        # ★ 排队等待槽位(不是立即拒绝): 与现网 _SHELL_PROC_SEM.acquire(timeout=_remaining) 同语义,
        #   立即拒绝会让"并发 20 条命令"从'排队后全部成功'退化为'一半直接报错'。
        if not slots.acquire(timeout=timeout if timeout else DEFAULT_TIMEOUT):
            _send(conn, {"type": "error", "message": "宿主并发已达上限(排队超时)"}, send_lock)
            return
        try:
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
                proc.wait(timeout=timeout if timeout else DEFAULT_TIMEOUT)
            except subprocess.TimeoutExpired:
                timed_out = True
                terminate_job(job)            # TerminateJobObject, 内核级杀整棵树
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    pass
            for t in pumps:
                t.join(timeout=_IDLE_JOIN)

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
    parent_pid = int(os.environ.get("OMNI_PROC_HOST_PARENT_PID", "0") or 0)
    if parent_pid:
        threading.Thread(target=_watch_parent, args=(parent_pid,), daemon=True).start()
    try:
        _serve_forever()
    except Exception as e:
        _log(f"fatal: {type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    main()
