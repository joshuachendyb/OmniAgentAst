# -*- coding: utf-8 -*-
# exit_rotator.py — gateway 出口切换适配器（给 --switch-cmd 直接调用）
# 编写人: 小欧    版本: v1.6    更新时间: 2026-11-12 02:30:00
#
# 修改历史（最新在最下）:
#   v1.0 2026-11-11 小欧 初版: warp/mihomo/tailscale/wg 四种 target, 桶判定复用 opcode225-gate.py
#   v1.1 2026-11-11 小欧 warp 重连后轮询 status 至 Connected(握手延迟曾误判失败);
#                       mihomo 控制器不可达时优雅降级 rc=2 不抛 traceback; 清理未用导入
#   v1.2 2026-11-11 小欧 mihomo 选组跳过内置 GLOBAL(Rule 模式下不控流量);
#                       切换前环形测活跳过死节点; /delay 两种返回形态都识别;
#                       旧出口身份未知(死节点)时新出口就绪即判成功
#   v1.3 2026-11-11 小欧 新增 v2rayn target: 改 guiNConfig.json 的 IndexId + 重启核心换节点;
#                       IndexId 必须写成带引号字符串(C# 侧为 string, 写数字会致整份配置
#                       反序列化失败而回落默认); 候选按库内顺序环形取, 逐个试到换出新桶
#   v1.4 2026-11-11 小欧 数据面只保留 mihomo: 删掉 warp/tailscale/wg/v2rayn 四个 target
#                       及其专属参数(--node/--tunnel/--conf/--v2rayn-dir/--port/--tries),
#                       连带删掉 subprocess/socket/sqlite3/re 依赖; mihomo 切换语义与返回码不变
#   v1.5 2026-11-12 小欧 exit_rotator 改 import: 被复用的模块由 opcode225-gate.py 更名
#                       exit_probe.py(可直接 import, 不再走 importlib 连字符 hack)
#   v1.6 2026-11-12 小欧 输出文案统一重排: 标签规范化([控制器]/[节点池]/[等待]), 措辞精确化
#                       (存活/失联、桶指纹), 结论行保留「换桶成功/失败」关键短语
#
# 用途:
#   gateway 撞 429(FreeUsageLimitError, 按出口 IP 记配额桶)后, 调本脚本换出口,
#   换到新桶(前缀/24·/48 + loc 变化)才返回 0, gateway 据此恢复发请求。
#   桶判定逻辑全部复用 exit_probe.py(exit_identity/wait_ip_change), 不重复实现。
#
# 用法:
#   python exit_rotator.py --verify                 # 只打印当前出口身份(桶)后退出
#   python exit_rotator.py --target mihomo          # Clash/mihomo API 轮换到组内下一节点
#   python exit_rotator.py --target mihomo --url http://127.0.0.1:9090 --secret xxx --group 节点选择
#   python exit_rotator.py --target mihomo --wait --proxy http://127.0.0.1:7890
#                                                   # 端口代理模式下用该代理观测出口身份
# 通用参数: --wait 等待桶变化(默认关); --ip-timeout 等待秒(默认 180); --delay 切后先等 N 秒
# 返回码: 0=已换到新桶  1=切换后桶未变  2=控制器不可达/参数缺失/切换失败

import argparse
import os
import sys
import time
import urllib.parse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# 复用 exit_probe 的桶判定(CF trace / exit_identity / wait_ip_change / make_client)
import exit_probe as gate


