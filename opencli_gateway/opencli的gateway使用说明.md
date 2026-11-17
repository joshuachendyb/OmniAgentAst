# opencli gateway 使用说明 — 小欧 2026-11-09

**来源**：https://github.com/jasonxu114514/opencode2api — opencode2api **v1.4.8**（上游 commit `159d7fdf`，2026-11-16 释出；上一版 v1.4.7 / `b296a61d`，2026-11-05）。完整台账、校验值与回滚包见 2.1。

**本次更新（2026-11-17，小欧）**

- 网关本体 v1.4.7 → **v1.4.8**。分两步走：先换官方 Release `opencode2api_v1.4.8_windows_amd64.zip`（与官方 SHA-256 比对通过）验证通路，再把源码快照前移到 `159d7fdf`、用这棵树本地编译后替换——**最终装机的是本地编译产物**（Go 1.25.6，13,972,480 B），母本 `opencli_gateway\` 与运行目录 `opencli\` 两份同哈希。
- 源码快照前移：全源码去 .git 落库 `backup\opencli_gateway-src_源码转存_20261117\gateway-src\`（125 个文件），20261109 旧快照保留不动。审计链由此恢复为"exe 由入库源码编出"，钉版信息见该目录 `PINNED.md`。
- 管理台收紧：`webui.listen` 由 `0.0.0.0:8081` 改为 `127.0.0.1:8081`。理由：v1.4.8 给管理台新增 OAuth 授权管理接口与 `go_subscription` 凭据字段，管理面不再对局域网开放。
- 文档补四处：新增 2.1 版本台账与升级记录；7.8 补 `upstream.prompt_environment`；7.13 补 `password_hash` 口令存储说明；第 1 章重试段补"重试失败保留真实 HTTP 状态与 `Retry-After`"。
- 除上面两项（`webui.listen`、`warp.enabled`）外，其它配置一项未改：车道、重试、轮换、令牌保持原值，旧 config.json 原样跑新 exe。
- 出口另作一次独立改动：`warp.enabled` 由 false 改为 **true**（母本与运行目录两份 config.json 同改），anonymous 车道的上游请求改走网关内置 WARP 出口池，不再经 `proxies`。理由、复验数据与代价见第 8 章。
- 落地验证（对最终装机的本地编译 exe 重跑，当时 `warp.enabled=false` 走裸线直连）：`/healthz` 报 `version=v1.4.8` 且 `ready=true`，`/v1/models` 仍 12 个；普通对话 2 秒返回，带 tools 请求 3 秒返回且工具名完整还原。启用 WARP 后的延迟另见 8.3。

**编辑历史**

| 日期 | 更新人 | 内容 |
|------|--------|------|
| 2026-11-09 | 小欧 | 初稿：网关模式与链路、部署、配置字段、WARP 出口池实测 |
| 2026-11-17 | 小欧 | 网关升至 v1.4.8；源码快照前移到 `159d7fdf` 并改由本地编译产出；管理台 listen 收紧；新增 2.1 台账；7.8／7.13／第 1 章补充；第 9 章外网出口内容收拢到 `OmniVPN\OmniVPN使用说明.md` 后移除该章（连带第 10 章） |
| 2026-11-17 | 小欧 | `warp.enabled` 默认改为 true：anonymous 车道改走内置 WARP 出口池（ipv6 双出口 /64 轮换，启动一次成功，实测请求一次通过、延迟 6~16 秒）；第 1 章出口转发、第 3 章场景与场景边界、第 4 章出网放行、7.6 同步改写；第 8 章补 8.3 启用复验、8.4 启用状态与回退；第 2 章运行目录维护口径与 6.2 重启步骤措辞对齐 |

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

**出口转发**。网关发出的上游请求经 `proxies`/`warp` 字段描述的出口路径走出。direct = 直连；`warp` 是网关自带的 WARP 出口池，2026-11-17 起 `enabled=true` 默认启用，anonymous 免费车道的上游请求全部改走进程内 WireGuard 隧道（Cloudflare 出口），不再经过 `proxies`。网关管应用层出口与上游重试，整机网络层出口归配套的 OmniVPN（见 `OmniVPN\OmniVPN使用说明.md`），两层各司其职。WARP 的机制、复验数据与代价见第 8 章。

**上游重试与判死**。`retry.max_attempts=3` 上游失败重试三次；`first_output_seconds=30` 上游 30 秒未吐首帧判死；`retry.timeout_seconds=300` 与宿主侧超时对齐，避免两边等待窗口错位。v1.4.8 起重试失败会保留最近一次上游 HTTP 响应与 `Retry-After`，不再以通用传输错误掩盖，排障以日志里的真实状态码为准。

网关本身近乎无状态：唯一落盘的是自动生成的状态缓存（`config.json.*.json` 系列，模型目录、可用性、轮换指针），删除即自动重建，只是冷启动多等约 12 秒。

## 2 代码介绍

**opencode2api.exe** 是网关本体：单文件程序（v1.4.8 版 13.3MB，由入库钉版源码本地编译产出），开箱即用，免安装免运行库。它是 Go 程序，源码来自上游 GitHub 仓库 **https://github.com/jasonxu114514/opencode2api**（README 与 Release 下载都在该仓库）。当前版本、上游 commit、exe 来源与校验值见 2.1 台账。铁律：源码只读钉版、禁止手改，所有运行定制都通过 `config.json` 完成（车道/出口/轮换/模型目录这类配置能表达的定制不进源码）；升级时按新 tag 重新钉版转存并本地编译（官方 Release 包可先用来验证通路）。

仓库里这套东西存了两份，职责不同：

`opencli_gateway\` 是**入库母本**，git 跟踪五个文件：opencode2api.exe（网关程序）、config.json（配置基准）、opencli_gateway_start.bat（启动壳）、opencli_gateway_stop.bat（停止壳）、opencli_gateway_stop.ps1（停止逻辑，被停止壳调用），外加本文档。它回答"这套东西的定义是什么"，**是唯一维护对象**。

`opencli\` 是**部署后的运行目录**（母本拷出去跑起来的那份），运行期还会自动生成状态缓存（`config.json.models.catalog.json`、`config.json.*.availability.json`、`config.json.rotation.json` 等）。该目录及其内容**不在维护范围**——本文档与维护动作只针对母本；运行目录里的状态缓存既不进版本库也不记录，母本 config.json 改动后按同值覆盖运行目录那一份即可，两份保持同值，不分别维护。

两个 bat 都是启动壳：opencli_gateway_start.bat 先查重（端口 8080 已监听则提示已在运行、不重复启动），否则前台拉起 `opencode2api.exe -config config.json`，窗口先列出服务端点/管理台/配置/停止方式再显示运行日志，关窗即停，进程意外退出时给出排查提示；opencli_gateway_stop.bat 按端口 8080/8081 找到监听进程，逐进程列出端口/角色/pid 后结束，杀完复检端口并给出明确结论（已停止/未在运行/未完全停止）。

与后端的接点只有一处：后端 config.yaml 的 provider `opencli`（`api_base: http://127.0.0.1:8080/v1`，`api_key` 与网关 `server_keys` 同值）。后端把 opencli 当一个普通 provider 调用，感知不到网关内部的轮换与重试。

