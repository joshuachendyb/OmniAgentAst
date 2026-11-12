# opencli gateway 使用说明 — 小欧 2026-11-09
---

## 1 网关是什么：技术模式说明

opencli 网关是一个**本地 LLM API 转发服务**（gateway 模式）。它的定位：OpenCode 宿主不直连上游 API，而是把本机的一个小服务当作模型端点，所有模型请求先到网关、由网关转发到上游。对宿主来说，网关就是一个普通的 OpenAI 兼容端点（`http://127.0.0.1:8080/v1`）；对上游来说，网关是唯一可见的调用方。

请求链路：

```
OpenCode 宿主(后端)
   │  provider "opencli": api_base = http://127.0.0.1:8080/v1, api_key = 令牌
   ▼
opencli 网关 (opencode2api.exe, 只听 127.0.0.1:8080, 管理台 8081)
   │  ① 令牌鉴权 → ② 车道选择 → ③ 模型别名轮换 → ④ 出口转发 → ⑤ 上游重试
   ▼
上游免费车道 (opencode.ai)
```

网关在链路中间做五件事，每一件都独立可解释：

**令牌鉴权**。宿主访问网关必须带令牌，网关与宿主两侧逐字符精确比对（config.json 的 `server_keys` 与后端 config.yaml 的 `opencli.api_key` 两处同值）。网关只听本机回环地址，令牌是第二道防线，防的是本机其它进程随意借用免费车道。

**车道选择**。请求按 `prefer` 字段指明的偏好进入车道：go（付费 go_keys）、zen（付费 zen_keys）、anonymous（匿名免费）。车道键为空即不可用，实际生效的是 anonymous——这是整套免费方案的车道。车道键位从配置读取，不落在代码里。

**模型别名轮换**。请求模型名可以是别名（如 `sota`/`sweet`），网关按 `rotation.order` 列表接力：上游对列表中某个模型不可用时自动切下一个。宿主点名具体模型（如 deepseek-v4.1-flash-free）时绕过别名直呼，不参与轮换。

**出口转发**。网关发出的上游请求经 `proxies`/`warp` 字段描述的出口路径走出。direct = 直连；`warp` 是网关自带的 WARP 出口池（2026-11-12 重验：12 个暴露模型 11 个可用、仅 beam-free 地域限制，启用障碍是隧道稳定性，维持关闭，实测依据见第 8 章）；现行出口方案是配套服务 OmniVPN（见第 9 章）——网关管应用层转发，OmniVPN 管网络层出口，两层各司其职。

**上游重试与判死**。`retry.max_attempts=3` 上游失败重试三次；`first_output_seconds=30` 上游 30 秒未吐首帧判死；`retry.timeout_seconds=300` 与宿主侧超时对齐，避免两边等待窗口错位。

网关本身近乎无状态：唯一落盘的是自动生成的状态缓存（`config.json.*.json` 系列，模型目录、可用性、轮换指针），删除即自动重建，只是冷启动多等约 12 秒。

## 2 代码介绍

**opencode2api.exe** 是网关本体：预编译单文件程序（约 18.5MB），开箱即用，免安装免运行库。它是 Go 程序，源码来自上游 GitHub 仓库 **https://github.com/jasonxu114514/opencode2api**（README 与 Release 下载都在该仓库）。本仓库对它做了钉版管理：钉定 commit `b296a61d`（对应上游 O2A 1.4.7 同源血统），该 commit 的全源码已转存 `backup\opencli_gateway-src_源码转存_20261109\gateway-src\`（去 .git、未改一行业务逻辑，钉版信息见转存根目录 `PINNED.md`），现用的 exe 即由这份源码用 Go 1.25.6 执行 `go build -buildvcs=false ./cmd/opencode2api` 编译产出。铁律：源码只读钉版、禁止手改，所有运行定制都通过 `config.json` 完成（车道/出口/轮换/限速这类配置能表达的定制不进源码）；升级时从该仓库 Releases 换新版 exe，或按新 commit 重新钉版转存并编译。

仓库里这套东西存了两份，职责不同：

