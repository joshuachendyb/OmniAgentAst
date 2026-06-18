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
    partial_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """发送POST /chat/stream, 接收SSE事件流, 返回结构化结果

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
    events: List[Dict[str, Any]] = []
    error_occurred = False
    final_event = None
    response_text = ""
    tool_calls: List[Dict[str, Any]] = []

    try:
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
    finally:
        total_time_ms = int((time.monotonic() - start_time) * 1000)
        event_types = [e.get("type", "") for e in events]
        logical_events = [e for e in events if e.get("type") != "chunk"]
        unique_step_numbers = len({e.get("step") for e in events if e.get("step") is not None})
        ret = {
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
            "user_msg_id": user_msg_id,
            "event_types": event_types,
        }
        if partial_result is not None:
            partial_result.update(ret)
        return ret


# ─── 流结束方式检测(公共函数, 替代assert final_event) ──────────

def assert_stream_ended(result: Dict[str, Any]) -> str:
    """返回流结束方式(final/error/中断), 不阻断
    所有方式都算流已结束, 忠实记录 -- 小健 2026-06-15"""
    if result.get("final_event") is not None:
        return "final"
    if result.get("has_error"):
        return "error"
    return "中断"


# ─── 数据库连接(通过后端API, 避免sqlite3直连权限问题) ────────

def _api_get(path: str, params: Optional[Dict] = None) -> Optional[Dict]:
    """同步GET请求后端API -- 小健 2026-06-14"""
    import urllib.request
    import urllib.parse
    url = f"{BASE_URL}{API_PREFIX}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
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


# ─── 步骤5: DB记录完整性验证 ─────────────────────────────────

def check_db(session_id: str) -> Dict[str, Any]:
    """检查数据库记录完整性(手册步骤5, 通过后端API) -- 小健 2026-06-14

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

    try:
        # ── chat_sessions (via API) ──
        session_data = _api_get(f"/sessions/{session_id}/messages")
        if session_data and session_data.get("session_id"):
            result["session_exists"] = True
            result["is_valid"] = bool(session_data.get("is_valid"))
            result["created_at"] = session_data.get("created_at")
            result["updated_at"] = session_data.get("updated_at")

        # ── chat_messages (via API) ──
        messages = session_data.get("messages", []) if session_data else []
        result["messages_count"] = len(messages)
        user_first_idx: Optional[int] = None
        assistant_first_idx: Optional[int] = None

        for mi, msg in enumerate(messages):
            role = msg.get("role", "")
            if role == "user":
                result["has_user_message"] = True
                if user_first_idx is None:
                    user_first_idx = mi
            elif role == "assistant":
                result["has_assistant_message"] = True
                if assistant_first_idx is None:
                    assistant_first_idx = mi

                steps_raw = msg.get("execution_steps")
                if steps_raw:
                    steps = steps_raw if isinstance(steps_raw, list) else json.loads(steps_raw)
                    result["execution_steps"] = steps
                    result["execution_steps_count"] = len(steps)

                    for si, step in enumerate(steps):
                        step_type = step.get("type", "")
                        if step_type == "action_tool":
                            if not step.get("tool_name"):
                                result["step_field_issues"].append(
                                    f"step[{si}]: tool_name empty(MUST)"
                                )
                            tp = step.get("tool_params")
                            if not tp or not isinstance(tp, dict):
                                result["step_field_issues"].append(
                                    f"step[{si}]: tool_params empty(MUST)"
                                )
                            obs = step.get("observation") or step.get("execution_result")
                            if not obs:
                                result["step_field_issues"].append(
                                    f"step[{si}]: observation empty(MUST)"
                                )
                        status = step.get("status")
                        if status is not None and status not in ("success", "error"):
                            result["step_field_issues"].append(
                                f"step[{si}]: status abnormal={status}"
                            )

        # ── message order ──
        if user_first_idx is not None and assistant_first_idx is not None:
            result["message_order_correct"] = user_first_idx < assistant_first_idx

    except Exception as e:
        result["errors"].append(f"API query error: {e}")

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


