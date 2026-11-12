"""按出口桶把节点做轮转排序, 让相邻节点落在不同桶。 — 小欧 2026-11-11

动机: exit_rotator.py 的 switch_mihomo() 是"切到组内下一个活节点"。若两个相邻节点
同桶(例如 9 个意大利节点挤在一起), 切完桶不变 → rc=1 → 白等一轮。
把节点按桶轮转排序后, 相邻节点必然不同桶, 一次切换就能换桶。

输入:
  nodes.yaml       可用节点
  bucket.tsv       普查结果 (节点/出口IP/前缀/loc/colo), 由 _survey_buckets.py --tsv 生成
输出:
  nodes_ordered.yaml  轮转排序后的节点, 注释里带实测出口桶
用法:
  python _order_nodes.py [nodes.yaml] [bucket.tsv]
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORK_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "log")   # 源码 nodepool\, 产物 log\ — 小欧-2026-11-11
sys.path.insert(0, SCRIPT_DIR)

from _filter_nodes import parse_blocks  # noqa: E402  同目录脚本, 复用节点块解析


def read_buckets(path):
    m = {}
    for line in open(path, encoding="utf-8", errors="replace"):
        p = line.rstrip("\n").split("\t")
        if len(p) >= 4 and p[0]:
            m[p[0]] = {"ip": p[1], "prefix": p[2], "loc": p[3],
                       "colo": p[4] if len(p) > 4 else ""}
    return m


def read_delay(path):
    m = {}
    for line in open(path, encoding="utf-8", errors="replace"):
        p = line.rstrip("\n").split("\t")
        if len(p) >= 2:
            try:
                m[p[1].strip()] = int(p[0])
            except ValueError:
                pass
    return m


def main():
    nodes = sys.argv[1] if len(sys.argv) > 1 else os.path.join(WORK_DIR, "nodes.yaml")
    tsv = sys.argv[2] if len(sys.argv) > 2 else os.path.join(WORK_DIR, "buckets.tsv")
    cap = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    out = os.path.join(WORK_DIR, "nodes_ordered.yaml")

    if not os.path.exists(tsv):
        print("缺少普查结果 %s, 先跑 _survey_buckets.py --tsv" % tsv)
        return 2

    buckets = read_buckets(tsv)
    delay = read_delay(os.path.join(WORK_DIR, "good_all.txt"))
    all_blocks = parse_blocks(nodes)
    blocks = [b for b in all_blocks if b[0] in buckets]
    dropped = [b[0] for b in all_blocks if b[0] not in buckets]
    if dropped:
        print("无出口(连不通)已剔除: %s" % ", ".join(dropped))

    groups = {}
    for name, lines in blocks:
        key = (buckets[name]["prefix"], buckets[name]["loc"])
        groups.setdefault(key, []).append((delay.get(name, 99999), name, lines))
    for key in groups:
        groups[key].sort()

    trimmed = 0
    if cap > 0:
        for key in list(groups):
            if len(groups[key]) > cap:
                trimmed += len(groups[key]) - cap
                groups[key] = groups[key][:cap]
    if trimmed:
        print("同桶冗余已裁剪 %d 个(每桶最多 %d 个, 同桶换不出新桶)" % (trimmed, cap))


    # 桶顺序按 loc 字母序固定下来, 保证每次生成结果一致
    order = sorted(groups, key=lambda k: (k[1], k[0]))
    print("桶 %d 个: %s" % (len(order), "  ".join("%s %s(%d)" % (k[1], k[0], len(groups[k])) for k in order)))

    by_name = {n: lines for _, n, lines in [t for g in groups.values() for t in g]}
    kept = []
    idx = {k: 0 for k in order}
    remaining = sum(len(groups[k]) for k in order)
    while remaining:
        for k in order:
            if idx[k] >= len(groups[k]):
                continue
            _, name, _ = groups[k][idx[k]]
            idx[k] += 1
            remaining -= 1
            b = buckets[name]
            kept.append("  # 出口 %s (%s/%s) — %s  %dms"
                        % (b["ip"], b["loc"], b["colo"], name, delay.get(name, 0)))
            kept.extend(l for l in by_name[name] if not l.lstrip().startswith("#"))

    text = "proxies:\n" + "\n".join(kept).rstrip("\n") + "\n"
    open(out, "w", encoding="utf-8", newline="\n").write(text)

    seq = []
    for l in kept:
        m = re.match(r"^\s*-\s+name:\s*(.+)$", l)
        if m:
            n = m.group(1).strip()
            if n in buckets:
                seq.append("%s(%s)" % (n, buckets[n]["loc"]))
    print("已写 %s" % out)
    print("切换顺序: %s" % " -> ".join(seq))
    return 0


if __name__ == "__main__":
    sys.exit(main())
