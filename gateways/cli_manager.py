# -*- coding: utf-8 -*-
r"""cli_manager.py — 下游进程生命周期框架（方言细节全部经驱动挂钩）。

编写人: 小欧    创建时间: 2026-11-05 09:10:00
通用层零方言: 候选、报文端点、密码形状、就绪判据均由 vendor\<provider>\driver 给出。

编辑历史:
  2026-11-05 R5 冷却封顶 1 h（下游 retryAfterMs 实测虚高 14 h）; 启动清场; 端口漂移留痕 -- 小欧
  2026-11-05 冷却判定从 acquire 迁出为 ensure_not_cooling; netstat 改按字节收防 GBK 静默失败 -- 小欧
  2026-11-05 命名对齐: GatewayError 迁 errors.py, record_failure→on_downstream_failure, init_driver→install_driver -- 小欧
  2026-11-05 R4 改按 fail_threshold 累计后才重启, 连续重启失败才升级退避 -- 小欧
  2026-11-05 启动失败路径补关日志句柄; 清扫线程加异常护栏; 准入缓存存绝对路径 -- 小欧
  2026-11-05 注释规范化: 压缩到两行内并统一署名日期 -- 小欧
  2026-11-05 运行期文案与行内注释去节号: preflight 启动拒绝原因、探针/候选注释 -- 小欧
"""
from __future__ import annotations

import ctypes
import os
import shutil
import socket
import subprocess
import sys
import threading
import time

import httpx

from driver_api import get_driver
from errors import GatewayError, RESTARTABLE_TYPES

# 硬约束: deny * 必须在最前（下游按 findLast 生效, 后写覆盖先写）— 小欧 2026-11-05
SESSION_PERMISSIONS = [
    {"action": "*", "resource": "*", "effect": "deny"},
    {"action": "read", "resource": "Z:/nope/*", "effect": "allow"},
]

FROZEN = bool(getattr(sys, "frozen", False))    # 打包版硬约束总开关 — 小欧 2026-11-05
# 免费额度冷却按 1 h 记; 下游 retryAfterMs 实测虚高到 14 h, 只作上限判据。— 小欧 2026-11-05
COOLDOWN_S = 3600


def runtime_dir():
    """网关自身目录: 打包版 = exe 同级; 源码 = 本文件目录。— 小欧 2026-11-05"""
    if FROZEN:
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def machine_root():
    r"""机器级根目录（LOCALAPPDATA\opencli-gateway; 多安装共享与沙箱公共落点）。— 小欧 2026-11-05"""
    return os.path.join(os.environ.get("LOCALAPPDATA")
                        or os.path.expanduser("~\\AppData\\Local"), "opencli-gateway")


SANDBOX_CWD = os.path.join(machine_root(), "sandbox")   # 空目录铁律: 禁放任何文件 — 小欧 2026-11-05

DRV = None          # 驱动单例; install_driver() 填充 — 小欧 2026-11-05


def install_driver(config):
    """装载驱动并注入通用侧运行时键; 驱动只读这些键, 不 import 通用层。— 小欧 2026-11-05"""
    global DRV
    config["runtime_dir"] = runtime_dir()
    config["frozen"] = FROZEN
    config["machine_root"] = machine_root()
    DRV = get_driver(config)
    return DRV


def _is_loopback(host):
    return host in ("127.0.0.1", "localhost", "::1")


