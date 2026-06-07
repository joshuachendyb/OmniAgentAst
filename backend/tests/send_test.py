"""
Send a test request via SSE and process events as they arrive
"""
import httpx, json, sys, os, time

os.environ["OLLAMA_MODELS"] = r"E:\ollama\models"
payload = {"messages": [{"role": "user", "content": "hello"}], "stream": True}

def parse_sse(line):
    if line.startswith("data: "):
        try: return json.loads(line[6:])
        except: return None
    return None

try:
    with httpx.Client(timeout=300) as client:
        start = time.time()
        with client.stream("POST", "http://127.0.0.1:8001/api/v1/chat/stream/v2", json=payload) as resp:
            print(f"HTTP_STATUS:{resp.status_code}")
            if resp.status_code != 200:
                print(f"BODY:{resp.text[:2000]}")
                sys.exit(1)
            event_count = 0
            for line in resp.iter_lines():
                if line.strip():
                    ev = parse_sse(line)
                    if ev:
                        event_count += 1
                        t = ev["type"]
                        msg = ev.get("error_message", "") or ev.get("content", "") or ""
                        if event_count <= 10 or t in ("error", "final"):
                            print(f"[{t}] {msg[:120]}")
                        if t == "error":
                            print(f"  ERROR_DETAIL: {json.dumps(ev, ensure_ascii=False)[:300]}")
                        if t == "final":
                            break
            elapsed = time.time() - start
            print(f"\nDONE: {event_count} events in {elapsed:.1f}s")
except Exception as e:
    print(f"EXCEPTION:{type(e).__name__}:{e}")
    import traceback
    traceback.print_exc()
