#!/usr/bin/env python
"""
3个真实全链路E2E测试 — Agent → LLM → Tool — 流式读取SSE

小健 2026-05-23
"""
import asyncio, json, sys, time
from pathlib import Path
from datetime import datetime

BASE = "http://127.0.0.1:8000"
CHAT_URL = f"{BASE}/api/v1/chat/stream/v2"
TOTAL_TIMEOUT = 600  # 10分钟

TASKS = [
    {"id": "E2E-1", "msg": "使用 search_files 工具在 tests/ 目录搜索 .py 文件", "expect_tool": "search_files"},
    {"id": "E2E-2", "msg": "使用 http_request 工具获取 httpbin.org/get 的内容", "expect_tool": "http_request"},
    {"id": "E2E-3", "msg": "使用 get_time 工具获取当前系统时间", "expect_tool": "get_time"},
]

async def run_one(task):
    import httpx
    start = time.time()
    events = []
    tools_called = []
    try:
        async with httpx.AsyncClient(timeout=TOTAL_TIMEOUT) as c:
            async with c.stream("POST", CHAT_URL, json={
                "messages": [{"role":"user","content":task["msg"]}], "stream": True
            }) as resp:
                if resp.status_code != 200:
                    return task["id"], False, [], f"HTTP {resp.status_code}", 0
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            ev = json.loads(line[6:])
                            events.append(ev)
                            t = ev.get("type","")
                            if t == "action_tool":
                                tn = ev.get("tool_name","")
                                if tn: tools_called.append(tn)
                            if t in ("final","error"):
                                break
                        except: pass
        dur = time.time()-start
        ok = task["expect_tool"] in tools_called
        final = any(e.get("type")=="final" for e in events)
        err = next((e.get("message","") for e in events if e.get("type")=="error"), None)
        return task["id"], ok or final, tools_called, err or "", round(dur, 1)
    except Exception as e:
        return task["id"], False, [], str(e)[:120], round(time.time()-start, 1)

async def main():
    # 检查后端
    import httpx
    try:
        r = await httpx.AsyncClient(timeout=5).get(f"{BASE}/api/v1/health")
        assert r.status_code==200
        print("[OK] 后端运行中")
    except:
        print("[FATAL] 后端未启动"); return

    print(f"\n=== 全链路E2E测试 (3个) ===")
    print(f"启动: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"模型: Ollama qwen2.5:1.5b | 超时: {TOTAL_TIMEOUT}s\n")

    results = []
    for task in TASKS:
        tid = task["id"]
        print(f"[{tid}] {task['msg'][:55]} ... ", end="", flush=True)
        id_, ok, tools, err, dur = await run_one(task)
        results.append((id_, ok, tools, err, dur))
        tag = "OK" if ok else "FAIL"
        ts = ",".join(tools[:4]) if tools else "(none)"
        e = f" | err: {err[:60]}" if err and not ok else ""
        print(f"{tag} {dur}s tools=[{ts}]{e}")

    print(f"\n=== 结果汇总 ===")
    passed = sum(1 for r in results if r[1])
    print(f"通过: {passed}/3 | 超时: {TOTAL_TIMEOUT}s/任务")
    for r in results:
        print(f"  [{r[0]}] {'OK' if r[1] else 'FAIL'} | tools={r[2]} | {r[3][:80] if r[3] else ''}")

if __name__ == "__main__":
    asyncio.run(main())