def preflight(config):
    """启动前安全闸门: 回环 + token + deny * + 驱动可装载 + 配置项兜底。
    返回问题清单, 非空即拒绝启动。— 小欧 2026-11-05"""
    problems = []
    driver_error = None
    try:
        install_driver(config)
    except RuntimeError as exc:
        driver_error = str(exc)
    if driver_error is not None:
        problems.append(driver_error)
    if not _is_loopback(config.get("host", "127.0.0.1")):
        problems.append("拒绝启动: 监听地址必须为 127.0.0.1（强制回环）")
    if not str(config.get("token") or "").strip():
        problems.append("拒绝启动: token 为空（须与宿主 api_key 一致）")
    if not SESSION_PERMISSIONS or SESSION_PERMISSIONS[0].get("action") != "*" \
            or SESSION_PERMISSIONS[0].get("effect") != "deny":
        problems.append("拒绝启动: 权限规则缺少首条 deny *（硬约束）")
    # 清扫线程与退避按 cfg[...] 直取: 缺键会在后台线程抛 KeyError 致清扫与退避静默停摆 — 小欧 2026-11-05
    for key in ("pool_size", "queue_max", "port_base", "port_span", "task_idle_gap_s",
                "idle_seconds", "max_age_seconds", "max_requests", "fail_threshold",
                "restart_min_interval_s", "backoff_cap_s", "startup_timeout",
                "log_keep_days"):
        try:
            ok = int(config.get(key, 0)) >= 1
        except (TypeError, ValueError):
            ok = False
        if not ok:
            problems.append("拒绝启动: 配置项 %s 缺失或不是正整数" % key)
    return problems


# —— 定位候选（驱动 5 级）+ 三关准入 ——

def _free_port_excluding(banned):
    """临时端口避开池段 [port_base, port_base+port_span-1]（探针端口纪律）。— 小欧 2026-11-05"""
    while True:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        if port not in banned:
            return port


def _pick_consecutive_ports(config):
    """port_base 起找 pool_size 个连续空闲端口; 整池顺延, 出 span 即失败。
    连续是为了端口清单可读; 不无限顺延, 免得撞上用户自己的服务。— 小欧 2026-11-05"""
    base, span = int(config["port_base"]), int(config["port_span"])
    size = int(config["pool_size"])
    busy = set()
    for port in range(base, base + span):
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                busy.add(port)
    for start in range(base, base + span - size + 1):
        if not any(p in busy for p in range(start, start + size)):
            return list(range(start, start + size))
    raise GatewayError(502, "network",
                    "%d–%d 内找不到 %d 个连续空闲端口，请检查端口占用"
                    % (base, base + span - 1, size))


def _listener_pids(ports):
    """本机 TCP 监听 → {port: pid}; 只看传入端口（netstat 解析, 不引第三方依赖）— 小欧 2026-11-05"""
    found = {}
    try:
        # netstat 在本机输出 GBK; text=True 解码失败会静默给 None 而不是抛错 — 按字节收
        raw = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True,
                             timeout=10, creationflags=0x08000000).stdout
    except Exception:
        return found
    for line in raw.decode("utf-8", "replace").splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[-2].upper() != "LISTENING":
            continue
        port = int(parts[1].rsplit(":", 1)[-1])
        if port in ports:
            found[port] = int(parts[-1])
    return found


def _image_name(pid):
    """PID → 可执行文件全路径; 取不到给空串（ctypes, 不引 psutil/wmic）— 小欧 2026-11-05"""
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(0x1000, False, int(pid))    # QUERY_LIMITED_INFORMATION
    if not handle:
        return ""
    try:
        buf, size = ctypes.create_unicode_buffer(1024), ctypes.c_uint(1024)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value
        return ""
    finally:
        kernel32.CloseHandle(handle)


def _reap_orphans(config):
    """启动清场: 网关被强杀会留下占池端口的下游 CLI, 不清则整池顺延且无告警。
    只杀镜像名匹配本驱动的进程。— 小欧 2026-11-05"""
    if _listener_pids([int(config["port"])]):
        return                         # 已有网关占用服务端口(重复启动): 不动它的下游, 交给绑定失败
    base, span = int(config["port_base"]), int(config["port_span"])
    names = set()
    for cand in DRV.cli_candidates(config):
        name = os.path.basename(str(cand.get("path") or "")).lower()
        if name:
            names.update((name, name + ".exe"))
    for port, pid in _listener_pids(range(base, base + span)).items():
        if os.path.basename(_image_name(pid)).lower() not in names:
            print("[reap] 池端口 %d 被非下游进程占用 pid=%d, 本次整池顺延"
                  % (port, pid), file=sys.stderr)      # 端口漂移必须留痕, 不静默
            continue                       # 非本网关下游 → 绝不误杀
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       capture_output=True, timeout=10, creationflags=0x08000000)
        print("[reap] 清掉上次遗留的下游进程 port=%d pid=%d" % (port, pid),
              file=sys.stderr)


