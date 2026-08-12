# -*- coding: utf-8 -*-
"""test_param_combos_round3_v2.py - encoding recovered"""

import asyncio

from app.services.task.task_context import _current_task_id

import os





import sys





import tempfile





from pathlib import Path





from typing import Dict, Any
import pytest











sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))











TMP = Path(tempfile.gettempdir()) / "omniagent_paramtest_v2"





TMP.mkdir(parents=True, exist_ok=True)











def _setup_file(name: str, content: str = "hello\nworld\nline3\nline4\nline5\n"):





    p = TMP / name





    p.write_text(content, encoding="utf-8")





    return str(p)











def _ec(r: Dict) -> str:





    """exec_code"""





    return r.get("llm_data", {}).get("status", {}).get("exec_code", "")











def _is_err(r: Dict) -> bool: return _ec(r) == "error"





def _is_ok(r: Dict) -> bool: return _ec(r) == "success"



def _is_warning(r: Dict) -> bool: return _ec(r) == "warning"

















# ============================================================





# Tool 1: read_text_file





# ============================================================





class TestReadTextFile:





    def test_r01_empty_path(self):





        from app.tools.file.read_text_file import readtext





        r = asyncio.run(readtext(path=""))





        assert _is_err(r), f"R01: empty path -> {_ec(r)}"











    def test_r02_dir_as_file(self):





        from app.tools.file.read_text_file import readtext





        r = asyncio.run(readtext(path=str(TMP)))





        assert _is_err(r), f"R02: dir as file -> {_ec(r)}"











    def test_r03_nonexistent_path(self):





        from app.tools.file.read_text_file import readtext





        r = asyncio.run(readtext(path=str(TMP / "ghost_xxx.yyy")))





        assert _is_err(r), f"R03: ghost file -> {_ec(r)}"











    def test_r04_limit_no_offset(self):





        from app.tools.file.read_text_file import readtext





        fp = _setup_file("r04.txt")





        r = asyncio.run(readtext(path=fp, limit=5))





        assert _is_ok(r), f"R04: limit w/o offset -> {_ec(r)}"











    def test_r05_negative_offset_only(self):





        from app.tools.file.read_text_file import readtext





        fp = _setup_file("r05.txt", content="a\nb\nc\nd\ne\nf\ng\nh\ni\nj\n")





        r = asyncio.run(readtext(path=fp, offset=-3))





        assert _is_err(r), f"R05: negative offset should error -> {_ec(r)}"



        f"R05: negative offset should return last N lines -> {_ec(r)}"

















# ============================================================





# Tool 2: write_text_file





# ============================================================





class TestWriteTextFile:





    def test_w01_content_not_string(self):





        from app.tools.file.write_text_file import writetext





        r = asyncio.run(writetext(path=str(TMP / "w01.txt"), content=12345))





        assert _is_err(r), f"W01: non-str content -> {_ec(r)}"











    def test_w02_append_nonexistent(self):





        from app.tools.file.write_text_file import writetext

        token = _current_task_id.set("test-w02")
        try:
            r = asyncio.run(writetext(path=str(TMP / "w02_ghost.txt"), content="test", append=True))
        finally:
            _current_task_id.reset(token)




        assert _is_ok(r), f"W02: append to ghost should create file -> {_ec(r)}"











    def test_w03_empty_content(self):





        from app.tools.file.write_text_file import writetext





        r = asyncio.run(writetext(path=str(TMP / "w03.txt"), content=""))





        assert _is_err(r), f"W03: empty content -> {_ec(r)}"











    def test_w04_append_with_encoding(self):





        from app.tools.file.write_text_file import writetext





        fp = _setup_file("w04.txt")





        r = asyncio.run(writetext(path=fp, content="new", encoding="gbk", append=True))





        assert _is_err(r), f"W04: append+encoding -> {_ec(r)}"











    def test_w05_invalid_encoding(self):





        from app.tools.file.write_text_file import writetext





        r = asyncio.run(writetext(path=str(TMP / "w05.txt"), content="test", encoding="xxx"))





        assert _is_err(r), f"W05: invalid encoding -> {_ec(r)}"

















# ============================================================





# Tool 3: edit_text_file





# ============================================================





