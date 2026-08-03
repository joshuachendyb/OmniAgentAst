
# -*- coding: utf-8 -*-
"""语法检测统一模块 — 小欧 2026-07-21
编辑历史:
# 2026-07-21 - 小欧 - 新建: 统一语法检测唯一真源; 注册表分发(VALIDATORS), 新增语言=加 _CODE_EXT+VALIDATORS 一行, 满足OCP/复用优先
# 2026-07-21 - 小欧 - Phase1: python(compile)/json(json.loads)/yaml(yaml.safe_load,懒加载); 未知语言放行避免误杀文本文件
    # 2026-07-21 - 小欧 - 由 app/utils/ 迁至 app/tools/toolhelper/(工具层共享函数合规落点)
    # 2026-07-21 - 小欧 - 修BOM隐患: 抽 _strip_bom()(转义\ufeff替代源码字面量BOM, DRY消除json/yaml两处重复), 符合KISS-DIRECT/DRY/SRP
    # 2026-07-24 - 小欧 - 修复: 去掉 str(e)[:120]截断(helper层不截断,调用方自行决定) — 北京老陈驱动
    """

# ═══════════════════════════════════════════════════════════════════════════
# 设计策略与逻辑(精要) — 小欧 2026-07-21
# ═══════════════════════════════════════════════════════════════════════════
# 【目标】防 LLM 把代码文件写坏(BUG-002类: 编辑/写入后语法错误落盘)
#
# 【原则】不自己写解析器; 全部调用语言官方/成熟库; 零新增依赖; 可扩展(OCP)
#   校验器复用标准库: python→compile()(CPython官方解析器)
#                   json→json.loads()   yaml→yaml.safe_load()(懒加载避免硬依赖)
#
# 【阻断 vs 警告】
#   edittext 任意模式         → 阻断(每次结果都是完整文件, 语法错即损坏)
#   writetext append=False    → 阻断(整文件覆盖, 语法错=文件损坏)
#   writetext append=True     → 仅警告(片段无法整体校验, 且为增量)
#   未知扩展名(.md/.csv/.txt) → 放行(无语法可言, 防误杀)
#
# 【误杀防护】仅对可解析语言校验; 追加模式不阻断; 不引入风格类lint
#
# 【涉及的其他语法检测代码/工具 — 哪些加 / 哪些不加】
#   本仓库现有(逐个点名):
#     · tool_fc_helper.validate_python_content   →【加】已被本模块取代(删除该死代码, 统一到 validate_syntax)
#     · edit_text_file.py 内联 compile 块        →【加】已被本模块取代(改调 validate_syntax, 消除重复)
#     · tool_fc_helper._SimpleHTMLValidator / validate_html_content →【加】Phase2 经 VALIDATORS 注册接入(复用, 不重写)
#     · 标准库 compile / json.loads / yaml.safe_load →【加】Phase1 已用(官方实现, 必用)
#   本仓库现有但【不加 / 保持独立】(不并入写文件硬阻断层):
#     · validate_xml_content / validate_csv_content(tool_fc_helper) → 数据格式校验, 非代码语法, 不并入
#     · check_content_safety(file_safety_checker) → 内容安全检查(None/空/null字节/类型), 职责不同;
#                                                    本模块是其之上的"新增语法层", 不替换、不耦合
#     · execute_sql.py 的 syntax_valid → SQL 专用校验, 属 execute_sql 工具内部, 不并入通用写文件护栏
#   外部 lint 库【不加进硬阻断】:
#     · ruff / pyflakes → 轻量lint, 多抓"未定义名"但也会拦"未用导入"等合法可运行代码(误杀);
#                         仅可作可选【非阻断 warning】层(须关掉风格规则), 不进硬阻断
#     · pylint / mypy  → 重型/慢/噪音大/需类型标注, 绝不适合每次写文件实时跑, 不接
#   一句话: 硬阻断只用"能否解析"(标准库+本仓库既有校验器); 数据格式/内容安全/SQL/风格语义lint 一律不并入硬阻断
# ═══════════════════════════════════════════════════════════════════════════

from dataclasses import dataclass
from typing import Callable, Optional

# 扩展名 → 语言键(新增语言在此加一行, 零侵入) — 小欧 2026-07-21
_CODE_EXT = {
    ".py": "python", ".pyw": "python", ".pyi": "python",
    ".json": "json",
    ".yaml": "yaml", ".yml": "yaml",
}


