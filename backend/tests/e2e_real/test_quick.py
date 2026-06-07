#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
E2E真实测试 — 完整模拟前端流程

前端真实流程：
  1. POST /api/v1/sessions → 创建session，拿到session_id
  2. POST /api/v1/sessions/{id}/messages → 保存用户消息
  3. POST /api/v1/chat/stream/v2 (带session_id) → SSE流式对话

之前的测试直接调chat/stream/v2不带session_id，导致message_saver 404错误。
现在完整模拟前端流程，杜绝任何非真实测试。

小健 2026-05-24
"""
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from e2e_real.error_collector import CompositeCollector, ErrorRecord
from e2e_real.bug_tracker import BugRegistry, BugVerifier, ReportGenerator, Severity

BASE_URL = "http://127.0.0.1:8000"
API_V1 = f"{BASE_URL}/api/v1"
HEALTH_URL = f"{API_V1}/health"
SESSIONS_URL = f"{API_V1}/sessions"
CHAT_URL = f"{API_V1}/chat/stream/v2"
REQUEST_TIMEOUT = 300


# ============================================================
# 前端流程模拟：创建session → 保存消息 → SSE对话
# ============================================================

async def frontend_create_session(title: str = "E2E测试会话") -> Optional[str]:
    """模拟前端：POST /api/v1/sessions 创建会话"""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            resp = await c.post(SESSIONS_URL, json={"title": title, "is_valid": True})
            if resp.status_code == 200:
                data = resp.json()
                session_id = data.get("session_id") or data.get("id")
                return session_id
            else:
                return None
    except Exception:
        return None


async def frontend_save_message(session_id: str, content: str) -> Optional[int]:
    """模拟前端：POST /api/v1/sessions/{id}/messages 保存用户消息"""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            resp = await c.post(
                f"{SESSIONS_URL}/{session_id}/messages",
                json={"role": "user", "content": content},
            )
            if resp.status_code == 200:
                return resp.json().get("message_id")
            else:
                return None
    except Exception:
        return None


async def frontend_chat_stream(
    msg: str,
    session_id: Optional[str] = None,
    timeout: int = REQUEST_TIMEOUT,
) -> Tuple[List[Dict], int, float, Optional[str]]:
    """模拟前端：POST /api/v1/chat/stream/v2 带session_id的SSE对话"""
    import httpx
    start = time.time()
    events = []
    body_json = {
        "messages": [{"role": "user", "content": msg}],
        "stream": True,
    }
    if session_id:
        body_json["session_id"] = session_id

    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            async with c.stream("POST", CHAT_URL, json=body_json) as resp:
                status_code = resp.status_code
                if status_code != 200:
                    body = await resp.aread()
                    return [], status_code, time.time() - start, body.decode("utf-8", errors="replace")[:300]
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            ev = json.loads(line[6:])
                            events.append(ev)
                        except json.JSONDecodeError:
                            pass
                        if events and events[-1].get("type") in ("final", "error"):
                            break
        return events, 200, time.time() - start, None
    except Exception as e:
        return events, 0, time.time() - start, f"{type(e).__name__}: {str(e)[:200]}"


async def frontend_full_flow(
    msg: str,
    timeout: int = REQUEST_TIMEOUT,
) -> Tuple[List[Dict], int, float, Optional[str], Optional[str]]:
    """
    完整前端流程：
    1. 创建session
    2. 保存用户消息
    3. SSE对话（带session_id）
    返回: (events, status_code, duration, error, session_id)
    """
    session_id = await frontend_create_session(title=f"E2E: {msg[:30]}")
    if session_id:
        await frontend_save_message(session_id, msg)

    events, status, dur, err = await frontend_chat_stream(msg, session_id=session_id, timeout=timeout)
    return events, status, dur, err, session_id


# ============================================================
# 深度SSE事件分析
# ============================================================

def deep_analyze(events: List[Dict], expect_tool: str = "") -> Dict[str, Any]:
    a = {
        "event_count": len(events),
        "types": [e.get("type", "") for e in events],
        "has_start": False, "has_final": False, "has_error": False,
        "has_thought": False, "has_action_tool": False, "has_observation": False,
        "tools_called": [], "final_response": "", "error_message": "",
        "step_count": 0, "consecutive_chunks": 0, "issues": [],
    }
    for ev in events:
        t = ev.get("type", "")
        if t == "start": a["has_start"] = True
        elif t == "final":
            a["has_final"] = True
            a["final_response"] = ev.get("response", "")[:500]
        elif t == "error":
            a["has_error"] = True
            a["error_message"] = ev.get("message", "")
        elif t == "thought":
            a["has_thought"] = True
            a["step_count"] += 1
        elif t == "action_tool":
            a["has_action_tool"] = True
            tn = ev.get("tool_name", "")
            if tn:
                a["tools_called"].append(tn)
            else:
                a["issues"].append("空工具名（BUG）")
            a["step_count"] += 1
        elif t == "observation":
            a["has_observation"] = True
            a["step_count"] += 1
        elif t == "chunk":
            a["consecutive_chunks"] += 1

    if not a["has_start"]:
        a["issues"].append("缺少start事件")
    if not a["has_final"] and not a["has_error"]:
        a["issues"].append("缺少final/error结束事件")
    if a["step_count"] == 0 and a["consecutive_chunks"] == 0:
        a["issues"].append("无任何中间步骤（thought/tool/observation）")
    if expect_tool and expect_tool not in a["tools_called"]:
        a["issues"].append(f"期望工具{expect_tool}未调用, 实际: {a['tools_called']}")
    error_kw = ["429", "500", "错误", "失败", "exception", "rate_limit"]
    if any(kw in a["final_response"].lower() for kw in error_kw):
        a["issues"].append("final含错误关键词")
    return a


# ============================================================
# 测试用例
# ============================================================

TESTS = [
    {"id": "T1", "desc": "简单对话-LLM连通性", "msg": "你好，请用一句话回复", "expect_tool": "", "timeout": 120},
    {"id": "T2", "desc": "文件工具-读取", "msg": "读取 G:/OmniAgentAs-desk/backend/pytest.ini 文件的内容", "expect_tool": "read_file", "timeout": 180},
    {"id": "T3", "desc": "系统工具-时间", "msg": "获取当前系统时间", "expect_tool": "get_time", "timeout": 120},
    {"id": "T4", "desc": "闲聊意图验证", "msg": "hello", "expect_tool": "", "timeout": 120},
]


# ============================================================
# 主测试流程
# ============================================================

async def main():
    start_time = datetime.now()
    registry = BugRegistry()
    collector = CompositeCollector()

    print(f"\n{'#'*60}")
    print(f"# E2E真实测试 (完整前端流程模拟)")
    print(f"# {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"# 零Mock — 完整模拟前端: createSession→saveMessage→SSE")
    print(f"{'#'*60}\n")

    # Phase 0: 环境预检
    import httpx
    try:
        r = await httpx.AsyncClient(timeout=5).get(HEALTH_URL)
        print(f"[OK] 后端: HTTP {r.status_code}")
    except Exception as e:
        print(f"[FATAL] 后端不可达: {e}")
        return

    # 检查当前provider
    try:
        r = await httpx.AsyncClient(timeout=5).get(f"{API_V1}/init-model/providers")
        print(f"[OK] 模型配置接口可用")
    except Exception:
        print(f"[INFO] 模型配置接口不可用(非致命)")

    # Phase 1: 前端流程模拟测试
    print(f"\n{'='*60}")
    print("Phase 1: 前端流程模拟测试")
    print(f"{'='*60}")

    results = {}
    for i, test in enumerate(TESTS, 1):
        tid = test["id"]
        print(f"\n[{i}/{len(TESTS)}] {tid}: {test['desc']}")
        print(f"  步骤1: 创建session...", end="", flush=True)

        session_id = await frontend_create_session(title=f"E2E: {test['msg'][:30]}")
        if session_id:
            print(f" OK (id={session_id[:8]}...)")
        else:
            print(f" FAIL (session创建失败，不带session_id继续)")

        if session_id:
            print(f"  步骤2: 保存用户消息...", end="", flush=True)
            msg_id = await frontend_save_message(session_id, test["msg"])
            print(f" {'OK id='+str(msg_id) if msg_id else 'FAIL(非致命)'}")

        print(f"  步骤3: SSE对话 (session_id={'有' if session_id else '无'})...", end="", flush=True)

        events, status, dur, err = await frontend_chat_stream(
            test["msg"], session_id=session_id, timeout=test["timeout"]
        )
        analysis = deep_analyze(events, expect_tool=test.get("expect_tool", ""))

        ok = analysis["has_start"] and (analysis["has_final"] or analysis["has_action_tool"]) and len(analysis["issues"]) == 0
        tools_str = ",".join(analysis["tools_called"][:3]) or "(none)"
        issues_str = "; ".join(analysis["issues"][:3]) if analysis["issues"] else ""
        print(f" {'OK' if ok else 'FAIL'} | {dur:.1f}s | types={analysis['types'][:6]} | tools=[{tools_str}]")
        if issues_str:
            print(f"  issues: {issues_str}")
        if analysis["final_response"]:
            print(f"  final: {analysis['final_response'][:120]}")

        if not ok:
            sev = Severity.CRITICAL if not analysis["has_final"] else Severity.HIGH
            bug = registry.add(
                title=f"{test['desc']}失败",
                severity=sev,
                description=f"issues: {issues_str}",
                discovered_by="e2e_real_frontend_flow",
                evidence=[f"events={analysis['types']}", f"tools={analysis['tools_called']}", f"issues={analysis['issues']}"],
            )
            print(f"  -> {bug.bug_id}")

        results[tid] = {
            "status": "OK" if ok else "FAIL",
            "dur": round(dur, 1),
            "session_id": session_id[:8] + "..." if session_id else None,
            "tools": analysis["tools_called"],
            "issues": analysis["issues"],
            "event_types": analysis["types"][:10],
        }

        await asyncio.sleep(2)

    # Phase 2: 错误收集与分析
    print(f"\n{'='*60}")
    print("Phase 2: 错误收集（app log分析）")
    print(f"{'='*60}")

    all_errors = collector.collect_flat(since=start_time)
    by_source = {}
    for e in all_errors:
        by_source[e.source] = by_source.get(e.source, 0) + 1
    print(f"  自{start_time.strftime('%H:%M:%S')}以来: {len(all_errors)}条")
    for src, cnt in sorted(by_source.items(), key=lambda x: -x[1]):
        print(f"    {src}: {cnt}条")
    if all_errors:
        print(f"\n  --- 最新5条 ---")
        for e in all_errors[:5]:
            print(f"    [{e.level}] {e.source}: {e.message[:80]}")

        critical_errors = [e for e in all_errors if e.level in ("ERROR", "CRITICAL")]
        if critical_errors:
            print(f"\n  发现{len(critical_errors)}条ERROR，注册为Bug")
            for ce in critical_errors[:3]:
                registry.add(
                    title=f"运行时错误: {ce.message[:60]}",
                    severity=Severity.HIGH,
                    description=ce.message,
                    discovered_by="error_collector",
                    evidence=[f"source={ce.source}, level={ce.level}"],
                    location=ce.file_path,
                )

    # Phase 3: 报告
    print(f"\n{'='*60}")
    reporter = ReportGenerator(registry)
    md_path = reporter.generate(test_results=results)
    summary = registry.summary()
    print(f"Bug: {summary['total']}个 | 确认: {summary['confirmed']} | 未修复: {summary['unfixed']}")
    print(f"报告: {md_path}")
    print(f"结束: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    asyncio.run(main())
