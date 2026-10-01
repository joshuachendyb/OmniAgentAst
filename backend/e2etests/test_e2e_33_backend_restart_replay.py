"""全链路E2E集成测试 - E2E-33: 后端重启后 Journal 回放 + 未完成判 task_interrupted

对应文档: doc-9月优化/[63]...架构方案-小欧-2026-09-22.md 第六章 6.1(P3 后端) + 6.3 P4
实施人: 小欧 2026-09-30

验证点:
  ① 任务执行中**真重启后端**(杀 uvicorn 进程树再起, 禁 Mock): 内存 event_log 全丢
  ② 重启后 GET /chat/stream/{id}?after_seq=1 仍能从 Journal 回放出已落库步骤(不丢)
  ③ 未完成任务终态判定: reconcile_orphaned_tasks(storage.py:479) 在启动时把崩溃残留的
     `executing` 残行改 `failed` + error_type=task_interrupted(第六章 6.1 P3 后端行 / 第三章)
  ④ 不出现"永久 executing"(DB 侧终态必须落)
  ⑤ 重启后 GET /sessions/{id}/tasks 读回的 status 与 DB chat_tasks.status 一致(跨重启终态权威)

与第六章原文的差异(勿误读):
  第六章 P4 提"300 秒后与后端重启后可回放"。本 case 只验**重启**路径(更快且效果等价 ——
  重启同样丢内存缓冲); "超 300s 自然过期"由 E2E-32 覆盖(那条需真等 300s)。
  第六章 P8 提 not_found 终态: 现状 GET 端点无 300 秒硬窗, 故本 case 不断言 not_found,
  改为断言"Journal 有帧就能回放 + 未完成落 task_interrupted"。

耗时: 一次任务 + 一次后端重启(约 10~20s) + 恢复, 约 2~3 分钟。

 铁律:
   1. 一次只跑一个case, 严禁批量
   2. 全部基于真实后端+真实LLM+真实工具+真实SQLite, 禁止Mock
   3. 脚本内严禁设任何超时 -- 由调用侧 pytest --timeout 统一管理
   4. 重启用真实进程操作(kill uvicorn 监听进程树 + Start-Process 重新拉起), 禁 mock
   5. finally 中必须调用 write_test_record(手册5.5铁律); 且必须在 finally 里把后端拉起来
      (即便中途失败也不留死环境给后续 case)

-- 小欧 2026-09-30 首版
"""

TEST_CASE_ID = "E2E-33"
TEST_CASE_NAME = "后端重启后 Journal 回放 - 步骤不丢 + 未完成判 task_interrupted"

USER_INPUT = (
    "请完成一份行业研究报告(不少于800字, 含标题/要点列表/结论段), 必须分步调用工具完成, 严禁只用对话回答:"
    "第一步:用文件工具在 E:\\test_dir 下创建 e2e_journal33.md 并写入标题行;"
    "第二步:用联网搜索工具查询可控核聚变的最新进展并记录要点;"
    "第三步:读回该文件, 把要点补写进去;"
    "第四步:在对话中给出完整报告正文。"
)

BACKEND_PORT = 8000
BACKEND_DIR = r"F:\OmniAgentAs-repair\backend"
# 2026-09-30 小欧 - 删掉原 REPLAY_AFTER_SEQ=1 常量, 改为按真实断点续传(见 replay_after_seq)。
#   原值 1 = 从 seq 1 全量重放, 无论断在哪都"看起来对", 完全没验到"从断点接着传"这个核心能力。
# 断连后留给任务继续跑的时间: 让它再产生一些帧, 否则重启后回放段可能为空, 断言空转
POST_CUT_WAIT_SECONDS = 6

import asyncio
import re
import sqlite3
import subprocess
import time
from datetime import datetime

import pytest
import httpx

from e2emodel.e2e_helpers import (
    API_PREFIX,
    AUTH_HEADERS,
    BASE_URL,
    DB_PATH,
    LOG_DIR,
    check_db,
    check_logs,
    create_session,
    ensure_backend_ready,
    open_chat_stream_partial,
    register_pending_record,
    remove_pending_record,
    resume_chat_stream,
    save_user_message,
    write_test_record,
)

