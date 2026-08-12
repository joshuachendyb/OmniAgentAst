# -*- coding: utf-8 -*-
"""语法护栏深度测试 — 小欧 2026-07-21
覆盖: detect_language 扩展名/shebang/未知/优先级; validate_syntax 多语言边界;
OCP 扩展与配置失误 fail-open; 校验器健壮性(非 SyntaxError 不 500); error_text;
以及 edittext/writetext 真实调用链上的护栏阻断/放行集成验证。

编辑历史:
  2026-08-11 - 小欧 - 修复顺序污染: _set_task() set ContextVar后未reset, task_id="test-task-id"泄漏到同进程后续测试
      (致tests/tools/test_edge_cases.py::TestCompress::test_source_none在完整套件中绕过任务检查走到Path(None)崩溃);
      新增autouse fixture _isolate_task_id 每个测试结束reset, 消除污染
"""
import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from app.tools.toolhelper import syntax_validator as sv
from app.services.task import task_context


@pytest.fixture(autouse=True)
def _isolate_task_id():
    """每个测试结束都reset task_id, 防_set_task()等未清理ContextVar泄漏污染后续测试 — 小欧 2026-08-11"""
    token = task_context._current_task_id.set("test-task-id")
    yield
    task_context._current_task_id.reset(token)


def run(coro):
    return asyncio.run(coro)


# ════════════════════════════════════════════════════════════════
# 1. detect_language
# ════════════════════════════════════════════════════════════════
class TestDetectLanguage:
    def test_py_extensions(self):
        for ext in (".py", ".pyw", ".pyi"):
            assert sv.detect_language(f"a{ext}") == "python"

    def test_json_yaml_extensions(self):
        assert sv.detect_language("a.json") == "json"
        assert sv.detect_language("a.yaml") == "yaml"
        assert sv.detect_language("a.yml") == "yaml"

    def test_unknown_extensions_pass(self):
        for p in ("a.md", "a.txt", "a.csv", "a.cfg", "a.toml", "a.xml",
                  "a.json5", "a.pyx", "noext", ""):
            assert sv.detect_language(p) == "unknown"

    def test_shebang_python(self):
        assert sv.detect_language("", "#!/usr/bin/env python3\nx=1") == "python"
        assert sv.detect_language("", "#!/usr/bin/python\n") == "python"

    def test_shebang_non_python(self):
        assert sv.detect_language("", "#!/bin/bash\n") == "unknown"

    def test_case_insensitive(self):
        assert sv.detect_language("A.PY") == "python"
        assert sv.detect_language("Config.YAML") == "yaml"

    def test_dir_with_dots(self):
        # 目录含点不应干扰扩展名判定
        assert sv.detect_language("/a.b/c/d.py") == "python"

    def test_pyw_not_grabbed_by_py_rule(self):
        # .pyw 必须以 .pyw 规则命中, 而非被 .py 误吞(endswith 语义)
        assert sv.detect_language("x.pyw") == "python"
        # 关键: .py 规则不会把 .pyw 当成 .py
        assert not "x.pyw".endswith(".py")

    def test_shebang_requires_python_keyword(self):
        # 带前导空格/不含 python 的 shebang 不应误判
        assert sv.detect_language("", " #!/usr/bin/env python\n") == "unknown"
        assert sv.detect_language("", "#!/usr/bin/ruby\n") == "unknown"


# ════════════════════════════════════════════════════════════════
# 2. validate_syntax — python
# ════════════════════════════════════════════════════════════════
class TestValidatePython:
    def test_valid_module(self):
        r = sv.validate_syntax("def f():\n    return 1\n", "python", "a.py")
        assert r.valid

    def test_bug002_repro_return_outside(self):
        # BUG-002 类: 'return' outside function
        bad = '"""加法"""\nreturn a + b\n'
        r = sv.validate_syntax(bad, "python", "add.py")
        assert not r.valid
        assert "return" in (r.error or "")

    def test_unterminated_string(self):
        r = sv.validate_syntax("s = 'hello\n", "python", "a.py")
        assert not r.valid

    def test_invalid_character_fullwidth(self):
        # 全角标点 → invalid character
        r = sv.validate_syntax("x = １\n", "python", "a.py")
        assert not r.valid

    def test_indentation_tab_error(self):
        r = sv.validate_syntax("def f():\n    return 1\n\tx = 2\n", "python", "a.py")
        assert not r.valid

    def test_valid_expression_statement(self):
        # exec 模式允许裸表达式
        assert sv.validate_syntax("1 + 1\n", "python", "a.py").valid

    def test_crlf_valid(self):
        # CRLF 不影响语法判定
        assert sv.validate_syntax("def f():\r\n    return 1\r\n", "python", "a.py").valid

    def test_future_import_valid(self):
        assert sv.validate_syntax(
            "from __future__ import annotations\ndef f(): pass\n", "python", "a.py").valid


