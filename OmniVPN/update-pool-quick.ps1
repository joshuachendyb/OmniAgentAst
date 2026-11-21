# update-pool-quick.ps1 — 节点池轻量巡检(约 1~2 分钟): 现池复验 + 桶分布统计 + 死点池复活结算
# 编写人: 小欧    日期: 2026-11-12    版本: v1.2    更新时间: 2026-11-21 08:47:43
# 更新: v1.1 小欧 2026-11-21 现池复验后加跑 _bucket_stats.py, 直接报"活着的池子有几个不同桶、
#                            还有几个桶没被最近 3 次换桶账本占用"(换桶策略改口径后的配套视图)
# 用途: 不重建整池, 只做三件事:
#   [现池复验] 把当前节点池(nodes_ordered.yaml, 缺则 nodes.yaml)逐节点重测, 报存活 x/y
#   [桶分布]   用存活结果 join 桶快照 log\buckets.tsv, 报互不相同的桶数与换桶可用桶数
#   [死点复活] 死点池(log\deadpool.txt)的节点追加实测(_deadpool.py revive),
#              实测后结算(复活移出/失败+1/连 5 死清除/新死入池, record)
# 用法: 双击 update-pool-quick.bat; 也挂在 proxy-switch.bat 尾部换桶后自动跑
# 说明: 临时端口 7897/9097 起 mihomo 测试实例, 不影响正在运行的 7890/9090 主实例;
#       全量重建(含抓源, 约 20~26 分钟)用 rebuild-pool.bat; _verify_nodes 退出码:
#       0=有存活 3=全死 2=基础设施错误(此时中止, 防止把故障误记成节点死)
# 更新: v1.2 小欧 2026-11-21 两处 _verify_nodes 调用加 --retry 1: 单遍实测会把抖动当死(实测同一批节点
#       连测两遍, 死的那几个换了一批), 复验少算活节点、死点被误判加重, 巡检结论会失真

param()
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot                       # OmniVPN(入口在根目录)
$here = Join-Path $root 'nodepool'          # 步骤实现脚本目录
$work = Join-Path $root 'log'
$qw = Join-Path $work 'quick'
New-Item -ItemType Directory -Force -Path $qw | Out-Null

function Step([string]$title, [string[]]$argv) {
    # 标题与空行用 Write-Host 直达控制台, 不进输出流 —— 函数返回值必须只有退出码一个
    # (曾经 "==> [$title]" 进了管道, $rc = Step 捕成数组, $rc -ne 0 恒真误抛 — 小欧 2026-11-12)
    Write-Host "==> [$title]"
    # python 的 stdout 在函数内同样会进输出流被 $rc = Step 捕获, 必须 Out-Host 定向到控制台
    & python @argv | Out-Host
    Write-Host ""
    return $LASTEXITCODE
}

# ---- [现池复验] ----
$poolNodes = Join-Path $work 'nodes_ordered.yaml'
if (-not (Test-Path $poolNodes)) { $poolNodes = Join-Path $work 'nodes.yaml' }
if (Test-Path $poolNodes) {
    $goodPool = Join-Path $qw 'good_pool.txt'
    $rc = Step '现池复验 (临时端口 7897)' @((Join-Path $here '_verify_nodes.py'), $poolNodes,
        '--raw', '--ports', '7897', '9097', '--threads', '12', '--timeout', '8000',
        '--retry', '1', '--out', $goodPool)
    if ($rc -eq 2) { throw "现池复验基础设施错误(mihomo 起不来?), 退出码 2, 中止巡检" }
    if (Test-Path $goodPool) {
        $alive = (Get-Content $goodPool | Where-Object { $_.Trim() }).Count
        $total = (Select-String -Path $poolNodes -Pattern '^\s*- name:' | Measure-Object).Count
        if ($alive -eq 0) {
            "现池存活: 0 / $total   <- 全死! 双击 rebuild-pool.bat 全量重建"
        } else {
            "现池存活: $alive / $total"
        }
        # 存活名单 join 桶快照: 报活池有几个互不相同的桶、还有几个没被最近 3 次账本占用
        # 池文件传 $poolNodes(刚复验的那份), 不用 _bucket_stats.py 默认的 mihomo\config.yaml, 口径对齐
        $rcStat = Step '现池桶分布 (离线统计)' @((Join-Path $here '_bucket_stats.py'), $poolNodes, '--alive', $goodPool)
        if ($rcStat -ne 0) { "桶分布统计跳过(退出码 $rcStat), 不影响巡检结论" }
    }
} else {
    "现池文件缺失(还没跑过 rebuild), 跳过现池复验"
}

# ---- [死点池复活] ----
$tlsDead = Join-Path $qw 'tls_quick.txt'
$injectQ = Join-Path $qw 'deadpool_inject_quick.txt'
Remove-Item $tlsDead, $injectQ -ErrorAction SilentlyContinue
New-Item -ItemType File -Force -Path $tlsDead | Out-Null   # 空文件, revive 只追加死点
$rc = Step '死点池复活注入' @((Join-Path $here '_deadpool.py'), 'revive', $tlsDead, $injectQ)
if ($rc -ne 0) { throw "死点池复活注入失败, 退出码 $rc" }

if ((Get-Item $injectQ).Length -gt 0) {
    $rc = Step '死点 URI 转 YAML' @((Join-Path $here '_uri2yaml.py'), $tlsDead, (Join-Path $qw 'nodes_dead.yaml'))
    if ($rc -ne 0) { throw "死点 URI 转 YAML 失败, 退出码 $rc" }
    $rc = Step '死点 mihomo 实测 (临时端口 7897)' @((Join-Path $here '_verify_nodes.py'),
        (Join-Path $qw 'nodes_dead.yaml'), '--raw', '--ports', '7897', '9097',
        '--threads', '12', '--timeout', '8000', '--retry', '1', '--out', (Join-Path $qw 'good_dead.txt'))
    if ($rc -eq 2) { throw "死点实测基础设施错误, 退出码 2, 中止结算(防止误记死点)" }
    $rc = Step '死点池结算(复活移出/失败+1/连5死清除)' @((Join-Path $here '_deadpool.py'), 'record',
        (Join-Path $qw 'nodes_dead.yaml.map.txt'),
        (Join-Path $qw 'good_dead.txt'),
        (Join-Path $work 'reachable.txt'),
        $injectQ)
    if ($rc -ne 0) { throw "死点池结算失败, 退出码 $rc" }
} else {
    "死点池为空, 无需复活实测"
}

""
"轻量巡检完成。全量重建(约 20~26 分钟)双击 rebuild-pool.bat"