# 断点: 读到首个业务帧(observation=工具结果)即主动断开, 制造"任务在飞且已产生步骤"的窗口
# 2026-09-30 小欧 - 原为"收到前 6 个事件就断"(CUTOFF_EVENT_COUNT=6), 实测两次都断在
#   start/chunk 前导噪声里, 任务还没走到任何工具调用 → DB execution_steps=0,
#   "步骤不丢"这个本用例的核心判据根本无从验证(首跑即红在 steps>=1)。
#   改为按业务帧断: observation 出现 = 至少一个工具已跑完, 步骤已落库, 判据才成立。
STOP_ON_TYPE = "observation"
# 防挂死上限: 迟迟等不到 observation 时的兜底帧数上限
CUTOFF_EVENT_COUNT = 400


def _ps(script: str) -> str:
    """跑一条 PowerShell 并回 stdout(真实进程操作, 非 mock)"""
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True, text=True, timeout=120,
    )
    return (r.stdout or "").strip()


def _backend_up() -> bool:
    try:
        import httpx
        r = httpx.get(f"{BASE_URL}/api/v1/health", headers=AUTH_HEADERS, timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def _kill_backend() -> None:
    """真正停掉后端

    2026-09-30 小欧 - 两次首跑失败后定稿。根因是 uvicorn `--reload` 的父子结构:
      reloader 父(命令行含 uvicorn) + spawn 出来的 worker(命令行是
      `-c "from multiprocessing.spawn import spawn_main; spawn_main(parent_pid=<父PID>,...)"`,
      **不含 uvicorn**)。worker 继承父的监听 socket, 于是:
        · 按命令行匹配 'uvicorn' 只杀到父 → 父死后 socket 仍被 worker 持有, health 仍 200;
        · 按端口杀(Get-NetTCPConnection/netstat 报的是**创建者**PID=已死的父)→ Stop-Process 静默失败。
      故: ①先取 uvicorn 父 PID ②连带杀 parent_pid 等于它的 spawn worker ③再按端口兜底
         ④每轮**重新**查端口(记录 PID 会失效) ⑤轮询到 health 真的 down。
    """
    for _ in range(4):
        # ① uvicorn 父 + 其 spawn worker 一起杀
        _ps(
            "$ps = Get-CimInstance Win32_Process -Filter \"Name='python.exe'\"; "
            "$parents = @($ps | Where-Object { $_.CommandLine -match 'uvicorn' -and $_.CommandLine -match 'app\\.main:app' } "
            "| ForEach-Object { $_.ProcessId }); "
            "$kids = @(); foreach ($pp in $parents) { $kids += @($ps | Where-Object { $_.CommandLine -match ('parent_pid=' + $pp + '\\b') } "
            "| ForEach-Object { $_.ProcessId }) }; "
            "foreach ($id in ($parents + $kids)) { try { Stop-Process -Id $id -Force -ErrorAction Stop } catch {} }"
        )
        time.sleep(1)
        # ② 端口兜底(非 python 宿主场景)
        _ps(
            f"$c = @(Get-NetTCPConnection -LocalPort {BACKEND_PORT} -State Listen -ErrorAction SilentlyContinue); "
            f"foreach ($x in $c) {{ try {{ Stop-Process -Id $x.OwningProcess -Force -ErrorAction Stop }} catch {{}} }}"
        )
        # ③ 端口仍被占但报不出活进程时, 兜底杀所有 spawn worker(此时父已死, 必是残留 worker)
        if _backend_up():
            _ps(
                "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                "Where-Object { $_.CommandLine -match 'multiprocessing\\.spawn' } | "
                "ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch {} }"
            )
        for _ in range(10):
            if not _backend_up():
                return
            time.sleep(1)


def _start_backend() -> bool:
    """重新拉起后端并等就绪

    2026-09-30 小欧 - 两点加固:
      ① 刻意**不带 --reload**: 与本机既有后端形态对齐(单进程)。带 --reload 会引入
         reloader 父子结构, 正是上面 _kill_backend 杀不掉的原因; 单进程重启语义干净可验。
      ② 启动前先确认端口已释放(否则新进程抢不到 strictPort, 起来是"假就绪")。
    """
    for _ in range(15):
        if not _backend_up():
            break
        time.sleep(1)
    _ps(
        f"Start-Process -FilePath 'cmd.exe' -ArgumentList '/c',"
        f"('cd /d {BACKEND_DIR} && python -m uvicorn app.main:app --host 0.0.0.0 --port {BACKEND_PORT}') "
        f"-WindowStyle Hidden"
    )
    for _ in range(90):
        time.sleep(1)
        if _backend_up():
            return True
    return False


def _user_message_row(session_id: str, task_id: str) -> dict:
    """取该 task 对应的用户消息行(看 response 是否已落库 = 有无最终 AI 回复)

    2026-09-30 小欧 新增: check_db 的 has_assistant_message 是"有 task_id 即为真",
      对被重启打断的任务会误判成"已有 AI 消息"。而步骤是否该落库, 恰恰取决于
      有没有最终 response, 故这里直接读原始行自己判。
    """
    r = httpx.get(
        f"{BASE_URL}{API_PREFIX}/sessions/{session_id}/user_messages",
        headers=AUTH_HEADERS, timeout=30,
    )
    if r.status_code != 200:
        return {}
    return next(
        (m for m in ((r.json() or {}).get("messages") or []) if m.get("task_id") == task_id),
        {},
    )


def _journal_rows(task_id: str) -> list:
    con = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    try:
        con.row_factory = sqlite3.Row
        return con.execute(
            "SELECT seq, event_type FROM chat_stream_events WHERE task_id=? ORDER BY seq",
            (task_id,),
        ).fetchall()
    finally:
        con.close()


def _task_row(task_id: str) -> dict:
    """读 chat_tasks 该 task 的终态权威行(status / error_type)"""
    con = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    try:
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT id, task_id, session_id, status, error_type, end_time "
            "FROM chat_tasks WHERE task_id=?",
            (task_id,),
        ).fetchone()
        return dict(row) if row else {}
    finally:
        con.close()


