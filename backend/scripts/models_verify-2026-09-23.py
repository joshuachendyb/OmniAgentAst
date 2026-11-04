# -*- coding: utf-8 -*-
# 拉取 /zen/v1/models 并过滤免费模型逐个验证 (小欧 2026-09-23)
# 免费模型 = 名字含 -free 后缀 或 big-pickle; 收费模型直接跳过
# 四条件: UA opencode/>=1.17.0 + 合法随机 session + tools含bash/read + stream:true
# muse 系走 /v1/responses + flat tools (无 function 包装); 其余走 /v1/chat/completions

import datetime
import json
import random
import string
import sys

import httpx

OUT = r"F:\agenttool\test-20260923\models_verify_report.txt"
URL_MODELS = "https://opencode.ai/zen/v1/models"
URL_CHAT = "https://opencode.ai/zen/v1/chat/completions"
URL_RESP = "https://opencode.ai/zen/v1/responses"
RESPONSES_MODELS = {
    "muse-spark-1.3-contributor-free",
    "muse-spark-1.2-contributor-free",
}
B62 = string.ascii_letters + string.digits
B16 = "0123456789abcdef"
_log = []


def log(s=""):
    print(s, flush=True)
    _log.append(s)


def rand_sid():
    return ("ses_"
            + "".join(random.choice(B16) for _ in range(12))
            + "".join(random.choice(B62) for _ in range(14)))


def hdrs():
    return {
        "Content-Type": "application/json",
        "User-Agent": "opencode/1.18.31",
        "x-opencode-session": rand_sid(),
    }


def tools_min():
    return [
        {"type": "function", "function": {
            "name": "bash",
            "description": "Executes a given command.",
            "parameters": {"type": "object", "properties": {
                "command": {"type": "string"},
            }, "required": ["command"]},
        }},
        {"type": "function", "function": {
            "name": "read",
            "description": "Read a file.",
            "parameters": {"type": "object", "properties": {
                "filePath": {"type": "string"},
            }, "required": ["filePath"]},
        }},
    ]


def is_free(mid):
    # 免费层特征: -free 后缀 或 特殊名 big-pickle
    return mid.endswith("-free") or mid == "big-pickle"


def fetch_models(client):
    r = client.get(URL_MODELS, headers={"User-Agent": "opencode/1.18.31"}, timeout=30)
    log("GET /v1/models -> %d" % r.status_code)
    if r.status_code != 200:
        log(r.text[:300])
        return []
    data = r.json().get("data", [])
    all_ids = [m.get("id", "") for m in data if m.get("id")]
    free_ids = [mid for mid in all_ids if is_free(mid)]
    log("全部模型 %d 个, 过滤后免费模型 %d 个" % (len(all_ids), len(free_ids)))
    for mid in free_ids:
        log("  free: %s" % mid)
    return free_ids


def verify_chat(client, model):
    body = {
        "model": model,
        "max_tokens": 32,
        "messages": [{"role": "user", "content": "Say OK"}],
        "tools": tools_min(),
        "stream": True,
    }
    try:
        r = client.post(URL_CHAT, headers=hdrs(),
                        content=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                        timeout=90)
        ok = r.status_code == 200
        detail = "200" if ok else "%d %s" % (r.status_code, r.text[:160].replace("\n", " "))
        return ok, detail
    except Exception as e:
        return False, "ERR %s" % e


def tools_flat():
    # Responses API 要求 flat tool 定义(无 function 包装), 否则 400 tools[0]
    return [
        {"type": "function", "name": "bash",
         "description": "Executes a given command.",
         "parameters": {"type": "object", "properties": {
             "command": {"type": "string"},
         }, "required": ["command"]}},
        {"type": "function", "name": "read",
         "description": "Read a file.",
         "parameters": {"type": "object", "properties": {
             "filePath": {"type": "string"},
         }, "required": ["filePath"]}},
    ]


def verify_responses(client, model):
    body = {
        "model": model,
        "input": "Say OK",
        "stream": True,
        "tools": tools_flat(),
    }
    try:
        r = client.post(URL_RESP, headers=hdrs(),
                        content=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                        timeout=90)
        ok = r.status_code == 200
        detail = "200" if ok else "%d %s" % (r.status_code, r.text[:160].replace("\n", " "))
        return ok, detail
    except Exception as e:
        return False, "ERR %s" % e


def main():
    log("=" * 78)
    log("NOW %s" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    log("拉模型列表, 过滤免费模型后逐个用四条件配方验证")

    client = httpx.Client(trust_env=False, timeout=90)
    models = fetch_models(client)
    log("待验证免费模型 %d 个" % len(models))

    passed = []
    failed = []
    for mid in models:
        if mid in RESPONSES_MODELS or mid.startswith("muse-"):
            ep = "responses"
            ok, detail = verify_responses(client, mid)
        else:
            ep = "chat"
            ok, detail = verify_chat(client, mid)
        tag = "PASS" if ok else "FAIL"
        log("[%s] %-40s %-10s %s" % (tag, mid, ep, detail))
        (passed if ok else failed).append(mid)

    log("")
    log("PASS %d / FAIL %d / TOTAL %d" % (len(passed), len(failed), len(models)))
    if failed:
        log("FAILED: " + ", ".join(failed))

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(_log))
    log("SAVED " + OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
