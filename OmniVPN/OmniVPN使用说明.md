# OmniVPN 使用说明
---

## 1 方案背景与研究结论

OpenCode 免费层的配额按出口 IP 网段记账。实测结论：同一个出口 IP 上换 session、换 UA 都仍然 429（`FreeUsageLimitError`），只有换出口 IP 才能换配额。因此撞 429 时的正确动作只有一个——把出口切到另一个节点，双击一下即可。

判定"出口换没换"的观测点是 Cloudflare trace（`https://www.cloudflare.com/cdn-cgi/trace`）。trace 返回的 `ip=` 是服务端实际看到的地址，opencode.ai 与 www.cloudflare.com 在同一张 CF 网络上，所以这个观测点最接近真实情况。出口桶的指纹由**前缀（IPv4 折 /24、IPv6 折 /48）**和**地区（loc）**组成，判定硬标准只有一条：**前缀变没变**——前缀变了就是新桶；loc 是随行的地区标注（换节点时通常跟着一起变，可佐证出口真的换了，但不单独作判桶依据）；尾号永远不算（CGNAT 场景尾号一直在变，前缀不变就还是同一个桶）。ipv4 与 ipv6 的区别只是前缀折算规则不同（/24 对 /48），不是第三条判定项。

## 2 mihomo 内核：是什么、提供什么

mihomo 是 Clash Meta 内核的延续版（Mihomo Meta），Go 语言编写的单文件代理内核，上游源码在 GitHub 仓库 **https://github.com/MetaCubeX/mihomo**。本目录使用自编精简版 `mihomo-slim.exe`（tag v1.19.34，约 47.8MB）：按官方 tag v1.19.34 取源码（转存本机 `D:\Downloads\mihomo-src\`，仓库外只读留存），裁掉 TUN、gvisor、WireGuard、QUIC 等本方案用不到的模块，只保留核心代理能力，`-s -w` 裁掉调试符号；重编命令见 §5。官方原版 exe 不在本目录（精简版已实测全链路等价）。

它在本方案里提供四项能力：

**本地代理端口（7890）**。HTTP 混合代理口，浏览器、系统代理、命令行程序都从这里进出。流量路径是：请求进入 7890 → mihomo 按当前选中的节点转发 → 节点服务器作为出口访问目标网站。

**外部控制器 API（9090）**。这是整套换桶方案的支点。控制器提供 REST 接口：`GET /proxies` 列出代理组和节点，`PUT /proxies/PROXY` 切换选中节点（不重启进程、不断连接管理），`GET /proxies/<节点>/delay` 对单个节点测活。换桶脚本就是靠这三个接口实现"确定性轮换"的，全程不需要重启 mihomo。

**节点内联配置**。所有节点直接写在 `mihomo\config.yaml` 的 `proxies:` 段里（当前 6 个免费节点）。不用 proxy-provider 是刻意的：换桶依赖的 `/proxies/<名>/delay` 测活接口对 provider 节点一律返回 404，组级测活接口 `/group/<组>/delay` 在大组时必返回 504，只有内联节点的逐个测活是可靠的。配置里还写了 `interface-name: WLAN`，强制连节点的流量走裸线物理网卡，不与系统上其它全局路由/代理工具抢占默认路由，可并行运行。

**选中状态记忆**。mihomo 运行时在 `mihomo\cache.db` 记住当前选中的节点，重启后恢复旧选择。这个行为无害：轮换脚本不依赖开机选的是谁，遇到失联节点会自动跳过。

## 3 其它组件

### 3.1 python 脚本（根目录两个）

**exit_probe.py（出口探测器）** 是出口身份判定的权威实现，被换桶脚本直接 import 复用。核心函数：`cf_trace`（取 CF trace 原始字段）、`exit_identity`（汇总 IP/协议族/前缀/loc/colo 的完整出口身份）、`net_prefix` 与 `identity_key`（桶指纹的计算与比对）、`wait_ip_change`（按桶指纹等待出口真正变化）、`make_client`（构造不走环境变量代理的 httpx 客户端）。它单独运行时有三种用法：**不带参数** = VPN 体检加走代理查当前出口桶两段连跑（日常首选，代理端口未运行时自动跳过走代理段）；`--mihomo` 只做完整 VPN 体检（服务进程、内核版本、节点池测活缓存、WinInet 系统代理、直连与代理出口对照）；`--cf-trace` 只查出口身份加 ASN 归属（缺省查裸线，配 `--proxy http://127.0.0.1:7890` 查走节点）。各种用法的报告都落盘 `log\exit_probe_report-*.txt`。exit=出口（网络出网点，不是"退出"），与功能名副其实。

