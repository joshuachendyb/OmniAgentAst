"""从 nodes_all.yaml 里只挑出验证通过的节点, 生成精简 nodes.yaml(带备注注释)。 — 小欧 2026-11-11

输入:
  nodes_all.yaml      全量内联节点
  nodes_all.yaml.map.txt  名称 -> 类型/服务器/端口/原备注
  good_nodes*.txt     验证结果 (每行 "延迟ms\\t名称")
输出:
  nodes.yaml          只含可用节点, 每个节点上方一行注释

注释里写明"类型 + 服务器:端口 + 原备注", 这样 config.yaml 里看到 N461 也不会一头雾水。
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORK_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "log")   # 源码 nodepool\, 产物 log\ — 小欧-2026-11-11
ALL = os.path.join(WORK_DIR, "nodes_all.yaml")
MAP = ALL + ".map.txt"
OUT = os.path.join(WORK_DIR, "nodes.yaml")


def parse_map():
    m = {}
    if not os.path.exists(MAP):
        return m
    for line in open(MAP, encoding="utf-8"):
        parts = line.rstrip("\n").split("\t")
        if len(parts) >= 4:
            m[parts[0]] = parts[1:]
    return m


def parse_blocks(path):
    """返回 [(name, [lines...])], 每个 block 含其上方紧邻的注释行。"""
    blocks = []
    pending = []
    cur = None
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if line.lstrip().startswith("#"):
            pending.append(line)
            continue
        m = re.match(r"^\s*-\s+name:\s*(.+)$", line)
        if m:
            if cur:
                blocks.append(cur)
            cur = (m.group(1).strip().strip("\"'"), pending + [line])
            pending = []
            continue
        if cur is not None:
            cur[1].append(line)
    if cur:
        blocks.append(cur)
    return blocks


def read_good(paths):
    """合并多份验证结果, 同名取最小延迟。"""
    good = {}
    for p in paths:
        if not os.path.exists(p):
            continue
        for line in open(p, encoding="utf-8", errors="replace"):
            line = line.rstrip("\n")
            if "\t" not in line:
                continue
            a, b = line.split("\t", 1)
            try:
                ms = int(a)
            except ValueError:
                continue
            name = b.strip()
            if name not in good or ms < good[name]:
                good[name] = ms
    return good


def main():
    good = read_good(sys.argv[1:] or [os.path.join(WORK_DIR, "good_nodes.txt")])
    if not good:
        print("没有可用节点结果, 中止")
        return 2

    mp = parse_map()
    blocks = parse_blocks(ALL)
    kept = []
    for name, lines in blocks:
        if name not in good:
            continue
        info = mp.get(name)
        if info:
            typ, addr, remark = info[0], info[1], (info[2] if len(info) > 2 else "")
            note = "  # [%sms] %s %s %s" % (good[name], typ, addr, remark)
        else:
            note = "  # [%sms] %s" % (good[name], name)
        kept.append(note.rstrip())
        # 原注释行不再重复保留, 只留内容行
        kept.extend(l for l in lines if not l.lstrip().startswith("#"))

    text = "proxies:\n" + "\n".join(kept).rstrip("\n") + "\n"
    open(OUT, "w", encoding="utf-8", newline="\n").write(text)

    n_nodes = sum(1 for l in kept if re.match(r"^\s*-\s+name:", l))
    print("可用 %d 个, 已写 %s" % (n_nodes, OUT))
    for name, ms in sorted(good.items(), key=lambda x: x[1]):
        info = mp.get(name, ["?", "?", ""])
        print("  %5dms  %-6s %-9s %-24s %s" % (ms, name, info[0], info[1], (info[2] if len(info) > 2 else "")[:36]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
