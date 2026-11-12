"""把 vless/vmess/trojan/ss/hysteria2/tuic 订阅链接转成 mihomo 的 proxies YAML 块。 — 小欧 2026-11-11

用途: exit_rotator.py 的 switch_mihomo() 依赖 /proxies/<name>/delay, 该接口对
proxy-provider 节点返回 404, 所以可用节点必须以"内联 proxies"形式写进 config.yaml。

输入: 每行一个 URI (可带 #备注)
输出: 标准 YAML 列表块, 名称统一改成 NNN (便于按编号精确引用)

只覆盖 mihomo 确实支持且字段可判定的一小撮协议; 判不出来的直接丢弃并计数,
绝不猜字段 —— 猜错的配置会让整份 config 自检失败。
"""
import base64
import json
import os
import sys
import urllib.parse

sys.stdout.reconfigure(encoding="utf-8")


def b64d(s):
    s = s.strip().replace("-", "+").replace("_", "/")
    return base64.b64decode(s + "=" * (-len(s) % 4)).decode("utf-8", "replace")


def q1(q, *keys, default=""):
    for k in keys:
        v = q.get(k)
        if v:
            return v[0]
    return default


def truthy(v):
    return str(v).lower() in ("1", "true", "yes")


def parse_vless(uri):
    u = urllib.parse.urlparse(uri)
    q = urllib.parse.parse_qs(u.query)
    p = {
        "type": "vless",
        "server": u.hostname,
        "port": u.port,
        "uuid": urllib.parse.unquote(u.username or ""),
        "udp": True,
    }
    flow = q1(q, "flow")
    if flow:
        p["flow"] = flow
    sec = q1(q, "security").lower()
    sni = q1(q, "sni", "peer", "host", default=u.hostname)
    if sec in ("tls", "xtls"):
        p["tls"] = True
        p["servername"] = sni
    elif sec == "reality":
        pbk = q1(q, "pbk")
        if not pbk:
            return None
        p["tls"] = True
        p["servername"] = sni
        ro = {"public-key": pbk}
        sid = q1(q, "sid")
        # mihomo 要求 short-id 为偶数长度十六进制; 空值必须整键省略, 不能写空串
        if sid and len(sid) % 2 == 0 and all(c in "0123456789abcdefABCDEF" for c in sid):
            ro["short-id"] = sid
        p["reality-opts"] = ro
        fp = q1(q, "fp")
        if fp:
            p["client-fingerprint"] = fp
    if truthy(q1(q, "allowInsecure", "insecure")):
        p["skip-cert-verify"] = True
    net = q1(q, "type", "network", default="tcp").lower()
    if net == "ws":
        p["network"] = "ws"
        p["ws-opts"] = {"path": q1(q, "path", default="/")}
        host = q1(q, "host")
        if host:
            p["ws-opts"]["headers"] = {"Host": host}
    elif net == "grpc":
        p["network"] = "grpc"
        p["grpc-opts"] = {"grpc-service-name": q1(q, "serviceName")}
    elif net in ("xhttp", "http", "h2"):
        # mihomo 对 xhttp 支持不完整, 直接放弃, 避免整份配置失败
        return None
    alpn = q1(q, "alpn")
    if alpn:
        p["alpn"] = [a for a in alpn.split(",") if a]
    return p


def parse_vmess(uri):
    cfg = json.loads(b64d(uri.split("://", 1)[1].split("#")[0]))
    p = {
        "type": "vmess",
        "server": cfg.get("add"),
        "port": int(cfg.get("port") or 0),
        "uuid": cfg.get("id"),
        "alterId": int(cfg.get("aid") or 0),
        "cipher": cfg.get("scy") or "auto",
        "udp": True,
    }
    net = (cfg.get("net") or "tcp").lower()
    if net == "ws":
        p["network"] = "ws"
        p["ws-opts"] = {"path": cfg.get("path") or "/"}
        if cfg.get("host"):
            p["ws-opts"]["headers"] = {"Host": cfg["host"]}
    elif net == "grpc":
        p["network"] = "grpc"
        p["grpc-opts"] = {"grpc-service-name": cfg.get("path") or ""}
    elif net in ("h2", "http", "xhttp"):
        return None
    if str(cfg.get("tls", "")).lower() in ("tls", "reality"):
        p["tls"] = True
        p["servername"] = cfg.get("sni") or cfg.get("host") or cfg.get("add")
    return p


def parse_trojan(uri):
    u = urllib.parse.urlparse(uri)
    q = urllib.parse.parse_qs(u.query)
    p = {
        "type": "trojan",
        "server": u.hostname,
        "port": u.port,
        "password": urllib.parse.unquote(u.username or ""),
        "udp": True,
    }
    sni = q1(q, "sni", "peer", "host", default=u.hostname)
    p["sni"] = sni
    if truthy(q1(q, "allowInsecure", "insecure")):
        p["skip-cert-verify"] = True
    net = q1(q, "type", "network", default="tcp").lower()
    if net == "ws":
        p["network"] = "ws"
        p["ws-opts"] = {"path": q1(q, "path", default="/")}
        host = q1(q, "host")
        if host:
            p["ws-opts"]["headers"] = {"Host": host}
    elif net == "grpc":
        p["network"] = "grpc"
        p["grpc-opts"] = {"grpc-service-name": q1(q, "serviceName")}
    elif net in ("xhttp", "h2", "http"):
        return None
    alpn = q1(q, "alpn")
    if alpn:
        p["alpn"] = [a for a in alpn.split(",") if a]
    return p


