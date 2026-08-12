# 编辑历史: 2026-07-18 小健 修正write_docx 不一致行normalize后成功写入(非回归) 对齐07-13重构
"""
Edge case bug tests for OmniAgent tools — 小欧 2026-06-24
"""

import os, sys, math, tempfile, asyncio, traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

TOOL_RESPONSE_KEYS = ['data', 'llm_data', 'other_data']

def _has_error(result):
    """Check if result dict has error in llm_data"""
    return result.get("llm_data", {}).get("status", {}).get("exec_code") == "error"

def _error_msg(result):
    return result.get("llm_data", {}).get("status", {}).get("detail", "")

def _data(result):
    return result.get("data", {})


# ═══════════════════════════════════════════════
# 1) write_pdf — XML special chars ⇒ reportlab Paragraph crash
# ═══════════════════════════════════════════════
def test_write_pdf_xml_special_chars():
    """BUG: write_pdf:180 — Paragraph() treats <>& as XML → crash (suppressed by outer try)"""
    from app.tools.document.write_pdf import write_pdf
    tmp = os.path.join(tempfile.gettempdir(), "_edge_pdf_special.pdf")
    try:
        result = write_pdf(path=tmp, title="Test",
            content="This has <script>alert('xss')</script> and & and > chars")
        assert not _has_error(result), f"XML chars caused error: {_error_msg(result)}"
    finally:
        os.path.exists(tmp) and os.remove(tmp)

def test_write_pdf_unsafe_html_tags():
    """BUG: write_pdf:180 — <b> <u> tags treated as XML markup → reportlab crash"""
    from app.tools.document.write_pdf import write_pdf
    tmp = os.path.join(tempfile.gettempdir(), "_edge_pdf_html.pdf")
    try:
        result = write_pdf(path=tmp, content="<b>bold</b> and <u>underline</u>")
        assert not _has_error(result), f"HTML tags crash: {_error_msg(result)}"
    finally:
        os.path.exists(tmp) and os.remove(tmp)

def test_write_pdf_table_with_html_chars():
    """BUG: write_pdf:186 — table data cells with XML special chars"""
    from app.tools.document.write_pdf import write_pdf
    tmp = os.path.join(tempfile.gettempdir(), "_edge_pdf_table_html.pdf")
    try:
        result = write_pdf(path=tmp,
            table_data=[["A&B", "C<D"], ["E>F", '"G"']])
        assert not _has_error(result), f"Table XML chars error: {_error_msg(result)}"
    finally:
        os.path.exists(tmp) and os.remove(tmp)

def test_write_pdf_huge_line():
    """EDGE: write_pdf:180 — 50K single line → Paragraph might overflow"""
    from app.tools.document.write_pdf import write_pdf
    tmp = os.path.join(tempfile.gettempdir(), "_edge_pdf_huge.pdf")
    try:
        result = write_pdf(path=tmp, content="x" * 50000)
        assert not _has_error(result), f"50K line error: {_error_msg(result)}"
    finally:
        os.path.exists(tmp) and os.remove(tmp)

def test_write_pdf_newlines_and_angles():
    """BUG: write_pdf:166-181 — line starting with > or < confuses heading detection"""
    from app.tools.document.write_pdf import write_pdf
    tmp = os.path.join(tempfile.gettempdir(), "_edge_pdf_angle_line.pdf")
    try:
        result = write_pdf(path=tmp, content="Normal\n> quoted line\n- list item\n<tag>like</tag>")
        assert not _has_error(result), f"Angle line error: {_error_msg(result)}"
    finally:
        os.path.exists(tmp) and os.remove(tmp)


# ═══════════════════════════════════════════════
# 2) write_docx — edge case content and tables
# ═══════════════════════════════════════════════
def test_write_docx_table_mismatched_rows():
    """write_docx: 表格行长度不一致 — 07-13对齐: normalize_table_data 已对行做等长填充,
    不再抛出 IndexError, 写入成功(健壮性提升, 非回归)。"""
    from app.tools.document.write_docx import write_docx
    tmp = os.path.join(tempfile.gettempdir(), "_edge_docx_mismatch.docx")
    try:
        table = [["H1","H2","H3"], ["short"], ["a","b","c","d","e"]]
        result = write_docx(path=tmp, table_data=table)
        # 当前行为: 行被填充为等长, 写入成功, 不再崩溃
        assert not _has_error(result), f"Mismatched rows 应被normalize后成功写入, 实际: {_error_msg(result)}"
    finally:
        os.path.exists(tmp) and os.remove(tmp)

