
# -*- coding: utf-8 -*-
"""语法检测统一模块 — 小欧 2026-07-21
编辑历史:
# 2026-07-21 - 小欧 - 新建: 统一语法检测唯一真源; 注册表分发(VALIDATORS), 新增语言=加 _CODE_EXT+VALIDATORS 一行, 满足OCP/复用优先
# 2026-07-21 - 小欧 - Phase1: python(compile)/json(json.loads)/yaml(yaml.safe_load,懒加载); 未知语言放行避免误杀文本文件
    # 2026-07-21 - 小欧 - 由 app/utils/ 迁至 app/tools/toolhelper/(工具层共享函数合规落点)
    # 2026-07-21 - 小欧 - 修BOM隐患: 抽 _strip_bom()(转义\ufeff替代源码字面量BOM, DRY消除json/yaml两处重复), 符合KISS-DIRECT/DRY/SRP
    # 2026-07-24 - 小欧 - 修复: 去掉 str(e)[:120]截断(helper层不截断,调用方自行决定) — 北京老陈驱动
    # 2026-10-12 - 小欧 - 增 toml(tomllib,标准库)/xml(xml.etree,标准库): 零外部依赖、解析严格零方言,
    #   误判率极低且写坏后果严重(pyproject/CI 配置失效整个工具链起不来); 沿用 OCP 各注册一行, 调用方零改动
    #   同批: 新增 _syntax_enabled, 按设置「沙箱›工具›语法检测」的总开关+每语言开关判定(默认全开)
    # 2026-10-13 - 小欧 - 修_node_check_js finally引用前未定义: _tmp防御式初始化None+if守卫再unlink, 防校验异常路径NameError掩盖原错 — 小欧 2026-10-13
    """

# ═══════════════════════════════════════════════════════════════════════════
# 设计策略与逻辑(精要) — 小欧 2026-07-21
# ═══════════════════════════════════════════════════════════════════════════
# 【目标】防 LLM 把代码文件写坏(编辑/写入后语法错误落盘)
#
# 【原则】不自己写解析器; 全部调用语言官方/成熟库; 零新增依赖; 可扩展(OCP)
#   校验器复用标准库: python→compile()(CPython官方解析器)
#                   json→json.loads()   yaml→yaml.safe_load()(懒加载避免硬依赖)
#
# 【现行策略: 全部仅告警, 照常落盘】(2026-10-12 北京老陈定案, 原为"edit/write 整文件写=阻断")
#   理由: 本检查是启发式, 存在误判; 误判即拦死合法写入, 代价高于提示价值。
#   edit/write(整文件与追加) → 均仅 warning, 文件照落盘, detail 载错因+hint 给修正出路。
#   未知扩展名(.md/.csv/.txt) → 放行(无语法可言, 防误杀)
#
# 【误杀防护】仅对可解析语言校验; 不引入风格类lint
#
# 【涉及的其他语法检测代码/工具 — 哪些加 / 哪些不加】
#   本仓库现有(逐个点名):
#     · tool_fc_helper.validate_python_content   →【加】已被本模块取代(删除该死代码, 统一到 validate_syntax)
#     · edit_text_file.py 内联 compile 块        →【加】已被本模块取代(改调 validate_syntax, 消除重复)
#     · tool_fc_helper._SimpleHTMLValidator / validate_html_content →【加】Phase2 经 VALIDATORS 注册接入(复用, 不重写)
#     · 标准库 compile / json.loads / yaml.safe_load →【加】Phase1 已用(官方实现, 必用)
#   本仓库现有但【不加 / 保持独立】(不并入写文件硬阻断层):
#     · validate_xml_content / validate_csv_content(tool_fc_helper) → 数据格式校验, 非代码语法, 不并入
#       ▲2026-10-12 小欧(北京老陈令) 例外: XML 已并入(VALIDATORS 注册, 标准库零依赖且解析严格);
#         阻断层已降级为告警(见 write/edit 同批改动), 误判代价大幅降低, 故按告警层重新评估
#     · check_content_safety(file_safety_checker) → 内容安全检查(None/空/null字节/类型), 职责不同;
#                                                    本模块是其之上的"新增语法层", 不替换、不耦合
#     · execute_sql.py 的 syntax_valid → SQL 专用校验, 属 execute_sql 工具内部, 不并入通用写文件护栏
#   外部 lint 库【不加进硬阻断】:
#     · ruff / pyflakes → 轻量lint, 多抓"未定义名"但也会拦"未用导入"等合法可运行代码(误杀);
#                         仅可作可选【非阻断 warning】层(须关掉风格规则), 不进硬阻断
#     · pylint / mypy  → 重型/慢/噪音大/需类型标注, 绝不适合每次写文件实时跑, 不接
#   一句话: 硬阻断只用"能否解析"(标准库+本仓库既有校验器); 数据格式/内容安全/SQL/风格语义lint 一律不并入硬阻断
# ═══════════════════════════════════════════════════════════════════════════