# ════════════════════════════════════════════════════════════════
# 3. validate_syntax — json
# ════════════════════════════════════════════════════════════════
class TestValidateJson:
    def test_valid_dict_list_number(self):
        assert sv.validate_syntax('{"a": 1}', "json", "a.json").valid
        assert sv.validate_syntax('[1, 2, 3]', "json", "a.json").valid
        assert sv.validate_syntax('42', "json", "a.json").valid
        assert sv.validate_syntax('"hi"', "json", "a.json").valid

    def test_nested(self):
        assert sv.validate_syntax('{"a": {"b": [1, 2]}}', "json", "a.json").valid

    def test_trailing_comma_invalid(self):
        r = sv.validate_syntax('{"a": 1,}', "json", "a.json")
        assert not r.valid

    def test_single_quote_invalid(self):
        r = sv.validate_syntax("{'a': 1}", "json", "a.json")
        assert not r.valid

    def test_comment_invalid(self):
        # 标准 JSON 不允许注释
        r = sv.validate_syntax('{"a": 1} // c', "json", "a.json")
        assert not r.valid

    def test_crlf_valid(self):
        assert sv.validate_syntax('{"a": 1}\r\n', "json", "a.json").valid


# ════════════════════════════════════════════════════════════════
# 4. validate_syntax — yaml
# ════════════════════════════════════════════════════════════════
class TestValidateYaml:
    def test_valid_mapping_list(self):
        assert sv.validate_syntax("a: 1\nb: 2\n", "yaml", "a.yaml").valid
        assert sv.validate_syntax("- 1\n- 2\n", "yaml", "a.yaml").valid

    def test_tab_indent_invalid(self):
        r = sv.validate_syntax("a:\n\tb: 1\n", "yaml", "a.yaml")
        assert not r.valid

    def test_malformed_invalid(self):
        r = sv.validate_syntax("a: b: c\n", "yaml", "a.yaml")
        assert not r.valid

    def test_scalar_valid(self):
        assert sv.validate_syntax("just a string\n", "yaml", "a.yaml").valid

    def test_bom_json_valid(self):
        # 带 UTF-8 BOM 的 .json 不应被误判非法(Windows 保存产物)
        assert sv.validate_syntax("﻿{\"a\": 1}", "json", "a.json").valid

    def test_bom_yaml_valid(self):
        assert sv.validate_syntax("﻿a: 1\n", "yaml", "a.yaml").valid

    def test_bom_json_invalid_still_caught(self):
        # BOM 之后仍是非法 JSON → 仍判 invalid
        r = sv.validate_syntax("﻿{\"a\": }", "json", "a.json")
        assert not r.valid


# ════════════════════════════════════════════════════════════════
# 5. 未知语言 / fail-open
# ════════════════════════════════════════════════════════════════
class TestUnknown:
    def test_unknown_language_passes(self):
        assert sv.validate_syntax("anything at all {{{", "unknown", "a.md").valid

    def test_unsupported_language_key_passes(self):
        # _CODE_EXT 映射到未在 VALIDATORS 注册的语言 → fail-open 放行
        r = sv.validate_syntax("x", "go", "a.go")
        assert r.valid
        assert r.language == "go"


# ════════════════════════════════════════════════════════════════
# 6. OCP 扩展
# ════════════════════════════════════════════════════════════════
class TestOCP:
    def test_register_new_language(self):
        def _v(content, file_path=None):
            return sv.SyntaxCheckResult(valid="FORBIDDEN" not in content, language="fake")
        orig = dict(sv.VALIDATORS)
        orig["fake"] = _v
        with patch.object(sv, "VALIDATORS", orig):
            with patch.dict(sv._CODE_EXT, {".fake": "fake"}):
                assert sv.detect_language("a.fake") == "fake"
                assert not sv.validate_syntax("FORBIDDEN", "fake", "a.fake").valid
                assert sv.validate_syntax("ok", "fake", "a.fake").valid


