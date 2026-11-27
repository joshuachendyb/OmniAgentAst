# OmniVPN 一级方案说明

> 文档名称: OmniVPN一级方案说明.md + 商量 + 2026-11-28
> 编写人: 商量  签名: 商量  日期: 2026-11-28
> 说明: 本文档为**一级方案**（出口节点直连裸线，无二级跳板）的完整说明。二级方案见 `OmniVPN二级方案说明.md`。

---

## 1 方案背景与研究结论

OpenCode 免费层的配额按出口 IP 网段记账。实测结论：同一个出口 IP 上换 session、换 UA 都仍然 429（`FreeUsageLimitError`），只有换出口 IP 才能换配额。因此撞 429 时的正确动作只有一个——把出口切到另一个节点，双击一下即可。

判定"出口换没换"的观测点是 Cloudflare trace（`https://www.cloudflare.com/cdn-cgi/trace`）。trace 返回的 `ip=` 是服务端实际看到的地址，opencode.ai 与 www.cloudflare.com 在同一张 CF 网络上，所以这个观测点最接近真实情况。出口桶的指纹由**前缀（IPv4 折 /24、IPv6 折 /48）**和**地区（loc）**组成，判定硬标准只有一条：**前缀变没变**——前缀变了就是新桶；loc 是随行的地区标注（换节点时通常跟着一起变，可佐证出口真的换了，但不单独作判桶依据）；尾号永远不算（CGNAT 场景尾号一直在变，前缀不变就还是同一个桶）。ipv4 与 ipv6 的区别只是前缀折算规则不同（/24 对 /48），不是第三条判定项。

只要求"和当前桶不同"不够：池内节点少时来回切会切回刚用完的桶，配额照旧是空的。所以换桶口径是**新桶要与最近 3 次用过的桶都不同**。历史账本落在 `log\bucket_history.json`（按最近在前、同桶只留一条、最多 3 条），每次换桶前把当前桶记入账本，等到的新桶不在账本里才算换桶成功、成功后入账。账本深度取 3 是因为当初现池可用 11 个互不相同的桶（15 个节点），留 3 条后还有 8 个候选桶，换桶空间充足；池内可用桶少于 4 个时可能出现"怎么切都在最近 3 次里"，此时执行 `python exit_rotator.py --reset-history` 清空账本再换。**注意**：上述 11 桶/8 候选是 2026-11-20 重建时的数据；当前一级配置实测只剩 **2 个互不相同的桶**（见 3.5），换桶空间严重不足，需重建一级节点池。

## 2 mihomo 内核：是什么、提供什么

mihomo 是 Clash Meta 内核的延续版（Mihomo Meta），Go 语言编写的单文件代理内核，上游源码在 GitHub 仓库 **https://github.com/MetaCubeX/mihomo**，发布页 **https://github.com/MetaCubeX/mihomo/releases**。

本目录当前的 `mihomo-slim.exe` 是**官方 release v1.19.34（2026-11-11 发布）的 Windows amd64 原版二进制**：下载 `mihomo-windows-amd64-v1.19.34.zip`（21.35 MB），解压得 `mihomo-windows-amd64.exe`（58.3 MB，go1.26.11 编译，Use tags: with_gvisor）。因为脚本（`proxy-on.ps1`、`nodepool\_verify_nodes.py`、`nodepool\_survey_buckets.py`）都按 `mihomo-slim.exe` 这个文件名定位内核，装回时沿用该文件名，内容不再裁剪：TUN、gvisor、WireGuard、QUIC 等模块都在，只是本方案不用，功能与旧精简版等价。

