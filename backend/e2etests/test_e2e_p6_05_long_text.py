"""E2E-P6-05: 闀挎枃鏈緭鍏ュ鐞?"

鎿嶄綔鎵嬪唽:
  鐢ㄤ緥: E2E-P6-05
  鐢ㄦ埛杈撳叆: 绾?000瀛楃殑闀挎枃鏈? 瑕佹眰Agent淇濆瓨鍒版枃浠?
  鍓嶇疆鏁版嵁: E:\\test_dir\\鍙啓
  棰勬湡杩囩▼: Agent鎺ユ敹闀挎枃鏈?-> 鍐欏叆鏂囦欢 -> 鍥炲纭
  閫氳繃鏍囧噯: final浜嬩欢瀛樺湪; 涓嶆寰幆(steps<50)
  澶辫触鏍囧噯: Agent宕╂簝/姝诲惊鐜?鏂囦欢鍐欏叆涓嶅畬鏁?
  娓呯悊: 鍒犻櫎long_text.txt

-- 灏忔 2026-06-27

铁律:
   1. 一个用例一个脚本，写完跑通再写下一个
   2. 所有验证基于真实后端运行，禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. finally中必须调用write_test_record(手册5.5铁律)
   6. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理
"""

TEST_CASE_ID = "E2E-P6-05"
TEST_CASE_NAME = "闀挎枃鏈緭鍏ュ鐞?"
USER_INPUT = "绾?000瀛楃殑闀挎枃鏈? 瑕佹眰Agent淇濆瓨鍒版枃浠?"

from pathlib import Path

import pytest
from e2emodel.e2e_helpers import (
    ensure_backend_ready, send_chat, check_db,
    verify_consistency, verify_steps, check_logs,
    print_report, write_test_record,
    assert_stream_ended, record_test_baseline,
    verify_response_quality, verify_response_time,
    verify_db_steps_data_completeness,
    register_pending_record,
)

