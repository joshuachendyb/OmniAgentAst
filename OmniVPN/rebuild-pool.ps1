# rebuild-pool.ps1 — 节点池重建流水线(9 步一键跑完, 整池死透时用)
# 编写人: 小欧    日期: 2026-11-12    版本: v1.0    更新时间: 2026-11-12 00:40:00
# 用途: proxy-switch 连 4 轮都换桶失败 = 免费池全死; 跑本脚本从 9 个公开订阅源重抓一批:
#       抓订阅 -> 裸线TCP筛 -> TLS筛 -> 转YAML -> mihomo实测 -> 只留可用 -> 定桶 -> 排序 -> 写回配置
# 用法: 双击 rebuild-pool.bat (或 powershell -File nodepool\rebuild-pool.ps1)
# 说明: 第 5 步 mihomo 逐节点实测最慢(千级节点约 15 分钟); 并发 12 实测存活数最准, 别调大
# 产物: 全部落 log\; 第 9 步写回 mihomo\config.yaml(自动留 .bak), 跑完自动重启 mihomo

param()
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot                      # OmniVPN\nodepool
$root = Split-Path -Parent $here           # OmniVPN
$work = Join-Path $root 'log'

function Step([string]$title, [string[]]$argv) {
    "==> [$title]"
    & python @argv
    if ($LASTEXITCODE -ne 0) { throw "步骤 [$title] 失败, 退出码 $LASTEXITCODE" }
    ""
}

Step '1/9 抓 9 个公开订阅源' @((Join-Path $here '_fetch2.py'))
Step '2/9 解析去重 + 裸线 TCP 筛' @((Join-Path $here '_parse_test.py'))
Step '3/9 TLS 握手筛(防被掐)' @((Join-Path $here '_tls_probe.py'))
Step '4/9 转 mihomo YAML' @((Join-Path $here '_uri2yaml.py'),
                           (Join-Path $work 'tls_ok.txt'),
                           (Join-Path $work 'nodes_all.yaml'))
Step '5/9 mihomo 逐节点实测(最慢, 约 15 分钟, 别关窗)' @(
    (Join-Path $here '_verify_nodes.py'),
    (Join-Path $work 'nodes_all.yaml'),
    '--raw', '--ports', '7897', '9097', '--threads', '12', '--timeout', '8000',
    '--out', (Join-Path $work 'good_all.txt'))
Step '6/9 只留可用节点' @((Join-Path $here '_filter_nodes.py'),
                          (Join-Path $work 'good_all.txt'))
Step '7/9 测出口定桶' @((Join-Path $here '_survey_buckets.py'),
                        (Join-Path $work 'nodes.yaml'),
                        '--ports', '7896', '9096', '--tsv', (Join-Path $work 'buckets.tsv'))
Step '8/9 按出口桶轮转排序' @((Join-Path $here '_order_nodes.py'))
Step '9/9 写回配置(自动留 .bak)' @((Join-Path $here '_rebuild_config.py'),
                                   (Join-Path $work 'nodes_ordered.yaml'),
                                   '--apply')

"==> 重启 mihomo 加载新节点池..."
& powershell -ExecutionPolicy Bypass -File (Join-Path $root 'proxy-off.ps1') -Stop
& powershell -ExecutionPolicy Bypass -File (Join-Path $root 'proxy-on.ps1')
exit $LASTEXITCODE
