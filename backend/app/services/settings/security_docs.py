# -*- coding: utf-8 -*-
"""
security_docs — 安全 Tab 说明文案源: 读 app/datafile/*.md(两个弹框各一个 + 分类表页面直出一个),
把 {{占位符}} 替换成真实路径值。

为什么插值放后端而非前端:
  占位符的值只有后端拿得到, 后端一次替换完 → 前端只把 md 交给 MarkdownSlot 渲染, 零字符串逻辑。

分层: 本模块只 import 三个轻量模块 app.config / app.logger / app.tools.tool_constants,
  且**绝不 import app.tools.security.path_safe_check** —— 后者 :71 顶层拉入整个 tool_registry。
  tool_constants 全部 import 只有 tool_types + app.constants, 不拉注册表, 直接用零代价。

为什么不需要处理盘符:
  FORBIDDEN_PATHS_WINDOWS_REL_* 常量已是与盘符无关的相对段, 既无硬编码盘符,
  也无 .replace("C:", ...) 字符串替换。分类表直接展示相对段, 语义等价。

datafile 目录定位为什么不用 get_frozen_dir():
  get_frozen_dir()(config.py:296)服务 logs/files 等**可写**目录; datafile 是**只读**资源,
  随 app/ 整树打包(spec:21-25 app_tree), 源码与 exe 两种模式下 __file__ 相对路径一致,
  故不需要 frozen 分支(多一个分支就多一处要同步的判断)。

读文件为什么不用 safe_read_file(shell_engine.py:257)—— 只借它的硬化, 不引它的依赖:
  ① shell_engine 顶层 import subprocess/tempfile/threading, 为读几行文本拖进整套子进程栈不值当;
  ② safe_read_file 把「文件不存在」与「空文件」都返回 "", 而本模块要区分二者
     (缺失→给用户一句报错, 空→给空文案), 语义不匹配。
  故仅复用 errors="replace" 这一条硬化结论, 其余自实现。

编辑历史:
  2026-10-06 小欧 - 新建: 读 3 个 md + {{占位符}} 插值 + 缺文件降级 + 失败落日志 + 轻量依赖。
  2026-10-06 小欧 - 三堂会审修 4 项: ①插值只算一次(原先每文件各算一遍, 3 次 get_config);
    ②异常捕获放宽到 Exception(原先只捕 OSError/ValueError, get_config() 抛别的会穿透成 500,
    与本模块"不抛异常"的承诺矛盾); ③降级文案不再回显异常细节(会泄露服务器路径);
    ④新增 {{system_protected}} 占位符, 分类表不再硬编码 \ProgramData 等 3 个名字。
  2026-10-06 小欧 - 禁区路径去掉反引号: 内联 code 的背景+圆角把分类表路径列撑成灰底碎块(实测 13 个)。
"""
from pathlib import Path
from typing import Dict

from app.config import get_code_root, get_config
from app.logger import logger
from app.tools.tool_constants import (
    FORBIDDEN_PATHS_WINDOWS_REL_EXACT,
    FORBIDDEN_PATHS_WINDOWS_REL_PREFIX,
    SYSTEM_PROTECTED_DIR_NAMES,
)

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
        "code_root": str(get_code_root()),
        "user_home": str(Path.home()),
        "project_root": str(get_config().get_project_root()),
        "allowed_dirs": "\n".join(str(p) for p in allowed) if allowed else "（未配置）",
    }


def _windows_forbidden_text() -> str:
    """禁区·系统的 Windows 禁用路径清单(直接取工具常量, 不另抄一份)。

    必须单行输出: 该占位符落在 md 表格单元格里, 换行会把表格行撑破(5 行变 14 行);
    <br/> 也不行 —— 本项目未装 rehype-raw, rehype-sanitize 会把它整段丢掉。
    故用「、」连成一行, 由前端 overflowWrap 负责折行。

    2026-10-06 三堂会审 #5: 路径**不加反引号** —— 内联 code 各带背景+圆角, 实测 13 个
    code 把「目录列表」列撑成一片灰底碎块。路径是正文不是代码, 交由 overflowWrap 折行。
    """
    paths = sorted(FORBIDDEN_PATHS_WINDOWS_REL_EXACT | FORBIDDEN_PATHS_WINDOWS_REL_PREFIX)
    return "、".join(paths)


def _system_protected_text() -> str:
    """系统保护目录名中**未被上一条覆盖**的那几个(如 \\ProgramData、\\Boot、\\Recovery)。

    SYSTEM_PROTECTED_DIR_NAMES 里的 windows / program files / program files (x86)
    已由 _windows_forbidden_text() 以完整相对段呈现, 此处只补差集, 避免同一目录列两遍。
    """
    covered = {p.lstrip("\\").lower() for p in FORBIDDEN_PATHS_WINDOWS_REL_EXACT}
    rest = sorted(SYSTEM_PROTECTED_DIR_NAMES - covered)
    return "、".join(f"\\{n}" for n in rest)


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
    values["system_forbidden"] = _windows_forbidden_text()
    values["system_protected"] = _system_protected_text()

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
