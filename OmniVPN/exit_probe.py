# -*- coding: utf-8 -*-
# exit_probe.py — 出口身份探测与 mihomo VPN 状态检查（查桶）
# 编写人: 小欧    版本: v2.5    更新时间: 2026-11-12 13:00:00
#
# 修改历史（最新在最下）:
#   ...（v1.2~v2.0 同旧版 opcode225-gate.py）
#   v2.1 2026-11-12 小欧 由 opcode225-gate.py 改名(原名是历史包名, 名不副实);
#                       新增 --mihomo: 一条命令查全 VPN 状态(端口/内核版本/PROXY 选中/
#                       各节点最近测活结果/系统代理/直连与代理出口身份); 报告名改 exit_probe_report-*
#   v2.2 2026-11-12 小欧 输出文案统一重排: 分节编号 [1]~[4], 状态措辞规范化
#                       (运行中/未运行、存活/失联、启用/未启用), 控制器端口提为常量
#   v2.3 2026-11-12 小欧 不带参数 = --mihomo 体检 + 走 7890 查当前出口桶, 两段连跑
#                       (用户指定); 显式 --cf-trace 缺省仍查裸线, 原口径不变
#   v2.4 2026-11-12 小欧 修复退化: 原"直连恒为裸线(loc=CN)"是硬假设, 机器上其它 TUN 模式 VPN
#                       (实测 skyline)接管直连后被误标为裸线且全程不点名; 新增 [0] 本机 VPN
#                       隧道环境节(枚举 TUN/隧道网卡 + 已知 VPN 进程), [4] 判定行改动态
#                       (隧道 Up = 直连出口为该 VPN 出口, 非裸线); 通用化实现, 不写死任何一家
#   v2.5 2026-11-12 小欧 出口信息永不缺位(用户要求: 不管哪个 VPN 在跑都要输出完整出口对照):
#                       不带参数时 7890 未运行不再跳过 trace 段, 改查直连链路出口(被 TUN 接管
#                       时即该 VPN 出口, 带 trace 明细+ASN 归属); 显式 --cf-trace 口径不变
#   v1.2 2026-11-04 小欧 --wait-ip 改用 Cloudflare trace 判定出口(CF 的 ip= 才是服务端所见);
#                       新增 --cf-trace; 出口身份带 family/loc/colo
#   v1.3 2026-11-04 小欧 出口身份增加配额桶前缀: IPv4 折 /24, IPv6 折 /48, 并显示 loc;
#                       --wait-ip 按"前缀 + loc"判定, 同前缀只换尾号不算换(CGNAT 尾号一直在变)
#   v1.4 2026-11-04 小欧 --cf-trace 增加 ASN/归属/reverse 查询(ip-api.com)
#   v1.5 2026-11-04 小欧 新增 --real 直连探测说明; 直连探测的 429 不代表真实额度
#   v1.6 2026-11-11 小欧 报告文件改写到 hooks/reports/ 子目录
#   v1.7 2026-11-11 小欧 移除 --real 系列(real_client_probe, 依赖已失效的 opencode-cli 路径)
#   v1.8 2026-11-11 小欧 报告落盘目录改为 hooks/log/, 与其它运行时生成物统一
#   v2.0 2026-11-11 小欧 只保留出口身份判定一条线: 删除免费模型探测流水线(--probe-urls/
#                       --models/--url-mode/--proxies/--switch-cmd/--wait-ip/--kill-bun/
#                       tools 假装/UA 轮换/call_once 等, 已无调用者); main 缩为 --cf-trace 查询,
#                       不带参数时行为相同; exit_rotator.py 复用的函数全部原样保留
#
# 用途:
#   判定"当前出口是哪个配额桶"。429 FreeUsageLimitError 按出口 IP 网段记账(实测:
#   同一 IP 换 session/UA 仍 429, 换出口 IP 才换桶), 桶指纹 = 前缀(IPv4 /24, IPv6 /48) + loc。
#   CF trace 的 ip= 是服务端实际看到的地址(opencode.ai 与 www.cloudflare.com 同一张 CF 网)。
#
# 用法:
#   python exit_probe.py                  # 不带参数 = --mihomo 体检 + 走 7890 查当前出口桶(连跑, 日常首选)
#   python exit_probe.py --mihomo         # 只做 VPN 状态体检(端口/内核/节点池/系统代理/出口对照)
#   python exit_probe.py --cf-trace       # 只查出口身份(缺省裸线, 恒 loc=CN) + ASN 归属
#   python exit_probe.py --cf-trace --proxy http://127.0.0.1:7890   # 查当前出口桶(走节点)
#
# --mihomo 查什么: [0] 本机 VPN 隧道环境(TUN/隧道网卡+VPN进程) → 7890/9090 端口 → 内核版本
#                  → PROXY 组当前选中 → 各节点最近测活结果 → 系统代理开关 → 直连出口 vs 走代理出口

