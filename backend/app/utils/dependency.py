# -*- coding: utf-8 -*-
"""
依赖自动安装工具 — 统一处理运行时Python依赖

【公用函数规范】
本文件是公共utility模块，所有依赖安装公共函数必须在此定义。
禁止在业务代码中重复实现依赖安装逻辑。

【小欧 2026-06-16】新增：DRY原则从gui_tools.py send_notification抽取
【小健 2026-06-18】增强：支持版本控制和前置依赖，集成到工具注册系统
【小欧 2026-10-11】新增：打包版(frozen)短路：
  exe 里 sys.executable 是自身，调 pip 必被自家 argparse 拦下刷屏；且即便装上 frozen
  进程也看不见（只认 _MEIPASS）。缺失时直接返回 False 并给可操作提示，不调 pip。
【小欧 2026-10-19】新增：锁定包护栏（LOCKED_PACKAGES + pip 约束文件，防传递依赖把锁定包
  顺带抬升）+ 启动期批量装（install_batch，免逐个依赖一次 subprocess）+ 注册期退化为纯检查。
【小欧 2026-10-19】修正：ensure_dependency 原把"检查"与"安装"混在一处，批量预装因此空转
  （判缺失那一步自己就把包单装掉了，N 个依赖仍起 N 次 pip）。现拆出 dependency_status(纯检查,
  零 subprocess) 与 install_missing(唯一装包入口, 启动期与运行期自愈共用)。
  另新增 normalize_dep: 依赖声明 str/dict 两种写法归一，import 名与 pip 名不得混用
  （pip 名 python-docx 不可 import，import 名 docx 装不上，混用必判缺库）。
【小欧 2026-10-19】边界修正 5 处（均由用例探测得出，每项三重复核）：
  ① normalize_dep 回落 pip_package 仅当其可作模块名（isidentifier）——含 '-' 的 pip 名
     回落必恒判缺库；② install_missing 补装 pre_install，原直接丢弃该字段（ensure_dependency
     认它而本函数不认，同一份声明两条路两种行为）；③ install_batch 整批失败后逐个降级重试，
     原先一个非法包名会让同批本来没问题的包一起失去安装机会；④ dependency_status 对非 "=="
     版本约束显式告警不生效——声明了却从不校验比不声明更危险；⑤ 新增 _PIP_LOCK 全局串行，
     pip 无跨进程锁，并发装包会同时写同一 site-packages（实测并发峰值曾达 3）。

===============================================================================
                         依赖管理系统使用指南
===============================================================================

1. 核心函数：ensure_dependency()
   用于检查并自动安装Python依赖包，支持版本控制和前置依赖。

   参数：
   - import_name: import时的模块名（如 'win10toast'）
   - pip_package: pip包名，默认等于import_name
   - version: 版本号，如 '==0.26.0'，可选
   - pre_install: 前置依赖列表（如 ['setuptools<70']），先于主包安装

   返回值：bool - True=依赖已可用，False=安装失败

   示例：
   ```
   # 简单依赖
   ensure_dependency("pandas")
   
   # 带版本号
   ensure_dependency("httpx", version="==0.26.0")
   
   # 带前置依赖
   ensure_dependency("win10toast", pre_install=["setuptools<70"])
   
   # 完整参数
   ensure_dependency(
       import_name="matplotlib", 
       pip_package="matplotlib",
       version=">=3.5.0",
       pre_install=["numpy"]
   )
   ```

2. 工具注册集成
   在工具注册文件中定义 TOOL_DEPENDENCIES 常量，支持两种格式：

   格式1：简单字符串（无版本限制）
   ```
   TOOL_DEPENDENCIES = {
       "analyze_data": ["pandas"],
       "filter_data": ["pandas"],
   }
   ```

   格式2：带版本号字符串
   ```
   TOOL_DEPENDENCIES = {
       "httpget": ["httpx==0.26.0", "httpcore==1.0.1"],
   }
   ```

   格式3：字典格式（完整参数）
   ```
   TOOL_DEPENDENCIES = {
        "notify": [
            {"import_name": "win10toast", "pip_package": "win10toast", "pre_install": ["setuptools<70"]}
        ],
   }
   ```

3. 注册时自动检查
   工具注册时会自动检查并安装所有依赖：
   ```
   tool_registry.register(
       name=name,
       description=desc,
       category=ToolCategory.DATAANALYSIS,
       implementation=func,
       dependencies=TOOL_DEPENDENCIES.get(name, []),  # 自动依赖检查
   )
   ```

4. 注意事项
   - 依赖检查在工具注册时进行，不在运行时
   - 安装失败会记录警告，但不阻止工具注册
   - 工具函数内部仍需进行运行时检查（使用 _check_module）
   - 版本锁定示例：httpx必须使用0.26.0版本（AGENTS.md要求）
"""

