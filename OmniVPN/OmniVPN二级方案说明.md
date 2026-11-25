# OmniVPN 二级方案说明

> 文档名称: OmniVPN二级方案说明.md + 商量 + 2026-11-25
> 编写人: 商量  签名: 商量  日期: 2026-11-25

---

## 1 与单级的差异

### 1.1 流量路径不同

**单级**：本机 → mihomo → 出口节点（vless，直连裸线）→ 目标网站。出口节点直接暴露在公网，易被识别封禁。

**二级**：本机 → mihomo → **一级跳板**（意大利米兰 ss，直连裸线）→ **二级出口**（vless，经一级中转）→ 目标网站。目标网站看到的是二级出口节点 IP，一级跳板只作中转不暴露。

```
单级:  本机 ──系统代理──> mihomo ──节点(直连)──> 目标网站
二级:  本机 ──系统代理──> mihomo ──一级跳板(意大利米兰ss)──> 二级出口(vless)──> 目标网站
```

### 1.2 配置结构不同

| 项目 | 单级 | 二级 |
|------|------|------|
| PROXY 组 | select，成员 = 节点 + Auto + DIRECT | select，成员 = `[Auto, DIRECT, INDONESIA_POOL, EXIT_POOL]` |
| 出口池 | 无独立池，PROXY 直接选节点 | 二级 `EXIT_POOL`（313 个 vless，全带 `dialer-proxy: INDONESIA_POOL`） |
| 跳板池 | 无 | 一级 `INDONESIA_POOL`（10 个意大利米兰 ss，直连裸线） |
| 节点数 | 17 个 | 一级 10 + 二级 313 |
| 出口桶数（实测） | 6 个 | **110 个** |
| 出口链路 | 节点直连裸线 | 节点经一级中转 |

### 1.3 收益与代价

**收益**：
- 出口桶覆盖大幅扩大：6 → 110 桶，撞 429 时换桶空间充足。
- 隐藏真实出口链路：目标网站只见二级出口 IP，一级跳板不暴露。

**代价**：
- 链路加长一跳，延迟上升（二级节点实测延迟最小 384ms / 中位 1024ms / 最大 4594ms / 平均 1360ms）。
- 两级都需存活才通：任一环节失联则整条链路断，故障点变多。

### 1.4 实测数据

- 二级节点可达性（delay 接口并发测，正式端口 9090）：313 个，**通 240（76.7%），不通 73**。
- 二级桶数（分批实测全部 240 个通节点）：**去重桶 110 个**，节点最集中 `193.29.139.0/24|NL`（荷兰）53 节点、`80.174.118.0/24|IT`（意大利）37 节点，其余 108 桶各 1~5 节点覆盖 US/FR/GB/DE/SG/CH/CA/JP/KR/HK/SE/AT/PL/BG/IL/ES 等。
- 结果落盘：`log\pool2_live_reach.json`（可达性）、`log\pool2_live_buckets2.json`（桶数）。

## 2 二级的实现技术要领

### 2.1 配置文件结构（mihomo\config.yaml）

端口：`7890`（HTTP 混合代理）/ `7891`（SOCKS）/ `127.0.0.1:9090`（控制器），模式 `Rule`。`proxies:` 段内联全部节点，`proxy-groups:` 段定义 4 个组：

| 组名 | 类型 | 成员数 | 说明 |
|------|------|--------|------|
| PROXY | select | 4 | 顶层出口选择：`[Auto, DIRECT, INDONESIA_POOL, EXIT_POOL]` |
| Auto | url-test | 313 | 自动选最快的二级节点，全部经一级中转 |
| INDONESIA_POOL | select | 10 | 一级跳板（IDN-01~10，意大利米兰 ss，端口 19999，直连裸线） |
| EXIT_POOL | select | 313 | 二级出口（N01~N1364，vless，端口 443，全带 `dialer-proxy: INDONESIA_POOL`） |

**关键**：二级节点必须带 `dialer-proxy: INDONESIA_POOL`（已验证 313/313），这是"经一级中转"的实现机制。一级节点不带 dialer-proxy（直连裸线）。

> ⚠️ **命名与实际地理不符（严谨提示）**：组名 `INDONESIA_POOL` 虽叫"Indonesia"，但一级跳板实际 server IP 为 `202.50.253.x`，经 ipinfo.io 权威核实归属 **意大利米兰（country=IT，city=Milan，org=AS30088 GTHost）**，并非印尼。组名沿用了历史命名，实际节点在意大利。文档中描述地理归属一律以实测 IP 为准（意大利米兰），组名 `INDONESIA_POOL` 仅作程序标识符使用。

### 2.2 启动默认走二级

