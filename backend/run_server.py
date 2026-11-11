# ============================================================================
# exe打包启动入口 — PyInstaller Analysis 入口, uvicorn 编程式启动(无--reload)
# 创建: 2026-09-19 小欧 - 后端打包exe(北京老陈驱动)
# 用法: run_server.exe [--host 127.0.0.1] [--port 8000] [--forwarded-allow-ips 127.0.0.1] [--no-wait]
#   程序自身资源(version.txt/config/config.yaml/logs/)定位exe所在目录,
#   首次启动若 config/config.yaml 缺失则由 config.yaml.example 复制生成。
#
# 编辑历史:
#   2026-09-19 小欧 - 新建。
#   2026-09-27 小欧 - 新增 --forwarded-allow-ips（显式传参，默认 127.0.0.1）。
#     起因: 该值原先走 uvicorn 默认值、不显式声明，运维为图省事改成 `*` 时无人察觉，
#     而 `*` 意味着任意客户端可伪造 X-Forwarded-For 把来源 IP 伪造成 127.0.0.1 →
#     免口令进（可读全部明文密钥、可改口令）。显式暴露该参数 + 启动告警 + 应用层
#     fail-closed（deps._is_trusted_localhost）三道防线。
#   2026-10-11 小欧 - 北京老陈令「打包版默认 8500」(--port 默认值 8000→常量 DEFAULT_PORT=8500;
#     打包配套文件非 app/ 系统代码, 可改; 配套删 pyi_rthook_default_port, 单一机制)。
#   2026-10-24 小欧 - FIX: 新增 _deploy_resources() 自动部署必备文件 + _ensure_config 提前到 import app.main 之前。
#     根因: PyInstaller onedir 模式下 datas 只落到 _internal/，但程序运行时期望这些文件在 exe 同级。
#     修复: 启动时自动从 _internal/ 拷贝 version.txt / config.yaml.example / OmniAgent.md 到 exe 同级 — 小欧-2026-10-24
#     根因2: app/logger/config.py:30 在模块级调用 get_config() → Config._load_config()
#     → _check_config_exists() 抛 FileNotFoundError，此时 _ensure_config 尚未执行。
#     修复2: _deploy_resources() 先部署文件，再 _ensure_config() 生成 config.yaml，最后才 import app.main — 小欧-2026-10-24
#   2026-10-24 小欧 - FIX2: _deploy_resources 改按 mtime 判定刷新(源新于目标则覆盖), 并加 刷新/跳过/失败 三类日志。
#     根因: 原判据 `not dst.exists()` 只创建不更新 —— 升级打包版本后 _internal/ 内
#     version.txt / OmniAgent.md 已更新, 但 exe 同级旧文件已存在 → 永不刷新 →
#     版本号显示旧值、项目规则不随升级生效, 且全程无报错(静默失效)。
#     修复: 抽出 _deploy_one() 单份部署, 三文件同一判据 src.stat().st_mtime > dst.stat().st_mtime;
#     config.yaml.example 刷新无害(_ensure_config 仅在 config/config.yaml 缺失时复制它)。
#   2026-10-25 小欧 - uvicorn 日志接管: 启动前调 setup_uvicorn_loggers(), uvicorn.run 传 log_config=None。
#     根因: 默认 dictConfig 把 uvicorn.access/error 指到同步 StreamHandler, 阻塞型 stdout 时冻结事件循环线程。
#     log_config=None 阻断 uvicorn 覆盖本配置, 否则装配无效。 — 小欧-2026-10-25
#     补充: uvicorn 三 logger 只挂共享文件 handler 落盘, 不挂 console 镜像(访问日志高频刷屏且无排障价值),
#     事件循环线程彻底零同步 stdout/stderr 写。 — 小欧-2026-10-25
#   2026-10-30 小欧 - version.txt 强制复制覆盖: _deploy_one 增 force 参数;
#     version.txt 部署改 force=True 不判 mtime 无条件覆盖(版本号必须与包内最新一致,
#     防目标 mtime 更新/被外部改动后跳过刷新致旧版本号); config.yaml.example/OmniAgent.md
#     保持原 mtime 判据不变。 — 小欧-2026-10-30
#   2026-10-30 小欧 - --forwarded-allow-ips 默认加 ::1 覆盖 IPv6 回环(原只 127.0.0.1,
#     部分系统 localhost 优先解析 ::1, 走 IPv6 时本机访问被误判 fail-closed);
#     help 文案精简为"可信反向代理 IP(逗号分隔,含 IPv6)…"; ⚠ 警告文案同步精简。
#     注: 不能写 localhost —— uvicorn 按 TCP 对端 IP 匹配(proxy_headers.py),
#     DNS 已把 localhost 解析成 IP, 字面量永不匹配。 — 小欧-2026-10-30
#   2026-11-04 小欧 - 新增端口预检 _port_busy/_port_owner/_explain_port_busy: 占用时不做
#     _deploy_resources 与 app.main 导入(原要白跑 1.7s 初始化, 到 uvicorn bind 才报
#     Errno 10048 退出, 用户看到的是"启动到一半就死"), 改为启动前试绑即判, 打印占用者
#     PID/进程名/路径 + 两条出路(本程序已在运行→直接浏览器用; 否则给清理命令/换端口)。
#     不自动杀进程: 占用者可能是无关程序或在跑任务的本程序实例, 自动杀等于误杀/丢数据。
#     — 小欧-2026-11-04
#   2026-11-04 小欧 - 新增 _wait_before_close + --no-wait: 占用提示后窗口驻留 30 秒再退出
#     (原 sys.exit 立即退, 双击启动时控制台一闪而过, 提示根本来不及看), 按任意键可提前关;
#     stdio 被重定向(脚本/自动化调用)不等待, 免得卡住调用方, --no-wait 可强制跳过。 — 小欧-2026-11-04
#   2026-11-06 小欧 - 根治幽灵配置文件: _ensure_config 原恒用 base/config/, 源码模式(base=backend)
#     生成到 backend/config/config.yaml, 而运行时 get_config_path() 读取代码库根 config/config.yaml
#     (路径错位) → backend/config/config.yaml 每次启动被重建、永不生效、反复误导定位(用户多次删除仍再生)。
#     修复: 新增 _config_target(): frozen=exe同级 config/, 源码=代码库根 config/(与 get_config_path 同源);
#     example 源 frozen=exe同级, 源码=backend/config.yaml.example(git 唯一模板)。 — 小欧-2026-11-06
#   2026-11-12 小欧 - uvicorn.run log_level "info"→None: 该值在 uvicorn Config.configure_logging 中
#     会 setLevel 强覆盖 uvicorn.error/access/asgi, 与 setup_uvicorn_loggers 设的总闸 DEBUG 冲突
#     (原来靠 startup 二次纠正才恢复, 属多余绕路); 置 None 后由本系统 handler 阈值统一裁决 — 小欧-2026-11-12
# ============================================================================
import argparse
import shutil
import sys
from multiprocessing import freeze_support
from pathlib import Path
from typing import Optional, Tuple