def test_write_docx_table_single_cell():
    """EDGE: write_docx with 1x1 table"""
    from app.tools.document.write_docx import write_docx
    tmp = os.path.join(tempfile.gettempdir(), "_edge_docx_1x1.docx")
    try:
        result = write_docx(path=tmp, table_data=[["only"]])
        assert not _has_error(result), f"1x1 table error: {_error_msg(result)}"
    finally:
        os.path.exists(tmp) and os.remove(tmp)

def test_write_docx_content_control_chars():
    """EDGE: write_docx with control characters"""
    from app.tools.document.write_docx import write_docx
    tmp = os.path.join(tempfile.gettempdir(), "_edge_docx_control.docx")
    try:
        result = write_docx(path=tmp, content="Line1\n\u0000\u0001\u0002\r\nLine2\n\u001f\u007f")
        assert _has_error(result), f"Control chars should error, got success"
    finally:
        os.path.exists(tmp) and os.remove(tmp)


# ═══════════════════════════════════════════════
# 3) write_xlsx — edge cases
# ═══════════════════════════════════════════════
def test_write_xlsx_invalid_sheet_name():
    """BUG: write_xlsx:156 — openpyxl rejects sheet name with []*:/\? chars"""
    from app.tools.document.write_xlsx import write_xlsx
    tmp = os.path.join(tempfile.gettempdir(), "_edge_xlsx_badsheet.xlsx")
    try:
        result = write_xlsx(path=tmp, data=[{"a":1}], sheet_name="Sheet [1] * 2024?")
        if _has_error(result):
            print(f"\n  BUG: invalid sheet name not sanitized: {_error_msg(result)}")
    finally:
        os.path.exists(tmp) and os.remove(tmp)

def test_write_xlsx_mixed_key_types():
    """EDGE: write_xlsx:150 — int keys mixed with str keys"""
    from app.tools.document.write_xlsx import write_xlsx
    tmp = os.path.join(tempfile.gettempdir(), "_edge_xlsx_mixedkeys.xlsx")
    try:
        result = write_xlsx(path=tmp, data=[{0: "zero", 1: "one"}, {"a": "A", "b": "B"}])
        assert not _has_error(result), f"Mixed keys error: {_error_msg(result)}"
    finally:
        os.path.exists(tmp) and os.remove(tmp)

def test_write_xlsx_deeply_nested():
    """EDGE: write_xlsx — nested dicts/lists as cell values"""
    from app.tools.document.write_xlsx import write_xlsx
    tmp = os.path.join(tempfile.gettempdir(), "_edge_xlsx_nested.xlsx")
    try:
        result = write_xlsx(path=tmp, data=[{"name": {"first": "A", "last": "B"}, "tags": [1,2,3]}])
        assert _has_error(result), f"Nested data should error, got success"
    finally:
        os.path.exists(tmp) and os.remove(tmp)


# ═══════════════════════════════════════════════
# 4) write_pptx — edge cases
# ═══════════════════════════════════════════════
def test_write_pptx_none_slides():
    """EDGE: write_pptx:245 — slides=None should error, not crash"""
    from app.tools.document.write_pptx import write_pptx
    tmp = os.path.join(tempfile.gettempdir(), "_edge_pptx_none.pptx")
    try:
        result = write_pptx(path=tmp, slides=None)
        assert _has_error(result), "slides=None should error"
    finally:
        os.path.exists(tmp) and os.remove(tmp)

def test_write_pptx_slide_with_table_none():
    """EDGE: write_pptx:204 — tables entry is not a list"""
    from app.tools.document.write_pptx import write_pptx
    tmp = os.path.join(tempfile.gettempdir(), "_edge_pptx_tablenone.pptx")
    try:
        slides = [{"type": 1, "title": "S1", "tables": None}]
        result = write_pptx(path=tmp, slides=slides)
        assert not _has_error(result), f"tables=None error: {_error_msg(result)}"
    finally:
        os.path.exists(tmp) and os.remove(tmp)