def switch_mihomo(ctrl: str, secret: str, group: str) -> bool:
    """Clash/mihomo 外部控制器: 组内轮换到当前节点的下一个(确定性循环, 无需状态文件).
    作者: 小欧 2026-11-11"""
    c = gate.make_client(timeout=30)
    try:
        hdr = {"Authorization": "Bearer %s" % secret} if secret else {}
        r = c.get(ctrl + "/proxies", headers=hdr)
        if r.status_code != 200:
            print("  [控制器] GET /proxies -> %s (外部控制器未开启、地址错误或鉴权失败)" % r.status_code)
            return False
        proxies = r.json().get("proxies", {})
        if not group:
            # 跳过 mihomo 内置 GLOBAL 组(Rule 模式下它不影响流量), 选第一个真实 Selector
            selectors = [k for k, v in proxies.items()
                         if v.get("type") == "Selector" and k != "GLOBAL"]
            if not selectors:
                print("  [节点池] 未发现可用 Selector 组")
                return False
            group = selectors[0]
            print("  [控制器] 自动选定组: %s" % group)
        entry = proxies.get(group)
        if not entry:
            print("  [控制器] 组不存在: %s" % group)
            return False
        now, all_nodes = entry.get("now"), entry.get("all") or []
        if now not in all_nodes or len(all_nodes) < 2:
            print("  [节点池] 组 %s 无可轮换节点 (当前选中 %s)" % (group, now))
            return False
        # 从当前节点的下一个开始环形找活节点(免费节点失联率高, 不测活会切进死胡同白等超时)
        idx = all_nodes.index(now)
        nxt = None
        for k in range(1, len(all_nodes)):
            cand = all_nodes[(idx + k) % len(all_nodes)]
            if cand in ("DIRECT", "REJECT", "Auto"):
                continue
            try:
                d = c.get(ctrl + "/proxies/" + urllib.parse.quote(cand, safe=""),
                          params={"url": "http://www.gstatic.com/generate_204", "timeout": 5000})
                if d.status_code != 200:
                    continue
                b = d.json() or {}
                # mihomo /delay 有两种返回形态: {"delay":N} 或完整代理对象(alive 字段)
                if b.get("delay") or b.get("alive") is True:
                    nxt = cand
                    break
            except Exception:
                continue
        if not nxt:
            print("  [节点池] 组 %s 内未发现存活节点" % group)
            return False
        r = c.put(ctrl + "/proxies/" + urllib.parse.quote(group, safe=""),
                  json={"name": nxt}, headers=hdr)
        if r.status_code not in (200, 204):
            print("  [控制器] 切换失败: PUT -> %s %s" % (r.status_code, r.text[:120]))
            return False
        print("  [切换] %s: %s -> %s" % (group, now, nxt))
        return True
    except Exception as e:  # 控制器不在/连接拒绝时优雅降级, 不抛 traceback
        print("  [控制器] 连接失败: %s" % str(e).splitlines()[-1])
        return False
    finally:
        c.close()


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="gateway 出口切换适配器(换 429 配额桶)")
    ap.add_argument("--verify", action="store_true", help="只打印当前出口身份(桶)后退出")
    ap.add_argument("--target", choices=["mihomo"], default="", help="切换后端, 目前只有 mihomo")
    ap.add_argument("--proxy", default="", help="观测出口用的代理(如 http://127.0.0.1:7890)")
    ap.add_argument("--url", default="http://127.0.0.1:9090", help="mihomo 外部控制器地址")
    ap.add_argument("--secret", default="", help="mihomo controller secret")
    ap.add_argument("--group", default="", help="mihomo Selector 组名(缺省自动选第一个)")
    ap.add_argument("--wait", action="store_true", help="等桶真的变了(/24·/48+loc)才返回 0")
    ap.add_argument("--ip-timeout", type=int, default=180)
    ap.add_argument("--delay", type=float, default=2.0, help="切换后先等 N 秒再观测")
    a = ap.parse_args()

    client = gate.make_client(proxy=a.proxy or None)

    if a.verify:
        ident = gate.exit_identity(client)
        client.close()
        print("当前出口: %s" % gate.fmt_identity(ident))
        return 0

    if not a.target:
        print("[错误] 缺 --target 或 --verify, 见 -h")
        client.close()
        return 2

    old = gate.exit_identity(client)
    print("切换前出口: %s" % gate.fmt_identity(old))

    if not switch_mihomo(a.url, a.secret, a.group):
        client.close()
        return 2

    if a.delay:
        time.sleep(a.delay)

    if a.wait:
        if not (old or {}).get("ip"):
            # 旧出口身份查不到(上一个节点是失联节点): 换完拿到可用出口即视为成功
            ident = gate.exit_identity(client)
            client.close()
            if ident and ident.get("ip"):
                print("当前出口: %s" % gate.fmt_identity(ident))
                print("换桶成功: 切换前出口身份不可得(失联节点), 新出口已就绪")
                return 0
            print("换桶失败: 新出口仍不可用")
            return 1
        ident = gate.wait_ip_change(client, old, a.ip_timeout, print)
        if not ident:
            ident = gate.exit_identity(client) or old
            client.close()
            print("当前出口: %s" % gate.fmt_identity(ident))
            print("换桶失败: 桶指纹未变, 仍在同一出口桶内, 请勿恢复发请求")
            return 1
    else:
        ident = gate.exit_identity(client) or old

    client.close()
    print("当前出口: %s" % gate.fmt_identity(ident))
    changed = gate.identity_key(ident) != gate.identity_key(old)
    print("换桶: %s" % ("成功" if changed else "失败 (桶指纹未变)"))
    return 0 if changed else 1


if __name__ == "__main__":
    sys.exit(main())