### 2.1 版本台账与升级记录

| 项 | 值 |
|----|----|
| 现用版本 | **v1.4.8** |
| 上游仓库 | https://github.com/jasonxu114514/opencode2api （Release：https://github.com/jasonxu114514/opencode2api/releases/tag/v1.4.8） |
| 上游 commit | `159d7fdf0fa30274cac6ea0112cd827833819e2c`（2026-11-16T21:28:09Z） |
| 上游释出 | 2026-11-16T21:34Z（北京 11-17 05:34） |
| 源码快照 | `backup\opencli_gateway-src_源码转存_20261117\gateway-src\`（全源码去 .git，125 个文件；钉版细节见该目录 `PINNED.md`，20261109 旧快照保留） |
| exe 来源 | **本地编译**：上述快照 + Go 1.25.6 `go build -trimpath -buildvcs=false -ldflags="-s -w -X main.version=v1.4.8" ./cmd/opencode2api`（参数与上游 `release.yml` 对齐） |
| exe SHA-256 | `b5b7c6b3f8bd77a7e992358977708561037b381a7b8121e8d223168465e093fc`（13,972,480 B） |
| 官方参考包 | `opencode2api_v1.4.8_windows_amd64.zip`，包 SHA-256 `ed77549a28b7922b24b39988f0803c1b088a75cae15306583ce116f1c79803f2`（下载后已比对通过），包内 exe `a211589e…2d81`／13,897,728 B／Go 1.24.13。**仅用于先验证通路，未最终装机** |
| 升级日期 | 2026-11-17，执行人 小欧 |
| 升级前版本 | v1.4.7（commit `b296a61d`，2026-11-05），exe 19,396,608 B，SHA-256 `15801b5d…b4c9` |
| 回滚包 | `backup\opencli_gateway\v1.4.7_before_upgrade_v1.4.8_20261117_134639\`（母本 exe/config + 运行目录 exe/config 四件） |

升级分两步走：先换官方 Release 包（本章许可的两条路之一）验证 v1.4.8 通路，再把源码快照前移到 `159d7fdf` 并本地编译替换。**审计链已恢复**——现在装机的 exe 就是拿 2.1 那个快照、按表里那条命令编出来的，"exe 由入库源码编出"成立，查实现不必再跑去上游仓库翻 commit。

本地 Go 1.25.6 与官方 CI 的 Go 1.24.13 编出的体积与哈希不同（13,972,480 B vs 13,897,728 B），属工具链差异，不是源码差异：`gateway-src\` 内容与 tag `v1.4.8` 一致（`git clone --depth 1 --branch v1.4.8` 后剔 `.git`，未改一行）。`-X main.version=v1.4.8` 是必带项，省了二进制自报 `dev`，`/healthz` 就分不出跑的是哪一版。

v1.4.8 对本套部署的实际影响（只列有关的三条，其余为 Responses 协议整形、legacy `functions` 转换、Go 订阅 OAuth 登录，与本部署无关）：

| 变更 | 对我们的意义 |
|------|-------------|
| 工具线上名由 `clint_` 改为 `mcp_` 命名空间（上游 PR #182） | 直接冲着免费层被拒的 `429 FreeUsageLimitError` 去的，我们跑 anonymous 车道正是吃这条修复。网关在中间改名、回程还原，宿主看到的工具名不变（实测带 tools 的请求往返后仍是客户端声明的名字） |
| 重试保留最近一次上游 HTTP 响应、状态码与 `Retry-After`；重试前释放旧连接与 WARP lease | 三次重试若全为传输失败，不再被通用网络错误掩盖——日志里能拿到真实 429，判"该换桶"还是"模型挂了"终于有据 |
| 新增可选 `upstream.prompt_environment` 与顶层 `go_subscription` | 两项均 `omitempty`，不填即保持原行为；**旧 config.json 原样可跑新 exe**，升级当时未改任何车道/重试/出口配置（`warp.enabled` 另在 2026-11-17 单独改为 true，见第 8 章） |

升级后的落地验证（2026-11-17，两次都跑过：官方包一次、最终装机的本地编译 exe 再跑一次，结论一致）：启动日志与 `/healthz` 均报 `version=v1.4.8`、`ready=true`、`exposed=12`；`/v1/models` 返回 12 个暴露模型（与升级前一致）；`deepseek-v4.1-flash-free` 普通对话 2 秒返回 `pong`；带 `tools` 的请求 3 秒返回 `finish_reason=tool_calls`，工具名与参数完整还原。以上是 `warp.enabled=false` 裸线直连下的数据，启用 WARP 后同一套请求的延迟升至 6~16 秒（见 8.3）。验证完即停掉进程，8080／8081 不留占用。

## 3 使用场景

**场景一：免费车道日常使用（现行主场景）。** 后端 provider 指向网关，全部模型请求走 anonymous 匿名免费车道。免费配额按出口网段记账，撞 429 时两层手段配合：出口层换桶（网关自带的 WARP 出口池，/64 轮换，见第 8 章）、应用层重试（网关自动重试三次，宿主无感）。网关在链路里提供了单点收口——宿主永远只对一个本地端点说话，上游怎么换、出口怎么换都不需要改宿主配置。

**场景二：接入付费键。** 拿到付费 key 时填入 `zen_keys` 或 `go_keys`，`prefer` 改指对应车道即可，宿主侧零改动。键为空时自动回落 anonymous。

**场景三：不用网关的直连形态。** 后端 config.yaml 里不启用 opencli provider（或删掉该 provider 段），宿主直连上游。这是绕开网关的备用形态：少一层转发、少一个常驻进程，代价是失去轮换、重试与令牌收口。排障时可临时切直连判断问题出在网关还是上游。

**场景边界：** 出口分两层：网关的 WARP 出口池管 anonymous 车道的应用层出口（第 8 章，现默认启用），OmniVPN 管整机网络层出口（`OmniVPN\OmniVPN使用说明.md`），两者互补不是替代关系。`warp.enabled=false` 时该车道回落 `proxies`（现为 direct 裸线）。

## 4 部署

拷 5 个文件到任意目录：opencode2api.exe、config.json、opencli_gateway_start.bat、opencli_gateway_stop.bat、opencli_gateway_stop.ps1。
出网需放行 UDP 2408 与 IPv6 出口（`warp` 现默认启用，anonymous 车道全部走上游 WARP 隧道；放不通网关起不来——初始化是 fail-closed，超时窗口为注册窗口 +30 秒。改 `warp.enabled=false` 才回到裸线直连，详见第 8 章）。
config.json.*.json 是自动生成的状态缓存，不用拷，删了会自动重建（冷启动多等 ~12 秒）。
启动壳会先把自己所在目录切为当前目录，所以换机器、换部署路径都不必改配置；注入给上游的环境块也随之指向新位置（详见 7.8）。

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
改完先按同值覆盖运行目录那一份（`opencli\config.json`），再按 5.2 → 5.1 的顺序重启网关（opencli_gateway_stop.bat → opencli_gateway_start.bat）。

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

warp 是网关内置 WARP 出口池的配置段，分 enabled（开关，现为 true）、pool_size（出口池上限，现为 2）、stack（ipv4/ipv6 栈，现为 ipv6）三项，另有可选的 source_ipv6（出口绑定的外层 IPv6 前缀，留空即用系统默认），本机未用。2026-11-17 按决策默认启用：anonymous 车道整体改走 WARP 出口，`proxies` 对该车道失效。机制、实测结论、复验数据与回退方式见第 8 章。

### 7.7 proxies / proxyfile（出口路由）

proxies 的 direct = 网关进程直连上游（走裸线出口），warp 关闭时 anonymous 车道就从这个出口走。warp.enabled=true 时 anonymous 车道自动整体改走第 8 章的 WARP 出口（实测不落回直连）。proxyfile 空 = 未用。

### 7.8 upstream（上游端点）

anonymous 是我们的上游；zen 那个参与状态文件名指纹，勿改。

网关冒充官方客户端时，system prompt 里带一段环境块：

```
<env>
  Working directory: ...
  Workspace root folder: ...
  Is directory a git repo: yes
  Platform: win32
  Today's date: ...
