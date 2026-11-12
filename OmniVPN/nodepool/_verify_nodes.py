"""用 mihomo 内联 proxies 做端到端验证: 起临时实例 -> 逐节点 delay -> 报告可用清单。 — 小欧 2026-11-11

为什么单独写: exit_rotator.py 依赖 /proxies/<name>/delay, 该接口只对"内联 proxies"有效,
对 proxy-provider 节点返回 404。所以"转换后的 YAML 能不能用"必须用这个接口来验。

用法: python _verify_nodes.py <nodes.yaml> [--ports 7897 9097] [--raw] [--threads 8]
  --raw  加 interface-name: WLAN, 走物理网卡(裸线), 绕开系统级全局路由/隧道工具
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORK_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "log")  # 产物统一落 hooks\log\
MIHOMO_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "mihomo")
EXE = os.path.join(MIHOMO_DIR, "mihomo-slim.exe")
TEST_URL = "http://www.gstatic.com/generate_204"

lock = threading.Lock()


def api(base, path, timeout=25):
    with urllib.request.urlopen(base + path, timeout=timeout) as r:
        txt = r.read().decode("utf-8")
        return json.loads(txt) if txt.strip() else {}


def load_names(path):
    names = []
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if line.startswith("  - name:"):
            names.append(line.split(":", 1)[1].strip().strip("\"'"))
    return names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("nodes")
    ap.add_argument("--ports", nargs=2, type=int, default=[7897, 9097])
    ap.add_argument("--raw", action="store_true")
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=6000)
    ap.add_argument("--retry", type=int, default=0, help="失败节点重试轮数(降低漏判)")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    http_port, ctrl_port = args.ports
    base = "http://127.0.0.1:%d" % ctrl_port
    nodes = os.path.abspath(args.nodes)

    head = [
        "port: %d" % http_port,
        "socks-port: %d" % (http_port + 1),
        "allow-lan: false",
        "mode: Rule",
        "log-level: warning",
        "external-controller: 127.0.0.1:%d" % ctrl_port,
    ]
    if args.raw:
        head.append("interface-name: WLAN")

    body = open(nodes, encoding="utf-8").read()
    tail = """

proxy-groups:
  - name: SEL
    type: select
    proxies:
%s

rules:
  - MATCH,SEL
""" % "\n".join("      - %s" % n for n in load_names(nodes))

    fd, cfg = tempfile.mkstemp(suffix=".yaml", prefix="_verify_")
    os.close(fd)
    open(cfg, "w", encoding="utf-8", newline="\n").write("\n".join(head) + "\n\n" + body + tail)

    chk = subprocess.run([EXE, "-t", "-d", MIHOMO_DIR, "-f", cfg],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if "test is successful" not in (chk.stdout + chk.stderr):
        print("配置自检失败:")
        print((chk.stdout + chk.stderr).strip()[-800:])
        os.unlink(cfg)
        return 2

    log = os.path.join(WORK_DIR, "_verify-run.log")
    proc = subprocess.Popen([EXE, "-d", MIHOMO_DIR, "-f", cfg],
                            stdout=open(log, "w", encoding="utf-8"),
                            stderr=subprocess.DEVNULL)
    try:
        ready = False
        for _ in range(40):
            time.sleep(0.5)
            try:
                api(base, "/proxies", timeout=3)
                ready = True
                break
            except Exception:
                continue
        if not ready:
            print("控制器未就绪, 日志尾部:")
            print(open(log, encoding="utf-8", errors="replace").read()[-800:])
            return 2

        names = load_names(nodes)
        print("节点 %d 个, 并发 %d, 控制器 %s" % (len(names), args.threads, base))
        good, bad = [], []

        def probe(name):
            q = urllib.parse.urlencode({"timeout": args.timeout, "url": TEST_URL})
            path = "/proxies/%s/delay?%s" % (urllib.parse.quote(name, safe=""), q)
            try:
                d = api(base, path, timeout=args.timeout / 1000.0 + 15)
                ms = d.get("delay")
                if isinstance(ms, int) and ms > 0:
                    return ms
            except Exception:
                pass
            return None

        def work(name):
            ms = probe(name)
            if ms:
                with lock:
                    good.append((name, ms))
                    print("  OK   %5dms  %s" % (ms, name), flush=True)
                return
            with lock:
                bad.append(name)

        with ThreadPoolExecutor(max_workers=args.threads) as ex:
            list(ex.map(work, names))

        for rnd in range(1, args.retry + 1):
            if not bad:
                break
            todo = list(bad)
            bad.clear()
            print()
            print("---- 第 %d 轮重试: %d 个 ----" % (rnd, len(todo)), flush=True)
            with ThreadPoolExecutor(max_workers=max(1, args.threads // 2)) as ex:
                list(ex.map(work, todo))

        print()
        print("==== 可用 %d / %d ====" % (len(good), len(names)))
        for name, ms in sorted(good, key=lambda x: x[1]):
            print("  %5dms  %s" % (ms, name))
        if args.out:
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
        try:
            os.unlink(cfg)
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
