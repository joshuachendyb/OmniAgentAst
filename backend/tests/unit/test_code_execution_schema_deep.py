# -*- coding: utf-8 -*-
"""
code_execution_schema 深度测试 - 小健 2026-05-05

旧测试完全缺失schema测试，本文件对以下Pydantic模型进行全面深度测试：
- ExecuteCodeInput（统一python+javascript，language字段区分）

覆盖：
- 正常构造（所有字段/仅必填/默认值验证）
- 字段类型验证
- code字段必填验证
- timeout范围验证（1-300边界值、越界值）
- working_dir可选验证（None/字符串）
- Schema生成（model_json_schema）
- 序列化/反序列化（model_dump/model_validate）

Author: 小健 - 2026-05-05
"""

import pytest
from pydantic import ValidationError

from app.services.tools.shell.code_execution_schema import (
    ExecuteCodeInput,
)


# =============================================================================
# 一、ExecuteCodeInput 正常构造
# =============================================================================

class TestExecuteCodeInputConstruction:
    """ExecuteCodeInput 正常构造"""

    def test_all_fields(self):
        """正常：指定所有字段"""
        model = ExecuteCodeInput(code="print('hi')", timeout=60, working_dir="/tmp")
        assert model.code == "print('hi')"
        assert model.timeout == 60
        assert model.working_dir == "/tmp"

    def test_required_field_only(self):
        """正常：仅必填字段code"""
        model = ExecuteCodeInput(code="print('hi')")
        assert model.code == "print('hi')"
        assert model.timeout == 30
        assert model.working_dir is None

    def test_code_and_timeout(self):
        """正常：code + timeout"""
        model = ExecuteCodeInput(code="pass", timeout=120)
        assert model.code == "pass"
        assert model.timeout == 120
        assert model.working_dir is None

    def test_code_and_working_dir(self):
        """正常：code + working_dir"""
        model = ExecuteCodeInput(code="pass", working_dir="D:/projects")
        assert model.working_dir == "D:/projects"
        assert model.timeout == 30


# =============================================================================
# 二、ExecuteCodeInput code字段验证
# =============================================================================

class TestExecuteCodeInputCodeField:
    """ExecuteCodeInput code字段验证"""

    def test_code_missing(self):
        """错误：缺少code字段"""
        with pytest.raises(ValidationError) as exc_info:
            ExecuteCodeInput()
        assert "code" in str(exc_info.value)

    def test_code_empty_string(self):
        """正常：code为空字符串（Pydantic不禁止）"""
        model = ExecuteCodeInput(code="")
        assert model.code == ""

    def test_code_multiline(self):
        """正常：code为多行字符串"""
        code = "import os\nprint(os.getcwd())\nprint('done')"
        model = ExecuteCodeInput(code=code)
        assert model.code == code

    def test_code_with_special_chars(self):
        """正常：code包含特殊字符"""
        model = ExecuteCodeInput(code="print('你好\t\n世界')")
        assert "你好" in model.code

    def test_code_int_type_error(self):
        """错误：code传int类型"""
        with pytest.raises(ValidationError) as exc_info:
            ExecuteCodeInput(code=123)
        assert "code" in str(exc_info.value)

    def test_code_none_type_error(self):
        """错误：code传None"""
        with pytest.raises(ValidationError) as exc_info:
            ExecuteCodeInput(code=None)
        assert "code" in str(exc_info.value)


# =============================================================================
# 三、ExecuteCodeInput timeout范围验证
# =============================================================================

class TestExecuteCodeInputTimeoutRange:
    """ExecuteCodeInput timeout范围验证（ge=1, le=300）"""

    def test_timeout_minimum_valid(self):
        """边界：timeout=1有效"""
        model = ExecuteCodeInput(code="pass", timeout=1)
        assert model.timeout == 1

    def test_timeout_maximum_valid(self):
        """边界：timeout=300有效"""
        model = ExecuteCodeInput(code="pass", timeout=300)
        assert model.timeout == 300

    def test_timeout_zero_invalid(self):
        """越界：timeout=0无效"""
        with pytest.raises(ValidationError) as exc_info:
            ExecuteCodeInput(code="pass", timeout=0)
        assert "timeout" in str(exc_info.value)

    def test_timeout_negative_invalid(self):
        """越界：timeout=-1无效"""
        with pytest.raises(ValidationError) as exc_info:
            ExecuteCodeInput(code="pass", timeout=-1)

    def test_timeout_301_invalid(self):
        """越界：timeout=301无效"""
        with pytest.raises(ValidationError) as exc_info:
            ExecuteCodeInput(code="pass", timeout=301)

    def test_timeout_999_invalid(self):
        """越界：timeout=999无效"""
        with pytest.raises(ValidationError) as exc_info:
            ExecuteCodeInput(code="pass", timeout=999)

    def test_timeout_default_30(self):
        """默认：timeout默认值为30"""
        model = ExecuteCodeInput(code="pass")
        assert model.timeout == 30

    def test_timeout_float_type_error(self):
        """类型错误：timeout传float"""
        with pytest.raises(ValidationError) as exc_info:
            ExecuteCodeInput(code="pass", timeout=30.5)

    def test_timeout_string_type_coerce(self):
        """类型强制：Pydantic v2自动将数字字符串转为int"""
        model = ExecuteCodeInput(code="pass", timeout="30")
        assert model.timeout == 30
        assert isinstance(model.timeout, int)


# =============================================================================
# 四、ExecuteCodeInput working_dir验证
# =============================================================================

