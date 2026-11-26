# -*- mode: python ; coding: utf-8 -*-
# ============================================================================
# OmniAgentAst 后端 exe 打包 spec(onedir, 无控制台) — 小欧 2026-10-24
# 构建: cd backend; E:\Appsw\python31311\Scripts\pyinstaller.exe OmniAgentBackend.spec
# 产物: backend/dist/OmniAgentBackend/OmniAgentBackend.exe + _internal/(onedir 绿色目录, 拷走即用)
#   说明: version.txt/config.yaml.example/OmniAgent.md 经 datas "." 目标进 _internal/ 根部,
#   exe 启动时 _deploy_resources() 自动复制到 exe 同级; 拷走前无需手动补任何根文件 — 小欧 2026-11-04(删多余收尾说明)
# 注意: playwright浏览器需用户机另装(playwright install chromium);
#   tesseract/pycorrector模型等外部依赖行为与源码运行一致, 不随包走。
#   无控制台模式: 日志落 dist/OmniAgentBackend/logs/app_YYYY-MM-DD.log, 可通过该文件查日志。
# 编辑历史:
#   2026-11-04 小欧 - 打包后处理增加"用户使用说明"环节: doc-打包与E2E 下最新一份
#     OmniAgent智能助手(SPA版)使用说明*.md 复制为 dist 根 OmniAgent使用说明.md(exe 同级)
#   2026-11-06 小欧 - 前端收集改逐文件并排除 stats.html(dist 缺失硬报错): stats.html 为
#     rollup-plugin-visualizer 诊断产物(2.4MB)不进生产包; 多 index-*.js 经实测为懒加载 chunk 属必要保留。
#   2026-11-07 小欧 - 修复 datas 目标路径: PyInstaller datas 第二参数是目标目录非文件路径,
#     原 web/index.html 被当目录→创建 web/index.html/index.html(嵌套一层, 前端白屏);
#     改 .parent 取目标目录, 文件名由 PyInstaller 自动保持 — 小欧-2026-11-07
#   2026-11-18 小欧 - 修复 hook 收集绕过 spec 瘦身过滤: contrib hook-pyarrow.py 用
#     collect_data_files('pyarrow') 全量收集, 把 tests/、include/arrow/testing 及零散 test_*.h
#     等 57 个测试文件带入产物(spec _datas 过滤管不到 hook datas); matplotlib 内置 hook 整目录
#     收集 mpl-data 带入 _classic_test_patch.mplstyle(测试样式)。新增 backend/pyinstaller_hooks/
#     自定义 hook-pyarrow.py + hook-matplotlib.py 经 hookspath 覆盖(USER_HOOKS 优先级最高),
#     用 excludes 精确排除测试套件, 产物 pyarrow 测试 57→0、matplotlib 测试样式 1→0 — 小欧-2026-11-18
#   2026-11-23 opencode - 排除构建机环境自带 ML 包(datasets/torch/transformers/spacy 及其链):
#     app/ 生产代码零引用, contrib hooks 只要发现环境装了就整包收进产物(~480MB 死重量);
#     显式 excludes 后即使构建机装了也不进包
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
             "pyperclip", "pptx", "win10toast",
             # JS/TS 语法校验 — 小欧 2026-10-12: 含 native .pyd, 不显式收集则打包版 ImportError
             #   (syntax_validator 已做软降级, 但主路径 tree-sitter 会整体失效只剩 node 兜底)
             "tree_sitter", "tree_sitter_javascript", "tree_sitter_typescript"):
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

# 打包瘦身: 排除第三方库自带的测试套件/测试数据(纯冗余, 只增大包体积) — 小欧 2026-11-18
#   collect_all 整包收集会把 pandas/pyarrow 等库的 tests 目录一并带入, 运行时不会被 import。
#   关键: 必须基于【源文件完整路径 d[0]】判断(含文件名), 而非目标目录 d[1](不含文件名)!
#   首版误用 d[1] 导致 _TEST_DATA_FILES 全部失配、pyarrow testing/ 目录段与零散 test 文件漏网。
#   注意: 不能按文件名含 "test" 简单过滤 —— numpy/_multiarray_tests.pyd、pandas/_libs/testing.pyd、
#   pandas/testing.py、pandas/_testing/ 等是真实运行模块(名字带 test 但业务依赖), 必须保留。
_TEST_FILE_NAMES = {
    # matplotlib 测试样式
    "_classic_test_patch.mplstyle",
    # tcl8 测试库
    "tcltest-2.5.8.tm",
    # reportlab 测试字体/脚本
    "hb-test.ttf", "test.py", "testdrawings.py", "testshapes.py", "testutils.py",
    # pandas pytest 配置与 util 测试辅助
    "conftest.py", "_test_decorators.py", "_tester.py",
}

def _is_test_artifact(src: str, dest: str) -> bool:
    s = src.replace("\\", "/")
    s_parts = s.split("/")
    # 1. 源路径含标准测试目录段(tests / testing): 覆盖 pandas/tests, pyarrow/tests,
    #    pyarrow/include/arrow/testing, h11/tests 等。注意不含 pandas/_testing(单下划线=运行依赖)。
    if "tests" in s_parts or "testing" in s_parts:
        return True
    fname = s_parts[-1]
    # 2. C++/Cython 测试源码(头文件/源文件, 绝无运行依赖): 覆盖 pyarrow test_*.h/*_test.h/python_test.cc 等
    if fname.endswith((".h", ".cc", ".pxd", ".pyx")) and "test" in fname.lower():
        return True
    # 3. 明确的零散测试数据/脚本文件
    if fname in _TEST_FILE_NAMES:
        return True
    return False

