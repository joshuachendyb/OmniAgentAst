"""E2E-P6-08: 绌虹粨鏋滃満鏅閿?"

鎿嶄綔鎵嬪唽:
  鐢ㄤ緥: E2E-P6-08
  鐢ㄦ埛杈撳叆: "鍏堝垪鍑篍:\\test_dir涓嬬殑鎵€鏈夋枃浠讹紝鐒跺悗鍦‥:\\test_dir\\empty_dir涓悳绱㈡墍鏈?txt鏂囦欢锛屽啀鎶婁袱涓粨鏋滃姣斾竴涓嬶紝鏈€鍚庢妸鎼滅储鎯呭喌姹囨€讳繚瀛樺埌E:\\test_dir\\search_result.txt"
  鍓嶇疆鏁版嵁: empty_dir/涓虹┖鐩綍
  棰勬湡杩囩▼: Agent鎼滅储绌虹洰褰?-> 鏈壘鍒颁换浣曟枃浠?-> 鍥炲鍛婄煡鐢ㄦ埛鏃犵粨鏋?
  閫氳繃鏍囧噯: final浜嬩欢瀛樺湪; 鍥炲鍖呭惈"鏈壘鍒?/"娌 湁"/"绌?; 涓嶆寰幆(steps<50)
  澶辫触鏍囧噯: Agent宕╂簝/姝诲惊鐜?

-- 灏忔 2026-06-27

铁律:
   1. 一个用例一个脚本，写完跑通再写下一个
   2. 所有验证基于真实后端运行，禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. finally中必须调用write_test_record(手册5.5铁律)
   6. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理
"""

TEST_CASE_ID = "E2E-P6-08"
TEST_CASE_NAME = "绌虹粨鏋滃満鏅閿?"
USER_INPUT = "鍏堝垪鍑篍:\\test_dir涓嬬殑鎵€鏈夋枃浠讹紝鐒跺悗鍦‥:\\test_dir\\empty_dir涓悳绱㈡墍鏈?txt鏂囦欢锛屽啀鎶婁袱涓粨鏋滃姣斾竴涓嬶紝鏈€鍚庢妸鎼滅储鎯呭喌姹囨€讳繚瀛樺埌E:\\test_dir\\search_result.txt"

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
EMPTY_DIR = TEST_DIR / "empty_dir"


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_p6_08_empty_result():
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

    user_input = f"鍏堝垪鍑篍:\\test_dir涓嬬殑鎵€鏈夋枃浠讹紝鐒跺悗鍦{EMPTY_DIR}涓悳绱㈡墍鏈?txt鏂囦欢锛屽啀鎶婁袱涓粨鏋滃姣斾竴涓嬶紝鏈€鍚庢妸鎼滅储鎯呭喌姹囨€讳繚瀛樺埌E:\\test_dir\\search_result.txt"

    EMPTY_DIR.mkdir(parents=True, exist_ok=True)

    try:
        register_pending_record(
            "E2E-P6-08", "绌虹粨鏋滃満鏅閿",
            USER_INPUT, {}, {}, [], [], {"errors": [], "tracebacks": []}, False,
        )
        assert ensure_backend_ready(), "鍚庣鏈惎鍔?鎵嬪唽6.1)"
        record_test_baseline()
        print(f"\n  [Step1] T0={test_start.strftime('%H:%M:%S')}, input: {user_input}")

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

        resp = result.get("response_text", "")
        empty_keywords = ["鏈壘鍒", "娌 湁", "绌", "涓嶅瓨鍦", "鎵句笉鍒", "鏃犵粨鏋"]
        found = [k for k in empty_keywords if k in resp]
        print(f"  鍥炲鍚┖缁撴灉鍏抽敭璇? {found}")
        assert len(found) >= 1, f"鍥炲搴旀彁绀烘湭鎵惧埌鏂囦欢(MUST), 瀹為檯鍥炲鍓?00瀛? {resp[:100]}"

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

        print_report(
            "E2E-P6-08", "绌虹粨鏋滃満鏅閿", result, db, lc,
           ci, si, True, elapsed,
            extra={
                "Tools": tool_names,
                "LLM calls": result["llm_call_count"],
                "Keywords found": found,
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
        if EMPTY_DIR.exists():
            try:
                EMPTY_DIR.rmdir()
            except OSError:
                pass
        write_test_record(
            "E2E-P6-08", "绌虹粨鏋滃満鏅閿",
           user_input, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )

    print(f"\n  [DONE] E2E-P6-08 {'PASSED' if passed else 'FAILED'}")