import argparse
import csv
import datetime
import ipaddress
import json
import os
import socket
import subprocess
import sys
import time

import httpx

IP_ECHO = ["https://api.ipify.org?format=json", "https://ifconfig.me/ip"]

# TUN/隧道网卡识别关键词(通用, 不写死任何一家 VPN) — 小欧 2026-11-12
TUN_KEYWORDS = ("tunnel", "tun-", "tap-", "wintun", "wireguard", "tap windows",
                "openvpn", "skyline", "tailscale", "zerotier", "radmin")
# 已知 VPN/代理内核进程名(子串匹配, 报告里点名谁在跑) — 小欧 2026-11-12
KNOWN_VPN_PROCS = ("skyline", "mihomo", "clash", "v2ray", "xray", "sing-box", "singbox",
                   "hysteria", "wireguard", "openvpn", "gost", "tun2socks", "tailscale")

# Cloudflare 的 trace 端点：返回 CF 眼中的来源 IP / 地区 / 边缘机房。
# opencode.ai 与 www.cloudflare.com 在同一张 CF 网络上，所以这里的 ip= 最接近服务端实际看到的地址。
CF_TRACE = "https://www.cloudflare.com/cdn-cgi/trace"

CONTROLLER_PORT = 9090                 # mihomo 外部控制器端口(与 config.yaml external-controller 对应)
CONTROLLER = "http://127.0.0.1:%d" % CONTROLLER_PORT
PROXY_PORT = 7890                      # 本地 HTTP 混合代理端口

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def cf_trace(client):
    """Cloudflare trace：CF 看到的来源 IP、地区(loc)、边缘机房(colo)。
    这是最接近"服务端实际看到的地址"的观测点（服务端用的就是 CF 注入的 CF-Connecting-IP）。"""
    try:
        r = client.get(CF_TRACE, headers={"User-Agent": "curl/8.21.0"}, timeout=15)
        if r.status_code != 200:
            return None
        data = {}
        for line in r.text.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip()
        return data or None
    except Exception:
        return None


def exit_ip(client):
    """兼容旧调用：优先 CF trace 的 ip（服务端所见），退回 ipify/ifconfig。"""
    t = cf_trace(client)
    if t and t.get("ip"):
        return t["ip"]
    for url in IP_ECHO:
        try:
            r = client.get(url, timeout=15)
            if r.status_code != 200:
                continue
            txt = r.text.strip()
            if txt.startswith("{"):
                return json.loads(txt).get("ip", "?")
            return txt.splitlines()[0].strip()
        except Exception:
            continue
    return None


def asn_of(client, ip):
    """查出口地址的 ASN/归属。免费接口限速，只在 --cf-trace 用一次。"""
    if not ip:
        return None
    try:
        r = client.get("http://ip-api.com/json/%s" % ip,
                       params={"fields": "status,country,regionName,city,isp,org,as,asname,reverse"},
                       timeout=12)
        d = r.json()
        return d if d.get("status") == "success" else None
    except Exception:
        return None


def exit_identity(client):
    """完整出口身份：CF 眼中的 ip/family/loc/colo/warp + IPv4 回声 + 网段前缀。"""
    t = cf_trace(client) or {}
    ip = t.get("ip")
    family = "v6" if ip and ":" in ip else ("v4" if ip else "?")
    v4 = None
    try:
        r = client.get("https://api.ipify.org?format=json", timeout=10)
        if r.status_code == 200:
            v4 = r.json().get("ip")
    except Exception:
        v4 = None
    return {
        "ip": ip,
        "family": family,
        "loc": t.get("loc"),
        "colo": t.get("colo"),
        "warp": t.get("warp"),
        "v4": v4,
        "prefix": net_prefix(ip),
        "prefix_v4": net_prefix(v4),
    }