import importlib.metadata
import os
import subprocess
import sys
import tempfile
import threading
from typing import Dict, Iterable, List, Optional

from app.logger import logger  # 小欧 2026-10-11: frozen 短路分支需记可操作提示日志

#: 铁律锁定包：版本一旦被传递依赖顺带抬升即破坏上层协议（TLS 等），任何装包动作都不得改动它们。
#: 单一真源 —— 装包时据此生成 pip 约束文件，装不上就报缺库，绝不静默换版本。
LOCKED_PACKAGES: Dict[str, str] = {
    "httpx": "0.26.0",       # 0.28+ 抬升 httpcore 破 TLS
    "httpcore": "1.0.1",
}

_CONSTRAINTS_PATH: Optional[str] = None
#: pip 全局串行锁: pip 自身无跨进程锁, 并发装包会同时写同一 site-packages。
#: 2026-10-19 小欧 - 实测3个工具并发缺库可同时起3个pip。所有 pip 调用点共用这一把。
_PIP_LOCK = threading.Lock()


def _constraints_file() -> str:
    """把 LOCKED_PACKAGES 落成 pip 约束文件路径（首次调用时生成）。

    约束文件随每次 pip 调用以 -c 带上：装任意新包时，其传递依赖若想把 httpx/httpcore
    抬到别的版本，pip 直接判冲突报错，而不是把锁定版本静默换掉。
    """
    global _CONSTRAINTS_PATH
    if _CONSTRAINTS_PATH and os.path.exists(_CONSTRAINTS_PATH):
        return _CONSTRAINTS_PATH
    fd, path = tempfile.mkstemp(prefix="omniagent_locked_", suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for _pkg, _ver in LOCKED_PACKAGES.items():
            f.write(f"{_pkg}=={_ver}\n")
    _CONSTRAINTS_PATH = path
    return path


def locked_conflict(pkg: Optional[str], version: Optional[str] = None) -> bool:
    """该安装请求是否会顶掉锁定包 —— True=冲突，须拒绝。

    裸装（version=None）等同于"装最新版"，对锁定包一律判冲突；
    带版本且与锁定值相同才放行（如 httpx==0.26.0）。
    """
    locked = LOCKED_PACKAGES.get(pkg or "")
    if locked is None:
        return False
    if version is None:
        return True
    return version.lstrip("=").strip() != locked


def normalize_dep(dep) -> tuple:
    """把依赖声明归一成 (import_name, pip_package, version, pre_install)。

    两种写法归到同一形状:
        'httpx==0.26.0'
        {'import_name': 'docx', 'pip_package': 'python-docx'}

    import_name 与 pip_package 不可混用: 判可用靠 __import__(import_name),
    装包靠 pip install (pip_package)。混用必错 —— pip 名 'python-docx' 不可 import,
    import 名 'docx' 装不上。形状不合法时 import_name 返回 None, 由调用方记格式错误。

    2026-10-19 小欧 - 此前 registry 三处各写一遍扁平化, 且批量预检那处把 dict 压成 pip 名
    再拿去 import, 导致 python-docx/python-pptx/pywin32 恒判缺库。归一收口于此。
    """
    if isinstance(dep, str):
        s = dep.strip()
        if not s:
            return None, None, None, None
        if "==" in s:
            parts = s.split("==")
            if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
                return None, None, None, None
            return parts[0].strip(), parts[0].strip(), "==" + parts[1].strip(), None
        return s, s, None, None
    if isinstance(dep, dict):
        pkg = (dep.get("pip_package") or "").strip()
        imp = (dep.get("import_name") or "").strip() or pkg
        # 未显式给 import_name 时回落 pip_package, 但仅当它本身可作模块名:
        # pip 名含 '-'/'.' 时不可 import(如 python-docx 的模块名是 docx), 回落必然恒判缺库。
        if imp and not imp.isidentifier():
            logger.error(f"[依赖] 依赖声明缺 import_name 且 pip_package 不可作模块名: {dep}")
            return None, None, None, None
        if not imp:
            return None, None, None, None
        return imp, (pkg or imp), dep.get("version"), dep.get("pre_install")
    return None, None, None, None


def dep_install_spec(imp: str, pkg: str, version: Optional[str]) -> str:
    """依赖的可读 pip 规格串, 供日志与缺库提示指名"该装什么"。"""
    return f"{pkg or imp}{version or ''}"


def _pip_install(pkg: str, version: Optional[str] = None) -> bool:
    """尝试pip安装，先普通模式失败后自动降级为--user

    Args:
        pkg: 包名，如 'httpx'
        version: 版本号，如 '==0.26.0'，可选
    """
    install_cmd = [sys.executable, "-m", "pip", "install", "-q",
                   "-c", _constraints_file()]
    if version:
        pkg_with_version = f"{pkg}{version}"
    else:
        pkg_with_version = pkg

    # 2026-10-19 小欧 - 锁定包护栏: 裸装锁定包=装最新版, 会顶掉铁律版本; 带错版本同样顶掉。
    #   此处拒绝而非让 pip 自行仲裁, 保证"锁被顶"是不可见的失败变成可见的拒绝。
    if locked_conflict(pkg, version):
        locked = LOCKED_PACKAGES.get(pkg)
        logger.error(
            f"[依赖] 拒绝安装锁定包 '{pkg}{version or ''}'：锁定版本 {locked}，"
            f"装别的版本会破坏既有协议。缺该依赖时请改用已锁定版本。"
        )
        return False

    # 2026-10-19 小欧 - 全局串行: pip 无跨进程锁, 两个装包同时跑会并发写同一 site-packages
    #   (实测3个工具并发缺库可同时起3个pip)。锁在**所有** pip 调用点(_pip_install 与 install_batch)
    #   共用一把, 免得只在批量侧加锁而单包侧仍可并发。
    with _PIP_LOCK:
        try:
            subprocess.check_call(install_cmd + [pkg_with_version])
            return True
        except subprocess.CalledProcessError:
            try:
                subprocess.check_call(install_cmd + ["--user", pkg_with_version])
                return True
            except subprocess.CalledProcessError:
                return False


def install_batch(packages: Iterable[str]) -> None:
    """一次 pip 调用装多个包（启动期批量），免 N 个依赖起 N 次 subprocess。

    调用方先用 dependency_status 判出缺失再传入；锁定包护栏仍由 _pip_install 逐个把关。
    整批失败时**逐个降级重试**并回报仍失败的包 —— 否则一个非法包名/版本冲突会让整批 pip 拒绝，
    连同批里本来没问题的包一起失去安装机会(实测如此)。
    """
    pkgs = [p for p in dict.fromkeys(packages) if p]
    if not pkgs:
        return
    if getattr(sys, "frozen", False):
        logger.warning(f"[依赖] 打包版(exe)不支持运行时批量装({len(pkgs)} 个): {', '.join(pkgs[:8])}")
        return
    cmd = [sys.executable, "-m", "pip", "install", "-q", "-c", _constraints_file()] + pkgs
    with _PIP_LOCK:
        try:
            subprocess.check_call(cmd)
            return
        except subprocess.CalledProcessError:
            pass
    logger.warning(f"[依赖] 批量安装失败({len(pkgs)} 包), 逐个重试以定位问题包")
    for pkg in pkgs:
        base = pkg.split("==")[0]
        ver = ("==" + pkg.split("==")[1]) if "==" in pkg else None
        if not _pip_install(base, ver):
            logger.error(f"[依赖] 单包安装仍失败: {pkg}")


def dependency_status(
    import_name: str,
    pip_package: Optional[str] = None,
    version: Optional[str] = None,
) -> bool:
    """纯检查依赖是否可用 —— 绝不发起任何 subprocess(零安装)。

    2026-10-19 小欧 - 从 ensure_dependency 拆出。原先"检查"与"安装"混在一个函数里,
      批量预装因此失效: 判定缺失的那一步自己就把包单装掉了, 批量装只接手失败残兵,
      N 个依赖仍起 N 次 pip(实测 3 个缺失 = 3 次单装 + 1 次批量, 比不批量更差)。
      批量化要生效, 必须先有一个"只看不装"的判定源。

    版本核对在 frozen 下跳过: 打包时版本已由构建机锁定并随包落地, 而
    importlib.metadata.version() 在 frozen 里读不到 dist-info, 必然抛 PackageNotFoundError
    被误判成"依赖缺失"(实测 httpx==0.26.0 已正确打进包却被判失败)。非 frozen 行为不变。
    """
    if not import_name:
        return False
    try:
        __import__(import_name)
    except ImportError:
        return False

    # 2026-10-19 小欧 - 非 "==" 形式的约束(>=3.0 / <2.0 / ~=1.2)本函数不参与判定, 必须显式告警:
    #   声明了却从不校验, 等于没声明, 且比不声明更危险(以为有版本把关)。此处只告警不实现
    #   完整约束解析 —— 全仓现无一处使用这类写法(YAGNI), 真正需要时再按 packaging 补。
    if version and not version.startswith("=="):
        logger.warning(
            f"[依赖] 版本约束 '{version}' ({pip_package or import_name}) 不被校验: "
            f"本模块只支持 '==精确版本', 该约束当前不生效。"
        )

    if version and version.startswith("==") and not getattr(sys, "frozen", False):
        try:
            installed = importlib.metadata.version(pip_package or import_name)
        except importlib.metadata.PackageNotFoundError:
            logger.warning(f"[依赖] {pip_package or import_name} 版本不可查")
            return False
        if installed != version[2:]:
            # 版本只取一次存局部: 原写成 f-string 里再调一次 version(), 而 PackageNotFoundError
            # 会在日志格式化阶段抛出(记不成日志, 反把判定打断)。
            logger.warning(
                f"[依赖] 版本不匹配: {pip_package or import_name} 已装 {installed}, 声明要求 {version}"
            )
            return False
    return True


def resolve_missing(deps: Iterable[tuple]) -> List[tuple]:
    """从归一依赖元组里筛出不可用的(纯检查, 零 subprocess) —— 单一判定源。

    元组形状 (import_name, pip_package, version, pre_install), 由 normalize_dep 产出。
    """
    return [d for d in deps if not dependency_status(d[0], d[1], d[2])]


def install_missing(deps: Iterable[tuple]) -> List[tuple]:
    """批量装齐 deps 中缺失的, 返回仍不可用的 —— **唯一装包入口**。

    2026-10-19 小欧 - 先纯检查、再一次 pip 装全部缺失、最后复检。
    启动期预装与运行期自愈都走本函数(DRY), 两处各写一遍判定逻辑正是上次假修复的温床。
    锁定包不进批量装: 由 _pip_install 护栏逐个判, 免得批量把铁律版本顶掉。
    pre_install(如 setuptools<70)必须先单独装: 它是约束/构建前置, 与主包同批装不保证先后,
      原实现直接丢弃该字段 —— ensure_dependency 认它而本函数不认, 同一份声明两条路两种行为。
    """
    items = list(deps)
    missing = resolve_missing(items)
    if not missing:
        return []
    for pre in dict.fromkeys(p for d in missing for p in (d[3] or [])):
        logger.info(f"[依赖] 安装前置依赖: {pre}")
        _pip_install(pre)
    specs = [dep_install_spec(*d[:3]) for d in missing]
    logger.info(f"[依赖] 缺失 {len(missing)}/{len(items)} 个: {', '.join(specs)}")
    install_batch([s for s, d in zip(specs, missing) if d[1] not in LOCKED_PACKAGES])
    still = resolve_missing(missing)
    if still:
        logger.warning(f"[依赖] 装后仍缺: {', '.join(dep_install_spec(*d[:3]) for d in still)}")
    return still


def ensure_dependency(
    import_name: str,
    pip_package: Optional[str] = None,
    version: Optional[str] = None,
    pre_install: Optional[list] = None,
) -> bool:
    """确保Python依赖可用，缺失则自动pip安装（普通→--user两级降级）

    Args:
        import_name: import时的模块名（如 'win10toast'）
        pip_package: pip包名，默认等于import_name
        version: 版本号，如 '==0.26.0'，可选
        pre_install: 前置依赖列表（如 ['setuptools<70']），先于主包安装

    Returns:
        bool: True=依赖已可用，False=安装失败

    2026-10-19 小欧 - 判定部分已抽为 dependency_status(纯检查); 本函数保留"缺就装"的
      旧语义供既有调用方使用。要批量化请走 install_missing, 别再逐个调本函数。
    """
    if pip_package is None:
        pip_package = import_name

    if dependency_status(import_name, pip_package, version):
        return True

    if pre_install:
        for pkg in pre_install:
            _pip_install(pkg)

    # 2026-10-11 小欧 - 打包版短路: frozen 下 sys.executable 是 exe 自身,
    #   调 pip 会被自家 argparse 以 unrecognized arguments 打回刷屏；且即便装上 frozen
    #   进程也看不见(只认 _MEIPASS)。直接返回 False，并给出可操作提示（要加包重打）。
    if getattr(sys, "frozen", False):
        logger.warning(
            f"[依赖] 打包版(exe)缺失依赖 '{pip_package}'：不支持运行时 pip 安装，已跳过。"
            f"需要该功能请重打包含该依赖的版本；或改用源码运行并执行 `pip install {pip_package}`。"
        )
        return False
    if not _pip_install(pip_package, version):
        return False
    return dependency_status(import_name, pip_package, version)

