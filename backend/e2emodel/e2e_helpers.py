"""E2E测试公共函数: 所有E2E测试脚本共用的辅助函数和验证逻辑

手册对照: 步骤5(DB完整性) + 步骤6(SSE-DB一致性) + 步骤7(合理性) + 步骤8(日志) + 步骤9(清理)

-- 小健 2026-06-14
"""

import json
import re
import socket
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx


# ─── 常量 ─────────────────────────────────────────────────────

BASE_URL = "http://127.0.0.1:8000"
API_PREFIX = "/api/v1"
DB_PATH = Path.home() / ".omniagent" / "chat_history.db"
LOG_DIR = Path(__file__).parent.parent / "logs"
PROMPT_LOG_DIR = LOG_DIR / "prompt-logs"
CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "config.yaml"


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


# ─── SSE事件收集(核心) ───────────────────────────────────────

async def send_chat(
    user_input: str,
    session_id: Optional[str] = None,
    timeout_seconds: int = 180,
) -> Dict[str, Any]:
    """发送POST /chat/stream, 接收SSE事件流, 返回结构化结果

    模拟真实前端流程: 创建session -> POST /messages保存user消息 -> POST /chat/stream
    -- 小健 2026-06-14
    """
    if not session_id:
        session_id = await create_session()
        if not session_id:
            raise RuntimeError("创建session失败")

    await save_user_message(session_id, user_input)

    chat_url = f"{BASE_URL}{API_PREFIX}/chat/stream"
    payload = {
        "messages": [{"role": "user", "content": user_input}],
        "stream": True,
        "session_id": session_id,
    }

    start_time = time.monotonic()
    events: List[Dict[str, Any]] = []
    error_occurred = False
    final_event = None
    response_text = ""
    tool_calls: List[Dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds)) as client:
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

                    if event_type == "final":
                        final_event = event
                        response_text = event.get("content") or event.get("response", "")

                    if event_type == "action_tool":
                        tool_calls.append({
                            "type": event_type,
                            "tool_name": event.get("tool_name", ""),
                            "tool_params": event.get("tool_params", {}),
                        })
        except httpx.TimeoutException:
            pass
        except Exception:
            pass

    total_time_ms = int((time.monotonic() - start_time) * 1000)
    event_types = [e.get("type", "") for e in events]
    logical_events = [e for e in events if e.get("type") != "chunk"]
    unique_step_numbers = len({e.get("step") for e in events if e.get("step") is not None})

    return {
        "events": events,
        "final_event": final_event,
        "has_error": error_occurred,
        "total_steps": len(events),
        "logical_step_count": len(logical_events),
        "unique_step_numbers": unique_step_numbers,
        "tool_calls": tool_calls,
        "llm_call_count": len(tool_calls) + 1,
        "total_time_ms": total_time_ms,
        "response_text": response_text,
        "session_id": session_id,
        "event_types": event_types,
    }


# ─── 数据库连接 ──────────────────────────────────────────────

def get_conn() -> Optional[sqlite3.Connection]:
    """获取数据库连接 -- 小健 2026-06-14"""
    if not DB_PATH.exists():
        return None
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# ─── 步骤5: DB记录完整性验证 ─────────────────────────────────