class TestExecuteCodeInputWorkingDir:
    """ExecuteCodeInput working_dir可选验证"""

    def test_working_dir_none(self):
        """正常：working_dir=None（默认）"""
        model = ExecuteCodeInput(code="pass")
        assert model.working_dir is None

    def test_working_dir_explicit_none(self):
        """正常：显式传None"""
        model = ExecuteCodeInput(code="pass", working_dir=None)
        assert model.working_dir is None

    def test_working_dir_string(self):
        """正常：字符串路径"""
        model = ExecuteCodeInput(code="pass", working_dir="/tmp/work")
        assert model.working_dir == "/tmp/work"

    def test_working_dir_windows_path(self):
        """正常：Windows路径"""
        model = ExecuteCodeInput(code="pass", working_dir="D:\\projects\\test")
        assert model.working_dir == "D:\\projects\\test"

    def test_working_dir_empty_string(self):
        """正常：空字符串路径（Pydantic不禁止）"""
        model = ExecuteCodeInput(code="pass", working_dir="")
        assert model.working_dir == ""

    def test_working_dir_int_type_error(self):
        """类型错误：working_dir传int"""
        with pytest.raises(ValidationError) as exc_info:
            ExecuteCodeInput(code="pass", working_dir=123)
        assert "working_dir" in str(exc_info.value)


# =============================================================================
# 五、ExecuteCodeInput Schema生成和序列化
# =============================================================================

class TestExecuteCodeInputSchemaSerialization:
    """ExecuteCodeInput Schema生成和序列化"""

    def test_model_json_schema(self):
        """Schema：生成JSON Schema"""
        schema = ExecuteCodeInput.model_json_schema()
        assert "properties" in schema
        assert "code" in schema["properties"]
        assert "timeout" in schema["properties"]
        assert "working_dir" in schema["properties"]

    def test_model_dump(self):
        """序列化：model_dump"""
        model = ExecuteCodeInput(code="print(1)", timeout=60, working_dir="/tmp")
        d = model.model_dump()
        assert d["code"] == "print(1)"
        assert d["timeout"] == 60
        assert d["working_dir"] == "/tmp"

    def test_model_dump_defaults(self):
        """序列化：model_dump包含默认值"""
        model = ExecuteCodeInput(code="pass")
        d = model.model_dump()
        assert d["timeout"] == 30
        assert d["working_dir"] is None

    def test_model_validate(self):
        """反序列化：model_validate"""
        data = {"code": "print(1)", "timeout": 60, "working_dir": "/tmp"}
        model = ExecuteCodeInput.model_validate(data)
        assert model.code == "print(1)"
        assert model.timeout == 60

    def test_schema_code_required(self):
        """Schema：code字段为required"""
        schema = ExecuteCodeInput.model_json_schema()
        assert "code" in schema.get("required", [])

    def test_schema_timeout_has_constraints(self):
        """Schema：timeout字段有ge/le约束"""
        schema = ExecuteCodeInput.model_json_schema()
        timeout_schema = schema["properties"]["timeout"]
        assert timeout_schema.get("minimum") == 1 or timeout_schema.get("exclusiveMinimum") is not None


# =============================================================================
# 六、ExecuteJavascriptInput 测试（对称性验证）
# =============================================================================

class TestExecuteCodeInputLanguageField:
    """ExecuteCodeInput language 字段验证"""

    def test_language_default_python(self):
        """正常：language 默认值为 python"""
        model = ExecuteCodeInput(code="pass")
        assert model.language == "python"

    def test_language_explicit_python(self):
        """正常：显式指定 language=python"""
        model = ExecuteCodeInput(code="pass", language="python")
        assert model.language == "python"

    def test_language_javascript(self):
        """正常：language=javascript"""
        model = ExecuteCodeInput(code="console.log(1);", language="javascript")
        assert model.language == "javascript"

    def test_language_invalid_value(self):
        """边界：language 传任意字符串不报错（无Literal约束）"""
        model = ExecuteCodeInput(code="pass", language="ruby")
        assert model.language == "ruby"

    def test_language_none_error(self):
        """错误：language 传 None"""
        with pytest.raises(ValidationError):
            ExecuteCodeInput(code="pass", language=None)

    def test_language_int_type_error(self):
        """类型错误：language 传 int"""
        with pytest.raises(ValidationError):
            ExecuteCodeInput(code="pass", language=123)

    def test_js_code_works_with_javascript_language(self):
        """正常：JavaScript 代码使用 language=javascript"""
        model = ExecuteCodeInput(code="console.log('hello');", language="javascript", timeout=60, working_dir="/tmp")
        assert model.code == "console.log('hello');"
        assert model.language == "javascript"
        assert model.timeout == 60
        assert model.working_dir == "/tmp"

    def test_schema_language_default_python(self):
        """Schema：language 字段默认值为 python"""
        schema = ExecuteCodeInput.model_json_schema()
        lang_schema = schema["properties"]["language"]
        assert lang_schema.get("default") == "python"
        assert lang_schema.get("type") == "string"

    def test_schema_contains_language(self):
        """Schema：JSON Schema 包含 language 字段"""
        schema = ExecuteCodeInput.model_json_schema()
        assert "language" in schema["properties"]

    def test_model_dump_contains_language(self):
        """序列化：model_dump 包含 language"""
        model = ExecuteCodeInput(code="pass", language="python")
        d = model.model_dump()
        assert d["language"] == "python"

    def test_safety_check_default_true(self):
        """默认：safety_check 默认值为 True"""
        model = ExecuteCodeInput(code="pass")
        assert model.safety_check is True

    def test_safety_check_explicit_false(self):
        """正常：显式设置 safety_check=False"""
        model = ExecuteCodeInput(code="pass", safety_check=False)
        assert model.safety_check is False

    def test_schema_contains_safety_check(self):
        """Schema：JSON Schema 包含 safety_check 字段"""
        schema = ExecuteCodeInput.model_json_schema()
        assert "safety_check" in schema["properties"]