历史版本曾是按同一 tag 自编的精简版（约 47.8 MB，`-s -w` 去符号、裁掉用不到的模块）。该自编件的源码目录 `D:\Downloads\mihomo-src\` 已不在本机（2026-11-20 核实），需要精简体积时按 §5.2 重新取源码编译，否则直接用官方包最省事。

它在本方案里提供四项能力：

**本地代理端口（一级 7892）**。HTTP 混合代理口，浏览器、系统代理、命令行程序都从这里进出。流量路径是：请求进入 7892 → mihomo 按当前选中的节点转发 → 节点服务器作为出口访问目标网站。

**外部控制器 API（一级 9092）**。这是整套换桶方案的支点。控制器提供 REST 接口：`GET /proxies` 列出代理组和节点，`PUT /proxies/PROXY` 切换选中节点（不重启进程、不断连接管理），`GET /proxies/<节点>/delay` 对单个节点测活。换桶脚本就是靠这三个接口实现"确定性轮换"的，全程不需要重启 mihomo。

**节点内联配置**。所有节点直接写在 `mihomo-single\config.yaml` 的 `proxies:` 段里（当前 17 个免费节点，单级结构，PROXY 直接选节点，桶数随重建变化）。不用 proxy-provider 是刻意的：换桶依赖的 `/proxies/<名>/delay` 测活接口对 provider 节点一律返回 404，组级测活接口 `/group/<组>/delay` 在大组时必返回 504，只有内联节点的逐个测活是可靠的。配置的顶层设计里还有一条 `interface-name: WLAN`，作用是强制连节点的流量走裸线物理网卡、不与系统上其它全局路由/代理工具抢占默认路由；当前 `config.yaml` 里**没有**写入这一项（2026-11-20 核对），本机装 Skyline TUN 时实测仍能正常出网，需要强制裸线时再补上该行并重启内核。

**选中状态记忆**。mihomo 运行时在 `mihomo-single\cache.db` 记住当前选中的节点，重启后恢复旧选择。这个行为无害：轮换脚本不依赖开机选的是谁，遇到失联节点会自动跳过。

## 3 其它组件

### 3.1 python 脚本（根目录两个）

**exit_probe.py（出口探测器）** 是出口身份判定的权威实现，被换桶脚本直接 import 复用。核心函数：`cf_trace`（取 CF trace 原始字段）、`exit_identity`（汇总 IP/协议族/前缀/loc/colo 的完整出口身份）、`net_prefix` 与 `identity_key`（桶指纹的计算与比对）、`wait_ip_change`（按桶指纹等待出口真正变化，可传 `avoid_keys` 指定要避开的最近桶）、`bucket_history_load`／`bucket_history_push`／`bucket_history_keys`／`bucket_is_fresh`／`bucket_history_clear`（最近 3 次桶账本的读写与判定，落盘 `log\bucket_history.json`）、`make_client`（构造不走环境变量代理的 httpx 客户端）。它单独运行时有三种用法：**不带参数** = VPN 体检加走代理查当前出口桶两段连跑（日常首选，代理端口未运行时自动跳过走代理段）；`--mihomo` 只做完整 VPN 体检（服务进程、内核版本、节点池测活缓存、WinInet 系统代理、直连与代理出口对照）；`--cf-trace` 只查出口身份加 ASN 归属（缺省查裸线，配 `--proxy http://127.0.0.1:7892` 查走节点）。各种用法的报告都落盘 `log\exit_probe_report-*.txt`。exit=出口（网络出网点，不是"退出"），与功能名副其实。

**exit_rotator.py（出口轮换器）** 是换桶的执行器。`switch_mihomo` 通过控制器从当前节点的下一个开始环形寻找存活节点（跳过 DIRECT/REJECT/Auto 和失联节点，逐个发测活确认），找到后 PUT 切换过去；`main` 负责参数解析和最终判定——`--verify` 打印当前出口身份与最近 3 次桶，`--wait` 模式下等到的新桶要避开最近 3 次用过的桶才返回 0，成功后新桶入账；`--reset-history` 清空账本。它复用 exit_probe 的全部桶判定与账本逻辑，自己不重复实现。exit_rotator 切换完只报告事实（返回码），撞 429 的时机判断由调用方（gateway 或人）负责。

### 3.2 双击入口（一级方案：根目录三对 bat+ps1，proxy-*-single）

