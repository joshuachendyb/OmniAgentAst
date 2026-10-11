# -*- mode: python ; coding: utf-8 -*-
# ============================================================================
# OmniAgentAst 后端 exe 打包 spec(onedir, 带控制台) — 小欧 2026-09-19(北京老陈驱动)
# 构建: cd backend; E:\Appsw\python31311\Scripts\pyinstaller.exe OmniAgentBackend.spec
# 构建后收尾(必需, onedir禁止datas目标".."只能拷):
#   copy ..\version.txt dist\OmniAgentBackend\
#   copy config.yaml.example dist\OmniAgentBackend\
#   copy ..\OmniAgent.md dist\OmniAgentBackend\   # 项目规则文件; 缺失时运行期会自动建空文件
# 产物: backend/dist/OmniAgentBackend/OmniAgentBackend.exe(绿色目录, 拷走即用)
#   exe旁自带: version.txt / config.yaml.example / config/ / logs(运行生成)
# 注意: playwright浏览器需用户机另装(playwright install chromium);
#   tesseract/pycorrector模型等外部依赖行为与源码运行一致, 不随包走。
# ============================================================================
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

BACKEND = Path(SPECPATH)
REPO = BACKEND.parent

# app/tools/registry.py 用变量式__import__动态加载分类模块, modulegraph静态分析收不全 →
# 工具独占依赖必须显式整包收集, 否则打包版启动只注册部分分类(实测7/9, 缺network/document) — 小欧 2026-10-11
_datas, _binaries, _hiddenimports = [], [], []
for _pkg in ("html2text", "reportlab", "openpyxl", "docx", "fitz", "pdfplumber", "pandas", "psutil",
             "pywin32", "win32gui", "pythoncom", "pywintypes", "pyautogui", "mss",
             "pyperclip", "pptx", "win10toast"):
    try:
        _d, _b, _h = collect_all(_pkg)
        _datas += _d
        _binaries += _b
        _hiddenimports += _h
    except Exception:  # 构建机未安装的包跳过, 不阻断打包
        pass

# 懒加载导入的模块静态分析扫不到(httpx/httpcore 在 LLM 服务内函数内 import), 必须显式收子模块
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
for _pkg in ("httpx", "httpcore", "anyio", "h11", "certifi", "sniffio", "idna", "win10toast"):
    try:
        _hiddenimports += collect_submodules(_pkg)
        _datas += collect_data_files(_pkg)
    except Exception:
        pass

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
    binaries=_binaries,
    datas=[
        (str(REPO / "version.txt"), "."),
        (str(BACKEND / "config.yaml.example"), "."),
    ] + _datas,
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
    ] + _hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 注意: 不可全局排除 pkg_resources —— win10toast 运行时真实依赖它;
    #   构建机原缺 jaraco.text/jaraco.functools 导致 pyi_rth_pkgres 钩子启动即崩,
    #   已于构建机补装该依赖而非排除包 — 小欧 2026-10-11
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
