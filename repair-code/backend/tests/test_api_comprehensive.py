# -*- coding: utf-8 -*-
"""
API鍏ㄩ潰测试 鈥?37中测癸細正常+异常+输照晫在写櫙
小欧 2026-06-22
"""
import httpx, sys, uuid, json

BASE = "http://127.0.0.1:8000"
ok, fail, bugs = 0, 0, []

def log(status, method, path, desc, detail=""):
    global ok, fail
    kw = "OK" if status else "FAIL"
    if status:
        ok += 1
    else:
        fail += 1
        print(f"  [{kw}]  {method:7s} {path:45s} | {desc}")
        if detail:
            for line in str(detail).split("\n"):
                print(f"         {line}")

def req(method, path, **kw):
    try:
        fn = getattr(httpx, method.lower())
        r = fn(BASE + path, timeout=10, **kw)
        return r.status_code, r
    except httpx.ConnectError:
        return 0, None

def check(method, path, desc, expected=None, **kw):
    code, r = req(method, path, **kw)
    status = True
    detail = ""
    if r is None:
        status = False; detail = "Connection refused"
    elif expected and code != expected:
        status = False
        detail = f"Expected {expected}, got {code}"
        try: detail += f" body={r.text[:200]}"
        except: pass
    log(status, method, path, desc, detail)
    return r

print("=" * 80)
print("OmniAgentAs-desk API Comprehensive Test v2")
print("Target:", BASE)
print("=" * 80)

# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?1. 鍩虹 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?print("\n--- [1] Root / Health / Echo ---")
check("GET", "/", "Root", 200)
check("GET", "/api/v1/health", "Health", 200)
check("POST", "/api/v1/echo", "Echo no body", 422)
check("POST", "/api/v1/echo", "Echo valid", 200, json={"message": "hello"})

# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?2. 宸ュ叿 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?print("\n--- [2] Tools ---")
r = check("GET", "/api/v1/tool/list", "Tool list", 200)
if r:
    j = r.json()
    tc = j.get("total", 0)
    log(True, "GET", "/api/v1/tool/list", f"Total: {tc}")
    if tc != 66: log(False, "", "", f"Expected 66, got {tc}")
    for desk in ["window_info","mouse_click","keyboard_control"]:
        if desk not in [t["name"] for t in j.get("tools",[])]:
            log(False, "", "", f"Missing desktop: {desk}")

check("POST", "/api/v1/tool/execute", "Exec no name", 422, json={})
r = check("POST", "/api/v1/tool/execute", "Exec not found", 200,
          json={"tool_name": "nonexistent", "params": {}})
if r and r.json().get("success", True) != False:
    log(False, "POST", "/api/v1/tool/execute", "Should fail for unknown tool")

# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?3. 配置 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?print("\n--- [3] Config ---")
check("GET", "/api/v1/config", "Get config", 200)
check("GET", "/api/v1/config/models", "Models", 200)
check("GET", "/api/v1/config/full", "Full config", 200)
check("GET", "/api/v1/config/path", "Path", 200)
check("GET", "/api/v1/config/read", "Read file", 200)
check("PUT", "/api/v1/config", "Update empty body (all optional defaults)", 200, json={})
check("PUT", "/api/v1/config", "Update bad provider", 422,
      json={"ai_provider": 123})  # wrong type
check("PUT", "/api/v1/config/validate", "Validate", 422, json={})  # requires provider+api_key
check("POST", "/api/v1/config/fix", "Fix config", 200)
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?4. 浼过瘽 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?print("\n--- [4] Sessions ---")
check("GET", "/api/v1/sessions", "List", 200)
check("GET", "/api/v1/sessions", "List paged", 200,
      params={"page": 1, "page_size": 10})
check("GET", "/api/v1/sessions", "List keyword", 200, params={"keyword": "test"})
check("GET", "/api/v1/sessions", "Invalid page", 422, params={"page": 0})
check("GET", "/api/v1/sessions", "Invalid page_size", 422, params={"page_size": 200})

