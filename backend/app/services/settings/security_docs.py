# -*- coding: utf-8 -*-
r"""  # 2026-10-14 小欧 - docstring 改 raw(消启动期 SyntaxWarning: invalid escape sequence '\P'): 内容含 \ProgramData 等 Windows 路径 — 小欧-2026-10-14
security_docs — 安全 Tab 说明文案源: 读 app/datafile/*.md(两个弹框各一个 + 分类表页面直出一个),
把 {{占位符}} 替换成真实路径值。

为什么插值放后端而非前端:
  占位符的值只有后端拿得到, 后端一次替换完 → 前端只把 md 交给 MarkdownSlot 渲染, 零字符串逻辑。

分层: 本模块只 import 三个轻量模块 app.config / app.logger /
  app.safety.path_dir_lists(★2026-10-20 原文此处写"四个"含 app.tools.tool_constants 已随禁区清单
  数据源收口删除; path_dir_lists 只取禁区·系统类别构建函数与平台根, 不调其判定函数)。

为什么不需要处理盘符:
  禁区清单改读系统目录名单 path_dir_lists(禁区·系统, 全系统唯一类别组织口), 展示时剥平台根
  前缀成相对段(Windows: C:\Windows → \Windows), 既无硬编码盘符, 也无 .replace("C:", ...)
  字符串替换。分类表直接展示相对段, 语义等价。

datafile 目录定位为什么不用 get_frozen_dir():
  get_frozen_dir()(config.py:296)服务 logs/files 等**可写**目录; datafile 是**只读**资源,
  随 app/ 整树打包(spec:21-25 app_tree), 源码与 exe 两种模式下 __file__ 相对路径一致,
  故不需要 frozen 分支(多一个分支就多一处要同步的判断)。

读文件为什么不用 safe_read_file(shell_engine.py:257)—— 只借它的硬化, 不引它的依赖:
   shell_engine 顶层 import subprocess/tempfile/threading, 为读几行文本拖进整套子进程栈不值当;
   safe_read_file 把「文件不存在」与「空文件」都返回 "", 而本模块要区分二者
     (缺失→给用户一句报错, 空→给空文案), 语义不匹配。
  故仅复用 errors="replace" 这一条硬化结论, 其余自实现。

编辑历史:
  2026-10-06 小欧 - 新建: 读 3 个 md + {{占位符}} 插值 + 缺文件降级 + 失败落日志 + 轻量依赖。
  2026-10-06 小欧 - 4 项: 插值只算一次(原先每文件各算一遍, 3 次 get_config);
    异常捕获放宽到 Exception(原先只捕 OSError/ValueError, get_config() 抛别的会穿透成 500,
    与本模块"不抛异常"的承诺矛盾); 降级文案不再回显异常细节(会泄露服务器路径);
    新增 {{system_protected}} 占位符, 分类表不再硬编码 \ProgramData 等 3 个名字。
  2026-10-06 小欧 - 禁区路径去掉反引号: 内联 code 的背景+圆角把分类表路径列撑成灰底碎块(实测 13 个)。
  2026-10-14 小欧 - SYSTEM_PROTECTED_DIR_NAMES 改从 app/utils/path_utils.py 导入; docstring 内「绝不 import」注释路径同步改址
  2026-10-19 小欧 - 修 _system_protected_text 崩溃: SYSTEM_PROTECTED_DIR_NAMES 已由 frozenset 迁为 tuple(list 语义, 保序),
      `tuple - set` 抛 TypeError 使安全 Tab 打开即 500; 改 `set(SYSTEM_PROTECTED_DIR_NAMES) - covered`(差集语义不变)。
  2026-10-20 16:17:50 小欧 - 禁区清单数据源收口(北京老陈令: 参考系统几类路径组织函数更新): 弃读 tool_constants
      旧常量(FORBIDDEN_PATHS_WINDOWS_REL_*, 与判定名单分叉的手抄份), 改读 path_dir_lists 禁区·系统类别构建函数
      (_build_forbidden_system_path, 全系统唯一组织口); 磁盘根(self_only)跳过(md 已单列), 剥平台根前缀成相对段;
      _system_protected_text 删除(数据并入禁区·系统), md 去 {{system_protected}} 占位符。
  2026-10-20 16:3x 小欧 - 三堂会审纠偏(北京老陈令: 四类行都要参考系统): 禁区·非系统/白名单内两行原仍写死
      (前者漏允许根自身/用户自启动目录, 后者硬编码 /tmp、/var/tmp 且漏会话工作区), 一并改读系统名单:
      新增 _forbidden_non_system_text(读 _build_forbidden_non_system_path, 按 label 分组合并) +
      _whitelist_text(读 _build_whitelist_path, 按来源 label 合并, 友好名映射); md 两行改
      {{forbidden_non_system}}/{{whitelist}} 整行占位; {{code_root}} 占位符随整行化删除。
"""
import os
from pathlib import Path
from typing import Dict, List