def test_write_pptx_slide_content_empty_list():
    """EDGE: write_pptx:197 — content=[] should not crash"""
    from app.tools.document.write_pptx import write_pptx
    tmp = os.path.join(tempfile.gettempdir(), "_edge_pptx_emptylist.pptx")
    try:
        result = write_pptx(path=tmp, slides=[{"type":1, "content":[]}])
        assert not _has_error(result), f"content=[] error: {_error_msg(result)}"
    finally:
        os.path.exists(tmp) and os.remove(tmp)

def test_write_pptx_content_items_without_text():
    """BUG: write_pptx:80-91 — dict item without 'text' key uses ''"""
    from app.tools.document.write_pptx import write_pptx
    tmp = os.path.join(tempfile.gettempdir(), "_edge_pptx_notext.pptx")
    try:
        slides = [{"type": 1, "content": [{"type": "paragraph"}, {"type": "bullets", "items": ["hi"]}]}]
        result = write_pptx(path=tmp, slides=slides)
        assert not _has_error(result), f"content without text error: {_error_msg(result)}"
    finally:
        os.path.exists(tmp) and os.remove(tmp)


# ═══════════════════════════════════════════════
# 5) timer_set — extreme delays
# ═══════════════════════════════════════════════
def test_timer_set_nan_delay():
    """BUG: timer_set:77 — float('nan') comparisons ALWAYS False → passes both guards → call_later(nan) crash"""
    from app.tools.timer.timer_set import timer_set
    result = asyncio.run(timer_set(delay=float('nan'), callback="test"))
    # nan <= 0 → False, nan > 86400 → False, so both checks pass
    # loop.call_later(float('nan'), ...) → ?
    if _has_error(result):
        print(f"\n  INFO: nan delay caught: {_error_msg(result)}")
    else:
        print(f"\n  BUG CONFIRMED?: float('nan') passed guards, result OK? timer_id: {_data(result).get('timer_id')}")

def test_timer_set_inf_delay():
    """BUG: timer_set:81 — float('inf') > 86400 is True → rejected, OK. But float('inf') is not < 0 so what about second check?"""
    from app.tools.timer.timer_set import timer_set
    result = asyncio.run(timer_set(delay=float('inf'), callback="test"))
    # inf > 86400 → True → should be rejected
    assert _has_error(result), f"float('inf') should be rejected, got: {_data(result)}"
    print(f"\n  OK: inf delay rejected: {_error_msg(result)}")

def test_timer_set_negative_small():
    """EDGE: timer_set with delay=-1e-10 (tiny negative)"""
    from app.tools.timer.timer_set import timer_set
    result = asyncio.run(timer_set(delay=-1e-10, callback="test"))
    print(f"\n  INFO: tiny negative delay result: {_error_msg(result) if _has_error(result) else 'success'}")
    # timer_set accepts tiny negative (treats as 0), no error expected

def test_timer_set_callback_none():
    """BUG: timer_set:91 — callback=None → callback.strip() crashes"""
    from app.tools.timer.timer_set import timer_set
    try:
        result = asyncio.run(timer_set(delay=0.1, callback=None))
        if _has_error(result):
            print(f"\n  INFO: callback=None caught: {_error_msg(result)}")
        else:
            print(f"\n  OK?: callback=None didn't error")
    except Exception as e:
        print(f"\n  BUG CONFIRMED: callback=None crashed: {type(e).__name__}: {e}")

def test_timer_set_callback_empty():
    """EDGE: timer_set with empty callback string"""
    from app.tools.timer.timer_set import timer_set
    result = asyncio.run(timer_set(delay=0.1, callback=""))
    # callback.strip().startswith("http") → False → log_message path
    assert not _has_error(result), f"Empty callback error: {_error_msg(result)}"


# ═══════════════════════════════════════════════
# 6) mouse_click — edge cases
# ═══════════════════════════════════════════════
def test_mouse_click_button_none():
    """BUG: mouse_click:48 — button=None → pyautogui.click(button=None)"""
    from app.tools.desktop.mouse_click import mouse_click
    result = mouse_click(x=100, y=100, button=None)
    if _has_error(result):
        print(f"\n  BUG CONFIRMED: button=None caused error: {_error_msg(result)}")
    else:
        print(f"\n  OK?: button=None didn't error")

def test_mouse_click_button_zero():
    """BUG: mouse_click:48 — button=0 → pyautogui.click(button=0)"""
    from app.tools.desktop.mouse_click import mouse_click
    result = mouse_click(x=100, y=100, button=0)
    if _has_error(result):
        print(f"\n  BUG CONFIRMED: button=0 caused error: {_error_msg(result)}")

