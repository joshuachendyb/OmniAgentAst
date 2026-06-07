"""
真实 API 测试 — 连接本地服务，模拟用户发任务
小沈 2026-05-21
"""
import json
import httpx
import time
import sys

BASE = "http://127.0.0.1:8000"
SSE_URL = f"{BASE}/api/v1/chat/stream/v2"
TIMEOUT = 180

TASKS = [
    # 1. 简单问答
    "你好，请问你是谁？",
    "今天天气怎么样？",
    "1+1等于几？",
    # 2. 文件操作
    "列出当前目录的文件",
    "读取当前目录下的一个python文件",
    "搜索包含'test'的文件",
    # 3. Shell操作
    "查看当前时间",
    # 4. 系统信息
    "查看系统信息",
    # 5. 边界情况
    "a",
    "",
    # 6. 长任务
    "请帮我递归列出所有python文件",
]

passed = 0
failed = 0
issues = []


def parse_sse(line: str):
    if line.startswith("data: "):
        try:
            return json.loads(line[6:])
        except json.JSONDecodeError:
            return None
    return None


def send_task(task: str) -> list:
    payload = {
        "messages": [{"role": "user", "content": task}],
        "stream": True,
    }
    events = []
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            with client.stream("POST", SSE_URL, json=payload) as resp:
                if resp.status_code != 200:
                    return [{"type": "error", "error_message": f"HTTP {resp.status_code}", "raw": resp.text[:500]}]
                for line in resp.iter_lines():
                    if not line.strip():
                        continue
                    ev = parse_sse(line)
                    if ev:
                        events.append(ev)
    except Exception as e:
        return [{"type": "error", "error_message": str(e)}]
    return events


def check_events(task: str, events: list):
    global passed, failed
    prefix = task[:40]

    if not events:
        failed += 1
        issues.append(f"[FAIL] 无事件返回: {prefix}")
        return

    last = events[-1]
    if last["type"] == "error":
        failed += 1
        issues.append(f"[FAIL] {prefix} → error: {last.get('error_message','')}")
        return

    if last["type"] != "final":
        failed += 1
        issues.append(f"[FAIL] {prefix} → 最后事件不是final: {last['type']}")
        return

    # 检查是否有start
    has_start = any(e["type"] == "start" for e in events)
    if not has_start:
        issues.append(f"[WARN] {prefix} → 没有start事件")

    passed += 1
    types = [e["type"] for e in events]
    print(f"  [OK] {prefix} -> {len(events)} events, types={types}")


if __name__ == "__main__":
    print("=" * 60)
    print(f"真实 API 测试 — {len(TASKS)} 个任务")
    print("=" * 60)

    for i, task in enumerate(TASKS, 1):
        print(f"\n[{i}/{len(TASKS)}] 发送: {task[:60]}")
        sys.stdout.flush()
        t0 = time.time()
        events = send_task(task)
        cost = time.time() - t0
        print(f"  耗时: {cost:.1f}s")
        check_events(task, events)

    print("\n" + "=" * 60)
    print(f"结果: {passed} passed, {failed} failed, {len(TASKS)} total")
    if issues:
        print("\n问题列表:")
        for iss in issues:
            print(f"  {iss}")
    print("=" * 60)
