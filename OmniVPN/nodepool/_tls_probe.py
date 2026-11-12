"""对裸线 TCP 可达的节点做 TLS 握手指纹筛查: 能握手的才可能真能用。 — 小欧 2026-11-11

输入 reachable.txt (scheme host port 源 原始链接)
输出 tls_ok.txt: 握手成功的节点原始链接; ss 等无 TLS 协议按 TCP 结果直接保留
"""
import base64
import json
import os
import socket
import ssl
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORK_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "log")   # 源码 nodepool\, 产物 log\ — 小欧-2026-11-11

IN = os.path.join(WORK_DIR, "reachable.txt")
OUT = os.path.join(WORK_DIR, "tls_ok.txt")
SRC = "192.168.1.4"


def b64(s):
    s = s.strip().replace("-", "+").replace("_", "/")
    return base64.b64decode(s + "=" * (-len(s) % 4)).decode("utf-8", "replace")


def tls_params(scheme, line):
    """返回 (need_tls, sni, alpn_hint)。"""
    try:
        if scheme == "trojan":
            q = urllib.parse.parse_qs(urllib.parse.urlparse(line).query)
            sni = (q.get("sni", [""])[0] or q.get("peer", [""])[0]
                   or urllib.parse.urlparse(line).hostname)
            return True, sni, q.get("alpn", [""])[0]
        if scheme == "vless":
            u = urllib.parse.urlparse(line)
            q = urllib.parse.parse_qs(u.query)
            sec = (q.get("security", [""])[0] or "").lower()
            if sec in ("tls", "reality", "xtls"):
                sni = (q.get("sni", [""])[0] or q.get("host", [""])[0] or u.hostname)
                return True, sni, q.get("alpn", [""])[0]
            return False, "", ""
        if scheme == "vmess":
            cfg = json.loads(b64(line.split("://", 1)[1].split("#")[0]))
            if str(cfg.get("tls", "")).lower() in ("tls", "reality") or cfg.get("tls") is True:
                sni = cfg.get("sni") or cfg.get("host") or cfg.get("add")
                return True, sni, cfg.get("alpn", "")
            return False, "", ""
        if scheme == "ss":
            return False, "", ""
    except Exception:
        return False, "", ""
    return False, "", ""


def tls_ok(host, port, sni, timeout=6.0):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    raw.settimeout(timeout)
    try:
        raw.bind((SRC, 0))
        raw.connect((host, port))
        with ctx.wrap_socket(raw, server_hostname=sni or host) as s:
            return True, s.version()
    except Exception as e:
        return False, type(e).__name__
    finally:
        try:
            raw.close()
        except Exception:
            pass


def main():
    recs = []
    for line in open(IN, encoding="utf-8"):
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 5:
            continue
        scheme, host, port, src, raw = parts
        recs.append((scheme, host, int(port), raw))
    print("待测:", len(recs))

    plain = []
    tls_list = []
    for scheme, host, port, raw in recs:
        need, sni, alpn = tls_params(scheme, raw)
        if need:
            tls_list.append((scheme, host, port, raw, sni, alpn))
        else:
            plain.append((scheme, host, port, raw))

    print("需 TLS 握手:", len(tls_list), " | 无 TLS(ss/vmess plain):", len(plain))
    print("开始 TLS 握手筛查(6 秒超时, 40 并发)...")

    def work(rec):
        scheme, host, port, raw, sni, alpn = rec
        ok, info = tls_ok(host, port, sni)
        return (rec, ok, info)

    survivors = [(s, h, p, r) for s, h, p, r in plain]
    n_ok = 0
    tls_versions = {}
    with ThreadPoolExecutor(max_workers=40) as ex:
        for i, (rec, ok, info) in enumerate(ex.map(work, tls_list), 1):
            if ok:
                n_ok += 1
                tls_versions[info] = tls_versions.get(info, 0) + 1
                scheme, host, port, raw, sni, alpn = rec
                survivors.append((scheme, host, port, raw))
                print("  TLS OK  %-6s %-40s %-5d sni=%-28s %s" % (
                    scheme, host[:38], port, (sni or host)[:26], info))
            if i % 200 == 0:
                print("  ... 已测 %d/%d, TLS 命中 %d" % (i, len(tls_list), n_ok))

    print()
    print("TLS 握手成功:", n_ok, " 版本分布:", tls_versions)
    print("存活合计(含无 TLS):", len(survivors))
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        for scheme, host, port, raw in survivors:
            f.write(raw + "\n")
    print("已写:", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