**exit_rotator.py（出口轮换器）** 是换桶的执行器。`switch_mihomo` 通过控制器从当前节点的下一个开始环形寻找存活节点（跳过 DIRECT/REJECT/Auto 和失联节点，逐个发测活确认），找到后 PUT 切换过去；`main` 负责参数解析和最终判定——`--verify` 只打印当前出口身份，`--wait` 模式下等桶指纹真的变了才返回 0。它复用 exit_probe 的全部桶判定逻辑，自己不重复实现。exit_rotator 切换完只报告事实（返回码），撞 429 的时机判断由调用方（gateway 或人）负责。

### 3.2 双击入口（根目录三对 bat+ps1）

bat 是给双击用的薄壳，实际逻辑都在同名 ps1 里。

**proxy-on.ps1** 完成"开机三件事"：启动 mihomo 内核（端口未监听才启动，最多等 15 秒）→ 设置 WinInet 系统代理到 `127.0.0.1:7890`（含本机地址绕过表，并用 InternetSetOption 通知系统立即生效）→ 分别查询直连出口与代理出口做对照，末尾打印换桶命令备忘。注意它只开代理不换桶——撞 429 必须点 proxy-switch。

**proxy-switch.ps1** 是换桶的日常入口。先确认内核在跑（没跑就先调 proxy-on），记下换桶前出口，然后最多 4 轮调用 exit_rotator 轮换（每轮自动跳过失联节点，单轮等待 25 秒——实测换桶 6~8 秒，同桶多等无意义）。任何一轮返回 0 即成功，返回 2（控制器不可达或参数错误）则中止重试。4 轮全失败会询问是否重建节点池，按 Y 进入 nodepool 流水线。

**proxy-off.ps1** 恢复直连：关闭 WinInet 系统代理；加 `-Stop` 参数时连 mihomo 进程一起停（同时收 `mihomo-slim` 与官方内核名两个进程名），停完报告当前直连出口。

### 3.3 nodepool 节点池流水线（入口在根目录，步骤实现在 nodepool\ 子目录）

