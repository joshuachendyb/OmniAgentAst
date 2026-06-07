"""启动服务器→运行测试→关闭服务器"""
import subprocess
import sys
import time
import os
import signal
import httpx

BACKEND_DIR = r"G:\OmniAgentAs-desk\backend"
PYTHON = r"E:\Appsw\python31311\python.exe"
SERVER_PORT = 8000
SERVER_URL = f"http://127.0.0.1:{SERVER_PORT}"

def wait_for_server(timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = httpx.get(f"{SERVER_URL}/api/v1/health", timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False

if __name__ == "__main__":
    print("Starting uvicorn server...")
    env = os.environ.copy()
    env["PYTHONPATH"] = BACKEND_DIR

    proc = subprocess.Popen(
        [PYTHON, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
         "--port", str(SERVER_PORT), "--log-level", "error"],
        cwd=BACKEND_DIR,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if not wait_for_server():
        print("Server failed to start")
        proc.kill()
        sys.exit(1)

    print(f"Server started (PID={proc.pid}), running tests...")
    test_args = sys.argv[1:] if len(sys.argv) > 1 else []
    result = subprocess.run(
        [PYTHON, "-m", "pytest", *test_args],
        cwd=BACKEND_DIR,
        env=env,
    )

    print("Stopping server...")
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

    sys.exit(result.returncode)