bat 是给双击用的薄壳，实际逻辑都在同名 ps1 里。**一级方案用 `proxy-*-single` 三对入口**（独立端口 7892/9092，独立目录 `mihomo-single\`），与二级的 `proxy-on/off/switch`（7890/9090）**并存互不干扰**。

**proxy-on-single.ps1** 完成一级开代理的整套动作：启动 mihomo 内核（`mihomo\mihomo-slim.exe -d mihomo-single -f mihomo-single\config.yaml`，端口 7892 未监听才启动，最多等 15 秒；检测到 7892 被占则只停该端口的一级实例，不影响二级 7890/9090）→ 设置 WinInet 系统代理到 `127.0.0.1:7892`（含本机地址绕过表，并用 InternetSetOption 通知系统立即生效）→ 打印当前节点池清单（几个节点、几个互不相同的桶、逐节点所属桶，离线读 `mihomo-single\config.yaml` 与 `log\buckets.tsv`，秒出），随后分别查询直连出口与代理出口做对照，末尾打印换桶命令备忘。注意它只开代理不换桶——撞 429 必须点 proxy-switch-single。

**proxy-switch-single.ps1** 是一级换桶的日常入口。先确认一级内核在跑（没跑就先调 proxy-on-single），打印换桶前出口与最近 3 次桶，然后最多 6 轮调用 exit_rotator 轮换（每轮自动跳过失联节点，单轮等待 25 秒——实测换桶 6~8 秒，同桶多等无意义；等到的桶若在最近 3 次里不算换出，本轮失败转下一轮）。轮次默认 6 而不是 4：最近 3 次桶占掉一部分可用桶后，要往后多试几个节点才碰得到新桶。任何一轮返回 0 即成功，返回 2（控制器不可达或参数错误）则中止重试。6 轮全失败会提示先试 `--reset-history`，再询问是否重建节点池，按 Y 进入 nodepool 流水线。**一级换桶口径**：`exit_rotator.py --target mihomo --group PROXY`（PROXY 直接选单级节点，与单级一致）。

**proxy-off-single.ps1** 恢复直连：关闭 WinInet 系统代理；加 `-Stop` 参数时连 mihomo 进程一起停（同时收 `mihomo-slim` 与官方内核名两个进程名），停完报告当前直连出口。

> **与二级入口的关系**：一级方案 `proxy-*-single`（7892/9092）与二级方案 `proxy-on/off/switch`（7890/9090）是**两套独立入口**，分别读 `mihomo-single\config.yaml` 与 `mihomo\config.yaml`，端口与工作目录都不同，可同时运行互不干扰。二级入口的说明见 `OmniVPN二级方案说明.md`。

### 3.3 nodepool 节点池流水线（入口在根目录，步骤实现在 nodepool\ 子目录）

免费节点生生死死是常态，整池死透时需要从公开订阅源重新抓一批。双击入口 `rebuild-pool.bat` 在 OmniVPN 根目录（用户要求：双击执行脚本不放子目录），它调用编排 `rebuild-pool.ps1`（v1.4），步骤实现脚本在 `nodepool\` 下，按序执行 11 步：抓取公开订阅源（`_fetch2.py`，9 源并行抓取，秒级完成，直连失败自动走 7890 备援，落 `log\subs\`）→ 解析去重加裸线 TCP 筛（`_parse_test.py`，按自动探测的物理网卡源地址 3 秒判据，开跑前打印实际源地址）→ TLS 真实握手筛（`_tls_probe.py`，防"TCP 通但 TLS 被掐"，与 TCP 筛绑同一个源地址）→ **死点池复活注入**（`_deadpool.py revive`，把上次实测失败的节点追加进待测清单，跳过 TCP/TLS 预筛直进实测，单次上限 300 条、池内总量上限 600 条）→ 转 mihomo YAML（`_uri2yaml.py`）→ mihomo 逐节点实测出网（`_verify_nodes.py`，最慢的一步，千级节点约 15 分钟，外加一轮重试约 5 分钟；并发 12 实测存活数最准，调大会低估；收尾按 504 超时 / 503 协议失败分列失败原因，并报重试救回几个）→ **死点池结算**（`_deadpool.py record`：注入且实测通过 = 复活移出池；仍失败 = 失败次数+1；连续 5 次死 = 彻底清除；本轮新失败的新鲜节点 = 入池。池文件 `log\deadpool.txt`）→ 只留可用节点（`_filter_nodes.py`）→ 测出口定桶（`_survey_buckets.py`）→ 按出口桶轮转排序（`_order_nodes.py`，保证相邻节点必不同桶，所以"切下一个活节点"几乎必然换桶）→ 写回 `mihomo\config.yaml`（`_rebuild_config.py`，自动留 `.bak`）。全部跑完后自动重启 mihomo 加载新池。**一级方案注意**：重建写回的是单级结构 `mihomo\config.yaml`；一级模式用 `mihomo-single\config.yaml`，重建后需把单级配置同步到 `mihomo-single\config.yaml`（改端口 7892/7893/9092）并重启一级实例。

死点池存在的原因：免费节点失联后过几天常会复活，一次性淘汰太浪费；连续 5 次实测仍死的才彻底扔掉。不想跑全量重建时，双击 `update-pool-quick.bat` 做轻量巡检（约 1~2 分钟）：现池逐节点复验报存活数 + 死点池复活实测与结算，实测用临时端口 7897/9097 起独立 mihomo 实例，不影响在跑的 7892/9092 一级实例；该巡检也挂在 `proxy-switch-single.bat` 尾部，换桶结束后自动带跑一遍。

公开免费池的存活率很低，2026-11-20 全量重建的实测口径：9 源进料解析 14238 条 → 按 host:port 去重 7668 条 → 裸线 TCP 可达 2108 条 → TLS 握手通 1389 条 → mihomo 逐个实测真能出网 **30** 条 → 测出口后 26 条可用、覆盖 **11 个不同出口桶** → 按桶轮转后落配置 **15 个节点**。约 0.4% 的进料能真正出网，节点失联与复活都属正常。

现池到底有几个互不相同的出口桶，用 `nodepool\_bucket_stats.py` 离线统计（不起内核、不联网）：默认读真正生效的 `mihomo-single\config.yaml`（一级），配 `log\buckets.tsv` 快照列出每个桶的节点清单，并标出哪些桶已被换桶账本占用、还剩几个可换的新桶；加 `--alive log\quick\good_pool.txt` 只算存活节点，加 `--by-node` 则逐节点一行（proxy-on-single 启动后打的就是这一种）。它已挂在 `update-pool-quick.ps1` 的现池复验之后，轻量巡检顺手就报。`buckets.tsv` 只在 `rebuild-pool.ps1` 第 9 步刷新，轻量巡检不刷新，所以快照时间会早于巡检时间。

### 3.4 目录里其余文件

`mihomo-single\config.yaml` 是**一级运行配置**：7892/7893/9092 三端口加当前节点池的内联节点（现 17 个，单级结构，PROXY 直接选节点）。`mihomo-single\cache.db` 是 mihomo 运行时自建的选中记忆，不入库。`mihomo\config.yaml` 是**二级运行配置**（两级池，见二级方案文档）。`log\` 存放全部运行时产物：节点池数据（nodes.yaml、nodes_ordered.yaml、buckets.tsv、good_all.txt，离线重跑"测出口定桶/轮转排序"两步够用）、换桶历史账本 bucket_history.json、探测报告 exit_probe_report-*.txt、订阅缓存、死点池 deadpool.txt 与轻量巡检目录 quick\。git 只跟踪源码与文档，exe、cache.db、log\ 均已 ignore。

### 3.5 一级模式独立端口与并存（proxy-*-single.bat 一套）

**一级模式**：出口节点直连裸线，无二级池（INDONESIA_POOL/EXIT_POOL），用独立配置 `mihomo-single\config.yaml`（单级 17 节点）。

**端口分离（关键）**：一级和二级用不同端口，两个实例可**并存**，互不干扰：

| 项目 | 二级模式 | 一级模式 |
|------|---------|---------|
| 配置目录 | `mihomo\`（config.yaml） | `mihomo-single\`（config.yaml） |
| 代理端口 | 7890（HTTP）/ 7891（SOCKS） | 7892（HTTP）/ 7893（SOCKS） |
| 控制器 | 127.0.0.1:9090 | 127.0.0.1:9092 |
| 出口链路 | 一级跳板 + 二级出口 | 节点直连裸线 |

> ⚠️ **为何必须独立目录**：mihomo 用 `-d` 指定工作目录并写 `cache.db`。若一级和二级共用同一 `-d mihomo`，cache.db 冲突会导致后启动实例被挤出。**必须用独立目录 `mihomo-single\`**，各自独立 cache.db 才能并存。

**一级入口链路**（入口作用详见 3.2）：

```
proxy-on-single.bat ──> proxy-on-single.ps1 (默认 Port=7892)
                          │
                          ├─[1] 启动 mihomo-slim.exe -d mihomo-single (读 mihomo-single\config.yaml, 端口 7892 未监听才启)
                          │        (检测到 7892 被占则只停该端口一级实例, 不影响二级 7890/9090)
                          ├─[2] 设 WinInet 系统代理 → 127.0.0.1:7892
                          ├─[3] 节点池清单: _bucket_stats.py mihomo-single\config.yaml --by-node
                          ├─[4] 代理链路: 读 9092 /proxies/PROXY (一级直出, 未串联二级)
                          └─[5] 出口对照: exit_rotator.py --verify (直连 vs 经 7892 代理出口)

