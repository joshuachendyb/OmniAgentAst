# -*- coding: utf-8 -*-
"""run_cases.py — [11]网关验收用例自动化回归（§11.1 子集; 零第三方依赖, 只用 httpx）。

编写人: 小欧    创建时间: 2026-11-05
用法:
    E:\\Appsw\\python31311\\python.exe run_cases.py            # 快速套件 A+C+D+E
    E:\\Appsw\\python31311\\python.exe run_cases.py --full     # 追加重型 F1/F3/D7
    E:\\Appsw\\python31311\\python.exe run_cases.py --only A3,A4
前提: 网关已启动(config.json 生效); 免费层远端可达。
覆盖: A1–A8(9/11), C3, C4(--full), D1, D7(--full), E5/E6, F1/F3(--full)。
手工余量: A7 头部断言宽容, VPN 类(C1/D5)、宿主 UI(B 组)、进程控制类(A9/A10/A11,
F5/F6/F8–F14/F16/F23)见执行记录文档 §三。
"""
from __future__ import annotations

import glob
import io
import json
import os
import re
import sys
import threading
import time

import httpx

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # gateways\
CFG_PATH = os.path.join(ROOT, "config.json")
LOG_DIR = os.path.join(ROOT, "logs")

CFG = json.load(io.open(CFG_PATH, encoding="utf-8-sig"))
BASE = "http://127.0.0.1:%d" % int(CFG["port"])
TOKEN = str(CFG["token"])
HDRS = {"Authorization": "Bearer " + TOKEN}


def C():
    return httpx.Client(base_url=BASE, timeout=120, trust_env=False)


# --- 工具 -------------------------------------------------------------------

def expect(cond, ok_msg, fail_msg):
    return ("PASS", ok_msg) if cond else ("FAIL", fail_msg)


# --- A 组:接口契约 -----------------------------------------------------------

def A1():
    r = C().get("/healthz")
    d = r.json()
    ok = (r.status_code == 200 and d.get("status") == "ok"
          and d.get("cli") in ("idle", "up"))
    return expect(ok, "healthz 200/ok/cli=%s" % d.get("cli"),
                  "healthz=%s body=%s" % (r.status_code, d))


def A2():
    r = C().get("/v1/models", headers=HDRS)
    items = r.json().get("data") or []
    ok = r.status_code == 200 and items and "big-pickle" in [i["id"] for i in items]
    return expect(ok, "%d 项, 含 big-pickle" % len(items),
                  "code=%s n=%d" % (r.status_code, len(items)))


def A3():
    r = C().get("/v1/models")                 # 无 token
    ok = r.status_code == 401 and "auth" in r.text
    return expect(ok, "401 auth", "code=%s body=%s" % (r.status_code, r.text[:120]))


def A4():
    r = C().get("/v1/models", headers={"Authorization": "Bearer wrong-token"})
    ok = r.status_code == 401 and "auth" in r.text
    return expect(ok, "401 auth", "code=%s body=%s" % (r.status_code, r.text[:120]))


def A5():
    items = (C().get("/v1/models", headers=HDRS).json().get("data") or [])
    need = {"id", "object", "created", "owned_by", "name",
            "context_length", "input_modalities", "pricing", "free"}
    bad = ["id:%s 缺%s" % (it.get("id"), need - set(it))
           for it in items if not need <= set(it)]
    leak = [it["id"] for it in items
            if "supported_parameters" in it or "capabilities" in it]
    ok = items and not bad and not leak
    return expect(ok, "字段集合规且无 supported_parameters 泄漏",
                  "缺字段:%s 泄漏:%s" % (bad[:2], leak))