if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())  # 与 app/main.py 同策略
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass


# 打包版默认端口(北京老陈令: 与代码库惯例 :8000 双开不冲突; 避开 E2E 代理 :9000)。
# 改端口只改这里, 重打即生效; 显式传 --port 恒优先 — 小欧-2026-10-11
DEFAULT_PORT = 8500


def _port_busy(host: str, port: int) -> bool:
    """试绑同 host/port 判占用(绑完立即关) — 小欧 2026-11-04

    与 uvicorn 内部绑定同口径, 但提前到任何初始化之前, 避免白跑 1.7s 才报 10048。
    Windows 下未设 SO_REUSEADDR, 已被监听的端口 bind 必抛 OSError, 与 uvicorn 一致。
    """
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
        return False
    except OSError:
        return True
    finally:
        sock.close()


def _port_owner(port: int) -> Optional[Tuple[int, str, str]]:
    """查监听 port 的进程 (pid, 进程名, 可执行路径); 不可用/无权限返回 None — 小欧 2026-11-04"""
    try:
        import psutil

        for conn in psutil.net_connections(kind="inet"):
            if conn.status != psutil.CONN_LISTEN or not conn.laddr or conn.laddr.port != port:
                continue
            if not conn.pid:
                return None
            try:
                proc = psutil.Process(conn.pid)
                cmd = proc.cmdline()
                return conn.pid, proc.name(), (cmd[0] if cmd else "")
            except Exception:
                return conn.pid, "", ""
    except Exception:
        return None
    return None


