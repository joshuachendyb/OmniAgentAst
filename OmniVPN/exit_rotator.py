# -*- coding: utf-8 -*-
# exit_rotator.py — gateway 出口切换适配器（给 --switch-cmd 直接调用）
# 编写人: 小欧    版本: v2.0    更新时间: 2026-11-22 10:00:00
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
#   v1.7 2026-11-21 小欧 换桶判定改为查历史账本(用户要求: 新桶要与最近 5 次的桶都不同):
#                       切换前的桶先记入历史, --wait 等到的桶必须避开最近 5 个桶才算换成功,
#                       成功后再入账; 新增 --reset-history 清空历史; --verify 附带历史列表
#   v1.8 2026-11-21 小欧 账本深度改 3(用户要求, 现池 7 个桶留 5 个太紧): 文案里的次数
#                       一律取 exit_probe.BUCKET_HISTORY_SIZE, 不再写死数字
#   v2.0 2026-11-22 小欧 两级池轮转: switch_mihomo 改名 switch_group(通用任意组环形轮换);
#                       新增 --mode {exit,indonesia,both} 决定轮转哪级池(exit=二级大转默认,
#                       indonesia=一级小转换跳板, both=先转二级再转一级); 新增 --exit-group/
#                       --indonesia-group 指定两级组名(默认 EXIT_POOL/INDONESIA_POOL);
#                       保留 --group 作单组覆盖(优先于 mode); 桶判定与历史账本仍复用 exit_probe
#
# 用途:
#   gateway 撞 429(FreeUsageLimitError, 按出口 IP 记配额桶)后, 调本脚本换出口,
#   换到新桶(前缀/24·/48 + loc 变化, 且不在最近几次用过的桶里)才返回 0,
#   gateway 据此恢复发请求。桶判定与历史账本全部复用 exit_probe.py
#   (exit_identity/wait_ip_change/bucket_history_*), 不重复实现。
#
# 用法:
#   python exit_rotator.py --verify                 # 打印当前出口身份(桶)+最近用过的桶后退出
#   python exit_rotator.py --reset-history          # 清空最近换桶历史(池子换过一批桶后重置)
#   python exit_rotator.py --target mihomo          # 二级大转: 轮换 EXIT_POOL 换出口(默认)
#   python exit_rotator.py --target mihomo --mode indonesia   # 一级小转: 换 INDONESIA_POOL 跳板
#   python exit_rotator.py --target mihomo --mode both        # 先转二级再转一级(两级都换)
#   python exit_rotator.py --target mihomo --url http://127.0.0.1:9090 --secret xxx --group 节点选择
#   python exit_rotator.py --target mihomo --wait --proxy http://127.0.0.1:7890
#                                                   # 端口代理模式下用该代理观测出口身份
# 通用参数: --wait 等待桶变化(默认关); --ip-timeout 等待秒(默认 180); --delay 切后先等 N 秒
# 返回码: 0=已换到账本以外的新桶  1=切换后仍在最近用过的桶内  2=控制器不可达/参数缺失/切换失败

import argparse
import os
import sys
import time
import urllib.parse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# 复用 exit_probe 的桶判定与最近 N 次桶账本(exit_identity / wait_ip_change / bucket_history_* / make_client)
import exit_probe as gate


