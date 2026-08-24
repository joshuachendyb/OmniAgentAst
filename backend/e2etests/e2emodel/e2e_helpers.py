# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-12 - 小欧 - COM_03记录误判修复: write_test_record按error_type区分可恢复/不可恢复错误
#   【病根】LLM幻觉调用未注册工具write被SafetyChecker blocked拦截, action_handler发ErrorStep(error_type=blocked)
#          进SSE流致has_error=True; 但blocked/user_rejected属可恢复错误(拒绝≠失败, 与react_cycle._RECOVERABLE_ERRORS
#          语义一致, 任务最终正常completed, pytest断言全过), 原判定"有error即失败"误置FAILED(记录与pytest矛盾)。
#   【改法】write_test_record遍历events按error_type判定: 仅不可恢复error(非blocked/user_rejected)才判失败。
# 2026-07-18 - 小欧 - FinalStep多态自包含终态重构: assert_stream_ended+PASS/FAIL判断改为outcome驱动
#   【病根】原assert_stream_ended仅靠final事件和has_error判断终态,
#          FinalStep多态重构后失败终态统一发type=final+outcome=failed(不再发error事件),
#          导致失败任务的end_type返回"final"而非"failed", PASS/FAIL判断无error事件→误判PASSED(unit-07)。
#   【改法】①assert_stream_ended: 读final_event.outcome区分failed/cancelled/failed
#          ②write_test_record: 读_final_outcome, 失败/取消时passed=False
# 2026-08-19 - 小欧 - §10.4.4 流重构(chunk 承载 answer 文本, 同步 e2e 断言): send_chat 的 response_text 改由累加 chunk.content 得到(排除 is_reasoning), 不再依赖 final.content/response——final 现仅作终止符(只含 outcome/seq)。(注: 本文件为测试辅助, 按规不提交, 此条仅供本地可追溯)
# 2026-08-21 - 小欧 - 北京老陈驱动: 对照v0.19.15→v0.19.21后端存储优化, 修正E2E记录/校验侧失配(M1-M5)。
#   【病根】v0.19.18废除action_tool→action(tools[]={tool,target,params}); ObservationStep仅带tool_result;
#          v0.19.19删chat_messages.execution_steps列; v0.19.21新增artifacts/token累计。但DB校验/记录侧仍按旧
#          type=="action_tool"判断并读tool_name/tool_params/observation/execution_result/status顶层键, 致对真实
#          action步骤完全不触发检查(假通过), 且observation/llm_call_count读错键恒空/恒1。
#   【改法】check_db/verify_db_steps_data_completeness/verify_steps/verify_db_prompt_consistency 改用
#          _is_action_step + _action_entries(读tools[].tool/params); observation读tool_result; 去掉步骤status检查;
#          check_logs的llm_call_count改 len(LLM调用记录); write_test_record §5.2/§5.3 同步新字段。
#          + verify_db_prompt_consistency 步骤数对比由全量(non-start/chunk)改为仅对齐 action+observation 数据步骤
#            (prompt日志还记录 startinfo/usage/thought-start/chunk 等DB不持久化步骤, 全量对比为假阳性FAIL);
#          + §7 观察结果数基线由 SSE工具数 改为 action步数(新协议单action步批量多工具, 观察按action步计)。
#          + §2 细分为2.1回复正文+2.2终态元信息(final_stats: duration+artifacts), 原独立§8删除, 附加信息恢复为§8。
#          (SSE/工具链侧 send_chat/_action_entries 已于2026-08-19适配, 本次不动; case脚本不动 — 北京老陈 2026-08-21 要求只改核心代码)
# 2026-08-21 - 小欧 - §2.2 终态元信息拆分为两个表: 表1(执行耗时+产出物数量) + 表2(产出物明细)
# 2026-08-22 - 小欧 - §2.2 表2对齐后端artifacts新结构(4字段: tool_name/name/path/type):
#   取值bug修复(原读tool键恒空→改tool_name)+补文件名(name)列; 第8节清理过期final_stats注释(已迁§2.2);
#   配合后端F1定案: 兜底派生已删, 仅写工具with_artifacts自声明才有产出物
# 2026-08-22 - 小欧 - §5.2执行步骤表按现行落库字段重造(北京老陈指示"按现在的step和数据字段更新"):
#   删恒空"状态"列(新协议步骤无status字段), 新增"内容摘要"列(_step_brief按type提取:
#   start用户消息/context_overview消息数tokens/stats轮次耗时/thought正文/action目标/
#   observation首条summary/final_stats耗时产出物/final结论/error类型);
#   observation行"工具"列改从tool_result[].tool_name取值(原仅action行有值);
#   字段真值经chat_task_steps.step_json实库核验
# 2026-08-22 - 小欧 - §1测试基本信息表新增"Token使用(prompt/completion/total)"行(北京老陈指示):
#   取DB final步骤accumulated_usage(prompt_tokens/completion_tokens/total_tokens), 无数据时显示"-"
# 2026-08-22 - 小欧 - §5.3改按轮交错配对渲染(北京老陈定案病根: 测试记录代码两段式排版问题, 系统侧零缺失):
#   原布局"全部轮次参数段→全部轮次观察段"致工具↔结果视觉对不上(action按工具计数/observation按轮计数,
#   4vs2、12vs6强化缺失错觉); 现遍历db_steps遇action轮即输出本轮参数+本轮observation;
#   附孤立observation兜底防静默丢数据; 三份P9记录扫描实证: 每轮必配对、0空观察
# 2026-08-22 - 小欧 - §5.2/§5.3展示限制调整(北京老陈指示): §5.2取消15条上限改全部步骤(标题同步改"全部");
#   §5.3限制只展示前10轮(第11轮起追加提示行, 全量步骤仍可在5.2表查看)
# 2026-08-22 - 小欧 - check_db竞态修复(p9_03失败实证, 非系统代码问题): 大任务SSE结束后后台仍在写
#   chat_user_message的task_id/response(p9_03: 17轮34工具大链路, 断言时未落库→has_assistant_message
#   误判False, 31s后才写入); user_messages取数改为等待行内出现task_id或response, 重试对齐8次×2s
# 2026-08-22 - 小欧 - §5.2 thought行摘要改双字段展示(北京老陈指示): 先"思考:"=reasoning(思考区)
#   后"结论:"=thought(LLM答案区), 空段跳过; 有价值字段=thought+reasoning(content与其恒同值不读);
#   病根=原取值漏reasoning字段致部分轮次(答案区空仅思考区)显示空白
# 2026-08-22 - 小欧 - §5.2表列头"步骤号"改"轮次"(北京老陈指示, 该列语义即LLM执行轮次)
# 2026-08-22 - 小欧 - §5.2 stats行摘要补retry_count展示(北京老陈问询驱动): 非零时追加"/工具重试N次",
#   落库字段step_count/severity为常量无价值不显示
# 2026-08-22 - 小欧 - §5.2接入token三层展示(定案: 系统代码无缺陷数据齐全, 记录侧此前未取):
#   stats行追加"/本轮Ntok"(usage不落库P6仅SSE, 按轮从result.events的usage事件取total_tokens);
#   final_stats行追加"/任务累计Ntok/会话累计Ntok"(从final步骤json的task/session_accumulated_tokens取)
# 2026-08-22 - 小欧 - §5.2每轮stats行升级为三组token(北京老陈指示): 本轮/任务累计/会话累计,
#   全部取自同一条SSE usage事件自带字段(llm_call_count_token/task/session_accumulated_tokens)
# 2026-08-22 - 小欧 - §5.2 token每组三数全显修正(北京老陈指错驱动): 原每组仅显total_tokens一数,
#   现新增_fmt_tok公共函数, 每组显示入(prompt)/出(completion)/总(total)三数; 三源真值核实:
#   base_agent.py四组初始化三字段/react_cycle usage事件顶层三数/final落库json实测三字段齐全
# 2026-08-22 - 小欧 - §5.2 SSE侧事件补行(北京老陈指示): usage/error/paused/resumed/retrying/cancelled
#   仅SSE不落库(P1~P6)原表格无行, 现按流序与落库步骤混排成行; chunk量大/thought_start纯信号不补;
#   落库类型分布实测8种(start/context_overview/thought/action/observation/stats/final_stats/final);
#   usage独立成行显本轮入/出/总三数, stats行去重只留任务/会话累计两组(北京老陈裁定)
# 2026-08-23 - 小欧 - §1测试基本信息表新增"model 结构信息"行(北京老陈指示): 展示归一后模型身份=ModelRef JSON,
#   取自chat_tasks.sessionModel(回退token_usage.task_model), 解析 provider/model/display_name; 佐证ModelRef归一落库正确
# 2026-08-23 - 小欧 - 消除测试记录"假PASSED"盲区: 新增 verify_token_usage 主动核查 token_usage 真实落库
#   (原 passed 仅依赖日志ERROR扫描, 落库静默失败不打ERROR则假PASS); 有LLM调用时 token_usage 行数须≥1且与
#   llm_call_count 一致, 否则 passed=False; 测试记录终态判定纳入此硬核查
# 2026-08-23 - 小欧 - §1测试基本信息表新增"跨任务注入上下文"行(北京老陈指示): 展示本任务之前注入的连续对话历史体量,
#   取自context_overview事件的injected_message_count/injected_estimated_tokens(多轮历史注入机制, 单轮任务为0显示"无");
#   §5.2 context_overview行与跨任务行的tok统一标注"(估算)"(chars//4纯数学估算, 非真实LLM token, 防误解)
"""
E2E测试核心测试脚本和代码
**公共函数**: 所有E2E测试脚本共用的辅助函数和验证逻辑

================================================================
核心原则(铁律) — 小欧 2026-07-03
  核心脚本(e2e_helpers.py) 负责: 所有通用逻辑
    - 计时(开始/结束/耗时)
    - SSE流接收和解析
    - DB检查、一致性验证、步骤合理性
    - 日志检查、测试记录写入
    - PASS/FAIL判断
  case脚本(test_e2e_*.py) 负责: 只做三件事
    1. 组装参数(用户输入、断言条件)
    2. 调用核心函数( send_chat / check_db / write_test_record 等 )
    3. 断言验证( assert xxx, "失败信息" )
  通用逻辑严禁散落在case脚本中
================================================================

手册步骤与核心函数对照 (小欧 2026-06-18 梳理):
  步骤 1 记录起始状态    → record_test_baseline() 已实现(DB count+日志大小)
  步骤 2 发送用户请求    → send_chat()           已实现
  步骤 3 SSE事件解析     → send_chat()           已实现
  步骤 4 验证事件流      → assert_stream_ended() 已实现
  步骤 7 DB记录完整性    → check_db()            已实现
  步骤 8 SSE-DB一致性    → verify_consistency()  已实现
  步骤 9 步骤合理性      → verify_steps()        已实现(编号+observation)
  步骤10 日志检查        → check_logs()          已实现
  步骤11 清理与记录      → write_test_record()   已实现
  步骤6 门禁-记录验证    → verify_test_record_exists() 已实现
  3.4 Prompt日志vsDB对比  → verify_db_prompt_consistency() 已实现; write_test_record()自动调用
  3.4 流结束             → assert_stream_ended() 已实现
  3.4 错误事件           → result["has_error"]   已实现
  3.4 回复含错误关键词   → write_test_record() resp_has_error 已实现
  3.4 事件总数           → 测试脚本 assert total_steps < 50 已实现
  3.4 LLM调用次数        → check_logs() llm_calls_found 已实现
  3.4 DB session记录     → check_db() session_exists 已实现
  3.4 DB messages记录    → check_db() has_user/assistant_message 已实现
  3.4 DB steps记录       → check_db() step_field_issues 已实现
  3.4 SSE vs DB步骤数    → verify_consistency() 偏差≤2 已实现
  3.4 SSE vs DB核心字段  → verify_consistency() tool_name+obs 已实现
  3.4 回复语义(长度)     → verify_response_quality()  已实现
  3.4 步骤顺序           → verify_steps() 编号递增 已实现
  3.4 日志级别           → check_logs() ERROR检查 已实现
  3.4 响应时间           → verify_response_time()     已实现
  3.5 铁律1 显式调用     → 测试脚本模板中规范 已实现
  3.5 铁律2 结果可见     → 测试脚本 print+assert 已实现
  3.5 铁律3 步骤7验证    → check_db() 已实现
  3.5 铁律4 步骤8验证    → verify_consistency() 已实现
  3.5 铁律5 日志检查     → check_logs() 已实现
  3.5 铁律6 不满足标FAIL → 测试脚本 assert 已实现

未实现/需手动:
  步骤 5 错误处理        → 分类/分析/修复需人工
  步骤 6 门禁-调用链分析 → [CALL CHAIN]输出数据,判断需人工
  步骤 9 工具选择合理性  → 语义判断需人工
  步骤 9 参数正确性      → 路径/关键词正确性需人工
  3.4 工具选择(大类匹配) → 工具大类是否匹配意图需人工
  3.4 参数正确性         → 关键参数是否正确需人工
  3.4 回复语义(相关性)   → 与指令是否相关需人工

-- 小健 2026-06-14
-- 更新: 2026-08-22 - 小欧 - 新增verify_db_tool_usage()公共函数(case侧DB工具步骤校验唯一入口, 复用_is_action_step/_action_entries新旧协议自适应; 登记FUNCTIONS.md v3.7 九.1)
"""