proxy-switch-single.bat ──> proxy-switch-single.ps1 (观测口 7892)
                          └─ 轮换: exit_rotator.py --target mihomo --group PROXY (单级节点直接选)

proxy-off-single.bat ──> proxy-off-single.ps1 (取消系统代理, 可选停内核)
```

**一级模式实测**（2026-11-28，独立目录 + 端口 7892/9092）：
- 一级实例与二级实例**并存成功**：7890/9090（二级）+ 7892/9092（一级）同时监听。
- 一级出口验证：`80.174.118.69 (v4)`，前缀 `80.174.118.0/24`，loc=IT（意大利），colo=MXP —— **一级链路真正出网**。
- 一级配置自检：`mihomo-single\config.yaml` test is successful。
- **一级桶数实测**（2026-11-28，`_survey_buckets.py` 逐节点拉 CF trace）：17 节点中**可用 3、互不相同的出口桶 2 个**——`80.174.118.0/24|IT`（意大利，N11/N16）、`193.233.127.0/24|NL`（荷兰，N928）；其余 **14 个节点连不通**（免费节点生生死死，当前一级池大部分已失联）。**换桶空间严重不足**：2 桶 < 账本 3 条，换桶会失败，需重建一级节点池（见 3.3 流水线）。

## 4 脚本与命令的使用

### 4.1 双击用法（日常，一级方案）

每天开始干活前双击 `proxy-on-single.bat`——窗口会依次打印内核就绪、系统代理启用、节点池清单（几个节点、几个桶、逐节点所属桶）、直连出口与代理出口对照，看完就能关（mihomo 是后台进程不受影响，但出口查询每步要 3~8 秒，别在查询中途关窗）。看"代理出口"那一项的 loc 和前缀，就是当前出口桶。注意一级方案走 `127.0.0.1:7892`，别与二级的 7890 混。

撞 429 时双击 `proxy-switch-single.bat`——窗口出现"换桶成功"即配额恢复，继续发请求；出现"换桶失败"说明节点池整体失效，按提示按 Y 重建（约 20~26 分钟），或直接双击根目录的 `rebuild-pool.bat`。

收工时双击 `proxy-off-single.bat`——取消系统代理并停止内核，本机恢复裸线直连（出口恒为 `loc=CN`）；只想关系统代理、保留内核运行，用命令行 `proxy-off-single.ps1`（不带 `-Stop`，见 4.2.1）。

平时想确认节点池健康度，双击 `update-pool-quick.bat`——先复验现池（打印"现池存活 x / y"，全死会提示重建），再把死点池里的节点拉出来实测一轮（复活移出、连续 5 死清除），全程 1~2 分钟。注意 `proxy-switch-single.bat` 每次换桶后会自动带跑这个巡检，通常无需手动双击。

### 4.2 命令行用法

以下相对路径命令的执行前提是站在仓库根 `D:\NDOOmniAgent` 下（脚本内部全部按 `__file__`/`$PSScriptRoot`/`%~dp0` 自定位，报告落盘与 import 不受当前目录影响，故也可改用绝对路径在任意目录执行）。bat 是双击入口，ps1 是同一功能的命令行实现（bat 内部就是调同名 ps1），按处理操作对象分节如下：

| 处理操作对象 | 双击入口（bat） | 命令行实现 |
|------|------|------|
| 一级 mihomo 实例与系统代理（7892/9092） | `proxy-on-single.bat` / `proxy-off-single.bat` | `proxy-on-single.ps1` / `proxy-off-single.ps1` |
| 出口桶（PROXY 组当前选中节点） | `proxy-switch-single.bat` | `proxy-switch-single.ps1`、`exit_rotator.py` |
| 节点池（`log\` 池数据 + `mihomo-single\config.yaml` 节点段） | `rebuild-pool.bat`、`update-pool-quick.bat` | `rebuild-pool.ps1`、`update-pool-quick.ps1`、`nodepool\_deadpool.py` |
| 出口身份与隧道环境诊断 | ——（报告落 `log\exit_probe_report-*.txt`） | `exit_probe.py` |
| 本机命令行程序的网络出口 | ——（设环境变量，无脚本） | `$env:HTTP_PROXY` / `$env:HTTPS_PROXY` |

#### 4.2.1 一级 mihomo 实例与系统代理

操作对象：7892/9092 端口的一级 mihomo 内核进程 + WinInet 系统代理开关。

```bat
:: 双击(或命令行直接调): 启动一级内核(未监听才启, 最多等 15 秒) + 设系统代理 + 打印直连/代理出口对照
OmniVPN\proxy-on-single.bat
:: 双击(或命令行直接调): 取消系统代理并连内核一起停(固定带 -Stop)
OmniVPN\proxy-off-single.bat
```

ps1 是更细粒度的命令行版，差别在 `proxy-off-single.ps1` 不带 `-Stop` 时只关系统代理、内核留着跑：

```powershell
powershell -ExecutionPolicy Bypass -File OmniVPN\proxy-on-single.ps1
powershell -ExecutionPolicy Bypass -File OmniVPN\proxy-off-single.ps1        # 只关系统代理, 内核继续跑
powershell -ExecutionPolicy Bypass -File OmniVPN\proxy-off-single.ps1 -Stop  # 关系统代理并停内核(= proxy-off-single.bat)
```

#### 4.2.2 出口桶（撞 429 时换出口，一级方案）

操作对象：PROXY 组当前选中的节点（换节点 = 换出口桶）。一级方案观测口为 `7892`。

```powershell
# = 双击 OmniVPN\proxy-switch-single.bat: 先确认内核在跑, 最多 6 轮自动换桶, 全失败引导重建
powershell -ExecutionPolicy Bypass -File OmniVPN\proxy-switch-single.ps1

