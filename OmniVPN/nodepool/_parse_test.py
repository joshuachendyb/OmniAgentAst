"""解析所有订阅源 -> 按 host:port 去重 -> 裸线(绑 WLAN 源地址)并行 TCP 可达性筛选。 — 小欧 2026-11-11

输出 hooks\\log\\reachable.txt: 每条一行 "scheme host port 原始链接"
"""
import base64
import json
import os
import socket
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORK_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "log")   # 源码 nodepool\, 产物 log\ — 小欧-2026-11-11
SUBS = os.path.join(WORK_DIR, "subs")
OUT = os.path.join(WORK_DIR, "reachable.txt")
SRC = "192.168.1.4"


def b64(s):
    s = s.strip().replace("-", "+").replace("_", "/")
    return base64.b64decode(s + "=" * (-len(s) % 4)).decode("utf-8", "replace")


def parse_line(line):
    """返回 (scheme, host, port, line) 或 None。"""
    line = line.strip()
    if not line or "://" not in line:
        return None
    scheme = line.split("://", 1)[0].lower()
    body = line.split("://", 1)[1]
    try:
        if scheme == "vmess":
            cfg = json.loads(b64(body.split("#")[0]))
            host, port = cfg.get("add"), int(cfg.get("port", 0))
            return ("vmess", host, port, line) if host and port else None
        if scheme == "ss":
            main = body.split("#")[0].split("?")[0]
            if "@" in main:
                main = main.split("@", 1)[1]
            else:
                main = b64(main)
                main = main.split("@", 1)[1] if "@" in main else ""
            host, _, port = main.rpartition(":")
            host = host.strip("[]")
            return ("ss", host, int(port), line) if host and port.isdigit() else None
        if scheme in ("vless", "trojan", "hysteria2", "hy2", "tuic", "ssr"):
            u = urllib.parse.urlparse(line)
            host = u.hostname
            port = u.port
            return (scheme, host, port, line) if host and port else None
    except Exception:
        return None
    return None


def tcp_ok(host, port, timeout=3.0):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.bind((SRC, 0))
        s.connect((host, port))
        return True
    except Exception:
        return False
    finally:
        s.close()


def main():
    records = []
    for fn in os.listdir(SUBS):
        path = os.path.join(SUBS, fn)
        for line in open(path, encoding="utf-8", errors="replace"):
            r = parse_line(line)
            if r:
                records.append(r + (fn,))
    print("解析到节点:", len(records))

    seen = {}
    for scheme, host, port, line, src in records:
        key = (host.lower(), port)
        if key not in seen:
            seen[key] = (scheme, host, port, line, src)
    uniq = list(seen.values())
    print("按 host:port 去重后:", len(uniq))
    schemes = {}
    for r in uniq:
        schemes[r[0]] = schemes.get(r[0], 0) + 1
    print("协议分布:", schemes)
    print()
    print("开始裸线 TCP 筛选(3 秒超时, 60 并发)...")

    def work(rec):
        return rec if tcp_ok(rec[1], rec[2]) else None

    alive = []
    with ThreadPoolExecutor(max_workers=60) as ex:
        for i, res in enumerate(ex.map(work, uniq), 1):
            if res:
                alive.append(res)
                print("  OK  %-6s %-42s %s" % (res[0], res[1][:40], res[2]))
            if i % 500 == 0:
                print("  ... 已测 %d/%d, 命中 %d" % (i, len(uniq), len(alive)))

    print()
    print("==== 裸线 TCP 可达: %d / %d ====" % (len(alive), len(uniq)))
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        for scheme, host, port, line, src in alive:
            f.write("%s\t%s\t%d\t%s\t%s\n" % (scheme, host, port, src, line))
    print("已写:", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
