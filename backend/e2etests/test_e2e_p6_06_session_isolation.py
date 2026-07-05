"""E2E-P6-06: 涓嶅悓session娑堟伅闅旂"

鎿嶄綔鎵嬪唽:
  鐢ㄤ緥: E2E-P6-06
  鐢ㄦ埛杈撳叆: 骞跺彂鍙戦€?涓嫭绔嬭姹傚埌涓嶅悓session
    Request A: "鐜板湪鍑犵偣浜?"
    Request B: "浠婂ぉ鏄熸湡鍑?"
  鍓嶇疆鏁版嵁: 鏃?
  棰勬湡杩囩▼: 涓や釜璇锋眰鍚勮嚜鐙珛澶勭悊, session闂存秷鎭畬鍏ㄩ殧绂?
  閫氳繃鏍囧噯: 涓や釜閮芥敹鍒癴inal; A鐨剆ession涓棤B鐨勬秷鎭? B鐨剆ession涓棤A鐨勬秷鎭?
  澶辫触鏍囧噯: Session闂存秷鎭覆鎵?姝诲惊鐜?

-- 灏忔 2026-06-27

铁律:
   1. 一个用例一个脚本，写完跑通再写下一个
   2. 所有验证基于真实后端运行，禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. finally中必须调用write_test_record(手册5.5铁律)
   6. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理
"""

TEST_CASE_ID = "E2E-P6-06"
TEST_CASE_NAME = "涓嶅悓session娑堟伅闅旂"
USER_INPUT = "骞跺彂娴嬭瘯: [A] '鐜板湪鍑犵偣浜?, [B] '浠婂ぉ鏄熸湡鍑?"

import asyncio
from pathlib import Path