def _in_range(version, compatible):
    """极简范围判据: '>=2.2.0 <2.3.0' 只解上下限段; `<=x` 为闭上限。— 小欧 2026-11-05"""
    lo, hi, hi_closed = None, None, False
    for token in str(compatible or "").split():
        if token.startswith(">="):
            lo = token[2:]
        elif token.startswith("<="):
            hi, hi_closed = token[2:], True
        elif token.startswith("<"):
            hi, hi_closed = token[1:], False
    parts = [int(x) for x in version.split(".")]
    if lo and parts < [int(x) for x in lo.split(".")]:
        return False
    if hi:
        edge = [int(x) for x in hi.split(".")]
        beyond = parts > edge if hi_closed else parts >= edge
        if beyond:
            return False
    return True


def _version_ok(path, compatible):
    """版本可读（正则来自驱动）且在范围。实测输出 `opencode v2.2.0`。— 小欧 2026-11-05"""
    try:
        out = subprocess.run([path, "--version"], capture_output=True,
                             text=True, timeout=15, creationflags=0x08000000)
    except Exception as exc:
        return "", "version-failed: %s" % exc
    match = DRV.version_re.match((out.stdout or "").strip())
    if not match:
        return "", "version-unreadable"
    version = match.group(1)
    if not _in_range(version, compatible):
        return version, "version-not-in-range"
    return version, ""


def _spawn(exe, port, env, cwd, log_file):
    """spawn 下游 serve; serve 子命令由驱动给出, 通用层只管弹道与管道。— 小欧 2026-11-05"""
    return subprocess.Popen(
        [exe] + DRV.spawn_args(exe, port),
        env=env, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        creationflags=0x08000000)                  # CREATE_NO_WINDOW


def _terminate(proc):
    """幂等停止: 重复调用不报错, 异常路径也要走到, 先 terminate 再强杀。— 小欧 2026-11-05"""
    if proc is None:
        return
    if proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=8)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def _env_for(tag):
    """装配环境变量: 通用层合 env, 隔离目录由驱动 env_overrides(tag) 给出并创建。
    用户全局配置在建会话前就进提示词, 权限补救无效, 必须出生前重定向。— 小欧 2026-11-05"""
    env = os.environ.copy()
    env.update(DRV.env_overrides(tag))
    os.makedirs(SANDBOX_CWD, exist_ok=True)        # 空目录, 禁止放任何文件 — 小欧 2026-11-05
    return env


def _read_password(proc, timeout, log_file):
    """stdout 逐行: 驱动 credential() 判密码与脱敏; 首个密码即用。
    读取线程必须持续排空 stdout, 否则管道写满会把下游卡死。— 小欧 2026-11-05"""
    holder = {"password": ""}

    def pump():
        for raw in iter(proc.stdout.readline, b""):
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            line, password = DRV.credential(line)   # 驱动判密 + 脱敏 — 小欧 2026-11-05
            if password and not holder["password"]:
                holder["password"] = password      # 捕获一次即够
            try:
                log_file.write((line + "\n").encode("utf-8"))
                log_file.flush()
            except Exception:
                pass

    thread = threading.Thread(target=pump, daemon=True)
    thread.start()
    thread.join(timeout)
    return holder["password"]


