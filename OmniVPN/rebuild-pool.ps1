# rebuild-pool.ps1 — 节点池重建流水线(11 步一键跑完, 整池死透时用)
# 编写人: 小欧    日期: 2026-11-12    版本: v1.2    更新时间: 2026-11-12 13:30:00
# 用途: proxy-switch 连 4 轮都换桶失败 = 免费池全死; 跑本脚本从公开订阅源重抓一批:
#       抓订阅 -> 裸线TCP筛 -> TLS筛 -> 死点复活注入 -> 转YAML -> mihomo实测 -> 死点结算
#       -> 只留可用 -> 定桶 -> 排序 -> 写回配置
# 用法: 双击 OmniVPN\rebuild-pool.bat (或 powershell -File OmniVPN\rebuild-pool.ps1)
# 更新: v1.1 小欧 2026-11-12 入口脚本挪至 OmniVPN 根目录(用户要求: 双击执行脚本不放子目录藏着),
#       $here 改指 nodepool\ 步骤实现目录, 九步逻辑零改动
# 更新: v1.2 小欧 2026-11-12 接入死点池(_deadpool.py): TLS 筛后注入死点复测(跳预筛直进实测),
#       实测后结算(复活移出/失败+1/连续 5 死清除/新死入池); 9 步扩为 11 步
# 说明: 第 6 步 mihomo 逐节点实测最慢(千级节点约 15 分钟); 并发 12 实测存活数最准, 别调大
# 产物: 全部落 log\; 第 11 步写回 mihomo\config.yaml(自动留 .bak), 跑完自动重启 mihomo

param()
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot                      # OmniVPN(入口在根目录, 步骤实现在 nodepool\)
$here = Join-Path $root 'nodepool'         # 流水线步骤脚本目录
$work = Join-Path $root 'log'

function Step([string]$title, [string[]]$argv) {
    "==> [$title]"
    & python @argv
    if ($LASTEXITCODE -ne 0) { throw "步骤 [$title] 失败, 退出码 $LASTEXITCODE" }
    ""
}

Step '1/11 抓公开订阅源(并行)' @((Join-Path $here '_fetch2.py'))
Step '2/11 解析去重 + 裸线 TCP 筛' @((Join-Path $here '_parse_test.py'))
Step '3/11 TLS 握手筛(防被掐)' @((Join-Path $here '_tls_probe.py'))
Step '4/11 死点池复活注入' @((Join-Path $here '_deadpool.py'),
                             'revive',
                             (Join-Path $work 'tls_ok.txt'),
                             (Join-Path $work 'deadpool_inject.txt'))
Step '5/11 转 mihomo YAML' @((Join-Path $here '_uri2yaml.py'),
                           (Join-Path $work 'tls_ok.txt'),
                           (Join-Path $work 'nodes_all.yaml'))
Step '6/11 mihomo 逐节点实测(最慢, 约 15 分钟, 别关窗)' @(
    (Join-Path $here '_verify_nodes.py'),
    (Join-Path $work 'nodes_all.yaml'),
    '--raw', '--ports', '7897', '9097', '--threads', '12', '--timeout', '8000',
    '--out', (Join-Path $work 'good_all.txt'))
Step '7/11 死点池结算(复活移出/失败+1/连5死清除/新死入池)' @((Join-Path $here '_deadpool.py'),
                             'record',
                             (Join-Path $work 'nodes_all.yaml.map.txt'),
                             (Join-Path $work 'good_all.txt'),
                             (Join-Path $work 'reachable.txt'),
                             (Join-Path $work 'deadpool_inject.txt'))
Step '8/11 只留可用节点' @((Join-Path $here '_filter_nodes.py'),
                          (Join-Path $work 'good_all.txt'))
Step '9/11 测出口定桶' @((Join-Path $here '_survey_buckets.py'),
                        (Join-Path $work 'nodes.yaml'),
                        '--ports', '7896', '9096', '--tsv', (Join-Path $work 'buckets.tsv'))
Step '10/11 按出口桶轮转排序' @((Join-Path $here '_order_nodes.py'))
Step '11/11 写回配置(自动留 .bak)' @((Join-Path $here '_rebuild_config.py'),
                                   (Join-Path $work 'nodes_ordered.yaml'),
                                   '--apply')

"==> 重启 mihomo 加载新节点池..."
& powershell -ExecutionPolicy Bypass -File (Join-Path $root 'proxy-off.ps1') -Stop
& powershell -ExecutionPolicy Bypass -File (Join-Path $root 'proxy-on.ps1')
exit $LASTEXITCODE
