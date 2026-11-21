r"""统计当前节点池的出口桶分布(离线, 不联网不起内核)。 — 小欧 2026-11-21

动机: 换桶策略已改为"新桶须避开最近 N 次用过的桶"(N 取 exit_probe.BUCKET_HISTORY_SIZE), 所以要能一眼看出
现池到底有几个互不相同的出口桶、这些桶里还有几个没被账本占掉。
池子=节点清单, 桶归属来自普查快照 log\buckets.tsv(_survey_buckets.py --tsv 生成)。

输入:
  mihomo\config.yaml        当前真正生效的节点池(默认; 也可传 log\nodes_ordered.yaml)
  log\buckets.tsv           节点 -> 出口IP/前缀/loc/colo 普查快照
  log\bucket_history.json   最近 N 次用过的桶(exit_probe 维护, 缺则按空账本)
  --alive <file>            只看存活节点(如 log\quick\good_pool.txt, 每行 "延迟ms\t名称")
用法:
  python _bucket_stats.py
  python _bucket_stats.py log\nodes_ordered.yaml
  python _bucket_stats.py --alive log\quick\good_pool.txt
  python _bucket_stats.py --by-node              # 逐节点一行(按池内轮转顺序), 供 proxy-on 启动后展示
输出: 每个桶一行(前缀/loc/桶内节点, 已被账本占用的桶带标记) + 汇总行; --by-node 则每个节点一行
返回码: 0=正常  2=池文件或桶快照缺失
"""
import argparse
import datetime
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)              # 源码 nodepool\, 产物 log\
WORK_DIR = os.path.join(ROOT, "log")
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, ROOT)

from _order_nodes import read_buckets, read_delay  # noqa: E402  同目录/上级脚本, 复用 TSV 解析
import exit_probe as gate                          # noqa: E402  账本指纹口径与 exit_rotator 保持同一份


def read_pool(path):
    """只取 proxies: 段里的节点名(顶层其它段如 proxy-groups 的 - name: 不算节点)。"""
    names = []
    in_proxies = False
    for line in open(path, encoding="utf-8", errors="replace"):
        s = line.rstrip("\n")
        if not s.strip() or s.lstrip().startswith("#"):
            continue
        if not s[:1].isspace():                # 顶层键: 决定后面是否还在 proxies 段
            in_proxies = s.split(":", 1)[0].strip() == "proxies"
            continue
        if not in_proxies:
            continue
        m = re.match(r"^\s*-\s+name:\s*(.+)$", s)
        if m:
            names.append(m.group(1).strip().strip("\"'"))
    return names


def print_by_node(shown, buckets, used):
    """逐节点一行(按池内顺序, 即轮转顺序): 节点 -> 所属桶前缀/loc — 小欧 2026-11-21"""
    print("  #   节点                     前缀                 loc  备注")
    print("  " + "-" * 78)
    for i, n in enumerate(shown, 1):
        b = buckets.get(n)
        if not b:
            print("  %-3d %-24s %-20s %-4s %s" % (i, n, "(未普查)", "-", "跑 _survey_buckets.py --tsv 补"))
            continue
        key = "%s|%s" % (b["prefix"], b["loc"])
        tail = "最近 %d 次已用" % gate.BUCKET_HISTORY_SIZE if key in used else ""
        print(("  %-3d %-24s %-20s %-4s %s" % (i, n, b["prefix"], b["loc"], tail)).rstrip())


def main():
    ap = argparse.ArgumentParser(description="统计当前节点池的出口桶分布(离线)")
    ap.add_argument("pool", nargs="?", default=os.path.join(ROOT, "mihomo", "config.yaml"),
                    help="池文件, 默认 mihomo\\config.yaml")
    ap.add_argument("--tsv", default=os.path.join(WORK_DIR, "buckets.tsv"), help="桶普查快照")
    ap.add_argument("--alive", default="", help="只看存活节点(每行 延迟ms\\t名称)")
    ap.add_argument("--by-node", action="store_true", help="逐节点一行(池内顺序), 不按桶分组")
    args = ap.parse_args()

    if not os.path.exists(args.pool):
        print("池文件不存在: %s" % args.pool)
        return 2
    if not os.path.exists(args.tsv):
        print("缺少桶普查快照 %s, 先跑 _survey_buckets.py --tsv" % args.tsv)
        return 2

    names = read_pool(args.pool)
    alive = read_delay(args.alive) if args.alive else {}
    buckets = read_buckets(args.tsv)
    used = set(gate.bucket_history_keys())

    shown = [n for n in names if not args.alive or n in alive]
    groups = {}
    missing = []
    for n in shown:
        b = buckets.get(n)
        if not b:
            missing.append(n)
            continue
        groups.setdefault((b["prefix"], b["loc"]), []).append(n)

    print("池文件      : %s" % os.path.relpath(args.pool, ROOT))
    if args.alive:
        print("存活过滤    : %s (存活 %d 个)" % (os.path.relpath(args.alive, ROOT), len(shown)))
    print("桶快照      : %s (%s)" % (os.path.relpath(args.tsv, ROOT),
                                     datetime.datetime.fromtimestamp(
                                         os.path.getmtime(args.tsv)).strftime("%Y-%m-%d %H:%M")))
    print("节点        : %d 个 (有桶记录 %d, 未普查 %d)"
          % (len(shown), len(shown) - len(missing), len(missing)))
    print("互不相同的桶: %d 个" % len(groups))
    print()
    if args.by_node:
        print_by_node(shown, buckets, used)
    else:
        print("  前缀                 loc  桶内节点")
        print("  " + "-" * 76)
        for key in sorted(groups, key=lambda k: (k[1] or "", k[0] or "")):
            nodes = groups[key]
            tail = "  <- 最近 %d 次已用" % gate.BUCKET_HISTORY_SIZE if ("%s|%s" % key) in used else ""
            print("  %-20s %-4s %d 个: %s%s"
                  % (key[0], key[1], len(nodes), ", ".join(nodes), tail))
        if missing:
            print("  %-20s %-4s %d 个: %s" % ("(未普查)", "-", len(missing), ", ".join(missing)))
    print()

    pool_keys = {"%s|%s" % k for k in groups}
    blocked = pool_keys & used
    print("最近 %d 次账本: 占用 %d 个桶, 其中落在现池 %d 个 -> 现在可换的新桶 %d 个"
          % (gate.BUCKET_HISTORY_SIZE, len(used), len(blocked), len(pool_keys) - len(blocked)))
    if pool_keys and len(pool_keys) - len(blocked) == 0:
        print("  池内桶已被账本占满: 换桶会 6 轮全失败, 先 exit_rotator.py --reset-history 或重建池")
    elif pool_keys and len(pool_keys) - len(blocked) == 1:
        print("  只剩 1 个可用桶, 该桶节点失联就换不出去: 建议重建池补进更多不同桶")
    if missing:
        print("  未普查节点不参与换桶判定: 跑 _survey_buckets.py --tsv 刷新快照")
    return 0


if __name__ == "__main__":
    sys.exit(main())
