"""现池复验(当前生效配置版): 用 mihomo/config.yaml 起临时实例, 逐节点 delay 测活。 — 小欧 2026-11-23

与 _verify_nodes.py 的区别: 那个吃"只含 proxies 段"的 nodes.yaml 并自拼 SEL 组, 只能验流水线中间产物;
本脚本吃**当前真正生效的 config.yaml**(含 proxy-groups 与 dialer-proxy 二级链), 只改端口不拼组,
所以每个节点测到的 delay 就是实际换桶时走的链路 —— update-pool-quick 的现池复验必须用这一份。

临时端口 7897/9097, 不影响在跑的 7890/9090 主实例。
输出格式与 _verify_nodes.py 一致: 每行 "延迟ms<TAB>节点名"(按延迟升序), 供 _bucket_stats.py --alive 用。
用法: python _verify_current.py [--ports 7897 9097] [--threads 12] [--timeout 8000] [--out good_pool.txt]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
MIHOMO_DIR = os.path.join(ROOT, "mihomo")
EXE = os.path.join(MIHOMO_DIR, "mihomo-slim.exe")
CFG = os.path.join(MIHOMO_DIR, "config.yaml")
WORK_DIR = os.path.join(ROOT, "log")
TEST_URL = "http://www.gstatic.com/generate_204"

lock = threading.Lock()


def api(base, path, timeout=25):
    with urllib.request.urlopen(base + path, timeout=timeout) as r:
        txt = r.read().decode("utf-8")
        return json.loads(txt) if txt.strip() else {}


def load_names(path):
    """只取 proxies 段的节点名, 顶格/缩进序列项都认, 不把 proxy-groups 的 - name: 算进来。"""
    names = []
    in_proxies = False
    for line in open(path, encoding="utf-8"):
        s = line.rstrip("\n")
        if not s.strip() or s.lstrip().startswith("#"):
            continue
        m = re.match(r"^(\s*)-\s+name:\s*(.+)$", s)
        if m:
            if in_proxies:
                names.append(m.group(2).strip().strip("\"'"))
            continue
        if not s[:1].isspace():
            in_proxies = s.split(":", 1)[0].strip() == "proxies"
    return names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=CFG)
    ap.add_argument("--ports", nargs=2, type=int, default=[7897, 9097])
    ap.add_argument("--threads", type=int, default=12)
    ap.add_argument("--timeout", type=int, default=8000)
    ap.add_argument("--retry", type=int, default=1)
    ap.add_argument("--out", default=os.path.join(WORK_DIR, "quick", "good_pool.txt"))
    args = ap.parse_args()
    http_port, ctrl_port = args.ports
    base = "http://127.0.0.1:%d" % ctrl_port

    text = open(args.config, encoding="utf-8").read()
    text = text.replace("port: 7890", "port: %d" % http_port, 1)
    text = text.replace("socks-port: 7891", "socks-port: %d" % (http_port + 1), 1)
    text = text.replace("external-controller: 127.0.0.1:9090",
                        "external-controller: 127.0.0.1:%d" % ctrl_port, 1)
    tmp = os.path.join(WORK_DIR, "_verify_current.yaml")
    open(tmp, "w", encoding="utf-8", newline="\n").write(text)

    chk = subprocess.run([EXE, "-t", "-d", MIHOMO_DIR, "-f", tmp],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if "test is successful" not in (chk.stdout + chk.stderr):
        print("配置自检失败:", (chk.stdout + chk.stderr)[-800:])
        return 2

    proc = subprocess.Popen([EXE, "-d", MIHOMO_DIR, "-f", tmp],
                            stdout=open(os.path.join(WORK_DIR, "_verify_current.log"), "w", encoding="utf-8"),
                            stderr=subprocess.DEVNULL)
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

        names = load_names(args.config)
        print("现池 %d 个节点(当前生效 config, 含二级链), 并发 %d" % (len(names), args.threads))
        good, bad = [], []
        reasons = Counter()

        def probe(name):
            q = urllib.parse.urlencode({"timeout": args.timeout, "url": TEST_URL})
            path = "/proxies/%s/delay?%s" % (urllib.parse.quote(name, safe=""), q)
            try:
                d = api(base, path, timeout=args.timeout / 1000.0 + 15)
                ms = d.get("delay")
                if isinstance(ms, int) and ms > 0:
                    return ms, ""
                return None, "无延迟字段 %r" % (d,)
            except urllib.error.HTTPError as e:
                try:
                    why = json.loads(e.read().decode("utf-8", "replace")).get("message", "")
                except Exception:
                    why = ""
                return None, "%d %s" % (e.code, why or e.reason)
            except Exception as e:
                return None, type(e).__name__

        def work(name):
            ms, why = probe(name)
            if ms:
                with lock:
                    good.append((name, ms))
                    print("  OK   %5dms  %s" % (ms, name), flush=True)
                return True
            with lock:
                bad.append(name)
                reasons[why] += 1
            return False

        with ThreadPoolExecutor(max_workers=args.threads) as ex:
            list(ex.map(work, names))

        for rnd in range(1, args.retry + 1):
            if not bad:
                break
            todo = list(bad)
            bad.clear()
            print("---- 第 %d 轮重试: %d 个 ----" % (rnd, len(todo)), flush=True)
            with ThreadPoolExecutor(max_workers=max(1, args.threads // 2)) as ex:
                got = sum(1 for ok in ex.map(work, todo) if ok)
            print("     本轮救回 %d 个" % got, flush=True)

        print("==== 现池存活 %d / %d ====" % (len(good), len(names)))
        if reasons:
            print("失败原因分布:")
            for why, n in reasons.most_common(8):
                print("  %4d x %s" % (n, why))
        if args.out:
            os.makedirs(os.path.dirname(args.out), exist_ok=True)
            with open(args.out, "w", encoding="utf-8", newline="\n") as f:
                for name, ms in sorted(good, key=lambda x: x[1]):
                    f.write("%d\t%s\n" % (ms, name))
            print("已写:", args.out)
        return 0 if good else 3
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