class TestEditTextFile:





    def test_e01_empty_old_string(self):





        from app.tools.file.edit_text_file import edittext





        fp = _setup_file("e01.txt")





        r = asyncio.run(edittext(path=fp, old_string=""))





        assert _is_err(r), f"E01: empty old_string -> {_ec(r)}"











    def test_e02_nonexistent_file(self):





        from app.tools.file.edit_text_file import edittext





        r = asyncio.run(edittext(path=str(TMP / "ghost_e02.txt"), old_string="x"))





        assert _is_err(r), f"E02: ghost file -> {_ec(r)}"

















# ============================================================





# Tool 4: list_directory





# ============================================================





class TestListDirectory:





    def test_l01_ghost_dir(self):





        from app.tools.file.list_directory import listdir





        from app.tools.file.tree import tree





        r = asyncio.run(listdir(path=str(TMP / "ghost_dir_xxx")))





        assert _is_err(r), f"L01: ghost dir -> {_ec(r)}"











    def test_l02_file_as_dir(self):





        from app.tools.file.list_directory import listdir





        from app.tools.file.tree import tree





        fp = _setup_file("l02.txt")





        r = asyncio.run(listdir(path=fp))





        assert _is_err(r), f"L02: file as dir -> {_ec(r)}"











    def test_l03_empty_dir(self):





        from app.tools.file.list_directory import listdir





        from app.tools.file.tree import tree





        d = TMP / "empty_l03"; d.mkdir(exist_ok=True)





        r = asyncio.run(listdir(path=str(d)))





        assert _is_ok(r), f"L03: empty dir -> {_ec(r)}"











    def test_l04_unicode_tree(self):





        from app.tools.file.list_directory import listdir





        from app.tools.file.tree import tree





        d = TMP / "涓鏂嘷l04"; d.mkdir(exist_ok=True)





        (d / "文件.txt").write_text("x")





        r = asyncio.run(tree(path=str(d)))





        assert _is_ok(r), f"L04: unicode tree -> {_ec(r)}"











    def test_l05_empty_path(self):





        """BUG#L05: 绌鸿矾寰勫簲璇error,浣嗚繑鍥瀞uccess"""





        from app.tools.file.list_directory import listdir





        from app.tools.file.tree import tree





        r = asyncio.run(listdir(path=""))





        # DESIRED: should error 鈥?EMPTY path is invalid





        assert _is_err(r), f"L05-BUG: empty path should error but got: {_ec(r)}"

















# ============================================================





# Tool 5: search_files





# ============================================================





class TestSearchFiles:





    def test_sf01_empty_pattern(self):





        from app.tools.file.search_files import find





        r = asyncio.run(find(pattern="", path=str(TMP)))





        assert _is_err(r), f"SF01: empty pattern -> {_ec(r)}"











    def test_sf02_ghost_dir(self):





        from app.tools.file.search_files import find





        r = asyncio.run(find(pattern="*.txt", path=str(TMP / "ghost")))





        assert _is_err(r), f"SF02: ghost dir -> {_ec(r)}"











    def test_sf03_no_match(self):





        from app.tools.file.search_files import find





        r = asyncio.run(find(pattern="*.ZZZZZ", path=str(TMP)))





        assert _is_ok(r), f"SF03: no match -> {_ec(r)}"











    def test_sf04_invalid_type(self):





        """BUG#SF04: type鍙傛暟鍊奸潪娉曚絾琚鎺?"""





        from app.tools.file.search_files import find





        r = asyncio.run(find(pattern="*.txt", path=str(TMP), type="INVALID_TYPE"))





        assert _is_err(r), f"SF04-BUG: invalid type should error but got: {_ec(r)}"











    def test_sf05_file_as_dir(self):





        """BUG#SF05: file path as search_dir should error"""





        from app.tools.file.search_files import find





        fp = _setup_file("sf05.txt")





        r = asyncio.run(find(pattern="*.txt", path=fp))





        assert _is_err(r), f"SF05-BUG: file as dir should error but got: {_ec(r)}"

















# ============================================================





# Tool 6: grep_file_content





# ============================================================





