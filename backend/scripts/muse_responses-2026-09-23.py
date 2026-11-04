# -*- coding: utf-8 -*-
# muse-*-contributor-free 逐个试 /v1/responses 各种 body 变体 (小欧 2026-09-23)

import datetime
import json
import random
import string
import sys

import httpx

OUT = r"F:\agenttool\test-20260923\muse_responses_report.txt"
URL_RESP = "https://opencode.ai/zen/v1/responses"
MODELS = [
    "muse-spark-1.3-contributor-free",
    "muse-spark-1.2-contributor-free",
]
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


def tools_bash_read():
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


def tools_flat():
    # Responses API 风格: flat tool 定义, 无 function 包装
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


def tools_web_search():
    # OpenAI Responses 内置工具风格
    return [{"type": "web_search"}]


def body_input_text(model, with_tools, tools=None):
    b = {
        "model": model,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": "Say OK"}]}],
        "stream": True,
    }
    if with_tools:
        b["tools"] = tools
    return b


def body_input_str(model, with_tools, tools=None):
    b = {
        "model": model,
        "input": "Say OK",
        "stream": True,
    }
    if with_tools:
        b["tools"] = tools
    return b


def post(client, tag, model, body):
    try:
        r = client.post(URL_RESP, headers=hdrs(),
                        content=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                        timeout=90)
        snippet = r.text[:220].replace("\n", " ")
        log("  [%s] %d %s" % (tag, r.status_code, snippet))
        return r.status_code
    except Exception as e:
        log("  [%s] ERR %s" % (tag, e))
        return -1


def main():
    log("=" * 78)
    log("NOW %s" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    log("muse contributor-free 逐个试 /v1/responses body 变体")

    client = httpx.Client(trust_env=False, timeout=90)

    for model in MODELS:
        log("")
        log("=== %s ===" % model)

        # V1: input 文本 + 无 tools (对照: 门禁是否强制 tools)
        post(client, "V1_input_text_no_tools", model,
             body_input_text(model, False))

        # V2: input 字符串 + 无 tools
        post(client, "V2_input_str_no_tools", model,
             body_input_str(model, False))

        # V3: input 文本 + chat 风格 function-wrapped tools (上次 400)
        post(client, "V3_wrapped_tools", model,
             body_input_text(model, True, tools_bash_read()))

        # V4: input 文本 + flat tools (Responses 官方风格)
        post(client, "V4_flat_tools", model,
             body_input_text(model, True, tools_flat()))

        # V5: input 文本 + web_search 内置工具
        post(client, "V5_web_search", model,
             body_input_text(model, True, tools_web_search()))

        # V6: input 字符串 + flat tools
        post(client, "V6_str_flat_tools", model,
             body_input_str(model, True, tools_flat()))

        # V7: stream false + 无 tools
        b = body_input_text(model, False)
        b["stream"] = False
        post(client, "V7_nostream_no_tools", model, b)

        # V8: stream false + flat tools
        b = body_input_text(model, True, tools_flat())
        b["stream"] = False
        post(client, "V8_nostream_flat_tools", model, b)

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(_log))
    log("")
    log("SAVED " + OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
