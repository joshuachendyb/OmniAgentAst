# ============================================================================
# exe打包启动入口 — PyInstaller Analysis 入口, uvicorn 编程式启动(无--reload)
# 创建: 2026-09-19 小欧 - 后端打包exe(北京老陈驱动)
# 用法: run_server.exe [--host 127.0.0.1] [--port 8000]
#   程序自身资源(version.txt/config/config.yaml/logs/)定位exe所在目录,
#   首次启动若 config/config.yaml 缺失则由 config.yaml.example 复制生成。
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
    args = parser.parse_args()

    base = _exe_dir()
    _ensure_config(base)

    import app.main  # noqa: F401 — 供PyInstaller静态收集业务第三方依赖, 运行期仍由uvicorn按名加载
    import uvicorn
    uvicorn.run("app.main:app", host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