from app.config import get_config
from app.logger import logger
# 2026-10-20 小欧 - 禁区清单数据源收口: 改读 path_dir_lists 三类名单组织函数(全系统唯一组织口),
#   弃 tool_constants 旧常量(与判定名单分叉的手抄份); _platform_root 供剥平台根前缀成相对段
from app.safety.path_dir_lists import (
    _build_forbidden_non_system_path,
    _build_forbidden_system_path,
    _build_whitelist_path,
    _platform_root,
)

#: 白名单 label → 文档友好名(与 md 措辞对齐; 未登记的 label 原样输出, 新增来源时兜住)
_WHITELIST_LABEL_TEXT = {
    "用户目录": "用户主目录",
    "系统临时目录": "系统临时目录",
    "项目根": "项目根目录",
    "授权目录": "授权目录",
    "会话工作区": "会话工作区",
}

# 2026-10-06 小欧 - datafile 定位: app/services/settings/ 上溯两级 = app/, 同级 datafile/
DATAFILE_DIR = Path(__file__).resolve().parents[2] / "datafile"

# 2026-10-06 小欧 - md 文件名与返回键的唯一映射(DRY: 文件名只此一处出现)
_DOC_FILES = {
    "policy": "security_policy.md",
    "flow": "path_decision.md",
    "classification": "dir_classification.md",
}


def _placeholder_values() -> Dict[str, str]:
    """占位符 → 真实值的唯一映射点。

    allowed_dirs 转多行: get_allowed_dirs() 返回 List[Path], 直接插值会渲染成
    Python 字面量 ['a', 'b']; 空列表时给一句提示, 否则单元格只剩一个空代码块。
    """
    allowed = get_config().get_allowed_dirs()
    return {
        "user_home": str(Path.home()),
        "project_root": str(get_config().get_project_root()),
        "allowed_dirs": "\n".join(str(p) for p in allowed) if allowed else "（未配置）",
    }


def _forbidden_system_text() -> str:
    """禁区·系统清单(平台根下相对段, 单行「、」连接) — 小欧 2026-10-20

    数据源: 系统目录名单 path_dir_lists 禁区·系统(全系统唯一类别组织口
    _build_forbidden_system_path), 不再读 tool_constants 旧常量 —— 那份是 Windows
    相对段的另一份手抄, 与判定名单已分叉(旧常量含 config\\SAM 等判定名单里没有的细项)。

    必须单行输出: 该占位符落在 md 表格单元格里, 换行会把表格行撑破(5 行变 14 行);
    <br/> 也不行 —— 本项目未装 rehype-raw, rehype-sanitize 会把它整段丢掉。
    故用「、」连成一行, 由前端 overflowWrap 负责折行。

    口径: 磁盘根(self_only 条目)跳过 —— md 已单列「磁盘根（系统盘根）」; 只取平台根
    下条目并剥前缀成相对段(Windows: C:\\Windows → \\Windows), 保持不硬编码盘符的展示口径。
    路径**不加反引号** — 内联 code 各带背景+圆角, 实测 13 个 code 把「目录列表」列撑成
    一片灰底碎块(2026-10-06 修复)。路径是正文不是代码, 交由 overflowWrap 折行。
    """
    plat = str(_platform_root())
    segs = []
    for rule in _build_forbidden_system_path():
        if rule.self_only:
            continue                                   # 磁盘根(仅自身) — md 已单列
        s = str(rule.path)
        if not os.path.normcase(s).startswith(os.path.normcase(plat)):
            continue                                   # 平台外条目(如 Linux 跨平台禁区)不进本机清单
        rel = s[len(plat):]
        segs.append((os.sep + rel) if rel and not rel.startswith(os.sep) else rel)
    return "、".join(sorted(segs))


