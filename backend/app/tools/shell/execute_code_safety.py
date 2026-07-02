# execute_code_safety.py — execute_code分级安全检查
# 小健 2026-06-27
#
# 三层防御：
#   第一层：正则规则匹配（RISK_CHECK_RULES，含用户输入组合检测）
#   第二层：AST别名检测（_resolve_import_aliases）
#   第三层：用户输入变量与危险函数组合升级（嵌入第一层内）

import ast
import re as re_mod
from typing import Any, Dict, List, Optional


class RiskLevel:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


RISK_CHECK_RULES: List[Dict[str, Any]] = [
    # ===== subprocess =====
    {
        "pattern": r"subprocess\.(run|call|Popen|check_output)\s*\(\s*\[[^\]]*?(python|node|python3)",
        "risk": RiskLevel.LOW,
        "desc": "执行解释器脚本（相对安全）",
        "allow": True,
    },
    {
        "pattern": r"subprocess\.(run|call|Popen|check_output)\s*\(\s*\[[^\]]*?\b(rm|del|format|shutdown|reboot)\b",
        "risk": RiskLevel.HIGH,
        "desc": "执行危险系统命令（列表形式）",
        "allow": False,
    },
    {
        "pattern": r"subprocess\.(run|call|Popen|check_output)\s*\(\s*[\'\"].*?\b(rm|del|format|shutdown|reboot)\b.*?shell\s*=\s*True",
        "risk": RiskLevel.HIGH,
        "desc": "执行危险系统命令（shell=True+危险命令）",
        "allow": False,
    },
    {
        "pattern": r"subprocess\.(run|call|Popen|check_output)\s*\((?!\s*\[[^\]]*?(?:python|node|python3))",
        "risk": RiskLevel.MEDIUM,
        "desc": "子进程调用（需审查）",
        "allow": True,
    },

    # ===== open/write =====
    {
        "pattern": r"open\s*\(.*[\'\"]w[bt\+]?[\'\"]",
        "risk": RiskLevel.MEDIUM,
        "desc": "文件写入操作（write模式）",
        "allow": True,
    },
    {
        "pattern": r"open\s*\(.*[\'\"]a[bt\+]?[\'\"]",
        "risk": RiskLevel.MEDIUM,
        "desc": "文件追加操作（append模式）",
        "allow": True,
    },

    # ===== eval ===== 小欧-2026-06-27 修复：标记为HIGH风险
    {
        "pattern": r"eval\s*\(",
        "risk": RiskLevel.HIGH,
        "desc": "eval执行任意代码（代码注入风险）",
        "allow": False,
    },

    # ===== exec ===== 小欧-2026-06-27 修复：标记为HIGH风险
    {
        "pattern": r"exec\s*\(",
        "risk": RiskLevel.HIGH,
        "desc": "exec执行任意代码（代码注入风险）",
        "allow": False,
    },

    # ===== compile ===== 小欧-2026-07-02 修复：排除 module.compile() 误杀
    {
        "pattern": r"(?<!\.)compile\s*\(",
        "risk": RiskLevel.HIGH,
        "desc": "compile编译任意代码（代码注入风险）",
        "allow": False,
    },

    # ===== 用户输入变量 + 危险函数组合 → HIGH =====
    {
        "pattern": r"(?<!\.)eval\s*\([^)]*?(?:input|sys\.argv|os\.getenv|os\.environ)",
        "risk": RiskLevel.HIGH,
        "desc": "eval用户输入（代码注入风险）",
        "allow": False,
    },
    {
        "pattern": r"(?<!\.)exec\s*\([^)]*?(?:input|sys\.argv|os\.getenv|os\.environ)",
        "risk": RiskLevel.HIGH,
        "desc": "exec用户输入（代码注入风险）",
        "allow": False,
    },
    {
        "pattern": r"subprocess\.(?:run|call|Popen|check_output)\s*\([^)]*?(?:input|sys\.argv|os\.getenv|os\.environ)[^)]*?shell\s*=\s*True",
        "risk": RiskLevel.HIGH,
        "desc": "subprocess用户输入+shell=True（命令注入风险）",
        "allow": False,
    },
    {
        "pattern": r"os\.system\s*\([^)]*?(?:input|sys\.argv|os\.getenv|os\.environ)",
        "risk": RiskLevel.HIGH,
        "desc": "os.system用户输入（命令注入风险）",
        "allow": False,
    },

    # ===== os.system / os.popen =====
    {
        "pattern": r"os\.system\s*\(",
        "risk": RiskLevel.MEDIUM,
        "desc": "os.system调用",
        "allow": True,
    },
    {
        "pattern": r"os\.popen\s*\(",
        "risk": RiskLevel.MEDIUM,
        "desc": "os.popen调用",
        "allow": True,
    },

    # ===== shutil.rmtree =====
    {
        "pattern": r"shutil\.rmtree\s*\(",
        "risk": RiskLevel.MEDIUM,
        "desc": "递归删除目录",
        "allow": True,
    },

    # ===== subprocess shell=True =====
    {
        "pattern": r"subprocess\.(run|call|Popen|check_output)\s*\([^)]*?shell\s*=\s*True",
        "risk": RiskLevel.MEDIUM,
        "desc": "subprocess shell=True",
        "allow": True,
    },

    # ===== os.remove / os.unlink =====
    {
        "pattern": r"os\.(remove|unlink)\s*\(",
        "risk": RiskLevel.MEDIUM,
        "desc": "os.remove/os.unlink 删除文件",
        "allow": True,
    },

    # ===== pathlib.Path.unlink =====
    {
        "pattern": r"Path\s*\(.*\)\.unlink\s*\(",
        "risk": RiskLevel.MEDIUM,
        "desc": "pathlib 删除文件",
        "allow": True,
    },

    # ===== __import__ 动态导入 =====
    {
        "pattern": r"__import__\s*\(\s*[\'\"]os[\'\"]\)",
        "risk": RiskLevel.HIGH,
        "desc": "__import__ 动态导入 os（可执行命令）",
        "allow": False,
    },

    # ===== importlib 动态导入 =====
    {
        "pattern": r"importlib\.import_module\s*\(",
        "risk": RiskLevel.MEDIUM,
        "desc": "importlib 动态导入（需审查）",
        "allow": True,
    },

    # ===== getattr绕过检测 ===== 小欧-2026-06-27 新增
    {
        "pattern": r"getattr\s*\([^)]*?,\s*[\'\"](?:system|popen|exec|eval|run|call|Popen)[\'\"]",
        "risk": RiskLevel.HIGH,
        "desc": "getattr绕过安全检查访问危险函数",
        "allow": False,
    },

    # ===== globals/locals绕过检测 ===== 小欧-2026-06-27 新增
    {
        "pattern": r"(globals|locals)\s*\(\s*\)\s*\[[\'\"]__builtins__[\'\"]",
        "risk": RiskLevel.HIGH,
        "desc": "通过globals/locals访问__builtins__绕过检查",
        "allow": False,
    },

    # ===== pickle 反序列化 =====
    {
        "pattern": r"pickle\.(load|loads)\s*\(",
        "risk": RiskLevel.HIGH,
        "desc": "pickle 反序列化（RCE 风险）",
        "allow": False,
    },

    # ===== ctypes 原生库加载 =====
    {
        "pattern": r"ctypes\.(CDLL|cdll|windll|oledll)\s*\(",
        "risk": RiskLevel.HIGH,
        "desc": "ctypes 加载原生库（代码执行风险）",
        "allow": False,
    },
]