# 底层执行器(单次口径; proxy-switch-single.ps1 内部调的就是它)
python OmniVPN\exit_rotator.py --verify --proxy http://127.0.0.1:7892
python OmniVPN\exit_rotator.py --target mihomo --group PROXY --wait --proxy http://127.0.0.1:7892

# 池内桶都已在最近 3 次里时, 清空历史账本后重换
python OmniVPN\exit_rotator.py --reset-history
```

返回码 0/1/2 的判定口径见 4.3。

#### 4.2.3 节点池

操作对象：`log\` 下的池数据文件与 `mihomo-single\config.yaml` 的节点段（含死点池 `log\deadpool.txt`）。

```powershell
# 全量重建(11 步约 20~26 分钟; = 双击 OmniVPN\rebuild-pool.bat)
powershell -ExecutionPolicy Bypass -File OmniVPN\rebuild-pool.ps1

# 轻量巡检(现池复验 + 死点复活结算, 1~2 分钟, 临时端口不影响在跑的 mihomo; = 双击 update-pool-quick.bat)
powershell -ExecutionPolicy Bypass -File OmniVPN\update-pool-quick.ps1

# 死点池单步手动(一般不用: 流水线第 4/11、7/11 步与巡检脚本会自动调)
python OmniVPN\nodepool\_deadpool.py revive <tls_ok.txt> <inject_out.txt>
python OmniVPN\nodepool\_deadpool.py record <map.txt> <good.txt> <reachable.txt> <inject.txt>

