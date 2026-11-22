"""公开订阅源抓取: 并行抓全部源, 取到哪个算哪个(含 base64 自动解码)。 — 小欧 2026-11-11

v2 2026-11-12 小欧 并行化+源单重整(实测数据驱动):
  [1] 串行 45s×N 最坏 9 分钟且偶发挂死(实测整跑 10 分钟未出结果被掐), 改 ThreadPoolExecutor
      全并发, 实测 8 源 1.5s 出全量;
  [2] 剔除 5 个 404 死源(Epodonios/vpei/mfuu-v2/aiboboxx-v2/soroushmirzaei), 新增实测
      存活的 mahdibland-EternityBase(4597 节点)与 mahdibland-Eternity(200), 源单共 9 个全活;
  [3] 直连(绕系统代理)失败自动走 7890 备援一击;
  [4] 全部源失败返回 3, 让流水线第 1 步即报错, 不再带病进第 2 步。

v3 2026-11-22 小欧 新增 2 个实测存活源, 并支持 Clash YAML 源自动转 URI:
  [1] 新增 v2rayfree(纯 URI, base64 单行, 19 节点)与 nodesradar(Clash YAML, 500 节点), 源单 9->11;
  [2] 新增 clash_yaml_to_uri(): 含 proxies: 段的源自动解析成每行一个 URI 再落盘,
      保证 subs/*.txt 统一 URI 格式, 下游 _parse_test/_uri2yaml 零改动;
  [3] v2cross.com 实测无公开订阅接口(sub.txt=410, HTML 内嵌节点带 &amp; 污染), 不接入;
  [4] 实测: v2rayfree 经 mihomo 实测 11/18 存活(印尼 ss 节点, 延迟 846~1186ms), 当前网络可用;
      nodesradar 欧美节点被 GFW 拦(本机中国直连), 随机 30 仅 2 可达且与 v2rayfree 重复,
      接入无害(重建时实测筛选不可达节点), 但当前网络下独立价值有限。
"""
import base64
import json
import os
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import yaml  # Clash YAML 源(nodesradar)解析用, PyYAML 6.0.2 — 小欧 2026-11-22

sys.stdout.reconfigure(encoding="utf-8")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORK_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "log")   # 源码在 nodepool\, 产物统一落 log\ — 小欧-2026-11-11
OUT = os.path.join(WORK_DIR, "subs")
os.makedirs(OUT, exist_ok=True)

PROXY_FALLBACK = "http://127.0.0.1:7890"   # 直连被掐时走 mihomo 混合口备援

# 11 个源 2026-11-22 逐一实测存活; 括号内为实测节点数(barry-far 与 EternityBase 是两个大头)
# v2rayfree 纯 URI(base64 单行, 19 节点); nodesradar 是 Clash YAML(500 节点, 转 URI 后 316 唯一)
CANDIDATES = [
    ("barry-far", "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/All_Configs_Sub.txt"),          # 9182
    ("mahdibland-base", "https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/EternityBase"),  # 4597
    ("mahdibland-eter", "https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/Eternity"),   # 200
    ("ermaozi", "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt"),             # 560
    ("ts-sf", "https://raw.githubusercontent.com/ts-sf/fly/main/v2"),                                            # 201
    ("passcro", "https://raw.githubusercontent.com/zhangkaiitugithub/passcro/main/speednodes.txt"),              # 43
    ("ripaojiedian", "https://raw.githubusercontent.com/ripaojiedian/freenode/main/sub"),                        # 20
    ("Pawdroid", "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub"),                            # 20
    ("freefq", "https://raw.githubusercontent.com/freefq/free/master/v2"),                                       # 15
    ("v2rayfree", "https://raw.githubusercontent.com/free-nodes/v2rayfree/main/sub"),                            # 19
    ("nodesradar", "https://radarhub.top/clash.yaml"),                                                          # 500(转URI 316)
]


def decode_if_b64(text):
    """单行且能 base64 解出多行节点时, 视为 base64 订阅。"""
    stripped = text.strip()
    if "\n" in stripped:
        return text
    try:
        pad = stripped + "=" * (-len(stripped) % 4)
        raw = base64.b64decode(pad, validate=False).decode("utf-8", "replace")
        if "://" in raw:
            return raw
    except Exception:
        pass
    return text


def _b64e(s):
    return base64.b64encode(s.encode("utf-8")).decode("utf-8")


