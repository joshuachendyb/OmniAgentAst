# tests/validate/test_file_path_checker.py
# 小欧矆 2026-06-27

import os
import sys
import tempfile
from pathlib import Path

import pytest

from app.tools.validate.file_path_checker import (
    validate_path_for_write,
    validate_path_for_delete,
    validate_path_for_overwrite,
    validate_path_for_extract,
)


# ============================================================
# validate_path_for_write()
# ============================================================

class TestValidatePathForWrite:
    """validate_path_for_write() full coverage test"""

    # 鈹查鈹查 文件不存在?鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查
    def test_file_not_exists(self):
        result = validate_path_for_write("/tmp/non_existent_file_xyz")
        assert result == (True, None, None)

    # 鈹查鈹查 文件存在,请昂对?鈮?1MB,岄潪连藉姞 鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查
    def test_file_exists_small_no_append(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"x" * 100)
            tmppath = f.name
        try:
            result = validate_path_for_write(tmppath)
            assert result == (True, None, None)
        finally:
            os.unlink(tmppath)

    # 鈹查鈹查 文件存在,请昂对?> 1MB,岄潪连藉姞 鈫?复ф件件惰标栬鍛?鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查
    def test_file_exists_large_no_append(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"x" * (1024 * 1024 + 1))
            tmppath = f.name
            expected_size = os.path.getsize(tmppath)
        try:
            ok, err, warn = validate_path_for_write(tmppath)
        except Exception:
            ok, err, warn = False, None, None
        assert ok is True
        assert err is None
        assert warn is not None
        assert "请确认" in warn

    # 钡查钡查 路径含 "program files"，解压类目需警燂级  钡查钡查钡查钡查钡查钡查钡查钡查钡查钡查钡查钡查钡查钡查
    @pytest.mark.parametrize("pf_dir", [
        r"C:\Program Files\test",
        r"C:\PROGRAM FILES (X86)\test",
        r"c:\program files\common files",
    ])
    def test_contains_program_files(self, pf_dir):
        ok, err, warn = validate_path_for_extract(pf_dir)
        assert ok is True
        assert err is None
        assert warn is not None
        assert "解压到系统目录" in warn
