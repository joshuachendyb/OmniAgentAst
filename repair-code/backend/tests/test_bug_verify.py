# 编辑历史: 2026-07-18 小健 修正write_docx 不一致行normalize后成功写入(非回归) 对齐07-13重构
"""
Edge case bug verification — pytest style
"""
import sys, os, tempfile, asyncio

# no sys.path manipulation — pytest handles it

def _err(r):
    return r.get("llm_data", {}).get("status", {}).get("detail", "")


def test_bug1_write_docx_mismatched_rows():
    """write_docx: 表格行长度不一致 — 07-13对齐: normalize_table_data 已对行做等长填充,
    不再抛出 IndexError, 而是成功写入(健壮性提升, 非回归)。"""
    from app.tools.document.write_docx import write_docx
    tmp = tempfile.mktemp(suffix=".docx")
    try:
        r = write_docx(path=tmp, table_data=[["H1","H2","H3"],["short"],["a","b","c","d","e"]])
        # 当前行为: 行被填充为等长, 写入成功(不再崩溃)
        assert r.get("llm_data", {}).get("status", {}).get("exec_code") == "success", \
            f"行长度不一致应被normalize后成功写入, 实际: {r}"
        assert _err(r) == ""
    finally:
        os.path.exists(tmp) and os.remove(tmp)


def test_bug2_write_docx_control_chars():
    """BUG: write_docx:139 — control chars in content crash ValueError"""
    from app.tools.document.write_docx import write_docx
    tmp = tempfile.mktemp(suffix=".docx")
    try:
        r = write_docx(path=tmp, content="hi\u0000there\n\u0001bye")
        assert "detail" in r.get("llm_data", {}).get("status", {}), "Expected error but got success"
        assert "null" in _err(r).lower() or "xml compatible" in _err(r).lower() or "control" in _err(r).lower()
    finally:
        os.path.exists(tmp) and os.remove(tmp)


def test_bug3_write_docx_none_row():
    """BUG: write_docx:164 — None row in table_data crash TypeError"""
    from app.tools.document.write_docx import write_docx
    tmp = tempfile.mktemp(suffix=".docx")
    try:
        r = write_docx(path=tmp, table_data=[None, ["a","b"]])
        assert "detail" in r.get("llm_data", {}).get("status", {}), "Expected error but got success"
        assert "nonetype" in _err(r).lower() or "len" in _err(r).lower()
    finally:
        os.path.exists(tmp) and os.remove(tmp)


def test_bug4_keyboard_control_none_type():
    """BUG: keyboard_control:42 — None text_or_keys crash AttributeError"""
    from app.tools.desktop.keyboard_control import keyboard_control
    r = keyboard_control(action="type", text_or_keys=None)
    assert "detail" in r.get("llm_data", {}).get("status", {}), "Expected error but got success"
    # AttributeError leaks — message should be human-readable
    assert "isascii" not in _err(r), "Internal AttributeError leaked to user"


def test_bug5_keyboard_control_none_shortcut():
    """BUG: keyboard_control:57 — None shortcut crash AttributeError"""
    from app.tools.desktop.keyboard_control import keyboard_control
    r = keyboard_control(action="shortcut", text_or_keys=None)
    assert "detail" in r.get("llm_data", {}).get("status", {}), "Expected error but got success"
    assert "split" not in _err(r), "Internal AttributeError leaked to user"


def test_bug6_write_xlsx_nested_dict():
    """BUG: write_xlsx:167 — nested dict cell value crash"""
    from app.tools.document.write_xlsx import write_xlsx
    tmp = tempfile.mktemp(suffix=".xlsx")
    try:
        r = write_xlsx(path=tmp, data=[{"name": {"first": "A", "last": "B"}}])
        assert "detail" in r.get("llm_data", {}).get("status", {}), "Expected error but got success"
        assert "cannot convert" in _err(r).lower()
    finally:
        os.path.exists(tmp) and os.remove(tmp)


def test_bug7_timer_empty_callback():
    """BUG: timer_set:91 — empty callback silently creates timer"""
    from app.tools.timer.timer_set import timer_set, _timer_callbacks
    _timer_callbacks.clear()
    r = asyncio.run(timer_set(delay=0.01, callback=""))
    assert "error_detail" not in r.get("data", {}), f"Empty callback should not cause error: {_err(r)}"
    # Check: timer was created silently with empty callback
    for tid, info in _timer_callbacks.items():
        assert info["callback"] == "", f"Expected empty callback, got: {info['callback']}"
    print(f"\n  NOTE: timer with empty callback created silently (id={r['data'].get('timer_id','?')})")


def test_bug8_write_docx_empty_content_skips_table():
    """BUG: write_docx:175 — content='' is falsy, elif table_data skips table"""
    from app.tools.document.write_docx import write_docx
    tmp = tempfile.mktemp(suffix=".docx")
    try:
        r = write_docx(path=tmp, content="", table_data=[["H1","H2"],["v1","v2"]])
        assert "error_detail" not in r.get("data", {}), f"Error: {_err(r)}"
        # The point is table was silently skipped because content='' triggers 'elif' bypass
        # This is a silent data loss bug — table data is just ignored
        print(f"\n  NOTE: table_data with content='' produced file (but table may be missing)")
    finally:
        os.path.exists(tmp) and os.remove(tmp)