# 现池桶分布统计(离线, 不起内核不联网; 报互不相同的桶数 + 被账本占掉几个 + 还剩几个可换)
python OmniVPN\nodepool\_bucket_stats.py OmniVPN\mihomo-single\config.yaml
python OmniVPN\nodepool\_bucket_stats.py OmniVPN\mihomo-single\config.yaml --alive OmniVPN\log\quick\good_pool.txt   # 只算存活节点
python OmniVPN\nodepool\_bucket_stats.py OmniVPN\mihomo-single\config.yaml --by-node   # 逐节点一行(池内轮转顺序), proxy-on-single 启动后打的就是这一种
```

`nodepool\` 下其余 `_*.py` 是流水线步骤实现脚本，只被编排 ps1 调用，不单独手动跑；`_bucket_stats.py` 例外，它是只读统计，随时可手动跑。

#### 4.2.4 出口身份与隧道环境诊断

操作对象：本机直连/代理两条链路的出口身份（IP、前缀、loc、ASN）与本机 VPN 隧道环境。

```powershell
# 体检 + 查当前出口(两段连跑, 日常首选): 7892 在跑查代理出口, 没跑则查直连链路出口(被 TUN VPN 接管时即该 VPN 出口)
python OmniVPN\exit_probe.py

# 只做 VPN/代理状态体检(TUN 隧道环境、端口、PROXY 选中、系统代理)
python OmniVPN\exit_probe.py --mihomo