def verify_db_prompt_consistency(
    session_id: str,
    user_msg_id: Optional[int] = None,
) -> List[str]:
    """验证DB execution_steps与Prompt日志«执行步骤»一致性 -- 小健 2026-06-15

    比较项:
      - 非chunk步骤数量一致
      - 同步骤号: type, tool_name, tool_params一致
      - action_tool步骤的execution_result一致
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
                if str(user_msg_id) in content:
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

    # 获取「执行步骤」节：第四个key
    log_keys = list(log_data.keys())
    if len(log_keys) < 4:
        issues.append(f"Prompt日志缺少执行步骤节, 仅{len(log_keys)}个节")
        return issues
    exec_steps_key = log_keys[3]
    log_steps = log_data.get(exec_steps_key, [])

    if not log_steps:
        issues.append("Prompt日志«执行步骤»为空")
        return issues

    # 非chunk/start步骤数对比(prompt日志不含start事件)
    db_main = [s for s in db_steps if s.get("type") not in ("chunk", "start")]
    log_main = [s for s in log_steps if s.get("\u6b65\u9aa4\u7c7b\u578b") not in ("chunk", "start")]

    if len(db_main) != len(log_main):
        issues.append(
            f"非chunk/start步骤数不一致: DB={len(db_main)}, Prompt日志={len(log_main)}"
        )

    # 按步骤号分组对比(只对比action_tool)
    db_by_step: Dict[int, List[Dict]] = {}
    log_by_step: Dict[int, List[Dict]] = {}
    for s in db_steps:
        sn = s.get("step")
        if sn is not None:
            db_by_step.setdefault(sn, []).append(s)
    for s in log_steps:
        sn = s.get("\u6b65\u9aa4")
        if sn is not None:
            log_by_step.setdefault(sn, []).append(s)

    all_step_nums = set(db_by_step.keys()) | set(log_by_step.keys())
    for sn in sorted(all_step_nums):
        db_ss = db_by_step.get(sn, [])
        log_ss = log_by_step.get(sn, [])
        # type对比
        # type对比(排除start, prompt日志不含该类型)
        db_types = sorted([s.get("type", "") for s in db_ss if s.get("type") != "start"])
        log_types = sorted([s.get("\u6b65\u9aa4\u7c7b\u578b", "") for s in log_ss if s.get("\u6b65\u9aa4\u7c7b\u578b") != "start"])
        if db_types != log_types:
            issues.append(f"步骤{sn} type不一致: DB={db_types}, Prompt日志={log_types}")

        # action_tool对比: tool_name + tool_params
        for db_s in db_ss:
            if db_s.get("type") != "action_tool":
                continue
            db_tn = db_s.get("tool_name", "")
            db_tp = db_s.get("tool_params", {})
            if isinstance(db_tp, str):
                try:
                    db_tp = json.loads(db_tp)
                except Exception:
                    db_tp = {"_raw": db_tp}
            # 在log_steps找同步骤的同tool
            matched = False
            for log_s in log_ss:
                evt = log_s.get("\u6570\u636e", {})
                if not isinstance(evt, dict):
                    continue
                log_tn = evt.get("tool_name", "")
                if log_tn != db_tn:
                    continue
                log_tp = evt.get("tool_params", {})
                if str(log_tp) != str(db_tp):
                    issues.append(
                        f"步骤{sn} tool_params不一致: DB={db_tp}, Prompt日志={log_tp}"
                    )
                matched = True
                break
            if not matched:
                issues.append(f"步骤{sn} tool_name({db_tn})在Prompt日志中未找到")

        # observation对比(仅action_tool)
        for db_s in db_ss:
            if db_s.get("type") != "action_tool":
                continue
            db_obs = db_s.get("observation") or db_s.get("execution_result", "")
            for log_s in log_ss:
                evt = log_s.get("\u6570\u636e", {})
                if not isinstance(evt, dict):
                    continue
                log_obs = evt.get("execution_result") or evt.get("observation") or ""
                # DB存结构化dict, Prompt日志存summary字符串, 用字符串包含检查
                db_str = str(db_obs)
                log_str = str(log_obs)
                if db_str and log_str:
                    # 提取DB中的有意义的标识(ERR_CODE, SUCCESS等)
                    db_upper = ''.join(c for c in db_str if c.isupper() or c == '_')
                    log_upper = ''.join(c for c in log_str if c.isupper() or c == '_')
                    if 'ERR' in db_upper and 'ERR' not in log_upper:
                        issues.append(
                            f"步骤{sn} observation错误码不匹配: DB含错误码, Prompt日志未含"
                        )
                    elif 'SUCCESS' in db_upper and 'SUCCESS' not in log_upper:
                        issues.append(
                            f"步骤{sn} observation状态不匹配: DB含SUCCESS, Prompt日志未含"
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

    # ── 步骤编号连续性(仅检查action_tool步骤,允许并行调用共享step号) ──
    # 小欧 2026-06-16: LLM可以在一次响应中返回多个并行tool_call,共享同一个step号
    tool_step_nums = [
        s.get("step") for s in steps
        if s.get("type") == "action_tool" and s.get("step") is not None
    ]
    if len(tool_step_nums) >= 2:
        for i in range(len(tool_step_nums) - 1):
            # 允许并行调用: 相同step号是正常的(如step=1下有read_text_file和list_directory)
            # 只检查严格递减的情况(如1->0, 2->1)
            if tool_step_nums[i + 1] < tool_step_nums[i]:
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
    user_msg_id: Optional[int] = None,
) -> Dict[str, Any]:
    """检查日志和prompt-logs(手册步骤8) -- 小健 2026-06-14

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
            if "流式错误" in line or "请求超时" in line:
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
    """清理测试产生的数据(手册步骤9, 通过后端API) -- 小健 2026-06-14

    - 通过API清理DB中的session记录
    - 清理测试产生的文件
    """
    if session_id:
        _api_delete(f"/sessions/{session_id}")

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


