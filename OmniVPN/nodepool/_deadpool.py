"""死点池: 记录实测失败的节点, 每次重建时先注入复测, 活了回池, 连续 5 死彻底清除。 — 小欧 2026-11-12

免费节点生生死死(实测: 入池时全活的节点次日就有一半失联, 过几天又复活), 一次性淘汰浪费。
本脚本给流水线补两步:
  revive  —— 把死点池的原始 URI 追加进 tls_ok.txt(跳过 TCP/TLS 预筛, 直接进 mihomo 实测),
             同时落本次注入清单 deadpool_inject.txt 供结算用;
  record  —— 实测结算: 注入且实测通过 = 复活(移出池); 注入仍失败 = 失败次数+1, 连续 5 次
             彻底清除; 本轮新失败的新鲜节点 = 入池。

池文件为 log 目录下 deadpool.txt, 每行: 失败次数<TAB>最近失败日期<TAB>原始URI (URI 不含 TAB)。
用法:
  python _deadpool.py revive   <tls_ok.txt> <inject_out>
  python _deadpool.py record   <nodes_all.yaml.map.txt> <good_all.txt> <reachable.txt> <inject_file>
"""
import os
import sys
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORK_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "log")   # 源码 nodepool\, 产物 log\
DEADPOOL = os.path.join(WORK_DIR, "deadpool.txt")

INJECT_CAP = 300     # 单次注入上限: 死点全测太拖第 6 步(每节点最多 8s), 300 条约 3 分钟
PURGE_AT = 5         # 连续失败次数达到即彻底清除


def norm_scheme(s):
    """hy2 与 hysteria2 是同一种协议的两个叫法, 统一归一(节点 key 对齐用)。"""
    return "hysteria2" if s in ("hy2", "hysteria2") else s


def uri_key(uri):
    """URI -> (协议, host, port); 解析失败返回 None。复用 _parse_test 的解析(DRY)。"""
    sys.path.insert(0, SCRIPT_DIR)
    from _parse_test import parse_line
    r = parse_line(uri)
    if not r:
        return None
    scheme, host, port, _ = r
    return (norm_scheme(scheme), (host or "").lower(), port)


def load_pool():
    """[(count, date_str, uri)]; 坏行忽略。"""
    rows = []
    if not os.path.exists(DEADPOOL):
        return rows
    for line in open(DEADPOOL, encoding="utf-8-sig", errors="replace"):
        parts = line.rstrip("\n").split("\t")
        if len(parts) != 3 or not parts[2].strip():
            continue
        try:
            rows.append((int(parts[0]), parts[1], parts[2]))
        except ValueError:
            continue
    return rows


def save_pool(rows):
    rows.sort(key=lambda r: (r[0], r[1]))   # 失败少/新失败的在前, 注入优先复活它们
    with open(DEADPOOL, "w", encoding="utf-8", newline="\n") as f:
        for count, d, uri in rows:
            f.write("%d\t%s\t%s\n" % (count, d, uri))


def read_keys_and_lines(map_path, good_path):
    """读实测结果: 返回 (good_keys, dead_keys, all_keys)。
    map 行: name<TAB>type<TAB>server:port<TAB>remark; good 行: ms<TAB>name。"""
    good_names = set()
    if os.path.exists(good_path):
        for line in open(good_path, encoding="utf-8", errors="replace"):
            p = line.rstrip("\n").split("\t")
            if len(p) == 2:
                good_names.add(p[1].strip())
    good_keys, dead_keys = set(), set()
    for line in open(map_path, encoding="utf-8", errors="replace"):
        p = line.rstrip("\n").split("\t")
        if len(p) < 3:
            continue
        name, typ, hostport = p[0], p[1], p[2]
        host, _, port = hostport.rpartition(":")
        if not host or not port.isdigit():
            continue
        key = (norm_scheme(typ), host.lower(), int(port))
        (good_keys if name in good_names else dead_keys).add(key)
    return good_keys, dead_keys


def read_reachable(path):
    """reachable.txt: scheme<TAB>host<TAB>port<TAB>源<TAB>URI -> {(协议,host,port): URI}"""
    m = {}
    for line in open(path, encoding="utf-8", errors="replace"):
        p = line.rstrip("\n").split("\t")
        if len(p) >= 5 and p[2].isdigit():
            m[(norm_scheme(p[0]), p[1].lower(), int(p[2]))] = p[4]
    return m


def cmd_revive(tls_ok, inject_out):
    rows = load_pool()
    if not rows:
        open(inject_out, "w", encoding="utf-8", newline="\n").write("")
        print("死点池为空, 无注入")
        return 0
    pick = sorted(rows)[:INJECT_CAP]
    existing = set()
    if os.path.exists(tls_ok):
        existing = {l.strip() for l in open(tls_ok, encoding="utf-8", errors="replace")}
    injected = []
    with open(tls_ok, "a", encoding="utf-8", newline="\n") as f:
        for _, _, uri in pick:
            if uri in existing:
                continue
            f.write(uri + "\n")
            injected.append(uri)
    open(inject_out, "w", encoding="utf-8", newline="\n").write(
        "".join(u + "\n" for u in injected))
    print("死点池 %d 条, 本次注入复测 %d 条(上限 %d)" % (len(rows), len(injected), INJECT_CAP))
    return 0


def cmd_record(map_path, good_path, reachable_path, inject_file):
    today = date.today().isoformat()
    good_keys, dead_keys = read_keys_and_lines(map_path, good_path)
    reach = read_reachable(reachable_path) if os.path.exists(reachable_path) else {}
    pool = load_pool()
    by_uri = {u: (c, d) for c, d, u in pool}

    revived, failed, purged, kept = [], [], [], 0
    purged_keys = set()
    if os.path.exists(inject_file):
        for line in open(inject_file, encoding="utf-8", errors="replace"):
            uri = line.strip()
            if not uri:
                continue
            key = uri_key(uri)
            count, old_d = by_uri.get(uri, (0, ""))
            if key and key in good_keys:
                revived.append(uri)
                by_uri.pop(uri, None)
            elif key and key in dead_keys:
                c = count + 1
                if c >= PURGE_AT:
                    purged.append(uri)
                    purged_keys.add(key)
                    by_uri.pop(uri, None)
                else:
                    by_uri[uri] = (c, today)
                    failed.append((c, uri))
            else:
                by_uri[uri] = (count, old_d or today)   # 没进本轮实测(转换被跳过等), 原样保留
                kept += 1

    # 新失败的新鲜节点入池(池里还没有同 key 的才加; 本轮刚清除的不回锅)
    pool_keys = {uri_key(u) for u in by_uri}
    fresh_new = []
    for key in dead_keys:
        if key in pool_keys or key in purged_keys:
            continue
        uri = reach.get(key)
        if uri:
            by_uri[uri] = (1, today)
            fresh_new.append(uri)

    rows = [(c, d, u) for u, (c, d) in by_uri.items()]
    save_pool(rows)
    print("死点池结算: 复活 %d, 仍死 %d(加重), 清除 %d(连续 %d 死), 新增 %d, 原样保留 %d, 池现有 %d 条"
          % (len(revived), len(failed), len(purged), PURGE_AT, len(fresh_new), kept, len(rows)))
    for u in purged[:5]:
        print("  清除: %s" % u[:90])
    return 0


def main():
    args = sys.argv[1:]
    if len(args) >= 1 and args[0] == "revive" and len(args) == 3:
        return cmd_revive(args[1], args[2])
    if len(args) >= 1 and args[0] == "record" and len(args) == 5:
        return cmd_record(args[1], args[2], args[3], args[4])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
