#!/usr/bin/env python
"""跑一个任务，全量输出所有SSE事件到JSON文件，然后分析"""
import asyncio, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = "http://127.0.0.1:8000"
CHAT_URL = f"{BASE}/api/v1/chat/stream/v2"
OUT_DIR = Path(__file__).parent / "reports"
OUT_DIR.mkdir(exist_ok=True)

async def run(msg):
    import httpx
    task_name = msg[:30].replace("/", "_").replace(" ", "_")
    out_file = OUT_DIR / f"e2e_{task_name}.json"
    
    start = time.time()
    events = []
    
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] 发送: {msg[:60]}")
    
    async with httpx.AsyncClient(timeout=900) as c:
        async with c.stream("POST", CHAT_URL, json={
            "messages": [{"role":"user","content":msg}], "stream": True
        }) as resp:
            ts = time.strftime("%H:%M:%S")
            print(f"[{ts}] HTTP {resp.status_code}")
            if resp.status_code != 200:
                return
            
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    try:
                        ev = json.loads(line[6:])
                        events.append(ev)
                        t = ev.get("type","")
                        if t == "action_tool":
                            print(f"[{time.strftime('%H:%M:%S')}] TOOL: {ev.get('tool_name','')} step={ev.get('step','')}")
                        elif t == "final":
                            content = ev.get("content","") or ev.get("message","") or ""
                            print(f"[{time.strftime('%H:%M:%S')}] FINAL: {str(content)[:150]}")
                        elif t == "error":
                            print(f"[{time.strftime('%H:%M:%S')}] ERROR: {ev.get('message','')}")
                        elif t in ("thought","text"):
                            pass
                        elif t == "start":
                            print(f"[{time.strftime('%H:%M:%S')}] START")
                    except: pass

    dur = time.time() - start
    ts2 = time.strftime("%H:%M:%S")
    
    # 写文件
    out_file.write_text(json.dumps(events, ensure_ascii=False, indent=2))
    
    print(f"[{ts2}] ===== 完成 ===== ")
    print(f"  耗时: {dur:.0f}s")
    print(f"  事件总数: {len(events)}")
    
    # 分析事件类型分布
    types = {}
    for ev in events:
        t = ev.get("type","?")
        types.setdefault(t, 0)
        types[t] += 1
    print(f"  事件类型: {json.dumps(types)}")
    
    # 工具调用统计
    tools = [ev for ev in events if ev.get("type")=="action_tool"]
    print(f"  工具调用: {len(tools)} 次")
    for ev in tools:
        print(f"    tool={ev.get('tool_name','')} step={ev.get('step','')}")
        params = ev.get("parameters","") or ev.get("params","") or ""
        if params:
            print(f"      params: {str(params)[:200]}")
    
    # 最终回复
    finals = [ev for ev in events if ev.get("type")=="final"]
    if finals:
        c = finals[0].get("content","") or ""
        print(f"  最终回复({len(c)}字符): {c[:300]}")
    
    errors = [ev for ev in events if ev.get("type")=="error"]
    if errors:
        print(f"  错误: {errors[0].get('message','')}")
    
    print(f"  完整事件已保存: {out_file}")

if __name__ == "__main__":
    msg = sys.argv[1] if len(sys.argv) > 1 else "读取 tests/temp_runtime_test/test_direct.txt 文件的内容"
    asyncio.run(run(msg))