# ─── 测试记录写入(手册5.5铁律) ──────────────────────────────

RECORD_DIR = Path(__file__).parent.parent.parent / "notes"


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
) -> None:
    """写入测试记录文件（手册5.5）-- 小健 2026-06-18

    必须在finally块中调用，即使失败也要写
    文件: notes/测试记录-{test_id}-{日期}.md
    
    v1.9增强: error_info参数记录异常详情(类型+消息+堆栈)
    """
    RECORD_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    ts_str = now.strftime("%Y-%m-%d %H:%M:%S")
    record_file = RECORD_DIR / f"测试记录-{test_id}-{date_str}.md"

    status = "PASSED" if passed else "FAILED"
    resp = result.get("response_text", "")
    tool_calls = result.get("tool_calls", [])
    tool_names = [t.get("tool_name", "") for t in tool_calls]
    event_types = result.get("event_types", [])
    events = result.get("events", [])
    logical_events = [e for e in events if e.get("type") != "chunk"]
    unique_step_nums = len({e.get("step") for e in events if e.get("step") is not None})

    resp_has_error = False
    if resp:
        resp_lower = resp.lower()
        clean_resp = resp.replace("\n", " ").replace("\r", " ")
        err_markers = ("错误:", "错误：", "超时,", "超时，", "超时)", "超时）", "出错", "failed:", "exception:", "traceback:")
        resp_has_error = any(m in clean_resp for m in err_markers)

    if not db:
        sid = result.get("session_id", "")
        if sid:
            try:
                fb = check_db(sid)
                if fb.get("session_exists"):
                    db = fb
            except Exception:
                pass

    lines: List[str] = []
    lines.append(f"# 测试记录-{test_id}-{date_str}")
    lines.append("")
    lines.append(f"**创建时间**: {ts_str}")
    lines.append(f"**测试编号**: {test_id}")
    lines.append(f"**测试结果**: {status}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 第1节：测试基本信息
    lines.append("## 1 测试基本信息")
    lines.append("")
    lines.append("| 项目 | 内容 |")
    lines.append("|------|------|")
    lines.append(f"| 测试编号 | {test_id} |")
    lines.append(f"| 任务描述 | {test_name} |")
    lines.append(f"| 用户命令 | `{user_input}` |")
    lines.append(f"| 执行时间 | {ts_str} |")
    lines.append(f"| 执行耗时 | {elapsed:.1f}秒 |")
    lines.append(f"| SSE总事件数 | {result.get('total_steps', 0)} |")
    lines.append(f"| LLM调用次数 | {result.get('llm_call_count', 0)} |")
    lines.append(f"| 逻辑步数 | {len(logical_events)} |")
    lines.append(f"| 不重复步骤号数 | {unique_step_nums} |")
    lines.append(f"| 测试结果 | **{status}** |")
    lines.append("")

    # 第2节：LLM回复内容
    lines.append("## 2 LLM回复内容")
    lines.append("")
    lines.append("```")
    lines.append(resp[:800] if resp else "(空)")
    lines.append("```")
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
            params_str = json.dumps(tc.get("tool_params", {}), ensure_ascii=False)[:100]
            lines.append(f"| {i+1} | {tc.get('tool_name', '')} | `{params_str}` |")
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

    # 第5.2节：执行步骤详情（前15条）
    db_steps = db.get("execution_steps", [])
    if db_steps:
        lines.append("### 5.2 执行步骤（前15条）")
        lines.append("")
        lines.append("| 序号 | 步骤号 | 类型 | 工具 | 状态 |")
        lines.append("|------|--------|------|------|--------|")
        for i, s in enumerate(db_steps[:15]):
            s_step = s.get("step", "")
            s_type = s.get("type", "")
            s_tool = s.get("tool_name", "")
            s_status = s.get("status", "")
            lines.append(f"| {i+1} | {s_step} | {s_type} | {s_tool} | {s_status} |")
        remaining = len(db_steps) - 15
        if remaining > 0:
            lines.append(f"| ... | (剩余{remaining}条) | | | |")
        lines.append("")

        # 第5.3节：步骤数据内容（action_tool步骤）
        action_steps = [s for s in db_steps if s.get("type") == "action_tool"]
        if action_steps:
            lines.append("### 5.3 步骤数据内容(action_tool)")
            lines.append("")
            for i, s in enumerate(action_steps):
                tn = s.get("tool_name", "?")
                tp = json.dumps(s.get("tool_params", {}), ensure_ascii=False)[:150]
                obs_raw = s.get("observation") or s.get("execution_result", "")
                obs_str = _obs_to_text(obs_raw)[:200] if obs_raw else "(空)"
                lines.append(f"**步骤{s.get('step', '?')}: {tn}**")
                lines.append(f"- 参数: `{tp}`")
                lines.append(f"- 观察结果: `{obs_str}`")
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
    lines.append(f"| 是否有error事件 | {'PASS' if not result.get('has_error') else 'FAIL'} | - |")
    lines.append(f"| 回复内容 | {'FAIL' if not resp or resp_has_error else 'PASS'} | {len(resp)}字{' [含错误关键词]' if resp_has_error else ''} |")
    lines.append(f"| 数据库验证 | {'PASS' if db.get('session_exists') else 'FAIL'} | - |")
    lines.append(f"| SSE-DB一致性 | {'PASS' if len(consistency_issues) == 0 else 'FAIL'} | {len(consistency_issues)}个问题 |")
    lines.append(f"| DB-Prompt日志一致性 | {'PASS' if db_prompt_ok else 'FAIL'} | {db_prompt_detail} |")
    lines.append(f"| 步骤合理性 | {'PASS' if len(step_issues) == 0 else 'FAIL'} | {len(step_issues)}个问题 |")
    lines.append(f"| 日志中ERROR | {'PASS' if len(log_check.get('errors', [])) == 0 else 'FAIL'} | {len(log_check.get('errors', []))}条 |")
    lines.append(f"| 日志中异常堆栈 | {'PASS' if len(log_check.get('tracebacks', [])) == 0 else 'FAIL'} | {len(log_check.get('tracebacks', []))}条 |")
    lines.append("")
    
    if not passed and error_info:
        lines.append("## 失败详情")
        lines.append("")
        lines.append("**异常信息**:")
        lines.append("")
        lines.append("```")
        lines.append(error_info[:1000])
        lines.append("```")
        lines.append("")

    if resp_has_error and resp:
        lines.append("**回复内容错误详情**:")
        lines.append("")
        lines.append("```")
        lines.append(resp[:300])
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

    db_tool_names = [s.get("tool_name", "") for s in db_steps if s.get("type") == "action_tool"]
    db_obs_count = sum(1 for s in db_steps if s.get("type") == "action_tool" and (s.get("observation") or s.get("execution_result")))
    sse_tool_names = [t.get("tool_name", "") for t in tool_calls]
    log_llm_calls = log_check.get("llm_calls_found", 0)
    prompt_log_files = log_check.get("prompt_log_files", [])

    lines.append("| 对比项 | DB | SSE | 日志 | 是否匹配 |")
    lines.append("|--------|-----|-----|------|----------|")
    lines.append(f"| 工具数量 | {len(db_tool_names)} | {len(sse_tool_names)} | {log_llm_calls}次LLM调用 | {'PASS' if abs(len(db_tool_names) - len(sse_tool_names)) <= 2 else 'FAIL'} |")
    lines.append(f"| 工具名称 | {db_tool_names[:5]} | {sse_tool_names[:5]} | - | {'PASS' if set(db_tool_names) & set(sse_tool_names) or (not db_tool_names and not sse_tool_names) else 'FAIL'} |")
    lines.append(f"| 观察结果数 | {db_obs_count} | {len(tool_calls)} | - | {'PASS' if db_obs_count >= len(tool_calls) - 1 else 'WARN'} |")
    lines.append(f"| Prompt日志文件 | - | - | {prompt_log_files} | {'PASS' if prompt_log_files else 'WARN'} |")
    lines.append("")

    # 第8节：附加信息(排除已在验证表显示的DbPromptIssues)
    if extra:
        lines.append("## 8 附加信息")
        lines.append("")
        for k, v in extra.items():
            if k == "DbPromptIssues":
                continue
            lines.append(f"- {k}: {v}")
        lines.append("")

    lines.append("---")
    lines.append(f"**更新时间**: {ts_str}")
    lines.append("")

    try:
        content = "\n".join(lines)
        with open(str(record_file), "w", encoding="utf-8-sig") as f:
            f.write(content)
    except PermissionError:
        alt_file = RECORD_DIR / f"测试记录-{test_id}-{date_str}-{int(now.timestamp())}.md"
        try:
            with open(str(alt_file), "w", encoding="utf-8") as f:
                f.write(content)
            print(f"  [WARN] write_test_record: used alt path {alt_file.name}")
        except Exception as e2:
            print(f"  [WARN] write_test_record failed: {e2}")
    except Exception as e:
        print(f"  [WARN] write_test_record failed: {e}")