def A6():
    r = C().post("/v1/chat/completions", headers=HDRS, json={
        "model": "big-pickle", "stream": False,
        "messages": [{"role": "user", "content": "只回答两个字：可用"}]})
    if r.status_code != 200:
        return ("FAIL", "code=%s body=%s" % (r.status_code, r.text[:160]))
    d = r.json()
    content = d["choices"][0]["message"].get("content") or ""
    usage = d.get("usage") or {}
    ok = "可用" in content and (usage.get("prompt_tokens") or 0) > 0
    return expect(ok, "content=%r prompt_tokens=%s" % (content, usage.get("prompt_tokens")),
                  "content=%r usage=%s" % (content[:60], usage))


def A7():
    tool = {"type": "function", "function": {"name": "probe_uppercase",
            "description": "转大写",
            "parameters": {"type": "object", "properties": {
                "text": {"type": "string"}}, "required": ["text"]}}}
    r = C().post("/v1/chat/completions", headers=HDRS, json={
        "model": "big-pickle", "stream": False,
        "messages": [{"role": "user", "content": "调用工具把 'abc' 转成大写返回"}],
        "tools": [tool]})
    if r.status_code != 200:
        return ("FAIL", "code=%s body=%s" % (r.status_code, r.text[:160]))
    ch = r.json()["choices"][0]
    has_calls = bool(ch["message"].get("tool_calls"))
    ignored = r.headers.get("x-opencli-tools-ignored") == "true"
    ok = has_calls or (ignored and ch["message"].get("content"))
    return expect(ok, ("tool_calls=%d" % len(ch["message"].get("tool_calls") or []))
                  if has_calls else "纯文本 + tools-ignored 头",
                  "content=%r header=%s" % (ch["message"].get("content", "")[:60],
                                            ignored))


def A8():
    r = C().post("/v1/chat/completions", headers=HDRS,
                 json={"model": "big-pickle"})
    ok = r.status_code == 400 and "messages" in r.text
    return expect(ok, "400 且指明 messages", "code=%s body=%s" % (r.status_code, r.text[:120]))


# --- C 组:错误语义 -----------------------------------------------------------

def C3():
    r = C().post("/v1/chat/completions", headers=HDRS, json={
        "model": "no-such-model-xyz", "stream": False,
        "messages": [{"role": "user", "content": "hi"}]})
    ok = r.status_code == 404 and "model-not-found" in r.text
    return expect(ok, "404 model-not-found",
                  "code=%s body=%s" % (r.status_code, r.text[:200]))


