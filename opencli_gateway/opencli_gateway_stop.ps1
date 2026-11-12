# opencli_gateway_stop.ps1 — 网关停止逻辑 (由 opencli_gateway_stop.bat 调用)
# 编写人: 小欧    版本: v1.0    更新时间: 2026-11-12
# 修改历史（最新在最下）:
#   v1.0 2026-11-12 小欧 初版: 按端口 8080/8081 找监听进程, 逐进程列出端口/角色/pid 后结束,
#                        结束后复检端口, 结论明确(已停止/未在运行/未完全停止); 同 pid 双端口只结束一次

$ports = 8080, 8081
$roleName = @{ 8080 = '网关服务(API)'; 8081 = '管理台' }

$conns = Get-NetTCPConnection -LocalPort $ports -State Listen -ErrorAction SilentlyContinue
if (-not $conns) {
    Write-Host '[检查] 端口 8080/8081 : 未运行 (均无监听)'
    Write-Host '[结果] 网关未在运行, 无需停止'
    exit 0
}

$procs = @($conns | Select-Object -ExpandProperty OwningProcess -Unique)
foreach ($id in $procs) {
    $p = Get-Process -Id $id -ErrorAction SilentlyContinue
    if ($p) {
        $pl = @($conns | Where-Object OwningProcess -EQ $id | ForEach-Object { $_.LocalPort })
        $roles = @()
        if ($pl -contains 8080) { $roles += $roleName[8080] }
        if ($pl -contains 8081) { $roles += $roleName[8081] }
        Write-Host ('[停止] 端口 {0} ({1}) : pid={2} {3} -> 已结束' -f ($pl -join ','), ($roles -join '+'), $p.Id, $p.ProcessName)
        Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    }
}

Start-Sleep -Milliseconds 500
if (Get-NetTCPConnection -LocalPort $ports -State Listen -ErrorAction SilentlyContinue) {
    Write-Host '[警告] 仍有端口在监听, 网关未完全停止, 请复查'
} else {
    Write-Host '[结果] 网关已停止 (端口 8080/8081 均无监听)'
}