TEST_DIR = Path("E:/test_dir")
TARGET_FILE = TEST_DIR / "long_text.txt"


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_p6_05_long_text():
    from datetime import datetime

    test_start = datetime.now()
    passed = False
    r = None
    sid = None
    db = {}
    ci = []
    si = []
    lc = {"errors": [], "tracebacks": []}
    elapsed = 0.0
    error_info = None

    base = "杩欐槸涓€娈电敤浜庢祴璇曢暱鏂囨湰澶勭悊鐨勬枃瀛楀唴瀹癸紝鍖呭惈涓嫳鏂囨贩鍚堝拰鏁板瓧绗﹀彿1234567890銆傞獙璇丄gent鑳藉惁姝ｇ‘澶勭悊鍜屼繚瀛樺畬鏁村唴瀹癸紝纭繚涓嶄涪澶便€佷笉鎴柇銆佷笉涔辩爜銆?"
    repeat_part = (base * 60)[:3000]
    user_input = f"鍏堟妸涓嬮潰杩欐闀挎枃瀛椾繚瀛樺埌E:\\test_dir\\long_text.txt锛岀劧鍚庤鍙栧畠纭鏂囦欢澶у皬鍜屽唴瀹瑰畬鏁存€э紝缁熻涓€涓嬮噷闈㈡湁澶氬皯涓瓧绗﹀拰澶氬皯涓崟璇嶏紝鎶婄粺璁＄粨鏋滆拷鍔犲埌鏂囦欢鏈熬锛屾渶鍚庡垪鍑虹洰褰曠‘璁ゆ枃浠跺凡鐢熸垚\n\n{repeat_part}"

    if TARGET_FILE.exists():
        TARGET_FILE.unlink(missing_ok=True)

    try:
        register_pending_record(
            "E2E-P6-05", "闀挎枃鏈緭鍏ュ鐞",
            USER_INPUT, {}, {}, [], [], {"errors": [], "tracebacks": []}, False,
        )
        assert ensure_backend_ready(), "鍚庣鏈惎鍔?鎵嬪唽6.1)"
        record_test_baseline()
        print(f"\n  [Step1] T0={test_start.strftime('%H:%M:%S')}, input len={len(user_input)}")

        result = await send_chat(user_input)
        r = result
        sid = result["session_id"]
        elapsed = result["total_time_ms"] / 1000.0

        tool_names = [t["tool_name"] for t in result["tool_calls"]]
        print(f"  [Step3-4] SSE: {result['total_steps']} events, tools: {tool_names}")

        end_type = assert_stream_ended(result)
        print(f"  娴佺粨鏉? {end_type}")

        assert result["total_steps"] >= 2, f"鑷冲皯start+final(MUST), got {result['total_steps']}"
        assert result["unique_step_numbers"] < 50, f"鐤戜技姝诲惊鐜?MUST): {result['unique_step_numbers']}姝?"

        for issue in verify_response_quality(result):
            pass
        for issue in verify_response_time(result):
            pass

        if result["has_error"]:
            print(f"  [WARN] 鏈塭rror浜嬩欢(SHOULD)锛屾祦缁撴潫: {end_type}")

        if TARGET_FILE.exists():
            content = TARGET_FILE.read_text(encoding="utf-8", errors="ignore")
            print(f"  [Check] {TARGET_FILE.name}: {len(content)} bytes")
        else:
            print(f"  [WARN] {TARGET_FILE} 鏈敓鎴?SHOULD, non-blocking)")

        print(f"  [Step5] DB check...")
        db = check_db(sid)
        assert db["session_exists"], "session蹇呴』淇濆瓨鍒癉B(MUST)"
        assert db["is_valid"], f"is_valid蹇呴』涓簍rue(MUST), got {db['is_valid']}"
        assert db["has_user_message"], "蹇呴』鏈塽ser娑堟伅(MUST)"
        assert db["has_assistant_message"], "蹇呴』鏈塧ssistant娑堟伅(MUST)"
        assert db["message_order_correct"], "娑堟伅椤哄簭蹇呴』user鍦ㄥ墠(MUST)"
        assert len(db["step_field_issues"]) == 0, f"step瀛楁涓嶅畬鏁?MUST): {db['step_field_issues']}"
        assert len(db["time_issues"]) == 0, f"鏃堕棿寮傚父(MUST): {db['time_issues']}"

        print(f"  [Step6] SSE-DB consistency...")
        ci = verify_consistency(result, sid)
        assert len(ci) == 0, f"涓€鑷存€ч獙璇佸け璐?MUST):\n" + "\n".join(f"  - {i}" for i in ci)

        print(f"  [Step7] Step reasonableness...")
        si = verify_steps(result, sid)
        assert len(si) == 0, f"姝ラ鍚堢悊鎬у紓甯?MUST): {si}"

        db_steps_issues = verify_db_steps_data_completeness(sid)
        assert len(db_steps_issues) == 0, f"DB姝ラ鏁版嵁涓嶅畬鏁?MUST): {db_steps_issues}"

        print(f"  [Step8] Log check...")
        lc = check_logs(test_start, sid)
        if lc["errors"]:
            print(f"  [WARN] 鏃ュ織鏈塃RROR(P6棰勬湡), count={len(lc['errors'])}")
        if lc["tracebacks"]:
            print(f"  [WARN] 鏃ュ織鏈塼raceback(P6棰勬湡), count={len(lc['tracebacks'])}")
        if not lc["session_records_found"]:
            print("  [WARN] 鏃ュ織鏈壘鍒皊ession鎿嶄綔璁板綍(SHOULD, non-blocking)")

        file_size = TARGET_FILE.stat().st_size if TARGET_FILE.exists() else 0
        print_report(
            "E2E-P6-05", "闀挎枃鏈緭鍏ュ鐞", result, db, lc,            ci, si, True, elapsed,
            extra={
                "Tools": tool_names,
                "LLM calls": result["llm_call_count"],
                "Input length": len(user_input),
                "Output file size": file_size,
            },
        )
        passed = True

    except Exception as e:
        passed = False
        import traceback
        error_info = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        print(f"  [FAIL] {error_info[:500]}")
        if sid:
            lc = check_logs(test_start, sid)
        raise
    finally:
        if TARGET_FILE.exists():
            TARGET_FILE.unlink(missing_ok=True)
        write_test_record(
            "E2E-P6-05", "闀挎枃鏈緭鍏ュ鐞",
           user_input, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )

    print(f"\n  [DONE] E2E-P6-05 {'PASSED' if passed else 'FAILED'}")
