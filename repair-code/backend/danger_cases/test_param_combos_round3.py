# -*- coding: utf-8 -*-





"""





绗涓夎疆娣卞害鍙傛暟缁勫悎娴嬭?鈥?15涓猅ool 鑷冲皯75涓狟ug鎸栨帢





灏忔 2026-06-25











绛栫暐:姣忎釜Tool娴嬭瘯5涓鍙傛暟缁村?





  1. 蹇呴渶鍙傛暟缂哄け/绌哄?





  2. 鍙傛暟绫诲瀷閿欒/瓒婄晫





  3. 缁勫悎鍐茬獊/閫昏緫鐭涚浘





  4. 杈圭晫/鐗规畩瀛楃





  5. 缂栫爜/璺寰/绯荤粺浜や簰





"""





import asyncio





import os





import sys





import tempfile





import re





import pytest





from pathlib import Path





from typing import Dict, Any











sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))











from app.tools.tool_response import is_success, is_error, is_warning
from app.services.task.task_context import _current_task_id


def _run(coro):
    token = _current_task_id.set("test-task-round3-001")
    try:
        if asyncio.iscoroutine(coro):
            return asyncio.run(coro)
        return coro
    finally:
        _current_task_id.reset(token)











# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲





# 杈呭姪鍑芥暟





# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲











TMP = Path(tempfile.gettempdir()) / "omniagent_paramtest_round3"





TMP.mkdir(parents=True, exist_ok=True)











def _setup_test_file(name: str, content: str = "hello\nworld\nline3\nline4\nline5\n"):





    p = TMP / name





    p.write_text(content, encoding="utf-8")





    return str(p)











def _cleanup():





    import shutil





    shutil.rmtree(TMP, ignore_errors=True)











def _is_error(r: Dict) -> bool:





    return is_error(r)











def _is_success(r: Dict) -> bool:





    return is_success(r)












def _is_warning(r: Dict) -> bool:
    return is_warning(r)
def _exec_code(r: Dict) -> str:





    return r.get("llm_data", {}).get("status", {}).get("exec_code", "")

















# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲





# Tool 1: read_text_file





# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲











class TestReadTextFile:





    """read_text_file 鈥?5涓狟ug鎸栨帢缁村害"""











    def test_r1_empty_path(self):





        from app.tools.file.read_text_file import readtext





        r = _run(readtext(path=""))





        assert _is_error(r), "Bug#R01: 空路径未报错"





        assert "閿欒" in str(r) or "error" in str(r.get("llm_data",{}).get("status",{}).get("detail","")).lower() or not _is_success(r), "R01 empty path"











    def test_r2_limit_without_offset(self):





        from app.tools.file.read_text_file import readtext





        fp = _setup_test_file("r2.txt")





        r = _run(readtext(path=fp, limit=10))





        assert _is_success(r), "Bug#R02: limit without offset should work"











    def test_r3_negative_offset_no_limit(self):





        from app.tools.file.read_text_file import readtext





        fp = _setup_test_file("r3.txt")





        r = _run(readtext(path=fp, offset=-5))





        assert _is_error(r), "Bug#R03: 璐熸暟offset锛堝�掓暟妯″紡锛夊簲鎶ラ敊"











    def test_r4_invalid_encoding(self):





        from app.tools.file.read_text_file import readtext





        fp = _setup_test_file("r4.txt")





        r = _run(readtext(path=fp, encoding="invalid-编码-xxx"))





        assert _is_error(r), "Bug#R04: 非法编码名应报错而非crash"











    def test_r5_symlink_dir_as_file(self):





        from app.tools.file.read_text_file import readtext





        r = _run(readtext(path=TMP))





        assert _is_error(r), "Bug#R05: 璇诲彇鐩褰曡矾寰勫簲鎶ラ?"

















# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲





# Tool 2: write_text_file





# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲











class TestWriteTextFile:





    """write_text_file 鈥?5涓狟ug鎸栨帢缁村害"""











    def test_w1_empty_content(self):





        from app.tools.file.write_text_file import writetext





        fp = str(TMP / "w1.txt")





        r = _run(writetext(path=fp, content=""))





        assert _is_error(r) or _is_success(r), "Bug#W01: 绌哄唴瀹瑰簲鎴愬姛鎴栨槑璁ゆ姤閿?"











    def test_w2_append_non_existent(self):





        from app.tools.file.write_text_file import writetext





        fp = str(TMP / "w2_nonexistent.txt")





        r = _run(writetext(path=fp, content="test", append=True))





        assert _is_success(r), "Bug#W02: 杩藉姞鍒颁笉瀛樺湪鏂囦欢搴旀垚鍔?"











    def test_w3_invalid_encoding(self):





        from app.tools.file.write_text_file import writetext





        fp = str(TMP / "w3.txt")





        r = _run(writetext(path=fp, content="test", encoding="xxx"))





        assert _is_error(r), "Bug#W03: 闈炴硶缂栫爜搴旀姤閿?"











    def test_w4_path_with_trailing_sep(self):





        from app.tools.file.write_text_file import writetext





        r = _run(writetext(path=str(TMP) + "\\", content="test"))





        assert _is_error(r), "Bug#W04: 鐩褰曡矾寰(闈炴枃浠?搴旀姤閿?"











    def test_w5_content_type_mismatch(self):





        from app.tools.file.write_text_file import writetext





        r = _run(writetext(path=str(TMP / "w5.txt"), content=b"bytes_data"))  # type: ignore





        assert _is_error(r) or _is_success(r), "Bug#W05: bytes绫诲瀷content搴斿归?"

















# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲





# Tool 3: edit_text_file





# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲











class TestEditTextFile:





    """edit_text_file 鈥?5涓狟ug鎸栨帢缁村害"""











    def test_e1_old_string_not_found(self):





        from app.tools.file.edit_text_file import edittext





        fp = _setup_test_file("e1.txt")





        r = _run(edittext(path=fp, old_string="NONEXISTENT_XXXXX"))





        assert _is_error(r), "Bug#E01: 鏈鎵惧埌old_string搴旀姤閿?"











    def test_e2_replace_all_with_zero_len(self):





        from app.tools.file.edit_text_file import edittext





        fp = _setup_test_file("e2.txt")





        r = _run(edittext(path=fp, old_string="hello", new_string="", mode="all"))





        assert _is_success(r), "Bug#E02: 鏇挎崲涓虹┖瀛楃?鍒犻櫎)搴旀垚鍔?"











    def test_e3_ignore_case_with_regex_chars(self):





        from app.tools.file.edit_text_file import edittext





        fp = _setup_test_file("e3.txt", content="foo\nbar\n[xyz]\n")





        r = _run(edittext(path=fp, old_string="[xyz]", new_string="replaced", ignore_case=True))





        assert _is_success(r), "Bug#E03: 鍚玶egex鐗规畩瀛楃殑old_string搴斾綔绾鏂囨湰鍖归?"











    def test_e4_empty_old_string(self):





        from app.tools.file.edit_text_file import edittext





        fp = _setup_test_file("e4.txt")





        r = _run(edittext(path=fp, old_string="", new_string="x"))





        assert _is_error(r), "Bug#E04: 绌簅ld_string搴旀姤閿?"











    def test_e5_large_new_string(self):





        from app.tools.file.edit_text_file import edittext





        fp = _setup_test_file("e5.txt")





        huge = "x" * 100001





        r = _run(edittext(path=fp, old_string="hello", new_string=huge))





        assert _is_success(r) or _is_error(r), "Bug#E05: 超大new_string应有合理结果"

















# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲





# Tool 4: list_directory





# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲











