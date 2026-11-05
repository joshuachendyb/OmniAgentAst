# -*- coding: utf-8 -*-
r"""cli_manager.py — 下游进程生命周期框架（通用层; 方言细节全部经驱动挂钩, D25）。

编写人: 小欧    创建时间: 2026-11-05 09:10:00
对齐: 6.3 定位与准入 / 7.1 生命周期 / 7.2 池与回收 / 8.2 权限 / 8.4 隔离 /
     8.6 密码不落盘。通用层零方言——候选、报文端点、密码形状、就绪判据均由
     vendor\<provider>\driver 给出（9.1.5 接口）。

职责覆盖（对应 9.6 实施步骤 0/3）:
  1. preflight()     启动前安全闸门: 回环 + token + deny * + 驱动可装载, 缺失拒绝启动（8.2/8.5）
  2. init_driver()   装载驱动（config["driver"]）并注入运行时键（runtime_dir/frozen/machine_root）
  3. admitted_exe()  三关准入: 版本可读 → 版本范围 → 能力探针（6.3.4）; 全失败抛 502
  4. Instance        环境装配(8.4) → spawn → stdout 捕获密码(8.6) → 就绪判定(7.1.3)
  5. CliManager      实例池 + 队列 32 + R0–R6(7.2.2) + 重启风暴保护(7.2.4) + R5 冷却
                      + 启动时清掉上次强杀遗留的下游进程（7.2.7 池端口）

编辑历史:
  2026-11-05 R5 冷却封顶 1 h（下游 retryAfterMs 实测虚高 14 h）; 启动清场; 端口漂移留痕 -- 小欧
  2026-11-05 冷却判定从 acquire 迁出为 check_cooldown（模型发现不拦）; netstat 改按字节收防 GBK 静默失败 -- 小欧
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

from driver import get_driver
from errors import RESTARTABLE_TYPES

# 8.2 硬约束: deny * 必须在最前（下游按 findLast 生效, 后写覆盖先写）
PERMISSIONS = [
    {"action": "*", "resource": "*", "effect": "deny"},
    {"action": "read", "resource": "Z:/nope/*", "effect": "allow"},
]

FROZEN = bool(getattr(sys, "frozen", False))    # 打包版硬约束总开关（6.3.6）
COOLDOWN_S = 3600        # 4.7 规则 3: free-limit 冷却按 1 h 记; 下游 retryAfterMs 实测虚高到 14 h, 只作上限判据


def runtime_dir():
    """网关自身目录: 打包版 = exe 同级; 源码 = 本文件目录。注入驱动候选路径用。"""
    if FROZEN:
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def machine_root():
    r"""机器级根目录（LOCALAPPDATA\opencli-gateway; 多安装共享与沙箱的公共落点）。"""
    return os.path.join(os.environ.get("LOCALAPPDATA")
                        or os.path.expanduser("~\\AppData\\Local"), "opencli-gateway")


SANDBOX_CWD = os.path.join(machine_root(), "sandbox")   # 空目录铁律（8.4 禁放文件）

DRV = None          # 驱动单例; init_driver() 填充


def init_driver(config):
    """装载驱动并注入通用侧运行时键; 驱动只能读这些键, 不 import 通用层。"""
    global DRV
    config["runtime_dir"] = runtime_dir()
    config["frozen"] = FROZEN
    config["machine_root"] = machine_root()
    DRV = get_driver(config)
    return DRV


class GateError(Exception):
    """下游异常到 HTTP 错误的唯一出口（gateway 捕获后走 errors.make_error 统一信封）。"""

    def __init__(self, status, etype, message, detail="", retry_after_s=None):
        super().__init__(message)
        self.status, self.etype = status, etype
        self.message, self.detail = message, detail
        self.retry_after_s = retry_after_s


def _is_loopback(host):
    return host in ("127.0.0.1", "localhost", "::1")


def preflight(config):
    """启动前安全闸门（实施排期第 0 步, 9.6）。返回问题清单, 非空即拒绝启动。

    ①监听必须回环（8.5）②token 非空（宿主 ai.opencli.api_key 必须一致）
    ③权限规则首条必须 deny *（8.2 代码级校验——安全底线不依赖"配置没被改过"）
    ④驱动可装载且自报名与 config 一致（9.1.5）⑤配置项正常性兜底。
    """
    problems = []
    driver_error = None
    try:
        init_driver(config)
    except RuntimeError as exc:
        driver_error = str(exc)
    if driver_error is not None:
        problems.append(driver_error)
    if not _is_loopback(config.get("host", "127.0.0.1")):
        problems.append("拒绝启动: 监听地址必须为 127.0.0.1（8.5 强制回环）")
    if not str(config.get("token") or "").strip():
        problems.append("拒绝启动: token 为空（须与宿主 api_key 一致，8.5）")
    if not PERMISSIONS or PERMISSIONS[0].get("action") != "*" \
            or PERMISSIONS[0].get("effect") != "deny":
        problems.append("拒绝启动: 权限规则缺少首条 deny *（8.2 硬约束）")
    if int(config.get("pool_size", 2)) < 1:
        problems.append("拒绝启动: pool_size 至少为 1")
    if int(config.get("queue_max", 32)) < 1:
        problems.append("拒绝启动: queue_max 至少为 1")
    return problems


# ---------------------------------------------------------------------------
# 定位候选（驱动 5 级）+ 三关准入（6.3.3–6.3.5）
# ---------------------------------------------------------------------------

def resolve_cli(config):
    """候选解析 = 驱动的 5 级候选; 解析顺序与准入条件写死在 6.3.2 原则。"""
    return DRV.cli_candidates(config)


def _free_port_excluding(banned):
    """临时端口避开池段 [port_base, port_base+port_span-1]（6.3.4 探针端口纪律）。"""
    while True:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        if port not in banned:
            return port


def _pick_consecutive_ports(config):
    """port_base 起找 pool_size 个连续空闲端口; 整池顺延, 出 span 即失败（7.2.7）。

    整池连续是 /healthz.instances[] 端口清单可读的前提; 不无限顺延——否则可能
    撞上用户自己的服务, 故障更难定位（7.2.7 原文）。
    """
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
    raise GateError(502, "network",
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
    """启动清场: 网关被强杀会留下占池端口的下游 CLI, 不清则整池顺延且无告警
    （2026-11-05 实测池端口漂到 8205）; 只杀镜像名匹配本驱动的进程 — 小欧 2026-11-05
    """
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
    """极简范围判据: '>=2.2.0 <2.3.0' 只解上下限段（6.3.4 配置口径; 2.3 未验证卡上限）。"""
    lo = hi = None
    for token in str(compatible or "").split():
        if token.startswith(">="):
            lo = token[2:]
        elif token.startswith("<") and not token.startswith("<="):
            hi = token[1:]
    parts = [int(x) for x in version.split(".")]
    if lo and parts < [int(x) for x in lo.split(".")]:
        return False
    if hi and parts >= [int(x) for x in hi.split(".")]:
        return False
    return True


def _version_ok(path, compatible):
    """第①②关: --version 可读（正则来自驱动）且在范围。实测输出 `opencode v2.2.0`。"""
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
    """spawn 下游 serve; serve 子命令由驱动给出（8.4）, 通用层只管弹道与管道。"""
    return subprocess.Popen(
        [exe] + DRV.spawn_args(exe, port),
        env=env, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        creationflags=0x08000000)                  # CREATE_NO_WINDOW


def _terminate(proc):
    """幂等停止（重复调用不报错, 异常路径也要走到, 7.2.7 清理伪码）。"""
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
    """8.4 装配: 通用层合环境变量, 隔离目录由驱动 env_overrides(tag) 给出并创建。

    实测（8.4）: 用户全局配置在"建会话之前"就进入模型提示词——awareness 不可由
    权限规则补救, 必须出生前重定向; 隔离后人格词 0 命中。
    """
    env = os.environ.copy()
    env.update(DRV.env_overrides(tag))
    os.makedirs(SANDBOX_CWD, exist_ok=True)        # 空目录, 禁止放任何文件（8.4）
    return env


def _read_password(proc, timeout, log_file):
    """stdout 逐行: 驱动 credential() 判密码与脱敏; 首个密码即用（8.6）。

    实测: 密码 0.33 s 出现（6.3.4）; 密码只在内存, 不入日志、不回显 /healthz。
    注意: 读取线程必须【持续排空】stdout——若找到密码就停止读取, 子进程 64 KB
    管道缓冲写满会把下游整个卡死（实现级陷阱, 设计在此明确）。线程为 daemon,
    网关退出即随进程消亡。
    """
    holder = {"password": ""}

    def pump():
        for raw in iter(proc.stdout.readline, b""):
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            line, password = DRV.credential(line)   # 驱动: 判密 + 脱敏（8.6）
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
    """第③关能力探针: 起服务 → stdout 捕获密码 → 驱动 ready() → 立即终止（6.3.4）。

    探针端口避开池段; 探针进程不复用为服务进程（防状态污染）; 探针 XDG 目录
    用独立 tag, 用完即弃。返回 (ok, reason)。
    """
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
        _terminate(proc)                         # 探针进程验证完立即释放（6.3.4）
        try:
            log_file.close()
        except Exception:
            pass


def admitted_exe(config):
    """三关准入闸口: 逐候选过 ①②③关, 通过即缓存; 全失败抛 502（6.3.5 禁止硬跑）。"""
    cached = config.get("_cli_ok")
    if cached and os.path.exists(cached):
        return cached
    config["candidates"] = []
    compatible = (config.get("cli") or {}).get("compatible", ">=2.2.0 <2.3.0")
    for cand in resolve_cli(config):
        path = cand["path"]
        if os.path.dirname(path):
            exists = os.path.exists(path)
        else:
            exists = shutil.which(path) is not None    # PATH 候选（4 级）用 which 判存在
        if not exists:
            config["candidates"].append(dict(cand, ok=False, reason="not-found"))
            continue
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
    raise GateError(502, "network",
                    "已探测 %d 个位置，均不合格（详见 /healthz）"
                    % len(config["candidates"]))
# ---------------------------------------------------------------------------
# Instance 与 CliManager（7.2 池语义 / 7.2.4 风暴保护 / R0–R6 落地）
# ---------------------------------------------------------------------------

class Instance:
    """池内一个实例 = 1 下游进程 + 1 端口 + 1 套按驱动隔离的数据目录（7.2.7 并发表）。

    状态机（7.2 图）: stopped → starting → ready ⇄ busy →(窗口等停机) stopped
    down 在本实现中并回"由重启风暴保护统一处理"（7.2.4 单飞重启）。
    """

    def __init__(self, index, port, config):
        self.index, self.port, self.config = index, port, config
        self.state = "stopped"
        self.proc = None
        self.log_file = None
        self.password = ""              # 仅内存（8.6: 不落盘 / 不回显 / 退出即弃）
        self.started_at = 0.0
        self.last_request_at = 0.0
        self.requests_done = 0          # R3 计数
        self.lock = threading.Lock()

    def start(self):
        """stopped|busy(刚被 acquire) → ready（含 R1 按需启动 + R0 启动清场）。

        幂等: 已 ready 或进程存活时直接复用（7.2.8 任务窗口复用语义, 不重起）。
        实施偏差记录（2026-11-05 小欧）: acquire() 已把实例置 busy 再进本方法,
        原守卫 if self.state != "stopped" 让首次请求 no-op 启动(实测 10061)。
        按 7.2.7 规格修守卫: 每次请求 ensure_started 先于转发, 新实例必须真启动。
        """
        with self.lock:
            if self.state == "ready":
                return
            if self.proc is not None and self.proc.poll() is None:
                self.state = "ready"          # 进程活但状态漂移(理论不可达): 就地复位
                return
            self.state = "starting"
        log_file = None
        try:
            exe = admitted_exe(self.config)
            logs_dir = os.path.join(runtime_dir(), "logs")
            os.makedirs(logs_dir, exist_ok=True)
            log_file = open(os.path.join(logs_dir, "cli-out.log"), "ab")
            env = _env_for("i%d" % self.index)         # 8.4 出生前装配（驱动给目录）
            self.proc = _spawn(exe, self.port, env, SANDBOX_CWD, log_file)
            self.log_file = log_file
            self.password = _read_password(self.proc, timeout=20, log_file=log_file)
            if not self.password:
                raise GateError(502, "server", "网关内部错误（下游密码未捕获）",
                                "stdout 20 s 内未出现驱动约定的密码行")
            self._wait_ready()                         # R0: 新进程天然零会话
            self.state, self.started_at = "ready", time.time()
            self.last_request_at, self.requests_done = time.time(), 0
        except GateError:
            _terminate(self.proc)
            self._reset("stopped")
            raise
        except Exception as exc:
            _terminate(self.proc)
            self._reset("stopped")
            raise GateError(502, "network", "下游启动失败", str(exc)) from exc

    def _wait_ready(self):
        """就绪轮询骨架通用; 硬判点是驱动的 ready()（7.1.3 的落地核心）。"""
        auth = DRV.auth(self.password)
        deadline = time.time() + float(self.config["startup_timeout"])
        while time.time() < deadline:
            if self.proc is not None and self.proc.poll() is not None:
                raise GateError(502, "server", "下游进程启动即退出",
                                "exit=%s" % self.proc.returncode)
            if DRV.ready(self.port, auth):
                return
            time.sleep(0.25)
        raise GateError(502, "network",
                        "下游启动超时（超过 %d s）" % int(self.config["startup_timeout"]))

    def touch(self):
        """请求结束: R3 计数 +1 + 重置 120 s 任务窗口（不 kill, 7.2.8）。"""
        self.last_request_at = time.time()
        self.requests_done += 1

    def stop(self):
        """幂等停机（R6/R2/R3/停服共用）。busy 期间绝不调用（流会中断, 7.2 图）。"""
        with self.lock:
            if self.state == "stopped":
                return
        _terminate(self.proc)
        self.proc = None
        if self.log_file is not None:
            try:
                self.log_file.close()
            except Exception:
                pass
            self.log_file = None
        self._reset("stopped")

    def _reset(self, state):
        self.state = state
        self.password = ""              # 进程退出即丢弃（8.6）

    def is_idle_beyond(self, gap_s):
        return self.state == "ready" and (time.time() - self.last_request_at) > gap_s

    def is_stale(self, max_age_s, max_requests):
        """R3 判据: 存活超限或完成请求数超限（在请求边界执行, 7.2.2）。"""
        return self.state == "ready" and (
            time.time() - self.started_at > max_age_s
            or self.requests_done >= max_requests)

    def http(self):
        """绑实例的 httpx 客户端; trust_env=False 防系统代理劫持（8.5）; auth 由驱动给。

        超时对齐 7.6: 该 client 只跑本地快调用; 长等待由 /wait 的 timeout 单独给。
        """
        return httpx.Client(
            base_url="http://127.0.0.1:%d" % self.port,
            auth=DRV.auth(self.password),
            timeout=httpx.Timeout(connect=10, read=60, write=30, pool=10),
            trust_env=False)

    def snapshot(self):
        """/healthz.instances[] 元素; 绝不含密码（8.6）。"""
        return {"index": self.index, "port": self.port, "state": self.state,
                "pid": self.proc.pid if self.proc is not None else None,
                "requests": self.requests_done}


class CliManager:
    """实例池唯一管理者; gateway.py 只与它对话（3.6 依赖方向）。

    R0 启动清场 = 新进程 + 网关每请求删会话 + 7.2.3 的"网关自记账"口径:
    会话 ID 全部由网关创建, 生命周期与请求同生共死, 启动清场天然无欠账,
    因而不依赖"下游是否存在会话枚举端点"（7.2.3 待实机确认项的默认①）。
    """

    def __init__(self, config):
        if DRV is None:
            init_driver(config)
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
        self.backoff_level = 0          # 60→120→240→…→1800（7.2.4）
        self.cooldown_until = 0.0       # R5 内部冷却截止（值只在内存）
        self.stop_flag = False

    # --- 启停 -------------------------------------------------------------

    def start_reaper(self):
        """后台清扫线程: R6（或 R2 兜底）+ R3。5 s 一轮, busy 的实例一律跳过。"""
        threading.Thread(target=self._reaper_loop, daemon=True).start()

    def _reaper_loop(self):
        while not self.stop_flag:
            time.sleep(5)
            cfg = self.config
            r6_on = bool(cfg.get("r6_enabled", True))
            gap = int(cfg["task_idle_gap_s"] if r6_on else cfg["idle_seconds"])
            for inst in self.instances:
                if inst.state == "busy":
                    continue            # busy 绝不杀（7.2 图: 停机只发生在 ready）
                if inst.is_stale(int(cfg["max_age_seconds"]), int(cfg["max_requests"])):
                    inst.stop()         # R3: 此刻必无在跑请求
                elif inst.is_idle_beyond(gap):
                    inst.stop()         # R6（开）/ R2（R6 关时的兜底, 7.2.2）

    def shutdown(self):
        """网关退出: 全部实例 terminate（cli_manager 是下游唯一责任人, 7.2）。"""
        self.stop_flag = True
        for inst in self.instances:
            inst.stop()

    # --- 池与队列（7.5 并发与背压 / R5 冷却） ------------------------------

    def acquire(self):
        """取空闲实例; 池满排队（≤ queue_max=32）。

        gateway-busy: 网关自己的队全满, Retry-After 给短值（头 ≤30 s 纪律, 4.7）。
        R5 冷却不在此判: 冷却是"调模型"的限制, 模型发现不耗额度（见 check_cooldown）。
        """
        with self.cond:
            while True:
                for inst in self.instances:
                    if inst.state in ("stopped", "ready"):
                        inst.state = "busy"
                        return inst
                if self._waiting >= self.queue_max:
                    raise GateError(429, "gateway-busy",
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

    def check_cooldown(self):
        """R5: 冷却窗口内拒绝调模型; 模型发现不耗额度, 不调本方法 — 小欧 2026-11-05"""
        remain = self.cooldown_until - time.time()
        if remain > 0:
            raise GateError(429, "free-limit",
                            "免费额度受限，冷却中（约 %d s 后可重试）" % int(remain))

    def note_cooldown(self, ms):
        """R5: 429 free-limit → 内部冷却, 绝不重启（重启不改出口 IP, 7.2.2）。

        下游 retryAfterMs 采信但封顶 COOLDOWN_S; 无头值同样按 COOLDOWN_S 记
        （2026-11-05 实测: 下游给 14 h, 额度早已恢复仍被本地冷却拦住）— 小欧 2026-11-05
        """
        secs = min((ms or 0) / 1000.0, COOLDOWN_S)
        self.cooldown_until = max(self.cooldown_until,
                                  time.time() + (secs if secs > 0 else COOLDOWN_S))

    # --- R4 + 重启风暴保护（7.2.2 / 7.2.4） --------------------------------

    def record_failure(self, etype):
        """连续下游类失败计数。仅 timeout/network/server 计; 其余确定性错误直接忽略。"""
        if etype not in RESTARTABLE_TYPES:
            return
        cfg = self.config
        interval = float(cfg["restart_min_interval_s"])
        wait = min(interval * (2 ** self.backoff_level), float(cfg["backoff_cap_s"]))
        if time.time() - self.last_restart_at < wait:
            return                      # 退避期内不重启（熔断状态）
        if not self.restart_lock.acquire(blocking=False):
            return                      # 单飞: 已有重启在途, 并发请求等它完成
        try:
            ok = True
            for inst in self.instances:
                if inst.state != "busy":
                    try:
                        inst.stop()
                    except Exception:
                        ok = False
            self.last_restart_at = time.time()
            if ok:
                self.backoff_level = 0  # 一次成功动作即复位（成功即复位规则）
            else:
                self.backoff_level = min(self.backoff_level + 1, 5)
        finally:
            self.restart_lock.release()

    def restart_wait_remaining(self):
        """重启退避剩余秒数（/healthz 报 restart-backoff 用, 7.2.4）。"""
        interval = float(self.config["restart_min_interval_s"])
        wait = min(interval * (2 ** self.backoff_level),
                   float(self.config["backoff_cap_s"]))
        return max(0.0, self.last_restart_at + wait - time.time())

    # --- /healthz 聚合（7.1.6 运维事实; 密码/token 永不出现在此, 8.6） ------

    def health_snapshot(self):
        states = [inst.state for inst in self.instances]
        serving = [s for s in states if s in ("ready", "busy")]
        status = "degraded" if (not serving and "stopped" not in states) else "ok"
        if all(s == "stopped" for s in states):
            cli = "idle"                # cli=idle 不是错误（4.7 规则 2: 先 R1 再转发）
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