def switch_group(ctrl: str, secret: str, group: str) -> bool:
    """Clash/mihomo 外部控制器: 指定 Selector 组内轮换到当前节点的下一个(确定性循环, 无需状态文件).
    适用于两级池任一组: 二级 EXIT_POOL(换出口) 或 一级 INDONESIA_POOL(换跳板).
    作者: 小欧 2026-11-11, 改名 2026-11-22"""
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
    ap.add_argument("--verify", action="store_true",
                    help="打印当前出口身份(桶)与最近 %d 次桶后退出" % gate.BUCKET_HISTORY_SIZE)
    ap.add_argument("--target", choices=["mihomo"], default="", help="切换后端, 目前只有 mihomo")
    ap.add_argument("--proxy", default="", help="观测出口用的代理(如 http://127.0.0.1:7890)")
    ap.add_argument("--url", default="http://127.0.0.1:9090", help="mihomo 外部控制器地址")
    ap.add_argument("--secret", default="", help="mihomo controller secret")
    ap.add_argument("--group", default="", help="mihomo Selector 组名(覆盖 mode, 单组轮转)")
    ap.add_argument("--mode", choices=["exit", "indonesia", "both"], default="exit",
                    help="轮转模式: exit=二级大转换出口(默认), indonesia=一级小转换跳板, "
                         "both=先转二级再转一级")
    ap.add_argument("--exit-group", default="EXIT_POOL", help="二级出口池组名")
    ap.add_argument("--indonesia-group", default="INDONESIA_POOL", help="一级跳板池组名")
    ap.add_argument("--wait", action="store_true",
                    help="等桶换成最近 %d 次以外的桶才返回 0" % gate.BUCKET_HISTORY_SIZE)
    ap.add_argument("--ip-timeout", type=int, default=180)
    ap.add_argument("--delay", type=float, default=2.0, help="切换后先等 N 秒再观测")
    ap.add_argument("--reset-history", action="store_true", help="清空最近换桶历史后退出")
    a = ap.parse_args()

    client = gate.make_client(proxy=a.proxy or None)

    if a.verify:
        ident = gate.exit_identity(client)
        client.close()
        print("当前出口: %s" % gate.fmt_identity(ident))
        keys = gate.bucket_history_keys()
        print("最近用过的桶: %d 个 (上限 %d): %s"
              % (len(keys), gate.BUCKET_HISTORY_SIZE, " | ".join(keys) if keys else "无记录"))
        return 0

    if a.reset_history:
        gate.bucket_history_clear()
        client.close()
        print("已清空换桶历史: %s" % gate.BUCKET_HISTORY_PATH)
        return 0

    if not a.target:
        print("[错误] 缺 --target 或 --verify, 见 -h")
        client.close()
        return 2

    old = gate.exit_identity(client)
    print("切换前出口: %s" % gate.fmt_identity(old))
    # 当前桶先记入历史: 新桶必须避开它和之前用过的桶
    recent = gate.bucket_history_push(old)
    keys = gate.bucket_history_keys(recent)
    print("最近用过的桶: %d 个 (上限 %d): %s"
          % (len(keys), gate.BUCKET_HISTORY_SIZE, " | ".join(keys) if keys else "无记录"))

    # 确定要轮转的组列表: --group 优先(单组覆盖), 否则按 mode 决定轮转哪级池
    if a.group:
        groups = [a.group]
        print("  [模式] 单组覆盖: %s" % a.group)
    elif a.mode == "indonesia":
        groups = [a.indonesia_group]
        print("  [模式] 一级小转(换跳板): %s" % a.indonesia_group)
    elif a.mode == "both":
        groups = [a.exit_group, a.indonesia_group]
        print("  [模式] 两级都转: %s -> %s" % (a.exit_group, a.indonesia_group))
    else:  # exit
        groups = [a.exit_group]
        print("  [模式] 二级大转(换出口): %s" % a.exit_group)

    for g in groups:
        if not switch_group(a.url, a.secret, g):
            client.close()
            return 2

    if a.delay:
        time.sleep(a.delay)

    if a.wait:
        if (old or {}).get("ip"):
            ident = gate.wait_ip_change(client, old, a.ip_timeout, print, avoid_keys=keys)
        else:
            # 旧出口身份查不到(上一个节点是失联节点): 新出口避开最近桶即算成功
            print("  [提示] 切换前出口身份不可得(失联节点), 新出口避开最近桶即算成功")
            ident = gate.exit_identity(client)
        if not ident:
            ident = gate.exit_identity(client) or old
            client.close()
            print("当前出口: %s" % gate.fmt_identity(ident))
            print("换桶失败: 出口仍落在最近用过的桶内或不可用, 请勿恢复发请求")
            return 1
    else:
        ident = gate.exit_identity(client) or old

    client.close()
    print("当前出口: %s" % gate.fmt_identity(ident))
    fresh = gate.bucket_is_fresh(ident, recent)
    if fresh:
        gate.bucket_history_push(ident)
    print("换桶: %s" % ("成功" if fresh else "失败 (落回最近用过的桶)"))
    return 0 if fresh else 1


if __name__ == "__main__":
    sys.exit(main())