_ALIAS_PATTERNS: Dict[str, List[tuple]] = {
    "subprocess": [
        (r"{}\.(run|call|Popen|check_output)\s*\(", RiskLevel.MEDIUM,
         "通过别名调用subprocess执行子进程"),
        (r"{}\.(run|call|Popen|check_output)\s*\([^)]*?shell\s*=\s*True", RiskLevel.MEDIUM,
         "通过别名调用subprocess且shell=True"),
        (r"{}\.(run|call|Popen|check_output)\s*\(\s*\[[^\]]*?\b(rm|del|format|shutdown|reboot)\b", RiskLevel.HIGH,
         "通过别名调用subprocess执行危险系统命令"),
    ],
    "os": [
        (r"{}\.(system|popen)\s*\(", RiskLevel.HIGH,
         "通过别名调用os执行系统命令"),
        (r"{}\.(remove|unlink)\s*\(", RiskLevel.MEDIUM,
         "通过别名调用os删除文件"),
    ],
    "shutil": [
        (r"{}\.rmtree\s*\(", RiskLevel.HIGH,
         "通过别名调用shutil递归删除"),
    ],
    "pickle": [
        (r"{}\.(load|loads)\s*\(", RiskLevel.HIGH,
         "通过别名调用pickle反序列化（RCE风险）"),
    ],
    "ctypes": [
        (r"{}\.(CDLL|cdll|windll|oledll)\s*\(", RiskLevel.HIGH,
         "通过别名调用ctypes加载原生库"),
    ],
}


def _resolve_import_aliases(code: str) -> Dict[str, str]:
    """AST解析代码，返回别名→真实模块名映射 — 小健 2026-06-27"""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {}
    aliases: Dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    aliases[alias.asname] = alias.name
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.asname:
                    aliases[alias.asname] = f"{node.module}.{alias.name}" if node.module else alias.name
    return aliases


def validate_code_safety(code: str) -> Dict[str, Any]:
    """分级安全检查（三层防御） — 小健 2026-06-27

    Returns:
        {"risk_level": "low/medium/high", "warnings": [...], "allow": bool, "details": [...]}
    """
    warnings: List[str] = []
    details: List[str] = []
    max_risk = RiskLevel.LOW
    allow = True

    # ── 第一层：正则规则匹配 ──
    for rule in RISK_CHECK_RULES:
        if re_mod.search(rule["pattern"], code):
            risk = rule["risk"]
            desc = rule["desc"]
            details.append(f"[{risk.upper()}] {desc}")
            if risk == RiskLevel.HIGH:
                max_risk = RiskLevel.HIGH
                allow = False
                warnings.append(desc)
            elif risk == RiskLevel.MEDIUM and max_risk != RiskLevel.HIGH:
                max_risk = RiskLevel.MEDIUM
                warnings.append(desc)

    # ── 第二层：AST别名检测 ──
    alias_map = _resolve_import_aliases(code)
    for alias, real_module in alias_map.items():
        top_module = real_module.split(".")[0]
        if top_module not in _ALIAS_PATTERNS:
            continue
        for pattern_tmpl, risk, desc in _ALIAS_PATTERNS[top_module]:
            pattern = pattern_tmpl.format(re_mod.escape(alias))
            if re_mod.search(pattern, code):
                desc_full = f"{desc}（{real_module}→{alias}）"
                details.append(f"[{risk.upper()}] {desc_full}")
                if risk == RiskLevel.HIGH:
                    max_risk = RiskLevel.HIGH
                    allow = False
                    warnings.append(desc_full)
                elif risk == RiskLevel.MEDIUM and max_risk != RiskLevel.HIGH:
                    max_risk = RiskLevel.MEDIUM
                    warnings.append(desc_full)

    return {
        "risk_level": max_risk,
        "warnings": warnings,
        "allow": allow,
        "details": details,
    }