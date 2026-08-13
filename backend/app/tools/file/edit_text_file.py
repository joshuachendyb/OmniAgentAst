# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-16 - 小欧 - _precise_replace_in_file 返回值移除未消费的 operation_id(YAGNI, 调用方不读取)
# 2026-07-17 - 小欧 - 新增护栏3项: ①锚点重叠检查(before/after拒绝); ②语法校验(all拒绝+增量warning); ③all宽匹配/边界拦截(拒绝+warning)
# 2026-07-17 - 小欧 - before/after 自动补空行(默认生效,无参数): 新增 _blank_line_sep, before/after 插入时与锚点/后续均隔一个空行(PEP8)
# 2026-07-17 - 小欧 - DRY重构: 抽出 _is_dangerous_anchor(old_string), _safety_wide_replace 仅保留宽匹配warning, 三引号拒绝统一走 _is_dangerous_anchor+内联
# 2026-07-20 - 小欧 - MAX_READ_SIZE 依3.5改名 EDITTEXT_INPUT_MAX_BYTES(edittext 自有内部常量, 各 tool 独立不公用, INER_ 前缀; 3.4 硬安全网保留, 文件过大拒绝, 不截断)
# 2026-07-20 - 小欧 - 门限复查: _build_edit_text_file_llm_data 移除顶层 "diff"(及 diff[:500] 截断, 违3.7); diff 统一经 data["diff"] → #24(已行×列收口+两态), 消除与 llm_data 段顶层 diff(:544)的重复渲染; 全/部分应用均置 data={"diff":...}
# 2026-07-21 - 小欧 - 修字段语义错位(SLAP/KISS-DIRECT): 阻断写入的校验错误字段 encode_error→validation_error(原误将语法错误存入编码错误字段), 全文件6处同步
# 2026-07-21 - 小欧 - #9 文件外部修改错误增强: check_conflict_strict 失败时附文件当前内容前2000字符到错误消息
# 2026-07-24 - 小欧 - 重构: 11处散落截断→main函数入口统一截断(3常量); helper/build函数去截断(北京老陈驱动)
# 2026-07-25 - 小欧 - 修复: execute_with_safety返回值类型不匹配——病根: 2026-07-15 execute_with_safety改为返回(bool,str), edittext是唯一未解包的调用方, tuple永为true致not success永假, 保险失效
# 2026-07-25 - 小欧 - 修复: edittext读文件后未调record_read——病根: conflict check无准确mtime基准, 使用前次操作(如writetext)的record_write mtime, Windows mtime波动致~50%误判
# 2026-07-25 - 小欧 - 修复: None/空校验在截断之后——病根: 2026-07-24截断重构移到main入口, old_string/new_string在None检查前被截断(TypeError), 应先将None/空校验提前
# 2026-07-25 - 小欧 - 清理: mtime_warning死变量——病根: 声明后从未赋值(YAGNI), 删除line 361声明、line 379/497返回值
# 2026-07-29 - 小欧 - validation_error加强: 格式"行N；语法错误；建议:xxxx"替代纯error_text; 透传_syn_line/_syn_suggestion到main; metrics新增error_line+suggestion; _check_anchor_overlap报错简化: 去除冗余行引用, 统一"只包含新内容"表述
# 2026-08-08 - 小欧 - task002问题1增强: 新增_anchor_signature_hint — before/after锚点为单行def/class签名行时给safety_hint提示(引导用方法体末行锚点), 不改插入逻辑(KISS), 与sl_warn/so_warn合并不覆盖 | py_compile ✓
# 2026-08-08 - 小欧 - _anchor_signature_hint 三堂会审精简: 空串/多行两项卫兵合并为 first=old_string.strip() 单卫(not first or '\n' in first), 消除重复rstrip/strip, 职责唯一零回归 | 回归 pytest: before_after+internal+retest 169✓ v2+deep+twelfth 112✓ guardrail+perf 64✓
# 2026-08-09 - 小欧 - task006 P4: 编码回退反馈 — 用户指定编码无效时原仅logger.warning, LLM感知不到
#   病根: _try_read_file_with_encodings 第三参数err_msg非None即被调用方raise, 报告"子函数返回hint"方案会破坏
#   该契约导致回退成功变失败(退化) → 改为调用方合成: encoding与used_enc不一致时生成encoding_fallback并入safety_hint, 增强不退化
#   验证: 指定无效编码→回退提示; 一致/未指定/失败短路均无提示
# 2026-08-09 - 小欧 - DRY合并: 本地 _try_read_file_with_encodings 迁入公共 file_encoding.read_file_with_encodings(import别名保持调用点零改动)
#   病根: readtext/edittext 各持一份同名编码回退读取实现且行为不一致(本版对preferred做替换符检查, readtext对preferred直接返回)
#   方案: 合并为公共版(取增强语义: 所有编码统一替换符阈值+mojibake检查); 本文件删除本地实现与本地阈值常量/get_file_encoding import;
#         P1修正(拼接顺序)在下方success分支, 优先保safety_hint完整
# 2026-08-12 - 小欧 - A1越层前置: safety 整目录由 app.services.safety 提升为顶层 app.safety, import 路径同步更新(配合 tools 禁 app.services 守护规则)
# 2026-08-12 - 小欧 - A1下沉: task_id ContextVar 迁至 app.tools.context, _current_task_id import 由 app.services.task.task_context 改 app.tools.context,
#   消除 tools 层对 app.services 越层依赖(守护测试 tools 禁 app.services 规则), 行为零变化(同一 ContextVar 对象)
# 2026-08-12 - 小欧 - A1后半面(4.1.7定案): 删除 from app.safety import record_operation/execute_with_safety,
#   改为 get_current_hooks() 取安全 hooks, 消除 tools→safety 越层; task_id 仍 _current_task_id.get()
# 2026-08-13 - 小欧 - A5职责拆分: hint_* 错误提示函数/导入源改 app.tools.toolhelper.error_hints
# 2026-08-13 - 小沈 - BUG-3修复(三堂会审): get_current_hooks() 改 get_current_hooks_or_noop() 兜底返回 NoOpHooks,
#   消除入口未注入时 _hooks.record_operation() NPE(如测试直接调工具函数), 行为零退化(生产路径已注入不变)
# 2026-08-13 - 小欧 - 三堂会审修复#5: _precise_replace_in_file 的 stat/read_bytes/read_text/open('w')
#   全链 to_win_long_path 长路径化(仅NT生效), 深嵌套目标不再 WinError 206; 编码回退读取传 \\?\ 前缀 Path;
#   报告/diff/语法检测仍用原路径(不暴露 \\?\ 前缀, detect_language 只按扩展名判断不受影响)
# 2026-08-13 - 小欧 - 三堂会审修复#23: 移除死导入 validate_str_param(合规/DRY)
#   【病根】from app.tools.validate.file_path_checker import validate_str_param 全文件零调用(grep仅导入处1处), 冗余导入
#   【改法】从导入行移除, 保留validate_path/OpCategory
"""
F4: edittext — 编辑文本文件

从file_tools.py拆分而来 — 小欧 2026-06-22
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import asyncio
import difflib
import re as re_mod
import time as _time_mod
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import EDITTEXT_INPUT_MAX_BYTES
from app.tools.tool_constants import ERR_FILE_EDIT_FAILED, ERR_FILE_REPLACE_FAILED
from app.tools.tool_constants import EDITTEXT_OUTPARM_LIMIT_OLD, EDITTEXT_OUTPARM_LIMIT_NEW, EDITTEXT_OUTPARM_LIMIT_SAFETY
from app.tools.context import _current_task_id, get_current_hooks_or_noop  # A1: ContextVar hooks — 小欧 2026-08-12; BUG-3修复 — 小沈 2026-08-13
from app.db.models.operation_models import OperationType
from app.tools.validate.file_type_checker import check_for_text_tool
from app.tools.validate.file_path_checker import validate_path, OpCategory  # 统一错误提示 - 小欧 2026-07-12; 2026-08-13 #23: 移除validate_str_param(全文件零调用)
from app.tools.toolhelper.error_hints import hint_for_write_error
from app.utils.path_utils import to_win_long_path  # #5长路径包裹 — 小欧 2026-08-13
from app.logger import logger
from app.tools.file.file_encoding import read_file_with_encodings as _try_read_file_with_encodings  # 小欧 2026-08-09: 本地重复实现合并入公共file_encoding
from app.tools.file.file_state import check_conflict_strict, record_write, record_read
from app.tools.file.fuzzy_match import fuzzy_find_replace  # 小欧 2026-07-11
from app.tools.toolhelper.syntax_validator import validate_syntax, detect_language  # 小欧 2026-07-21 统一语法检测接入


def _insert_line_after(content: str, match_end: int, new_string: str) -> str:
    """在 match_end 所在行的行尾之后插入 new_string 作为独立新行, 与锚点/后续均隔空行 - 小欧 2026-07-12 / 2026-07-17 空行分隔

    定位包含 match_end 的行的终止换行符:其后所有后续内容下移至新行之后,
    保证 new_string 独占一行,且与锚点行、后续内容各有空行分隔(PEP8)。
    """
    nl = content.find('\n', match_end)
    if nl == -1:
        # 匹配行是末行且无换行:末尾补空行后追加
        return content + '\n\n' + new_string
    ins_pos = nl + 1
    if ins_pos < len(content):
        # 其后续内容:new_string 前后均补空行, 与锚点/后续内容分隔 — 小欧 2026-07-17 空行分隔
        return content[:ins_pos] + '\n' + new_string + _blank_line_sep(new_string) + content[ins_pos:]
    # 换行符即文件末尾:补空行后追加
    return content[:ins_pos] + '\n' + new_string


def _blank_line_sep(text: str) -> str:
    """返回 text 与后文之间的空行分隔符,确保恰好一个空行 — 小欧 2026-07-17"""
    return '\n' if text.endswith('\n') else '\n\n'


def _apply_replacement(
    content: str, old_string: str, new_string: str,
    ignore_case: bool, mode: str,
) -> Tuple[str, int, int]:
    """执行替换/插入操作,返回(new_content, count, total_matches) — 小欧 2026-06-22 — 小健 2026-06-24 修复硬编码flags=2 — 小欧 2026-07-05 增加total_matches — 小欧 2026-07-11 replace_all→mode,增加before/after
    before/after 语义:在包含 old_string 的那一行之前/之后插入一条独立新行(非子串内联拼接) — 小欧 2026-07-12 修复行拼接缺陷"""

    count = 0
    total_matches = 0

    if mode == "before":
        if ignore_case:
            pattern = re_mod.escape(old_string)
            total_matches = len(re_mod.findall(pattern, content, re_mod.IGNORECASE))
            if total_matches == 1:
                match = re_mod.search(pattern, content, re_mod.IGNORECASE)
                # 行边界感知:在匹配行行首之前插入独立新行,前后均补空行 - 小欧 2026-07-12 - 2026-07-17 空行分隔
                line_start = content.rfind('\n', 0, match.start()) + 1
                _lead = '\n' if line_start > 0 else ''
                content = content[:line_start] + _lead + new_string + _blank_line_sep(new_string) + content[line_start:]
                count = 1
        else:
            total_matches = content.count(old_string)
            if total_matches == 1:
                idx = content.find(old_string)
                # 行边界感知:在匹配行行首之前插入独立新行,前后均补空行 - 小欧 2026-07-12 - 2026-07-17 空行分隔
                line_start = content.rfind('\n', 0, idx) + 1
                _lead = '\n' if line_start > 0 else ''
                content = content[:line_start] + _lead + new_string + _blank_line_sep(new_string) + content[line_start:]
                count = 1
        return content, count, total_matches

    if mode == "after":
        if ignore_case:
            pattern = re_mod.escape(old_string)
            total_matches = len(re_mod.findall(pattern, content, re_mod.IGNORECASE))
            if total_matches == 1:
                match = re_mod.search(pattern, content, re_mod.IGNORECASE)
                # 行边界感知:在匹配行行尾之后插入独立新行,避免与原行拼接 - 小欧 2026-07-12
                content = _insert_line_after(content, match.end(), new_string)
                count = 1
        else:
            total_matches = content.count(old_string)
            if total_matches == 1:
                idx = content.find(old_string)
                # 行边界感知:在匹配行行尾之后插入独立新行,避免与原行拼接 - 小欧 2026-07-12
                content = _insert_line_after(content, idx + len(old_string), new_string)
                count = 1
        return content, count, total_matches

    if mode == "all":
        flags = 0 if not ignore_case else re_mod.IGNORECASE
        pattern = re_mod.escape(old_string)
        if ignore_case:
            total_matches = len(re_mod.findall(pattern, content, flags))
            count = total_matches
            content = re_mod.sub(pattern, lambda m: new_string, content, flags=flags)
        else:
            total_matches = content.count(old_string)
            count = total_matches
            content = content.replace(old_string, new_string)
        return content, count, total_matches

    # mode == "once"
    if ignore_case:
        pattern = re_mod.escape(old_string)
        total_matches = len(re_mod.findall(pattern, content, re_mod.IGNORECASE))
        match = re_mod.search(pattern, content, re_mod.IGNORECASE)
        if match:
            content = content[:match.start()] + new_string + content[match.end():]
            count = 1
    else:
        total_matches = content.count(old_string)
        idx = content.find(old_string)
        if idx >= 0:
            content = content[:idx] + new_string + content[idx + len(old_string):]
            count = 1
    return content, count, total_matches


def _check_anchor_overlap(mode: str, old_string: str, new_string: str) -> str:
    """检测 before/after 下 new_string 首/尾行是否与锚点old_string整行相同
    before: new_string 尾行 == old_string → 锚点行将被重复保留
    after:  new_string 首行 == old_string → 锚点行将被重复保留
    返回错误描述(拒绝)或空字符串(通过) — 小欧 2026-07-17"""
    if not old_string or not new_string:
        return ""
    _os = old_string.strip()
    if not _os:
        return ""
    if mode == "before":
        _last_line = new_string.rstrip('\n').rsplit('\n')[-1].strip() if '\n' in new_string else new_string.strip()
        if _last_line and _last_line == _os:
            return (f"new_string尾行与锚点old_string相同,"
                    f"插入后锚点行重复。"
                    f"new_string只包含新内容即可,不要包含old_string整行")
    elif mode == "after":
        _first_line = new_string.strip('\n').split('\n')[0].strip() if '\n' in new_string else new_string.strip()
        if _first_line and _first_line == _os:
            return (f"new_string首行与锚点old_string相同,"
                    f"插入后锚点行重复。"
                    f"new_string只包含新内容即可,不要包含old_string整行")
    return ""


_SIG_ANCHOR_RE = re_mod.compile(r'^(?:async\s+)?(?:def|class)\s+\w+')


def _anchor_signature_hint(old_string: str) -> str:
    """检测 before/after 锚点是否为单行函数/类签名行(def/class), 返回引导提示或空串 — 小欧 2026-08-08 (task002问题1)

    场景: LLM 常以 'def sort_data(self):' 单行签名作 after 锚点, 本工具按"所在行"定位,
    插入会落在签名行后(即方法体之前)而非方法末尾, 导致新方法错位/旧方法体移位。
    提示引导改用方法体末行(如 return 行)作锚点。仅提示不改插入逻辑(KISS-DIRECT)。
    """
    first = old_string.strip()
    if not first or '\n' in first:
        return ""
    if _SIG_ANCHOR_RE.match(first):
        return (f"锚点是函数/类定义签名行({first[:40]}…)，before/after 按'匹配行'定位插入，"
                f"以签名行作锚点会插到方法体之前。建议改用方法体末行(如 return 行)作锚点。")
    return ""


def _safety_structure_loss(original: str, new_content: str) -> str:
    """检测替换是否导致函数/类定义丢失 — 小沈 2026-07-08"""
    orig_funcs = set(re_mod.findall(r'^\s*(?:async\s+)?def\s+(\w+)', original, re_mod.MULTILINE))
    new_funcs  = set(re_mod.findall(r'^\s*(?:async\s+)?def\s+(\w+)', new_content, re_mod.MULTILINE))
    parts = []
    if len(new_funcs) < len(orig_funcs):
        lost = orig_funcs - new_funcs
        if lost:
            parts.append(f"函数: {', '.join(sorted(lost))}")
    orig_classes = set(re_mod.findall(r'^\s*class\s+(\w+)', original, re_mod.MULTILINE))
    new_classes  = set(re_mod.findall(r'^\s*class\s+(\w+)', new_content, re_mod.MULTILINE))
    if len(new_classes) < len(orig_classes):
        lost = orig_classes - new_classes
        if lost:
            parts.append(f"类: {', '.join(sorted(lost))}")
    return "替换将删除以下定义: " + "；".join(parts) if parts else ""


def _safety_short_old(old_string: str, mode: str, total_matches: int) -> str:
    """检测过短old_string批量替换风险 — 小沈 2026-07-08 — 小欧 2026-07-11 replace_all→mode"""
    if mode == "all" and len(old_string) <= 2 and total_matches >= 5:
        return f"old_string仅{len(old_string)}字符，all模式匹配{total_matches}处，请确认"
    return ""


_WIDE_REPLACE_MAX = 5
_DANGEROUS_ANCHORS = ('"""', "'''")