`opencli_gateway\` 是**入库母本**，git 跟踪五个文件：opencode2api.exe（网关程序）、config.json（配置基准）、opencli_gateway_start.bat（启动壳）、opencli_gateway_stop.bat（停止壳）、opencli_gateway_stop.ps1（停止逻辑，被停止壳调用），外加本文档。它回答"这套东西的定义是什么"，**是唯一维护对象**。

`opencli\` 是**部署后的运行目录**（母本拷出去跑起来的那份），运行期还会自动生成状态缓存（`config.json.models.catalog.json`、`config.json.*.availability.json`、`config.json.rotation.json` 等）。该目录及其内容**不在维护范围**——本文档与维护动作只针对母本，运行目录里有什么、改了什么，一律不管。

两个 bat 都是启动壳：opencli_gateway_start.bat 先查重（端口 8080 已监听则提示已在运行、不重复启动），否则前台拉起 `opencode2api.exe -config config.json`，窗口先列出服务端点/管理台/配置/停止方式再显示运行日志，关窗即停，进程意外退出时给出排查提示；opencli_gateway_stop.bat 按端口 8080/8081 找到监听进程，逐进程列出端口/角色/pid 后结束，杀完复检端口并给出明确结论（已停止/未在运行/未完全停止）。

与后端的接点只有一处：后端 config.yaml 的 provider `opencli`（`api_base: http://127.0.0.1:8080/v1`，`api_key` 与网关 `server_keys` 同值）。后端把 opencli 当一个普通 provider 调用，感知不到网关内部的轮换与重试。

## 3 使用场景

**场景一：免费车道日常使用（现行主场景）。** 后端 provider 指向网关，全部模型请求走 anonymous 匿名免费车道。免费配额按出口 IP 网段记账，撞 429 时两层手段配合：出口层换桶（双击 `OmniVPN\proxy-switch.bat`，换出口 IP），应用层重试（网关自动重试三次，宿主无感）。网关在链路里提供了单点收口——宿主永远只对一个本地端点说话，上游怎么换、出口怎么换都不需要改宿主配置。

**场景二：接入付费键。** 拿到付费 key 时填入 `zen_keys` 或 `go_keys`，`prefer` 改指对应车道即可，宿主侧零改动。键为空时自动回落 anonymous。

**场景三：不用网关的直连形态。** 后端 config.yaml 里不启用 opencli provider（或删掉该 provider 段），宿主直连上游。这是绕开网关的备用形态：少一层转发、少一个常驻进程，代价是失去轮换、重试与令牌收口。排障时可临时切直连判断问题出在网关还是上游。

**场景边界：** 网关只解决"应用层怎么调上游"，不解决"出口 IP 从哪来"。出口受限（429 按网段记账）时需要配套的 OmniVPN 换出口桶，两者是互补关系不是替代关系。

## 4 部署

拷 5 个文件到任意目录：opencode2api.exe、config.json、opencli_gateway_start.bat、opencli_gateway_stop.bat、opencli_gateway_stop.ps1。
出网放行 UDP 2408（仅重新启用 warp 出口池时需要，当前 warp 已关闭，直连部署用不到；warp 详见第 8 章）。
config.json.*.json 是自动生成的状态缓存，不用拷，删了会自动重建（冷启动多等 ~12 秒）。

## 5 启动与停止

### 5.1 启动

双击 opencli_gateway_start.bat：窗口先列出服务端点（8080/v1）、管理台（8081）、配置文件与停止方式，再显示网关运行日志。端口 8080 已监听时提示已在运行、不重复启动；网关进程意外退出时给出排查提示（常见：端口被占用）。

### 5.2 停止

双击 opencli_gateway_stop.bat（内部调用 opencli_gateway_stop.ps1）：逐进程列出占用的端口（8080 网关服务 / 8081 管理台）、pid 与进程名后结束，完成后复检端口并给出明确结论；端口无监听时提示网关未在运行。

## 6 换令牌

### 6.1 生成新令牌

令牌随便写，啥格式都行——网关不校验长度和字符集，唯一硬规则：server_keys 至少留 1 个（全删起不来）。
鉴权是两边逐字符精确匹配，写 64 位 hex 只是防猜的好习惯，不是规定。
生成命令任选其一：

PowerShell：-join ((1..32) | ForEach-Object { '{0:x2}' -f (Get-Random -Max 256) })

Python：python -c "import secrets; print(secrets.token_hex(32))"