免费节点生生死死是常态，整池死透时需要从公开订阅源重新抓一批。双击入口 `rebuild-pool.bat` 在 OmniVPN 根目录（用户要求：双击执行脚本不放子目录），它调用编排 `rebuild-pool.ps1`（v1.2），步骤实现脚本在 `nodepool\` 下，按序执行 11 步：抓取公开订阅源（`_fetch2.py`，9 源并行抓取，秒级完成，直连失败自动走 7890 备援，落 `log\subs\`）→ 解析去重加裸线 TCP 筛（`_parse_test.py`，绑源地址 3 秒判据）→ TLS 真实握手筛（`_tls_probe.py`，防"TCP 通但 TLS 被掐"）→ **死点池复活注入**（`_deadpool.py revive`，把上次实测失败的节点追加进待测清单，跳过 TCP/TLS 预筛直进实测，单次上限 300 条）→ 转 mihomo YAML（`_uri2yaml.py`）→ mihomo 逐节点实测出网（`_verify_nodes.py`，最慢的一步，千级节点约 15 分钟；并发 12 实测存活数最准，调大会低估）→ **死点池结算**（`_deadpool.py record`：注入且实测通过 = 复活移出池；仍失败 = 失败次数+1；连续 5 次死 = 彻底清除；本轮新失败的新鲜节点 = 入池。池文件 `log\deadpool.txt`）→ 只留可用节点（`_filter_nodes.py`）→ 测出口定桶（`_survey_buckets.py`）→ 按出口桶轮转排序（`_order_nodes.py`，保证相邻节点必不同桶，所以"切下一个活节点"几乎必然换桶）→ 写回 `mihomo\config.yaml`（`_rebuild_config.py`，自动留 `.bak`）。全部跑完后自动重启 mihomo 加载新池。

死点池存在的原因：免费节点失联后过几天常会复活，一次性淘汰太浪费；连续 5 次实测仍死的才彻底扔掉。不想跑全量重建时，双击 `update-pool-quick.bat` 做轻量巡检（约 1~2 分钟）：现池逐节点复验报存活数 + 死点池复活实测与结算，实测用临时端口 7897/9097 起独立 mihomo 实例，不影响在跑的 7890/9090 主实例；该巡检也挂在 `proxy-switch.bat` 尾部，换桶结束后自动带跑一遍。

公开免费池的存活率约 1.2%（实测口径：源单 9 源进料 15001 条 → TLS 通约 2 千 → mihomo 节点约 1300 → 真能出网约 16 → 每桶留 2 共 6），节点失联与复活都属正常。

### 3.4 目录里其余文件

`mihomo\config.yaml` 是运行配置：7890/7891/9090 三端口加 6 个内联节点加 WLAN 绑定。`mihomo\cache.db` 是 mihomo 运行时自建的选中记忆，不入库。`log\` 存放全部运行时产物：节点池数据（nodes.yaml、nodes_ordered.yaml、buckets.tsv、good_all.txt，离线重跑"测出口定桶/轮转排序"两步够用）、探测报告 exit_probe_report-*.txt、订阅缓存、死点池 deadpool.txt 与轻量巡检目录 quick\。git 只跟踪源码与文档，exe、cache.db、log\ 均已 ignore。

## 4 脚本与命令的使用

### 4.1 双击用法（日常）

每天开始干活前双击 `proxy-on.bat`——窗口会依次打印内核就绪、系统代理启用、直连出口与代理出口对照，看完就能关（mihomo 是后台进程不受影响，但出口查询每步要 3~8 秒，别在查询中途关窗）。看"代理出口"那一项的 loc 和前缀，就是当前出口桶。

撞 429 时双击 `proxy-switch.bat`——窗口出现"换桶成功"即配额恢复，继续发请求；出现"换桶失败"说明节点池整体失效，按提示按 Y 重建（约 15~20 分钟），或直接双击根目录的 `rebuild-pool.bat`。

收工时双击 `proxy-off.bat`——取消系统代理并停止内核，本机恢复裸线直连（出口恒为 `loc=CN`）；只想关系统代理、保留内核运行，用命令行 `proxy-off.ps1`（不带 `-Stop`，见 4.2.1）。

平时想确认节点池健康度，双击 `update-pool-quick.bat`——先复验现池（打印"现池存活 x / y"，全死会提示重建），再把死点池里的节点拉出来实测一轮（复活移出、连续 5 死清除），全程 1~2 分钟。注意 `proxy-switch.bat` 每次换桶后会自动带跑这个巡检，通常无需手动双击。

### 4.2 命令行用法

以下相对路径命令的执行前提是站在仓库根 `D:\NDOOmniAgent` 下（脚本内部全部按 `__file__`/`$PSScriptRoot`/`%~dp0` 自定位，报告落盘与 import 不受当前目录影响，故也可改用绝对路径在任意目录执行）。bat 是双击入口，ps1 是同一功能的命令行实现（bat 内部就是调同名 ps1），按处理操作对象分节如下：

| 处理操作对象 | 双击入口（bat） | 命令行实现 |
|------|------|------|
| mihomo 主实例与系统代理（7890/9090） | `proxy-on.bat` / `proxy-off.bat` | `proxy-on.ps1` / `proxy-off.ps1` |
| 出口桶（PROXY 组当前选中节点） | `proxy-switch.bat` | `proxy-switch.ps1`、`exit_rotator.py` |
| 节点池（`log\` 池数据 + `mihomo\config.yaml` 节点段） | `rebuild-pool.bat`、`update-pool-quick.bat` | `rebuild-pool.ps1`、`update-pool-quick.ps1`、`nodepool\_deadpool.py` |
| 出口身份与隧道环境诊断 | ——（报告落 `log\exit_probe_report-*.txt`） | `exit_probe.py` |
| 本机命令行程序的网络出口 | ——（设环境变量，无脚本） | `$env:HTTP_PROXY` / `$env:HTTPS_PROXY` |

#### 4.2.1 mihomo 主实例与系统代理

操作对象：7890/9090 端口的 mihomo 内核进程 + WinInet 系统代理开关。

```bat
:: 双击(或命令行直接调): 启动内核(未监听才启, 最多等 15 秒) + 设系统代理 + 打印直连/代理出口对照
OmniVPN\proxy-on.bat
:: 双击(或命令行直接调): 取消系统代理并连内核一起停(固定带 -Stop)
OmniVPN\proxy-off.bat
```

ps1 是更细粒度的命令行版，差别在 `proxy-off.ps1` 不带 `-Stop` 时只关系统代理、内核留着跑：

```powershell
powershell -ExecutionPolicy Bypass -File OmniVPN\proxy-on.ps1
powershell -ExecutionPolicy Bypass -File OmniVPN\proxy-off.ps1        # 只关系统代理, 内核继续跑
powershell -ExecutionPolicy Bypass -File OmniVPN\proxy-off.ps1 -Stop  # 关系统代理并停内核(= proxy-off.bat)
```

#### 4.2.2 出口桶（撞 429 时换出口）

操作对象：PROXY 组当前选中的节点（换节点 = 换出口桶）。

```powershell
# = 双击 OmniVPN\proxy-switch.bat: 先确认内核在跑, 最多 4 轮自动换桶, 全失败引导重建
powershell -ExecutionPolicy Bypass -File OmniVPN\proxy-switch.ps1

