"""把内联节点清单写回 config.yaml / config-tun.yaml, 保留端口/TUN/DNS/规则不动。 — 小欧 2026-11-11

做法: 只替换 proxies 与 proxy-groups 两段, 头部(端口/TUN/DNS)和 rules 原样保留。
这样"换节点"与"改内核参数"彻底解耦, 改坏了也只影响节点段。

用法: python _rebuild_config.py <nodes.yaml> [--apply]
  不带 --apply 只做预演, 打印将要写入的规模。
"""
import os
import re
import shutil
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORK_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "log")   # 源码 nodepool\, 产物 log\ — 小欧-2026-11-11
MIHOMO_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "mihomo")

TARGETS = [
    os.path.join(MIHOMO_DIR, "config.yaml"),
]

GROUP_TAIL = """- name: PROXY
  type: select
  proxies:
  - Auto
  - DIRECT
%s
- name: Auto
  type: url-test
  proxies:
%s
  url: https://www.google.com/generate_204
  interval: 300
  tolerance: 50
"""


def node_names(nodes_text):
    return [m.group(1).strip()
            for m in re.finditer(r"^\s*-\s+name:\s*(.+)$", nodes_text, re.M)]


def rebuild(path, nodes_text, names, apply):
    lines = open(path, encoding="utf-8").read().splitlines()
    p_idx = g_idx = r_idx = None
    for i, l in enumerate(lines):
        s = l.strip()
        if s == "proxies:" and p_idx is None:
            p_idx = i
        elif s == "proxy-groups:" and g_idx is None:
            g_idx = i
        elif s == "rules:" and r_idx is None:
            r_idx = i
    if p_idx is None or g_idx is None or r_idx is None:
        print("  !! %s 结构不符(proxies/proxy-groups/rules 缺一), 跳过" % path)
        return False

    head = lines[:p_idx]
    rules = lines[r_idx:]

    sel_items = "\n".join("  - %s" % n for n in names)
    auto_items = "\n".join("  - %s" % n for n in names)
    groups = "proxy-groups:\n" + (GROUP_TAIL % (sel_items, auto_items))

    out = head + ["proxies:"] + [""] + nodes_text.splitlines() + \
          [""] + groups.splitlines() + [""] + rules

    text = "\n".join(out).rstrip("\n") + "\n"
    if apply:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        bak = path + ".bak-" + stamp
        shutil.copy2(path, bak)
        open(path, "w", encoding="utf-8", newline="\n").write(text)
        print("  已写 %s  节点 %d 个  备份 %s" % (os.path.basename(path), len(names), os.path.basename(bak)))
    else:
        print("  [预演] %s  头部 %d 行 + 节点 %d 个 + 规则 %d 行"
              % (os.path.basename(path), len(head), len(names), len(rules)))
    return True


def main():
    nodes_arg = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        WORK_DIR, "nodes_ordered.yaml")
    apply = "--apply" in sys.argv

    raw = open(nodes_arg, encoding="utf-8").read()
    if raw.lstrip().startswith("proxies:"):
        raw = raw.lstrip()[len("proxies:"):]
    nodes_text = raw.strip("\n")
    if not nodes_text.strip():
        print("节点文件为空, 中止")
        return 2

    names = node_names(nodes_text)
    print("节点文件: %s  节点 %d 个" % (os.path.basename(nodes_arg), len(names)))
    print()
    ok = 0
    for path in TARGETS:
        if rebuild(path, nodes_text, names, apply):
            ok += 1
    return 0 if ok == len(TARGETS) else 2


if __name__ == "__main__":
    sys.exit(main())