### 6.2 填入并生效

把新令牌填到两处：本目录 config.json 的 server_keys 和后端 config.yaml 的 opencli.api_key。
改完 stop.bat → start.bat 重启网关。

## 7 config.json 字段说明

### 7.1 rotation（模型轮换别名，当前闲置）

sota/sweet 是别名；客户端请求 model="sota" 时按 order 列表自动接力，坏一个切下一个。
宿主每次点名调模型（如 deepseek-v4.1-flash-free），不走别名，所以这段闲着。
first_output_seconds=30：上游 30 秒没吐首帧判死。

### 7.2 listen（监听）

127.0.0.1:8080，只听本机，勿改 0.0.0.0。

### 7.3 server_keys（令牌）

宿主访问网关的令牌，与后端 config.yaml 的 opencli.api_key 两处同值。

### 7.4 zen_keys / go_keys（付费车道键位）

空 = 不用，走匿名免费车道。

### 7.5 anonymous（匿名免费车道开关）

true，我们的车道就靠它。

### 7.6 warp（网关内置 WARP 出口池）

warp 是网关内置 WARP 出口池的配置段，三个键：enabled（开关）、pool_size（出口池上限）、stack（ipv4/ipv6 栈）。它的机制、实测结论与启用方式自成一体，单独成章，全文见第 8 章。

### 7.7 proxies / proxyfile（出口路由）

proxies 的 direct = 网关进程直连上游（走裸线出口），warp 关闭时 anonymous 车道就从这个出口走。warp.enabled=true 时 anonymous 车道自动整体改走第 8 章的 WARP 出口（实测不落回直连）。proxyfile 空 = 未用。

### 7.8 upstream（上游端点）

anonymous 是我们的上游；zen 那个参与状态文件名指纹，勿改。

### 7.9 retry（上游重试）

max_attempts=3，timeout_seconds=300，与宿主 timeout=300 对齐。

### 7.10 models（模型目录）

refresh_seconds=300，每 5 分钟刷新；free_only=false，清单全出（现暴露 12 个，穿 WARP 实测 11 个可用，见第 8 章）。

### 7.11 performance（连接池调优）

默认值在跑，别动。

### 7.12 logging（日志）

level=info，ring_size=2000。

### 7.13 webui（管理台）

:8081，用户 admin。

### 7.14 prefer（车道偏好）

"go"；无 go_keys 时实际走 anonymous。

### 7.15 reasoning（推理力度）

effort=high。

## 8 网关内置 WARP 出口池

网关的出口有两条路：本章的内置 WARP 出口池，和第 9 章的配套服务 OmniVPN。本章讲内置这条。

### 8.1 这是什么

网关进程 opencode2api.exe 自己内置的备用出口，不需要任何外部服务。原理是进程内起 userspace WireGuard 隧道到 Cloudflare（UDP 2408），向 Cloudflare 注册出独立出口 IP；上游回 403/429 时，网关自动换一个新出口再试。

它与 OmniVPN 完全独立：OmniVPN 换的是整机的网络层出口，这个换的是网关自己的应用层出口，可单独用也可叠加用。当前 enabled=false 维持关闭。

### 8.2 实测结论

此前"上游封锁 WARP、备胎报废"的判定是观测手段错误——在机器外测，请求根本没穿过这条车道。2026-11-12 将观测点全部移到网关进程内部（启动日志出口 IP、/healthz、穿 8080 的真实请求）重验，结论反转如下。

ipv6 栈换桶真实。每次轮换出全新 /64（实测 2a09:bac5:1f4f:2da5、1f4c:183c、1f4e:1846 等），403 后自动换出口的机制正常运转。

ipv4 栈换桶无效。Cloudflare 永远分配同一个共享 NAT 地址 104.28.208.150/32，重复注册全部被丢弃，pool_size 名存实亡。要用 WARP 必须选 stack=ipv6。

上游 403 是逐模型地域判定，不是封锁，且中招的极少。2026-11-12 把网关暴露的 12 个模型全部穿 WARP 出口逐个实测：11 个 200 成功（big-pickle、deepseek-v4.1-flash-free、flint-40b-free、glm-5.3-flash-free、iceman-free、inkling-2-small-free、longcat-2.5-free、mimo-v2.6-flash-free、minimax-m3.1-flash-free、nemotron-3.5-lightning-free、nemotron-3.5-super-vl-free），只有 beam-free 403（回复 "This model is not available in your country"，跨 3 个不同 /64 测了 5 次全部 403，是稳定的地域限制）。