def test_mouse_click_x_only():
    """BUG: mouse_click:48 — x=100, y=None → pyautogui.click(y=None)"""
    from app.tools.desktop.mouse_click import mouse_click
    result = mouse_click(x=100, y=None)
    if _has_error(result):
        print(f"\n  BUG CONFIRMED: x=100,y=None caused error: {_error_msg(result)}")

def test_mouse_click_negative_coords():
    """EDGE: mouse_click with negative coords"""
    from app.tools.desktop.mouse_click import mouse_click
    result = mouse_click(x=-100, y=-100)
    if _has_error(result):
        print(f"\n  INFO: negative coords error (expected): {_error_msg(result)}")


# ═══════════════════════════════════════════════
# 7) keyboard_control — edge cases
# ═══════════════════════════════════════════════
def test_keyboard_control_none():
    """BUG: keyboard_control:42 — text_or_keys=None → None.isascii() → AttributeError"""
    from app.tools.desktop.keyboard_control import keyboard_control
    try:
        result = keyboard_control(action="type", text_or_keys=None)
        if _has_error(result):
            print(f"\n  INFO: None caught (in try): {_error_msg(result)}")
        else:
            print(f"\n  OK?: None didn't error")
    except Exception as e:
        print(f"\n  BUG CONFIRMED: keyboard_control(None) crashed: {type(e).__name__}: {e}")
        raise

def test_keyboard_control_none_shortcut():
    """BUG: keyboard_control:57 — shortcut with None → split crash"""
    from app.tools.desktop.keyboard_control import keyboard_control
    try:
        result = keyboard_control(action="shortcut", text_or_keys=None)
        if _has_error(result):
            print(f"\n  INFO: shortcut None caught: {_error_msg(result)}")
    except Exception as e:
        print(f"\n  BUG CONFIRMED: keyboard_control shortcut(None) crashed: {type(e).__name__}: {e}")
        raise

def test_keyboard_control_empty_keys():
    """EDGE: keyboard_control with empty string"""
    from app.tools.desktop.keyboard_control import keyboard_control
    result = keyboard_control(action="type", text_or_keys="")
    if _has_error(result):
        print(f"\n  INFO: empty type error: {_error_msg(result)}")


# ═══════════════════════════════════════════════
# 8) screen_capture — invalid region
# ═══════════════════════════════════════════════
def test_screen_capture_zero_region():
    """BUG: screen_capture:58-60 — region with width=0,height=0 → pyautogui.screenshot(region=(0,0,0,0)) crash"""
    from app.tools.desktop.screen_capture import screen_capture
    result = screen_capture(region={"x": 100, "y": 100, "width": 0, "height": 0})
    if _has_error(result):
        print(f"\n  BUG CONFIRMED: zero-sized region caused error: {_error_msg(result)}")

def test_screen_capture_negative_region():
    """BUG: screen_capture:58-60 — width=-50 → pyautogui.screenshot(region=(0,0,-50,-50)) crash"""
    from app.tools.desktop.screen_capture import screen_capture
    result = screen_capture(region={"x": 0, "y": 0, "width": -50, "height": -50})
    if _has_error(result):
        print(f"\n  BUG CONFIRMED: negative-size region caused error: {_error_msg(result)}")

def test_screen_capture_missing_region_keys():
    """BUG: screen_capture:59 — region.get('width', 800) defaults when keys missing"""
    from app.tools.desktop.screen_capture import screen_capture
    result = screen_capture(region={"color": "red"})  # no x,y,width,height
    if _has_error(result):
        print(f"\n  INFO: missing keys caught: {_error_msg(result)}")
    else:
        print(f"\n  INFO: missing keys used defaults (x=0,y=0,width=800,height=600)")


# ═══════════════════════════════════════════════
# 9) read_media_file — empty/corrupt
# ═══════════════════════════════════════════════
def test_read_media_file_zero_byte():
    """EDGE: readmedia with 0-byte file — base64 of empty is ''"""
    from app.tools.file.read_media_file import readmedia
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.close()
    os.truncate(tmp.name, 0)
    try:
        result = asyncio.run(readmedia(path=tmp.name))
        if not _has_error(result):
            b64 = _data(result).get("base64_data", "")
            assert b64 == "", f"Empty file should produce empty base64, got len={len(b64)}"
            print(f"\n  OK: 0-byte file returned empty base64")
        else:
            print(f"\n  INFO: 0-byte file error: {_error_msg(result)}")
    finally:
        os.path.exists(tmp.name) and os.remove(tmp.name)