_before = len(_datas)
_datas = [d for d in _datas if not _is_test_artifact(d[0], d[1])]
print(f"[spec] 打包瘦身: 排除第三方测试文件 {_before - len(_datas)} 个 (剩余 {len(_datas)} 个数据项)")
_pyarrow_test_after = [d for d in _datas if "pyarrow" in d[0].replace("\\", "/").lower() and ("test" in d[0].replace("\\", "/").lower() or "testing" in d[0].replace("\\", "/").lower())]
print(f"[spec] 调试: 过滤后 _datas 仍含 pyarrow 测试 {len(_pyarrow_test_after)} 个")

# app/系命名空间包(无__init__.py), collect_all/modulegraph收不全 →
# 业务源码整树以源码形式拷入_internal/app, 由launcher置sys.path后按普通源码导入 — 小欧 2026-09-19
app_tree = Tree(
    str(BACKEND / "app"),
    prefix="app",
    excludes=["__pycache__", "*.pyc"],
)

# 前端 dist → _internal/web/（双击exe完整应用）— 小欧 2026-10-27
# 需先 npm run build 生成 frontend/dist/，否则打包直接报错(防"静默无前端包");
#   挂载判据在 main.py(_STATIC_MOUNTED/_missing_web): 打包态缺 assets/index.html 启动即 error 喊出, 开发态没 dist 静默 API-only — 小欧 2026-11-01
# 2026-11-06 小欧 - 逐文件收集 dist(排除 stats.html): stats.html 是 rollup-plugin-visualizer 诊断产物,
#   不进生产包(2.4MB 纯冗余); 多 index-*.js 为懒加载 chunk 属必要, 一并收集。
_frontend_dist = REPO / "frontend" / "dist"
if not _frontend_dist.is_dir():
    raise SystemExit(f"[spec] 前端构建产物缺失: {_frontend_dist} —— 请先 npm run build (或走 build_spa.ps1) 再打包")
_frontend_datas = []
for _f in _frontend_dist.rglob("*"):
    if _f.is_file() and _f.name != "stats.html":
        _frontend_datas.append((str(_f), str(Path("web") / _f.relative_to(_frontend_dist).parent)))

a = Analysis(
    [str(BACKEND / "run_server.py")],
    pathex=[str(BACKEND)],
    binaries=_binaries,
    datas=[
        (str(REPO / "version.txt"), "."),
        (str(BACKEND / "config.yaml.example"), "."),
        (str(REPO / "OmniAgent.md"), "."),  # 项目规则文件 — 小欧 2026-10-24
    ] + _frontend_datas + _datas,
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
        "app.proc",          # 进程宿主([65] E1): 独立进程包, 由 --proc-host/-m 动态拉起 — 小欧 2026-11-26
        "app.proc.host",
        "app.proc.client",
        "app.proc.win_job_object",  # 宿主 Job 收编(动态 import, modulegraph 收不全) — 小欧 2026-11-26
    ] + _hiddenimports,
    # pyarrow 测试套件瘦身: 自定义 hook-pyarrow.py 覆盖 contrib 原版(collect_data_files 全量收集
    #   会把 tests/、include/arrow/testing 及零散 test_*.h 一并带入), 经 excludes 精确排除 —
    #   小欧 2026-11-18. 优先级 USER_HOOKS(1000) > CONTRIBUTED(-1000), 完整覆盖不污染第三方库。
    hookspath=[str(BACKEND / "pyinstaller_hooks")],
    hooksconfig={},
    runtime_hooks=[],
    # 注意: 不可全局排除 pkg_resources —— win10toast 运行时真实依赖它;
    #   构建机原缺 jaraco.text/jaraco.functools 导致 pyi_rth_pkgres 钩子启动即崩,
    #   已于构建机补装该依赖而非排除包 — 小欧 2026-10-11
    # ML 包排除: 构建机装了 datasets/torch/transformers/spacy, contrib hook 会整包收进产物,
    #   但 app/ 生产代码零引用, 属纯死重量(实测 ~480MB) — opencode 2026-11-23
    excludes=[
        "datasets", "torch", "torchvision", "torchaudio",
        "transformers", "spacy", "blis", "thinc",
        "tokenizers", "sentencepiece", "hf_xet", "huggingface_hub",
    ],
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

# 打包后处理: 用户使用说明放到 exe 同级, 包内固定名 OmniAgent使用说明.md — 小欧-2026-11-04
# 源文档 doc-打包与E2E/OmniAgent智能助手(SPA版)使用说明-<签名>-<日期>.md, 取最新一份, 改名固定不带日期:
#   升级覆盖同名文件, 部署目录不积累历史版本; 文档缺失只告警不阻断打包。
import shutil as _shutil

_doc_dir = REPO / "doc-打包与E2E"
_docs = sorted(_doc_dir.glob("OmniAgent智能助手(SPA版)使用说明*.md"), key=lambda p: p.stat().st_mtime)
if _docs:
    _doc_dst = Path(DISTPATH) / "OmniAgentBackend" / "OmniAgent使用说明.md"
    _shutil.copy2(_docs[-1], _doc_dst)
    print(f"[post-build] 使用说明 -> {_doc_dst}  (源 {_docs[-1].name})")
else:
    print(f"[post-build] 警告: {_doc_dir} 下未找到使用说明, 包内不含 OmniAgent使用说明.md")