隧道稳定性差。启动验证成功率约五五开，命中失败即起不来；隧道内自带 DNS 频繁超时，造成请求级 502/504——实测中凡是 502/504 的模型换一次重试全部转为 200，说明是隧道瞬时故障而非模型不可用。这是重新启用要付出的主要代价。

### 8.3 结论与启用方式

车道能力结论：模型覆盖接近全量，12 个暴露模型 11 个可用，仅 beam-free 被上游地域限制；ipv6 栈换桶真实，ipv4 栈无效。出口自主：enabled=true 后 anonymous 车道的上游请求全部改走网关内置 WARP 出口（实测 12 个模型请求的尝试链全部是 warp 腿，无一落回直连），不需要 mihomo 在跑、不需要系统代理和环境变量，只要求裸线能发出 UDP 2408、裸线 IPv6 可达（stack=ipv6 启动验证要走通）。就这条车道自身而言，不依赖 OmniVPN。

但当前不建议用它替代 OmniVPN 当主车道，障碍有三。第一，启动验证成功率约五五开，命中失败网关直接起不来，需重启再试。第二，隧道内自带 DNS 频繁超时，产生请求级 502/504；网关的 max_attempts=3 自动换出口重试能兜住（实测失败请求重试全部转为 200），代价是延迟明显变大——实测 200 成功耗时 2.3~110 秒，OmniVPN 车道正常 1~3 秒。第三，WARP 的 /64 出口是全球 WARP 用户共享的网段，上游配额按网段记账，共享网段上的 429 频率未做长期验证（本次实测未遇到）。

启用方式：
[1] config.json 的 warp.enabled 改回 true，重启网关即生效；
[2] stack 固定用 ipv6（ipv4 换不出新桶，没有使用价值）；
[3] 出网需放行 UDP 2408（见第 4 章部署）；
[4] 定位是备用车道：OmniVPN 仍是日常主车道，WARP 适合在裸线网段配额打光、OmniVPN 换桶无效时兜底。是否启用由用户决策。

## 9 外网出口(代理) — 配套服务 OmniVPN — 小欧 2026-11-12