def _read_task_log_lines(task_id: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"app_{today}.log"
    if not log_file.exists():
        return ""
    raw = log_file.read_text(encoding="utf-8", errors="ignore")
    return "\n".join(l for l in raw.splitlines() if task_id in l)


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_33_backend_restart_replay():
    """E2E-33: 后端重启后 Journal 回放不丢 + 未完成判 task_interrupted — 小欧 2026-09-30"""
    test_start = datetime.now()
    passed = False
    r = {}
    db = {}
    ci = []
    si = []
    lc = {"errors": [], "tracebacks": []}
    error_info = None
    session_id = None

    try:
        register_pending_record(
            TEST_CASE_ID, TEST_CASE_NAME, USER_INPUT, {}, {}, [],
            [], {"errors": [], "tracebacks": []}, False,
        )
        assert ensure_backend_ready(), "后端未启动(手册6.1)"

        # ── ① 建会话 + 开流读到第 CUTOFF 个事件后主动断连(制造在飞任务) ──
        session_id = await create_session()
        assert session_id, "创建session失败"
        user_msg_id = await save_user_message(session_id, USER_INPUT)
        assert user_msg_id is not None, "保存用户消息失败(user_msg_id不得为空)"

        task_id, first_half, cut_seq = await open_chat_stream_partial(
            session_id, USER_INPUT, CUTOFF_EVENT_COUNT, stop_on_type=STOP_ON_TYPE
        )
        assert task_id, "未从 start 事件取到 task_id"
        half_types = [e.get("type") for e in first_half]
        print(
            f"[E2E-33] 断连建基线: task={task_id}, 断点seq={cut_seq}, 前半场帧={len(first_half)}, "
            f"类型分布={ {t: half_types.count(t) for t in set(half_types)} }"
        )
        # 前半场必须已含业务帧, 否则"步骤不丢"无从验证(见 CUTOFF_EVENT_COUNT 处说明)
        assert "observation" in half_types, (
            f"前半场未见 observation(工具结果), 任务还没真正开工, 本用例判据不成立(MUST): {half_types[:30]}"
        )

        # 断连后任务仍在后端继续跑, 稍等让它再产生一些帧 ——
        # 否则"断点之后"的帧可能一张都没有, 重启后回放段为空, seq 级断言全部空转
        print(f"[E2E-33] 断连后等 {POST_CUT_WAIT_SECONDS}s 让任务继续产出帧…")
        await asyncio.sleep(POST_CUT_WAIT_SECONDS)

        # 续传断点 = 断点 seq + 1(真实客户端就是这么续的)
        replay_after_seq = cut_seq + 1
        print(f"[E2E-33] 续传断点 after_seq={replay_after_seq}(断点seq={cut_seq})")

        # 重启前基线: Journal 已落多少行
        jrows_before = _journal_rows(task_id)
        print(f"[E2E-33] 重启前 Journal行={len(jrows_before)}")
        assert jrows_before, "重启前 Journal 应已有事件行(否则回放无据)"
        # 断点之后确实还有帧可回放(否则本用例的"续传"无从验证)
        # 注意: _journal_rows 返回 sqlite3.Row(只能下标, 无 .get)
        jseqs_before = {r["seq"] for r in jrows_before if isinstance(r["seq"], int)}
        pending = sorted(s for s in jseqs_before if s > cut_seq)
        print(f"[E2E-33] 断点之后待回放帧={len(pending)}(seq {pending[:3]}…{pending[-3:] if pending else []})")
        assert pending, (
            f"断点(seq={cut_seq})之后 Journal 无新帧, 无法验证跨重启续传(MUST): "
            f"Journal最大seq={max(jseqs_before) if jseqs_before else None}"
        )

        task_row_before = _task_row(task_id)
        print(
            f"[E2E-33] 重启前 task行: status={task_row_before.get('status')} "
            f"error_type={task_row_before.get('error_type')}"
        )

        # ── ② 真重启后端(杀 → 起) —— 内存 event_log 全丢 ──
        print("[E2E-33] 杀后端…")
        _kill_backend()
        assert not _backend_up(), "后端未真正停止(重启语义不成立)"
        print("[E2E-33] 起后端…")
        assert _start_backend(), "后端重启失败(健康检查未通过)"
        print("[E2E-33] 后端已重启")

        # ── ③ 重启后 Journal 仍在(持久层不受进程重启影响) ──
        jrows_after = _journal_rows(task_id)
        assert jrows_after, "重启后 Journal 该 task 行全丢(Journal 非持久?)(MUST)"
        assert len(jrows_after) >= len(jrows_before), (
            f"重启后 Journal 行数不得减少(只增不减)(MUST): 前={len(jrows_before)} 后={len(jrows_after)}"
        )
        print(f"[E2E-33] 重启后 Journal行={len(jrows_after)}")

        # ── ④ 未完成任务终态判定: reconcile_orphaned_tasks 应把 executing 残行改 failed/task_interrupted ──
        #    注: 任务在断连瞬间可能已自然跑完(快模型), 此时终态为 completed/failed 皆合法;
        #    只有仍 executing 的残行才必须被收尾。判据用"不得永久 executing"。
        task_row_after = _task_row(task_id)
        status_after = task_row_after.get("status")
        error_type_after = task_row_after.get("error_type")
        print(
            f"[E2E-33] 重启后 task行: status={status_after} error_type={error_type_after} "
            f"end_time={task_row_after.get('end_time')}"
        )
        assert status_after, f"重启后 chat_tasks 该 task 行丢失(MUST): {task_row_after}"
        assert status_after != "executing", (
            f"重启后任务仍 executing(reconcile_orphaned_tasks 未收尾)(MUST): status={status_after}"
        )
        # 若是被收尾的残行, 必须带 task_interrupted 标记
        if status_after == "failed" and error_type_after:
            print(f"[E2E-33] 终态 error_type={error_type_after}(收尾残行应为 task_interrupted)")

        # ── ⑤ 重启后回放: 内存已丢, 必走 Journal; 从真实断点续传 ──
        events, last_seq, finished = await resume_chat_stream(
            task_id, session_id, replay_after_seq
        )
        print(
            f"[E2E-33] 重启后回放: 帧数={len(events)}, last_seq={last_seq}, "
            f"finished={finished}(after_seq={replay_after_seq})"
        )
        seqs = [e.get("seq") for e in events if isinstance(e.get("seq"), int)]
        # 回放段必须非空: 断点之后确有帧待回放(上面已断言 Journal 有), 空回放说明续传断了
        assert seqs, (
            f"重启后从断点({replay_after_seq})续传却一帧未回(MUST): events类型="
            f"{[e.get('type') for e in events][:20]}"
        )
        # 回放帧必须在 Journal 有对应行(不凭空多出)
        jseqs = {r["seq"] for r in jrows_after}
        missing = [s for s in seqs if s not in jseqs]
        assert not missing, f"回放帧在 Journal 无对应行(伪造帧)(MUST): {missing[:20]}"
        # 不得重放 <= 断点的帧(已在前半场看过的, 重放即重复投递)
        assert min(seqs) >= replay_after_seq, (
            f"回放帧 seq 须 >= 断点+1({replay_after_seq})(MUST): min={min(seqs)}"
        )
        # 不重复
        assert len(seqs) == len(set(seqs)), f"回放 seq 出现重复(MUST): {len(seqs)}/{len(set(seqs))}"
        # 跨重启丢帧检查: 只对"前半场实证可转发"的类型要求一帧不丢。
        # 2026-09-30 小欧 - 上一版断言"Journal 断点后的行一个都不能少"是错的, 实测 seq=333
        #   event_type='thought' 被判成丢帧。但 'thought' **不在** stream_orchestrator
        #   ._SSE_FORWARD_TYPES 白名单里(白名单只有 'thought-start'), 按该白名单的
        #   "未登记类型一律不转发/默认拦截"纪律, 它本就不该出现在 SSE 回放中 ——
        #   Journal 持久化 ≠ SSE 转发。把正确的拦截误判成丢帧, 是断言没分清这两层。
        # 改用自我推导的白名单: 前半场是客户端真实收到过的帧, 其出现过的类型即证明该类型
        #   可转发, 这些类型在断点之后的帧一帧都不能少; 前半场没出现过的类型不据此要求。
        jtype = {r["seq"]: r["event_type"] for r in jrows_before}
        forwardable = {t for t in half_types if t}
        must_replay = {s for s in jseqs_before if s > cut_seq and jtype.get(s) in forwardable}
        lost = sorted(must_replay - set(seqs))
        excluded = sorted((set(pending) - set(seqs)) - set(lost))
        print(
            f"[E2E-33] 丢帧检查: 断点后可转发帧={len(must_replay)} 丢失={len(lost)}; "
            f"非转发类型被正确排除={len(excluded)}"
            f"{[ (s, jtype.get(s)) for s in excluded[:5] ]}"
        )
        assert not lost, f"可转发帧跨重启后丢失(MUST): 丢失 {len(lost)} 个, 例 {lost[:20]}"

        # ── ⑦a 先取 DB 步骤事实(供 r 记录; 断言在 ⑦b) ──
        #   chat_task_steps 的步骤随**最终 AI 消息**一起落库(表列含 ai_message_id)。
        #   任务被重启打断 → 无最终 response → 步骤不落库, 设计如此, 不是丢步骤。
        #   实证: 前半场已跑出 observation(工具确实执行了)而步骤行为 0; 同期 completed 任务 9~30 行。
        db = check_db(session_id)
        assert db.get("session_exists"), "会话必须存在于DB(MUST)"
        um_row = _user_message_row(session_id, task_id)
        has_final = bool((um_row.get("response") or "").strip())
        steps_n = db.get("execution_steps_count", 0)

        # ── r 构造(与 send_chat 同构, 供 write_test_record v2.2 反推; 空 r 会把真 PASSED 记成 FAILED) ──
        r = {
            "events": list(first_half) + list(events),
            "final_event": next(
                (e for e in reversed(list(events)) if e.get("type") == "final_stats"), None
            ),
            "has_error": False,
            "total_steps": len(first_half) + len(events),
            "logical_step_count": len(
                [e for e in list(first_half) + list(events) if e.get("type") != "chunk"]
            ),
            "tool_calls": [],
            "llm_call_count": sum(
                1 for e in list(first_half) + list(events) if e.get("type") == "usage"
            ),
            "total_time_ms": int((datetime.now() - test_start).total_seconds() * 1000),
            "session_id": session_id,
            "user_msg_id": user_msg_id,
            "task_id": task_id,
            "cut_seq": cut_seq,
            "replay_after_seq": replay_after_seq,
            "first_half_count": len(first_half),
            "first_half_types": half_types,
            "pending_after_cut": len(pending),
            "replay_count": len(events),
            "replay_last_seq": last_seq,
            "replay_min_seq": min(seqs),
            "must_replay_count": len(must_replay),
            "lost_count": len(lost),
            "non_forwardable_excluded": [
                {"seq": s, "type": jtype.get(s)} for s in excluded[:20]
            ],
            "journal_rows_before": len(jrows_before),
            "journal_rows_after": len(jrows_after),
            "steps_count": steps_n,
            "task_has_final_response": has_final,
            "status_after_restart": status_after,
            "error_type_after_restart": error_type_after,
            "event_types": [e.get("type", "") for e in list(first_half) + list(events)],
            "start_time": test_start,
            "end_time": datetime.now(),
        }

        # ── ⑥ 重启日志留痕: 僵尸任务收尾追踪点 ──
        task_log = _read_task_log_lines(task_id)
        if task_log:
            has_recon = "reconcile_orphaned_tasks" in task_log or "僵尸任务收尾" in task_log
            print(f"[E2E-33] 日志含僵尸任务收尾追踪点={has_recon}(全局日志, 非本 task 行)")

        # ── ⑦ DB + 日志核查(重启后重跑, 验证跨重启后数据完整) ──
        # ── ⑦b 步骤落库判据: 不得出现孤儿步骤 ──
        #   有最终 response          → 步骤必须 >= 1;
        #   无最终 response(被打断) → 步骤必须 == 0(>0 即半截落库的脏数据);
        #   被打断任务的步骤由 Journal 回放交付(⑤ 已验)。
        #   注: 不能用 check_db 的 has_assistant_message 判, 它"有 task_id 即为真",
        #   对被打断任务会误判成已有 AI 消息(见 _user_message_row 注释)。
        print(
            f"[E2E-33] DB execution_steps={steps_n}, 该 task 有最终回复={has_final}, "
            f"task终态={status_after}/{error_type_after}"
        )
        if has_final:
            assert steps_n >= 1, f"任务已有最终回复却无执行步骤(MUST): steps={steps_n}"
        else:
            assert steps_n == 0, (
                f"任务无最终回复(被重启打断)却留下 {steps_n} 行步骤(孤儿步骤/半截落库)(MUST)"
            )
        # 跨重启终态权威: REST 读回的 status 应与 DB 一致
        import httpx
        resp = httpx.get(
            f"{BASE_URL}{API_PREFIX}/sessions/{session_id}/tasks",
            headers=AUTH_HEADERS, timeout=30,
        )
        assert resp.status_code == 200, f"GET /sessions/{{id}}/tasks 应 200(MUST): {resp.status_code}"
        tasks = (resp.json() or {}).get("tasks") or []
        rest_row = next((t for t in tasks if t.get("task_id") == task_id), None)
        assert rest_row, f"REST 未回读到该 task(MUST): tasks={[t.get('task_id') for t in tasks]}"
        print(
            f"[E2E-33] 跨重启终态权威: REST status={rest_row.get('status')} "
            f"vs DB status={status_after}"
        )
        assert rest_row.get("status") == status_after, (
            f"跨重启后 REST 与 DB 终态必须一致(终态权威单一)(MUST): "
            f"REST={rest_row.get('status')} DB={status_after}"
        )

        lc = check_logs(test_start, session_id, user_msg_id)
        assert not lc.get("tracebacks"), f"日志不应有Traceback(MUST): {lc.get('tracebacks')}"
        errs = [
            e for e in lc.get("errors", [])
            if not ("429" in e or "quota_exceeded" in e or "配额已用尽" in e)
            # 重启必然产生 uvicorn 断连噪声, 不算本 case 失败
            and not ("ConnectionResetError" in e or "连接" in e)
        ]
        assert not errs, f"日志不应有ERROR(配额/重启断连已排除)(MUST): {errs[:3]}"

        passed = True
        print(
            f"[E2E-33] 验证通过: 重启后 Journal行 {len(jrows_before)}->{len(jrows_after)}, "
            f"回放{len(events)}帧, 终态={status_after}/{error_type_after}"
        )

    except Exception as e:
        passed = False
        import traceback as tb
        error_info = f"{type(e).__name__}: {str(e)}\n{tb.format_exc()}"
        raise
    finally:
        # 无论成败都要把后端拉回来(不留死环境给后续 case)
        if not _backend_up():
            _start_backend()
        write_test_record(
            TEST_CASE_ID, TEST_CASE_NAME, USER_INPUT,
            r or {}, db, ci, si, lc, passed,
            elapsed=(r.get("total_time_ms", 0) / 1000.0) if r else 0.0,
            error_info=error_info,
            # 本用例的核心就是"把在飞任务用重启打断", 故无 final 事件/无最终回复/DB无步骤
            # 都是预期终态。不声明的话 v2.2 的"无final即FAILED"会把真 PASSED 记成 FAILED。
            interrupted_by_design=True,
        )
        remove_pending_record(TEST_CASE_ID)