r = check("POST", "/api/v1/sessions", "Create", 200, json={"title": "test"})
sid = r.json().get("session_id") if r else None
if sid: log(True, "POST", "/api/v1/sessions", f"Created: {sid}")

check("POST", "/api/v1/sessions", "Create empty", 200, json={})
check("POST", "/api/v1/sessions", "Create invalid title type", 422, json={"title": 123})

if sid:
    check("PUT", f"/api/v1/sessions/{sid}", "Update", 200, json={"title": "updated"})
    check("PUT", f"/api/v1/sessions/{sid}", "Update empty body -> 400", 400, json={})
    check("PUT", f"/api/v1/sessions/{sid}", "Update with version", 200,
          json={"title": "v2", "version": 2})
    check("PUT", f"/api/v1/sessions/nonexistent_{uuid.uuid4()}", "Update nonexistent", 404,
          json={"title": "x"})
    # Back to version info
    r = check("GET", f"/api/v1/sessions/{sid}/messages", "Get msgs", 200)
    check("DELETE", f"/api/v1/sessions/{sid}", "Delete", 200)

check("DELETE", "/api/v1/sessions/nonexistent", "Delete nonexistent", 404)
check("GET", "/api/v1/sessions/titles/batch", "Batch no ids", 422)
check("GET", "/api/v1/sessions/titles/batch", "Batch empty ids", 400,
      params={"session_ids": ""})
check("GET", "/api/v1/sessions/titles/batch", "Batch valid", 200,
      params={"session_ids": "a,b"})

# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?5. 消息 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?print("\n--- [5] Messages ---")
check("GET", "/api/v1/sessions/nonexistent/messages", "Get nonexistent", 404)
check("POST", "/api/v1/sessions/nonexistent/messages", "Save nonexistent", 404,
      json={"role": "user", "content": "hi"})
check("POST", "/api/v1/sessions/nonexistent/messages", "Save no body", 422, json={})

r = check("POST", "/api/v1/sessions", "Create for msg", 200, json={"title": "msg-test"})
sid2 = r.json().get("session_id") if r else None

if sid2:
    check("GET", f"/api/v1/sessions/{sid2}/messages", "Get msgs", 200)
    check("POST", f"/api/v1/sessions/{sid2}/messages", "Save user", 200,
          json={"role": "user", "content": "hello"})
    check("POST", f"/api/v1/sessions/{sid2}/messages", "Save assistant", 200,
          json={"role": "assistant", "content": "hi"})
    check("POST", f"/api/v1/sessions/{sid2}/messages", "Save with steps", 200,
          json={"role": "assistant", "content": "thinking...",
                "execution_steps": [{"type": "thought", "content": "s1"}]})
    check("POST", f"/api/v1/sessions/{sid2}/messages", "Save with client info", 200,
          json={"role": "user", "content": "t", "client_os": "win", "browser": "chrome"})
    check("POST", f"/api/v1/sessions/{sid2}/messages", "Save unknown role", 200,
          json={"role": "unknown", "content": "test"})
    r2 = check("GET", f"/api/v1/sessions/{sid2}/messages", "Verify msgs", 200)
    if r2:
        cnt = len(r2.json().get("messages", []))
        if cnt < 5: log(False, "GET", "", f"Expected >=5, got {cnt}")

# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?6. Execution Steps 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?print("\n--- [6] Execution Steps ---")
check("POST", "/api/v1/sessions/nonexistent/execution_steps", "Steps no session",
      404, json={"execution_steps": []})
check("POST", "/api/v1/sessions/nonexistent/execution_steps", "Steps no body (all optional -> session check first)",
      404, json={})

if sid2:
    check("POST", f"/api/v1/sessions/{sid2}/execution_steps", "Save steps", 200,
          json={"execution_steps": [{"type": "tool", "content": "t"}]})
    check("POST", f"/api/v1/sessions/{sid2}/execution_steps", "Save empty steps", 200,
          json={"execution_steps": []})

# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?7. Execution Stream 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?print("\n--- [7] Execution Stream ---")
check("GET", "/api/v1/chat/execution/nonexistent/stream", "Stream nonexistent", 404)
if sid2:
    r = check("GET", f"/api/v1/chat/execution/{sid2}/stream", "Stream existing", 200)
    if r:
        # check SSE
        content = r.text[:100] if r.text else ""
        log(True, "GET", f"/api/v1/chat/execution/{sid2}/stream",
            f"SSE received ({len(r.text)}b, starts {content[:50]})")

# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?8. Chat 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?print("\n--- [8] Chat ---")
check("GET", "/api/v1/chat/validate", "Validate", 200)
check("POST", "/api/v1/chat/stream", "No body", 422, json={})
check("POST", "/api/v1/chat/stream", "Empty msgs", 200,
      json={"messages": []})  # returns SSE error, not 422 (by design)
check("POST", "/api/v1/chat/stream/confirm", "Confirm no body", 200,
      json={})  # uses request.json() directly -> returns {success:false}
check("POST", "/api/v1/chat/stream/confirm", "Confirm invalid id", 200,
      json={"confirm_id": "x", "confirmed": True})
check("POST", "/api/v1/chat/stream/cancel/nonexistent", "Cancel", 200)
check("POST", "/api/v1/chat/stream/pause/nonexistent", "Pause", 200)
check("POST", "/api/v1/chat/stream/resume/nonexistent", "Resume", 200)

# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?9. Metrics 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?print("\n--- [9] Metrics ---")
check("GET", "/api/v1/metrics", "Get", 200)
check("GET", "/api/v1/metrics/raw", "Raw", 200)
check("GET", "/api/v1/metrics/health", "Health", 200)
check("POST", "/api/v1/metrics/reset", "No body", 422, json={})
check("POST", "/api/v1/metrics/reset", "Confirm false", 400,
      json={"confirm": False})  # returns 400 by code, not 422
check("POST", "/api/v1/metrics/reset", "Confirm not bool (Pydantic coerce \"no\"->False)", 400,
      json={"confirm": "no"})

# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?10. Tasks 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?print("\n--- [10] Tasks ---")
check("GET", "/api/v1/tasks", "List", 200)
check("GET", "/api/v1/tasks", "Limit", 200, params={"limit": 5})
check("GET", "/api/v1/tasks", "Invalid limit", 422, params={"limit": 0})
check("GET", "/api/v1/tasks", "Limit too high", 422, params={"limit": 200})
check("GET", "/api/v1/tasks/nonexistent", "Get task", 200)
check("GET", "/api/v1/tasks/nonexistent/operations", "Get ops", 200)

# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?11. Provider/Model CRUD 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?print("\n--- [11] Provider/Model CRUD ---")
check("POST", "/api/v1/config/provider", "No body", 422, json={})
check("POST", "/api/v1/config/provider", "Missing api_base", 422,
      json={"name": "test_p"})  # api_base is required
check("DELETE", "/api/v1/config/provider/nonexistent", "Del provider", 404)
check("PUT", "/api/v1/config/provider/nonexistent", "Upd provider", 404, json={})
check("DELETE", "/api/v1/config/provider/nonexistent/model/x", "Del model", 404)
check("PUT", "/api/v1/config/provider/nonexistent/model/x", "Upd model", 404,
      json={"model": "new"})
check("POST", "/api/v1/config/provider/nonexistent/model", "Add model", 404,
      json={"model": "gpt-4"})
check("POST", "/api/v1/config/provider/nonexistent/model", "Add model no body", 422,
      json={})

print()
print("=" * 80)
print(f"RESULTS: OK={ok}  FAIL={fail}")
if fail:
    print(f"WARNING: {fail} tests failed!")
else:
    print("ALL TESTS PASSED!")
print("=" * 80)