def _forbidden_non_system_text() -> str:
    """禁区·非系统清单(全路径, 按 label 分组合并) — 小欧 2026-10-20

    数据源: 系统目录名单 path_dir_lists 禁区·非系统(_build_forbidden_non_system_path):
    代码目录(含下级) + 允许根自身(self_only, 删硬拦) + 用户自启动目录(含下级)。
    单行「、」连接(表格单元格约束, 见 _forbidden_system_text 同款说明)。
    """
    groups: Dict[str, List[str]] = {}
    for rule in _build_forbidden_non_system_path():
        groups.setdefault(rule.label, []).append(str(rule.path))
    return "、".join(f"{label}（{'、'.join(paths)}）" for label, paths in groups.items())


def _whitelist_text() -> str:
    """白名单清单(全路径, 按来源 label 分组合并) — 小欧 2026-10-20

    数据源: 系统目录名单 path_dir_lists 白名单(_build_whitelist_path):
    用户目录 + 系统临时目录 + 允许根(项目根/授权目录/会话工作区)。
    会话工作区是任务级注入, 设置页(无任务上下文)不出现该组 —— 与判定口径一致。
    """
    groups: Dict[str, List[str]] = {}
    for rule in _build_whitelist_path():
        groups.setdefault(rule.label, []).append(str(rule.path))
    return "、".join(f"{_WHITELIST_LABEL_TEXT.get(label, label)}（{'、'.join(paths)}）"
                     for label, paths in groups.items())


def _render(filename: str, values: Dict[str, str]) -> str:
    """读 md 并替换全部占位符; 未登记的占位符原样保留(便于发现拼写错误)。

    errors="replace" 借自 safe_read_file: 用户手改 md 若存成非 UTF-8, 不应让
    UnicodeDecodeError 穿透成 500。
    """
    text = (DATAFILE_DIR / filename).read_text(encoding="utf-8", errors="replace")
    for key, val in values.items():
        text = text.replace("{{" + key + "}}", val)
    return text


def load_security_docs() -> Dict[str, str]:
    """返回 {policy, flow, classification} 三段已插值 md(两个弹框 + 页面直出各一份)。

    单个文件缺失不抛异常: 该段降级为一行提示, 其余段仍可用——
    说明文案缺失不该让整个安全 Tab 打不开。
    """
    # 2026-10-06 小欧 - 插值只算一次: 原先 _render 内部各算一遍, 3 个文件 = 3 次 get_config()
    values = _placeholder_values()
    values["system_forbidden"] = _forbidden_system_text()
    values["forbidden_non_system"] = _forbidden_non_system_text()
    values["whitelist"] = _whitelist_text()

    out: Dict[str, str] = {}
    for key, filename in _DOC_FILES.items():
        try:
            out[key] = _render(filename, values)
        except Exception as exc:  # noqa: BLE001 - 降级是本函数的契约, 任何异常都不许穿透成 500
            # 落日志: 文件缺失/不可读是真事件, 否则线上无从查起
            # (同 path_safe_check.py logger.warning 既有范式)
            logger.warning(f"[security_docs] 说明文件读取失败: {filename} - {exc}", exc_info=True)
            # 2026-10-06 小欧 - 只回文件名不回异常细节: exc 里带服务器绝对路径与栈信息
            out[key] = f"> 说明文件读取失败，请检查安装包是否完整：{filename}"
    return out