def net_prefix(ip, v4_bits=24, v6_bits=48):
    """把地址折算成配额桶：IPv4 看 /24，IPv6 看 /48（配额很可能按这个粒度记账）。"""
    if not ip:
        return None
    try:
        addr = ipaddress.ip_address(ip)
        bits = v4_bits if addr.version == 4 else v6_bits
        return str(ipaddress.ip_network("%s/%d" % (ip, bits), strict=False))
    except Exception:
        return None


def fmt_identity(i):
    if not i:
        return "未知"
    parts = ["%s (%s)" % (i.get("ip") or "?", i.get("family") or "?")]
    extras = []
    if i.get("v4") and i.get("v4") != i.get("ip"):
        extras.append("ipv4=%s" % i["v4"])
    if i.get("prefix"):
        extras.append("前缀=%s" % i["prefix"])
    if i.get("prefix_v4") and i.get("prefix_v4") != i.get("prefix"):
        extras.append("v4前缀=%s" % i["prefix_v4"])
    if i.get("loc"):
        extras.append("loc=%s" % i["loc"])
    if i.get("colo"):
        extras.append("colo=%s" % i["colo"])
    if i.get("warp"):
        extras.append("warp=%s" % i["warp"])
    if extras:
        parts.append("[" + " ".join(extras) + "]")
    return " ".join(parts)


def wait_ip_change(client, old_ident, timeout, log):
    """按"配额桶"判定是否真的换了出口：比 /24、/48 前缀和 loc。
    只换门牌号（同前缀）等于没换，继续等；换到不同前缀/不同国家才算换成功。"""
    if not (old_ident or {}).get("ip"):
        return None
    old_key = identity_key(old_ident)
    log("  [等待] 换桶前出口: %s" % fmt_identity(old_ident))
    log("  [等待] 判定口径 = 前缀(%s) 或 loc 变化; 同前缀仅尾号变化不计入 (上限 %ds)"
        % (old_key, timeout))
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(3)
        ident = exit_identity(client)
        if identity_key(ident) != old_key:
            log("  [等待] 已换至新出口桶 -> %s (耗时 %.0fs)" % (fmt_identity(ident), time.time() - start))
            return ident
        if (ident or {}).get("colo") and ident.get("colo") != old_ident.get("colo"):
            log("  [等待] 仅 CF 边缘机房变化 (colo %s -> %s), 桶指纹未变, 继续等待"
                % (old_ident.get("colo"), ident.get("colo")))
            old_ident = dict(old_ident, colo=ident.get("colo"))
    log("  [等待] 超时: 桶指纹未变, 本次切换仍在同一出口桶内")
    return None


def identity_key(ident):
    """配额桶的近似指纹：IPv6 /48、IPv4 /24、loc。"""
    if not ident:
        return None
    prefix = ident.get("prefix")
    if not prefix and ident.get("ip"):
        prefix = net_prefix(ident["ip"])
    return "%s|%s" % (prefix or "?", ident.get("loc") or "?")


def make_client(proxy=None, timeout=90):
    kwargs = {"trust_env": False, "timeout": timeout}
    if proxy:
        kwargs["proxy"] = proxy
    return httpx.Client(**kwargs)


def _port_open(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except OSError:
        return False


def _list_adapters():
    """枚举本机网卡: [(名称, 描述, 状态)]。经 PowerShell Get-NetAdapter 取权威数据。"""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-NetAdapter | Select-Object Name,InterfaceDescription,Status | "
             "ConvertTo-Csv -NoTypeInformation"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=25)
        rows = list(csv.DictReader((r.stdout or "").splitlines()))
        return [(x.get("Name", ""), x.get("InterfaceDescription", ""), x.get("Status", ""))
                for x in rows if x.get("Name")]
    except Exception:
        return []


