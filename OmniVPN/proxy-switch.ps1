# proxy-switch.ps1 — 一键换出口桶(撞 429 配额用完时双击)
# 编写人: 小欧    日期: 2026-11-11    版本: v1.2    更新时间: 2026-11-12 00:40:00
# 更新: v1.1 小欧 2026-11-11 exit_rotator.py 只保留 mihomo, 同步删掉 -Target v2rayn 分支
# 更新: v1.2 小欧 2026-11-12 4 轮全失败时改为询问是否自动重建节点池(nodepool\rebuild-pool.ps1)
# 更新: v1.3 小欧 2026-11-12 目录迁移 OmniVPN\: 脚本路径自洽, 不再依赖 hooks\
# 更新: v1.4 小欧 2026-11-12 输出文案统一重排: 分节 [1/4]~[4/4], 措辞精确化, 保留「换桶成功/失败」结论短语
# 用途: 换到新的出口 IP 桶(/24 或 /48 前缀 + loc 变化), 由 exit_rotator.py 判定是否真换了
# 用法:
#   powershell -ExecutionPolicy Bypass -File hooks\proxy-switch.ps1        # 观测口 mihomo:7890
# 参数:
#   -Group      mihomo 的 Selector 组名(默认 PROXY)
#   -Tries      最多换几轮(默认 4), 每轮自动试下一个节点
#   -IpTimeout  单轮等待观测超时秒数(默认 25; 实测换桶 6~8 秒, 同桶多等也无意义)
# 返回码: 0=已换到新桶  1=多轮仍未换出  2=工具/参数问题

param(
    [string]$Group = 'PROXY',
    [int]$Tries = 4,
    [int]$IpTimeout = 25
)

$ErrorActionPreference = 'Stop'
$rot = Join-Path $PSScriptRoot 'exit_rotator.py'
$on = Join-Path $PSScriptRoot 'proxy-on.ps1'

function Test-Port([int]$p) {
    return [bool](Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue)
}

# mihomo 是 HTTP 混合口 7890(命令行工具能直接用)
$port = 7890
$proxy = "http://127.0.0.1:$port"
"== OmniVPN proxy-switch: 轮换出口桶 (429 配额用尽后执行) =="
"观测口 : $proxy"

# 1. 代理没在跑就先起来(启动逻辑复用 proxy-on.ps1, 不重复实现)
if (-not (Test-Port $port)) {
    "---- 前置: 内核未运行, 执行启动 + 设系统代理 ----"
    & powershell -ExecutionPolicy Bypass -File $on -Port $port
}

# 2. 记下换桶前的桶
"---- 换桶前出口 (Cloudflare trace, 3~8 秒, 请勿中途关窗) ----"
& python $rot --verify --proxy $proxy

# 3. 反复切, 直到换出新桶(免费节点失联率高, 单轮常失败, 每轮自动试下一个存活节点)
"---- 轮换执行 (最多 $Tries 轮, 自动跳过失联节点) ----"
$ok = $false
for ($i = 1; $i -le $Tries; $i++) {
    "  -- 第 $i/$Tries 轮 --"
    & python $rot --target mihomo --wait --proxy $proxy --ip-timeout $IpTimeout --group $Group
    $rc = $LASTEXITCODE
    if ($rc -eq 0) { $ok = $true; break }
    if ($rc -eq 2) { "  [中止] 返回码 2: 控制器不可达或参数错误, 终止重试"; break }
    "  [本轮未换出] 桶指纹未变, 继续尝试下一节点"
}

# 4. 报结果
"---- 换桶后出口 (复验, 3~8 秒) ----"
& python $rot --verify --proxy $proxy
if ($ok) {
    "换桶成功: 出口桶已更新, 可继续发起请求"
    exit 0
}
"换桶失败: $Tries 轮均未换出新桶 (节点池可能整体失效)"
$ans = Read-Host "是否立即重建节点池? (9 步约 15 分钟, 完成后自动重启 mihomo) [Y/N]"
if ($ans -match '^[Yy]') {
    & powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'nodepool\rebuild-pool.ps1')
    exit $LASTEXITCODE
}
exit 1
