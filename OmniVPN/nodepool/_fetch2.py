"""公开订阅源抓取: 并行抓全部源, 取到哪个算哪个(含 base64 自动解码)。 — 小欧 2026-11-11

v2 2026-11-12 小欧 并行化+源单重整(实测数据驱动):
  [1] 串行 45s×N 最坏 9 分钟且偶发挂死(实测整跑 10 分钟未出结果被掐), 改 ThreadPoolExecutor
      全并发, 实测 8 源 1.5s 出全量;
  [2] 剔除 5 个 404 死源(Epodonios/vpei/mfuu-v2/aiboboxx-v2/soroushmirzaei), 新增实测
      存活的 mahdibland-EternityBase(4597 节点)与 mahdibland-Eternity(200), 源单共 9 个全活;
  [3] 直连(绕系统代理)失败自动走 7890 备援一击;
  [4] 全部源失败返回 3, 让流水线第 1 步即报错, 不再带病进第 2 步。
"""
import base64
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORK_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "log")   # 源码在 nodepool\, 产物统一落 log\ — 小欧-2026-11-11
OUT = os.path.join(WORK_DIR, "subs")
os.makedirs(OUT, exist_ok=True)

PROXY_FALLBACK = "http://127.0.0.1:7890"   # 直连被掐时走 mihomo 混合口备援

# 8 个源 2026-11-12 逐一实测存活; 括号内为实测节点数(barry-far 与 EternityBase 是两个大头)
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


def _open(url, proxy):
    """proxy=None 绕开系统代理真直连; 否则经指定代理。"""
    handler = urllib.request.ProxyHandler({} if proxy is None else
                                          {"http": proxy, "https": proxy})
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.build_opener(handler).open(req, timeout=25)


def fetch_one(item):
    """抓一个源: 先真直连, 失败走 7890 备援; 落盘并返回一行结果报告。"""
    name, url = item
    last_err = None
    for via, proxy in (("直连", None), ("7890", PROXY_FALLBACK)):
        try:
            with _open(url, proxy) as r:
                data = r.read()
            text = decode_if_b64(data.decode("utf-8", "replace"))
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