# 只查出口身份
python OmniVPN\exit_probe.py --cf-trace                                # 裸线, 恒 loc=CN
python OmniVPN\exit_probe.py --cf-trace --proxy http://127.0.0.1:7892  # 当前一级出口桶(看这个)
```

不管哪个 VPN 在跑，报告都输出完整出口对照（直连出口 + 代理出口 + trace 明细 + ASN 归属），落盘 `log\exit_probe_report-*.txt`。

#### 4.2.5 本机命令行程序的网络出口

操作对象：不认 WinInet 系统代理的命令行程序（bun/undici 等）。手动喂环境变量，只认 `http://`，别用 7893 SOCKS（一级）：

```powershell
$env:HTTP_PROXY='http://127.0.0.1:7892'; $env:HTTPS_PROXY='http://127.0.0.1:7892'
```

### 4.3 返回码与判定口径

换桶判定标准：前缀（IPv4 折 /24、IPv6 折 /48）与 loc 一起变才算新桶，同前缀只换尾号仍是同一桶；在此基础上还要避开最近 3 次用过的桶（账本 `log\bucket_history.json`），落回这 3 个桶里同样不算换桶，哪怕它的前缀与当前桶不同。exit_rotator 的返回码：0 = 已换出最近 3 次以外的新桶，可恢复发请求；1 = 切换了但出口仍落在最近用过的桶内（候选同桶或全部失联），proxy-switch 会自动再试下一节点；2 = 控制器不可达、参数缺失或切换失败，需查现场（9090 是否在听），不能当作成功。

### 4.4 常见问题处置

`proxy-on-single` 报端口未监听，手动跑 `OmniVPN\mihomo\mihomo-slim.exe -d OmniVPN\mihomo-single -f OmniVPN\mihomo-single\config.yaml` 看内核报错。`proxy-switch-single` 返回 2，查 `127.0.0.1:9092` 控制器是否在听。窗口停在"直连出口"没动静，是 python 查询在等网络回包（3~8 秒），会自己出来，别关窗。浏览器出口没变，是命令行程序不认系统代理，按 4.2.5 节喂环境变量。重启后选中节点变了，是 mihomo 的 cache.db 记忆行为，无害。换桶后网页变慢，免费节点带宽所限，属预期，本方案只作应急。6 轮全失败，多半是整池死透或池内桶都已在最近 3 次里，先 `--reset-history` 再换，仍不行走重建。重建时窗口出现"裸线 TCP 可达: 0 / N"，先看开跑第一行打印的"裸线源地址"：正常应是物理网卡 IPv4（本机为 `192.168.1.18`）；显示未探到或走默认路由时，先用 `Get-NetAdapter -Physical` 确认物理网卡是 Up 且拿到 IPv4，再确认 `python -c "import psutil"` 可用（源地址探测靠它列网卡），修好再重跑。