def _is_dangerous_anchor(old_string: str) -> bool:
    """old_string 是否命中 docstring 边界(三引号) — 小欧 2026-07-17"""
    return old_string.strip() in _DANGEROUS_ANCHORS


def _safety_wide_replace(old_string: str, mode: str, total_matches: int) -> str:
    """all 模式宽匹配 warning — 小欧 2026-07-17 — 三引号拒绝见 _is_dangerous_anchor+内联"""
    if mode != "all":
        return ""
    if total_matches > _WIDE_REPLACE_MAX:
        return f"all匹配{total_matches}处(>阈值{_WIDE_REPLACE_MAX}), 建议改用once/count或缩小old_string"
    return ""


def _build_edit_text_file_llm_data(
    exec_code: str, duration_ms: int,
    file_path: str = "", applied: int = 0, total: int = 0, detail: str = "",
    diff: str = "", total_matches: int = 0, mtime_warning: str = "",
    hint: str = "", safety_hint: str = "",
    user_old_string: str = "", user_new_string: str = "",
    user_mode: str = "", user_ignore_case: Optional[bool] = None,
    user_encoding: Optional[str] = None,
) -> Dict[str, Any]:
    """edit_text_file的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小欧 2026-07-05 增加diff/total_matches/mtime_warning — 小沈 2026-07-05 新增hint参数 — 小欧 2026-07-06 diff移入other_data — 小欧 2026-07-06 diff移回metrics — 小欧 2026-07-11 replace_all→mode"""
    _act_params = {"path": file_path}
    if user_old_string:
        _act_params["old_string"] = user_old_string
    if user_new_string:
        _act_params["new_string"] = user_new_string
    if user_mode and user_mode != "once":
        _act_params["mode"] = user_mode
    if user_ignore_case is not None:
        _act_params["ignore_case"] = user_ignore_case
    if user_encoding:
        _act_params["encoding"] = user_encoding
    if exec_code == "error":
        return {
            "summary": f"编辑文件{file_path}，失败",
            "action": {"tool": "edittext", "tool_zh": "编辑文件", "target": file_path, "params": _act_params},
            "status": {"exec_code": "error", "message": "编辑失败", "code": ERR_FILE_EDIT_FAILED, "detail": detail, "hint": hint if hint else "请检查文件路径和编辑参数"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    _hint_parts = []
    if mtime_warning:
        _hint_parts.append(mtime_warning)
    if safety_hint:
        _hint_parts.append(safety_hint)
    _warning_msg = ""
    if total_matches > applied:
        _remaining = total_matches - applied
        _warning_msg = f"剩余{_remaining}处未修改"
        _hint_parts.append("建议使用 mode='all' 一次替换所有匹配")
    _hint = "；".join(_hint_parts) if _hint_parts else ""
    _exec_code = "warning" if (_warning_msg or mtime_warning or safety_hint) else "success"
    if _exec_code == "warning":
        _summary = f"编辑文件{file_path}，成功,提示说明: 替换 {applied}/{total_matches} 处"
        if _warning_msg:
            _summary += f"，注意: {_warning_msg}"
    else:
        _summary = f"编辑文件{file_path}，成功: 替换 {applied}/{total_matches} 处"
    return {
        "summary": _summary,
        "action": {"tool": "edittext", "tool_zh": "编辑文件", "target": file_path, "params": _act_params},
        "status": {"exec_code": _exec_code, "message": "编辑完成", "code": "", "detail": _warning_msg, "hint": _hint},
        "duration_ms": duration_ms,
        "metrics": {
            "applied": {"value": applied, "text": f"{applied}/{total}处"},
            "total_matches": {"value": total_matches, "text": f"共{total_matches}处"},
        },
    }


async def _precise_replace_in_file(
    file_path: str, old_string: str, new_string: str,
    mode: str = "once", ignore_case: bool = False,
    dry_run: bool = False, encoding: Optional[str] = None,
) -> Dict[str, Any]:
    """精确替换文件中的字符串(返回原始dict,不含build3/llm_data) — 小欧 2026-06-22 — 小欧 2026-07-11 replace_all→mode"""
    if not old_string:
        return {"error_detail": "old_string不能为空"}

    task_id = _current_task_id.get(None)
    if not task_id:
        return {"error_detail": "当前没有活跃任务ID"}

    try:
        _anchor_hint = ""  # before/after 签名行锚点提示, 统一初始化防 NameError — 小欧 2026-08-08
        # 工具层校验：非空/保留字符/保留名/系统目录/文件存在+是文件 — 小欧 2026-07-04
        # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
        is_valid, err, warn = validate_path(OpCategory.READ_FILE, file_path, content=new_string)
        if not is_valid:
            return {"error_detail": err}
        if warn:
            logger.warning(f"[edittext] {warn}")

        path = Path(file_path).resolve()
        _long = to_win_long_path(path)  # #5长路径: stat/read/open 统一 \\?\ 前缀 — 小欧 2026-08-13
        if Path(_long).stat().st_size > EDITTEXT_INPUT_MAX_BYTES:
            return {"error_detail": f"文件过大({Path(_long).stat().st_size}字节)", "file_size": Path(_long).stat().st_size}

        # B2 fix: detect CRLF from raw bytes — 小欧 2026-06-27
        _has_crlf = False
        try:
            _raw = Path(_long).read_bytes()[:8192]
            _has_crlf = b'\r\n' in _raw
        except Exception:
            pass

        content, used_enc, err_msg = await _try_read_file_with_encodings(Path(_long), encoding)
        if err_msg:
            raise ValueError(err_msg)
        # 编码回退反馈: 用户指定编码但实际以其它编码读取成功 → 生成提示(LLM可见, 增强不退化) — 小欧 2026-08-09
        # 注意: 不能改 _try_read_file_with_encodings 第三参数(err_msg非None即raise, 会导致回退成功变失败)
        _encoding_fallback = ""
        if encoding and used_enc and used_enc != encoding:
            _encoding_fallback = f"指定编码 '{encoding}' 无效或无法解码，已回退使用 '{used_enc}' 读取"
        record_read(file_path, content)

        # 编码预检移入 _replace_sync：验完整落盘内容(write_content)，
        # 覆盖 new_string + 原文 errors='replace' 残留的 U+FFFD，且在 open('w') 截断前失败 — 小欧 2026-07-11

        conflict_err = check_conflict_strict(file_path)
        if conflict_err:
            try:
                _preview = Path(_long).read_text("utf-8", errors="replace")[:2000]  # #5长路径 — 小欧 2026-08-13
                conflict_err += f"\n文件当前内容(前2000字符):\n{_preview}"
            except Exception:
                pass
            return {"error_detail": conflict_err}

        # 无操作跳过（仅replace模式，插入模式即使内容相同也改变文件） — 小欧 2026-07-11
        if old_string == new_string and mode in ("once", "all"):
            total_matches = content.count(old_string) if mode == "all" else (1 if old_string in content else 0)
            return {
                "file_path": str(path),
                "applied_edits": 0, "total_edits": 0,
                "total_matches": total_matches,
                "diff": "", "skipped": True,
                "encoding_fallback": _encoding_fallback,  # 编码回退提示 — 小欧 2026-08-09
            }

        # before/after 模式：new_string 不能为空(插入空内容无意义,否则误报成功) — 小欧 2026-07-11
        if mode in ("before", "after") and new_string == "":
            return {"error_detail": f"mode={mode} 需要非空 new_string（插入内容不能为空）"}

        # before/after 模式：校验唯一匹配 — 小欧 2026-07-11
        if mode in ("before", "after"):
            if ignore_case:
                total_matches = len(re_mod.findall(re_mod.escape(old_string), content, re_mod.IGNORECASE))
            else:
                total_matches = content.count(old_string)
            if total_matches == 0:
                return {"error_detail": f"未找到匹配内容: '{old_string}'（mode={mode}）"}
            if total_matches > 1:
                return {"error_detail": f"before/after模式要求唯一匹配，old_string在文件中出现{total_matches}次，请提供更多上下文以精确定位"}
            # before/after 锚点重叠检查 — 小欧 2026-07-17
            _overlap_err = _check_anchor_overlap(mode, old_string, new_string)
            if _overlap_err:
                return {"error_detail": _overlap_err}

            # 签名行锚点提示: def/class 单行签名作为 before/after 锚点时,
            # 插入位置为签名行后/前而非常规方法体之后, 易错位. 引导使用完整方法体末行锚点 — 小欧 2026-08-08 (task002问题1)
            _anchor_hint = _anchor_signature_hint(old_string)

        _hooks = get_current_hooks_or_noop()  # A1: ContextVar 取安全 hooks(BUG-3修复: _or_noop 兜底防 NPE) — 小沈 2026-08-13
        operation_id = _hooks.record_operation(
            task_id=task_id, operation_type=OperationType.MODIFY,
            destination_path=path, sequence_number=0,
        )

        replace_result = {}
        if mode in ("before", "after") and _anchor_hint:
            replace_result['safety_hint'] = _anchor_hint

        def _replace_sync() -> bool:
            new_content, count, total_matches = _apply_replacement(content, old_string, new_string, ignore_case, mode)
            # 模糊回退: mode=once精确匹配失败时尝试escape_normalized — 小欧 2026-07-11
            if count == 0 and mode == "once" and not ignore_case:
                fuzzy_content, fuzzy_count, fuzzy_total, fuzzy_err = fuzzy_find_replace(
                    content, old_string, new_string
                )
                if fuzzy_count > 0:
                    new_content, count, total_matches = fuzzy_content, fuzzy_count, fuzzy_total
            replace_result['count'] = count
            replace_result['total_matches'] = total_matches
            if dry_run:
                return True
            if count == 0:
                lines = content.split('\n')
                preview = '\n'.join(lines[:15])
                replace_result['content_preview'] = preview
                replace_result['total_lines'] = len(lines)
                return False
            replace_result['diff'] = ''.join(difflib.unified_diff(
                content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=str(path), tofile=str(path),
                n=3,
            ))
            sl_warn = _safety_structure_loss(content, new_content)
            so_warn = _safety_short_old(old_string, mode, total_matches)
            if sl_warn or so_warn:
                # 与签名行锚点提示合并, 不覆盖 (task002问题1增强) — 小欧 2026-08-08
                replace_result['safety_hint'] = "；".join(filter(None, [_anchor_hint, sl_warn, so_warn]))
            # all 模式宽匹配/边界检查 — 小欧 2026-07-17
            if mode == "all":
                wr_warn = _safety_wide_replace(old_string, mode, total_matches)
                if wr_warn:
                    _cur_hint = replace_result.get('safety_hint', '')
                    replace_result['safety_hint'] = "；".join(filter(None, [_cur_hint, wr_warn]))
                # 确定破坏(三引号) → 拒绝写入
                if _is_dangerous_anchor(old_string):
                    replace_result['validation_error'] = (
                        f"拒绝 all 模式对 docstring 边界('{old_string}')的替换——将破坏所有文档字符串。"
                        f"请用 mode='once'+含上下文的精确 old_string 替换目标行"
                    )
                    return False
            write_content = new_content.replace('\n', '\r\n') if _has_crlf else new_content
            # 完整编码预检：验落盘全文,含原文残留U+FFFD,赶在open('w')截断前失败 — 小欧 2026-07-11
            try:
                write_content.encode(used_enc)
            except UnicodeEncodeError as e:
                replace_result['validation_error'] = f"替换后内容含编码 {used_enc} 不支持的字符: {e}"
                return False
            # 语法校验 — 统一模块; 任意模式完整文件语法错→拒绝写入(防写坏) — 小欧 2026-07-21 — 小欧 2026-07-29 优化error_text带行号+建议
            if not replace_result.get('validation_error'):
                _syn = validate_syntax(new_content, detect_language(str(path), new_content), str(path))
                if not _syn.valid:
                    _parts = [_syn.error or "语法错误"]
                    if _syn.line:
                        _parts.insert(0, f"行{_syn.line}")
                    if _syn.suggestion:
                        _parts.append(f"建议:{_syn.suggestion}")
                    replace_result['validation_error'] = "；".join(_parts)
                    replace_result['_syn_line'] = _syn.line
                    replace_result['_syn_suggestion'] = _syn.suggestion
                    return False
            with open(_long, 'w', encoding=used_enc, newline='') as f:  # #5长路径 — 小欧 2026-08-13
                f.write(write_content)
            record_write(file_path)
            return True

        # 根据operation_id是否存在选择执行方式 — 小健 2026-06-24
        if operation_id:
            raw = await asyncio.to_thread(_hooks.execute_with_safety, operation_id, operation_func=_replace_sync)
            success, _ = raw if isinstance(raw, tuple) else (raw, "")
        else:
            logger.info("Database unavailable, executing edit operation without recording")
            success = await asyncio.to_thread(_replace_sync)

        count = replace_result.get('count', 0)

        # 优先处理编码失败(count!=0但写入被拦),避免误判为"未找到匹配" — 小欧 2026-07-11
        if replace_result.get('validation_error'):
            _err = replace_result['validation_error']
            _line = replace_result.get('_syn_line')
            _sugg = replace_result.get('_syn_suggestion')
            _ret = {"error_detail": _err}
            if _line:
                _ret["_syn_line"] = _line
            if _sugg:
                _ret["_syn_suggestion"] = _sugg
            return _ret

        if not success or count == 0:
            preview = replace_result.get('content_preview', '')
            total_lines = replace_result.get('total_lines', 0)
            if total_lines == 1 and not content.strip():
                return {"error_detail": f"未找到匹配内容: 文件为空"}
            _ed = f"未找到匹配内容: '{old_string}'。文件共{total_lines}行，前15行:\n{preview}"
            if mode == "once" and count == 0 and new_string and new_string in content:
                _ed += "。提示: new_string 在文件中但 old_string 未找到，可能参数填反"
            return {
                "error_detail": _ed,
            }

        return {
            "file_path": str(path),  # 小欧 2026-07-16 移除未消费的 operation_id(YAGNI)
            "applied_edits": count, "total_edits": count,
            "total_matches": replace_result.get("total_matches", count),
            "diff": replace_result.get("diff", ""),
            "safety_hint": replace_result.get("safety_hint", ""),
            "encoding_fallback": _encoding_fallback,  # 编码回退提示 — 小欧 2026-08-09
        }

    except Exception as e:
        logger.error(f"edittext failed: {file_path}: {e}")
        return {"error_detail": str(e), "hint": hint_for_write_error(e, Path(file_path).name)}  # 统一错误提示 - 小欧 2026-07-12


async def edittext(
    path: str,
    old_string: str,
    new_string: str = "",
    mode: str = "once",
    ignore_case: bool = False,
    encoding: Optional[str] = None,
) -> Dict[str, Any]:
    """编辑文本文件 — 小健 2026-06-20 删dry_run参数 — 小欧 2026-06-22 独立文件 — 小欧 2026-06-24 增加ignore_case参数 — 小欧 2026-07-11 replace_all→mode — 小欧 2026-07-11 路径参数统一为path"""
    # 路径参数统一为path,桥接到内部变量file_path — 小欧 2026-07-11
    file_path = path
    t0 = _time_mod.perf_counter()

    # None/空校验必须先于截断 — 小欧 2026-07-25 修复截断先于None检查的预存bug
    if old_string is None:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_edit_text_file_llm_data("error", duration_ms, file_path=file_path, detail="old_string不能为None", user_old_string="", user_new_string="", user_mode=mode, user_ignore_case=ignore_case, user_encoding=encoding)
        return build_error(data={}, llm_data=llm_data)
    if new_string is None:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_edit_text_file_llm_data("error", duration_ms, file_path=file_path, detail="new_string不能为None", user_old_string="", user_new_string="", user_mode=mode, user_ignore_case=ignore_case, user_encoding=encoding)
        return build_error(data={}, llm_data=llm_data)
    if not old_string:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_edit_text_file_llm_data("error", duration_ms, file_path=file_path, detail="old_string不能为空字符串", user_old_string="", user_new_string="", user_mode=mode, user_ignore_case=ignore_case, user_encoding=encoding)
        return build_error(data={}, llm_data=llm_data)

    # main函数入口统一截断(helper/build函数均不截断) — 小欧 2026-07-24
    _old_preview = old_string[:EDITTEXT_OUTPARM_LIMIT_OLD]
    _new_preview = new_string[:EDITTEXT_OUTPARM_LIMIT_NEW]

    # mode 有效性检查 — 小欧 2026-07-11
    if mode not in ("once", "all", "before", "after"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_edit_text_file_llm_data("error", duration_ms, file_path=file_path, detail=f"无效mode: '{mode}'，可选值: once, all, before, after", user_old_string=_old_preview, user_new_string=_new_preview, user_mode=mode, user_ignore_case=ignore_case, user_encoding=encoding)
        return build_error(data={}, llm_data=llm_data)

    if '\x00' in file_path:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_edit_text_file_llm_data("error", duration_ms, file_path=file_path, detail="file_path包含空字节", user_old_string=_old_preview, user_new_string=_new_preview, user_mode=mode, user_ignore_case=ignore_case, user_encoding=encoding)
        return build_error(data={}, llm_data=llm_data)

    # 文件类型检查 — 北京老陈 2026-07-09
    ft_valid, ft_detail, ft_tool = check_for_text_tool(file_path, check_content=True)
    if not ft_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        if ft_tool:
            _hint = f"建议使用{ft_tool}工具"
        elif ft_tool == "":
            _hint = "请检查文件路径和文件名是否正确"
        else:
            _hint = "请选择正确的工具类型"
        llm_data = _build_edit_text_file_llm_data("error", duration_ms, file_path=file_path, detail=ft_detail, hint=_hint, user_old_string=_old_preview, user_new_string=_new_preview, user_mode=mode, user_ignore_case=ignore_case, user_encoding=encoding)
        return build_error(
            data={"error_detail": ft_detail, "params": {"path": file_path}},
            llm_data=llm_data,
        )

    dry_run = False
    result = await _precise_replace_in_file(
        file_path=file_path, old_string=old_string, new_string=new_string,
        mode=mode, ignore_case=ignore_case,
        dry_run=dry_run, encoding=encoding,
    )
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
    # 语法错误/其他错误处理 — 小欧 2026-07-29 加metrics error_line+suggestion
    error_detail = result.get("error_detail")
    if error_detail:
        llm_data = _build_edit_text_file_llm_data("error", duration_ms, file_path=file_path, detail=error_detail, hint=result.get("hint"), user_old_string=_old_preview, user_new_string=_new_preview, user_mode=mode, user_ignore_case=ignore_case, user_encoding=encoding)  # 统一错误提示 - 小欧 2026-07-12
        _syn_line = result.get("_syn_line")
        _syn_sugg = result.get("_syn_suggestion")
        if _syn_line:
            llm_data["metrics"]["error_line"] = {"value": _syn_line, "text": f"第{_syn_line}行"}
        if _syn_sugg:
            llm_data["metrics"]["suggestion"] = {"value": _syn_sugg, "text": _syn_sugg}
        return build_error(
            data={"error_detail": error_detail, "params": {"path": file_path}},
            llm_data=llm_data,
        )
    # P1修正(2026-08-09 - 小欧): 编码回退提示改放尾部, 优先保safety_hint完整(原200上限行为不变),
    #   回退文案可截断(仅降级本轮新增提示, 不退化原安全提示); 边界: 单者存在不带多余";"
    _sh = result.get("safety_hint", "") or ""
    _fb = result.get("encoding_fallback", "") or ""
    _merged_hint = f"{_sh}；{_fb}" if (_sh and _fb) else (_sh or _fb)
    llm_data = _build_edit_text_file_llm_data(
        "success", duration_ms, file_path=file_path,
        applied=result.get("applied_edits", 0), total=result.get("total_edits", 0),
        diff=result.get("diff", ""),
        total_matches=result.get("total_matches", 0),
        mtime_warning=result.get("mtime_warning", "") or "",
        safety_hint=_merged_hint[:EDITTEXT_OUTPARM_LIMIT_SAFETY],  # 编码回退并入safety_hint(LLM可见) — 小欧 2026-08-09
        user_old_string=_old_preview, user_new_string=_new_preview,
        user_mode=mode, user_ignore_case=ignore_case,
        user_encoding=encoding,
    )
    # ---- observation_formatter route -------------------------------------------
    # branch: #21 fallback (key:val)
    # trigger: 无上述20条分支匹配 — result 含 applied_edits/diff，不命中任何专用分支
    # handler: _format_scalar_data(data) — key | value 单行列表
    # file:    observation_formatter.py:214
    # ------------------------------------------------------------------------------
    # =============================================================================
    # 数据设计三档：
    #   完全成功 (applied == total_matches > 0)  → data={}
    #   部分成功 (applied < total_matches, applied>0) → data={"diff": ...}
    #   跳过/无操作 (skipped 或 applied==0)       → data={}
    # — 小欧 2026-07-06 21:00:00
    # =============================================================================
    _applied = llm_data["metrics"]["applied"]["value"]
    _total_matches = llm_data["metrics"]["total_matches"]["value"]
    _skipped = result.get("skipped", False)
    if _skipped or _applied == 0:
        data = {}
    else:
        # diff 统一经 data["diff"] → #24(已行×列收口+两态); 不在 llm_data 顶层重复渲染(严禁重复)
        data = {"diff": result.get("diff", "")}
    return build_success(data=data, llm_data=llm_data)


# 本地 mtime 缓存已于 2026-07-05 迁移到 file/file_state.py — 小欧