网关的外网出口代理已整体收拢到配套目录 `OmniVPN\`（唯一维护且入库的目录），内核、配置、脚本、文档全部自洽其中，原 `hooks\` 与 `vpn-trial\` 旧目录已删除。权威说明见 **`OmniVPN\OmniVPN使用说明.md`**（mihomo 内核能力、组件职责、命令用法、排错全在）；本节只列网关视角的要点。

### 9.1 内核与它提供的能力

内核是 mihomo 自编精简版 `OmniVPN\mihomo\mihomo-slim.exe`（Clash Meta 延续版，tag v1.19.34，单文件绿色程序，无安装动作）。它提供四项能力：本地 HTTP 混合代理口 7890（浏览器、系统代理、命令行程序共用）；外部控制器 API 9090（列组/切节点/逐节点测活，是换桶机制的支点，切换不重启进程）；节点内联配置（`mihomo\config.yaml`，绑 WLAN 裸线，与系统上其它全局路由/代理工具可并行运行）；选中节点记忆（cache.db，重启恢复旧选择，无害）。

### 9.2 双击脚本（都在 OmniVPN\）

| 双击 | 作用 | 何时用 |
|------|------|--------|
| `OmniVPN\proxy-on.bat` | 启动 mihomo + 设系统代理 7890 + 打印直连/代理出口对照 | 开始干活前 |
| `OmniVPN\proxy-switch.bat` | 换出口桶，最多 4 轮自动跳失联节点，全失败引导重建节点池 | 撞 429 时 |
| `OmniVPN\proxy-off.bat` | 取消系统代理 + 停止 mihomo（bat 固定带 `-Stop`） | 收工/回直连 |
| `OmniVPN\rebuild-pool.bat` | 重建节点池（11 步约 15~20 分钟，含死点池复活/结算，跑完自动重启 mihomo；步骤实现在 nodepool\） | 整池死透时 |
| `OmniVPN\update-pool-quick.bat` | 轻量巡检：现池复验 + 死点复活结算（约 1~2 分钟，临时端口不影响在跑的 mihomo） | 换桶后自动带跑/想看池健康度时 |

mihomo 是独立后台进程，关掉窗口不影响代理运行；出口查询每步 3~8 秒，别在查询中途关窗。

### 9.3 proxy-on 只开代理，不换桶

`proxy-on.bat` 只做三件事：启动内核 → 设系统代理 `127.0.0.1:7890` → 打印直连与代理出口对照。**换桶必须显式双击 `proxy-switch.bat`**。

默认走 mihomo 的原因：7890 是 HTTP 混合口，命令行工具的 HTTP 客户端可直接用；SOCKS 口（7891）bun/undici 这类 HTTP 客户端会报 `UnsupportedProxyProtocol`。换节点只调控制器 API（约 5 秒），不重启核心。

### 9.4 换桶判定口径与返回码

上游免费层配额按出口 IP 网段记账。判桶的硬标准只有一条：前缀变没变（IPv4 折 /24、IPv6 折 /48）——前缀变了就是新桶；loc 是随行的地区标注，不单独作判桶依据；同前缀只换尾号仍算同一个桶。观测点为 Cloudflare trace，`ip=` 即服务端所见地址。

| 返回码 | 含义 | 处置 |
|--------|------|------|
| 0 | 已换出新桶 | 恢复发请求 |
| 1 | 桶指纹未变（候选同桶或失联） | proxy-switch 自动再试；4 轮全失败引导重建 |
| 2 | 控制器不可达/参数缺失/切换失败 | 查现场（9090 是否在听），别当成功 |

### 9.5 命令行等价用法

```powershell
# 体检 + 查当前出口桶(两段连跑, 首选)
python OmniVPN\exit_probe.py

# 开 / 关
powershell -ExecutionPolicy Bypass -File OmniVPN\proxy-on.ps1
powershell -ExecutionPolicy Bypass -File OmniVPN\proxy-off.ps1 -Stop

# 换桶 / 只查出口
python OmniVPN\exit_rotator.py --target mihomo --group PROXY --wait --proxy http://127.0.0.1:7890
python OmniVPN\exit_rotator.py --verify --proxy http://127.0.0.1:7890
```

（相对路径命令的执行前提是站在仓库根 `D:\NDOOmniAgent` 下；改用绝对路径则任意目录可用。）

### 9.6 给命令行程序喂代理

系统代理只覆盖认它的程序（浏览器、Electron 桌面版）。命令行程序要自己给环境变量，且 bun / undici 这类 HTTP 客户端只认 `http://`：

```powershell
$env:HTTP_PROXY  = 'http://127.0.0.1:7890'
$env:HTTPS_PROXY = 'http://127.0.0.1:7890'
$env:ALL_PROXY   = 'http://127.0.0.1:7890'
```

不要用 SOCKS5 端口（`7891`），这类 fetch 会报 `UnsupportedProxyProtocol`。

### 9.7 节点池的定位与重建

节点池是公开免费节点（存活率约 1.2%，死节点多、会集体抖动），只作应急通道；节点生生死死属常态，探活与轮换会自动跳过失联节点。整池死透时按 proxy-switch 的引导重建（nodepool 11 步流水线，含死点池复活与结算，约 15~20 分钟）。v2rayN、gost、WARP 隧道等旧通道已于 2026-11-11 移除，exit_rotator 仅保留 mihomo 一种 target。

### 9.8 日常流程

```
不动             → 直连
撞 429           → 双击 proxy-on.bat       （第一次，开代理）
还 429，换出口   → 双击 proxy-switch.bat   （每撞一次双击一次）
不折腾了         → 双击 proxy-off.bat      （恢复直连）
```

要点：换桶后不必重启浏览器或程序——系统代理仍是 `127.0.0.1:7890`，变的只是 mihomo 背后的出口 IP；只想关系统代理、保留内核运行，用 `OmniVPN\proxy-off.ps1`（不带 `-Stop`）。

## 10 详细文档

doc-11月优化：[17] 运行手册与模块分析、[18] 技术原理。
