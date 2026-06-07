"""
启动服务器并捕获全部输出
"""
import subprocess, sys, time, json, httpx, os, threading

os.environ["OLLAMA_MODELS"] = r"E:\ollama\models"
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8001"],
    cwd=r"G:\OmniAgentAs-desk\backend",
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
)

output_lines = []

def gather(stream, label):
    for line in iter(stream.readline, ''):
        if line:
            output_lines.append(f"[{label}] {line.rstrip()}")

t1 = threading.Thread(target=gather, args=(proc.stdout, "OUT"), daemon=True)
t2 = threading.Thread(target=gather, args=(proc.stderr, "ERR"), daemon=True)
t1.start()
t2.start()

time.sleep(10)

# Check server health
try:
    r = httpx.get("http://127.0.0.1:8001/docs", timeout=5)
    print(f"SERVER_ALIVE:{r.status_code}")
except Exception as e:
    print(f"SERVER_DEAD:{e}")
    for l in output_lines[-50:]:
        print(l)
    proc.kill()
    sys.exit(1)

# Send request
payload = {"messages": [{"role": "user", "content": "hello"}], "stream": True}
try:
    with httpx.Client(timeout=180) as client:
        with client.stream("POST", "http://127.0.0.1:8001/api/v1/chat/stream/v2", json=payload) as resp:
            print(f"HTTP_STATUS:{resp.status_code}")
            if resp.status_code != 200:
                print(f"BODY:{resp.text[:2000]}")
            else:
                for line in resp.iter_lines():
                    if line.strip() and line.startswith("data: "):
                        try:
                            ev = json.loads(line[6:])
                            print(f"EVENT:{ev['type']}|step={ev.get('step')}|err={ev.get('error_message','')[:100]}")
                        except: pass
except Exception as e:
    print(f"HTTP_ERROR:{type(e).__name__}:{e}")

time.sleep(2)
if proc.poll() is not None:
    print(f"SERVER_CRASHED code={proc.returncode}")
else:
    print("SERVER_OK")
    proc.kill()

# Print server output
print("=== SERVER LOGS ===")
for l in output_lines[-100:]:
    print(l)