PROXY 组**无默认 now** → mihomo 启动时 select 组默认选中第一个成员 = **Auto**。Auto 组是 url-test，313 成员全带 `dialer-proxy: INDONESIA_POOL`（经一级中转）→ **启动即走二级出口**。

四条路径对应级别：

| PROXY 选中 | 级别 | 说明 |
|-----------|------|------|
| Auto（默认） | 二级 | url-test 自动选最快的二级节点，经一级中转 |
| EXIT_POOL | 二级 | 313 个二级出口节点，全经一级中转 |
| INDONESIA_POOL | 一级 | 10 个意大利米兰节点直出，不串二级 |
| DIRECT | 直连 | 不走节点 |

### 2.3 换桶必踩的坑：PROXY=Auto 会覆盖 EXIT_POOL 切换

Auto 组是 `url-test`，会自动选最快的二级节点。**只要 PROXY=Auto，切换 EXIT_POOL 的 now 就不生效**——出口恒为 Auto 自动选的节点（实测曾固定指向 62.210.124.146 法国，所有探测出口都指向它）。

**结论**：要正确换二级桶，**PROXY 必须直接选 EXIT_POOL**（不是 Auto）。

### 2.4 换桶正确姿势

1. 先确保 `PROXY = EXIT_POOL`（若为 Auto，先切到 EXIT_POOL）；
2. 再切换 `EXIT_POOL` 的 `now` 到目标二级节点；
3. 出口才随二级选中节点变化，换桶生效。

## 3 二级的各个相关 bat / ps1 / 配置文件是如何配合的

### 3.1 文件总览（根目录 + mihomo\ + nodepool\）

| 文件 | 角色 | 对二级的支持 |
|------|------|-------------|
| `proxy-on.bat` / `proxy-on.ps1` | 开代理（启动内核 + 设系统代理 + 验证出口） | ✅ 支持（读 config.yaml 渲染两级链路） |
| `proxy-off.bat` / `proxy-off.ps1` | 关代理（取消系统代理，可选停内核） | ✅ 支持（不依赖组结构） |
| `proxy-switch.bat` / `proxy-switch.ps1` | 换出口桶（撞 429 时双击） | ⚠️ 需注意（见 3.3，默认 `--group PROXY` 在二级下不换二级桶） |
| `rebuild-pool.bat` / `rebuild-pool.ps1` | 全量重建节点池（11 步） | ❌ 会回退单级（见 3.5，`_rebuild_config.py` 写回单级结构） |
| `update-pool-quick.bat` / `update-pool-quick.ps1` | 轻量巡检（现池复验 + 死点复活） | ✅ 支持（v1.4 读当前生效 config.yaml 含二级链） |
| `exit_probe.py` | 出口探测器（桶判定权威实现） | ✅ 支持（按出口 IP 判桶，与级别无关） |
| `exit_rotator.py` | 换桶执行器 | ✅ 支持（v2.0 已加 `--mode exit/indonesia/both`） |
| `mihomo\config.yaml` | 正式运行配置（两级池） | 两级结构本体 |
| `mihomo\config-expand-test.yaml` | 两级源配置（复制为正式 config.yaml 用） | 两级结构源 |
| `mihomo\config-single-backup-20261125_164726.yaml` | 原单级配置备份（回滚用） | 单级备份 |
| `log\pool2_live_reach.json` | 二级可达性实测结果 | 实测数据 |
| `log\pool2_live_buckets2.json` | 二级桶数实测结果 | 实测数据 |

### 3.2 开代理链路：proxy-on.bat → proxy-on.ps1 → config.yaml

```
proxy-on.bat ──> proxy-on.ps1 (默认 Port=7890)
                   │
                   ├─[1] 启动 mihomo-slim.exe -d mihomo (读 config.yaml, 端口未监听才启)
                   ├─[2] 设 WinInet 系统代理 → 127.0.0.1:7890
                   ├─[3] 节点池清单: nodepool\_bucket_stats.py --by-node (读 config.yaml + log\buckets.tsv)
                   ├─[4] 代理链路: 读 9090 /proxies/PROXY, 渲染两级串联
                   │         (PROXY=EXIT_POOL/Auto → 打"一级 INDONESIA_POOL + 二级 EXIT_POOL"两级)
                   ├─[5] 出口对照: exit_rotator.py --verify (直连 vs 代理出口)
                   └─[6] 换桶备忘
```

**二级下工作正常**：PROXY 无默认 now → 启动默认选 Auto（url-test，313 成员全带 `dialer-proxy: INDONESIA_POOL`）→ **走二级**；[4] 段读 9090 渲染两级串联（`INDONESIA_POOL` 一级 + `EXIT_POOL` 二级），[5] 段出口对照验证实际出口。

