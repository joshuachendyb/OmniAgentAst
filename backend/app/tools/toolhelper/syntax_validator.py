# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-21 - 小欧 - 新建: 从 file/edit_text_file.py 抽出内联 compile() 校验为可复用模块(83379fbb)
#                  · BOM去扰: UTF-8 BOM(efbbbf)防SyntaxErrors/"invalid character"误报, 校验前strip — BUG-002
#                  · 多语言: python/json/yaml, 未知语言fail-open放行(防误杀文本文件)
#                  · OCP: VALIDATORS注册表, 新增语言仅加一行(调用方无感知)
#                  · 健壮性: 校验器抛非预期异常不500, 优雅判invalid
# 2026-07-21 - 小欧 - c4367cfb: BOM 字面量/字段语义统一(_strip_bom 返回纯str, error_text不含BOM残留); .pyw 不被.py吞
# 2026-07-24 - 小欧 - fbdbe775: 去掉 str(e) 截断, 交由调用方决定呈现
#
"""
python/json/yaml 语法校验 — 从 file/edit_text_file.py 抽出内联 compile() 为可复用模块 — 小欧 2026-07-21 (83379fbb)

职责单一(SRP): BOM-strip + 多语言 compile/parse + 结构化返回。不做截断、不做注册。

设计:
1. BOM去扰: UTF-8 BOM(efbbbf -> \\ufeff)会干扰SyntaxErrors/触发"invalid character"误报, 校验前strip — BUG-002
2. 多语言: python(compile) / json(json.loads) / yaml(yaml.safe_load); 未知语言fail-open放行
3. OCP: VALIDATORS注册表, 新增语言仅加一行(_CODE_EXT + VALIDATORS), 调用方无感知
4. 健壮性: 校验器抛非语法异常不500, 优雅返回 invalid(避免工具500)
5. 无 str(e) 截断: 调用方自行决定如何呈现(fbdbe775, 2026-07-24)

[注意] BUG-002 详情仅据 commit-message + test_bug002_repro_return_outside 推断(原树缺失):
      原内联版 compile(new_content, ...) 未strip BOM -> BOM 被误判为 invalid character;
      同类还有 'return outside function' 等 SyntaxError 未统一捕获。此模块先行strip+BOM去扰,
      并在 validate_syntax 外层兜底所有异常防止 500。
"""
import json
import os
from dataclasses import dataclass
from typing import Dict, Optional

import yaml  # PyYAML, requirements>=6.0


# UTF-8 BOM 字面量(Python str 形, 即 efbbbf 解码后) — 校验前去除, 防SyntaxErrors误报 — 小欧 2026-07-21
_UTF8_BOM = "\ufeff"


# 扩展名 -> 语言映射 (lookup 用 os.path.splitext, 区分大小写不敏感) — 小欧 2026-07-21
# c4367cfb: .pyw 独立映射(而非被 .py endswith 吞), 修正"字面量/字段语义"
_CODE_EXT: Dict[str, str] = {
    ".py": "python",
    ".pyw": "python",
    ".pyi": "python",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
}


def _strip_bom(content: str) -> str:
    """去除行首 UTF-8 BOM(efbbbf) — 小欧 2026-07-21 (BOM去扰 / BUG-002)

    字段语义(c4367cfb): 返回值类型始终为 str, 仅移除行首单个 BOM, 不改变其它任何字符。
    """
    if content and content[0] == _UTF8_BOM:
        return content[1:]
    return content


def detect_language(file_path: str = "", content: Optional[str] = None) -> str:
    """探测内容语言 — 小欧 2026-07-21

    优先按扩展名(_CODE_EXT, 大小写不敏感, 用 splitext 而非 endswith 以避免 .pyw 被 .py 吞);
    扩展名未命中且有 shebang(行首 #! 含 'python')时判为 python; 否则 unknown(fail-open)。
    """
    if file_path:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in _CODE_EXT:
            return _CODE_EXT[ext]
    if content:
        first_line = content.split("\n", 1)[0]
        if first_line.startswith("#!") and "python" in first_line:
            return "python"
    return "unknown"


