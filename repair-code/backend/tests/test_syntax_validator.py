# -*- coding: utf-8 -*-
"""syntax_validator 单元测试 — 小欧 2026-07-21
编辑历史:
# 2026-07-21 - 小欧 - 新建: 覆盖 detect_language/validate_syntax/未知放行/注册表可扩展(BUG-002同类用例)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.tools.toolhelper.syntax_validator import (  # noqa: E402
    detect_language,
    validate_syntax,
    SyntaxCheckResult,
    VALIDATORS,
)


def test_detect_language_by_ext():
    assert detect_language("a.py") == "python"
    assert detect_language("a.pyw") == "python"
    assert detect_language("a.json") == "json"
    assert detect_language("a.yaml") == "yaml"
    assert detect_language("a.yml") == "yaml"
    assert detect_language("a.txt") == "unknown"
    assert detect_language("a.md") == "unknown"


def test_detect_language_shebang():
    assert detect_language("script", "#!/usr/bin/env python3\n") == "python"
    assert detect_language("script", "print('hi')\n") == "unknown"


def test_validate_python_valid():
    res = validate_syntax("def f():\n    return 1\n", "python", "x.py")
    assert res.valid
    assert res.error is None


def test_validate_python_invalid_bug002_class():
    # 顶层 return —— BUG-002 同类错误, 必须拦截并报行号
    res = validate_syntax("x = 1\nreturn x\n", "python", "x.py")
    assert not res.valid
    assert res.line == 2
    assert "return" in res.error
    assert "行" in res.error_text()


def test_validate_python_unterminated_suggestion():
    res = validate_syntax("s = 'abc\n", "python", "x.py")
    assert not res.valid
    assert res.suggestion is not None
    assert "raw string" in res.suggestion


def test_validate_json_valid_and_invalid():
    assert validate_syntax('{"a": 1}', "json", "c.json").valid
    bad = validate_syntax('{"a": ', "json", "c.json")
    assert not bad.valid
    assert "JSON" in bad.error


def test_validate_yaml_valid_and_invalid():
    assert validate_syntax("name: foo\n", "yaml", "c.yaml").valid
    bad = validate_syntax('name: "unterminated\n', "yaml", "c.yaml")
    assert not bad.valid
    assert "YAML" in bad.error


def test_unknown_language_passes():
    # 未知/未支持语言一律放行, 防误杀文本文件
    assert validate_syntax("any content {{{", "unknown", "a.txt").valid
    assert validate_syntax("any content {{{", "markdown", "a.md").valid


def test_registry_extensible():
    # OCP: 新增语言只需在 VALIDATORS 注册一行, 调用方无感知
    def _fake(content, fp=None):
        return SyntaxCheckResult(valid=False, language="fake", error="boom")
    VALIDATORS["fake"] = _fake
    try:
        res = validate_syntax("x", "fake", "x.fake")
        assert not res.valid and res.error == "boom"
    finally:
        del VALIDATORS["fake"]