def _probe(exe, config):
    """能力探针: 起服务 → stdout 捕获密码 → 驱动 ready() → 立即终止。
    探针端口避开池段, 进程不复用为服务进程, 返回 (ok, reason)。— 小欧 2026-11-05"""
    banned = set(range(int(config["port_base"]),
                       int(config["port_base"]) + int(config["port_span"])))
    port = _free_port_excluding(banned)
    os.makedirs(str(config.get("machine_root")), exist_ok=True)   # probe.log 落点先建
    log_file = open(os.path.join(str(config.get("machine_root")), "probe.log"), "ab")
    proc = None
    try:
        proc = _spawn(exe, port, _env_for("probe"), SANDBOX_CWD, log_file)
        password = _read_password(proc, timeout=20, log_file=log_file)
        if not password:
            return False, "probe-failed: stdout 无密码输出（驱动 credential 未捕获）"
        auth = DRV.auth(password)
        for _ in range(60):                      # ≤ 20 s（实测就绪均值 0.98 s）
            if proc.poll() is not None:
                return False, "probe-failed: serve 启动即退出"
            if DRV.ready(port, auth):
                return True, ""
            time.sleep(0.3)
        return False, "probe-failed: 驱动就绪判据 20 s 未通过"
    finally:
        _terminate(proc)                         # 探针进程验证完立即释放 — 小欧 2026-11-05
        try:
            log_file.close()
        except Exception:
            pass


def resolve_admitted_cli(config):
    """三关准入闸口: 逐候选过版本可读/范围/探针, 通过即缓存绝对路径; 全失败抛 502 — 小欧 2026-11-05"""
    cached = config.get("_cli_ok")
    if cached and os.path.exists(cached):
        return cached
    config["candidates"] = []
    compatible = (config.get("cli") or {}).get("compatible", ">=2.2.0 <2.3.0")
    for cand in DRV.cli_candidates(config):        # 驱动 5 级候选 — 小欧 2026-11-05
        path = cand["path"]
        found = path if os.path.dirname(path) else (shutil.which(path) or "")
        if not found or not os.path.exists(found):
            config["candidates"].append(dict(cand, ok=False, reason="not-found"))
            continue
        path = os.path.abspath(found)              # 后续 spawn/缓存一律绝对路径
        version, reason = _version_ok(path, compatible)
        if reason:
            config["candidates"].append(dict(cand, version=version, ok=False,
                                             reason=reason))
            continue
        need_probe = cand.get("probe", True)
        ok, preason = (True, "") if not need_probe else _probe(path, config)
        if not ok:
            config["candidates"].append(dict(cand, version=version, ok=False,
                                             reason=preason))
            continue
        config["candidates"].append(dict(cand, version=version, ok=True))
        config["_cli_ok"] = path
        config["cli_version"] = version
        return path
    raise GatewayError(502, "network",
                    "已探测 %d 个位置，均不合格（详见 /healthz）"
                    % len(config["candidates"]))
# —— Instance 与 CliManager（池语义 / 风暴保护 / 回收规则）——