### 3.3 换桶链路：proxy-switch.bat → proxy-switch.ps1 → exit_rotator.py（二级下需注意）

```
proxy-switch.bat ──> proxy-switch.ps1 (默认 -Group PROXY, -Tries 6)
                       │
                       ├─[1] 前置: 7890 未跑则调 proxy-on.ps1
                       ├─[2] 换桶前出口: exit_rotator.py --verify
                       ├─[3] 轮换: exit_rotator.py --target mihomo --wait --group PROXY (最多 6 轮)
                       └─[4] 换桶后出口复验 + 报成功/失败
```

**⚠️ 二级下的关键问题**：`proxy-switch.ps1` 默认传 `--group PROXY`，而 `exit_rotator.py` 的 `--group` **优先于 mode**。此时轮换的是 **PROXY 组**（成员 `[Auto, DIRECT, INDONESIA_POOL, EXIT_POOL]`），`switch_group` 会跳过 DIRECT/REJECT/Auto，在 **INDONESIA_POOL 与 EXIT_POOL 之间切换**——这**不能**换二级出口桶（EXIT_POOL 内部 313 个成员不动，出口不变）。

**二级下正确换桶姿势**：直接用 `exit_rotator.py --mode exit`（默认轮换 EXIT_POOL）：

```powershell
# 二级下换出口桶: 轮换 EXIT_POOL 的 313 个成员(经一级中转)
python exit_rotator.py --target mihomo --mode exit --wait --proxy http://127.0.0.1:7890
# 一级小转(换跳板): 轮换 INDONESIA_POOL 的 10 个成员
python exit_rotator.py --target mihomo --mode indonesia --wait --proxy http://127.0.0.1:7890
# 两级都转: 先转二级再转一级
python exit_rotator.py --target mihomo --mode both --wait --proxy http://127.0.0.1:7890
```

> 说明：`exit_rotator.py` v2.0 已支持两级轮转（`--mode exit/indonesia/both`，`--exit-group` / `--indonesia-group` 默认 EXIT_POOL / INDONESIA_POOL）。但 `proxy-switch.ps1` 仍传 `--group PROXY`，在二级下会走 PROXY 组轮换而非二级池轮换。**建议后续把 proxy-switch.ps1 默认改为 `--mode exit`** 以对齐二级换桶口径（现文档标注为待办）。

### 3.4 轻量巡检：update-pool-quick.bat → update-pool-quick.ps1 → _verify_current.py

```
update-pool-quick.bat ──> update-pool-quick.ps1 (v1.4)
                            │
                            ├─[1] 现池复验: nodepool\_verify_current.py --config mihomo\config.yaml
                            │         (临时端口 7897/9097, 逐节点 delay 测活, 含 dialer-proxy 二级链)
                            ├─[2] 现池桶分布: nodepool\_bucket_stats.py --alive good_pool.txt
                            ├─[3] 死点池复活注入: _deadpool.py revive
                            ├─[4] 死点 URI 转 YAML: _uri2yaml.py
                            ├─[5] 死点 mihomo 实测: _verify_nodes.py (临时端口 7897)
                            └─[6] 死点池结算: _deadpool.py record
```

**二级下工作正常**：v1.4 已改为读**当前生效的 config.yaml（含二级链）**，不再读旧的 nodes_ordered.yaml；`_verify_current.py` 吃完整 config（含 proxy-groups 与 dialer-proxy），只改端口不拼组，测到的 delay 就是实际换桶时走的链路。**只复验不写回配置**，不破坏二级结构。

### 3.5 全量重建：rebuild-pool.bat → rebuild-pool.ps1 → _rebuild_config.py（⚠️ 会回退单级）

```
rebuild-pool.bat ──> rebuild-pool.ps1 (v1.5, 11 步)
                       ├─[1/11] 抓订阅 _fetch2.py
                       ├─[2/11] 解析去重+裸线TCP筛 _parse_test.py
                       ├─[3/11] TLS握手筛 _tls_probe.py
                       ├─[4/11] 死点复活注入 _deadpool.py revive
                       ├─[5/11] 转YAML _uri2yaml.py
                       ├─[6/11] mihomo逐节点实测 _verify_nodes.py (最慢)
                       ├─[7/11] 死点结算 _deadpool.py record
                       ├─[8/11] 只留可用 _filter_nodes.py
                       ├─[9/11] 测出口定桶 _survey_buckets.py
                       ├─[10/11] 按桶轮转排序 _order_nodes.py
                       ├─[11/11] 写回配置 _rebuild_config.py --apply
                       └─ 重启 mihomo (proxy-off -Stop + proxy-on)
```

**⚠️ 二级下的关键问题**：`_rebuild_config.py` 的 `GROUP_TAIL` 是**单级结构**——