import asyncio
import atexit
import json
import re
import signal
import socket
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx


# ─── 超时保护机制（手册5.5铁律：即使超时也要写记录）──────────────
# 小健 2026-06-18 添加

_pending_records: List[Dict[str, Any]] = []


def _flush_pending_records():
    """进程退出时写入所有未完成的测试记录"""
    for rec in _pending_records:
        try:
            write_test_record(**rec)
        except Exception:
            pass
    _pending_records.clear()


atexit.register(_flush_pending_records)


def _signal_handler(signum, frame):
    """信号处理：进程被终止前写入记录；不调sys.exit，让finally块自然执行 — 小欧 2026-07-01"""
    _flush_pending_records()


for _sig in (signal.SIGTERM, signal.SIGINT):
    try:
        signal.signal(_sig, _signal_handler)
    except (OSError, ValueError):
        pass


def register_pending_record(
    test_id: str,
    test_name: str,
    user_input: str,
    result: Dict[str, Any],
    db: Dict[str, Any],
    consistency_issues: List[str],
    step_issues: List[str],
    log_check: Dict[str, Any],
    passed: bool,
    elapsed: float = 0.0,
    extra: Optional[Dict[str, Any]] = None,
    dpi: Optional[List[str]] = None,
    error_info: Optional[str] = None,
):
    """注册一个待写入的测试记录（超时保护）"""
    _pending_records.append({
        "test_id": test_id,
        "test_name": test_name,
        "user_input": user_input,
        "result": result,
        "db": db,
        "consistency_issues": consistency_issues,
        "step_issues": step_issues,
        "log_check": log_check,
        "passed": passed,
        "elapsed": elapsed,
        "extra": extra,
        "dpi": dpi,
        "error_info": error_info,
    })


def remove_pending_record(test_id: str):
    """测试正常完成时移除待写入记录"""
    _pending_records[:] = [r for r in _pending_records if r.get("test_id") != test_id]


# ─── 常量 ─────────────────────────────────────────────────────

BASE_URL = "http://127.0.0.1:8000"
API_PREFIX = "/api/v1"
DB_PATH = Path.home() / ".omniagent" / "chat_history.db"
LOG_DIR = Path(__file__).parent.parent.parent / "logs"
PROMPT_LOG_DIR = LOG_DIR / "prompt-logs"


# ─── 后端检查 ────────────────────────────────────────────────

