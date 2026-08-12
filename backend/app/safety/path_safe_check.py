
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-18 - 小欧 - #3 fix: 白名单盘符下增加系统保护目录拒绝(windows/program files/programdata等),
#    用 Path.parts[1] 精确只查盘符后第一级, 避免 C:\Users\MyProject\Program Files 误杀
# 2026-08-02 - 小欧 - 加固: _is_forbidden_path 新增磁盘根目录黑名单(C:\), 防止白名单盘符机制放行盘根删除
# 2026-08-04 - 小欧 - 盘符动态化(北京老陈驱动): 新增 get_existing_drives(当前磁盘符号列表)/get_system_drive(真实系统盘符)/_get_project_root_safety(项目根上移Safety层,恒非None);
#    _is_forbidden_path 系统目录 C: 模板运行时动态替换真实系统盘符(不漏判不误伤); get_default_allowed_paths 盘符枚举 A-J 上限改动态(get_existing_drives) — 设计文档 v1.15
# 2026-08-10 - 小欧 - 步骤1实施(⑤⑦⑧⑨⑪, 北京老陈驱动「项目根=tool工作区, 代码库根=tool禁区」): ⑤get_project_root_safety收敛走config(兜底用户主目录); ⑦代码库根_unsafe_get_code_root_roots为禁区(含父子级); ⑧工具路径参数名补dest列表; ⑨validate_tool_path遍历所有命中参数逐一校验; ⑪废除「所有现存盘符」全盘放开, 白名单=主目录+tmp+项目根+授权目录(动态懒加载)
# 2026-08-10 - 小欧 - BUG-B/C修复: 新增 _resolve_path_param 逻辑路径参数解析(download.dest=相对下载目录/rename.dest=仅文件名→真实文件系统路径),
#    validate_tool_path 校验前先解析, 消除"相对/文件名语义被当绝对路径校验→resolve到cwd→误判代码库禁区拦截"(download/rename完全不可用);
#    validate_tool_path 返回扩展为三元组 (is_valid, msg, failed_path), failed_path=首个校验失败的真实路径, 供临时授权定位真正越权参数(BUG-D修复) — 小欧 2026-08-10
# 2026-08-10 - 小欧 - P3 缺陷修复(三堂会审复核发现, 第二次代码更新): _SYSTEM_PROTECTED 系统保护目录(windows/program files等)
#   写/删 返回 category 由 None → "system" — _is_forbidden_path 仅精确锁 WIN_EXACT 本身(C:\Windows), 其子路径漏过禁区判定,
#   旧返回 None 使 T2 当"白名单外可临时授权"处理(系统目录可被授权写入, 违表五「系统禁区写❌硬拦永不授权」); 读 mode 放行(与禁区读一致, 3.2.9)
# 2026-08-10 - 小欧 - 三堂会审 BUG-1/BUG-3 修复(v1.45): 
#   BUG-1: validate_tool_path 原 `tool_name not in path_tools` 用 LLM 原始名判归属, 别名工具(list_directory/read_text_file等)
#     不在注册名集合 → 直接 return True 放行, 绕过全部路径校验; 改归一化名 normal_name 判(与 mode 推断同源, P2 防别名漏检补齐)
#   BUG-3: 原 hit_params 直接查原始 params, PARAM_ALIASES 参数别名(rename.new_name→dest/copy.src→path/dst→dest等)
#     命中不了 _PATH_PARAM_KEYS → 该参数路径越权漏检; 校验前先 normalize_params 归一化(校验对象与工具实际落盘路径一致)
#   _resolve_path_param 同步改用归一化名+归一化 params(download/rename 相对语义解析不受别名影响) — 小欧 2026-08-10
# 2026-08-10 - 小欧 - T2 回归修复(三堂会审+回归测试复核发现, v1.45): 空路径/路径穿越返回 category 由 None → "system" —
#   validate_path 对空路径/穿越返回 (False, msg, None), T2 将 category=None 一律当"白名单外非禁区→可授权请求",
#   使空路径/穿越从 blocked 退化为可授权(违"无效/恶意路径应硬拦"); 归入 system 后 T2 硬拦永不授权,
#   与 test_bug_empty_path_not_validated / test_f5_03_path_traversal_blocked 断言对齐 — 小欧 2026-08-10
# 2026-08-11 - 小欧 - fix D1: validate_path 末段except分支 category=None→"system"(永不授权硬拦),
#   原category=None→T2当"白名单外非禁区→可授权请求"→异常/恶意路径可被grant_temp_auth放行(安全漏洞);
#   与同文件_is_forbidden_path异常返回"system"(L197-199)/空路径"system"(L230)/穿越"system"(L259)/校验异常"system"(L267)/系统保护"system"(L288)一致 — 小欧 2026-08-11
# 2026-08-11 - 小欧 - fix D1残留(实证补充, task005报告核验发现): validate_tool_path 自身兜底except分支 category=None→"system"(永不授权硬拦),
#   原返回 (False, "路径安全检查异常", None, None) — category=None → T2 当"白名单外非禁区→可授权请求"(requires_confirmation+auth_path),
#   异常/恶意路径理论上仍可被临时授权放行(与D1同源隐患); 归入"system"后 T2 硬拦永不授权, 与 validate_path 各异常分支"system"口径全链一致 — 小欧 2026-08-11
# 2026-08-12 - 小欧 - A1越层前置: safety 整目录由 app.services.safety 提升为顶层 app.safety, 本文件 import 路径同步更新(配合 tools 禁 app.services 守护规则)
"""
path_safe_check — 文件路径越权校验（Safety层）

Safety层职责（本文件）：
  - 路径黑名单：禁止访问系统敏感路径（_is_forbidden_path）
  - 路径白名单：只允许在 ALLOWED_PATHS 内操作路径
  - 路径穿越(..)拒绝
  - 调用入口 validate_tool_path() 自动判断工具分类 + 找路径参数

工具层（validate/file_path_checker.py + validate/file_safety_checker.py）独立运行、互不调用：
  - 非空/保留字符/保留名/系统目录硬阻断/存在性+类型/业务警告
  - 内容安全检查 / 模块安装检查

从 file_tools.py 提取,供 safety 和 tools 共用,打破循环依赖

小沈 2026-06-17
小健 2026-06-23 增加系统敏感路径黑名单校验
小欧 2026-07-04 补充两层架构说明注释
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory
from app.tools.tool_constants import (
    FORBIDDEN_PATHS_EXACT,
    FORBIDDEN_PATHS_PREFIX,
    FORBIDDEN_PATHS_WINDOWS_EXACT,
    FORBIDDEN_PATHS_WINDOWS_PREFIX,
)
from app.tools.tools_alias_mapper import normalize_tool_name, normalize_params  # P2/三堂会审BUG-3: 工具名+参数名别名归一防漏检 — 小欧 2026-08-10
from app.logger import logger


def get_existing_drives() -> List[Path]:
    """动态获取当前存在的磁盘符号列表 — 小欧 2026-08-04 (北京老陈驱动, 设计文档 v1.14/v1.15)
    R2(磁盘根递归删除→拒绝) 判定时刻使用, 不写死盘符(遍历A-Z探测存在盘, 应对U盘插拔/盘符重映射)"""
    drives: List[Path] = []
    if os.name == "nt":
        for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            drive = Path(f"{c}:/")
            if drive.exists():
                drives.append(drive)
    return drives


def get_system_drive() -> str:
    """动态获取真实系统盘符(安全检查时刻) — 小欧 2026-08-04 (北京老陈驱动, 设计文档 v1.13)
    写死C:作默认模板不足, 运行时动态替换为真实系统盘符(支持系统盘非C:/盘符重映射, 不漏判不误伤)。
    优先级: SystemRoot/WINDIR 环境变量 → SystemDrive → 探测存在\\Windows的盘符 → 兜底 C:
    返回带冒号的盘符如 "C:" 或 "D:"(无反斜杠)"""
    for var in ("SystemRoot", "WINDIR"):
        root = os.environ.get(var)
        if root:
            drive, _ = os.path.splitdrive(root)
            if drive:
                return drive
    sdrive = os.environ.get("SystemDrive", "")
    if sdrive:
        return sdrive.rstrip("\\/")
    if os.name == "nt":
        for c in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            if os.path.isdir(f"{c}:\\Windows"):
                return f"{c}:"
    return "C:"


def get_default_allowed_paths() -> List[Path]:
    """获取默认允许的路径列表 — 小沈 2026-06-17 从file_tools提取
    小欧 2026-08-04: 盘符枚举A-J硬编码上限改动态(get_existing_drives) — 北京老陈驱动
    小欧 2026-08-10 ⑪: 废除「所有现存盘符」全盘放开, 白名单=主目录+tmp+项目根+授权目录(3.3决策②);
    get_existing_drives 不再拼入(各盘只有落在主目录/项目根/授权目录内的路径才允许)。
    """
    from app.config import get_config  # 局部导入避免模块级对 config 的耦合(补B lazy)
    paths = [
        Path.home(),
        Path("/tmp"),
        Path("/var/tmp"),
    ]
    try:
        cfg = get_config()
        paths.append(Path(cfg.get_project_root()).resolve())
        for d in cfg.get_allowed_dirs():
            paths.append(Path(d))
    except Exception:
        pass
    return paths


ALLOWED_PATHS: List[Path] = get_default_allowed_paths()


def _get_project_root_safety() -> Path:
    """获取项目根(tool工作区)供 Safety 层判定 — 小欧 2026-08-10 ⑤收敛走config
    统一走 config.get_project_root(): 配置 app.project_root 优先, 未配置→用户主目录;
    不再以代码位置推算(那是代码库根, 属tool禁区, 不得充当项目根)。
    """
    from app.config import get_config
    try:
        cfg_root = get_config().get_project_root()
        if cfg_root:
            return Path(cfg_root).resolve()
    except Exception:
        pass
    return Path.home()


def _is_forbidden_path(file_path: str) -> Tuple[Optional[str], Optional[str]]:
    """检查路径是否在系统敏感路径黑名单中 — 小健 2026-06-23
    P1 (v1.43 修正): 返回值扩展为禁区类别(category, msg)
    
    Args:
        file_path: 待检查路径
        
    Returns:
        (category, error_message) — category ∈ {"system", "non_system", None}:
            "system" = 系统敏感目录+磁盘根(3.2.8 第1-5类, 写/删永不授权)
            "non_system" = 代码库根及父子级(3.2.8 第6类, 写可任务级授权, 删硬拦)
            None = 非禁区(白名单外·非禁区)
    """
    try:
        real_path = Path(os.path.realpath(os.path.expanduser(file_path)))
        real_path_str = str(real_path)
        real_path_lower = real_path_str.lower()
        
        # 磁盘根目录(C:\)黑名单 — 白名单盘符机制允许盘根操作, 此处硬阻断 — 小欧 2026-08-02
        # P1: 磁盘根属于系统禁区(system)
        try:
            drive, rest = os.path.splitdrive(real_path_str)
            if drive and not rest.strip("\\/"):
                return "system", f"禁止访问磁盘根目录: {file_path}"
        except Exception:
            pass
        
        if os.name == 'nt':
            sys_drive = get_system_drive()  # 真实系统盘符(写死C:模板作默认, 运行时动态替换) — 小欧 2026-08-04
            for forbidden in FORBIDDEN_PATHS_WINDOWS_EXACT:
                _f = forbidden.replace("C:", sys_drive, 1) if forbidden.upper().startswith("C:") else forbidden
                if real_path_lower == _f.lower():
                    return "system", f"禁止访问系统敏感文件: {file_path}"
            for forbidden_prefix in FORBIDDEN_PATHS_WINDOWS_PREFIX:
                _f = forbidden_prefix.replace("C:", sys_drive, 1) if forbidden_prefix.upper().startswith("C:") else forbidden_prefix
                if real_path_lower.startswith(_f.lower()):
                    return "system", f"禁止访问系统敏感目录: {file_path}"

        # ⑦ 代码库根禁区(tool禁区, 开关无关硬拦截): 代码库根及其子/父级全部禁止 — 小欧 2026-08-10
        # P1: 代码库根属非系统禁区(non_system)
        try:
            from app.config import get_code_root
            code_root = get_code_root()
            if code_root:
                _cr = Path(os.path.realpath(code_root))
                cr_lower = str(_cr).lower()
                if (real_path_lower == cr_lower
                        or real_path_lower.startswith(cr_lower + os.sep)
                        or real_path_lower.startswith(cr_lower + "/")):
                    return "non_system", f"禁止访问代码库(tool禁区): {file_path}"
        except Exception:
            pass

        for forbidden in FORBIDDEN_PATHS_EXACT:
            if real_path_str == forbidden:
                return "system", f"禁止访问系统敏感文件: {file_path}"
        for forbidden_prefix in FORBIDDEN_PATHS_PREFIX:
            if real_path_str.startswith(forbidden_prefix):
                return "system", f"禁止访问系统敏感目录: {file_path}"
        
        return None, None
    except Exception as e:
        # 【P1-21修复】异常时拒绝访问而非放行 — chendyg 2026-06-26
        # P1: 异常判定为system禁区(硬拦永不授权)
        return "system", f"路径安全检查异常,拒绝访问: {file_path} ({e})"


def validate_path(file_path: str, allowed_paths: Optional[List[Path]] = None,
                  mode: str = "write") -> Tuple[bool, Optional[str], Optional[str]]:
    """验证文件路径是否在白名单内(安全层)
    P3 (v1.43 修正): 增加 mode 分级判定, 返回值扩展为 (is_valid, msg, category)

    Args:
        file_path: 待验证路径
        allowed_paths: 白名单(默认使用 ALLOWED_PATHS)
        mode: 操作类型('read'/'write'/'delete'), 默认 'write'

    Returns:
        (is_valid, error_message, category) — category ∈ {"system", "non_system", None}
            用于 P4/T2 显式分流(P1 返回类别替代 msg 字符串特征)

    判定规则(3.2.14/表五):
        - 读: 白名单外非禁区/禁区全部放行(内容敏感性 contentFilter 兜底)
        - 写: 系统禁区硬拦/非系统禁区写→查 is_temp_authorized(已任务级授权则放行)/白名单外写临时授权
        - 删: 系统+非系统禁区一律硬拦/白名单外删临时授权

    小沈 2026-06-17 从 FileTools._validate_path 提取为纯函数
    小健 2026-06-23 增加黑名单优先检查
    小欧 2026-06-25 增加路径穿越(..)拒绝
    小欧 2026-06-26 拒绝空路径
    """
    if not file_path or not file_path.strip():
        # T2 回归修复 (三堂会审复核发现, v1.45): 空路径是无效参数, 归入 category="system"(永不授权),
        #   原返回 category=None → T2 当"白名单外非禁区→可授权请求", 空路径从 blocked 退化为可授权(退化);
        #   与 test_bug_empty_path_not_validated 断言(空路径应 blocked)对齐 — 小欧 2026-08-10
        return False, "路径为空", "system"

    is_forbidden, forbidden_msg = _is_forbidden_path(file_path)
    if is_forbidden:
        # P3: 读放行 — 禁区读✅放行(内容敏感性 contentFilter 兜底)
        if mode == "read":
            return True, None, is_forbidden
        # P3: 写/删 — 系统禁区硬拦, 非系统禁区写查is_temp_authorized, 删硬拦
        if is_forbidden == "system":
            return False, forbidden_msg, "system"
        if is_forbidden == "non_system":
            # 非系统禁区删硬拦(删无授权分支)
            if mode == "delete":
                return False, forbidden_msg, "non_system"
            # 非系统禁区写 → 查 is_temp_authorized(任务级授权)
            from app.safety.temp_auth import is_temp_authorized
            if is_temp_authorized(file_path):
                return True, None, "non_system"
            return False, forbidden_msg, "non_system"
        # 兜底: 异常判定为 system 硬拦
        return False, forbidden_msg, is_forbidden

    # 路径穿越拒绝: 包含..的路径直接拒绝 — 小欧 2026-06-25
    # T2 回归修复 (v1.45): 穿越路径归入 category="system"(永不授权) — 原返回 None → T2 当白名单外可授权,
    #   与 test_f5_03_path_traversal_blocked 断言(穿越应 blocked)对齐 — 小欧 2026-08-10
    try:
        # 检查原始路径的每个部分是否包含..
        path_parts = Path(file_path).parts
        if ".." in path_parts:
            return False, f"路径包含..,禁止路径穿越: {file_path}", "system"
        # 也检查规范化解析后的路径（处理绝对路径中的..）
        resolved = os.path.realpath(file_path)
        original_resolved = os.path.realpath(os.path.dirname(file_path))
        if not resolved.startswith(original_resolved) and file_path != resolved:
            return False, f"路径穿越检测: {file_path} 解析为 {resolved}", "system"
    except Exception as e:
        logger.warning(f"[path_safe_check] 路径校验异常: {file_path}: {e}")
        return False, f"路径校验异常: {file_path}", "system"

    # P3: 白名单判定 — 白名单内读/写/删都放行(删受 R3-R6)
    # 补B(2026-08-10): 白名单懒加载——每次调用动态计算(主目录+tmp+项目根+授权目录),
    # 避免模块导入时 config 未就绪取错值; allowed_paths 显式传入时优先使用
    paths = allowed_paths if allowed_paths is not None else get_default_allowed_paths()
    try:
        real_path = Path(os.path.realpath(os.path.expanduser(file_path)))

        # 白名单盘符下仍拒绝系统保护目录（收紧范围）— 小欧 2026-07-18 #3 fix
        _SYSTEM_PROTECTED = frozenset({
            "windows", "program files", "program files (x86)",
            "programdata", "boot", "recovery",
        })
        _real_parts = real_path.parts
        if len(_real_parts) > 1 and _real_parts[1].lower() in _SYSTEM_PROTECTED:
            # P3 (v1.43): 读放行(内容敏感性 contentFilter 兜底, 与禁区读一致);
            #   写/删 → 系统禁区(category="system") — _is_forbidden_path 仅精确锁 WIN_EXACT 本身,
            #   其子路径(如 C:\Windows\a.txt) 靠本处兜底, 归类 system 使 T2 硬拦永不授权(表五/3.2.9)
            if mode == "read":
                return True, None, "system"
            return False, f"路径位于系统保护目录,禁止操作: {file_path}", "system"

        for allowed in paths:
            allowed_real = Path(os.path.realpath(allowed))
            try:
                real_parts = Path(real_path).parts
                allowed_parts = Path(allowed_real).parts

                if len(real_parts) >= len(allowed_parts):
                    prefix_match = all(real_parts[i] == allowed_parts[i] for i in range(len(allowed_parts)))
                    if not prefix_match:
                        continue

                    if len(allowed_parts) == 1 and (allowed_parts[0].endswith(':') or allowed_parts[0].endswith(':\\') or allowed_parts[0].endswith(':/')):
                        if str(real_path) == str(allowed_real) or real_path.parts[0] == allowed_parts[0]:
                            return True, None, None
                    else:
                        if len(real_parts) >= len(allowed_parts):
                            return True, None, None
            except (ValueError, OSError):
                pass

        # P3: 白名单外判定 — temp_auth(3.2.12) 仅在非禁区生效(禁区已在_is_forbidden_path拦截)
        # P3: 读 — 白名单外非禁区/禁区全部放行(contentFilter 兜底); 所以这里不用判mode, 直接放行
        # P3: 写/删 — 白名单外(非禁区)走临时授权判定
        from app.safety.temp_auth import is_temp_authorized
        if mode == "read":
            # P3: 读放行 — 白名单外非禁区读✅直接放行(只读工具)
            # (P1/P2 已拦截系统/代码库禁区, 此处剩白名单外·非禁区)
            return True, None, None
        # P3: 写/删 — 白名单外非禁区走临时授权
        if is_temp_authorized(file_path):
            return True, None, None
        return False, f"路径 '{file_path}' 不在允许的操作范围内(仅允许:{', '.join(str(p) for p in paths[:5])}...)", None

    except Exception as e:
        # 2026-08-11 小欧 fix D1: 异常路径归类为system(永不授权硬拦), 与_is_forbidden_path异常处理(L197-199)一致;
        #   原category=None→T2当"白名单外非禁区→可授权请求"→异常/恶意路径可被grant_temp_auth放行(安全漏洞)
        return False, f"路径验证失败: {str(e)}", "system"


# 路径相关的工具分类 — 5类工具涉及文件路径操作
_PATH_CATEGORIES = {
    ToolCategory.FILE, ToolCategory.DOCUMENT,
    ToolCategory.DATAANALYSIS, ToolCategory.NETWORK,
    ToolCategory.DESKTOP,
}

# 工具参数中可能的路径参数名(⑧2026-08-10补dest: compress/extract/move/copy/rename/generate_chart/download/screen_capture 的目标/输出路径)
_PATH_PARAM_KEYS = ("path", "source_path", "target_path", "file_path",
                    "directory", "file_name", "destination_path", "output_path",
                    "dest")

# P2: 只读工具集合(3.2.15, 以真实注册名为准, stat 无对应注册工具已剔除) — 小欧 2026-08-10 v1.43
_READ_ONLY_TOOLS = frozenset({
    "listdir", "tree", "find", "grep", "readtext", "readmedia",
    "read_pdf", "read_docx", "read_pptx", "read_xlsx",
})


def _resolve_path_param(tool_name: str, key: str, value: str, params: Dict[str, Any]) -> str:
    """工具逻辑路径参数→真实文件系统路径(白名单校验前) — 小欧 2026-08-10
    仅相对/文件名语义参数需要解析(BUG-B/C修复), 其余工具路径参数均为绝对路径原样返回:
      - download.dest: 相对下载目录(project_root/download), 真实路径 = 下载目录/dest (network_schema.py:57);
      - rename.dest:   仅文件名不含目录(file_schema.py:358), 工具内 dst = src.parent/新名 (rename_file.py:89), 真实路径 = 源文件同目录;
    解析逻辑与工具内部真实落盘逻辑一一对应(对齐白名单校验对象与实际写入对象)。
    """
    if tool_name == "download" and key == "dest":
        from app.config import get_config  # 局部导入避免模块级耦合
        base = os.path.join(get_config().get_project_root(), "download")
        return os.path.abspath(os.path.join(base, value.lstrip("/\\")))
    if tool_name == "rename" and key == "dest":
        src = params.get("path") or ""
        if src:
            return str(Path(src).parent / Path(value).name)
        return value
    return value


def validate_tool_path(tool_name: str, params: Dict[str, Any],
                       mode: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """
    工具路径检查：自动判断分类 + 找路径参数 + 调validate_path
    P4 (v1.43): 增加 mode 参数, 返回值扩展为四元组 (is_valid, error_message, failed_path, category)
    
    Args:
        tool_name: 工具名
        params: 工具参数
        mode: 操作模式(读/写/删), 若为None则按 tool_name 推断(3.2.15):
            - tool_name ∈ _READ_ONLY_TOOLS → 'read'
            - tool_name == 'delete' → 'delete'
            - 其余路径工具 → 'write'

    Returns:
        (is_valid, error_message, failed_path, category) —
            failed_path = 首个校验失败的真实路径(临时授权 auth_path 用, 成功时为 None)
            category ∈ {"system", "non_system", None} — 供 T2 显式分流(P1 返回类别替代 msg 字符串特征)
    
    将调度逻辑从 tool_safety_checker._check_known_risks 迁移至此，
    path相关的事情全部在 path_safe_check 中处理。
    小欧 2026-06-27, 2026-08-10 ⑨改为遍历所有命中路径参数逐一校验(漏洞B修复)
    ⑯2026-08-10: 逻辑路径参数先经 _resolve_path_param 解析为真实路径再校验(BUG-B/C);
                 返回 failed_path 供临时授权定位真正越权参数, 而非固定 path-or-dest(BUG-D)
    """
    try:
        # P4: mode 推断 — 按 tool_name 分组(3.2.15): 只读集合/read, delete/delete, 其余写工具/write
        normal_name = normalize_tool_name(tool_name)  # P2: 防别名漏判
        if mode is None:
            if normal_name in _READ_ONLY_TOOLS:
                mode = "read"
            elif normal_name == "delete":
                mode = "delete"
            else:
                mode = "write"
        
        # BUG-3 (三堂会审复核发现, v1.45): 参数别名先归一化再取路径参数 —
        #   LLM 常传 PARAM_ALIASES 里的别名(如 rename.new_name→dest/copy.src→path/dst→dest),
        #   原代码 hit_params 直接查原始 params, 别名参数命中不了 _PATH_PARAM_KEYS → 路径越权漏检。
        #   此处用 normalize_params 归一化后找路径参数, 校验对象与工具实际落盘路径一致(增强不退化)。
        normalized_params, _ = normalize_params(normal_name, params)
        
        all_categories = tool_registry.get_categories()
        path_tools = set()
        for cat in _PATH_CATEGORIES:
            path_tools.update(all_categories.get(cat, []))

        # BUG-1 (三堂会审复核发现, v1.45): path_tools 归属判断用归一化名 —
        #   原代码 `tool_name not in path_tools` 用 LLM 原始名, 别名工具(如 list_directory/read_text_file)
        #   不在 path_tools(注册名集合) → 直接 return True 放行, 绕过全部路径校验;
        #   统一走 normalize_tool_name 归一化后再判, 与 mode 推断同源(P2 防别名漏检补齐)。
        if normal_name not in path_tools:
            return True, None, None, None

        # ⑨ 遍历所有命中路径参数逐一校验, 任一越权即拒绝(原只取第一个命中参数的漏洞B修复)
        hit_params = [key for key in _PATH_PARAM_KEYS if normalized_params.get(key) is not None]
        if not hit_params:
            return True, None, None, None

        for key in hit_params:
            real_path = _resolve_path_param(normal_name, key, normalized_params[key], normalized_params)
            valid, err, category = validate_path(real_path, mode=mode)
            if not valid:
                return False, err, real_path, category

        return True, None, None, None
    except Exception as e:
        # 2026-08-11 小欧 fix D1残留: 兜底异常归 category="system"(永不授权硬拦) —
        #   原返回 None → T2 当"白名单外非禁区→可授权请求", 异常/恶意路径可被临时授权放行(与D1同源隐患);
        #   与 validate_path 各异常分支"system"口径全链一致(T2 硬拦永不授权)
        return False, f"路径安全检查异常: {e}", None, "system"


__all__ = ["ALLOWED_PATHS", "get_default_allowed_paths", "get_existing_drives",
           "get_system_drive", "_get_project_root_safety", "validate_path",
           "validate_tool_path", "_is_forbidden_path", "_READ_ONLY_TOOLS"]