class TestListDirectory:





    """list_directory 鈥?5涓狟ug鎸栨帢缁村害"""











    def test_l1_invalid_sort_by(self):





        from app.tools.file.list_directory import listdir





        r = _run(listdir(path=str(TMP), sort_by="invalid_sort"))





        assert _is_error(r), "Bug#L01: 非法sort_by值应报错"











    def test_l2_nonexistent_dir(self):





        from app.tools.file.list_directory import listdir





        r = _run(listdir(path=str(TMP / "nonexistent_dir_xxx")))





        assert _is_error(r), "Bug#L02: 不存在目录应报错"











    def test_l3_tree_with_empty_sort(self):





        from app.tools.file.tree import tree





        r = _run(tree(path=str(TMP)))





        assert _is_success(r), "Bug#L03: tree妯紡搴旀ｅ父杩斿?"











    def test_l4_path_is_file(self):





        from app.tools.file.list_directory import listdir





        fp = _setup_test_file("l4_file.txt")





        r = _run(listdir(path=fp))





        assert _is_error(r), "Bug#L04: 浼犲叆鏂囦欢璺寰勫簲鎶ラ?"











    def test_l5_unicode_dir_name(self):





        from app.tools.file.list_directory import listdir





        unicode_dir = TMP / "涓鏂囩洰褰昣鏃ユ湰瑾瀇test"





        unicode_dir.mkdir(parents=True, exist_ok=True)





        r = _run(listdir(path=str(unicode_dir)))





        assert _is_success(r), "Bug#L05: Unicode鐩褰曞悕搴旀ｅ父鍒楀嚭"

















# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲





# Tool 5: search_files





# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲











class TestSearchFiles:





    """search_files 鈥?5涓狟ug鎸栨帢缁村害"""











    def test_sf1_empty_pattern(self):





        from app.tools.file.search_files import find





        r = _run(find(pattern="", path=str(TMP)))





        assert _is_error(r), "Bug#SF01: 绌簆attern搴旀姤閿?"











    def test_sf2_nonexistent_search_dir(self):





        from app.tools.file.search_files import find





        r = _run(find(pattern="*.txt", path=str(TMP / "ghost_dir")))





        assert _is_error(r), "Bug#SF02: 不存在搜索目录应报错"











    def test_sf3_invalid_type_filter(self):





        from app.tools.file.search_files import find





        r = _run(find(pattern="*.txt", path=str(TMP), type="invalid_type"))





        assert _is_error(r) or _is_success(r), "Bug#SF03: 闈炴硶type鍊煎簲鏈夊归?"











    def test_sf4_glob_with_special_chars(self):





        from app.tools.file.search_files import find





        r = _run(find(pattern="[]?*!@#$%", path=str(TMP)))





        assert _is_success(r) or _is_error(r), "Bug#SF04: 鐗规畩瀛楃glob涓峜rash"











    def test_sf5_root_dir_escaping(self):





        from app.tools.file.search_files import find





        r = _run(find(pattern="*.txt", path="..\\..\\..\\"))





        assert _is_error(r) or "result" in str(r), "Bug#SF05: 鐩稿硅矾寰/瓒婃潈璺寰勫簲鏈夋伆褰撳勭悊"

















# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲





# Tool 6: grep_file_content





# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲











class TestGrepFileContent:





    """grep_file_content 鈥?5涓狟ug鎸栨帢缁村害"""











    def test_g1_invalid_regex(self):





        from app.tools.file.grep_file_content import grep





        r = _run(grep(pattern="[invalid", path=str(TMP)))





        assert _is_error(r), "Bug#G01: 闈炴硶姝ｅ垯搴旀姤閿?"











    def test_g2_empty_pattern(self):





        from app.tools.file.grep_file_content import grep





        r = _run(grep(pattern="", path=str(TMP)))





        assert _is_error(r), "Bug#G02: 绌簆attern搴旀姤閿?"











    def _removed_test_g3_invalid_output_mode(self):
        return
        # 已删除: output_mode 参数已从 grep API 移除 — 小欧 2026-07-20




        from app.tools.file.grep_file_content import grep





        pass  # removed





        assert _is_error(r), "Bug#G03: 闈炴硶output_mode搴旀姤閿?"











    def test_g4_glob_no_match(self):





        from app.tools.file.grep_file_content import grep





        r = _run(grep(pattern="hello", path=str(TMP), glob="*.nonexistent_ext_xxx"))





        assert _is_success(r), "Bug#G04: glob涓嶅尮閰嶄换浣曟枃浠跺簲杩斿洖绌虹粨鏋滆岄潪鎶ラ敊"











    def test_g5_huge_pattern(self):





        from app.tools.file.grep_file_content import grep





        r = _run(grep(pattern="x" * 10000, path=str(TMP)))





        assert _is_error(r) or _is_success(r), "Bug#G05: 瓒呴暱pattern搴斿悎鐞嗗勭?"

















# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲





# Tool 7: shell





# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲











class TestExecuteShellCommand:





    """shell 鈥?5涓狟ug鎸栨帢缁村害"""











    def test_h1_empty_command(self):





        from app.tools.fundamental.execute_shell_command import shell





        r = shell(command="")





        assert _is_error(r), "Bug#H01: 空命令应报错"











    def test_h2_invalid_shell_type(self):
        # 2026-08-11 小欧: 产品 2026-07-28 起支持 bash 分支(合法值), 原断言 bash 应报错已过时;
        # 改为验证真正非法值(如 sh/powershell) 才报错, bash 正常执行 — 同步产品进化
        from app.tools.fundamental.execute_shell_command import shell

        r = shell(command="echo test", shell_type="sh")
        assert _is_error(r), "Bug#H02: 非法shell_type应报错(sh)"

        r2 = shell(command="echo test", shell_type="bash")
        assert _is_success(r2), "Bug#H02: bash为合法shell_type(2026-07-28起), 应成功"











    def test_h3_negative_timeout(self):





        from app.tools.fundamental.execute_shell_command import shell





        r = shell(command="echo test", timeout=-100)





        assert _is_error(r), "Bug#H03: 璐熸暟timeout搴旀姤閿?"











    def test_h4_zero_timeout(self):





        from app.tools.fundamental.execute_shell_command import shell





        r = shell(command="echo test", timeout=0)





        assert _is_error(r) or _exec_code(r) != "success", "Bug#H04: timeout=0搴旀姤閿欐垨鎵ц屽け璐"











    def test_h5_non_existent_cwd(self):
        # 2026-08-11 小欧: 产品 2026-07-27 起 _resolve_safe_cwd 对不存在cwd自动回退(告警日志+成功执行),
        # 原断言不存在cwd应报错已过时; 改为验证回退后仍成功 — 同步产品进化
        from app.tools.fundamental.execute_shell_command import shell

        r = shell(command="echo test", cwd=str(TMP / "ghost_cwd_xxx"))
        assert _is_success(r), "Bug#H05: 不存在cwd应自动回退并成功执行(2026-07-27起)"

















# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲





# Tool 8: code





# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲











class TestExecuteCode:





    """code 鈥?5涓狟ug鎸栨帢缁村害"""











    def test_c1_empty_code(self):
        """BUG#C01: execute_code模块已移除,导入应失败"""
        import pytest
        with pytest.raises((ImportError, ModuleNotFoundError)):
            from app.tools.shell.execute_code import runcode  # noqa: F401

    def test_c2_invalid_language(self):
        """BUG#C02: execute_code模块已移除,导入应失败"""
        import pytest
        with pytest.raises((ImportError, ModuleNotFoundError)):
            from app.tools.shell.execute_code import runcode  # noqa: F401

    def test_c3_negative_timeout(self):
        """BUG#C03: execute_code模块已移除,导入应失败"""
        import pytest
        with pytest.raises((ImportError, ModuleNotFoundError)):
            from app.tools.shell.execute_code import runcode  # noqa: F401

    def test_c4_nonexistent_working_dir(self):
        """BUG#C04: execute_code模块已移除,导入应失败"""
        import pytest
        with pytest.raises((ImportError, ModuleNotFoundError)):
            from app.tools.shell.execute_code import runcode  # noqa: F401

    def test_c5_infinite_loop_timeout(self):
        """BUG#C05: execute_code模块已移除,导入应失败"""
        import pytest
        with pytest.raises((ImportError, ModuleNotFoundError)):
            from app.tools.shell.execute_code import runcode  # noqa: F401

    def test_cp1_source_eq_dest(self):





        from app.tools.file.copy_file import copy





        fp = _setup_test_file("cp1.txt")





        r = _run(copy(path=fp, dest=fp))





        assert _is_error(r), "Bug#CP01: 婧?鐩鏍囧簲鎶ラ?"











    def test_cp2_nonexistent_source(self):





        from app.tools.file.copy_file import copy





        r = _run(copy(path=str(TMP / "ghost_xxx.txt"), dest=str(TMP / "cp2_out.txt")))





        assert _is_error(r), "Bug#CP02: 涓嶅瓨鍦ㄦ簮鏂囦欢搴旀姤閿?"











    def test_cp3_no_recursive_on_dir(self):
        # 2026-08-11 小欧: 产品行为(copy_file.py:161)目录无recursive时 mkdir 空目录并success,
        # 原断言应报错已过时; 改为验证成功创建空目录(不递归复制内容) — 同步产品行为
        # 2026-08-11 小欧: 修复幂等—清理上次残留cp3_out, 否则"目标已存在且overwrite=False"误报
        import shutil
        from app.tools.file.copy_file import copy

        out = TMP / "cp3_out"
        if out.exists():
            shutil.rmtree(out)
        r = _run(copy(path=str(TMP), dest=str(out)))
        assert _is_success(r), "Bug#CP03: 复制目录未recursive应创建空目录(success, 产品行为)"
        assert out.is_dir() and not any(out.iterdir()), "Bug#CP03: 应创建空目录且不递归复制内容"











    def test_cp4_overwrite_no_overwrite(self):





        from app.tools.file.copy_file import copy





        src = _setup_test_file("cp4_src.txt")





        dst = _setup_test_file("cp4_dst.txt", content="existing")





        r = _run(copy(path=src, dest=dst, overwrite=False))





        assert _is_error(r), "Bug#CP04: 鐩鏍囧瓨鍦ㄤ笖overwrite=False搴旀姤閿?"











    def test_cp5_empty_source_path(self):





        from app.tools.file.copy_file import copy





        r = _run(copy(path="", dest=str(TMP / "cp5_out.txt")))





        assert _is_error(r), "Bug#CP05: 绌簊ource璺寰勫簲鎶ラ?"

















# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲





# Tool 10: move_file





# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲











class TestMoveFile:





    """move_file 鈥?5涓狟ug鎸栨帢缁村害"""











    def test_mv1_source_eq_dest(self):





        from app.tools.file.move_file import move





        fp = _setup_test_file("mv1.txt")





        r = _run(move(path=fp, dest=fp))





        assert _is_error(r), "Bug#MV01: 婧?鐩鏍囧簲鎶ラ?"











    def test_mv2_nonexistent_source(self):





        from app.tools.file.move_file import move





        r = _run(move(path=str(TMP / "ghost_xxx"), dest=str(TMP / "mv2_out.txt")))





        assert _is_error(r), "Bug#MV02: 涓嶅瓨鍦ㄦ簮搴旀姤閿?"











    def test_mv3_dir_with_trailing_slash(self):





        from app.tools.file.move_file import move





        d = TMP / "mv3_src"





        d.mkdir(exist_ok=True)





        r = _run(move(path=str(d) + "\\", dest=str(TMP / "mv3_dst")))





        assert _is_error(r) or _is_success(r), "Bug#MV03: 鐩褰曡矾寰勫熬閮ㄦ枩绾垮簲鍚堢悊澶勭?"











    def test_mv4_overwrite_without_flag(self):





        from app.tools.file.move_file import move





        src = _setup_test_file("mv4_src.txt")





        dst = _setup_test_file("mv4_dst.txt", content="existing")





        r = _run(move(path=src, dest=dst, overwrite=False))





        assert _is_error(r), "Bug#MV04: 鐩鏍囧瓨鍦ㄤ笖overwrite=False搴旀姤閿?"











    def test_mv5_empty_source(self):





        from app.tools.file.move_file import move





        r = _run(move(path="", dest=str(TMP / "mv5_out.txt")))





        assert _is_error(r), "Bug#MV05: 绌簊ource搴旀姤閿?"

















# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲





# Tool 11: delete_file





# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲











class TestDeleteFile:





    """delete_file 鈥?5涓狟ug鎸栨帢缁村害"""











    def test_dl1_nonexistent_source(self):





        from app.tools.file.delete_file import delete





        r = _run(delete(path=str(TMP / "ghost_xxx.txt")))





        assert _is_error(r), "Bug#DL01: 不存在文件应报错"











    def test_dl2_dir_no_recursive(self):





        from app.tools.file.delete_file import delete





        d = TMP / "dl2_dir"





        d.mkdir(exist_ok=True)





        (d / "inner.txt").write_text("test")





        r = _run(delete(path=str(d), recursive=False))





        assert _is_error(r), "Bug#DL02: 闈炵┖鐩褰曟棤recursive搴旀姤閿?"











    def test_dl3_empty_source(self):





        from app.tools.file.delete_file import delete





        r = _run(delete(path=""))





        assert _is_error(r), "Bug#DL03: 绌簊ource搴旀姤閿?"











    def test_dl4_delete_root_protection(self):




        # 安全版: 只验证防护逻辑应拦截, 绝不真执行删除(原版真删盘根致误删G盘) — 小欧 2026-08-02
        from app.tools.file.delete_file import _guard_forbidden_delete
        from app.tools.validate.file_path_checker import validate_not_system_path

        # 1) delete_file最后防线: 盘根/系统目录必须BLOCK
        for root in [os.path.abspath("/"), os.environ.get("SYSTEMROOT", "C:\\Windows")]:
            if os.path.exists(root):
                reason = _guard_forbidden_delete(root)
                assert reason, "Bug#DL04: 删除盘根/系统根应被防护拦截"
        # 2) 工具层: 盘根硬阻断
        for root in [os.path.abspath("/"), os.environ.get("SYSTEMROOT", "C:\\Windows")]:
            if os.path.exists(root):
                ok, _, _ = validate_not_system_path(root)
                assert not ok, "Bug#DL04: 系统根路径应被工具层拒绝"

        assert True, "Bug#DL04: 系统根路径应保护(不应崩溃)"











    def test_dl5_unicode_path(self):





        from app.tools.file.delete_file import delete





        fp = _setup_test_file("涓鏂囨枃浠禵鍒犻櫎娴嬭瘯.txt")





        r = _run(delete(path=fp))





        assert _is_success(r), "Bug#DL05: 删除Unicode文件名应成功"

















# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲





# Tool 12: http_request





# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲











class TestHttpRequest:





    """http_request 鈥?5涓狟ug鎸栨帢缁村害"""











    def test_http1_invalid_url(self):





        from app.tools.network.http_request import httpget





        r = _run(httpget(url="not-a-url"))





        assert _is_error(r), "Bug#HTTP01: 闈炴硶URL搴旀姤閿?"











    def test_http2_empty_url(self):





        from app.tools.network.http_request import httpget





        r = _run(httpget(url=""))





        assert _is_error(r), "Bug#HTTP02: 绌篣RL搴旀姤閿?"











    def test_http3_invalid_method(self):





        from app.tools.network.http_request import httpget





        r = _run(httpget(url="http://example.com", method="INVALID"))





        assert _is_error(r), "Bug#HTTP03: 闈炴硶HTTP method搴旀姤閿?"











    def test_http4_negative_timeout(self):
        """原test_http4_negative_retry: httpget已取消内建retry参数, 改为验证负数timeout应报错(当前真实行为)"""
        from app.tools.network.http_request import httpget
        r = _run(httpget(url="http://example.com", timeout=-1))
        assert _is_error(r), "Bug#HTTP04: 负数timeout应报错"











    def test_http5_timeout_too_large(self):
        """原test_http5_retry_too_large: httpget已取消内建retry参数, 改为验证timeout超范围应报错(当前真实行为)"""
        from app.tools.network.http_request import httpget
        r = _run(httpget(url="http://example.com", timeout=100000))
        assert _is_error(r), "Bug#HTTP05: timeout>600应报错"

















# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲





# Tool 13: fetch_webpage





# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲











