# -*- coding: utf-8 -*-
"""
Deep code logic bug search - read each tool source to find loopholes
xiaojian 2026-06-24
"""
import asyncio
import os
import tempfile
import pytest


def _run(coro):
    if asyncio.iscoroutine(coro):
        return asyncio.run(coro)
    return coro


class TestDeepLogicBugs:
    """Deep code logic bug tests"""

    def test_read_text_file_encoding_detection_garbage(self):
        """BUG candidate: encoding detection遇到garbage data"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            f.write(b'\x80\x81\x82\x83\x84\x85')
            f.write(b'\xff\xfe\xfd\xfc\xfb\xfa')
            f.write(b'\x00\x01\x02\x03\x04\x05')
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"garbage encoding result: {result['llm_data']['status']}")
        finally:
            os.unlink(tmp)

    def test_read_text_file_encoding_detection_mixed(self):
        """BUG candidate: file contains mixed encoding content"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            f.write("Chinese test\n".encode('utf-8'))
            f.write("GBK encoding test\n".encode('gbk'))
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"mixed encoding result: {result['llm_data']['status']}")
        finally:
            os.unlink(tmp)

    def test_read_text_file_offset_zero_behavior(self):
        """BUG candidate: offset=0 behavior"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("line1\nline2\nline3\nline4\nline5\n")
            tmp = f.name
        try:
            result = _run(readtext(tmp, offset=0, limit=2))
            print(f"offset=0 result: {result['llm_data']['status']}")
            if result['llm_data']['status']['exec_code'] == 'success':
                print(f"  content='{result['data']['content']}'")
                print(f"  line_count={result['data'].get('line_count')}")
        finally:
            os.unlink(tmp)

    def test_read_text_file_line_count_not_in_data(self):
        """BUG candidate: line_count in data"""
        from app.tools.file.read_text_file import readtext
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("line1\nline2\nline3\n")
            tmp = f.name
        try:
            result = _run(readtext(tmp))
            print(f"data keys: {result['data'].keys()}")
            assert 'line_count' not in result['data'], "line_count should not be in data (moved to metrics)"
            assert 'total_lines' not in result['data'], "total_lines should not be in data (moved to metrics)"
        finally:
            os.unlink(tmp)

    def test_grep_import_os_missing(self):
        """BUG candidate: grep_file_content.py import os location"""
        from app.tools.file import grep_file_content
        assert hasattr(grep_file_content, 'grep')

    def test_search_files_fnmatch_case_insensitive_on_windows(self):
        """BUG: search_files ignore_case=False无效 on Windows"""
        from app.tools.file.search_files import find
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "Test.TXT"), 'w') as f:
                f.write("content")
            with open(os.path.join(tmpdir, "test.txt"), 'w') as f:
                f.write("content")

            result = _run(find("test.txt", tmpdir, ignore_case=False))
            total = result['llm_data']['metrics']['total']['value']
            print(f"ignore_case=False result: total={total}")
            if total == 2:
                print("  BUG confirmed: ignore_case=False does not work on Windows")
            elif total == 1:
                print("  correct: ignore_case=False works on Windows")

    def test_list_directory_tree_ignores_files(self):
        """BUG candidate: tree mode only shows directories not files"""
        from app.tools.file.list_directory import listdir
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "subdir"))
            with open(os.path.join(tmpdir, "file.txt"), 'w') as f:
                f.write("content")

            result = _run(listdir(tmpdir))
            print(f"tree mode result: {result['llm_data']['status']}")

    def test_list_directory_statistics_accuracy(self):
        """BUG candidate: statistics data accuracy"""
        from app.tools.file.list_directory import listdir
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "a.txt"), 'w') as f:
                f.write("12345")
            with open(os.path.join(tmpdir, "b.txt"), 'w') as f:
                f.write("1234567890")
            os.makedirs(os.path.join(tmpdir, "subdir"))

            result = _run(listdir(tmpdir))
            metrics = result['llm_data']['metrics']
            print(f"metrics: {metrics}")
            assert metrics['file_count']['value'] == 2, f"file_count error: {metrics}"
            assert metrics['dir_count']['value'] == 1, f"dir_count error: {metrics}"

    @pytest.mark.skip(reason="read_config_file deleted on 2026-06-24")
    def test_read_config_file_ini_section(self):
        """BUG candidate: INI file section parsing (module deleted)"""
        pass

    @pytest.mark.skip(reason="read_config_file deleted on 2026-06-24")
    def test_read_config_file_xml_parse_error(self):
        """BUG candidate: XML parse error (module deleted)"""
        pass

    def test_read_media_file_text_file(self):
        """BUG candidate: read_media_file reads text file"""
        from app.tools.file.read_media_file import readmedia
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("This is a text file")
            tmp = f.name
        try:
            result = _run(readmedia(tmp))
            print(f"text file result: {result['llm_data']['status']}")
        finally:
            os.unlink(tmp)

    def test_read_media_file_empty_file(self):
        """BUG candidate: empty media file"""
        from app.tools.file.read_media_file import readmedia
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.png', delete=False) as f:
            f.write(b'')
            tmp = f.name
        try:
            result = _run(readmedia(tmp))
            print(f"empty PNG result: {result['llm_data']['status']}")
        finally:
            os.unlink(tmp)

    def test_read_media_file_pdf_rejection(self):
        """Verify PDF is rejected"""
        from app.tools.file.read_media_file import readmedia
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdf', delete=False) as f:
            f.write(b'%PDF-1.4 fake content')
            tmp = f.name
        try:
            result = _run(readmedia(tmp))
            print(f"PDF result: {result['llm_data']['status']}")
        finally:
            os.unlink(tmp)