class Instance:
    """池内一个实例 = 1 下游进程 + 1 端口 + 1 套按驱动隔离的数据目录。
    状态机: stopped → starting → ready ⇄ busy → stopped。— 小欧 2026-11-05"""

    def __init__(self, index, port, config):
        self.index, self.port, self.config = index, port, config
        self.state = "stopped"
        self.proc = None
        self.log_file = None
        self.password = ""              # 仅内存: 不落盘 / 不回显 / 退出即弃 — 小欧 2026-11-05
        self.started_at = 0.0
        self.last_request_at = 0.0
        self.requests_done = 0          # R3 计数
        self.lock = threading.Lock()

    def start(self):
        """stopped|busy(刚被 acquire) → ready: 按需启动并等就绪。
        幂等: 已 ready 或进程存活时直接复用。— 小欧 2026-11-05"""
        with self.lock:
            if self.state == "ready":
                return
            if self.proc is not None and self.proc.poll() is None:
                self.state = "ready"          # 进程活但状态漂移(理论不可达): 就地复位
                return
            self.state = "starting"
        log_file = None
        try:
            exe = resolve_admitted_cli(self.config)
            logs_dir = os.path.join(runtime_dir(), "logs")
            os.makedirs(logs_dir, exist_ok=True)
            log_file = open(os.path.join(logs_dir, "cli-out.log"), "ab")
            self.log_file = log_file                  # 先挂上: 失败路径靠 _close_log 必达
            env = _env_for("i%d" % self.index)         # 出生前装配, 隔离目录由驱动给 — 小欧 2026-11-05
            self.proc = _spawn(exe, self.port, env, SANDBOX_CWD, log_file)
            self.password = _read_password(self.proc, timeout=20, log_file=log_file)
            if not self.password:
                raise GatewayError(502, "server", "网关内部错误（下游密码未捕获）",
                                "stdout 20 s 内未出现驱动约定的密码行")
            self._wait_ready()                         # R0: 新进程天然零会话
            self.state, self.started_at = "ready", time.time()
            self.last_request_at, self.requests_done = time.time(), 0
        except GatewayError:
            _terminate(self.proc)
            self._close_log()                          # 失败路径必关句柄, 防重启风暴下泄漏 — 小欧 2026-11-05
            self._reset("stopped")
            raise
        except Exception as exc:
            _terminate(self.proc)
            self._close_log()
            self._reset("stopped")
            raise GatewayError(502, "network", "下游启动失败", str(exc)) from exc

    def _wait_ready(self):
        """就绪轮询骨架通用; 硬判点是驱动的 ready()。— 小欧 2026-11-05"""
        auth = DRV.auth(self.password)
        deadline = time.time() + float(self.config["startup_timeout"])
        while time.time() < deadline:
            if self.proc is not None and self.proc.poll() is not None:
                raise GatewayError(502, "server", "下游进程启动即退出",
                                "exit=%s" % self.proc.returncode)
            if DRV.ready(self.port, auth):
                return
            time.sleep(0.25)
        raise GatewayError(502, "network",
                        "下游启动超时（超过 %d s）" % int(self.config["startup_timeout"]))

    def touch(self):
        """请求结束: 计数 +1 + 重置任务窗口（不 kill）。— 小欧 2026-11-05"""
        self.last_request_at = time.time()
        self.requests_done += 1

    def stop(self):
        """幂等停机（空闲/老化回收与停服共用）。busy 期间绝不调用。— 小欧 2026-11-05"""
        with self.lock:
            if self.state == "stopped":
                return
        _terminate(self.proc)
        self.proc = None
        self._close_log()
        self._reset("stopped")

    def _close_log(self):
        """关闭下游 stdout 日志句柄; 幂等（stop 与 start 失败路径共用）— 小欧 2026-11-05"""
        if self.log_file is not None:
            try:
                self.log_file.close()
            except Exception:
                pass
            self.log_file = None

    def _reset(self, state):
        self.state = state
        self.password = ""              # 进程退出即丢弃 — 小欧 2026-11-05

    def is_idle_beyond(self, gap_s):
        return self.state == "ready" and (time.time() - self.last_request_at) > gap_s

    def is_stale(self, max_age_s, max_requests):
        """老化判据: 存活超限或完成请求数超限（在请求边界执行）。— 小欧 2026-11-05"""
        return self.state == "ready" and (
            time.time() - self.started_at > max_age_s
            or self.requests_done >= max_requests)

    def http(self):
        """绑实例的 httpx 客户端; trust_env=False 防系统代理劫持; auth 由驱动给。
        只跑本地快调用, 长等待由 /wait 的 timeout 单独给。— 小欧 2026-11-05"""
        return httpx.Client(
            base_url="http://127.0.0.1:%d" % self.port,
            auth=DRV.auth(self.password),
            timeout=httpx.Timeout(connect=10, read=60, write=30, pool=10),
            trust_env=False)

    def aclient(self, read_timeout=60):
        """http() 的异步版: 非流式整包全链路走它, 不阻塞事件循环。
        read_timeout 可传: /wait 是阻塞式等待, 调用点单独给 900 s。— 小欧 2026-11-05"""
        return httpx.AsyncClient(
            base_url="http://127.0.0.1:%d" % self.port,
            auth=DRV.auth(self.password),
            timeout=httpx.Timeout(connect=10, read=read_timeout, write=30, pool=10),
            trust_env=False)

    def snapshot(self):
        """/healthz.instances[] 元素; 绝不含密码。— 小欧 2026-11-05"""
        return {"index": self.index, "port": self.port, "state": self.state,
                "pid": self.proc.pid if self.proc is not None else None,
                "requests": self.requests_done}