# ════════════════════════════════════════════════════════════════
# 7. 健壮性: 校验器抛非预期异常不应 500, 应优雅判 invalid
# ════════════════════════════════════════════════════════════════
class TestRobustness:
    def test_validator_raising_runtimeerror_does_not_propagate(self):
        def _boom(content, file_path=None):
            raise RuntimeError("unexpected parser crash")
        orig = dict(sv.VALIDATORS)
        orig["boomlang"] = _boom
        with patch.object(sv, "VALIDATORS", orig):
            # 不应抛异常, 应优雅返回 invalid(避免工具 500)
            r = sv.validate_syntax("x", "boomlang", "a.boom")
            assert not r.valid
            assert "校验器异常" in (r.error or "")

    def test_deeply_nested_python_no_crash(self):
        # 极深嵌套可能触发 RecursionError; 不应 500
        deep = "(" * 2000 + "1" + ")" * 2000
        r = sv.validate_syntax(deep, "python", "a.py")
        assert isinstance(r.valid, bool)


# ════════════════════════════════════════════════════════════════
# 8. error_text
# ════════════════════════════════════════════════════════════════
class TestErrorText:
    def test_valid_returns_empty(self):
        assert sv.SyntaxCheckResult(valid=True).error_text() == ""

    def test_includes_suggestion(self):
        r = sv.SyntaxCheckResult(valid=False, error="E", suggestion="S")
        assert r.error_text() == "E；建议:S"

    def test_line_none_no_crash(self):
        r = sv.SyntaxCheckResult(valid=False, error="E", line=None)
        assert r.error_text() == "E"


# ════════════════════════════════════════════════════════════════
# 9. 集成: writetext 真实调用链护栏
# ════════════════════════════════════════════════════════════════
def _set_task():
    token = task_context._current_task_id.set("test-task-id")
    return token


def _patch_record(monkeypatch):
    # 桩掉持久化层(record_operation), 强制走直接写入分支, 与护栏无关
    monkeypatch.setattr(
        "app.tools.file.write_text_file.record_operation", lambda **k: None)
    monkeypatch.setattr(
        "app.tools.file.edit_text_file.record_operation", lambda **k: None)


class TestWritetextIntegration:
    def test_invalid_py_blocked_append_false(self, tmp_path, monkeypatch):
        _patch_record(monkeypatch)
        _set_task()
        f = tmp_path / "bad.py"
        res = run(write_text_file_writetext(f, "def f(:\n  pass\n", append=False))
        # 语法错误 → 阻断, 文件未创建
        assert not f.exists()
        _assert_syntax_error(res)

    def test_valid_py_written(self, tmp_path, monkeypatch):
        _patch_record(monkeypatch)
        _set_task()
        f = tmp_path / "good.py"
        content = "def f():\n    return 1\n"
        res = run(write_text_file_writetext(f, content, append=False))
        assert f.exists()
        assert f.read_text(encoding="utf-8") == content
        assert res["llm_data"]["status"]["exec_code"] == "success"

    def test_invalid_py_append_true_warns_but_writes(self, tmp_path, monkeypatch):
        _patch_record(monkeypatch)
        _set_task()
        f = tmp_path / "bad.py"
        res = run(write_text_file_writetext(f, "def f(:\n", append=True))
        # 追加模式仍写入, 但返回 warning 让 LLM 可见(不静默)
        assert f.exists()
        assert res["llm_data"]["status"]["exec_code"] == "warning"
        assert "语法" in str(res)

    def test_invalid_json_blocked(self, tmp_path, monkeypatch):
        _patch_record(monkeypatch)
        _set_task()
        f = tmp_path / "bad.json"
        res = run(write_text_file_writetext(f, '{"a": }', append=False))
        assert not f.exists()
        _assert_syntax_error(res)

    def test_valid_json_written(self, tmp_path, monkeypatch):
        _patch_record(monkeypatch)
        _set_task()
        f = tmp_path / "good.json"
        res = run(write_text_file_writetext(f, '{"a": 1}', append=False))
        assert f.exists()
        assert res["llm_data"]["status"]["exec_code"] == "success"

    def test_markdown_not_blocked(self, tmp_path, monkeypatch):
        _patch_record(monkeypatch)
        _set_task()
        f = tmp_path / "note.md"
        weird = "def f(:\n):\nreturn ))){\n"
        res = run(write_text_file_writetext(f, weird, append=False))
        # 未知语言放行, 文件应写入
        assert f.exists()
        assert res["llm_data"]["status"]["exec_code"] == "success"

    def test_invalid_yml_blocked(self, tmp_path, monkeypatch):
        _patch_record(monkeypatch)
        _set_task()
        f = tmp_path / "bad.yml"
        res = run(write_text_file_writetext(f, "a: b: c\n", append=False))
        assert not f.exists()
        _assert_syntax_error(res)