def _vpn_processes():
    """正在运行的已知 VPN/代理内核进程名(去重)。"""
    try:
        r = subprocess.run(["tasklist", "/FO", "CSV", "/NH"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=25)
        running = {row[0].lower() for row in csv.reader((r.stdout or "").splitlines()) if row}
        return sorted({p for p in KNOWN_VPN_PROCS if any(p in n for n in running)})
    except Exception:
        return []


def tunnel_env(log):
    """[0] 本机 VPN 隧道环境: TUN/隧道网卡 + 已知 VPN 进程。
    判定直连链路是否被其它 VPN 接管(skyline 等 TUN 工具开着时, 直连出口=该 VPN 出口,
    不再是裸线; v2.3 及以前误标为裸线) — 小欧 2026-11-12"""
    adapters = _list_adapters()
    tunnels = [(n, d, s) for (n, d, s) in adapters
               if any(k in (d or "").lower() or k in (n or "").lower() for k in TUN_KEYWORDS)]
    log("[0] 本机 VPN 隧道环境")
    if tunnels:
        for n, d, s in tunnels:
            tag = "  <- 接管中(直连出口被此网卡接管)" if s == "Up" else ""
            log("    网卡 %-30s [%s] %s%s" % (n, s, d, tag))
    else:
        log("    网卡         : 未发现 TUN/隧道类网卡")
    procs = _vpn_processes()
    log("    VPN 进程     : %s" % (", ".join(procs) if procs else "未发现已知 VPN 进程"))
    tun_up = any(s == "Up" for _, _, s in tunnels)
    log("    结论         : %s" % (
        "隧道网卡 Up, 直连链路已被 VPN(TUN)接管 -> [4] 的直连出口是该 VPN 的出口, 非裸线"
        if tun_up else
        "无 Up 状态隧道网卡 -> 直连出口为裸线"))
    return tun_up


def mihomo_status(log, proxy):
    """一条命令体检 mihomo VPN: 服务进程 -> 节点池 -> 系统代理 -> 出口对照。
    作者: 小欧 2026-11-12"""
    tun_up = tunnel_env(log)
    log("[1] 服务进程")
    up, api = _port_open(PROXY_PORT), _port_open(CONTROLLER_PORT)
    log("    代理端口 %d : %s" % (PROXY_PORT, "运行中" if up else "未运行"))
    log("    控制器 %d : %s" % (CONTROLLER_PORT, "运行中" if api else "未运行"))
    if api:
        try:
            c = httpx.Client(trust_env=False, timeout=10)
            log("    内核版本   : %s" % c.get(CONTROLLER + "/version").json().get("version", "?"))
            g = c.get(CONTROLLER + "/proxies/PROXY").json()
            log("[2] 节点池 (PROXY 组, 读最近测活缓存, 不发新探针)")
            log("    当前选中   : %s" % g.get("now"))
            for n in [x for x in (g.get("all") or []) if x not in ("Auto", "DIRECT")]:
                d = c.get(CONTROLLER + "/proxies/" + n).json()
                h = d.get("history") or []
                delay = ("%dms" % h[-1]["delay"]) if h else "-"
                state = "存活" if d.get("alive") else "失联"
                log("    %-6s : %s  delay=%s" % (n, state, delay))
            log("    注: 存活状态为最近一次测速缓存, 免费节点状态变化快, 以 [4] 代理出口实测为准")
            c.close()
        except Exception as e:
            log("    [错误] 控制器查询失败: %s" % str(e).splitlines()[-1])
    else:
        log("    [错误] 控制器不可达, 节点池状态无法读取")
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
        en = winreg.QueryValueEx(k, "ProxyEnable")[0]
        try:
            sv = winreg.QueryValueEx(k, "ProxyServer")[0]
        except OSError:
            sv = ""
        winreg.CloseKey(k)
        log("[3] 系统代理 (WinInet)")
        log("    状态       : %s" % ("启用 -> " + sv if en else "未启用"))
    except Exception as e:
        log("[3] 系统代理 (WinInet)")
        log("    [错误] 注册表读取失败: %s" % str(e).splitlines()[-1])
    log("[4] 出口对照 (Cloudflare trace 实测, 服务端所见)")
    log("    直连出口   : %s" % fmt_identity(exit_identity(make_client())))
    log("    代理出口   : %s" % fmt_identity(
        exit_identity(make_client(proxy=proxy or "http://127.0.0.1:%d" % PROXY_PORT))))
    log("    判定       : %s" % (
        "直连出口已被隧道接管(见[0]), 这一行是 VPN 的出口不是裸线; 看「代理出口」的前缀+loc 即 mihomo 出口桶"
        if tun_up else
        "直连恒为裸线(loc=CN); 看「代理出口」的前缀+loc 即当前出口桶"))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="出口身份探测与 mihomo VPN 状态检查（查桶）")
    ap.add_argument("--mihomo", action="store_true",
                    help="只做 VPN 状态体检(端口/内核/选中节点/节点存活/系统代理/出口对照)")
    ap.add_argument("--cf-trace", action="store_true",
                    help="只查出口身份与 ASN 归属(不带 --proxy 时查裸线; 不带任何参数时自动走 7890)")
    ap.add_argument("--proxy", default="", help="观测出口用的代理(如 http://127.0.0.1:7890)，查节点桶用")
    args = ap.parse_args()

    lines = []
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report_dir = os.path.join(SCRIPT_DIR, "log")  # 生成物统一落 log/, 不堆根目录
    os.makedirs(report_dir, exist_ok=True)
    out_path = os.path.join(report_dir, "exit_probe_report-%s.txt"
                            % datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S"))

    def log(s=""):
        print(s, flush=True)
        lines.append(s)

    log("=" * 78)
    log("exit_probe v2.5  出口身份探测 / mihomo VPN 状态    %s" % stamp)
    log("=" * 78)

    # 模式判定: 显式 --mihomo 只体检; 显式 --cf-trace 只查出口(缺省裸线);
    # 不带参数 = 体检 + 查当前出口桶, 两段连跑(用户指定 2026-11-12)
    mode_status = args.mihomo or not args.cf_trace
    mode_trace = args.cf_trace or not args.mihomo

    if mode_status:
        mihomo_status(log, args.proxy)

    if mode_trace:
        if args.cf_trace:
            obs = args.proxy or None   # 显式 --cf-trace: 不给 --proxy 即查裸线(None=直连, 口径不变)
        else:
            # v2.5: 7890 未运行不再跳过——不管哪个 VPN 在跑都要给完整出口信息;
            # mihomo 没跑时当前出口 = 直连链路出口(skyline 等 TUN 接管时即该 VPN 出口, 见[0])
            if args.proxy:
                obs = args.proxy
            elif _port_open(PROXY_PORT):
                obs = "http://127.0.0.1:%d" % PROXY_PORT
            else:
                obs = None
                log("[提示] 本地代理端口 %d 未运行: 无 mihomo 代理出口可查, "
                    "下面查的是直连链路出口(被 TUN VPN 接管时即该 VPN 的出口, 见[0])" % PROXY_PORT)
        client = make_client(proxy=obs)
        trace = cf_trace(client)
        if not trace:
            log("[错误] Cloudflare trace 无响应 (链路不通或被代理拦截)")
            client.close()
            with open(out_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            print("报告已落盘: %s" % out_path)
            return 2
        for key in ("ip", "loc", "colo", "warp", "gateway", "visit_scheme", "http", "tls"):
            if key in trace:
                log("%-14s %s" % (key, trace[key]))
        ident = exit_identity(client)
        log("出口身份       : %s" % fmt_identity(ident))
        info = asn_of(client, (ident or {}).get("ip"))
        if info:
            log("ASN            : %s  (%s)" % (info.get("as"), info.get("asname")))
            log("归属           : %s %s %s / %s" % (info.get("country"), info.get("regionName"),
                                                  info.get("city"), info.get("isp")))
            if info.get("reverse"):
                log("reverse        : %s" % info["reverse"])
        log("说明: ip= 即服务端(经 Cloudflare)所见地址; 换节点后该值不变 = 未换出口。")
        log("      出口桶指纹 = 前缀(IPv4 /24, IPv6 /48) + loc; 同前缀仅尾号变化 = 同一桶。")
        client.close()

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("报告已落盘: %s" % out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