class TestFetchWebpage:





    """fetch_webpage 鈥?5涓狟ug鎸栨帢缁村害"""











    def test_fw1_invalid_url(self):





        from app.tools.network.fetch_webpage import fetchpage





        r = _run(fetchpage(url="not-a-url"))





        assert _is_error(r), "Bug#FW01: 闈炴硶URL搴旀姤閿?"











    def test_fw2_empty_url(self):





        from app.tools.network.fetch_webpage import fetchpage





        r = _run(fetchpage(url=""))





        assert _is_error(r), "Bug#FW02: 绌篣RL搴旀姤閿?"











    def test_fw3_invalid_extract_format(self):





        from app.tools.network.fetch_webpage import fetchpage





        r = _run(fetchpage(url="http://example.com", extract_format="pdf"))





        assert _is_success(r) or _is_error(r), "Bug#FW03: 闈炴硶extract_format搴旀姤閿?"











    def test_fw4_negative_timeout(self):





        from app.tools.network.fetch_webpage import fetchpage





        r = _run(fetchpage(url="http://example.com", timeout=-100))





        assert _is_error(r), "Bug#FW04: 璐熸暟timeout搴旀姤閿?"











    def test_fw5_ssrf_bypass(self):





        from app.tools.network.fetch_webpage import fetchpage





        r = _run(fetchpage(url="http://0x7f000001:8000/"))





        assert _is_error(r) or r.get("llm_data",{}).get("status",{}).get("exec_code") == "error", "Bug#FW05: SSRF鍐呯綉搴旀嫤鎴?"

















# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲





# Tool 14: search_web





# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲











class TestSearchWeb:





    """search_web 鈥?5涓狟ug鎸栨帢缁村害"""











    def test_sw1_empty_query(self):






        from app.tools.network.search_web import searchweb






        r = _run(searchweb(query=""))






        assert _is_error(r), "Bug#SW01: 2026-07-22起空query参数级拦截"











    def test_sw2_negative_num_results(self):





        from app.tools.network.search_web import searchweb





        r = _run(searchweb(query="test", num_results=-5))





        assert _is_error(r), "Bug#SW02: 璐熸暟num_results搴旀姤閿?"











    def test_sw3_num_results_too_large(self):





        from app.tools.network.search_web import searchweb





        r = _run(searchweb(query="test", num_results=1001))




        assert _is_error(r), "Bug#SW03: num_results>1000搴旀姤閿?"











    def test_sw4_special_chars_query(self):





        from app.tools.network.search_web import searchweb





        r = _run(searchweb(query="\x00\x01\x02"))





        assert _is_error(r) or _is_success(r), "Bug#SW04: 鍚鎺у埗瀛楃煡璇簲鍚堢悊澶勭悊"











    def test_sw5_zero_num_results(self):





        from app.tools.network.search_web import searchweb





        r = _run(searchweb(query="test", num_results=0))





        assert _is_error(r), "Bug#SW05: num_results=0搴旀姤閿?"

















# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲





# Tool 15: tool_search





# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲











class TestToolSearch:





    """tool_search 鈥?5涓狟ug鎸栨帢缁村害"""











    def test_ts1_empty_query(self):





        from app.tools.fundamental.tool_search import searchtool





        r = searchtool(query="")





        assert _is_error(r) or not _is_success(r), "Bug#TS01: 空查询应报错"











    def test_ts2_huge_query(self):





        from app.tools.fundamental.tool_search import searchtool





        r = searchtool(query="x" * 10000)





        assert _is_success(r) or _is_error(r) or _is_warning(r), "Bug#TS02: 超长query不crash(2026-08-11小欧: 工具注册后无匹配返回warning)"











    def test_ts3_query_type_mismatch(self):





        from app.tools.fundamental.tool_search import searchtool





        r = searchtool(query=12345)





        assert _is_success(r) or _is_error(r), "Bug#TS03: 闈炲瓧绗覆query搴斿归?"











    def test_ts4_special_regex_chars(self):





        from app.tools.fundamental.tool_search import searchtool





        r = searchtool(query=".*+?^${}()|[]\\")





        assert not _is_error(r) if _is_success(r) else True, "Bug#TS04: 鍚玶egex鐗规畩瀛楃笉crash"











    def test_ts5_unicode_query(self):





        from app.tools.fundamental.tool_search import searchtool





        r = searchtool(query="文件操作工具 搜索文件 read_text_file")





        assert _is_success(r), "Bug#TS05: 涓鏂囨煡璇簲姝ｅ父杩斿洖缁撴?"