def _explain_port_busy(host: str, port: int) -> None:
    """端口占用的人话说明: 是谁占的 + 两条出路(直接用/清理或换端口) — 小欧 2026-11-04"""
    owner = _port_owner(port)
    pid, name, exe = owner if owner else (0, "", "")
    is_self = "omniagent" in name.lower() or "omniagent" in exe.lower()
    shown_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    rule = "=" * 68

    print(f"\n{rule}", flush=True)
    print(f"[run_server] ❌ 端口 {port} 已被占用, 本次启动终止(未改动任何文件)", flush=True)
    print(rule, flush=True)
    if pid:
        print(f"  占用者: PID {pid}  {name or '未知进程'}", flush=True)
        if exe:
            print(f"          {exe}", flush=True)
    else:
        print("  占用者: 未识别(可能权限不足, 或被系统进程占用)", flush=True)

    if is_self:
        print("\n  ✅ 判断: 本程序已经在运行, 不用再开一个 —— 浏览器直接访问:", flush=True)
        print(f"     👉 http://{shown_host}:{port}", flush=True)
        print("\n  只有确认要重启时才需要结束它:", flush=True)
    else:
        print("\n  要用本程序, 先清理占用者(或换个端口):", flush=True)

    if pid:
        print("\n  ① 结束占用进程", flush=True)
        print(f"     PowerShell:  Stop-Process -Id {pid} -Force", flush=True)
        print(f"     CMD:         taskkill /F /PID {pid}", flush=True)
    else:
        print("\n  ① 查出是谁占的", flush=True)
        print(f"     PowerShell:  Get-NetTCPConnection -LocalPort {port} -State Listen", flush=True)
        print(f"                  Get-NetTCPConnection -LocalPort {port} -State Listen"
              f" | ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force }}", flush=True)
        print(f"     CMD:         netstat -ano | findstr :{port}", flush=True)
        print(f"                  for /f \"tokens=5\" %a in ('netstat -ano ^| findstr :{port}"
              f" ^| findstr LISTENING') do taskkill /F /PID %a", flush=True)
    print("  ② 再双击本程序", flush=True)
    print("\n  不想清理也可以直接换端口启动(两种命令行相同):", flush=True)
    print(f"     OmniAgentBackend.exe --port {port + 1}", flush=True)
    print(f"{rule}\n", flush=True)


def _wait_before_close(seconds: int = 30) -> None:
    """端口占用提示后驻留 N 秒再退出, 防双击启动时窗口一闪而过看不清提示 — 小欧 2026-11-04

    有控制台时按任意键立即关闭; stdio 被重定向(脚本/自动化调用)不等待, 免得卡住调用方。
    """
    import time

    if not sys.stdin or not sys.stdin.isatty():
        return
    try:
        import msvcrt
    except ImportError:
        msvcrt = None

    print(f"  本窗口保留 {seconds} 秒后自动关闭 (按任意键立即关闭)...", flush=True)
    deadline = time.monotonic() + seconds
    while True:
        left = int(round(deadline - time.monotonic()))
        if left <= 0:
            break
        print(f"\r  剩余 {left:2d} 秒 ", end="", flush=True)
        if msvcrt is not None and msvcrt.kbhit():
            msvcrt.getch()
            break
        time.sleep(0.2)
    print(f"\r{' ' * 24}\r", end="", flush=True)