import os  # node --check 兜底路径的临时文件清理 — 小欧 2026-10-12
from dataclasses import dataclass
from typing import Callable, Optional

# 扩展名 → 语言键(新增语言在此加一行, 零侵入) — 小欧 2026-07-21
_CODE_EXT = {
    ".py": "python", ".pyw": "python", ".pyi": "python",
    ".json": "json",
    ".yaml": "yaml", ".yml": "yaml",
    # 2026-10-12 小欧(北京老陈令) - 增 TOML/XML: 均为标准库可校验、解析严格零方言(误判率极低),
    #   且写坏后果严重(pyproject/CI 配置失效整个工具链起不来), 早提示价值高
    ".toml": "toml",
    ".xml": "xml",
    # 2026-10-12 小欧(北京老陈令) - JS/TS 系扩展名: 由 tree-sitter 解析(主) / node --check 兜底(A方案)
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "tsx",
}

# JS/TS 校验器懒加载缓存 — 小欧 2026-10-12
# tree-sitter 为主(覆盖 JS/JSX/TS/TSX, 不依赖 Node); 装不上时 .js/.mjs/.cjs 退回 node --check
_JS_LANG = None
_TS_LANG = None
_TSX_LANG = None
_TS_TRIED = False


def _load_ts_languages():
    """懒加载 tree-sitter 三语言(JS/TS/TSX); 任一失败返回 None 走降级 — 小欧 2026-10-12"""
    global _JS_LANG, _TS_LANG, _TSX_LANG, _TS_TRIED
    if _TS_TRIED:
        return _JS_LANG, _TS_LANG, _TSX_LANG
    _TS_TRIED = True
    try:
        from tree_sitter import Language
        import tree_sitter_javascript as _tsjs
        import tree_sitter_typescript as _tsts
        _JS_LANG = Language(_tsjs.language())
        _TS_LANG = Language(_tsts.language_typescript())
        _TSX_LANG = Language(_tsts.language_tsx())
    except Exception as _e:  # 未安装/动态库不可用 → 软降级, 不阻断工具
        _JS_LANG = _TS_LANG = _TSX_LANG = None
    return _JS_LANG, _TS_LANG, _TSX_LANG


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


def _validate_toml(content: str, file_path: Optional[str] = None) -> SyntaxCheckResult:
    """TOML 语法校验(tomllib, Python3.11+ 标准库, 零外部依赖) — 小欧 2026-10-12"""
    try:
        import tomllib
        # 去 BOM, 同 json/yaml 避免 Windows 保存产物被误判 — 小欧 2026-10-12
        tomllib.loads(_strip_bom(content))
        return SyntaxCheckResult(valid=True, language="toml")
    except Exception as e:
        return SyntaxCheckResult(valid=False, language="toml", error=f"TOML语法错误: {str(e)}")


def _validate_xml(content: str, file_path: Optional[str] = None) -> SyntaxCheckResult:
    """XML 语法校验(xml.etree, 标准库) — 小欧 2026-10-12"""
    try:
        from xml.etree import ElementTree
        ElementTree.fromstring(_strip_bom(content))
        return SyntaxCheckResult(valid=True, language="xml")
    except Exception as e:
        return SyntaxCheckResult(valid=False, language="xml", error=f"XML语法错误: {str(e)}")


def _ts_syntax_errors(content: str, lang) -> list:
    """返回 tree-sitter 解析错误节点 [(行号, 类型)] — 小欧 2026-10-12"""
    from tree_sitter import Parser
    _tree = Parser(lang).parse(content.encode("utf-8"))
    if not _tree.root_node.has_error:
        return []
    _out = []
    _stack = [_tree.root_node]
    while _stack:
        _n = _stack.pop()
        if _n.type == "ERROR" or _n.is_missing:
            _out.append((_n.start_point[0] + 1, _n.type))
        _stack.extend(_n.children)
    return _out[:3]  # 最多取前3处, 避免长文噪声


def _node_check_js(content: str, file_path: Optional[str] = None):
    """A方案兜底: node --check 校验 JS(仅做语法解析不执行) — 小欧 2026-10-12"""
    import shutil, subprocess, tempfile
    _node = shutil.which("node")
    if not _node:
        return None  # 无 Node → 跳过(等价放行)
    _tmp = None  # 防御式初始化: finally块引用前确保已定义 — 小欧 2026-10-12
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as _f:
            _f.write(content)
            _tmp = _f.name
        _r = subprocess.run([_node, "--check", _tmp], capture_output=True, text=True,
                            timeout=10, encoding="utf-8", errors="replace")
        return (_r.returncode == 0), (_r.stderr or "").strip()
    except Exception:
        return None
    finally:
        try:
            if _tmp:
                os.unlink(_tmp)
        except Exception:
            pass