def parse_ss(uri):
    body = uri.split("://", 1)[1].split("#")[0]
    body = body.split("?", 1)[0]
    if "@" in body:
        userinfo, hostport = body.rsplit("@", 1)
        try:
            dec = b64d(userinfo)
            method, _, password = dec.partition(":")
        except Exception:
            method, _, password = userinfo.partition(":")
    else:
        dec = b64d(body)
        userinfo, _, hostport = dec.rpartition("@")
        method, _, password = userinfo.partition(":")
    host, _, port = hostport.rpartition(":")
    host = host.strip("[]")
    if not (host and port.isdigit() and method and password):
        return None
    return {
        "type": "ss",
        "server": host,
        "port": int(port),
        "cipher": method,
        "password": password,
        "udp": True,
    }


def parse_hy2(uri):
    u = urllib.parse.urlparse(uri)
    q = urllib.parse.parse_qs(u.query)
    p = {
        "type": "hysteria2",
        "server": u.hostname,
        "port": u.port,
        "password": urllib.parse.unquote(u.username or ""),
    }
    sni = q1(q, "sni", "peer")
    if sni:
        p["sni"] = sni
    if truthy(q1(q, "insecure", "allowInsecure")):
        p["skip-cert-verify"] = True
    return p


def parse_tuic(uri):
    u = urllib.parse.urlparse(uri)
    q = urllib.parse.parse_qs(u.query)
    p = {
        "type": "tuic",
        "server": u.hostname,
        "port": u.port,
        "uuid": urllib.parse.unquote(u.username or ""),
        "password": urllib.parse.unquote(u.password or ""),
    }
    sni = q1(q, "sni", "peer")
    if sni:
        p["sni"] = sni
    alpn = q1(q, "alpn")
    p["alpn"] = [a for a in alpn.split(",") if a] if alpn else ["h3"]
    return p


PARSERS = {
    "vless": parse_vless,
    "vmess": parse_vmess,
    "trojan": parse_trojan,
    "ss": parse_ss,
    "hysteria2": parse_hy2,
    "hy2": parse_hy2,
    "tuic": parse_tuic,
}


def yaml_scalar(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    s = str(v)
    if s == "" or any(c in s for c in ":#{}[],&*?|-<>=!%@`\"'\\") or s != s.strip():
        return '"%s"' % s.replace("\\", "\\\\").replace('"', '\\"')
    return s


# 这几类值必须强制加引号: 十六进制串会被 YAML 当数字(08/1e5 等), 公钥带 - 会被当锚点
FORCE_QUOTE = {"short-id", "public-key"}


def emit(name, p):
    out = ["  - name: %s" % name]
    for k in ("type", "server", "port", "cipher", "uuid", "password", "alterId",
              "flow", "udp", "tls", "sni", "servername", "skip-cert-verify",
              "client-fingerprint", "alpn", "network"):
        if k in p:
            v = p[k]
            if isinstance(v, list):
                out.append("    %s:" % k)
                for item in v:
                    out.append("      - %s" % yaml_scalar(item))
            else:
                out.append("    %s: %s" % (k, yaml_scalar(v)))
    for k in ("reality-opts", "ws-opts", "grpc-opts"):
        if k in p:
            out.append("    %s:" % k)
            for kk, vv in p[k].items():
                if isinstance(vv, dict):
                    out.append("      %s:" % kk)
                    for k3, v3 in vv.items():
                        out.append("        %s: %s" % (k3, yaml_scalar(v3)))
                elif kk in FORCE_QUOTE:
                    out.append('      %s: "%s"' % (kk, str(vv).replace('"', '\\"')))
                else:
                    out.append("      %s: %s" % (kk, yaml_scalar(vv)))
    return "\n".join(out)


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    work_dir = os.path.join(os.path.dirname(script_dir), "log")   # 源码 nodepool\, 产物 log\ — 小欧-2026-11-11
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(work_dir, "tls_ok.txt")
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(work_dir, "nodes.yaml")

    seen = set()
    blocks = []
    mapping = []
    stats = {"in": 0, "ok": 0, "skip": 0, "dup": 0}
    by_type = {}
    n = 0
    for line in open(src, encoding="utf-8", errors="replace"):
        line = line.strip()
        if "://" not in line:
            continue
        stats["in"] += 1
        scheme = line.split("://", 1)[0].lower()
        fn = PARSERS.get(scheme)
        if not fn:
            stats["skip"] += 1
            continue
        try:
            p = fn(line)
        except Exception:
            p = None
        if not p or not p.get("server") or not p.get("port"):
            stats["skip"] += 1
            continue
        key = (p["type"], p["server"], p["port"],
               p.get("uuid") or p.get("password") or "")
        if key in seen:
            stats["dup"] += 1
            continue
        seen.add(key)
        n += 1
        stats["ok"] += 1   # 修复: ok 从未自增导致打印恒为"生成 0" — 小欧 2026-11-12
        by_type[p["type"]] = by_type.get(p["type"], 0) + 1
        name = "N%02d" % n
        remark = urllib.parse.unquote(line.split("#", 1)[1]) if "#" in line else ""
        if remark:
            blocks.append("  # %s" % remark.replace("\n", " ")[:90])
        blocks.append(emit(name, p))
        mapping.append("%s\t%s\t%s:%s\t%s" % (name, p["type"], p["server"], p["port"], remark))

    open(dst, "w", encoding="utf-8", newline="\n").write("proxies:\n" + "\n".join(blocks) + "\n")
    open(dst + ".map.txt", "w", encoding="utf-8", newline="\n").write("\n".join(mapping) + "\n")

    print("输入 %(in)d 条 -> 生成 %(ok)d 个, 跳过 %(skip)d(协议不支持/字段缺失), 去重 %(dup)d" % stats)
    print("类型分布:", by_type)
    print("已写:", dst)
    print("对照表:", dst + ".map.txt")



if __name__ == "__main__":
    sys.exit(main())