@dataclass
class SyntaxCheckResult:
    """语法校验结果 — 小欧 2026-07-21"""
    valid: bool
    language: str = "unknown"
    error: Optional[str] = None
    line: Optional[int] = None
    suggestion: Optional[str] = None

    def error_text(self) -> str:
        """组装友好中文报错(含行号+建议) — 小欧 2026-07-21"""
        if self.valid:
            return ""
        parts = [self.error or "语法错误"]
        if self.suggestion:
            parts.append(f"建议:{self.suggestion}")
        return "；".join(parts)


def detect_language(file_path: str, content: str = "") -> str:
    """识别内容语言: 扩展名优先, fallback 头部 shebang; 未知返回 'unknown'(放行) — 小欧 2026-07-21"""
    if file_path:
        _lower = file_path.lower()
        for ext, lang in _CODE_EXT.items():
            if _lower.endswith(ext):
                return lang
    if content:
        _first = content.splitlines()[0] if content.splitlines() else ""
        if _first.startswith("#!") and "python" in _first:
            return "python"
    return "unknown"


def _strip_bom(content: str) -> str:
    """去除UTF-8 BOM头(\ufeff) — 小欧 2026-07-21
    用转义序列替代源码字面量BOM(防编辑器/编码转换吞掉); SRP: BOM处理单一落点, DRY消除json/yaml重复"""
    return content[1:] if content.startswith("\ufeff") else content


def _validate_python(content: str, file_path: Optional[str] = None) -> SyntaxCheckResult:
    """Python 语法校验(compile, CPython官方解析器) — 小欧 2026-07-21"""
    try:
        compile(content, file_path or "<string>", "exec")
        return SyntaxCheckResult(valid=True, language="python")
    except SyntaxError as e:
        suggestion = None
        if e.msg:
            if "unterminated string literal" in e.msg:
                suggestion = "转义字符串请使用raw string r'...', 如 r'\\\\' 代替 '\\\\'"
            elif "invalid character" in e.msg:
                suggestion = "Python不支持全角标点, 请使用半角括号()、逗号,、冒号:、分号;"
            elif "invalid escape sequence" in e.msg:
                suggestion = "请在字符串前加r前缀使用raw string, 或将转义字符双写如 \\d → r'\\d'"
        return SyntaxCheckResult(
            valid=False, language="python",
            error=f"Python语法错误(行{e.lineno}: {e.msg})",
            line=e.lineno, suggestion=suggestion,
        )


def _validate_json(content: str, file_path: Optional[str] = None) -> SyntaxCheckResult:
    """JSON 语法校验(json.loads, 官方实现) — 小欧 2026-07-21"""
    try:
        import json as _json
        # 去 BOM, 避免带 BOM 的 .json 被误判非法(常见 Windows 保存产物) — 小欧 2026-07-21
        _content = _strip_bom(content)
        _json.loads(_content)
        return SyntaxCheckResult(valid=True, language="json")
    except Exception as e:
        return SyntaxCheckResult(valid=False, language="json", error=f"JSON语法错误: {str(e)}")


def _validate_yaml(content: str, file_path: Optional[str] = None) -> SyntaxCheckResult:
    """YAML 语法校验(yaml.safe_load, 懒加载避免硬依赖) — 小欧 2026-07-21"""
    try:
        import yaml
        # 去 BOM, 同上避免误判 — 小欧 2026-07-21
        _content = _strip_bom(content)
        yaml.safe_load(_content)
        return SyntaxCheckResult(valid=True, language="yaml")
    except Exception as e:
        return SyntaxCheckResult(valid=False, language="yaml", error=f"YAML语法错误: {str(e)}")


# 语言 → 校验器(新增语言=在此注册一行, 满足OCP开闭原则) — 小欧 2026-07-21
VALIDATORS = {
    "python": _validate_python,
    "json": _validate_json,
    "yaml": _validate_yaml,
}


def validate_syntax(content: str, language: str, file_path: Optional[str] = None) -> SyntaxCheckResult:
    """统一语法校验入口 — 小欧 2026-07-21
    language: 'python' | 'json' | 'yaml' | 'unknown'(放行)
    未支持语言一律 valid(不拦截), 避免误杀 .md/.csv/.txt 等文本文件
    扩展新语言: 在 _CODE_EXT 加扩展名映射 + 在 VALIDATORS 注册校验函数, 调用方无感知
    """
    if language == "unknown" or language not in VALIDATORS:
        return SyntaxCheckResult(valid=True, language=language)
    try:
        return VALIDATORS[language](content, file_path)
    except Exception as e:
        # 校验器意外崩溃(如 RecursionError / RuntimeError)不应让工具 500,
        # 优雅降级为 invalid(阻断而非写坏), 避免 BUG-002 类损坏 — 小欧 2026-07-21
        return SyntaxCheckResult(
            valid=False, language=language,
            error=f"校验器异常: {type(e).__name__}: {str(e)}",
        )