def _exe_dir() -> Path:
    """exe所在目录(frozen)或本文件所在backend目录(源码调试) — 小欧 2026-09-19"""
    if getattr(sys, "frozen", False):
        # 业务源码以源码树拷入_internal/app, 需入sys.path才能按普通源码导入 — 小欧 2026-09-19
        sys.path.insert(0, sys._MEIPASS)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _deploy_one(src: Path, dst: Path, name: str, force: bool = False) -> None:
    """单份资源部署: 缺失则创建, 源 mtime 新于目标则刷新 — 小欧 2026-10-24

    判据用 mtime 而非 exists(): 升级打包版本后 _internal/ 内的源文件已更新,
    若只判 exists(), exe 同级旧文件会永不刷新 → version.txt 显示旧版本号、
    OmniAgent.md 规则不随升级生效, 且全程无报错(静默失效)。

    force=True: 无条件复制覆盖(不判 mtime)。version.txt 专用 —— 版本号必须
    与包内最新一致, 即便目标 mtime 更新/被外部改动, 也强制用包内最新覆盖。
    — 小欧-2026-10-30
    """
    if not src.exists():
        return
    try:
        if force or not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime:
            shutil.copy2(src, dst)
            print(f"[run_server] _deploy_resources: refreshed {name} -> {dst}", flush=True)
        else:
            print(f"[run_server] _deploy_resources: skipped {name} (dst >= src)", flush=True)
    except OSError as e:
        print(f"[run_server] ⚠️ _deploy_resources: FAILED {name} -> {dst}: {e}", flush=True)


def _deploy_resources(base: Path) -> None:
    """打包后资源部署: 把 _internal/ 里的必备文件拷到 exe 同级 — 小欧 2026-10-24
    
    PyInstaller onedir 模式下 datas 只落到 _internal/，但程序运行时期望这些文件在 exe 同级。
    本函数在启动时自动完成部署，无需手动收尾拷贝。

    刷新判据: 源 mtime 新于目标则覆盖(见 _deploy_one), 三份文件同一判据。
    config.yaml.example 刷新无害 —— _ensure_config 仅在 config/config.yaml 缺失时
    才从 example 复制, 用户已生成的 config.yaml 不受影响。

    version.txt 例外: 强制复制覆盖(force=True), 版本号必须与包内最新一致,
    不因目标 mtime 更新而跳过 —— 北京老陈令 2026-10-30。
    """
    src_base = base / "_internal"
    if not src_base.exists():
        return
    # version.txt — 必须存在且为最新(强制覆盖, 不判 mtime), 否则 get_version() 返回旧版本号或 "0.0.0"
    _deploy_one(src_base / "version.txt", base / "version.txt", "version.txt", force=True)
    # config.yaml.example — 必须存在, 否则 _ensure_config 无法生成 config.yaml
    _deploy_one(src_base / "config.yaml.example", base / "config.yaml.example", "config.yaml.example")
    # OmniAgent.md — 项目规则文件注入 System Prompt; 缺失时程序只建空文件 → 规则不生效
    _deploy_one(src_base / "OmniAgent.md", base / "OmniAgent.md", "OmniAgent.md")


def _config_target(base: Path) -> Path:
    """config/config.yaml 目标路径 — 小欧 2026-11-06

    frozen(exe): exe 同级的 config/config.yaml(程序资源在 exe 旁, 与 _deploy_resources 一致)。
    源码模式: 代码库根(backend 上级) 的 config/config.yaml —— 与 app.config.get_config_path()
    返回值一致(该函数按 app/config.py 位置上溯 3 层 = 代码库根)。两模式保证
    "生成位置 == 运行时读取位置", 杜绝幽灵配置文件(2026-11-06 根治)。"""
    if getattr(sys, "frozen", False):
        return base / "config" / "config.yaml"
    return Path(__file__).resolve().parent.parent / "config" / "config.yaml"