## 5 内核 exe 缺失时的恢复与重编

### 5.1 从官方 release 装回（推荐，1 分钟）

内核二进制不入库（`OmniVPN/mihomo/*.exe` 已在 `.gitignore`），换机、清理磁盘或误删后会缺失，表现是 `proxy-on` 报"未找到内核程序: ...mihomo-slim.exe"。恢复步骤：

```powershell
# 1) 查最新 tag（当前最新 v1.19.34，2026-11-11 发布）
curl.exe -s https://api.github.com/repos/MetaCubeX/mihomo/releases/latest

# 2) 下载 Windows amd64 包
curl.exe -L -o $env:TEMP\mihomo.zip `
  https://github.com/MetaCubeX/mihomo/releases/download/v1.19.34/mihomo-windows-amd64-v1.19.34.zip

# 3) 解压并把 exe 按脚本要求改名放回 mihomo 目录
Expand-Archive $env:TEMP\mihomo.zip $env:TEMP\mihomo -Force
Copy-Item $env:TEMP\mihomo\mihomo-windows-amd64.exe F:\OmniAgentAs-01\OmniVPN\mihomo\mihomo-slim.exe -Force

# 4) 校验版本，应输出 Mihomo Meta v1.19.34 windows amd64
F:\OmniAgentAs-01\OmniVPN\mihomo\mihomo-slim.exe -v

# 5) 启动并验证（一级: 7892 代理口、7893 socks、9092 控制器; 二级见二级方案文档）
F:\OmniAgentAs-01\OmniVPN\proxy-on-single.bat
```

包名怎么选：普通 x64 机器用 `mihomo-windows-amd64-v1.19.34.zip`；CPU 较新可用 `-v2-`/`-v3-`（Go 微架构档位，需 CPU 支持对应指令集）；老系统用 `-compatible-`；32 位用 `386`，ARM 用 `arm64`。下载慢时把 URL 交给下载工具或走代理（`curl.exe -x http://127.0.0.1:7890 ...`）。

2026-11-20 08:08 按上述步骤装回并实测：进程 `mihomo-slim` 监听 7890/7891/9090，控制器 `/version` 返回 v1.19.34，经 7890 查 CF trace 出口 `130.61.145.251`（loc=DE，colo=FRA），经 7890 访问 `models.opencode.ai` 返回 HTTP 200，`proxy-on.ps1` 设置系统代理成功。

### 5.2 想要精简体积时重编

```powershell
# 取指定 tag 源码（需要 git 与 Go，本机 Go 在 E:\30AI编程工具\go1.25\bin\go.exe）
git clone --depth 1 --branch v1.19.34 https://github.com/MetaCubeX/mihomo.git D:\Downloads\mihomo-src
cd D:\Downloads\mihomo-src
go build -trimpath -ldflags "-s -w -X github.com/metacubex/mihomo/constant.Version=v1.19.34-slim" -o mihomo-slim.exe .
```

自编精简版的体积收益只有 10 MB 左右（58.3 MB → 47.8 MB），功能上本方案用不到的部分本来就不参与转发，日常没必要为了这点体积自己编译；官方包出问题（缺 DLL、被杀软误报）时才优先考虑自编。

## 6 相关文档

`opencli\部署与启停说明.md` 第 5 章有网关侧出口代理启停与换桶摘要；`doc-11月优化\[19]LLM429限流分级处理与冷却记忆优化设计-小欧-2026-11-08.md` 说明了 429 为什么要换桶；mihomo 内核上游仓库为 https://github.com/MetaCubeX/mihomo，发布页 https://github.com/MetaCubeX/mihomo/releases，内核缺失的装回与重编步骤见 §5（本机已无 `D:\Downloads\mihomo-src\` 源码）。

## 7 查询方法
python exit_probe.py                              # 二级(默认 7890/9090)
python exit_probe.py --controller-port 9092 --proxy-port 7892   # 一级