class CliManager:
    """实例池唯一管理者; gateway.py 只与它对话。
    启动清场: 会话 ID 全由网关创建, 生命周期与请求同生共死, 天然无欠账。— 小欧 2026-11-05"""

    def __init__(self, config):
        if DRV is None:
            install_driver(config)
        self.driver = DRV
        self.config = config
        _reap_orphans(config)           # 先清上次强杀遗留的下游, 再定池端口
        self.instances = [Instance(i, port, config)
                          for i, port in enumerate(_pick_consecutive_ports(config))]
        self.queue_max = int(config["queue_max"])
        self.cond = threading.Condition()
        self._waiting = 0               # 排队中的请求数（池满时累计）
        self.restart_lock = threading.Lock()
        self.last_restart_at = 0.0
        self.backoff_level = 0          # 60→120→240→…→1800 — 小欧 2026-11-05
        self.fail_streak = 0            # 连续下游类失败计数（达 fail_threshold 才重启）— 小欧 2026-11-05
        self.restarted_since_success = False   # 上次重启后尚无成功请求 = 连续失败 — 小欧 2026-11-05
        self.cooldown_until = 0.0       # 内部冷却截止（值只在内存）— 小欧 2026-11-05
        self.stop_flag = False
        self._reaper_started = False    # start_reaper 幂等标志 — 小欧 2026-11-05

    # --- 启停 ---

    def start_reaper(self):
        """后台清扫线程: 老化回收 + 空闲回收。5 s 一轮, busy 的实例一律跳过。幂等。— 小欧 2026-11-05"""
        if self._reaper_started:
            return
        self._reaper_started = True
        threading.Thread(target=self._reaper_loop, daemon=True).start()

    def _reaper_loop(self):
        while not self.stop_flag:
            time.sleep(5)
            try:
                self._reap_once()
            except Exception as exc:      # 单轮异常不得杀线程, 否则清扫静默停摆 — 小欧 2026-11-05
                print("[reaper] 本轮清扫异常, 已跳过: %r" % (exc,), file=sys.stderr)

    def _reap_once(self):
        """单轮: 老化/请求数优先于空闲回收; busy 的实例一律跳过。— 小欧 2026-11-05"""
        cfg = self.config
        r6_on = bool(cfg.get("r6_enabled", True))
        gap = int(cfg["task_idle_gap_s"] if r6_on else cfg["idle_seconds"])
        for inst in self.instances:
            if inst.state == "busy":
                continue            # busy 绝不杀（停机只发生在 ready）— 小欧 2026-11-05
            if inst.is_stale(int(cfg["max_age_seconds"]), int(cfg["max_requests"])):
                inst.stop()         # 老化/请求数超限 — 小欧 2026-11-05
            elif inst.is_idle_beyond(gap):
                inst.stop()         # 空闲回收（窗口等停机）— 小欧 2026-11-05

    def shutdown(self):
        """网关退出: 全部实例 terminate（本模块是下游唯一责任人）。— 小欧 2026-11-05"""
        self.stop_flag = True
        for inst in self.instances:
            inst.stop()

    # --- 池与队列（并发与背压 / 冷却） ---

    def acquire(self):
        """取空闲实例; 池满排队（≤ queue_max）。
        队全满抛 gateway-busy, Retry-After 给短值; 冷却不在此判。— 小欧 2026-11-05"""
        with self.cond:
            while True:
                for inst in self.instances:
                    if inst.state in ("stopped", "ready"):
                        inst.state = "busy"
                        return inst
                if self._waiting >= self.queue_max:
                    raise GatewayError(429, "gateway-busy",
                                    "网关繁忙（排队已达 %d）" % self.queue_max,
                                    retry_after_s=5.0)
                self._waiting += 1
                try:
                    self.cond.wait(timeout=60)
                finally:
                    self._waiting -= 1

    def release(self, inst):
        if inst.state == "busy":
            inst.state = "ready"
        with self.cond:
            self.cond.notify()

    def ensure_not_cooling(self):
        """冷却窗口内拒绝调模型（会抛, 不是查询）; 模型发现不耗额度, 不调本方法 — 小欧 2026-11-05"""
        remain = self.cooldown_until - time.time()
        if remain > 0:
            raise GatewayError(429, "free-limit",
                            "免费额度受限，冷却中（约 %d s 后可重试）" % int(remain))

    def note_cooldown(self, ms):
        """429 free-limit → 内部冷却, 绝不重启（重启不改出口 IP）。
        下游 retryAfterMs 采信但封顶 COOLDOWN_S, 无头值同样按 COOLDOWN_S 记。— 小欧 2026-11-05"""
        secs = min((ms or 0) / 1000.0, COOLDOWN_S)
        self.cooldown_until = max(self.cooldown_until,
                                  time.time() + (secs if secs > 0 else COOLDOWN_S))

    # --- 失败计数 + 重启风暴保护 ---

    def note_success(self):
        """请求成功收口: 失败计数清零; 上次重启后终于成功 → 退避复位。— 小欧 2026-11-05"""
        self.fail_streak = 0
        if self.restarted_since_success:
            self.restarted_since_success = False
            self.backoff_level = 0

    def on_downstream_failure(self, etype):
        """连续 fail_threshold 次下游类失败才重启一次; 连续重启失败才升级退避。
        单次抖动不重启, 退避窗口内不重启（计数保留）。— 小欧 2026-11-05"""
        if etype not in RESTARTABLE_TYPES:
            return
        cfg = self.config
        self.fail_streak += 1
        if self.fail_streak < int(cfg["fail_threshold"]):
            return                      # 未达阈值: 单次抖动不重启（R4）
        interval = float(cfg["restart_min_interval_s"])
        wait = min(interval * (2 ** self.backoff_level), float(cfg["backoff_cap_s"]))
        if time.time() - self.last_restart_at < wait:
            return                      # 退避窗口内不重启; 计数保留, 窗口过后再试
        if not self.restart_lock.acquire(blocking=False):
            return                      # 单飞: 已有重启在途, 并发请求等它完成
        try:
            failed = False
            for inst in self.instances:
                if inst.state != "busy":
                    try:
                        inst.stop()
                    except Exception:
                        failed = True
            self.last_restart_at = time.time()
            if self.restarted_since_success or failed:
                # 上次重启后仍无成功请求（或停止动作本身报错）→ 连续重启失败, 升级退避
                self.backoff_level = min(self.backoff_level + 1, 5)
            self.restarted_since_success = True
            self.fail_streak = 0
        finally:
            self.restart_lock.release()

    def restart_wait_remaining(self):
        """重启退避剩余秒数（/healthz 用）。— 小欧 2026-11-05"""
        interval = float(self.config["restart_min_interval_s"])
        wait = min(interval * (2 ** self.backoff_level),
                   float(self.config["backoff_cap_s"]))
        return max(0.0, self.last_restart_at + wait - time.time())

    # --- /healthz 聚合（运维事实; 密码/token 永不出现） ---

    def health_snapshot(self):
        states = [inst.state for inst in self.instances]
        serving = [s for s in states if s in ("ready", "busy")]
        status = "degraded" if (not serving and "stopped" not in states) else "ok"
        if all(s == "stopped" for s in states):
            cli = "idle"                # cli=idle 不是错误: 先按需启动再转发 — 小欧 2026-11-05
        elif serving:
            cli = "up"
        else:
            cli = "down"
        return {
            "status": status,
            "cli": cli,
            "driver": self.driver.name,
            "driver_version": self.config.get("cli_version", ""),
            "frozen": FROZEN,
            "system_probe": self.config.get(
                "system_probe_note",
                "disabled(packaged)" if FROZEN else "allowed"),
            "candidates": self.config.get("candidates", []),
            "instances": [inst.snapshot() for inst in self.instances],
            "restart_backoff_s": round(self.restart_wait_remaining(), 1),
            "cooldown_remaining_s": max(0, int(self.cooldown_until - time.time())),
            "pool_states": sorted(set(states)),
        }