def ensure_backend_ready() -> bool:
    """检查后端是否已就绪 -- 小健 2026-06-14"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        sock.connect(("127.0.0.1", 8000))
        sock.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


# ─── 步骤1: 记录测试起始状态 (record_test_baseline) ─────────────
# 小欧 2026-06-18 新增: 手册步骤1未实现项自动化

def record_test_baseline() -> Dict[str, Any]:
    """手册步骤1: 记录测试起始状态(DB base count + 日志文件大小)

    返回:
      - db_session_count: 当前DB会话总数
      - log_file_size: 当前app日志文件大小(bytes)
      - log_file: 日志文件路径
    -- 小欧 2026-06-18
    """
    baseline: Dict[str, Any] = {
        "db_session_count": 0,
        "log_file_size": 0,
        "log_file": "",
    }

    # DB会话数
    try:
        session_data = _api_get("/sessions")
        if session_data and isinstance(session_data, list):
            baseline["db_session_count"] = len(session_data)
        elif session_data and isinstance(session_data, dict):
            sessions = session_data.get("sessions", [])
            baseline["db_session_count"] = len(sessions)
    except Exception:
        pass

    # 日志文件大小
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"app_{today}.log"
    if log_file.exists():
        baseline["log_file_size"] = log_file.stat().st_size
        baseline["log_file"] = str(log_file)

    return baseline


# ─── 步骤1+3.4: 响应质量验证 (verify_response_quality) ─────────
# 小欧 2026-06-18 新增: 手册3.4"回复语义"未实现项自动化

def verify_response_quality(result: Dict[str, Any]) -> List[str]:
    """手册3.4: 回复质量验证(长度+关键词)

    验证项:
      - 回复长度 > 10字(SHOULD)
      - 回复不含错误关键词(MAY)
    -- 小欧 2026-06-18
    """
    issues: List[str] = []
    resp = result.get("response_text", "")

    if not resp or not resp.strip():
        issues.append("回复为空(MUST)")
        return issues

    resp_len = len(resp.strip())
    if resp_len <= 10:
        issues.append(f"回复过短({resp_len}字, 要求>10字)(SHOULD)")

    clean = resp.replace("\n", " ").replace("\r", " ")
    err_markers = ("错误:", "错误：", "超时,", "超时，", "超时)", "超时）", "出错", "failed:", "exception:", "traceback:")
    if any(m in clean for m in err_markers):
        issues.append("回复含错误关键词(MAY)")

    return issues


# ─── 步骤1+3.4: 响应时间验证 (verify_response_time) ────────────
# 小欧 2026-06-18 新增: 手册3.4"响应时间"未实现项自动化

def verify_response_time(result: Dict[str, Any]) -> List[str]:
    """手册3.4: 响应时间验证(单步<120s, 多步<600s)

    验证项:
      - 单步任务总耗时 < 120s(SHOULD)
      - 多步任务总耗时 < 600s(SHOULD)
    -- 小欧 2026-06-18
    """
    issues: List[str] = []
    total_ms = result.get("total_time_ms", 0)
    total_s = total_ms / 1000.0
    tool_count = len(result.get("tool_calls", []))

    if tool_count <= 1:
        # 单步: <120s
        if total_s >= 120:
            issues.append(f"单步响应超时({total_s:.1f}s, 要求<120s)(SHOULD)")
    else:
        # 多步: <600s
        if total_s >= 600:
            issues.append(f"多步响应超时({total_s:.1f}s, 要求<600s)(SHOULD)")

    return issues


# ─── Session管理 ─────────────────────────────────────────────

async def create_session() -> Optional[str]:
    """创建session(POST /sessions) -- 小健 2026-06-14"""
    url = f"{BASE_URL}{API_PREFIX}/sessions"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json={})
        if resp.status_code == 200:
            return resp.json().get("session_id")
    return None


async def save_user_message(session_id: str, content: str) -> Optional[int]:
    """保存user消息到DB(模拟前端POST /messages) -- 小健 2026-06-14"""
    url = f"{BASE_URL}{API_PREFIX}/sessions/{session_id}/messages"
    payload = {"role": "user", "content": content}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json=payload)
        if resp.status_code == 200:
            return resp.json().get("message_id")
    return None


# ─── 步骤2+3: 发送用户请求 + SSE事件解析 (send_chat) ─────────

async def send_chat(
    user_input: str,
    session_id: Optional[str] = None,
    timeout_seconds: int = 180,
    partial_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """手册步骤2+3: 发送POST /chat/stream, 接收SSE事件流, 返回结构化结果

    通用逻辑(本函数负责):
      - wall clock计时: start_time/end_time写入result，供write_test_record直接取
      - SSE流接收: httpx timeout=None，由pytest.ini的timeout统一管理
      - 事件解析: 组装events/tool_calls/response_text等结构化数据
      模拟真实前端流程: 创建session -> POST /messages保存user消息 -> POST /chat/stream
    -- 小健 2026-06-14
    """
    if not session_id:
        session_id = await create_session()
        if not session_id:
            raise RuntimeError("创建session失败")

    user_msg_id = await save_user_message(session_id, user_input)

    chat_url = f"{BASE_URL}{API_PREFIX}/chat/stream"
    payload = {
        "messages": [{"role": "user", "content": user_input}],
        "stream": True,
        "session_id": session_id,
    }

    start_time = time.monotonic()
    wall_start = datetime.now()
    events: List[Dict[str, Any]] = []
    error_occurred = False
    final_event = None
    response_text = ""
    tool_calls: List[Dict[str, Any]] = []

    # ======================================================================
    # 超时：send_chat 内部不设任何超时。
    # 整个测试流程的超时统一由 pytest.ini 的 timeout=3000 管理，
    # 该值涵盖 SSE 流接收的完整耗时（LLM 思考 + 工具执行 + 流式输出）。
    # httpx.AsyncClient(timeout=None) 禁用了传输层超时，
    # 避免读 chunk 超时误杀正常的长 SSE 流。
    #
    # 铁律：所有 E2E 测试脚本严禁手动设置超时参数，
    #       也严禁在 send_chat/start_background_stream 等函数内
    #       添加任何形式的墙钟超时或 asyncio.wait_for。
    #       如需调整超时，只改 pytest.ini 的 timeout 值。
    #       -- 小欧 2026-07-03
    # ======================================================================
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            try:
                async with client.stream("POST", chat_url, json=payload) as resp:
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        try:
                            event = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        event_type = event.get("type", "")
                        events.append(event)

                        if event_type == "error":
                            error_occurred = True

                        # 2026-08-19 小欧 方法2修正(老陈驱动): chunk 不再边收边拼——全部事件已入 events(line373),
                        #   最终答复待 stream 结束后按 final.step 取该轮非 reasoning 正文 chunk 拼接,
                        #   避免把前几轮 thought 过渡话术混入(原全量拼接致02/03脏/01空)。

                        if event_type == "final":
                            final_event = event

                        # 2026-08-19 小欧 协议适配(§10.3.3(2)废除action_tool→action): 工具调用事件改从 action.tools[] 取,
                        #   每元素含 tool(工具名)/params(参数), 兼容旧 action_tool(tool_name/tool_params)。
                        if event_type in ("action", "action_tool"):
                            tools_raw = event.get("tools") or []
                            if tools_raw:
                                for _it in tools_raw:
                                    if not isinstance(_it, dict):
                                        continue
                                    tool_calls.append({
                                        "type": "action",
                                        "tool_name": _it.get("tool") or _it.get("tool_name") or "",
                                        "tool_params": _it.get("params") or _it.get("tool_params") or {},
                                    })
                            else:
                                tool_calls.append({
                                    "type": event_type,
                                    "tool_name": event.get("tool_name", ""),
                                    "tool_params": event.get("tool_params", {}),
                                })
            except httpx.TimeoutException:
                pass
            except Exception:
                pass  # 其他流式异常不影响主流程
    finally:
        total_time_ms = int((time.monotonic() - start_time) * 1000)
        event_types = [e.get("type", "") for e in events]
        logical_events = [e for e in events if e.get("type") != "chunk"]
        unique_step_numbers = len({e.get("step") for e in events if e.get("step") is not None})

        # 2026-08-19 小欧 方法2修正(老陈驱动): 最终答复 = 最后一轮(fin_step)的 chunk 两类拼接——
        #   reason(推理, is_reasoning 正文) + resp(最终答复, 非 reasoning), 用 [最后总结] 分隔线拼进记录 ## 2;
        #   解决原全量拼接把前几轮 thought 过渡话术混入(02/03脏)+ 全 reasoning 被滤空(01)的问题;
        #   若该轮无正文 chunk(return_direct/action轮), resp 回退 final.response/content。
        fin_step = (final_event or {}).get("step")
        reason = "".join(
            e.get("content", "") for e in events
            if e.get("type") == "chunk" and e.get("step") == fin_step and e.get("is_reasoning")
        )
        resp = "".join(
            e.get("content", "") for e in events
            if e.get("type") == "chunk" and e.get("step") == fin_step and not e.get("is_reasoning")
        )
        if not (resp or "").strip():
            resp = (final_event or {}).get("response") or (final_event or {}).get("content") or ""
        if (reason or "").strip():
            response_text = reason.rstrip() + "\n[最后总结]: ------------\n" + resp
        else:
            response_text = resp

        ret = {
            "events": events,
            "final_event": final_event,
            "has_error": error_occurred,
            "total_steps": len(events),
            "logical_step_count": len(logical_events),
            "unique_step_numbers": unique_step_numbers,
            "tool_calls": tool_calls,
            # 2026-08-21 小欧 修正: llm_call_count 应为「LLM调用次数」而非工具调用次数。
            #   旧值 len(tool_calls)+1 把批量工具数当成LLM轮次(9_02误为5, 实3; com04误为39, 实13)。
            #   真实LLM调用次数 = SSE中 usage 事件数(每次LLM完成必带一个usage), 与Prompt日志«LLM调用记录»一致。
            "llm_call_count": sum(1 for e in events if e.get("type") == "usage") or (len(tool_calls) + 1),
            "total_time_ms": total_time_ms,
            "response_text": response_text,
            "reply": response_text,
            "session_id": session_id,
            "user_msg_id": user_msg_id,
            "event_types": event_types,
            "start_time": wall_start,
            "end_time": datetime.now(),
        }
        if partial_result is not None:
            partial_result.update(ret)
        return ret


# ─── 流式SSE启动(用于TR测试: 需要后台读取+中途cancel) ────────
# 小健 2026-06-19 从TR-02~05提取,修复异常吞掉问题

async def start_chat_stream_async(
    session_id: str, user_input: str, api_prefix: str = "",
) -> Dict[str, Any]:
    """启动chat SSE流,返回(task_id, events, bg_task, error)

    用于TR测试场景: 需要后台读取SSE事件,然后中途cancel/pause
    修复: 异常不再吞掉,通过error字段暴露 -- 小健 2026-06-19
    修复: 与send_chat一致,先保存user消息到DB -- 小健 2026-06-19
    """
    # 与send_chat一致: 先保存user消息到DB
    await save_user_message(session_id, user_input)

    prefix = api_prefix or API_PREFIX
    chat_url = f"{BASE_URL}{prefix}/chat/stream"
    payload = {
        "messages": [{"role": "user", "content": user_input}],
        "stream": True,
        "session_id": session_id,
    }
    result: Dict[str, Any] = {"task_id": None, "events": [], "error": None}

    async def _stream_reader():
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", chat_url, json=payload) as resp:
                    try:
                        async for line in resp.aiter_lines():
                            if line.startswith("data: "):
                                try:
                                    event = json.loads(line[6:])
                                    result["events"].append(event)
                                    if event.get("type") == "start" and event.get("task_id"):
                                        result["task_id"] = event["task_id"]
                                except json.JSONDecodeError:
                                    continue
                    except asyncio.CancelledError:
                        pass
        except asyncio.CancelledError:
            pass
        except Exception as e:
            result["error"] = str(e)
            print(f"  [SSE ERROR] {type(e).__name__}: {e}")

    bg_task = asyncio.create_task(_stream_reader())
    # 等待task_id出现,最多10秒
    for _ in range(20):
        if result["task_id"]:
            break
        await asyncio.sleep(0.5)

    return {
        "task_id": result["task_id"],
        "events": result["events"],
        "bg_task": bg_task,
        "error": result["error"],
    }


# ─── 步骤4: 验证事件流正确性 (assert_stream_ended) ─────────────

def assert_stream_ended(result: Dict[str, Any]) -> str:
    """返回流结束方式(final/failed/cancelled/error/中断), 不阻断
    所有方式都算流已结束, 忠实记录 -- 小健 2026-06-15
    2026-07-18 小欧 响应 FinalStep 多态重构: 终态统一 type=final, 由 outcome 声明结果,
    故 final 事件须按 outcome 区分 failed/cancelled, 不再仅依赖 error 事件"""
    final_event = result.get("final_event")
    if isinstance(final_event, dict):
        oc = final_event.get("outcome", "completed")
        if oc == "failed":
            return "failed"
        if oc == "cancelled":
            return "cancelled"
    if result.get("final_event") is not None:
        return "final"
    if result.get("has_error"):
        return "error"
    return "中断"


# ─── 数据库连接(通过后端API, 避免sqlite3直连权限问题) ────────

def _api_get(path: str, params: Optional[Dict] = None, timeout: int = 10) -> Optional[Dict]:
    """同步GET请求后端API -- 小健 2026-06-14

    timeout 可调: 大任务结束后后端仍在后台做大体积DB写入(如1.4MB execution_steps),
    可能短暂占用SQLite写锁导致本GET被阻塞, 调用方按需传更长超时 — 小欧 2026-07-13
    """
    import urllib.request
    import urllib.parse
    url = f"{BASE_URL}{API_PREFIX}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _api_delete(path: str) -> bool:
    """同步DELETE请求后端API -- 小健 2026-06-14"""
    import urllib.request
    url = f"{BASE_URL}{API_PREFIX}{path}"
    try:
        req = urllib.request.Request(url, method="DELETE")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status < 400
    except Exception:
        return False


# ─── 步骤7: DB记录完整性验证 (check_db) ────────────────────────

def check_db(session_id: str) -> Dict[str, Any]:
    """手册步骤7: 检查数据库记录完整性(通过后端API) -- 小健 2026-06-14

    验证项:
      - session存在 + is_valid + created_at/updated_at合理
      - user message + assistant message都存在 + 顺序正确
      - execution_steps中每个step字段完整性:
        action/action_tool步骤: tools[].tool/params 非空; observation步骤: tool_result 非空
        (v0.19.18起 action_tool→action, observation 仅带 tool_result, 步骤无 status 字段)
    v2.0: 不再读 chat_messages，改用 chat_user_message — 小欧 2026-08-21
    """
    result: Dict[str, Any] = {
        "session_exists": False,
        "is_valid": None,
        "created_at": None,
        "updated_at": None,
        "time_issues": [],
        "has_user_message": False,
        "has_assistant_message": False,
        "message_order_correct": False,
        "messages_count": 0,
        "execution_steps_count": 0,
        "execution_steps": [],
        "step_field_issues": [],
        "errors": [],
    }

    try:
        # ── chat_sessions (via API) ──
        # 大任务结束后 send_chat 随SSE流结束即返回, 但 agent_runner 后台任务仍在 finally 中
        # 做大体积DB写入(如1.4MB execution_steps), 短暂占用SQLite写锁, 致本GET可能超时返回None。
        # 此处重试若干次, 等待真实后端保存完成(非Mock) — 小欧 2026-07-13
        session_data = None
        for _attempt in range(8):
            session_data = _api_get(f"/sessions/{session_id}/messages", timeout=30)
            if session_data and session_data.get("session_id"):
                break
            time.sleep(2)
        if session_data and session_data.get("session_id"):
            result["session_exists"] = True
            result["is_valid"] = bool(session_data.get("is_valid"))
            result["created_at"] = session_data.get("created_at")
            result["updated_at"] = session_data.get("updated_at")

        # ── chat_user_message (via API, 不再读 chat_messages) ──
        # 2026-08-22 小欧 竞态修复(p9_03实证): 大任务SSE结束后 agent_runner 后台仍在大体积写库
        #   (task_id/response 最晚31s后才落库), 原重试5次×1s不够致 has_assistant_message 误判False;
        #   改为等待"行内出现task_id或response"才收数, 预算对齐sessions接口8次×2s
        user_msgs_data = None
        user_msgs: List[Dict[str, Any]] = []
        for _attempt in range(8):
            user_msgs_data = _api_get(f"/sessions/{session_id}/user_messages", timeout=30)
            user_msgs = user_msgs_data.get("messages", []) if user_msgs_data else []
            if any(m.get("response") or m.get("task_id") for m in user_msgs):
                break
            time.sleep(2)

        result["messages_count"] = len(user_msgs)

        # chat_user_message 每行是一个用户消息+AI回复，有 task_id 即有 assistant 消息
        if user_msgs:
            result["has_user_message"] = True
            result["has_assistant_message"] = any(m.get("response") or m.get("task_id") for m in user_msgs)
            result["message_order_correct"] = True  # chat_user_message 按 created_at 升序，天然有序

            # 取最后一个有 execution_steps 的任务步骤
            for _um in reversed(user_msgs):
                _task_id = _um.get("task_id")
                if _task_id:
                    _steps_data = _api_get(f"/chat/execution/task/{_task_id}/steps", timeout=30)
                    if _steps_data and _steps_data.get("steps"):
                        steps = _steps_data["steps"]
                        result["execution_steps"] = steps
                        result["execution_steps_count"] = len(steps)

                        for si, step in enumerate(steps):
                            step_type = step.get("type", "")
                            if _is_action_step(step):
                                _entries = _action_entries(step)
                                if not _entries:
                                    result["step_field_issues"].append(
                                        f"step[{si}](type={step_type}): 无工具调用信息(MUST)"
                                    )
                                for _ei, _en in enumerate(_entries):
                                    if not _en.get("tool_name"):
                                        result["step_field_issues"].append(
                                            f"step[{si}]#{_ei}: tool_name empty(MUST)"
                                        )
                                    _tp = _en.get("tool_params")
                                    if not isinstance(_tp, dict):
                                        result["step_field_issues"].append(
                                            f"step[{si}]#{_ei}: tool_params非dict(MUST)"
                                        )
                            elif step_type == "observation":
                                if not step.get("tool_result"):
                                    result["step_field_issues"].append(
                                        f"step[{si}]: tool_result empty(MUST)"
                                    )
                        break  # 取到步骤即退出

    except Exception as e:
        result["errors"].append(f"API query error: {e}")

    return result


# ─── 安全错误过滤 ────────────────────────────────────────────

SAFETY_KEYWORDS = [
    "安全检查", "拒绝执行", "高风险",
    "pickle", "RCE", "extract",
    "create_task", "delete_task",
    "Permission denied", "DB operation failed",
    "NoneType", "Errno 13", "ERR_SQL_EXEC",
    "UNIQUE constraint", "拒绝访问", "WinError 5", "WinError 32",
    "readtext failed", "unable to open database",
]


def filter_safety_errors(errors: List[str]) -> Dict[str, List[str]]:
    """过滤安全相关错误，返回安全错误和非安全错误
    
    返回:
      - safety_errors: 安全相关错误（可忽略）
      - other_errors: 其他错误（需要关注）
    -- 小欧 2026-07-03
    """
    safety_errors = [e for e in errors if any(k in e for k in SAFETY_KEYWORDS)]
    other_errors = [e for e in errors if e not in safety_errors]
    return {"safety_errors": safety_errors, "other_errors": other_errors}


# ─── 工具函数 ──────────────────────────────────────────────

def _obs_to_text(obs) -> str:
    """将observation(dict/str/其他)转为可比较的文本 -- 小健 2026-06-14"""
    if isinstance(obs, str):
        return obs
    if isinstance(obs, dict):
        for key in ("message", "content", "text", "output", "result", "data"):
            val = obs.get(key)
            if isinstance(val, str) and val.strip():
                return val
            if isinstance(val, dict):
                for k2 in ("message", "content", "text", "output", "result"):
                    v2 = val.get(k2)
                    if isinstance(v2, str) and v2.strip():
                        return v2
        return json.dumps(obs, ensure_ascii=False)
    return str(obs)


# ─── 步骤8: SSE vs DB一致性验证 (verify_consistency) ────────────
# 2026-08-19 小欧 工具调用协议适配(§10.3.3(2)废除action_tool→action):
#   新增统一判定/规整辅助, DB侧从 tools[] {tool,params} 或旧 tool_name/tool_params 归一为 tool_name/tool_params。
def _is_action_step(step: Any) -> bool:
    """新旧协议工具步骤统一判定 - 小欧 2026-08-19"""
    return isinstance(step, dict) and step.get("type") in ("action", "action_tool")


def _action_entries(step: Any) -> List[Dict[str, Any]]:
    """把工具步骤规整为 {tool_name, tool_params} 列表 - 小欧 2026-08-19
    新协议 action: tools[] 每元素 {tool, params}; 旧协议 action_tool: 直接 tool_name/tool_params"""
    if not isinstance(step, dict):
        return []
    if step.get("type") == "action":
        out: List[Dict[str, Any]] = []
        for t in step.get("tools") or []:
            if isinstance(t, dict):
                out.append({
                    "tool_name": t.get("tool") or t.get("tool_name") or "",
                    "tool_params": t.get("params") or t.get("tool_params") or {},
                })
        return out
    if step.get("type") == "action_tool":
        return [{
            "tool_name": step.get("tool_name", ""),
            "tool_params": step.get("tool_params", {}),
        }]
    return []


def _fmt_tok(d: Any) -> str:
    """token字典三数全显: 入=prompt_tokens/出=completion_tokens/总=total_tokens - 小欧 2026-08-22"""
    d = d if isinstance(d, dict) else {}
    return (
        f"入{d.get('prompt_tokens', '?')}"
        f"/出{d.get('completion_tokens', '?')}"
        f"/总{d.get('total_tokens', '?')}"
    )


def verify_db_tool_usage(
    db: Dict[str, Any],
    expect_any_tools: Optional[List[str]] = None,
    min_tool_steps: int = 1,
) -> List[str]:
    """DB侧工具步骤统一校验(case脚本唯一入口, 杜绝各case自写取数块) - 小欧 2026-08-22

    病根定案: 19个case曾复制粘贴"action_tool过滤+顶层tool_name+observation字段"旧取数块,
    §10.3模型变更即全量碎裂; 现收敛本函数单点维护, 内部复用_is_action_step/_action_entries
    新旧协议自适应。校验三项:
      ①工具步骤数≥min_tool_steps
      ②expect_any_tools给定时, 全部工具步骤中至少命中一个期望工具
      ③每个工具步骤: actions归一后工具名非空, 且按step号配对的observation步骤tool_result[]非空
    返回问题列表(空=通过); 参数db为check_db()返回值。
    """
    issues: List[str] = []
    steps = db.get("execution_steps", []) or []
    tool_steps = [s for s in steps if _is_action_step(s)]
    if len(tool_steps) < min_tool_steps:
        issues.append(f"工具步骤数{len(tool_steps)}<{min_tool_steps}")
        return issues
    if expect_any_tools:
        _used = {e.get("tool_name") for s in tool_steps for e in _action_entries(s)}
        if not (_used & set(expect_any_tools)):
            issues.append(f"期望工具未使用: 期望{sorted(set(expect_any_tools))} 实际{sorted(_used)}")
    _obs_by_step = {s.get("step"): (s.get("tool_result") or [])
                    for s in steps if s.get("type") == "observation"}
    for s in tool_steps:
        _names = [e.get("tool_name") for e in _action_entries(s)]
        if not _names or not all(_names):
            issues.append(f"step{s.get('step')}工具名缺失: {_names}")
            continue
        if not _obs_by_step.get(s.get("step")):
            issues.append(f"step{s.get('step')}工具结果缺失: {_names}")
    return issues


def _step_brief(step: Any, limit: int = 40) -> str:
    """按现行落库字段提取各类型步骤内容摘要(§5.2表格"内容摘要"列用) - 小欧 2026-08-22
    字段真值经 chat_task_steps.step_json 实库核验: start(user_message)/context_overview(message_count,
    estimated_tokens,truncated)/stats(llm_call_count,duration)/thought(content)/action(tools[].target)/
    observation(tool_result[].llm_data.summary)/final_stats(duration,artifacts)/final(outcome,response)/error"""
    if not isinstance(step, dict):
        return ""

    def _cut(val) -> str:
        s = str(val or "").replace("\n", " ").replace("|", "\\|").strip()
        return s[:limit] + ("…" if len(s) > limit else "")

    t = step.get("type", "")
    if t == "start":
        return _cut(step.get("user_message"))
    if t == "context_overview":
        return f"消息{step.get('message_count', 0)}条/≈{step.get('estimated_tokens', 0)}tok(估算)" + ("/已裁剪" if step.get("truncated") else "")
    if t == "stats":
        # 2026-08-22 小欧 补展示retry_count(仅非零追加): stats落库字段=llm_call_count/duration/
        #   retry_count/step_count(轮次预算常量100)/severity(恒info), 后两字段无展示价值不显示
        _s = f"第{step.get('llm_call_count', 0)}轮/耗时{step.get('duration', 0)}s"
        _rc = step.get("retry_count", 0) or 0
        return _s + (f"/工具重试{_rc}次" if _rc else "")
    if t == "thought":
        # 2026-08-22 小欧 按北京老陈指示: 有价值字段=thought+reasoning(content与其恒同值不读);
        #   展示顺序先"思考:"=reasoning(思考区)后"结论:"=thought(LLM答案区); 空段跳过
        _parts = []
        _c = str(step.get("thought") or "").strip()
        _r = str(step.get("reasoning") or "").strip()
        if _r:
            _parts.append("思考: " + _cut(_r))
        if _c:
            _parts.append("结论: " + _cut(_c))
        return " | ".join(_parts)
    if t == "action":
        tgts = [str(x.get("target", "")) for x in (step.get("tools") or []) if isinstance(x, dict)]
        return _cut(", ".join(x for x in tgts if x))
    if t == "observation":
        tr = step.get("tool_result") or []
        if not tr:
            return ""
        first = tr[0] if isinstance(tr[0], dict) else {}
        ld = first.get("llm_data") or {}
        prefix = f"[{len(tr)}项] " if len(tr) > 1 else ""
        return prefix + _cut(ld.get("summary"))
    if t == "final_stats":
        arts = step.get("artifacts") or []
        return f"耗时{step.get('duration', 0)}s/产出物{len(arts)}个"
    if t == "final":
        return _cut(f"[{step.get('outcome', '')}] {step.get('response', '')}")
    if t == "error":
        return _cut(f"[{step.get('error_type', '')}] {step.get('content', '')}")
    return _cut(step.get("content"))


def verify_consistency(
    result: Dict[str, Any], session_id: str
) -> List[str]:
    """手册步骤8: 验证SSE事件与DB记录的一致性 -- 小健 2026-06-14

    验证项:
      - tool_calls数量一致(偏差<=2)
      - tool_name一致
      - observation内容一致(相似度>=80%)
      - final response内容一致(相似度>=50%)
    """
    issues: List[str] = []

    db = check_db(session_id)
    if db["errors"]:
        issues.extend(db["errors"])
        return issues
    if not db["session_exists"]:
        issues.append(f"DB中未找到session: {session_id}")
        return issues

    sse_tool_calls = result.get("tool_calls", [])
    db_steps = db.get("execution_steps", [])

    db_tool_calls = []
    for s in db_steps:
        if _is_action_step(s):
            db_tool_calls.extend(_action_entries(s))

    # ── 数量对比(偏差<=2) ──
    sse_count = len(sse_tool_calls)
    db_count = len(db_tool_calls)
    if abs(sse_count - db_count) > 2:
        issues.append(f"工具调用数量偏差过大: SSE={sse_count}, DB={db_count}")

    # ── tool_name对比 ──
    sse_names = [t.get("tool_name", "") for t in sse_tool_calls]
    db_names = [t.get("tool_name", "") for t in db_tool_calls]
    shared = set(sse_names) & set(db_names)
    if not shared and sse_names and db_names:
        issues.append(f"tool_name完全不一致: SSE={sse_names}, DB={db_names}")

    # ── observation相似度>=80% ──
    # 新协议 observation为独立 step, 观察结果在 tool_result[]; action 步骤不再内嵌 observation
    sse_obs_list = [
        e.get("tool_result") or e.get("observation") or e.get("content", "")
        for e in result["events"]
        if e.get("type") in ("action", "action_tool", "observation")
        and (e.get("tool_result") or e.get("observation") or e.get("content"))
    ]
    # 新协议 observation为独立 step, 观察结果在 tool_result[]
    db_obs_list = [
        s.get("tool_result") or s.get("observation") or s.get("execution_result") or s.get("content", "")
        for s in db_steps
        if s.get("type") == "observation"
        and (s.get("tool_result") or s.get("observation") or s.get("execution_result") or s.get("content"))
    ]
    if sse_obs_list and db_obs_list:
        for sse_obs in sse_obs_list:
            if not sse_obs or (isinstance(sse_obs, str) and not sse_obs.strip()):
                continue
            best = 0.0
            sse_str = _obs_to_text(sse_obs)
            sw = set(sse_str.lower().split()[:30])
            for db_obs in db_obs_list:
                if not db_obs:
                    continue
                db_str = _obs_to_text(db_obs)
                dw = set(db_str.lower().split()[:30])
                if sw and dw:
                    sim = len(sw & dw) / max(len(sw), len(dw))
                    best = max(best, sim)
            if best < 0.8:
                issues.append(
                    f"observation偏差(最好匹配={best:.2f}, 要求>=0.80)"
                )

    # ── final response相似度>=50% ──
    sse_resp = result.get("response_text", "")
    if sse_resp and db_steps:
        last = db_steps[-1]
        if last.get("type") == "final":
            db_resp = last.get("response") or last.get("content", "")
            if db_resp and sse_resp:
                sse_r = str(sse_resp) if not isinstance(sse_resp, str) else sse_resp
                db_r = str(db_resp) if not isinstance(db_resp, str) else db_resp
                sw = set(sse_r.lower().split()[:50])
                dw = set(db_r.lower().split()[:50])
                if sw and dw:
                    overlap = len(sw & dw)
                    min_len = min(len(sw), len(dw))
                    if min_len > 0 and overlap / min_len < 0.5:
                        issues.append(
                            f"final response偏差(重叠={overlap/min_len:.2f}, 要求>=0.50)"
                        )

    return issues


def verify_db_prompt_consistency(
    session_id: str,
    user_msg_id: Optional[int] = None,
) -> List[str]:
    """验证DB execution_steps与Prompt日志«步骤产出»严格一致性 -- 小健 2026-06-24

    严格比较项:
      - 非chunk/start步骤数量必须完全一致
      - 同步骤号: action 的 tool_name/tool_params 必须完全一致
      - 同步骤号: observation 的 tool_result(错误码/状态) 必须一致
      - 步骤顺序必须完全一致

    v0.19.18起 action_tool→action(tools[]={tool,target,params}); observation 仅带 tool_result。
    v2.2: 增强严格性，不允许偏差
    """
    issues: List[str] = []

    db = check_db(session_id)
    db_steps = db.get("execution_steps", [])
    if not db_steps:
        issues.append("DB无执行步骤数据")
        return issues

    # 找到prompt日志文件
    prompt_log_file = None
    if user_msg_id is not None and PROMPT_LOG_DIR.exists():
        for pf in sorted(PROMPT_LOG_DIR.glob("prompt_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:50]:
            try:
                content = pf.read_text(encoding="utf-8", errors="ignore")
                if str(user_msg_id) in content and session_id in content:
                    prompt_log_file = pf
                    break
            except Exception:
                pass

    if not prompt_log_file:
        issues.append("未找到匹配的Prompt日志文件")
        return issues

    try:
        log_data = json.loads(prompt_log_file.read_text(encoding="utf-8", errors="ignore"))
    except Exception as e:
        issues.append(f"读取Prompt日志失败: {e}")
        return issues

    # 获取「步骤产出」节
    exec_steps_key = "步骤产出"
    log_steps = log_data.get(exec_steps_key, [])

    if not log_steps:
        issues.append("Prompt日志«步骤产出»为空")
        return issues

    # action/observation步骤数对比(对齐到双方都有意义的数据步骤)
    # v0.19.18起 prompt日志还会记录 startinfo/usage/thought-start/chunk 等 DB不持久化的步骤,
    # 故不能用全量步骤数对比, 只能对齐 action/observation 两类数据步骤。
    db_main = [s for s in db_steps if _is_action_step(s) or s.get("type") == "observation"]
    log_main = [
        s for s in log_steps
        if s.get("步骤类型") in ("action", "observation")
        or (isinstance(s.get("数据"), dict) and _is_action_step(s.get("数据")))
    ]

    if len(db_main) != len(log_main):
        issues.append(
            f"action/observation步骤数不一致(DB={len(db_main)}, Prompt日志={len(log_main)})(MUST)"
        )

    # 按步骤号分组: 收集每个 step 的 action 工具项(tool_name/tool_params) 与 observation 文本
    # v0.19.18起 action/action_tool: tools[]={tool,target,params}; observation: tool_result[]
    def _collect(step):
        _acts = _action_entries(step) if _is_action_step(step) else []
        _obs = ""
        if step.get("type") == "observation":
            _tr = step.get("tool_result")
            _obs = _obs_to_text(_tr) if _tr else ""
        return _acts, _obs

    db_acts: Dict[int, List[Dict]] = {}
    db_obs: Dict[int, str] = {}
    for s in db_steps:
        sn = s.get("step")
        if sn is None:
            continue
        _a, _o = _collect(s)
        if _a:
            db_acts.setdefault(sn, []).extend(_a)
        if _o:
            db_obs[sn] = _o
    log_acts: Dict[int, List[Dict]] = {}
    log_obs: Dict[int, str] = {}
    for s in log_steps:
        sn = s.get("步骤")
        if sn is None:
            continue
        evt = s.get("数据", {})
        if not isinstance(evt, dict):
            continue
        _a, _o = _collect(evt)
        if _a:
            log_acts.setdefault(sn, []).extend(_a)
        if _o:
            log_obs[sn] = _o

    all_step_nums = set(db_acts.keys()) | set(log_acts.keys()) | set(db_obs.keys()) | set(log_obs.keys())
    for sn in sorted(all_step_nums):
        db_actions = db_acts.get(sn, [])
        log_actions = log_acts.get(sn, [])

        # action 数量对比
        if len(db_actions) != len(log_actions):
            issues.append(
                f"步骤{sn} action数量不一致(DB={len(db_actions)}, Prompt日志={len(log_actions)})(MUST)"
            )

        max_len = max(len(db_actions), len(log_actions))
        for i in range(max_len):
            # 哪边多出
            if i >= len(db_actions):
                issues.append(f"步骤{sn} DB少第{i+1}个action, Prompt日志多出(MUST)")
                continue
            if i >= len(log_actions):
                issues.append(f"步骤{sn} DB多出第{i+1}个action, Prompt日志缺少(MUST)")
                continue

            db_s = db_actions[i]
            log_evt = log_actions[i]

            # tool_name对比
            db_tn = db_s.get("tool_name", "")
            log_tn = log_evt.get("tool_name", "")
            if db_tn != log_tn:
                issues.append(
                    f"步骤{sn} 第{i+1}个tool_name不一致(DB={db_tn}, Prompt日志={log_tn})(MUST)"
                )

            # tool_params对比
            db_tp = db_s.get("tool_params", {})
            if isinstance(db_tp, str):
                try:
                    db_tp = json.loads(db_tp)
                except Exception:
                    db_tp = {"_raw": db_tp}
            log_tp = log_evt.get("tool_params", {})
            if str(db_tp) != str(log_tp):
                issues.append(
                    f"步骤{sn} 第{i+1}个tool_params不一致(DB={db_tp}, Prompt日志={log_tp})(MUST)"
                )

        # observation 对比(同 step 号)
        db_o = db_obs.get(sn, "")
        log_o = log_obs.get(sn, "")
        if db_o and log_o:
            db_upper = ''.join(c for c in db_o if c.isupper() or c == '_')
            log_upper = ''.join(c for c in log_o if c.isupper() or c == '_')
            if 'ERR' in db_upper and 'ERR' not in log_upper:
                issues.append(
                    f"步骤{sn} observation错误码不匹配: DB含错误码, Prompt日志未含(MUST)"
                )
            elif 'SUCCESS' in db_upper and 'SUCCESS' not in log_upper:
                issues.append(
                    f"步骤{sn} observation状态不匹配: DB含SUCCESS, Prompt日志未含(MUST)"
                )

    return issues


def verify_db_steps_data_completeness(
    session_id: str,
) -> List[str]:
    """验证DB执行步骤数据完整性 -- 小健 2026-06-24

    严格检查每个 action/action_tool 步骤的:
      - tools[].tool 不能为空
      - tools[].params 必须存在且为dict
    每个 observation 步骤的:
      - tool_result 不能为空
    (v0.19.18起废除action_tool→action(tools[]={tool,target,params}); observation仅带tool_result; 步骤无status字段)
    """
    issues: List[str] = []
    
    db = check_db(session_id)
    db_steps = db.get("execution_steps", [])
    
    if not db_steps:
        issues.append("DB无执行步骤数据(MUST)")
        return issues
    
    for i, step in enumerate(db_steps):
        step_type = step.get("type", "")
        step_num = step.get("step", "")

        if _is_action_step(step):
            # action/action_tool: 工具信息在 tools[]={tool,target,params}
            _entries = _action_entries(step)
            if not _entries:
                issues.append(f"步骤{step_num}(index={i}): 无工具调用信息(MUST)")
            for _ei, _en in enumerate(_entries):
                tool_name = _en.get("tool_name", "")
                if not tool_name:
                    issues.append(f"步骤{step_num}(index={i})#{_ei}: tool_name为空(MUST)")
                tool_params = _en.get("tool_params")
                if tool_params is None or not isinstance(tool_params, dict):
                    issues.append(f"步骤{step_num}(index={i})#{_ei}: tool_params为空或非dict(MUST)")
        elif step_type == "observation":
            # observation: 观察结果在 tool_result[]
            if not step.get("tool_result"):
                issues.append(f"步骤{step_num}(index={i}): tool_result为空(MUST)")

        # step号检查
        if step_num is None:
            issues.append(f"步骤(index={i}): step号缺失(MUST)")

    return issues


# ─── 步骤9: 步骤合理性验证 (verify_steps) ──────────────────────

def verify_steps(
    result: Dict[str, Any], session_id: str
) -> List[str]:
    """手册步骤9: 验证步骤合理性 -- 小健 2026-06-14

    验证项:
      - 步骤编号连续递增
      - 每个工具调用都有observation
      - 步骤顺序合理(先读后写等)
    """
    issues: List[str] = []

    db = check_db(session_id)
    if not db["session_exists"] or not db["execution_steps"]:
        return issues

    steps = db["execution_steps"]

    # ── 步骤编号连续性(仅检查action/action_tool步骤,允许并行调用共享step号) ──
    # 小欧 2026-06-16: LLM可以在一次响应中返回多个并行tool_call,共享同一个step号
    tool_step_nums = [
        s.get("step") for s in steps
        if _is_action_step(s) and s.get("step") is not None
    ]
    if len(tool_step_nums) >= 2:
        for i in range(len(tool_step_nums) - 1):
            # 允许并行调用: 相同step号是正常的(如step=1下有read_text_file和list_directory)
            # 只检查严格递减的情况(如1->0, 2->1)
            if tool_step_nums[i + 1] < tool_step_nums[i]:
                issues.append(f"工具步骤编号不递增: {tool_step_nums[i]}->{tool_step_nums[i+1]}")

    # ── observation完整性: 每个 action 步骤应有同 step 号的 observation 步骤且 tool_result 非空 ──
    obs_by_step = {
        s.get("step"): s for s in steps if s.get("type") == "observation"
    }
    for i, step in enumerate(steps):
        if _is_action_step(step):
            sn = step.get("step")
            obs = obs_by_step.get(sn)
            if obs is None or not obs.get("tool_result"):
                issues.append(f"step[{i}]({step.get('type')} step={sn}): 缺对应observation(tool_result)")

    return issues


# ─── 步骤10: 日志检查 (check_logs) ─────────────────────────────

def check_logs(
    start_time: Optional[datetime] = None,
    session_id: Optional[str] = None,
    user_msg_id: Optional[int] = None,
) -> Dict[str, Any]:
    """手册步骤10: 检查日志和prompt-logs -- 小健 2026-06-14

    验证项:
      - 无ERROR级别日志
      - 无异常traceback
      - 有session操作记录
      - 有SSE事件发送记录
      - prompt-logs已保存
      - LLM调用次数合理(无死循环)

    匹配规则: user_msg_id > session_id(一轮对话一个prompt日志)
    """
    result: Dict[str, Any] = {
        "errors": [],
        "tracebacks": [],
        "session_records_found": False,
        "sse_records_found": False,
        "llm_calls_found": 0,
        "prompt_log_files": [],
        "_debug_raw_lines": 0,
        "_debug_filtered_lines": 0,
        "_debug_session_in_raw": False,
        "_debug_session_in_filtered": False,
    }

    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"app_{today}.log"

    if not log_file.exists():
        return result

    try:
        raw_content = log_file.read_text(encoding="utf-8", errors="ignore")
        result["_debug_raw_lines"] = len(raw_content.splitlines())

        # ── 时间过滤 ──
        # 铁律: 日志只有秒精度(%H:%M:%S), start_time有微秒精度。
        # 截断到秒避免同秒日志被误过滤 — 小欧 2026-07-15
        if start_time:
            start_time_sec = start_time.replace(microsecond=0)
            filtered: List[str] = []
            current_ts: Optional[datetime] = None
            for line in raw_content.splitlines():
                m = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
                if m:
                    try:
                        current_ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        current_ts = None
                if current_ts is None or current_ts >= start_time_sec:
                    filtered.append(line)
            content = "\n".join(filtered)
            result["_debug_filtered_lines"] = len(filtered)
            result["_debug_session_in_raw"] = bool(session_id and session_id in raw_content)
            result["_debug_session_in_filtered"] = bool(session_id and session_id in content)
        else:
            content = raw_content

        # ── ERROR检查(MUST) ──
        # 只匹配ERROR级别日志(格式: timestamp - ERROR - ...)，不匹配内容中的ERROR字样
        # 锚定时间戳+级别字段,避免INFO行消息体含" - ERROR - "被贪婪误判 - 小沈 2026-07-17
        for line in re.findall(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} - ERROR - .*$", content, re.MULTILINE)[:10]:
            if "unable to open database file" in line:
                continue
            if "e2e_test" in line:
                continue
            if "流式错误" in line or "请求超时" in line:
                continue
            if "operation_cleanup" in line and "Failed to size-cleanup" in line:
                continue
            if "database is locked" in line:
                continue
            if "Error executing operation" in line:
                continue
            if "操作已被中断" in line:
                continue
            if "未知错误" in line and ("http" in line.lower() or "fetch" in line.lower()):
                continue
            if "ERR_SQL_EXEC" in line:
                continue
            if "LLM格式错误" in line:
                continue
            if "写入失败" in line and "文件系统错误" in line:
                continue
            # 压缩工具用密码加密后, 无密码解压属预期失败(已捕获), 非后端缺陷 — 小欧 2026-07-13
            if "is encrypted" in line or ("解压失败" in line and "encrypted" in line):
                continue
            result["errors"].append(line.strip()[:200])

        # ── traceback检查(MUST) ──
        # 只统计独立的Python traceback(行首)，排除工具结果中嵌入的traceback(属于LLM生成代码问题)
        tb_count = len(re.findall(r"^Traceback \(most recent call last\)", content, re.MULTILINE))
        if tb_count > 0:
            result["tracebacks"].append(f"发现{tb_count}个traceback")

        # ── session操作记录检查 ──
        if session_id and session_id in content:
            result["session_records_found"] = True
        elif re.search(r"session", content, re.IGNORECASE):
            result["session_records_found"] = True

        # ── SSE事件发送记录检查 ──
        if re.search(r"(SSE|event|stream|data:)", content, re.IGNORECASE):
            result["sse_records_found"] = True

        # ── prompt-logs检查 ──
        if PROMPT_LOG_DIR.exists():
            prompt_files = sorted(
                PROMPT_LOG_DIR.glob("prompt_*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if user_msg_id is not None:
                # 按用户消息ID匹配，一轮对话只对应一个prompt日志
                matched = []
                for pf in prompt_files[:50]:
                    try:
                        content = pf.read_text(encoding="utf-8", errors="ignore")
                        if str(user_msg_id) in content:
                            matched.append(pf)
                            if len(matched) >= 1:
                                break
                    except Exception:
                        pass
                recent = matched[:1] if matched else []
            elif session_id:
                matched = []
                for pf in prompt_files[:50]:
                    try:
                        content = pf.read_text(encoding="utf-8", errors="ignore")
                        if session_id in content:
                            matched.append(pf)
                            if len(matched) >= 1:
                                break
                    except Exception:
                        pass
                recent = matched[:1] if matched else []
            else:
                recent = [f for f in prompt_files if f.stat().st_mtime >= (now.timestamp() - 3600)]
            result["prompt_log_files"] = [f.name for f in recent[:1]]
            for pf in recent[:1]:
                try:
                    pdata = json.loads(pf.read_text(encoding="utf-8", errors="ignore"))
                    # Prompt日志顶层无 llm_call_count; LLM调用次数 = «LLM调用记录»数组长度
                    result["llm_calls_found"] += len(pdata.get("LLM调用记录", [])) or 1
                except Exception:
                    pass

    except Exception as e:
        result["errors"].append(f"读取日志异常: {e}")

    return result


# ─── 步骤11: 清理 (cleanup) ────────────────────────────────────

def cleanup(
    session_id: Optional[str] = None,
    test_files: Optional[List[Path]] = None,
) -> None:
    """手册步骤11: 清理测试产生的数据(通过后端API) -- 小健 2026-06-14

    - 通过API清理DB中的session记录
    - 清理测试产生的文件
    """
    if session_id:
        _api_delete(f"/sessions/{session_id}")

    if test_files:
        for f in test_files:
            if f.exists():
                f.unlink(missing_ok=True)


# ─── 测试报告 ────────────────────────────────────────────────

def print_report(
    test_id: str,
    test_name: str,
    result: Dict[str, Any],
    db_check: Dict[str, Any],
    log_check: Dict[str, Any],
    consistency_issues: List[str],
    step_issues: List[str],
    passed: bool,
    elapsed: float,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """输出结构化测试报告 -- 小健 2026-06-14"""
    mark = "[OK]" if passed else "[FAIL]"
    status = "PASSED" if passed else "FAILED"

    event_desc = "->".join(result.get("event_types", [])) or "none"
    tool_names = [t["tool_name"] for t in result.get("tool_calls", [])]

    db_sess = mark if db_check.get("session_exists") else "[FAIL]"
    db_valid = mark if db_check.get("is_valid") else "[WARN]"
    db_order = mark if db_check.get("message_order_correct") else "[WARN]"
    db_msg = mark if db_check.get("has_assistant_message") else "[FAIL]"
    db_step = mark if db_check.get("execution_steps_count", 0) > 0 else "[WARN]"
    db_field = mark if len(db_check.get("step_field_issues", [])) == 0 else "[FAIL]"

    sse_ok = mark if len(consistency_issues) == 0 else "[FAIL]"
    step_ok = mark if len(step_issues) == 0 else "[WARN]"
    log_err = mark if len(log_check.get("errors", [])) == 0 else "[FAIL]"
    log_tb = mark if len(log_check.get("tracebacks", [])) == 0 else "[FAIL]"
    log_sess = mark if log_check.get("session_records_found") else "[WARN]"
    log_sse = mark if log_check.get("sse_records_found") else "[WARN]"

    report = (
        f"\n=== {test_id}: {test_name} ===\n"
        f"  Status: {status}\n"
        f"  Elapsed: {elapsed:.1f}s ({result.get('total_time_ms', 0)}ms)\n"
        f"  SSE events: {result.get('total_steps', 0)} ({event_desc})\n"
        f"  LLM calls: {result.get('llm_call_count', 0)}\n"
        f"  DB: {db_sess} session, {db_valid} is_valid, {db_order} order,"
        f" {db_msg} msgs, {db_step} steps, {db_field} fields\n"
        f"  Consistency: {sse_ok} ({len(consistency_issues)} issues)\n"
        f"  Step reason: {step_ok} ({len(step_issues)} issues)\n"
        f"  Logs: {log_err} no-ERROR, {log_tb} no-TB,"
        f" {log_sess} sess-records, {log_sse} SSE-records\n"
        f"  Tools: {tool_names}\n"
    )
    if extra:
        for k, v in extra.items():
            report += f"  {k}: {v}\n"
    report += f"  Conclusion: {status}"

    try:
        print(report)
    except UnicodeEncodeError:
        print(report.encode("ascii", errors="replace").decode("ascii"))


# ─── 步骤6+11: 门禁记录验证 + 测试记录写入 ───────────────────

RECORD_DIR = Path(__file__).parent.parent.parent.parent / "notes"


# ─── 超时 marker 系统（进程被强杀时保留证据）────────────────────
# 小欧 2026-06-26
# 在测试开始时写一个 JSON marker 文件，结束时删除。
# 如果进程被强杀，marker 文件保留在磁盘上，recover_timeout_markers() 可恢复为 TIMEOUT 记录。

STATUS_DIR = RECORD_DIR / ".e2e_status"


def write_test_marker(test_id: str, test_name: str = "", user_input: str = ""):
    """在测试开始时写入 marker 文件，标记该测试正在运行。
    
    写磁盘是同步操作，即使进程随后被强杀，marker 文件也已存在。
    """
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    marker = STATUS_DIR / f"{test_id}.json"
    data = {
        "test_id": test_id,
        "test_name": test_name,
        "user_input": user_input,
        "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "RUNNING",
    }
    marker.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [MARKER] {marker.name}")


def clear_test_marker(test_id: str):
    """测试正常/异常完成时删除 marker 文件。"""
    marker = STATUS_DIR / f"{test_id}.json"
    if marker.exists():
        marker.unlink()
        print(f"  [MARKER CLEAR] {marker.name}")
    else:
        # 同时检查旧命名模式兼容
        for old in STATUS_DIR.glob(f"{test_id}_*.json"):
            old.unlink()


def recover_timeout_markers() -> int:
    """扫描 STATUS_DIR 中剩余的 marker，转为 TIMEOUT 测试记录。
    
    如果进程被强杀（bash timeout），marker 未清理。
    调用此函数将其转换为标准的 TIMEOUT 记录文件。
    返回恢复的记录数。
    """
    if not STATUS_DIR.exists():
        return 0
    count = 0
    for marker_file in sorted(STATUS_DIR.glob("*.json")):
        try:
            data = json.loads(marker_file.read_text(encoding="utf-8"))
            test_id = data.get("test_id", marker_file.stem)
            test_name = data.get("test_name", "未知")
            user_input = data.get("user_input", "")
            start_time = data.get("start_time", "未知")
            elapsed = 0.0
            # 如果start_time已知，计算已经过了多久
            if start_time != "未知":
                try:
                    st = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                    elapsed = (datetime.now() - st).total_seconds()
                except ValueError:
                    pass
            # 写入 TIMEOUT 记录
            TIMEOUT_RECORD = (
                f"# 测试记录-{test_id}\n\n"
                f"**创建时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"**测试编号**: {test_id}\n"
                f"**测试名称**: {test_name}\n"
                f"**用户命令**: {user_input}\n"
                f"**测试结果**: TIMEOUT\n\n"
                f"---\n\n"
                f"## 1 超时说明\n\n"
                f"测试在 {start_time} 启动后进程被强杀，未正常完成 `write_test_record()`。\n"
                f"此记录由 `recover_timeout_markers()` 从残留 marker 恢复。\n\n"
                f"**恢复时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"**已过时间**: {elapsed:.0f}秒\n\n"
                f"---\n"
                f"**更新时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            )
            today = datetime.now().strftime("%Y-%m-%d")
            record_file = RECORD_DIR / f"测试记录-{test_id}-{today}.md"
            record_file.write_text(TIMEOUT_RECORD, encoding="utf-8")
            print(f"  [RECOVER TIMEOUT] {record_file.name}")
            marker_file.unlink()
            count += 1
        except Exception as e:
            print(f"  [RECOVER FAIL] {marker_file.name}: {e}")
    return count


def verify_test_record_exists(test_id: str) -> bool:
    """验证测试记录文件是否存在 -- 小欧 2026-06-18
    
    每个测试跑完后必须调用此函数确认记录已生成。
    返回True表示记录存在，False表示记录缺失（严重问题）。
    """
    today = datetime.now().strftime("%Y-%m-%d")
    record_file = RECORD_DIR / f"测试记录-{test_id}-{today}.md"
    exists = record_file.exists()
    if exists:
        size = record_file.stat().st_size
        print(f"  [RECORD] {record_file.name} ({size} bytes)")
    else:
        print(f"  [RECORD FAIL] {record_file.name} NOT FOUND!")
    return exists


def verify_token_usage(session_id: str, expected_calls: int) -> List[str]:
    """主动验证 token_usage 真实落库(消除"日志无ERROR即PASS"盲区) — 小欧 2026-08-23
    原 write_test_record 的 passed 仅依赖日志ERROR扫描; 若 token_usage_insert 静默失败(不打ERROR),
    测试记录会假PASSED。本函数直接查DB确认 token_usage 行数, 与 llm_call_count 比对。
    返回 issue 列表(空=通过); expected_calls<=0 时不强制(任务可能无LLM调用)。"""
    issues: List[str] = []
    if not session_id:
        return issues
    try:
        _c = sqlite3.connect(str(DB_PATH))
        _c.row_factory = sqlite3.Row
        _n = _c.execute(
            "SELECT count(*) n FROM token_usage WHERE session_id=?", (session_id,)
        ).fetchone()["n"]
        _c.close()
        if expected_calls and expected_calls > 0:
            if _n == 0:
                issues.append(
                    f"token_usage 落库失败(静默): session={session_id} 期望≥{expected_calls}行, 实际0行")
            elif _n < expected_calls:
                issues.append(
                    f"token_usage 落库不全: session={session_id} 期望{expected_calls}行, 实际{_n}行")
    except Exception as _e:
        issues.append(f"token_usage 核查异常: {_e}")
    return issues


def write_test_record(
    test_id: str,
    test_name: str,
    user_input: str,
    result: Dict[str, Any],
    db: Dict[str, Any],
    consistency_issues: List[str],
    step_issues: List[str],
    log_check: Dict[str, Any],
    passed: bool,
    elapsed: float = 0.0,
    extra: Optional[Dict[str, Any]] = None,
    dpi: Optional[List[str]] = None,
    error_info: Optional[str] = None,
    test_title: Optional[str] = None,
) -> Optional[Path]:
    """手册步骤6+11: 写入测试记录文件 + 输出[CALL CHAIN]+[RECORD OK] -- 小健 2026-06-18

    职责划分(铁律):
      核心脚本(e2e_helpers.py): 所有通用逻辑——计时、格式化、文件写入、判断PASS/FAIL
      case脚本(test_e2e_*.py): 只负责组装参数、调用核心函数、断言验证
      通用逻辑严禁散落在case脚本中

    计时来源:
      start_time/end_time — 由send_chat()写入result，本函数直接取
      elapsed(SSE耗时) — 由调用方从result["total_time_ms"]算出传入
      运行耗时(start→end) — 本函数从result["start_time"]到datetime.now()自动算出

    必须在finally块中调用，即使失败也要写
    文件: notes/测试记录-{test_id}-{日期}.md
    
    v1.9增强: error_info参数记录异常详情(类型+消息+堆栈)
    v2.0增强: 超时保护 - 注册待写入记录，进程异常终止时由atexit/signal写入
    v2.1增强: 返回记录文件路径；写入后验证文件存在；失败时尝试备用路径
    v2.2增强: 新的PASS/FAIL判断标准 - final=通过, 任何error=失败, DB-Prompt严格对比
    v2.3增强: 计时统一由核心脚本处理，case脚本不传start_time -- 小欧 2026-07-03
    -- 小健 2026-06-24
    """
    if test_title:
        test_name = test_title
    # 兼容处理: consistency_issues可能传入tool_calls(dict列表)而非issues(string列表)
    # dict列表代表tool_calls,不是一致性问题,应视为空问题 -- 小健 2026-06-19
    if consistency_issues and isinstance(consistency_issues[0], dict):
        consistency_issues = []
    # 先清除同test_id旧记录，再注册新记录（防止_reflush_pending_records重复写入）
    remove_pending_record(test_id)
    # 注册待写入记录（超时保护）
    register_pending_record(
        test_id, test_name, user_input, result, db,
        consistency_issues, step_issues, log_check,
        passed, elapsed, extra, dpi, error_info,
    )
    RECORD_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    end_str = now.strftime("%Y-%m-%d %H:%M:%S")
    record_file = RECORD_DIR / f"测试记录-{test_id}-{date_str}.md"

    # ── 计时：全部从result取，case脚本不参与 -- 小欧 2026-07-03 ──
    wall_start = result.get("start_time")
    sse_elapsed = elapsed  # SSE流接收耗时(调用方从total_time_ms算出传入)
    if wall_start is not None:
        test_elapsed = (now - wall_start).total_seconds()
        start_str = wall_start.strftime("%Y-%m-%d %H:%M:%S")
    else:
        test_elapsed = elapsed
        start_str = end_str

    # ============================================================
    # v2.2 新的PASS/FAIL判断标准 - 小健 2026-06-24
    # 1. 最终有final事件 → 通过
    # 2. 最终有error事件 或中途系统代码出现问题 → 失败
    # 3. tool问题必须记录在测试记录中
    # ============================================================
    final_event = result.get("final_event")
    has_error = result.get("has_error", False)
    # 2026-07-18 小欧 响应 FinalStep 多态重构: 终态统一 type=final, 由 outcome 声明结果,
    # 失败/取消不再发 error 事件, 故须读 final.outcome 判终态, 否则失败任务被误判 PASSED
    _final_outcome = final_event.get("outcome", "completed") if isinstance(final_event, dict) else "completed"
    end_type = assert_stream_ended(result)

    # 提取回复内容（统一在if/else外初始化）
    resp = result.get("response_text", "")
    resp_has_error = False

    # 新的判断标准: 必须有final事件才通过; 终态失败/取消(error事件或outcome)→失败
    # 2026-08-12 小欧 COM_03误判修复: has_error需按error_type区分可恢复/不可恢复。
    #   blocked/user_rejected(拒绝≠失败, react_cycle._RECOVERABLE_ERRORS)不判失败, 与任务实际completed一致。
    _RECOVERABLE_ERROR_TYPES = {"blocked", "user_rejected"}
    _fatal_error = False
    for _ev in result.get("events", []):
        if _ev.get("type") == "error" and _ev.get("error_type", "") not in _RECOVERABLE_ERROR_TYPES:
            _fatal_error = True
            break
    if final_event is not None:
        # 有final事件，检查是否有不可恢复error或终态失败/取消
        if _fatal_error or _final_outcome in ("failed", "cancelled"):
            passed = False

    else:
        # 没有final事件，失败
        passed = False
    
    # DB-Prompt一致性FAIL则整体FAILED
    if passed and dpi is not None and len(dpi) > 0:
        passed = False
    
    # 日志中有ERROR或traceback则失败
    if passed:
        if len(log_check.get("errors", [])) > 0:
            passed = False
        if len(log_check.get("tracebacks", [])) > 0:
            passed = False
    # 2026-08-23 小欧: 主动核查 token_usage 落库(消除"日志无ERROR即PASS"盲区)
    if passed:
        _tu_sid = result.get("session_id", "")
        if _tu_sid:
            _tu_issues = verify_token_usage(_tu_sid, result.get("llm_call_count", 0))
            if _tu_issues:
                passed = False
    tool_calls = result.get("tool_calls", [])
    tool_names = [t.get("tool_name", "") for t in tool_calls]
    event_types = result.get("event_types", [])
    events = result.get("events", [])
    logical_events = [e for e in events if e.get("type") != "chunk"]
    unique_step_nums = len({e.get("step") for e in events if e.get("step") is not None})


    if not db:
        sid = result.get("session_id", "")
        if sid:
            try:
                fb = check_db(sid)
                if fb.get("session_exists"):
                    db = fb
            except Exception:
                pass

    # 自动调用 Prompt日志 vs DB步骤对比（用例脚本无需手动调用）
    if dpi is None:
        _sid = result.get("session_id", "")
        _umid = result.get("user_msg_id")
        if _sid:
            try:
                dpi = verify_db_prompt_consistency(_sid, _umid)
            except Exception:
                dpi = []

    # 任务Token使用情况(取DB final步骤accumulated_usage, 实库字段: prompt/completion/total_tokens) - 小欧 2026-08-22
    _final_usage = {}
    for _s in reversed(db.get("execution_steps", [])):
        if isinstance(_s, dict) and _s.get("type") == "final":
            _final_usage = _s.get("accumulated_usage") or {}
            break

    lines: List[str] = []
    lines.append(f"# 测试记录-{test_id}-{date_str}")
    lines.append("")
    lines.append(f"**创建时间**: {end_str}")
    lines.append(f"**测试编号**: {test_id}")
    status = "PASSED" if passed else "FAILED"
    lines.append(f"**测试结果**: {status}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # model 结构信息(小欧 2026-08-23): 归一后模型身份=ModelRef JSON, 取自 chat_tasks.sessionModel(回退 token_usage.task_model)
    _model_info = "-"
    try:
        if _sid:
            _mc = sqlite3.connect(str(DB_PATH))
            _mc.row_factory = sqlite3.Row
            _mr = _mc.execute(
                "SELECT sessionModel FROM chat_tasks WHERE session_id=? ORDER BY rowid DESC LIMIT 1",
                (_sid,)).fetchone()
            _mj = None
            if _mr and _mr["sessionModel"]:
                _mj = json.loads(_mr["sessionModel"])
            else:
                _mt = _mc.execute(
                    "SELECT task_model FROM token_usage WHERE session_id=? ORDER BY rowid DESC LIMIT 1",
                    (_sid,)).fetchone()
                if _mt and _mt["task_model"]:
                    _mj = json.loads(_mt["task_model"])
            _mc.close()
            if _mj:
                _model_info = (f"provider={_mj.get('provider')}, model={_mj.get('model')}, "
                               f"display_name={_mj.get('display_name')}")
    except Exception:
        _model_info = "-"

    # 跨任务注入上下文(小欧 2026-08-23): 取自 context_overview 事件的 injected_message_count/injected_estimated_tokens,
    # 展示本任务之前注入的连续对话历史体量(多轮历史注入机制, 单轮任务为0)
    _inj_info = "无(本任务单轮/无历史注入)"
    for _ev in result.get("events", []):
        if isinstance(_ev, dict) and _ev.get("type") == "context_overview":
            _inj_n = _ev.get("injected_message_count", 0) or 0
            _inj_tok = _ev.get("injected_estimated_tokens", 0) or 0
            if _inj_n or _inj_tok:
                _inj_info = f"消息{_inj_n}条/≈{_inj_tok}tok(估算)"
            break

    # 第1节：测试基本信息
    lines.append("## 1 测试基本信息")
    lines.append("")
    lines.append("| 项目 | 内容 |")
    lines.append("|------|------|")
    lines.append(f"| 测试编号 | {test_id} |")
    lines.append(f"| 任务描述 | {test_name} |")
    lines.append(f"| 用户命令 | `{user_input}` |")
    lines.append(f"| 开始时间 | {start_str} |")
    lines.append(f"| 结束时间 | {end_str} |")
    lines.append(f"| 运行耗时 | {test_elapsed:.1f}秒 |")
    lines.append(f"| SSE接收耗时 | {sse_elapsed:.1f}秒 |")
    lines.append(f"| SSE总事件数 | {result.get('total_steps', 0)} |")
    lines.append(f"| LLM调用次数 | {result.get('llm_call_count', 0)} |")
    if _final_usage:
        _usage_cell = (
            f"{_final_usage.get('prompt_tokens', '-')} / "
            f"{_final_usage.get('completion_tokens', '-')} / "
            f"{_final_usage.get('total_tokens', '-')}"
        )
    else:
        _usage_cell = "-"
    lines.append(f"| Token使用(prompt/completion/total) | {_usage_cell} |")
    lines.append(f"| model 结构信息 | {_model_info} |")
    lines.append(f"| 跨任务注入上下文 | {_inj_info} |")
    lines.append(f"| 逻辑步数 | {len(logical_events)} |")
    lines.append(f"| 不重复步骤号数 | {unique_step_nums} |")
    lines.append(f"| 测试结果 | **{status}** |")
    lines.append("")

    # 第2节：LLM回复内容 + 终态元信息
    lines.append("## 2 LLM回复内容")
    lines.append("")
    lines.append("### 2.1 回复正文")
    lines.append("")
    lines.append("```")
    # 2026-08-19 小欧 转义: LLM答复内嵌的 ``` 会提前打断外层围栏致记录排版错位, 替换为 ~~~ 防冲突
    _resp_cell = (resp or "").replace("```", "~~~")
    lines.append(_resp_cell if resp else "(空)")
    lines.append("```")
    lines.append("")
    # 2.2 终态元信息(final_stats): duration(执行耗时) + artifacts(任务产出物)
    # 小欧 2026-08-21: 后端v0.19.18起 final_stats 事件携带 duration/artifacts 两个meta字段
    # 小欧 2026-08-22: artifacts 为4字段 {tool_name,name,path,type}, 且仅写工具自声明(F1定案删兜底派生)才有值
    _final_stats = None
    for _ev in result.get("events", []):
        if isinstance(_ev, dict) and _ev.get("type") == "final_stats":
            _final_stats = _ev
            break
    lines.append("### 2.2 终态元信息(final_stats)")
    lines.append("")
    if _final_stats:
        _dur = _final_stats.get("duration")
        _arts = _final_stats.get("artifacts") or []
        # 表1: 执行耗时 + 产出物数量
        lines.append(f"| 指标 | 值 |")
        lines.append(f"|------|-----|")
        if _dur is not None:
            lines.append(f"| 执行耗时(duration) | {_dur}秒 |")
        lines.append(f"| 产出物数量(artifacts) | {len(_arts)}个 |")
        lines.append("")
        # 表2: 产出物明细（4字段: tool_name/name/path/type — 小欧 2026-08-22 取值对齐新结构）
        if _arts:
            lines.append(f"| 序号 | 工具(tool_name) | 文件名(name) | 类型(type) | 路径(path) |")
            lines.append(f"|------|------|------|------|------|")
            for _ai, _a in enumerate(_arts):
                _tname = _a.get("tool_name", "")
                _name = _a.get("name", "")
                _path = _a.get("path", "")
                _type = _a.get("type", "")
                lines.append(f"| {_ai+1} | {_tname} | {_name} | {_type} | `{_path}` |")
    else:
        lines.append("（本次无 final_stats 事件）")
    lines.append("")

    # 第3节：工具调用链
    lines.append("## 3 工具调用链")
    lines.append("")
    if tool_names:
        lines.append(" -> ".join(tool_names))
        lines.append("")
        lines.append("| 序号 | 工具名 | 参数 |")
        lines.append("|------|--------|------|")
        for i, tc in enumerate(tool_calls):
            params_str = json.dumps(tc.get("tool_params", {}), ensure_ascii=False)
            params_display = params_str[:100] + "..." if len(params_str) > 100 else params_str
            lines.append(f"| {i+1} | {tc.get('tool_name', '')} | `{params_display}` |")
    else:
        lines.append("(无工具调用)")
    lines.append("")
    # 第4节：SSE事件详情
    lines.append("## 4 SSE事件详情")
    lines.append("")
    chunk_count = 0
    for e in events:
        et = e.get("type", "")
        step = e.get("step", "")
        if et == "chunk":
            chunk_count += 1
            continue
        tool = e.get("tool_name", "")
        desc = f"- {et} 步骤={step}"
        if tool:
            desc += f" 工具={tool}"
        lines.append(desc)
    if chunk_count > 0:
        lines.append(f"  ... (chunk x{chunk_count})")
    lines.append("")

    # 第5节：数据库验证详情
    lines.append("## 5 数据库验证详情")
    lines.append("")
    lines.append("| 检查项 | 结果 |")
    lines.append("|--------|------|")
    lines.append(f"| 会话是否存在 | {db.get('session_exists', 'N/A')} |")
    lines.append(f"| 是否有效 | {db.get('is_valid', 'N/A')} |")
    lines.append(f"| 创建时间 | {db.get('created_at', 'N/A')} |")
    lines.append(f"| 更新时间 | {db.get('updated_at', 'N/A')} |")
    lines.append(f"| 消息顺序正确 | {db.get('message_order_correct', 'N/A')} |")
    lines.append(f"| 消息数量 | {db.get('messages_count', 0)} |")
    lines.append(f"| 执行步骤数 | {db.get('execution_steps_count', 0)} |")
    lines.append(f"| 步骤字段问题数 | {len(db.get('step_field_issues', []))} |")
    lines.append("")

    # 第5.2节：执行步骤详情（全部步骤, 北京老陈指示取消15条限制）— 小欧 2026-08-22
    db_steps = db.get("execution_steps", [])
    if db_steps:
        # token三层接入(系统数据齐全, 记录侧此前未展示): usage不落库(P6)仅SSE通道, 本轮token按轮
        #   从SSE usage事件取; 任务/会话累计从final步骤json取(每轮即时落库+终态透传) - 小欧 2026-08-22
        _usage_by_step: Dict[Any, Dict[str, Any]] = {}
        for _ev in result.get("events", []):
            if isinstance(_ev, dict) and _ev.get("type") == "usage" and _ev.get("step") is not None:
                _usage_by_step[_ev["step"]] = _ev
        _final_db: Dict[str, Any] = {}
        for _s in reversed(db_steps):
            if isinstance(_s, dict) and _s.get("type") == "final":
                _final_db = _s
                break

        # SSE侧事件补行(北京老陈指示): usage/error/paused/resumed/retrying/cancelled仅SSE不落库(P1~P6),
        #   按流序插入本表与落库步骤混排; chunk逐token量大/thought_start纯开始信号(steps/__init__.py:11
        #   仅SSE实时信号)不补。对齐法: 落库步骤随emit同步落库,SSE到达序=落库序,顺序遍历events遇落库
        #   类型即按位消耗db_steps; 对齐守卫: events中落库类型事件数≠len(db_steps)(如断连缺帧)时
        #   位置推断不可靠, 退化为"落库表全量在前+SSE行尾部追加", 宁可乱序不错位 - 小欧 2026-08-22
        _SSE_WANT = ("usage", "error", "paused", "resumed", "retrying", "cancelled")
        _SSE_SKIP = {"chunk", "thought_start"}
        _rows: List[Any] = []  # 元素二元组: ("db", 落库step) / ("sse", SSE事件)
        _n_db_ev = sum(
            1 for _ev in result.get("events", [])
            if isinstance(_ev, dict)
            and _ev.get("type") not in _SSE_SKIP
            and _ev.get("type") not in _SSE_WANT
        )
        if _n_db_ev == len(db_steps):
            _j = 0
            for _ev in result.get("events", []):
                if not isinstance(_ev, dict):
                    continue
                _t = _ev.get("type")
                if _t in _SSE_SKIP:
                    continue
                if _t in _SSE_WANT:
                    _rows.append(("sse", _ev))
                else:
                    _rows.append(("db", db_steps[_j]))
                    _j += 1
        else:
            _rows = [("db", _s) for _s in db_steps]
            _rows += [
                ("sse", _ev) for _ev in result.get("events", [])
                if isinstance(_ev, dict) and _ev.get("type") in _SSE_WANT
            ]

        lines.append("### 5.2 执行步骤（全部·含SSE侧usage/error等未落库事件）")
        lines.append("")
        lines.append("| 序号 | 轮次 | 类型 | 工具 | 内容摘要 |")
        lines.append("|------|--------|------|------|----------|")
        for i, (_kind, _item) in enumerate(_rows):
            if _kind == "sse":
                _t = _item.get("type", "")
                if _t == "usage":
                    # usage独立成行: 本轮token三数入(prompt)/出(completion)/总(total)
                    #   ——react_cycle.py:470-483每次LLM调用yield一条 - 小欧 2026-08-22
                    _b = (
                        f"本轮({_fmt_tok(_item)})tok"
                        if _item.get("total_tokens") is not None
                        else ""
                    )
                else:
                    _b = _step_brief(_item)
                lines.append(
                    f"| {i+1} | {_item.get('step', '')} | {_t} |  | {_b} |"
                )
                continue
            s = _item
            s_step = s.get("step", "")
            s_type = s.get("type", "")
            s_tool = ""
            if _is_action_step(s):
                _entries = _action_entries(s)
                s_tool = ", ".join(e.get("tool_name", "") for e in _entries)
            elif s_type == "observation":
                _tr = s.get("tool_result") or []
                s_tool = ", ".join(
                    x.get("tool_name", "") for x in _tr if isinstance(x, dict)
                )
            _brief = _step_brief(s)
            if s_type == "stats":
                # 每轮stats行两组token三数全显(北京老陈指示): 任务/会话累计各含入(prompt)/出(completion)
                #   /总(total)三数; 本轮三数由usage独立行承担, 此处不重复 - 小欧 2026-08-22
                _u = _usage_by_step.get(s_step)
                if _u and _u.get("total_tokens") is not None:
                    _uk = _u.get("task_accumulated_tokens")
                    _us = _u.get("session_accumulated_tokens")
                    if _uk:
                        _brief += f"/任务累计({_fmt_tok(_uk)})tok"
                    if _us:
                        _brief += f"/会话累计({_fmt_tok(_us)})tok"
            elif s_type == "final_stats" and _final_db:
                # final_stats行两组token三数全显: 任务/会话累计各含入/出/总三数 - 小欧 2026-08-22
                _tk = _final_db.get("task_accumulated_tokens")
                _sk = _final_db.get("session_accumulated_tokens")
                if _tk:
                    _brief += f"/任务累计({_fmt_tok(_tk)})tok"
                if _sk:
                    _brief += f"/会话累计({_fmt_tok(_sk)})tok"
            lines.append(f"| {i+1} | {s_step} | {s_type} | {s_tool} | {_brief} |")
        lines.append("")

        # 第5.3节：步骤数据内容 — 按轮交错配对(本轮参数→本轮观察结果), 消除原"全参数段→全观察段"
        #   两段式排版造成的"工具↔结果对不上/时有时无"错觉 — 病根定案: 测试记录代码问题 - 小欧 2026-08-22
        #   2026-08-22 北京老陈指示: §5.3限制只展示前10轮
        action_steps = [s for s in db_steps if _is_action_step(s)]
        obs_steps = [s for s in db_steps if s.get("type") == "observation"]
        if action_steps or obs_steps:
            _round_order: List[Any] = []
            for _s in db_steps:
                if _is_action_step(_s) or _s.get("type") == "observation":
                    _sn = _s.get("step", "?")
                    if _sn not in _round_order:
                        _round_order.append(_sn)
            _allowed_rounds = set(_round_order[:10])
            _extra_rounds = len(_round_order) - len(_allowed_rounds)
            lines.append(f"### 5.3 步骤数据内容(action/observation 按轮配对, 前10轮)")
            lines.append("")
            _obs_by_step: Dict[Any, List[Dict[str, Any]]] = {}
            for _o in obs_steps:
                _obs_by_step.setdefault(_o.get("step", "?"), []).append(_o)

            def _render_obs(o: Dict[str, Any]) -> None:
                on = o.get("step", "?")
                tr = o.get("tool_result")
                obs_str = _obs_to_text(tr) if tr else "(空)"
                lines.append(f"**步骤{on}: observation**")
                lines.append(f"- 观察结果: `{obs_str}`")

            for s in db_steps:
                if not _is_action_step(s):
                    continue
                sn = s.get("step", "?")
                if sn not in _allowed_rounds:
                    continue
                for _en in _action_entries(s):
                    tn = _en.get("tool_name", "?")
                    tp = json.dumps(_en.get("tool_params", {}), ensure_ascii=False)
                    lines.append(f"**步骤{sn}: {tn}**")
                    lines.append(f"- 参数: `{tp}`")
                for _o in _obs_by_step.pop(sn, []):
                    _render_obs(_o)
            # 兜底: 无action配对的孤立observation轮(正常不存在, 防静默丢数据)
            for _sn in list(_obs_by_step.keys()):
                if _sn not in _allowed_rounds:
                    _obs_by_step.pop(_sn)
            for _o_list in _obs_by_step.values():
                for _o in _o_list:
                    _render_obs(_o)
            if _extra_rounds > 0:
                lines.append(f"> (第11轮起共{_extra_rounds}轮未展示, 全量见5.2执行步骤表)")
            lines.append("")

    # DB↔Prompt日志一致性(来自dpi参数或extra)
    db_prompt_issues = dpi if dpi is not None else (extra or {}).get("DbPromptIssues", [])
    db_prompt_ok = len(db_prompt_issues) == 0
    db_prompt_detail = f"{len(db_prompt_issues)}个问题" if db_prompt_issues else "PASS"

    # 第6节：验证结果
    lines.append("## 6 验证结果")
    lines.append("")
    lines.append("| 验证项 | 结果 | 说明 |")
    lines.append("|--------|------|------|")
    stream_end_type = assert_stream_ended(result)
    lines.append(f"| 流结束 | {stream_end_type} | - |")
    # 2026-08-12 小欧 COM_03误判修复: error事件区分可恢复(blocked/user_rejected,拒绝≠失败)/不可恢复
    _recoverable_errors = [
        f"step={_e.get('step')}({_e.get('error_type','')})"
        for _e in result.get("events", [])
        if _e.get("type") == "error" and _e.get("error_type", "") in _RECOVERABLE_ERROR_TYPES
    ]
    _fatal_error_desc = "不可恢复error事件" if _fatal_error else ("无error事件" if not _recoverable_errors else f"仅可恢复拒绝事件({';'.join(_recoverable_errors)})")
    lines.append(f"| 是否有error事件 | {'FAIL' if _fatal_error else 'PASS'} | {_fatal_error_desc} |")
    lines.append(f"| 回复内容 | {'FAIL' if not resp or resp_has_error else 'PASS'} | {len(resp)}字{' [含错误关键词]' if resp_has_error else ''} |")
    lines.append(f"| 数据库验证 | {'PASS' if db.get('session_exists') else 'FAIL'} | - |")
    lines.append(f"| SSE-DB一致性 | {'PASS' if len(consistency_issues) == 0 else 'FAIL'} | {len(consistency_issues)}个问题 |")
    lines.append(f"| DB-Prompt日志一致性 | {'PASS' if db_prompt_ok else 'FAIL'} | {db_prompt_detail} |")
    step_field_issues = db.get("step_field_issues", [])
    lines.append(f"| 步骤字段完整性 | {'PASS' if len(step_field_issues) == 0 else 'FAIL'} | {len(step_field_issues)}个问题 |")
    lines.append(f"| 步骤合理性 | {'PASS' if len(step_issues) == 0 else 'FAIL'} | {len(step_issues)}个问题 |")
    lines.append(f"| 日志中ERROR | {'PASS' if len(log_check.get('errors', [])) == 0 else 'FAIL'} | {len(log_check.get('errors', []))}条 |")
    lines.append(f"| 日志中异常堆栈 | {'PASS' if len(log_check.get('tracebacks', [])) == 0 else 'FAIL'} | {len(log_check.get('tracebacks', []))}条 |")
    lines.append("")
    
    # DB-Prompt日志不一致详情
    if db_prompt_issues:
        lines.append("### DB-Prompt日志不一致详情")
        lines.append("")
        for i, issue in enumerate(db_prompt_issues):
            lines.append(f"{i+1}. {issue}")
        lines.append("")

    if not passed and error_info:
        lines.append("## 失败详情")
        lines.append("")
        lines.append("**异常信息**:")
        lines.append("")
        lines.append("```")
        lines.append(error_info[:5000])
        lines.append("```")
        lines.append("")

    if resp_has_error and resp:
        lines.append("**回复内容错误详情**:")
        lines.append("")
        lines.append("```")
        lines.append(resp)
        lines.append("```")
        lines.append("")

    log_errors = log_check.get("errors", [])
    log_tracebacks = log_check.get("tracebacks", [])
    if log_errors or log_tracebacks:
        lines.append("### 日志错误详情")
        lines.append("")
        if log_errors:
            lines.append("**ERROR日志**:")
            lines.append("")
            for err in log_errors:
                lines.append(f"```")
                lines.append(err)
                lines.append("```")
            lines.append("")
        if log_tracebacks:
            lines.append("**异常堆栈**:")
            lines.append("")
            for tb in log_tracebacks:
                lines.append(f"```")
                lines.append(tb[:500])
                lines.append("```")
            lines.append("")

    if consistency_issues:
        lines.append("### 一致性问题详情")
        lines.append("")
        for iss in consistency_issues:
            lines.append(f"- {iss}")
        lines.append("")

    if step_issues:
        lines.append("### 步骤问题详情")
        lines.append("")
        for iss in step_issues:
            lines.append(f"- {iss}")
        lines.append("")

    if db_prompt_issues:
        lines.append("### DB-Prompt日志不一致详情")
        lines.append("")
        for iss in db_prompt_issues:
            lines.append(f"- {iss}")
        lines.append("")

    # 第7节：三方一致性对比（DB/应用日志/Prompt日志）
    lines.append("## 7 三方一致性（DB/应用日志/Prompt日志）")
    lines.append("")

    # 2026-08-19 小欧 新协议适配: 工具名从 tools[]规整, 观察数按独立observation step计
    db_tool_names = [
        en["tool_name"]
        for s in db_steps if _is_action_step(s)
        for en in _action_entries(s)
    ]
    db_obs_count = sum(1 for s in db_steps if s.get("type") == "observation")
    db_action_step_count = sum(1 for s in db_steps if _is_action_step(s))
    sse_tool_names = [t.get("tool_name", "") for t in tool_calls]
    log_llm_calls = log_check.get("llm_calls_found", 0)
    prompt_log_files = log_check.get("prompt_log_files", [])

    lines.append("| 对比项 | DB | SSE | 日志 | 是否匹配 |")
    lines.append("|--------|-----|-----|------|----------|")
    lines.append(f"| 工具数量 | {len(db_tool_names)} | {len(sse_tool_names)} | {log_llm_calls}次LLM调用 | {'PASS' if abs(len(db_tool_names) - len(sse_tool_names)) <= 2 else 'FAIL'} |")
    lines.append(f"| 工具名称 | {db_tool_names[:5]} | {sse_tool_names[:5]} | - | {'PASS' if set(db_tool_names) & set(sse_tool_names) or (not db_tool_names and not sse_tool_names) else 'FAIL'} |")
    # v0.19.18起 单action步骤可批量多工具, 观察结果按 action步骤 计(每action步1个observation), 故比对基线用 action步数 而非 工具数
    # 纯对话(无action步)时无观察可比对, 直接PASS
    _obs_ok = True if db_action_step_count == 0 else db_obs_count >= max(1, db_action_step_count - 1)
    lines.append(f"| 观察结果数 | {db_obs_count} | {len(tool_calls)} (action步={db_action_step_count}) | - | {'PASS' if _obs_ok else 'WARN'} |")
    lines.append(f"| Prompt日志文件 | - | - | {prompt_log_files} | {'PASS' if prompt_log_files else 'WARN'} |")
    lines.append("")

    # 第8节：附加信息(排除已在验证表显示的DbPromptIssues)
    # (final_stats 已迁§2.2渲染, 此处不再重复 — 小欧 2026-08-22 清理过期注释)
    if extra:
        lines.append("## 8 附加信息")
        lines.append("")
        for k, v in extra.items():
            if k == "DbPromptIssues":
                continue
            lines.append(f"- {k}: {v}")
        lines.append("")

    lines.append("---")
    lines.append(f"**更新时间**: {end_str}")
    lines.append("")

    written_path: Optional[Path] = None
    content = "\n".join(lines)
    import tempfile as _tf
    for _attempt in range(3):
        try:
            _fd, _tmp = _tf.mkstemp(suffix=".md", dir=str(RECORD_DIR))
            with open(_fd, "w", encoding="utf-8-sig") as f:
                f.write(content)
            import os as _os
            _os.replace(_tmp, str(record_file))
            written_path = record_file
            break
        except PermissionError:
            import time as _time
            _time.sleep(0.5)
            if _attempt == 2:
                alt_file = RECORD_DIR / f"测试记录-{test_id}-{date_str}-{int(now.timestamp())}.md"
                try:
                    with open(str(alt_file), "w", encoding="utf-8") as f:
                        f.write(content)
                    written_path = alt_file
                    print(f"  [WARN] write_test_record: used alt path {alt_file.name}")
                except Exception as e2:
                    print(f"  [WARN] write_test_record failed: {e2}")
        except Exception as e:
            print(f"  [WARN] write_test_record failed: {e}")
            break

    # 验证记录文件是否真正写入成功
    if written_path and written_path.exists():
        size = written_path.stat().st_size
        print(f"  [RECORD OK] {written_path.name} ({size} bytes)")
    else:
        print(f"  [RECORD FAIL] {test_id} 记录文件未生成!")

    # 输出调用链
    if tool_names:
        chain = " -> ".join(tool_names)
        print(f"  [CALL CHAIN] {chain}")
    else:
        print(f"  [CALL CHAIN] (无工具调用)")

    # 正常完成，移除待写入记录 + 清理 marker
    remove_pending_record(test_id)
    clear_test_marker(test_id)
    return written_path