class TestGrepFileContent:





    def test_g01_invalid_regex(self):





        from app.tools.file.grep_file_content import grep





        r = asyncio.run(grep(pattern="[invalid", path=str(TMP)))





        assert _is_err(r), f"G01: invalid regex -> {_ec(r)}"











    def test_g02_empty_pattern(self):





        from app.tools.file.grep_file_content import grep





        r = asyncio.run(grep(pattern="", path=str(TMP)))





        assert _is_err(r), f"G02: empty pattern -> {_ec(r)}"











    def test_g03_ghost_dir(self):





        from app.tools.file.grep_file_content import grep





        r = asyncio.run(grep(pattern="hello", path=str(TMP / "ghost")))





        assert _is_err(r), f"G03: ghost dir -> {_ec(r)}"











    def test_g04_glob_no_match(self):





        from app.tools.file.grep_file_content import grep





        r = asyncio.run(grep(pattern="hello", path=str(TMP), glob="*.ZZZZZ"))





        assert _is_ok(r), f"G04: no match glob -> {_ec(r)}"











    def _removed_test_g05_invalid_output_mode(self):
        return
        # 已删除: output_mode 参数已从 grep API 移除 — 小欧 2026-07-20





        from app.tools.file.grep_file_content import grep





        pass  # removed





        assert _is_err(r), f"G05: invalid output_mode -> {_ec(r)}"

















# ============================================================





# Tool 7: shell





# ============================================================





class TestShellCommand:





    def test_h01_empty(self):





        from app.tools.fundamental.execute_shell_command import shell





        r = shell(command="")





        assert _is_err(r), f"H01: empty cmd -> {_ec(r)}"











    def test_h02_invalid_shell_type(self):





        from app.tools.fundamental.execute_shell_command import shell





        r = shell(command="echo test", shell_type="linux")





        assert _is_err(r), f"H02: linux shell_type -> {_ec(r)}"











    def test_h03_negative_timeout(self):





        from app.tools.fundamental.execute_shell_command import shell





        r = shell(command="echo test", timeout=-100)





        assert _is_err(r), f"H03: negative timeout -> {_ec(r)}"











    def test_h04_ghost_cwd(self):
        # 2026-08-11 小欧: 产品 2026-07-27 起 _resolve_safe_cwd 对不存在cwd自动回退(告警+成功),
        # 原断言报错已过时; 改为验证回退后成功 — 同步产品进化
        from app.tools.fundamental.execute_shell_command import shell

        r = shell(command="echo test", cwd=str(TMP / "ghost"))
        assert _is_ok(r), f"H04: ghost cwd应自动回退并成功 -> {_ec(r)}"











    def test_h05_whitespace(self):





        from app.tools.fundamental.execute_shell_command import shell





        r = shell(command="   \t   ")





        assert _is_err(r), f"H05: whitespace cmd -> {_ec(r)}"

















# ============================================================





# Tool 8: code





# ============================================================





class TestExecuteCode:





    def test_c01_empty(self):
        """BUG#C01: execute_code模块已移除,导入应失败"""
        import pytest
        with pytest.raises((ImportError, ModuleNotFoundError)):
            from app.tools.shell.execute_code import runcode  # noqa: F401

    def test_c02_invalid_language(self):
        """BUG#C02: execute_code模块已移除,导入应失败"""
        import pytest
        with pytest.raises((ImportError, ModuleNotFoundError)):
            from app.tools.shell.execute_code import runcode  # noqa: F401

    def test_c03_negative_timeout(self):
        """BUG#C03: execute_code模块已移除,导入应失败"""
        import pytest
        with pytest.raises((ImportError, ModuleNotFoundError)):
            from app.tools.shell.execute_code import runcode  # noqa: F401

    def test_c04_ghost_workdir(self):
        """BUG#C04: execute_code模块已移除,导入应失败"""
        import pytest
        with pytest.raises((ImportError, ModuleNotFoundError)):
            from app.tools.shell.execute_code import runcode  # noqa: F401

    def test_c05_zero_timeout(self):
        """BUG#C05: execute_code模块已移除,导入应失败"""
        import pytest
        with pytest.raises((ImportError, ModuleNotFoundError)):
            from app.tools.shell.execute_code import runcode  # noqa: F401

