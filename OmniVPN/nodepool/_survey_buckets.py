"""普查每个可用节点给出的真实出口: 逐节点切 PROXY 组 -> 经本地代理口拉 CF trace。 — 小欧 2026-11-11

目的: 换桶的判据是 /24(或 /48) 前缀 + loc 同时变化。节点再多, 若出口同桶也没意义,
所以必须先把"这些节点能提供几个互不相同的桶"数清楚。

用法: python _survey_buckets.py <nodes.yaml> [--ports 7897 9097]
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORK_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "log")  # 产物统一落 hooks\log\
MIHOMO_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "mihomo")
EXE = os.path.join(MIHOMO_DIR, "mihomo-slim.exe")
CF_TRACE = "https://www.cloudflare.com/cdn-cgi/trace"


def api(base, path, method="GET", body=None, timeout=20):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        txt = r.read().decode("utf-8")
        return json.loads(txt) if txt.strip() else {}


def load_names(path):
    names = []
    for line in open(path, encoding="utf-8"):
        s = line.strip()
        if s.startswith("- name:"):
            names.append(s.split(":", 1)[1].strip().strip("\"'"))
    return names


def trace_via_proxy(proxy_port, timeout=20):
    op = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": "http://127.0.0.1:%d" % proxy_port,
                                     "https": "http://127.0.0.1:%d" % proxy_port}))
    req = urllib.request.Request(CF_TRACE, headers={"User-Agent": "curl/8.21.0"})
    with op.open(req, timeout=timeout) as r:
        txt = r.read().decode("utf-8", "replace")
    d = {}
    for line in txt.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            d[k] = v
    return d


def prefix_of(ip):
    if ":" in ip:
        return ":".join(ip.split(":")[:3]) + "::/48"
    p = ip.split(".")
    return ".".join(p[:3]) + ".0/24" if len(p) == 4 else ip


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("nodes")
    ap.add_argument("--ports", nargs=2, type=int, default=[7897, 9097])
    ap.add_argument("--group", default="PROXY")
    ap.add_argument("--tsv", default="", help="把 节点/出口IP/前缀/loc/colo 写成 TSV")
    ap.add_argument("--apply", action="store_true", help="同时切出真实出口(默认只读 trace)")
    args = ap.parse_args()

    http_port, ctrl_port = args.ports
    base = "http://127.0.0.1:%d" % ctrl_port
    names = load_names(args.nodes)
    if not names:
        print("节点清单为空")
        return 2

    head = ["port: %d" % http_port, "socks-port: %d" % (http_port + 1),
            "allow-lan: false", "mode: Rule", "log-level: warning",
            "external-controller: 127.0.0.1:%d" % ctrl_port]
    body = open(args.nodes, encoding="utf-8").read()
    tail = """
proxy-groups:
- name: %s
  type: select
  proxies:
%s

rules:
  - MATCH,%s
""" % (args.group, "\n".join("  - %s" % n for n in names), args.group)

    fd, cfg = tempfile.mkstemp(suffix=".yaml", prefix="_survey_")
    os.close(fd)
    open(cfg, "w", encoding="utf-8", newline="\n").write("\n".join(head) + "\n\n" + body + tail)

    chk = subprocess.run([EXE, "-t", "-d", MIHOMO_DIR, "-f", cfg],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if "test is successful" not in (chk.stdout + chk.stderr):
        print("配置自检失败:", (chk.stdout + chk.stderr)[-500:])
        os.unlink(cfg)
        return 2

    log = os.path.join(WORK_DIR, "_survey-run.log")
    proc = subprocess.Popen([EXE, "-d", MIHOMO_DIR, "-f", cfg],
                            stdout=open(log, "w", encoding="utf-8"),
                            stderr=subprocess.DEVNULL)
    rows = []
    try:
        for _ in range(40):
            time.sleep(0.5)
            try:
                api(base, "/proxies", timeout=3)
                break
            except Exception:
                continue
        else:
            print("控制器未就绪")
            return 2

        print("%-8s %-9s %-22s %-40s %-18s %s" % ("节点", "延迟", "服务器", "出口IP", "前缀", "loc/colo"))
        print("-" * 118)
        for name in names:
            try:
                api(base, "/proxies/%s" % urllib.parse.quote(args.group, safe=""),
                    method="PUT", body={"name": name})
            except Exception as e:
                print("  %-8s 切换失败 %s" % (name, e))
                continue
            t = {}
            for attempt in range(2):
                try:
                    t = trace_via_proxy(http_port)
                    break
                except Exception:
                    time.sleep(1)
            ip = t.get("ip", "")
            if not ip:
                rows.append({"node": name, "ok": False})
                print("  %-8s %-9s %-22s %s" % (name, "-", "-", "无 trace(连不通)"))
                continue
            pf = prefix_of(ip)
            rows.append({"node": name, "ok": True, "ip": ip, "prefix": pf,
                         "loc": t.get("loc"), "colo": t.get("colo")})
            print("  %-8s %-9s %-22s %-40s %-18s %s/%s"
                  % (name, "-", "-", ip, pf, t.get("loc"), t.get("colo")))

        ok = [r for r in rows if r.get("ok")]
        buckets = {}
        for r in ok:
            buckets.setdefault((r["prefix"], r["loc"]), []).append(r["node"])
        print()
        print("==== 可用 %d / %d, 互不相同的出口桶 %d 个 ====" % (len(ok), len(names), len(buckets)))
        for (pf, loc), nodes in buckets.items():
            print("  %-18s loc=%-4s  %s" % (pf, loc, ", ".join(nodes)))

        if args.tsv:
            with open(args.tsv, "w", encoding="utf-8", newline="\n") as f:
                for r in ok:
                    f.write("%s\t%s\t%s\t%s\t%s\n" % (r["node"], r["ip"], r["prefix"],
                                                      r.get("loc", ""), r.get("colo", "")))
            print("已写:", args.tsv)
        return 0 if buckets else 3
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except Exception:
            proc.kill()
        try:
            os.unlink(cfg)
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
