"""解析所有订阅源 -> 按 host:port 去重 -> 裸线(绑物理网卡源地址)并行 TCP 可达性筛选。 — 小欧 2026-11-11

输出 hooks\\log\\reachable.txt: 每条一行 "scheme host port 原始链接"

更新: 2026-11-21 小欧 源地址不再写死 192.168.1.4(换网或 DHCP 一变 bind 全失败, 整轮节点静默全判死):
      新增 lan_source_ip() 用 psutil 列物理网卡 IPv4(排除隧道/虚拟/链路本地), 192.168 段优先,
      逐个真连验证通过才采用; 全部不可用则返回 None(不绑源地址走系统默认路由), 开跑前打印实际值。
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

# 名字里带这些词的网卡一律不算裸线(全局隧道/虚拟网卡绑上去等于走隧道) — 小欧 2026-11-21
VIRTUAL_HINTS = ("vpn", "tunnel", "tap", "tun", "wireguard", "wintun", "loopback",
                 "virtual", "vmware", "hyper-v", "vethernet", "docker", "bluetooth")

# 裸线验证靶点: 境内直连可达, 逐个试到通为止 — 小欧 2026-11-21
PROBE_TARGETS = (("223.5.5.5", 443), ("114.114.114.114", 53), ("www.baidu.com", 443))


def _physical_ipv4():
    """物理网卡的 IPv4 列表(排除隧道/虚拟/回环/链路本地); psutil 缺失时返回 []。"""
    try:
        import psutil
    except ImportError:
        return []
    out = []
    for name, addrs in psutil.net_if_addrs().items():
        low = name.lower()
        if any(h in low for h in VIRTUAL_HINTS):
            continue
        for a in addrs:
            if a.family == socket.AF_INET and not a.address.startswith(("127.", "169.254.")):
                out.append(a.address)
    return out


def _prefer(ips):
    """家用网段优先: 192.168 > 172.16-31 > 其他。"""
    def rank(ip):
        if ip.startswith("192.168."):
            return 0
        parts = ip.split(".")
        if ip.startswith("172.") and len(parts) == 4 and 16 <= int(parts[1]) <= 31:
            return 1
        return 2
    return sorted(ips, key=rank)


def _bindable(ip):
    """真连一个境内靶点确认这个源地址能出网; bind 错地址会让整轮节点全判死, 必须验证后再用。

    靶点必须选境内直连可达的: 1.1.1.1 / 8.8.8.8 这类在境内裸线是超时的(实测), 拿它们验证会把
    能用的源地址判成不可用, 于是永远退化成"不绑源地址"。 — 小欧 2026-11-21
    """
    for host, port in PROBE_TARGETS:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.5)
        try:
            s.bind((ip, 0))
            s.connect((host, port))
            return True
        except Exception:
            continue
        finally:
            s.close()
    return False


def lan_source_ip():
    """裸线源地址: 取物理网卡 IPv4, 全部不可用返回 None(不绑, 走系统默认路由)。

    不能用 socket.gethostbyname(hostname) 顶替: 全局隧道工具会把主机名解析到隧道地址
    (实测本机主机名 -> 10.111.222.1, 正是 Skyline 隧道口), 绑上去等于走隧道。 — 小欧 2026-11-21
    """
    for ip in _prefer(_physical_ipv4()):
        if _bindable(ip):
            return ip
    return None


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


def tcp_ok(host, port, src, timeout=3.0):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        if src:
            s.bind((src, 0))
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
    src = lan_source_ip()
    print("裸线源地址: %s" % (src or "未绑定(物理网卡取不到, 走系统默认路由)"))
    print("开始裸线 TCP 筛选(3 秒超时, 60 并发)...")

    def work(rec):
        return rec if tcp_ok(rec[1], rec[2], src) else None

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