</env>
```

除日期外，其余四项都可被 v1.4.8 新增的可选项 `prompt_environment`（`working_directory`／`workspace_root`／`platform`／`is_git_repo`）覆写。默认值全部运行时算出，不落在配置里：`working_directory` 与 `workspace_root` 取网关进程启动时的当前目录（`os.Getwd()`，每进程只算一次，取不到才回落 `/workspace`）；`is_git_repo` 恒为 `yes`，照官方客户端文本写死，与实际是不是仓库无关；`platform` 取 `runtime.GOOS`，Windows 归一为 `win32`。

因为跟着启动目录走，**换机器或换部署目录都不用改配置**：两个启动壳开头的 `cd /d "%~dp0"` 会把当前目录切到脚本所在处，环境块随之自动指向新位置。只有从计划任务、服务、快捷方式或任意目录直接拉起 exe 时，当前目录可能是 `C:\Windows\System32` 之类，环境块就会写成那个目录。

需要钉死时（上一种启动方式，或想让它指向真正干活的后端目录）写：

```json
"upstream": {
  "prompt_environment": {
    "working_directory": "D:\\NDOOmniAgent",
    "workspace_root": "D:\\NDOOmniAgent"
  }
}
```

`platform` 留空则按主机推断；`is_git_repo` 留空或写 `true` 都是 `yes`，写 `false` 才是 `no`。本机默认值里只有工作目录与实际不符（默认指向 `opencli\`，真正干活的是后端所在的仓库根），改不改都行——这段只影响模型对环境与路径的认知，不影响路由、额度、重试与 429 处置；写错方向反而更糟：`platform` 写成 `linux` 而实际是 Windows，模型就会给 bash 命令。

该字段只能经配置 JSON 或配置 API 写入，WebUI 无独立输入框；两个路径字段禁止控制字符、行分隔符与尖括号，`platform` 只认 linux/darwin/win32（写 `windows` 自动规范为 `win32`）。

### 7.9 retry（上游重试）

max_attempts=3，timeout_seconds=300，与宿主 timeout=300 对齐。

### 7.10 models（模型目录）

refresh_seconds=300，每 5 分钟刷新；free_only=false，清单全出（现暴露 12 个，穿 WARP 实测 11 个可用，见第 8 章）。

### 7.11 performance（连接池调优）

默认值在跑，别动。

### 7.12 logging（日志）

level=info，ring_size=2000。

### 7.13 webui（管理台）

127.0.0.1:8081，用户 admin。口令以 `password_hash`（argon2id）保存，明文 `password` 字段只在设置口令那一次写入、随即被哈希取代并清空。

2026-11-17 由 `0.0.0.0:8081` 收紧回 `127.0.0.1:8081`：v1.4.8 给管理台加了 OAuth 授权管理接口与 `go_subscription` 凭据字段，管理面的价值升高，没必要再对局域网可达。改完需重启网关生效（`webui.enabled`／`webui.listen` 是重启生效项）。

### 7.14 prefer（车道偏好）

"go"；无 go_keys 时实际走 anonymous。

### 7.15 reasoning（推理力度）

effort=high。

## 8 网关内置 WARP 出口池

网关的出口有两条路：本章的内置 WARP 出口池，和整机网络层的配套服务 OmniVPN（见 `OmniVPN\OmniVPN使用说明.md`）。本章讲内置这条，它现为默认启用的主出口。

### 8.1 这是什么

网关进程 opencode2api.exe 自己内置的出口，不需要任何外部服务。设计上它是主车道之外的备胎，2026-11-17 起默认启用，成为 anonymous 车道的主出口。原理是进程内起 userspace WireGuard 隧道到 Cloudflare（UDP 2408），向 Cloudflare 注册出独立出口 IP；上游回 403/429 时，网关自动换一个新出口再试。

它与 OmniVPN 完全独立：OmniVPN 换的是整机的网络层出口，这个换的是网关自己的应用层出口，可单独用也可叠加用。2026-11-17 之前维持关闭，2026-11-17 起按决策默认启用（`enabled=true`、`pool_size=2`、`stack=ipv6`）。

### 8.2 实测结论（2026-11-12 重验）

此前"上游封锁 WARP、备胎报废"的判定是观测手段错误——在机器外测，请求根本没穿过这条车道。2026-11-12 将观测点全部移到网关进程内部（启动日志出口 IP、/healthz、穿 8080 的真实请求）重验，结论反转如下。

ipv6 栈换桶真实。每次轮换出全新 /64（实测 2a09:bac5:1f4f:2da5、1f4c:183c、1f4e:1846 等），403 后自动换出口的机制正常运转。

ipv4 栈换桶无效。Cloudflare 永远分配同一个共享 NAT 地址 104.28.208.150/32，重复注册全部被丢弃，pool_size 名存实亡。要用 WARP 必须选 stack=ipv6。

上游 403 是逐模型地域判定，不是封锁，且中招的极少。2026-11-12 把网关暴露的 12 个模型全部穿 WARP 出口逐个实测：11 个 200 成功（big-pickle、deepseek-v4.1-flash-free、flint-40b-free、glm-5.3-flash-free、iceman-free、inkling-2-small-free、longcat-2.5-free、mimo-v2.6-flash-free、minimax-m3.1-flash-free、nemotron-3.5-lightning-free、nemotron-3.5-super-vl-free），只有 beam-free 403（回复 "This model is not available in your country"，跨 3 个不同 /64 测了 5 次全部 403，是稳定的地域限制）。

隧道稳定性差。启动验证成功率约五五开，命中失败即起不来；隧道内自带 DNS 频繁超时，造成请求级 502/504——实测中凡是 502/504 的模型换一次重试全部转为 200，说明是隧道瞬时故障而非模型不可用。当时判定这是重新启用要付出的主要代价。

### 8.3 2026-11-17 启用复验

2026-11-17 14:47 把 `warp.enabled` 改为 true（`pool_size=2`、`stack=ipv6`）重启实测，8.2 里"启动验证五五开、请求级 502/504"在本机当前网络下没有复现：

| 观测项 | 结果 |
|---|---|
| 启动注册 | 一次成功。14:47:46 报 `egress … ready at 2a09:bac5:636f:1028::19c:29a`，5 秒后备用出口 `…636e:30c8::4dc:33` 就绪 |
| 池状态 | `/healthz` 的 `warp` 段：`status=ready`、`stack=ipv6`、`size=2`、`active=2`、`standby=2`、`cooling=0` |
| 换桶真实 | 两条出口分属不同 /64（`2a09:bac5:636f:1028::/64` 与 `2a09:bac5:636e:30c8::/64`），日志 `legs` 里按请求交替出现 |
| 请求结果 | 普通对话、带 tools 请求、连发 3 条，全部一次成功（`attempts=1`），未出现 502/504 |
| 延迟 | 普通对话 6 秒；带 tools 16 秒；连发 10／15／12 秒。同期裸线直连 2~3 秒 |

代价落在延迟上：每次请求都要多绕一趟 Cloudflare 隧道，工具往返越多增量越明显。本次只有 5 个请求（1 条普通对话、1 条带 tools、3 条连发），属好天气样本，长时段成功率仍需继续观察。

### 8.4 启用状态与回退

车道能力结论不变：模型覆盖接近全量，12 个暴露模型 11 个可用，仅 beam-free 被上游地域限制；ipv6 栈换桶真实，ipv4 栈无效。出口自主：`warp.enabled=true` 后 anonymous 车道的上游请求全部改走网关内置 WARP 出口（实测尝试链全部是 warp 腿，无一落回直连），不需要 mihomo 在跑、不需要系统代理和环境变量，只要求裸线能发出 UDP 2408、裸线 IPv6 可达。

2026-11-17 起默认启用，下列代价要一并记住，按影响排序：

1. **启动是 fail-closed**。注册不到出口网关直接起不来，表现为配置初始化失败、进程退出（超时窗口为注册窗口 +30 秒，源码 `internal/gateway/runtime.go`）。撞上一般是 Cloudflare 侧抖动或裸线 UDP 2408 不通，不是配置写错，重启再试。
2. **stack=ipv6 依赖本机全局 IPv6**。本机 WLAN 有 `2408:8207:2469:dd80::/64` 全局地址，故可用；换到纯 IPv4 网络会启动失败，届时改 `stack=ipv4`（能起但没有换桶能力）或临时关闭。
3. **免费车道不再经过 `proxies`**。`OmniVPN\proxy-switch.bat` 换桶对 anonymous 车道已无效，网关只在自己的 WARP 出口池里轮换；OmniVPN 仍可管整机网络层出口。
4. **延迟上行**。普通对话 2~3 秒 → 6 秒，带 tools 3 秒 → 16 秒，见 8.3。
5. **出口网段是共享的**。WARP 的 /64 由全球 WARP 用户共用，上游配额按网段记账，撞 429 的频率没有长期数据；`max_attempts=3` 会换出口重试，网段整体被打满时换桶也无效——那时只能临时 `warp.enabled=false` 回裸线（可叠 OmniVPN）换一条出口。

回退只有一步：`warp.enabled` 改回 false 重启，即回裸线直连（延迟恢复 2~3 秒），其它字段不用动。stack 固定 ipv6——ipv4 换不出新桶，没有使用价值。