def _ensure_config(base: Path) -> None:
    """首次启动补 config/config.yaml(缺失时由 config.yaml.example 复制) — 小欧 2026-09-19

    2026-11-06 修复: 目标路径改用 _config_target()(frozen=exe同级/源码=代码库根), example 源
    frozen=exe同级, 源码=backend/config.yaml.example(git 唯一模板)。原实现恒用 base/config/
    在源码模式生成 backend/config/config.yaml, 与运行时读取位置(仓库根 config/)错位,
    导致该文件每次启动被重建却不生效。 — 小欧-2026-11-06"""
    target = _config_target(base)
    if target.exists():
        return
    if getattr(sys, "frozen", False):
        example = base / "config.yaml.example"
    else:
        example = Path(__file__).resolve().parent / "config.yaml.example"
    if example.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(example, target)
        print(f"[run_server] 已由 config.yaml.example 生成 {target}", flush=True)


def main() -> None:
    freeze_support()
    parser = argparse.ArgumentParser(description="OmniAgentAst 后端服务")
    parser.add_argument("--host", default="127.0.0.1")
    # 2026-10-11 小欧 - 北京老陈令「打包版默认 8500」(代码库占惯例 :8000 不动):
    #   本文件属打包配套(非 app/ 系统代码,可改); 改默认值不锁死, 显式传 --port 恒优先。
    #   配套删 pyi_rthook_default_port(同一目的不再留两套机制) — 小欧-2026-10-11
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--forwarded-allow-ips", default="127.0.0.1,::1",
        help="可信反向代理 IP（逗号分隔，含 IPv6）。默认只信任本机。"
             "非可信反代环境请勿改动，填 * 会信任任意来源（危险）。")
    parser.add_argument(
        "--no-wait", action="store_true",
        help="端口被占用时打印提示后立即退出, 不等 30 秒(供脚本/自动化调用)")
    args = parser.parse_args()

    if args.forwarded_allow_ips.strip() == "*":
        # 不是禁止启动（部署者可能知情），但必须让风险可见 —— 应用层会因无法区分
        # 真回环与伪造而取消回环豁免（deps._is_trusted_localhost），即本机也要输口令。
        print("[run_server] ⚠️ 警告：--forwarded-allow-ips=* 会信任所有来源，"
              "客户端可伪造来源 IP，本机访问将不再自动豁免口令。", flush=True)

    # 端口预检: 被占则说明是谁占的并给出出路后退出, 不进入 _deploy_resources/app.main 初始化 — 小欧 2026-11-04
    if _port_busy(args.host, args.port):
        _explain_port_busy(args.host, args.port)
        if not args.no_wait:
            _wait_before_close()
        sys.exit(1)

    base = _exe_dir()
    _deploy_resources(base)   # 自动部署 version.txt/config.yaml.example/OmniAgent.md 到 exe 同级
    _ensure_config(base)      # 确保 config/config.yaml 存在，再导入 app.* 模块

    import app.main  # noqa: F401 — 供PyInstaller静态收集业务第三方依赖, 运行期仍由uvicorn按名加载
    # 小欧 - 2026-09-27：把 forwarded_allow_ips 注入应用层。
    #   应用层原先自己读 FORWARDED_ALLOW_IPS 环境变量，与 uvicorn 各读一次可能不一致
    #   （命令行启动时应用层读不到、只看到默认值）。改为同源注入，两边不可能分叉，
    #   并顺带修掉"命令行传 * 时应用层检测不到、fail-closed 失效"的盲区。
    from app.api.v1.deps import set_forwarded_allow_ips
    set_forwarded_allow_ips(args.forwarded_allow_ips)
    # uvicorn 日志非阻塞化(2026-10-25): 须在 uvicorn.run 之前装配, 且传 log_config=None
    # 防 uvicorn 默认 dictConfig 覆盖。 — 小欧-2026-10-25
    # 2026-11-12 小欧 - log_level=None: 不在 uvicorn 侧设级别, 交由本系统 handler 阈值裁决(原因见文件头历史)。
    from app.logger.shared_handler import setup_uvicorn_loggers
    setup_uvicorn_loggers()
    import uvicorn
    uvicorn.run("app.main:app", host=args.host, port=args.port, log_level=None,
                log_config=None, forwarded_allow_ips=args.forwarded_allow_ips)


if __name__ == "__main__":
    main()
