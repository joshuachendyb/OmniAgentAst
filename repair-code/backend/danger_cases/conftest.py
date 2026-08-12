# -*- coding: utf-8 -*-
"""
pytest fixtures for danger_cases 危险用例测试
— 小欧 2026-08-11 新建

背景: test_registry_tools.py / test_execute_shell_command.py 引用的 temp_output_dir
fixture 仅定义于 backend/tests/tools/param_combination/conftest.py, pytest conftest
作用域不覆盖本目录, 导致 8 个用例 ERROR(fixture not found)。
本 conftest 提供同名 fixture, 与 param_combination/conftest.py 行为一致(临时目录)。
"""
import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def temp_output_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)