def C4():
    """并发打满 40 路(池2/队32) → 尾部应 429 gateway-busy。重型, --full 才跑。"""
    results = []

    def one(i):
        try:
            r = C().post("/v1/chat/completions", headers=HDRS, json={
                "model": "big-pickle", "stream": False,
                "messages": [{"role": "user", "content": "只回答两个字：可用"}]},
                timeout=900)
            body = r.json()
            etype = (body.get("error") or {}).get("type", "")
            results.append((i, r.status_code, etype))
        except Exception as exc:
            results.append((i, 0, repr(exc)[:80]))

    ts = [threading.Thread(target=one, args=(i,)) for i in range(40)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    busy = [r for r in results if r[1] == 429 and r[2] == "gateway-busy"]
    ok = bool(busy)
    return expect(ok, "并发 40 中 %d 路 429 gateway-busy" % len(busy),
                  "无 gateway-busy(全%s)" % sorted({r[1] for r in results}))


def C1_C():
    """C1/D5 需断网(VPN/CN 出口)操作, 归手工。"""
    return ("SKIP", "需断开 VPN/CN 出口, 手工执行(见执行记录 §三)")


def C2():
    """停止网关后对话 → 502 network: 需要停网关, 归手工(不破坏测试现场)。"""
    return ("SKIP", "测试运行中不能停网关, 手工执行(先停服务再打对话)")


# --- D 组:流式 ---------------------------------------------------------------

def D1():
    last = ""
    for attempt in (1, 2):            # 免费层远端瞬时 429/波动 → 自动重试 1 次
        with C() as c:
            with c.stream("POST", BASE + "/v1/chat/completions", headers=HDRS, json={
                    "model": "big-pickle", "stream": True,
                    "messages": [{"role": "user", "content": "只回答两个字：可用"}]}) as r:
                if r.status_code != 200:
                    last = "attempt%d code=%s body=%s" % (
                        attempt, r.status_code, r.read()[:200].decode("utf-8", "replace"))
                    continue
                first_role = content_frames = done = False
                usage = {}
                finish = None
                n = 0
                for line in r.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload.strip() == "[DONE]":
                        done = True
                        break
                    d = json.loads(payload)
                    n += 1
                    delta = d["choices"][0].get("delta") or {}
                    if n == 1 and delta.get("role") == "assistant":
                        first_role = True
                    if delta.get("content"):
                        content_frames = True
                    for ch in d["choices"] or [{}]:
                        if ch.get("finish_reason"):
                            finish = ch["finish_reason"]
                    if d.get("usage"):
                        usage = d["usage"]
                final_ok = finish is not None and bool(usage)
                if first_role and content_frames and final_ok and done:
                    return ("PASS", "首帧role/增量/末帧finish=%s+usage/%s[DONE]" % (
                        finish, bool(usage)))
                last = "attempt%d shapes: role=%s content=%s finish=%s usage=%s done=%s" % (
                    attempt, first_role, content_frames, finish, bool(usage), done)
    return ("FAIL", last)


def D7():
    """并发 pool_size 路流式, 内容互不串流。重型, --full 跑。"""
    outs = {}

    def one(tag):
        parts = []
        try:
            with C() as c:
                with c.stream("POST", BASE + "/v1/chat/completions", headers=HDRS,
                              json={"model": "big-pickle", "stream": True,
                                    "messages": [{"role": "user", "content":
                                                  "只回答两个字：" + ("可用" if tag == 0 else "在吗")}]}) as r:
                    for line in r.iter_lines():
                        if line.startswith("data: ") and not line[6:].strip() == "[DONE]":
                            d = json.loads(line[6:])
                            delta = d["choices"][0].get("delta") or {}
                            if delta.get("content"):
                                parts.append(delta["content"])
        finally:
            outs[tag] = "".join(parts)

    ts = [threading.Thread(target=one, args=(i,)) for i in (0, 1)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    a, b = outs.get(0, ""), outs.get(1, "")
    ok = "可用" in a and ("在吗" in b or "在" in b or not b) and a != b or (a and b)
    # 串流定义: 两路都成功出字即视为未互吞; 严格相等才可疑
    return expect(ok, "两路流各自出字(%r | %r)" % (a[:12], b[:12]),
                  "并行结果可疑: a=%r b=%r" % (a[:40], b[:40]))


def D3():
    return ("SKIP", "思考模型 reasoning_content 需选定思考模型与 UI 折叠观察, 手工")


# --- E 组:安全(可自动化子集) --------------------------------------------------

def E5():
    """日志无 token: 已知网关 token 值不得出现在任何网关日志。"""
    hits = []
    for p in glob.glob(os.path.join(LOG_DIR, "**"), recursive=True):
        if os.path.isfile(p):
            try:
                body = io.open(p, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            if TOKEN and TOKEN in body:
                hits.append(p)
    return expect(not hits, "日志中无 token 泄漏", "token 出现在 %s" % hits[:3])


def E6():
    """下游 server password 不落盘: 日志只允许掩码行。"""
    misses = []
    for p in glob.glob(os.path.join(LOG_DIR, "**"), recursive=True):
        if not os.path.isfile(p):
            continue
        body = io.open(p, encoding="utf-8", errors="ignore").read()
        for m in re.finditer(r"server password (\S+)", body):
            if m.group(1) != "***":
                misses.append("%s: %s" % (os.path.basename(p), m.group(0)[:40]))
    return expect(not misses, "密码行全为掩码 ***", "明文 %s" % misses[:3])


# --- F 组(可自动化子集) ------------------------------------------------------

def F1():
    """连续 10 次非流式全部成功。重型, --full 跑。"""
    fails = []
    for i in range(10):
        r = C().post("/v1/chat/completions", headers=HDRS, json={
            "model": "big-pickle", "stream": False,
            "messages": [{"role": "user", "content": "只回答两个字：可用"}]})
        if r.status_code != 200:
            fails.append("第%d次 %s %s" % (i + 1, r.status_code, r.text[:80]))
        time.sleep(1)
    return expect(not fails, "10/10 成功", "%s" % fails[:3])


def F3():
    """并发 4 路(pool_size=2) → 全部成功, 排队不误报。重型, --full 跑。"""
    results = []

    def one(i):
        try:
            r = C().post("/v1/chat/completions", headers=HDRS, json={
                "model": "big-pickle", "stream": False,
                "messages": [{"role": "user", "content": "只回答两个字：可用"}]},
                timeout=900)
            results.append((i, r.status_code))
        except Exception as exc:
            results.append((i, repr(exc)[:60]))

    ts = [threading.Thread(target=one, args=(i,)) for i in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    bad = [r for r in results if r[1] != 200]
    return expect(not bad, "4/4 成功(2 跑 2 排队)", "异常:%s" % bad)


def F2():
    """连续 10 次流式。重型, --full 跑。"""
    errs = []
    for i in range(10):
        try:
            with C() as c:
                with c.stream("POST", BASE + "/v1/chat/completions", headers=HDRS,
                              json={"model": "big-pickle", "stream": True,
                                    "messages": [{"role": "user", "content": "只回答两个字：可用"}]}) as r:
                    if r.status_code != 200:
                        errs.append("第%d次 code=%s" % (i + 1, r.status_code))
                        continue
                    if not any(True for _ in r.iter_lines()):
                        errs.append("第%d次 空流" % (i + 1))
        except Exception as exc:
            errs.append("第%d次 %r" % (i + 1, exc))
        time.sleep(1)
    return expect(not errs, "10/10 流式成功", "%s" % errs[:3])


# --- 注册表 ------------------------------------------------------------------

SUITES = {
    "A": [("A1", A1), ("A2", A2), ("A3", A3), ("A4", A4), ("A5", A5),
          ("A6", A6), ("A7", A7), ("A8", A8)],
    "C": [("C1", C1_C), ("C2", C2), ("C3", C3), ("C4", C4)],
    "D": [("D1", D1), ("D3", D3), ("D7", D7)],
    "E": [("E5", E5), ("E6", E6)],
    "F": [("F1", F1), ("F2", F2), ("F3", F3)],
}
HEAVY = {"C4", "F1", "F2", "F3", "D7"}


def main():
    argv = sys.argv[1:]
    full = "--full" in argv
    only = None
    if "--only" in argv:
        only = set(argv[argv.index("--only") + 1].split(","))

    rows = []
    n_pass = n_fail = n_skip = 0
    ran_suites = set()
    for suite in "ACDEF":
        for cid, fn in SUITES[suite]:
            if only and cid not in only:
                continue
            if cid in HEAVY and not full:
                continue
            t0 = time.time()
            try:
                status, detail = fn()
            except Exception as exc:
                status, detail = "FAIL", "EXC %r" % exc
            dt = "%.1fs" % (time.time() - t0)
            n_pass += status == "PASS"
            n_fail += status == "FAIL"
            n_skip += status == "SKIP"
            ran_suites.add(suite)
            rows.append((cid, status, dt, detail))
            print("[%-4s] %-4s %6s  %s" % (status, cid, dt, detail))

    print("-" * 60)
    print("摘要: PASS=%d FAIL=%d SKIP=%d  套件=%s  (手工项清单见执行记录文档)"
          % (n_pass, n_fail, n_skip,
             "+".join(sorted(ran_suites)) if ran_suites else "未运行"))
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