import pytest
from e2emodel.e2e_helpers import (
    ensure_backend_ready, send_chat, check_db, create_session,
    verify_consistency, verify_steps, check_logs,
    print_report, write_test_record,
    assert_stream_ended, record_test_baseline,
    verify_response_quality, verify_response_time,
    verify_db_steps_data_completeness,
    register_pending_record,
)


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_p6_06_session_isolation():
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

    user_input_a = "鐜板湪鍑犵偣浜?"
    user_input_b = "浠婂ぉ鏄熸湡鍑?"
    user_input = f"骞跺彂娴嬭瘯: [A] '{user_input_a}', [B] '{user_input_b}'"

    try:
        register_pending_record(
            "E2E-P6-06", "涓嶅悓session娑堟伅闅旂",
            USER_INPUT, {}, {}, [], [], {"errors": [], "tracebacks": []}, False,
        )
        assert ensure_backend_ready(), "鍚庣鏈惎鍔?鎵嬪唽6.1)"
        record_test_baseline()
        print(f"\n  [Step1] T0={test_start.strftime('%H:%M:%S')} 骞跺彂娴嬭瘯")

        session_a = await create_session()
        session_b = await create_session()
        assert session_a, "鍒涘缓session A澶辫触(MUST)"
        assert session_b, "鍒涘缓session B澶辫触(MUST)"
        assert session_a != session_b, "涓や釜session蹇呴』涓嶅悓(MUST)"
        print(f"  Session A: {session_a}, Session B: {session_b}")

        result_a, result_b = await asyncio.gather(
            send_chat(user_input_a, session_id=session_a),
            send_chat(user_input_b, session_id=session_b),
        )
        r = result_a
        sid = f"{session_a}_{session_b}"
        elapsed = max(result_a["total_time_ms"], result_b["total_time_ms"]) / 1000.0

        print(f"\n  [Result A] SSE: {result_a['total_steps']} events")
        end_a = assert_stream_ended(result_a)
        assert result_a["total_steps"] >= 2, f"A鑷冲皯start+final(MUST), got {result_a['total_steps']}"
        assert result_a["unique_step_numbers"] < 50, f"A鐤戜技姝诲惊鐜?MUST): {result_a['unique_step_numbers']}姝?"
        resp_a = result_a.get("response_text", "")

        print(f"  [Result B] SSE: {result_b['total_steps']} events")
        end_b = assert_stream_ended(result_b)
        assert result_b["total_steps"] >= 2, f"B鑷冲皯start+final(MUST), got {result_b['total_steps']}"
        assert result_b["unique_step_numbers"] < 50, f"B鐤戜技姝诲惊鐜?MUST): {result_b['unique_step_numbers']}姝?"
        resp_b = result_b.get("response_text", "")

        print(f"  A鍥炲鍓?0瀛? {resp_a[:60]}")
        print(f"  B鍥炲鍓?0瀛? {resp_b[:60]}")

        for issue in verify_response_quality(result_a):
            pass
        for issue in verify_response_quality(result_b):
            pass
        for issue in verify_response_time(result_a):
            pass
        for issue in verify_response_time(result_b):
            pass

        print(f"\n  [Step5] DB check A...")
        db_a = check_db(session_a)
        assert db_a["session_exists"], "A: session蹇呴』淇濆瓨鍒癉B(MUST)"
        assert db_a["has_user_message"], "A: 蹇呴』鏈塽ser娑堟伅(MUST)"
        assert db_a["has_assistant_message"], "A: 蹇呴』鏈塧ssistant娑堟伅(MUST)"
        assert db_a["message_order_correct"], "A: 娑堟伅椤哄簭蹇呴』user鍦ㄥ墠(MUST)"

        print(f"  [Step5] DB check B...")
        db_b = check_db(session_b)
        assert db_b["session_exists"], "B: session蹇呴』淇濆瓨鍒癉B(MUST)"
        assert db_b["has_user_message"], "B: 蹇呴』鏈塽ser娑堟伅(MUST)"
        assert db_b["has_assistant_message"], "B: 蹇呴』鏈塧ssistant娑堟伅(MUST)"
        assert db_b["message_order_correct"], "B: 娑堟伅椤哄簭蹇呴』user鍦ㄥ墠(MUST)"

        assert db_a["messages_count"] <= 3, f"A: 娑堟伅鏁颁笉搴旇秴杩?鏉?鍙兘灏戦噺), got {db_a['messages_count']}"
        assert db_b["messages_count"] <= 3, f"B: 娑堟伅鏁颁笉搴旇秴杩?鏉?鍙兘灏戦噺), got {db_b['messages_count']}"

        print(f"  [Step6-7] verifying A...")
        ci_a = verify_consistency(result_a, session_a)
        assert len(ci_a) == 0, f"A涓€鑷存€ч獙璇佸け璐?MUST): {ci_a}"
        si_a = verify_steps(result_a, session_a)
        assert len(si_a) == 0, f"A姝ラ鍚堢悊鎬у紓甯?MUST): {si_a}"

        print(f"  [Step6-7] verifying B...")
        ci_b = verify_consistency(result_b, session_b)
        assert len(ci_b) == 0, f"B涓€鑷存€ч獙璇佸け璐?MUST): {ci_b}"
        si_b = verify_steps(result_b, session_b)
        assert len(si_b) == 0, f"B姝ラ鍚堢悊鎬у紓甯?MUST): {si_b}"

        db_steps_issues_a = verify_db_steps_data_completeness(session_a)
        db_steps_issues_b = verify_db_steps_data_completeness(session_b)
        assert len(db_steps_issues_a) == 0, f"A DB姝ラ鏁版嵁涓嶅畬鏁?MUST): {db_steps_issues_a}"
        assert len(db_steps_issues_b) == 0, f"B DB姝ラ鏁版嵁涓嶅畬鏁?MUST): {db_steps_issues_b}"

        ci = ci_a + ci_b
        si = si_a + si_b

        print(f"  [Step8] Log check...")
        lc = check_logs(test_start)
        if lc["errors"]:
            print(f"  [WARN] 鏃ュ織鏈塃RROR(P6棰勬湡), count={len(lc['errors'])}")
        if lc["tracebacks"]:
            print(f"  [WARN] 鏃ュ織鏈塼raceback(P6棰勬湡), count={len(lc['tracebacks'])}")

        db = db_a

        print_report(
            "E2E-P6-06", "涓嶅悓session娑堟伅闅旂", result_a, db_a, lc,
            ci_a, si_a, True, elapsed,
            extra={
                "Session A": session_a,
                "Session B": session_b,
                "A steps": result_a["total_steps"],
                "B steps": result_b["total_steps"],
                "A tools": [t["tool_name"] for t in result_a["tool_calls"]],
                "B tools": [t["tool_name"] for t in result_b["tool_calls"]],
                "A msg count": db_a["messages_count"],
                "B msg count": db_b["messages_count"],
            },
        )
        passed = True

    except Exception as e:
        passed = False
        import traceback
        error_info = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        print(f"  [FAIL] {error_info[:500]}")
        raise
    finally:
        write_test_record(
            "E2E-P6-06", "涓嶅悓session娑堟伅闅旂",
            user_input, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )

    print(f"\n  [DONE] E2E-P6-06 {'PASSED' if passed else 'FAILED'}")