def test_read_media_file_text_ext():
    """EDGE: readmedia with known text extension should reject"""
    from app.tools.file.read_media_file import readmedia
    tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
    tmp.close()
    try:
        result = asyncio.run(readmedia(path=tmp.name))
        assert _has_error(result), "Should reject .txt files"
        assert "文本" in _error_msg(result) or "text" in _error_msg(result).lower(), f"Wrong error: {_error_msg(result)}"
    finally:
        os.path.exists(tmp.name) and os.remove(tmp.name)

def test_read_media_file_unknown_ext():
    """EDGE: readmedia with unknown extension → uses application/octet-stream"""
    from app.tools.file.read_media_file import readmedia
    tmp = tempfile.NamedTemporaryFile(suffix=".xyz", delete=False)
    tmp.close()
    with open(tmp.name, 'wb') as f: f.write(b"hello")
    try:
        result = asyncio.run(readmedia(path=tmp.name))
        if not _has_error(result):
            mime = _data(result).get("mime_type", "")
            print(f"\n  INFO: unknown ext mime: {mime}")
            assert mime == "application/octet-stream", f"Wrong mime: {mime}"
        else:
            print(f"\n  INFO: unknown ext error: {_error_msg(result)}")
    finally:
        os.path.exists(tmp.name) and os.remove(tmp.name)


# ═══════════════════════════════════════════════
# 10) write_pdf — unicode/emoji
# ═══════════════════════════════════════════════
def test_write_pdf_emoji_content():
    """EDGE: write_pdf with emoji — reportlab font may not support"""
    from app.tools.document.write_pdf import write_pdf
    tmp = os.path.join(tempfile.gettempdir(), "_edge_pdf_emoji.pdf")
    try:
        result = write_pdf(path=tmp, content="Hello 世界 🤖🎉 \u0000\u0001 control")
        if _has_error(result):
            print(f"\n  INFO: emoji error (expected if font missing): {_error_msg(result)[:100]}")
    finally:
        os.path.exists(tmp) and os.remove(tmp)


# ═══════════════════════════════════════════════
# 11) timer_set — callback with bad URL crash
# ═══════════════════════════════════════════════
def test_timer_set_callback_bad_url():
    """EDGE: timer_set callback=http://bad.url that times out"""
    from app.tools.timer.timer_set import timer_set, _timer_events
    _timer_events.clear()
    result = asyncio.run(timer_set(delay=0.01, callback="http://192.0.2.1:1/"))
    assert not _has_error(result), f"bad URL error: {_error_msg(result)}"
    import time
    time.sleep(0.1)
    # Should have a timeout event
    print(f"\n  INFO: bad URL timer events: {len(_timer_events)}")


# ═══════════════════════════════════════════════
# 12) timer_clear with non-existent timer_id
# ═══════════════════════════════════════════════
def test_timer_clear_nonexistent():
    """EDGE: timer_clear with non-existent id"""
    from app.tools.timer.timer_clear import timer_clear
    result = asyncio.run(timer_clear(timer_id="nonexistent_123"))
    assert not _has_error(result), f"Nonexistent clear error: {_error_msg(result)}"
    msg = result.get("llm_data", {}).get("status", {}).get("message", "")
    assert "已取消" not in msg, "Non-existent timer should not be marked as cancelled"


# ═══════════════════════════════════════════════
# 13) write_docx — both content & table_data simultaneously
# ═══════════════════════════════════════════════
def test_write_docx_both_content_and_table():
    """BUG: write_docx:175 — elif table_data → table ignored when content is also provided"""
    from app.tools.document.write_docx import write_docx
    tmp = os.path.join(tempfile.gettempdir(), "_edge_docx_both.docx")
    try:
        result = write_docx(path=tmp, title="Title", content="Some text",
                            table_data=[["H1","H2"],["v1","v2"]])
        assert not _has_error(result), f"Both content/table error: {_error_msg(result)}"
    finally:
        os.path.exists(tmp) and os.remove(tmp)


if __name__ == "__main__":
    import subprocess
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-xvs", "--tb=long"]))