def _clash_node_to_uri(p):
    """把 Clash YAML 单个节点转成标准 URI(与 _uri2yaml.PARSERS 字段对齐)。

    只转 mihomo 支持的 trojan/ss/vmess/hysteria2; 其他类型(select/url/direct等)返回 None。
    字段映射严格对齐 _uri2yaml.py 的解析器, 保证转出的 URI 能被下游原样读回。
    """
    t = p.get("type")
    server = p.get("server")
    port = p.get("port")
    if not server or not port:
        return None
    name = p.get("name", "")
    if t == "trojan":
        q = {}
        if p.get("sni"):
            q["sni"] = p["sni"]
        if p.get("skip-cert-verify"):
            q["insecure"] = "1"
        q["udp"] = "1"
        return "trojan://%s@%s:%s?%s#%s" % (
            urllib.parse.quote(p.get("password", ""), safe=""),
            server, port, urllib.parse.urlencode(q), urllib.parse.quote(name))
    if t == "ss":
        body = _b64e("%s:%s" % (p.get("cipher", ""), p.get("password", "")))
        return "ss://%s@%s:%s#%s" % (body, server, port, urllib.parse.quote(name))
    if t == "vmess":
        net = p.get("network", "tcp")
        cfg = {
            "v": "2", "ps": name,
            "add": server, "port": str(port),
            "id": p.get("uuid", ""), "aid": str(p.get("alterId", 0)),
            "scy": p.get("cipher", "auto"),
            "net": net, "type": "none", "host": "", "path": "",
            "tls": "tls" if p.get("tls") else "",
            "sni": p.get("servername") or "",
        }
        if net == "ws":
            ws = p.get("ws-opts", {}) or {}
            cfg["path"] = ws.get("path", "/")
            h = ws.get("headers", {}) or {}
            cfg["host"] = h.get("Host", "") if isinstance(h, dict) else ""
        elif net == "grpc":
            go = p.get("grpc-opts", {}) or {}
            cfg["path"] = go.get("grpc-service-name", "")
        return "vmess://%s#%s" % (_b64e(json.dumps(cfg, ensure_ascii=False)), urllib.parse.quote(name))
    if t == "hysteria2":
        q = {}
        if p.get("sni"):
            q["sni"] = p["sni"]
        if p.get("skip-cert-verify"):
            q["insecure"] = "1"
        return "hysteria2://%s@%s:%s?%s#%s" % (
            urllib.parse.quote(p.get("password", ""), safe=""),
            server, port, urllib.parse.urlencode(q), urllib.parse.quote(name))
    return None


def clash_yaml_to_uri(text):
    """Clash YAML 全文 -> 每行一个 URI 的纯文本(下游 _parse_test/_uri2yaml 零改动)。

    只取 proxies 段, 逐节点转 URI; 跳过 select/url/direct/reject 等非节点类型。
    解析失败返回空串, 让 fetch_one 报 0 节点(不把坏 YAML 当成功)。
    """
    try:
        d = yaml.safe_load(text)
    except Exception:
        return ""
    if not isinstance(d, dict):
        return ""
    lines = []
    for p in d.get("proxies", []) or []:
        if not isinstance(p, dict):
            continue
        uri = _clash_node_to_uri(p)
        if uri:
            lines.append(uri)
    return "\n".join(lines)


def _open(url, proxy):
    """proxy=None 绕开系统代理真直连; 否则经指定代理。"""
    handler = urllib.request.ProxyHandler({} if proxy is None else
                                          {"http": proxy, "https": proxy})
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.build_opener(handler).open(req, timeout=25)


def fetch_one(item):
    """抓一个源: 先真直连, 失败走 7890 备援; 落盘并返回一行结果报告。

    Clash YAML 源(如 nodesradar)自动经 clash_yaml_to_uri 转成 URI 再落盘,
    保证 subs/*.txt 统一为每行一个 URI, 下游 _parse_test/_uri2yaml 零改动。
    """
    name, url = item
    last_err = None
    for via, proxy in (("直连", None), ("7890", PROXY_FALLBACK)):
        try:
            with _open(url, proxy) as r:
                data = r.read()
            text = decode_if_b64(data.decode("utf-8", "replace"))
            # Clash YAML 源: 含 proxies: 段且带 - name: 节点, 转成 URI 纯文本
            if "proxies:" in text and "- name:" in text:
                text = clash_yaml_to_uri(text)
            open(os.path.join(OUT, name + ".txt"), "w", encoding="utf-8", newline="\n").write(text)
            nodes = [l for l in text.splitlines() if "://" in l]
            return "  OK   %-16s %8d B %5d 节点 (%s)" % (name, len(data), len(nodes), via)
        except Exception as e:
            last_err = e
    return "  FAIL %-16s %s" % (name, str(last_err)[:70])


def main():
    ok = 0
    with ThreadPoolExecutor(max_workers=len(CANDIDATES)) as ex:
        for line in ex.map(fetch_one, CANDIDATES):
            print(line, flush=True)
            if " OK " in line:
                ok += 1
    print("源存活 %d / %d" % (ok, len(CANDIDATES)))
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