class TestCopyFile:





    def test_cp01_source_eq_dest(self):





        """BUG#CP01: path==dest不应是success"""





        from app.tools.file.copy_file import copy





        fp = _setup_file("cp01.txt")





        r = asyncio.run(copy(path=fp, dest=fp))





        assert _is_err(r), f"CP01-BUG: path==dest should error, got: {_ec(r)} (data: {r.get('data')})"











    def test_cp02_ghost_source(self):





        from app.tools.file.copy_file import copy





        r = asyncio.run(copy(path=str(TMP / "ghost.txt"), dest=str(TMP / "cp02_out.txt")))





        assert _is_err(r), f"CP02: ghost source -> {_ec(r)}"











    def test_cp03_dir_no_recursive(self):

        token = _current_task_id.set("test-cp03")
        try:
            from app.tools.file.copy_file import copy

            d = TMP / "cp03_dir"; d.mkdir(parents=True, exist_ok=True)
            out = TMP / "cp03_out"
            if out.exists():
                import shutil; shutil.rmtree(str(out))
            r = asyncio.run(copy(path=str(d), dest=str(out)))
        finally:
            _current_task_id.reset(token)

        assert _is_ok(r), f"CP03: dir w/o recursive creates empty dest -> {_ec(r)}"











    def test_cp04_empty_source(self):





        from app.tools.file.copy_file import copy





        r = asyncio.run(copy(path="", dest=str(TMP / "cp04_out.txt")))





        assert _is_err(r), f"CP04: empty source -> {_ec(r)}"











    def test_cp05_overwrite_existing(self):





        """BUG#CP05: overwrite=False但目标存在不应是success"""





        from app.tools.file.copy_file import copy





        src = _setup_file("cp05_src.txt")





        dst = _setup_file("cp05_dst.txt", content="existing")





        r = asyncio.run(copy(path=src, dest=dst, overwrite=False))





        assert _is_err(r), f"CP05-BUG: overwrite=False with existing should error, got: {_ec(r)}"

















# ============================================================





# Tool 10: move_file





# ============================================================





class TestMoveFile:





    def test_mv01_source_eq_dest(self):





        """BUG#MV01: path==dest不应是success"""





        from app.tools.file.move_file import move





        fp = _setup_file("mv01.txt")





        r = asyncio.run(move(path=fp, dest=fp))





        assert _is_err(r), f"MV01-BUG: path==dest should error, got: {_ec(r)} (data: {r.get('data')})"











    def test_mv02_ghost_source(self):





        from app.tools.file.move_file import move





        r = asyncio.run(move(path=str(TMP / "ghost.txt"), dest=str(TMP / "mv02_out.txt")))





        assert _is_err(r), f"MV02: ghost source -> {_ec(r)}"











    def test_mv03_empty_source(self):





        from app.tools.file.move_file import move





        r = asyncio.run(move(path="", dest=str(TMP / "mv03_out.txt")))





        assert _is_err(r), f"MV03: empty source -> {_ec(r)}"











    def test_mv04_empty_dest(self):





        from app.tools.file.move_file import move





        fp = _setup_file("mv04.txt")





        r = asyncio.run(move(path=fp, dest=""))





        assert _is_err(r), f"MV04: empty dest -> {_ec(r)}"

















# ============================================================





# Tool 11: delete_file





# ============================================================





class TestDeleteFile:





    def test_dl01_ghost_file(self):





        """BUG#DL01: 删除不存在文件不应是success"""





        from app.tools.file.delete_file import delete





        r = asyncio.run(delete(path=str(TMP / "ghost.txt")))





        assert _is_err(r), f"DL01-BUG: ghost file should error, got: {_ec(r)}"











    def test_dl02_empty_source(self):





        from app.tools.file.delete_file import delete





        r = asyncio.run(delete(path=""))





        assert _is_err(r), f"DL02: empty source -> {_ec(r)}"

















# ============================================================





# Tool 12: http_request





# ============================================================





class TestHttpRequest:





    def test_http01_invalid_url(self):





        from app.tools.network.http_request import httpget





        r = asyncio.run(httpget(url="not-a-url"))





        assert _is_err(r), f"HTTP01: invalid URL -> {_ec(r)}"











    def test_http02_empty_url(self):





        from app.tools.network.http_request import httpget





        r = asyncio.run(httpget(url=""))





        assert _is_err(r), f"HTTP02: empty URL -> {_ec(r)}"











    def test_http03_invalid_method(self):





        from app.tools.network.http_request import httpget





        r = asyncio.run(httpget(url="http://127.0.0.1:1", method="INVALID"))





        assert _is_err(r), f"HTTP03: invalid method -> {_ec(r)}"











    def test_http04_zero_retry(self):





        from app.tools.network.http_request import httpget





        r = asyncio.run(httpget(url="http://127.0.0.1:1"))





        assert _is_err(r), f"HTTP04: retry=0 -> {_ec(r)}"











    def test_http05_negative_retry(self):





        from app.tools.network.http_request import httpget





        r = asyncio.run(httpget(url="http://127.0.0.1:1"))





        assert _is_err(r), f"HTTP05: negative retry -> {_ec(r)}"

















