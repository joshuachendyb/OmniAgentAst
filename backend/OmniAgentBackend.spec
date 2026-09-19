# -*- mode: python ; coding: utf-8 -*-
# ============================================================================
# OmniAgentAst 后端 exe 打包 spec(onedir, 带控制台) — 小欧 2026-09-19(北京老陈驱动)
# 构建: cd backend; E:\Appsw\python31311\Scripts\pyinstaller.exe OmniAgentBackend.spec
# 构建后收尾(必需, onedir禁止datas目标".."只能拷):
#   copy ..\version.txt dist\OmniAgentBackend\
#   copy config.yaml.example dist\OmniAgentBackend\
# 产物: backend/dist/OmniAgentBackend/OmniAgentBackend.exe(绿色目录, 拷走即用)
#   exe旁自带: version.txt / config.yaml.example / config/ / logs(运行生成)
# 注意: playwright浏览器需用户机另装(playwright install chromium);
#   tesseract/pycorrector模型等外部依赖行为与源码运行一致, 不随包走。
# ============================================================================
import sys
from pathlib import Path

BACKEND = Path(SPECPATH)
REPO = BACKEND.parent

# app/系命名空间包(无__init__.py), collect_all/modulegraph收不全 →
# 业务源码整树以源码形式拷入_internal/app, 由launcher置sys.path后按普通源码导入 — 小欧 2026-09-19
app_tree = Tree(
    str(BACKEND / "app"),
    prefix="app",
    excludes=["__pycache__", "*.pyc"],
)

a = Analysis(
    [str(BACKEND / "run_server.py")],
    pathex=[str(BACKEND)],
    binaries=[],
    datas=[
        (str(REPO / "version.txt"), "."),
        (str(BACKEND / "config.yaml.example"), "."),
    ],
    hiddenimports=[
        "aiosqlite",
        "sqlalchemy.dialects.sqlite.aiosqlite",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.http.httptools_impl",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.websockets_impl",
        "uvicorn.protocols.websockets.wsproto_impl",
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",
        "jinja2",
        "platformdirs",  # setuptools/pkg_resources运行时rthook依赖(构建机原缺失已补装) — 小欧 2026-09-19
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="OmniAgentBackend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    app_tree,  # 业务源码树(含模板)拷入_internal/app — 小欧 2026-09-19
    strip=False,
    upx=False,
    upx_exclude=[],
    name="OmniAgentBackend",
)
