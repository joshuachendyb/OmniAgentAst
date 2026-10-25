# ============================================================================
# exe打包启动入口 — PyInstaller Analysis 入口, uvicorn 编程式启动(无--reload)
# 创建: 2026-09-19 小欧 - 后端打包exe(北京老陈驱动)
# 用法: run_server.exe [--host 127.0.0.1] [--port 8000] [--forwarded-allow-ips 127.0.0.1]
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
# ============================================================================
import argparse
import shutil
import sys
from multiprocessing import freeze_support
from pathlib import Path

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


def _exe_dir() -> Path:
    """exe所在目录(frozen)或本文件所在backend目录(源码调试) — 小欧 2026-09-19"""
    if getattr(sys, "frozen", False):
        # 业务源码以源码树拷入_internal/app, 需入sys.path才能按普通源码导入 — 小欧 2026-09-19
        sys.path.insert(0, sys._MEIPASS)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _deploy_one(src: Path, dst: Path, name: str) -> None:
    """单份资源部署: 缺失则创建, 源 mtime 新于目标则刷新 — 小欧 2026-10-24

    判据用 mtime 而非 exists(): 升级打包版本后 _internal/ 内的源文件已更新,
    若只判 exists(), exe 同级旧文件会永不刷新 → version.txt 显示旧版本号、
    OmniAgent.md 规则不随升级生效, 且全程无报错(静默失效)。
    """
    if not src.exists():
        return
    try:
        if not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime:
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
    """
    src_base = base / "_internal"
    if not src_base.exists():
        return
    # version.txt — 必须存在且为最新, 否则 get_version() 返回旧版本号或 "0.0.0"
    _deploy_one(src_base / "version.txt", base / "version.txt", "version.txt")
    # config.yaml.example — 必须存在, 否则 _ensure_config 无法生成 config.yaml
    _deploy_one(src_base / "config.yaml.example", base / "config.yaml.example", "config.yaml.example")
    # OmniAgent.md — 项目规则文件注入 System Prompt; 缺失时程序只建空文件 → 规则不生效
    _deploy_one(src_base / "OmniAgent.md", base / "OmniAgent.md", "OmniAgent.md")


def _ensure_config(base: Path) -> None:
    """首次启动补 config/config.yaml(由同目录 config.yaml.example 复制) — 小欧 2026-09-19"""
    target = base / "config" / "config.yaml"
    if target.exists():
        return
    example = base / "config.yaml.example"
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
        "--forwarded-allow-ips", default="127.0.0.1",
        help="信任哪些对端的 X-Forwarded-For。默认仅本机反代。"
             "⚠️ 填 * 会让任意客户端伪造 client.host（可伪造 127.0.0.1 免口令访问），"
             "确需信任内网反代时只列该反代的 IP。")
    args = parser.parse_args()

    if args.forwarded_allow_ips.strip() == "*":
        # 不是禁止启动（部署者可能知情），但必须让风险可见 —— 应用层会因无法区分
        # 真回环与伪造而取消回环豁免（deps._is_trusted_localhost），即本机也要输口令。
        print("[run_server] ⚠️ 警告：--forwarded-allow-ips=* 信任任意来源的 X-Forwarded-For，"
              "客户端可伪造来源 IP。为安全起见，本机回环将不再自动豁免鉴权。", flush=True)

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
    from app.logger.shared_handler import setup_uvicorn_loggers
    setup_uvicorn_loggers()
    import uvicorn
    uvicorn.run("app.main:app", host=args.host, port=args.port, log_level="info",
                log_config=None, forwarded_allow_ips=args.forwarded_allow_ips)


if __name__ == "__main__":
    main()