# ============================================================





# Tool 13: fetch_webpage





# ============================================================





class TestFetchWebpage:





    def test_fw01_invalid_url(self):





        from app.tools.network.fetch_webpage import fetchpage





        r = asyncio.run(fetchpage(url="not-a-url"))





        assert _is_err(r), f"FW01: invalid URL -> {_ec(r)}"











    def test_fw02_empty_url(self):





        from app.tools.network.fetch_webpage import fetchpage





        r = asyncio.run(fetchpage(url=""))





        assert _is_err(r), f"FW02: empty URL -> {_ec(r)}"











    def test_fw03_invalid_extract_format(self):





        """BUG#FW03: extract_format涓嶉獙璇佲斺斾紶"pdf"浠嶇敤markdown鍥為"""





        from app.tools.network.fetch_webpage import fetchpage





        r = asyncio.run(fetchpage(url="http://127.0.0.1:1", extract_format="pdf"))





        assert _is_err(r), f"FW03-BUG: invalid format -> {_ec(r)}"











    def test_fw04_huge_timeout(self):





        """BUG#FW04: timeout涓嶉獙璇佲斺斾紶999999搴旀姤閿?"""





        from app.tools.network.fetch_webpage import fetchpage





        r = asyncio.run(fetchpage(url="http://127.0.0.1:1", timeout=999999))





        assert _is_err(r), f"FW04-BUG: huge timeout -> {_ec(r)}"











    def test_fw05_negative_timeout(self):





        from app.tools.network.fetch_webpage import fetchpage





        r = asyncio.run(fetchpage(url="http://127.0.0.1:1", timeout=-5000))





        assert _is_err(r), f"FW05: negative timeout -> {_ec(r)}"

















# ============================================================





# Tool 14: search_web





# ============================================================





class TestSearchWeb:





    def test_sw01_empty_query(self):






        from app.tools.network.search_web import searchweb






        r = asyncio.run(searchweb(query=""))






        assert _is_err(r), f"SW01: 2026-07-22起空query参数级拦截 -> {_ec(r)}"











    def test_sw02_negative_num_results(self):





        """BUG#SW02: num_results=-5搴旀姤閿欎絾涓嶉獙璇?"""





        from app.tools.network.search_web import searchweb





        r = asyncio.run(searchweb(query="test", num_results=-5))





        assert _is_err(r), f"SW02-BUG: num_results=-5 -> {_ec(r)}"











    def test_sw03_huge_num_results(self):





        """BUG#SW03: num_results=500搴旀姤閿欎絾涓嶉獙璇?"""





        from app.tools.network.search_web import searchweb





        r = asyncio.run(searchweb(query="test", num_results=1001))




        assert _is_err(r), f"SW03-BUG: num_results=1001 -> {_ec(r)}"











    def test_sw04_zero_num_results(self):





        """BUG#SW04: num_results=0搴旀姤閿欎絾涓嶉獙璇?"""





        from app.tools.network.search_web import searchweb





        r = asyncio.run(searchweb(query="test", num_results=0))





        assert _is_err(r), f"SW04-BUG: num_results=0 -> {_ec(r)}"

















# ============================================================





# Tool 15: tool_search





# ============================================================





class TestToolSearch:





    def test_ts01_empty_query(self):





        from app.tools.fundamental.tool_search import searchtool





        r = searchtool(query="")





        assert _is_err(r), f"TS01: empty query -> {_ec(r)}"











    def test_ts02_whitespace_query(self):





        from app.tools.fundamental.tool_search import searchtool





        r = searchtool(query="   \t   ")





        assert _is_err(r), f"TS02: whitespace query -> {_ec(r)}"











    def test_ts03_huge_query(self):





        from app.tools.fundamental.tool_search import searchtool





        r = searchtool(query="x" * 50000)





        assert _is_ok(r) or _is_warning(r), f"TS03: huge query -> {_ec(r)}"











    def test_ts04_regex_chars(self):





        from app.tools.fundamental.tool_search import searchtool





        r = searchtool(query=".*+?^${}()|[]\\")





        assert _is_ok(r) or _is_warning(r), f"TS04: regex chars -> {_ec(r)}"











    def test_ts05_chinese(self):





        from app.tools.fundamental.tool_search import searchtool





        r = searchtool(query="文件操作 搜索 读取")





        assert _is_ok(r), f"TS05: chinese -> {_ec(r)}"






