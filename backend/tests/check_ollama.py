"""检查 Ollama 状态 - 进程 + API + 真实推理"""
import httpx, json, time

# 1. 进程检查
import subprocess
r = subprocess.run(["powershell", "-Command", "Get-Process ollama* | Format-Table Id, ProcessName, StartTime -AutoSize"],
                   capture_output=True, text=True, timeout=15)
print("=== 1. Ollama 进程 ===")
print(r.stdout.strip() or "无 Ollama 进程")
print(r.stderr.strip() if r.stderr else "")

# 2. API 连接检查
print("\n=== 2. Ollama API ===")
try:
    r = httpx.get("http://127.0.0.1:11434/api/tags", timeout=10)
    print(f"HTTP {r.status_code}")
    data = r.json()
    models = data.get("models", [])
    print(f"模型数: {len(models)}")
    for m in models:
        d = m["details"]
        print(f"  - {m['name']}  ({d['parameter_size']}, {d['quantization_level']})")
except Exception as e:
    print(f"API连接失败: {e}")

# 3. 真实推理测试
print("\n=== 3. 真实推理测试 ===")
try:
    start = time.time()
    r = httpx.post("http://127.0.0.1:11434/api/generate", json={
        "model": "qwen2.5:1.5b",
        "prompt": "say hello",
        "stream": False,
        "options": {"num_predict": 10}
    }, timeout=120)
    dur = time.time() - start
    print(f"HTTP {r.status_code}, 耗时 {dur:.0f}s")
    if r.status_code == 200:
        data = r.json()
        resp = data.get("response", "")
        ec = data.get("eval_count", 0)
        ed = data.get("eval_duration", 0) // 10**9
        print(f"响应: '{resp[:100]}'")
        print(f"eval_count={ec}, eval_duration={ed}s")
        print(f"平均: {ec/max(ed,1):.1f} tokens/s")
except Exception as e:
    print(f"推理测试失败: {e}")

print("\n=== 完成 ===")
