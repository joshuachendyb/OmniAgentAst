"""
测试服务器完整请求流程 — 捕获所有输出
小沈 2026-05-21
"""
import subprocess, sys, time, json, httpx, os

backend_dir = r"G:\OmniAgentAs-desk\backend"
os.environ["OLLAMA_MODELS"] = r"E:\ollama\models"

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8001", "--log-level", "debug"],
    cwd=backend_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1
)

time.sleep(8)
if proc.poll() is not None:
    print(f"CRASHED on startup, code={proc.returncode}")
    out, err = proc.communicate(timeout=5)
    print("STDERR:", err[-3000:])
    sys.exit(1)

print(f"Server started, PID={proc.pid}")

# Send simple request
payload = {"messages": [{"role": "user", "content": "hello"}], "stream": True}
try:
    with httpx.Client(timeout=120) as client:
        with client.stream("POST", "http://127.0.0.1:8001/api/v1/chat/stream/v2", json=payload) as resp:
            print(f"HTTP: {resp.status_code}")
            for line in resp.iter_lines():
                if line.strip():
                    if line.startswith("data: "):
                        try:
                            ev = json.loads(line[6:])
                            print(f"  [{ev['type']}] step={ev.get('step')} content={str(ev.get('content',''))[:80]}")
                        except: pass
                    else:
                        if "error" in line.lower() or "traceback" in line.lower():
                            print(f"  RAW: {line[:200]}")
except Exception as e:
    print(f"HTTP error: {type(e).__name__}: {e}")

time.sleep(2)
if proc.poll() is not None:
    print(f"\nSERVER CRASHED after request, code={proc.returncode}")
    out, err = proc.communicate(timeout=5)
    print("=== STDERR ===")
    print(err[-5000:])
else:
    print("\nServer alive after request")
    proc.terminate()
    time.sleep(1)
    out, err = proc.communicate(timeout=5)
    if err:
        print("=== STDERR ===")
        print(err[-2000:])