```
GROUP_TAIL = PROXY: [Auto, DIRECT, 节点...] + Auto: url-test(节点...)
```

它只写回 `proxies` 与 `proxy-groups` 两段，**不含 INDONESIA_POOL / EXIT_POOL 两级组**。因此**全量重建后 config.yaml 会回退到单级**（PROXY 直接选节点，无一级跳板）。

**二级下重建后必须重新套用两级结构**：

```powershell
# 重建完成后, 重新套两级结构(备份当前单级配置后复制两级源配置)
Copy-Item mihomo\config.yaml mihomo\config-single-backup-<时间戳>.yaml
Copy-Item mihomo\config-expand-test.yaml mihomo\config.yaml
# 重启 mihomo 加载两级
powershell -ExecutionPolicy Bypass -File proxy-off.ps1 -Stop
powershell -ExecutionPolicy Bypass -File proxy-on.ps1
```

> 建议后续把 `_rebuild_config.py` 的 `GROUP_TAIL` 升级为两级结构（或重建后自动套用 config-expand-test.yaml），现文档标注为待办。

### 3.6 配置文件三者关系

| 文件 | 用途 | 说明 |
|------|------|------|
| `mihomo\config.yaml` | **正式运行配置**（两级池，当前生效） | proxy-on / proxy-off / proxy-switch / update-pool-quick 都读它 |
| `mihomo\config-expand-test.yaml` | **两级源配置**（未改动） | 复制为正式 config.yaml 用；重建回退单级后用它恢复两级 |
| `mihomo\config-single-backup-20261125_164726.yaml` | **单级备份**（回滚用） | 原单级 17 节点配置；如需回滚复制回 config.yaml 并重启 |

### 3.7 保证二级可用性的完整链条

```
[启动]   proxy-on.bat ──> config.yaml(两级) ──> PROXY 默认 Auto(二级) ──> 走二级出口 ✅
[换桶]   exit_rotator.py --mode exit ──> 轮换 EXIT_POOL(313) ──> 换二级出口桶 ✅
         (注: proxy-switch.ps1 默认 --group PROXY, 二级下需改用 --mode exit)
[巡检]   update-pool-quick.bat ──> _verify_current.py 读 config.yaml(含二级链) ──> 复验二级链路 ✅
[重建]   rebuild-pool.bat ──> _rebuild_config.py(单级) ──> 回退单级 ⚠️
         (重建后需 Copy-Item config-expand-test.yaml → config.yaml 恢复两级)
[回滚]   config-single-backup-20261125_164726.yaml ──> 复制回 config.yaml ──> 回单级
```

**可用性结论**：启动、换桶（用 `--mode exit`）、轻量巡检、出口验证四条链都支持二级；唯一会破坏二级的是**全量重建**（`_rebuild_config.py` 写回单级），重建后需重新套用 `config-expand-test.yaml` 恢复两级。

### 3.8 当前运行态（2026-11-25 18:49 实测）

- 正式实例 7890/9090 两级模式，**PROXY=EXIT_POOL**（走二级池）。
- EXIT_POOL now = **N314**，INDONESIA_POOL now = **IDN-08**。
- 出口：`167.88.63.0/24|US`。
- 系统代理：`ProxyEnable=1`，`ProxyServer=127.0.0.1:7890`（已启用）。
- 注意：mihomo 进程**仍在运行**（非停止态），若需真正重启需先 `Stop-Process -Name mihomo*`。

### 3.9 待办与建议

1. **proxy-switch.ps1 默认改 `--mode exit`**：当前默认 `--group PROXY` 在二级下轮换 PROXY 组（在 INDONESIA_POOL / EXIT_POOL 间切换），不能换二级出口桶；应默认用 `--mode exit`（轮换 EXIT_POOL）。
2. **_rebuild_config.py 升级两级结构**：当前 `GROUP_TAIL` 是单级，全量重建会回退单级；建议升级为含 INDONESIA_POOL / EXIT_POOL 的两级结构，或重建后自动套用 config-expand-test.yaml。
3. **73 个二级节点 delay 测不通**：N01/N03/N28/N48/N1364/N22/N37/N62/N41/N47/N58/N51/N96/N53/N63/N92/N76/N93/N79/N120/N95/N101/N119/N109/N111/N118/N142/N143/N171/N145/N146/N180/N148/N170/N178/N200/N166/N198/N214/N224/N217/N190/N193/N195/N234/N226/N203/N244/N207/N209/N232/N245/N255/N258/N261/N265/N270/N269/N263/N259/N286/N264/N275/N272/N302/N277/N289/N296/N295/N304/N299/N308/N313。delay 测不通可能为偶发超时，出口探测复验部分节点实际通，可择机复测。