@dataclass
class SyntaxCheckResult:
    """语法校验结果 — 小欧 2026-07-21

    字段语义: valid为bool, error/line/suggestion/language 均可为None。
    error_text() 统一组装对外呈现字串(含'行'/'语法'), 供 edit_text_file/writetext 的 encode_error/detail 复用。
    """
    valid: bool
    language: str = ""
    error: Optional[str] = None
    line: Optional[int] = None
    suggestion: Optional[str] = None

    def error_text(self) -> str:
        """组装对外错误文本 — 小欧 2026-07-21 (c4367cfb: line None 不崩, suggestion 可空)"""
        if self.valid:
            return ""
        segs = []
        if self.line is not None:
            segs.append(f"第{self.line}行")
        if self.error:
            segs.append(self.error)
        text = "".join(segs)
        if self.suggestion:
            text = f"{text}；建议:{self.suggestion}" if text else f"建议:{self.suggestion}"
        return text


def _validate_python(content: str, file_path: Optional[str] = None) -> SyntaxCheckResult:
    """python 校验: BOM-strip + compile(exec), 捕 SyntaxError/RecursionError — 小欧 2026-07-21 (BUG-002)"""
    clean = _strip_bom(content)
    try:
        compile(clean, file_path or "<string>", "exec")
        return SyntaxCheckResult(valid=True, language="python")
    except SyntaxError as e:
        error = f"Python语法错误: {e.msg}"
        suggestion: Optional[str] = None
        if "unterminated" in (e.msg or "") or "string literal" in (e.msg or ""):
            suggestion = "转义字符串请使用raw string r'...',如 r'\\\\' 代替 '\\\\'"
        elif "invalid character" in (e.msg or ""):
            suggestion = "Python不支持全角标点,请使用半角括号()、逗号,、冒号:、分号;"
        elif "invalid escape sequence" in (e.msg or ""):
            suggestion = "请在字符串前加r前缀使用raw string,或将转义字符双写如 \\d → r'\\d'"
        return SyntaxCheckResult(valid=False, language="python", error=error, line=e.lineno, suggestion=suggestion)
    except RecursionError:
        return SyntaxCheckResult(valid=False, language="python", error="Python语法错误: 递归嵌套过深(超过编译器限制)")


def _validate_json(content: str, file_path: Optional[str] = None) -> SyntaxCheckResult:
    """json 校验: BOM-strip + json.loads — 小欧 2026-07-21 (BOM去扰)"""
    clean = _strip_bom(content)
    try:
        json.loads(clean)
        return SyntaxCheckResult(valid=True, language="json")
    except ValueError as e:
        return SyntaxCheckResult(valid=False, language="json", error=f"JSON语法错误: {e}")


def _validate_yaml(content: str, file_path: Optional[str] = None) -> SyntaxCheckResult:
    """yaml 校验: BOM-strip + yaml.safe_load — 小欧 2026-07-21 (BOM去扰)"""
    clean = _strip_bom(content)
    try:
        yaml.safe_load(clean)
        return SyntaxCheckResult(valid=True, language="yaml")
    except yaml.YAMLError as e:
        return SyntaxCheckResult(valid=False, language="yaml", error=f"YAML语法错误: {e}")


# OCP: 新增语言仅在此注册一行, 调用方 validate_syntax 无感知 — 小欧 2026-07-21
VALIDATORS: Dict[str, callable] = {
    "python": _validate_python,
    "json": _validate_json,
    "yaml": _validate_yaml,
}


def validate_syntax(content: str, language: str, file_path: Optional[str] = None) -> SyntaxCheckResult:
    """多语言语法校验 — 小欧 2026-07-21 (83379fbb)

    Args:
        content: 源码/数据文本(可能含 UTF-8 BOM)。
        language: 语言标识(来自 detect_language 或调用方显式传入)。
        file_path: 用于 compile()/报错上下文。

    Returns:
        SyntaxCheckResult. unknown/unsupported 语言 fail-open(valid=True) — 防误杀文本文件。
        校验器抛非预期异常也不500, 优雅返回 invalid(健壮性, test_validator_raising_runtimeerror)。
    """
    validator = VALIDATORS.get(language)
    if validator is None:
        # fail-open: 未注册语言放行(防误杀 .md/.txt 等文本) — 小欧 2026-07-21
        return SyntaxCheckResult(valid=True, language=language)
    try:
        return validator(content, file_path)
    except Exception as e:
        # 健壮性: 校验器内部异常不应 500, 降级为 invalid — 小欧 2026-07-21
        return SyntaxCheckResult(valid=False, language=language, error=f"校验器异常: {type(e).__name__}: {e}")


__all__ = [
    "detect_language",
    "validate_syntax",
    "SyntaxCheckResult",
    "VALIDATORS",
    "_CODE_EXT",
    "_strip_bom",
]