# ════════════════════════════════════════════════════════════════
# 10. 集成: edittext 真实调用链护栏
# ═════════════════════════════════════════════════════════=======
class TestEdittextIntegration:
    def test_invalid_replace_blocked(self, tmp_path, monkeypatch):
        _patch_record(monkeypatch)
        _set_task()
        f = tmp_path / "m.py"
        original = "def add(a, b):\n    return a + b\n"
        f.write_text(original, encoding="utf-8")
        # 把合法的 return 行替换成残缺语句 → 语法错误
        res = run(edit_text_file_edittext(
            str(f), "    return a + b", "    def ", mode="once"))
        # 阻断, 文件内容不变
        assert f.read_text(encoding="utf-8") == original
        assert res.get("encode_error") or _has_syntax_error(res)

    def test_valid_replace_applied(self, tmp_path, monkeypatch):
        _patch_record(monkeypatch)
        _set_task()
        f = tmp_path / "m.py"
        original = "x = 1\ny = 2\n"
        f.write_text(original, encoding="utf-8")
        res = run(edit_text_file_edittext(str(f), "y = 2", "y = 3", mode="once"))
        assert f.read_text(encoding="utf-8") == "x = 1\ny = 3\n"
        assert res["llm_data"]["status"]["exec_code"] == "success"

    def test_all_mode_invalid_blocked(self, tmp_path, monkeypatch):
        _patch_record(monkeypatch)
        _set_task()
        f = tmp_path / "m.py"
        original = "def add(a, b):\n    return a + b\n"
        f.write_text(original, encoding="utf-8")
        # all 模式把整文件替换成残缺语句 → 语法错误, 应阻断且文件不变
        res = run(edit_text_file_edittext(str(f), original, "def x(\n", mode="all"))
        assert f.read_text(encoding="utf-8") == original
        _assert_syntax_error(res)


# ════════════════════════════════════════════════════════════════
# 11. 模糊测试 + 误杀核查(对抗式深挖)
# ════════════════════════════════════════════════════════════════
class TestFuzz:
    def test_no_crash_on_random_input(self):
        import random, string
        rng = random.Random(0)
        for _ in range(500):
            n = rng.randint(0, 60)
            s = "".join(rng.choice(string.printable) for _ in range(n))
            for lang in ("python", "json", "yaml", "unknown", "", "go"):
                r = sv.validate_syntax(s, lang, "f.x")
                assert isinstance(r, sv.SyntaxCheckResult)
                assert isinstance(r.valid, bool)
                assert r.line is None or isinstance(r.line, int)

    def test_valid_code_not_falsely_killed(self):
        # 合法代码绝不能被误拦(误杀即 bug)
        must_valid = [
            ("python", "def f():\n    pass\n"),
            ("python", 'x = 1\ny = "def g(:"\n'),
            ("python", "from __future__ import annotations\ndef f(a: list[int]) -> int:\n    return a[0]\n"),
            ("python", "match x:\n    case 1:\n        print(1)\n"),
            ("python", "async def f():\n    await g()\n"),
            ("python", 'a: int = 1\nb: str = "hi"\n'),
            ("json", '{"a": 1, "b": [true, false, null], "c": 1.5e3}'),
            ("json", "[]"),
            ("json", '"just a string"'),
            ("yaml", "key: [1, 2, 3]\n"),
            ("yaml", "multiline: |\n  line1\n  line2\n"),
            ("yaml", "anchors:\n  a: &anchor value\n  b: *anchor\n"),
            ("yaml", "- 1\n- 2\n"),
        ]
        killed = []
        # 注意: 仅对与扩展名匹配的语言校验(模拟真实调用)
        ext_map = {"python": ".py", "json": ".json", "yaml": ".yaml"}
        for lang, c in must_valid:
            r = sv.validate_syntax(c, lang, "f" + ext_map[lang])
            if not r.valid:
                killed.append((lang, c[:40], r.error))
        assert killed == [], f"合法代码被误杀: {killed}"


# ════════════════════════════════════════════════════════════════
# helpers
# ════════════════════════════════════════════════════════════════
from app.tools.file import write_text_file, edit_text_file


def write_text_file_writetext(f, content, append=False):
    return write_text_file.writetext(str(f), content, append=append)


def edit_text_file_edittext(path, old, new, mode="once"):
    return edit_text_file.edittext(path, old, new, mode=mode)


def _assert_syntax_error(res):
    text = str(res)
    assert "语法" in text, text


def _has_syntax_error(res):
    return "语法" in str(res)
