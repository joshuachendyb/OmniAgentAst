# proxy-switch-single.ps1 — 一键换出口桶(一级模式, 撞 429 配额用完时双击)
# 编写人: 商量    日期: 2026-11-28    版本: v1.1
# 用途: 与二级 proxy-switch.ps1 并存互斥。一级模式 = PROXY 直接选单级节点(无二级池),
#       换桶轮换 PROXY 组(成员 = 节点 + Auto + DIRECT), 与单级 exit_rotator 口径一致。
#       一级实例独立端口 7892/9092, 与二级 7890/9090 并存不冲突。
# 用法:
#   powershell -ExecutionPolicy Bypass -File proxy-switch-single.ps1        # 观测口 mihomo:7892
# 参数:
#   -Group      mihomo 的 Selector 组名(默认 PROXY)
#   -Tries      最多换几轮(默认 6), 每轮自动试下一个节点
#   -IpTimeout  单轮等待观测超时秒数(默认 25)
# 返回码: 0=已换到新桶  1=多轮仍未换出  2=工具/参数问题

param(
    [string]$Group = 'PROXY',
    [int]$Tries = 6,
    [int]$IpTimeout = 25
)

$ErrorActionPreference = 'Stop'
$rot = Join-Path $PSScriptRoot 'exit_rotator.py'
$on = Join-Path $PSScriptRoot 'proxy-on-single.ps1'
$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

function Test-Port([int]$p) {
    return [bool](Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue)
}

# 一级 mihomo 是 HTTP 混合口 7892(命令行工具能直接用)
$port = 7892
$proxy = "http://127.0.0.1:$port"

"============================================================"
"proxy-switch-single v1.0  轮换出口桶(一级模式)   $stamp"
"============================================================"
""

# 1. 前置: 代理没在跑就先起来(启动逻辑复用 proxy-on-single.ps1, 不重复实现)
'[1] 前置检查 (内核 + 观测口)'
"    观测口     : $proxy"
if (-not (Test-Port $port)) {
    "    内核端口 $port : 未运行, 执行启动 + 设系统代理"
    & powershell -ExecutionPolicy Bypass -File $on -Port $port
} else {
    "    内核端口 $port : 运行中"
}
""

# 2. 记下换桶前的桶
'[2] 换桶前出口 (Cloudflare trace, 3~8 秒, 请勿中途关窗)'
& python $rot --verify --proxy $proxy | ForEach-Object { "    $_" }
""

# 3. 反复切, 直到换出最近 3 次以外的新桶
"[3] 轮换执行 (最多 $Tries 轮, 新桶须避开最近 3 次用过的桶)"
$ok = $false
for ($i = 1; $i -le $Tries; $i++) {
    "    -- 第 $i/$Tries 轮 --"
    & python $rot --target mihomo --wait --proxy $proxy --ip-timeout $IpTimeout --group $Group | ForEach-Object { "    $_" }
    $rc = $LASTEXITCODE
    if ($rc -eq 0) { $ok = $true; break }
    if ($rc -eq 2) { '    [中止] 返回码 2: 控制器不可达或参数错误, 终止重试'; break }
    '    [本轮未换出] 出口仍落在最近 3 次用过的桶内, 继续尝试下一节点'
}
""

# 4. 报结果
'[4] 换桶后出口 (复验, 3~8 秒)'
& python $rot --verify --proxy $proxy | ForEach-Object { "    $_" }
if ($ok) {
    '换桶成功: 出口桶已更新, 可继续发起请求'
    exit 0
}
'换桶失败: ' + $Tries + ' 轮均未换出新桶 (节点池可能整体失效, 或池内出口桶都已在最近 3 次里)'
'           若确认池内还有可用节点, 可先执行 exit_rotator.py --reset-history 清空换桶历史再试'
exit 1
