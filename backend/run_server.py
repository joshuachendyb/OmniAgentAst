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


def _exe_dir() -> Path:
    """exe所在目录(frozen)或本文件所在backend目录(源码调试) — 小欧 2026-09-19"""
    if getattr(sys, "frozen", False):
        # 业务源码以源码树拷入_internal/app, 需入sys.path才能按普通源码导入 — 小欧 2026-09-19
        sys.path.insert(0, sys._MEIPASS)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


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
    parser.add_argument("--port", type=int, default=8000)
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
    _ensure_config(base)

    import app.main  # noqa: F401 — 供PyInstaller静态收集业务第三方依赖, 运行期仍由uvicorn按名加载
    # 小欧 - 2026-09-27：把 forwarded_allow_ips 注入应用层。
    #   应用层原先自己读 FORWARDED_ALLOW_IPS 环境变量，与 uvicorn 各读一次可能不一致
    #   （命令行启动时应用层读不到、只看到默认值）。改为同源注入，两边不可能分叉，
    #   并顺带修掉"命令行传 * 时应用层检测不到、fail-closed 失效"的盲区。
    from app.api.v1.deps import set_forwarded_allow_ips
    set_forwarded_allow_ips(args.forwarded_allow_ips)
    import uvicorn
    uvicorn.run("app.main:app", host=args.host, port=args.port, log_level="info",
                forwarded_allow_ips=args.forwarded_allow_ips)


if __name__ == "__main__":
    main()
