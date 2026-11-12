"""第二批公共节点源候选, 取到哪个算哪个(含 base64 自动解码)。 — 小欧 2026-11-11"""
import base64
import os
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORK_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "log")   # 源码在 nodepool\, 产物统一落 log\ — 小欧-2026-11-11
OUT = os.path.join(WORK_DIR, "subs")
os.makedirs(OUT, exist_ok=True)

CANDIDATES = [
    ("barry-far", "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/All_Configs_Sub.txt"),
    ("Epodonios", "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/All_Configs_Sub.txt"),
    ("ermaozi", "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt"),
    ("freefq", "https://raw.githubusercontent.com/freefq/free/master/v2"),
    ("ripaojiedian", "https://raw.githubusercontent.com/ripaojiedian/freenode/main/sub"),
    ("Pawdroid", "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub"),
    ("ts-sf", "https://raw.githubusercontent.com/ts-sf/fly/main/v2"),
    ("passcro", "https://raw.githubusercontent.com/zhangkaiitugithub/passcro/main/speednodes.txt"),
    ("vpei", "https://raw.githubusercontent.com/vpei/Free-Node-Merge/main/o.txt"),
    ("mfuu-v2", "https://raw.githubusercontent.com/mfuu/v2ray/master/v2"),
    ("aiboboxx-v2", "https://raw.githubusercontent.com/aiboboxx/v2rayfree/main/v2rayfree"),
    ("soroushmirzaei", "https://raw.githubusercontent.com/soroushmirzaei/telegram-configs-collector/main/protocols/vless"),
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


def main():
    for name, url in CANDIDATES:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=45) as r:
                data = r.read()
            text = decode_if_b64(data.decode("utf-8", "replace"))
            dst = os.path.join(OUT, name + ".txt")
            open(dst, "w", encoding="utf-8", newline="\n").write(text)
            nodes = [l for l in text.splitlines() if "://" in l]
            print("  OK   %-16s %8d B  %5d 节点" % (name, len(data), len(nodes)))
        except Exception as e:
            print("  FAIL %-16s %s" % (name, str(e)[:60]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