def _validate_js_family(content: str, file_path: Optional[str] = None) -> SyntaxCheckResult:
    """JS/JSX/TS/TSX 语法校验 — 小欧 2026-10-12

    主: tree-sitter(全覆盖, 不依赖 Node); 备: node --check(仅 .js 系, tree-sitter 不可用时兜底)
    注: 语言由 file_path 扩展名推得(VALIDATORS 统一契约是 (content, file_path), 不可加第三参)
    """
    language = detect_language(file_path or "") or "javascript"
    _js, _ts, _tsx = _load_ts_languages()
    _lang = {"javascript": _js, "typescript": _ts, "tsx": _tsx}.get(language)
    if _lang is not None:
        _errs = _ts_syntax_errors(content, _lang)
        if not _errs:
            return SyntaxCheckResult(valid=True, language=language)
        _desc = {"javascript": "JavaScript", "typescript": "TypeScript", "tsx": "TSX"}[language]
        return SyntaxCheckResult(
            valid=False, language=language, line=_errs[0][0],
            error=f"{_desc}语法错误(行{_errs[0][0]}: {_errs[0][1]}"
                  + (f"等{len(_errs)}处" if len(_errs) > 1 else "") + ")",
        )
    if language == "javascript":  # A方案: tree-sitter 不可用时用 node --check 兜底
        _nc = _node_check_js(content, file_path)
        if _nc is None:
            return SyntaxCheckResult(valid=True, language=language)  # 无 Node 也跳过
        _ok, _msg = _nc
        if _ok:
            return SyntaxCheckResult(valid=True, language=language)
        return SyntaxCheckResult(valid=False, language=language, error=f"JavaScript语法错误: {_msg[:200]}")
    return SyntaxCheckResult(valid=True, language=language)  # TS/TSX 无 tree-sitter → 放行


# 语言 → 校验器(新增语言=在此注册一行, 满足OCP开闭原则) — 小欧 2026-07-21
VALIDATORS = {
    "python": _validate_python,
    "json": _validate_json,
    "yaml": _validate_yaml,
    "toml": _validate_toml,   # 2026-10-12 小欧 标准库 tomllib
    "xml": _validate_xml,     # 2026-10-12 小欧 标准库 xml.etree
    "javascript": _validate_js_family,  # 2026-10-12 小欧 tree-sitter 主 + node --check 备
    "typescript": _validate_js_family,
    "tsx": _validate_js_family,
}


def _syntax_enabled(language: str) -> bool:
    """查设置: sandbox.tool.syntax_check 总开关 + 每语言开关(默认全开) — 小欧 2026-10-12

    tsx 归typescript 开关(同一校验器族)。取配置失败一律 fail-open(放行), 绝不因读不到配置而阻断。
    """
    # 2026-10-12 小欧: language→配置键后缀映射; 新增语言时在此补一行
    _key = {"tsx": "typescript"}.get(language, language)
    try:
        from app.config import get_config as _cfg
        _base = "sandbox.tool.syntax_check"
        if not bool(_cfg().get(f"{_base}.enabled", True)):
            return False
        return bool(_cfg().get(f"{_base}.{_key}", True))
    except Exception as _e:
        return True  # 配置不可用 → fail-open


def validate_syntax(content: str, language: str, file_path: Optional[str] = None) -> SyntaxCheckResult:
    """统一语法校验入口 — 小欧 2026-07-21
    language: 'python' | 'json' | 'yaml' | 'toml' | 'xml' | 'javascript' | 'typescript' | 'tsx' | 'unknown'(放行)
    未支持语言一律 valid(放行), 避免误杀 .md/.csv/.txt 等文本文件
    开关(设置页「沙箱 › 工具 › 语法检测」): 本函数为唯一判定点, 调用方无感知
    扩展新语言: 在 _CODE_EXT 加扩展名映射 + 在 VALIDATORS 注册校验函数 + 在 _syntax_enabled 补映射
    """
    if language == "unknown" or language not in VALIDATORS:
        return SyntaxCheckResult(valid=True, language=language)
    if not _syntax_enabled(language):
        return SyntaxCheckResult(valid=True, language=language)  # 该语言已关闭 → 放行
    try:
        return VALIDATORS[language](content, file_path)
    except Exception as e:
        # 校验器意外崩溃(如 RecursionError / RuntimeError)不应让工具 500,
        # 优雅降级为 invalid 并仅作 warning 上报(2026-10-12 起不再阻断落盘) — 小欧 2026-07-21 / 2026-10-12
        return SyntaxCheckResult(
            valid=False, language=language,
            error=f"校验器异常: {type(e).__name__}: {str(e)}",
        )