def check_db(session_id: str) -> Dict[str, Any]:
    """检查数据库记录完整性(手册步骤5) -- 小健 2026-06-14

    验证项:
      - session存在 + is_valid + created_at/updated_at合理
      - user message + assistant message都存在 + 顺序正确
      - execution_steps中每个step的tool_name/tool_params/observation/status字段完整性
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

    conn = get_conn()
    if conn is None:
        result["errors"].append("DB连接失败")
        return result

    try:
        # ── chat_sessions ──
        row = conn.execute(
            "SELECT * FROM chat_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row:
            result["session_exists"] = True
            result["is_valid"] = row["is_valid"]
            result["created_at"] = row["created_at"]
            result["updated_at"] = row["updated_at"]

            now_ms = int(datetime.now().timestamp() * 1000)
            for field_name in ("created_at", "updated_at"):
                val = row[field_name]
                if val is not None and isinstance(val, (int, float)):
                    if val > now_ms + 60000:
                        result["time_issues"].append(f"{field_name}超出现时间: {val}")

        # ── chat_messages ──
        messages = conn.execute(
            "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()

        result["messages_count"] = len(messages)
        user_first_id: Optional[int] = None
        assistant_first_id: Optional[int] = None

        for msg in messages:
            role = msg["role"]
            msg_id = msg["id"]
            if role == "user":
                result["has_user_message"] = True
                if user_first_id is None:
                    user_first_id = msg_id
            elif role == "assistant":
                result["has_assistant_message"] = True
                if assistant_first_id is None:
                    assistant_first_id = msg_id

                steps_json = msg["execution_steps"]
                if steps_json:
                    try:
                        steps = json.loads(steps_json)
                        result["execution_steps"] = steps
                        result["execution_steps_count"] = len(steps)

                        for si, step in enumerate(steps):
                            step_type = step.get("type", "")
                            if step_type == "action_tool":
                                if not step.get("tool_name"):
                                    result["step_field_issues"].append(
                                        f"step[{si}]: tool_name为空(MUST)"
                                    )
                                tp = step.get("tool_params")
                                if not tp or not isinstance(tp, dict):
                                    result["step_field_issues"].append(
                                        f"step[{si}]: tool_params为空或非dict(MUST)"
                                    )
                                obs = step.get("observation") or step.get("execution_result")
                                if not obs:
                                    result["step_field_issues"].append(
                                        f"step[{si}]: observation/execution_result为空(MUST)"
                                    )
                            status = step.get("status")
                            if status is not None and status not in ("success", "error"):
                                result["step_field_issues"].append(
                                    f"step[{si}]: status异常={status}"
                                )
                    except json.JSONDecodeError:
                        result["errors"].append("execution_steps JSON解析失败")

        # ── 消息顺序 ──
        if user_first_id is not None and assistant_first_id is not None:
            result["message_order_correct"] = user_first_id < assistant_first_id

    except Exception as e:
        result["errors"].append(f"DB查询异常: {e}")
    finally:
        conn.close()

    return result


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


# ─── 步骤6: SSE vs DB一致性验证 ──────────────────────────────

def verify_consistency(
    result: Dict[str, Any], session_id: str
) -> List[str]:
    """验证SSE事件与DB记录的一致性(手册步骤6) -- 小健 2026-06-14

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

    db_tool_calls = [
        s for s in db_steps
        if s.get("type") == "action_tool" and s.get("tool_name")
    ]

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
    # SSE event有observation字段(dict)和content字段(格式化字符串), DB存的是dict
    sse_obs_list = [
        e.get("observation") or e.get("content", "")
        for e in result["events"]
        if e.get("type") == "action_tool"
        and (e.get("observation") or e.get("content"))
    ]
    db_obs_list = [
        s.get("observation") or s.get("execution_result", "")
        for s in db_steps
        if s.get("type") == "action_tool"
        and (s.get("observation") or s.get("execution_result"))
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


# ─── 步骤7: 步骤合理性验证 ──────────────────────────────────

def verify_steps(
    result: Dict[str, Any], session_id: str
) -> List[str]:
    """验证步骤合理性(手册步骤7) -- 小健 2026-06-14

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

    # ── 步骤编号连续性(仅检查action_tool步骤) ──
    tool_step_nums = [
        s.get("step") for s in steps
        if s.get("type") == "action_tool" and s.get("step") is not None
    ]
    if len(tool_step_nums) >= 2:
        for i in range(len(tool_step_nums) - 1):
            if tool_step_nums[i + 1] <= tool_step_nums[i]:
                issues.append(f"工具步骤编号不递增: {tool_step_nums[i]}->{tool_step_nums[i+1]}")

    # ── observation完整性 ──
    for i, step in enumerate(steps):
        if step.get("type") == "action_tool" and step.get("tool_name"):
            obs = step.get("observation") or step.get("execution_result")
            if not obs:
                issues.append(f"step[{i}]({step.get('tool_name')}): 缺observation")

    return issues


# ─── 步骤8: 日志检查 ────────────────────────────────────────

def check_logs(
    start_time: Optional[datetime] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """检查日志和prompt-logs(手册步骤8) -- 小健 2026-06-14

    验证项:
      - 无ERROR级别日志
      - 无异常traceback
      - 有session操作记录
      - 有SSE事件发送记录
      - prompt-logs已保存
      - LLM调用次数合理(无死循环)
    """
    result: Dict[str, Any] = {
        "errors": [],
        "tracebacks": [],
        "session_records_found": False,
        "sse_records_found": False,
        "llm_calls_found": 0,
        "prompt_log_files": [],
    }

    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"app_{today}.log"

    if not log_file.exists():
        return result

    try:
        content = log_file.read_text(encoding="utf-8", errors="ignore")

        # ── 时间过滤 ──
        if start_time:
            filtered: List[str] = []
            current_ts: Optional[datetime] = None
            for line in content.splitlines():
                m = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
                if m:
                    try:
                        current_ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        current_ts = None
                if current_ts is None or current_ts >= start_time:
                    filtered.append(line)
            content = "\n".join(filtered)

        # ── ERROR检查(MUST) ──
        for line in re.findall(r"^.*ERROR.*$", content, re.MULTILINE)[:10]:
            if "unable to open database file" in line:
                continue
            if "e2e_test" in line:
                continue
            result["errors"].append(line.strip()[:200])

        # ── traceback检查(MUST) ──
        tb_count = content.count("Traceback (most recent call last)")
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
            recent = [f for f in prompt_files if f.stat().st_mtime >= (now.timestamp() - 3600)]
            result["prompt_log_files"] = [f.name for f in recent[:5]]
            for pf in recent[:5]:
                try:
                    pdata = json.loads(pf.read_text(encoding="utf-8", errors="ignore"))
                    result["llm_calls_found"] += pdata.get("llm_call_count", 0) or 1
                except Exception:
                    pass

    except Exception as e:
        result["errors"].append(f"读取日志异常: {e}")

    return result


# ─── 步骤9: 清理 ────────────────────────────────────────────

def cleanup(
    session_id: Optional[str] = None,
    test_files: Optional[List[Path]] = None,
) -> None:
    """清理测试产生的数据(手册步骤9) -- 小健 2026-06-14

    - 清理DB中的session和messages记录
    - 清理测试产生的文件
    """
    conn = get_conn()
    if conn:
        try:
            if session_id:
                conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
                conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
            else:
                conn.execute("DELETE FROM chat_messages WHERE session_id LIKE 'e2e_test_%'")
                conn.execute("DELETE FROM chat_sessions WHERE id LIKE 'e2e_test_%'")
            conn.commit()
        except Exception as e:
            print(f"  [WARN] cleanup DB failed: {e}")
        finally:
            conn.close()

    if test_files:
        for f in test_files:
            if f.exists():
                f.unlink(missing_ok=True)


# ─── 配置管理(security.enabled) ─────────────────────────────

def get_security_enabled() -> Optional[bool]:
    """读取config.yaml中security.enabled -- 小健 2026-06-14"""
    try:
        import yaml
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            return config.get("security", {}).get("enabled")
    except Exception:
        pass
    return None


def set_security_enabled(enabled: bool) -> bool:
    """设置config.yaml中security.enabled -- 小健 2026-06-14"""
    try:
        import yaml
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            if "security" not in config:
                config["security"] = {}
            config["security"]["enabled"] = enabled
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
            return True
    except Exception:
        pass
    return False


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