# 底层执行器(单次口径; proxy-switch.ps1 内部调的就是它)
python OmniVPN\exit_rotator.py --verify --proxy http://127.0.0.1:7890
python OmniVPN\exit_rotator.py --target mihomo --group PROXY --wait --proxy http://127.0.0.1:7890
```

返回码 0/1/2 的判定口径见 4.3。

#### 4.2.3 节点池

操作对象：`log\` 下的池数据文件与 `mihomo\config.yaml` 的节点段（含死点池 `log\deadpool.txt`）。

```powershell
# 全量重建(11 步约 15~20 分钟; = 双击 OmniVPN\rebuild-pool.bat)
powershell -ExecutionPolicy Bypass -File OmniVPN\rebuild-pool.ps1

# 轻量巡检(现池复验 + 死点复活结算, 1~2 分钟, 临时端口不影响在跑的 mihomo; = 双击 update-pool-quick.bat)
powershell -ExecutionPolicy Bypass -File OmniVPN\update-pool-quick.ps1

# 死点池单步手动(一般不用: 流水线第 4/11、7/11 步与巡检脚本会自动调)
python OmniVPN\nodepool\_deadpool.py revive <tls_ok.txt> <inject_out.txt>
python OmniVPN\nodepool\_deadpool.py record <map.txt> <good.txt> <reachable.txt> <inject.txt>
```

`nodepool\` 下其余 `_*.py` 是流水线步骤实现脚本，只被编排 ps1 调用，不单独手动跑。

#### 4.2.4 出口身份与隧道环境诊断

操作对象：本机直连/代理两条链路的出口身份（IP、前缀、loc、ASN）与本机 VPN 隧道环境。

```powershell
# 体检 + 查当前出口(两段连跑, 日常首选): 7890 在跑查代理出口, 没跑则查直连链路出口(被 TUN VPN 接管时即该 VPN 出口)
python OmniVPN\exit_probe.py

# 只做 VPN/代理状态体检(TUN 隧道环境、端口、PROXY 选中、系统代理)
python OmniVPN\exit_probe.py --mihomo

# 只查出口身份
python OmniVPN\exit_probe.py --cf-trace                                # 裸线, 恒 loc=CN
python OmniVPN\exit_probe.py --cf-trace --proxy http://127.0.0.1:7890  # 当前出口桶(看这个)
```

不管哪个 VPN 在跑，报告都输出完整出口对照（直连出口 + 代理出口 + trace 明细 + ASN 归属），落盘 `log\exit_probe_report-*.txt`。

#### 4.2.5 本机命令行程序的网络出口

操作对象：不认 WinInet 系统代理的命令行程序（bun/undici 等）。手动喂环境变量，只认 `http://`，别用 7891 SOCKS：

```powershell
$env:HTTP_PROXY='http://127.0.0.1:7890'; $env:HTTPS_PROXY='http://127.0.0.1:7890'
```

### 4.3 返回码与判定口径

换桶判定标准：前缀（IPv4 折 /24、IPv6 折 /48）与 loc 一起变才算新桶，同前缀只换尾号仍是同一桶。exit_rotator 的返回码：0 = 已换出新桶，可恢复发请求；1 = 切换了但桶指纹未变（候选同桶或全部失联），proxy-switch 会自动再试下一节点；2 = 控制器不可达、参数缺失或切换失败，需查现场（9090 是否在听），不能当作成功。

### 4.4 常见问题处置

`proxy-on` 报端口未监听，手动跑 `OmniVPN\mihomo\mihomo-slim.exe -d OmniVPN\mihomo` 看内核报错。`proxy-switch` 返回 2，查 `127.0.0.1:9090` 控制器是否在听。窗口停在"直连出口"没动静，是 python 查询在等网络回包（3~8 秒），会自己出来，别关窗。浏览器出口没变，是命令行程序不认系统代理，按 4.2.5 节喂环境变量。重启后选中节点变了，是 mihomo 的 cache.db 记忆行为，无害。换桶后网页变慢，免费节点带宽所限，属预期，本方案只作应急。4 轮全失败，整池死透，走重建。

## 5 相关文档

`opencli\部署与启停说明.md` 第 5 章有网关侧出口代理启停与换桶摘要；`doc-11月优化\[19]LLM429限流分级处理与冷却记忆优化设计-小欧-2026-11-08.md` 说明了 429 为什么要换桶；mihomo 内核上游仓库为 https://github.com/MetaCubeX/mihomo，本地源码在 `D:\Downloads\mihomo-src\`（官方 tag v1.19.34），重编命令：`go build -trimpath -ldflags "-s -w -X github.com/metacubex/mihomo/constant.Version=v1.19.34-slim" -o mihomo-slim.exe .`
