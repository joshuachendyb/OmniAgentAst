# ============================================================================
# build_spa.ps1 — SPA 同源打包自动化: 前端构建 + 后端 PyInstaller + 产物验证
# 创建: 2026-11-06 小欧
# 用法: powershell -ExecutionPolicy Bypass -File build_spa.ps1
#       或双击 build_spa.bat
# ============================================================================
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$frontend = Join-Path $root "frontend"
$backend  = Join-Path $root "backend"
$spec     = Join-Path $backend "OmniAgentBackend.spec"
$distDir  = Join-Path $backend "dist\OmniAgentBackend"
$distExe  = Join-Path $distDir "OmniAgentBackend.exe"
$distWeb  = Join-Path $distDir "_internal\web\index.html"
$distVer  = Join-Path $distDir "_internal\version.txt"

$scriptStart = Get-Date

function Format-Duration($s) {
    if ($s -lt 60) { return "{0:F1}s" -f $s }
    $m = [int]$s / 60; $rs = $s % 60
    return "{0}m{1:F0}s" -f $m, $rs
}

function Write-Header($msg) {
    $line = "=" * 60
    Write-Host ""
    Write-Host $line -ForegroundColor Yellow
    Write-Host "  $msg" -ForegroundColor Yellow
    Write-Host $line -ForegroundColor Yellow
}

function Write-Step($n, $total, $msg) {
    Write-Host ""
    Write-Host "── [$n/$total] $msg ──" -ForegroundColor Cyan
}

function Write-OK($msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Info($msg) { Write-Host "  [..] $msg" -ForegroundColor Gray }
function Write-Err($msg)  { Write-Host "  [FAIL] $msg" -ForegroundColor Red }

Write-Header "SPA 同源打包开始"

# ── 前置检查 ──
Write-Step 0 3 "环境检查"
$nodeVer = try { (node --version) 2>$null } catch { $null }
if (-not $nodeVer) { Write-Err "node 未安装或不在 PATH"; exit 1 }
Write-OK "Node.js $nodeVer"

$pyVer = try { (python --version) 2>$null } catch { $null }
if (-not $pyVer) { Write-Err "python 未安装或不在 PATH"; exit 1 }
Write-OK "Python $pyVer"

if (-not (Test-Path $spec)) { Write-Err "spec 文件不存在: $spec"; exit 1 }
Write-OK "spec: OmniAgentBackend.spec"

# ── [1/3] 前端构建 ──
Write-Step 1 3 "前端构建 (npm run build = tsc + vite build)"
Write-Info "输出目录: frontend\dist\"
$stepStart = Get-Date
Push-Location $frontend
try {
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "npm run build 退出码 $LASTEXITCODE" }
} catch {
    Write-Err "前端构建失败: $_"
    Write-Info "常见原因: TypeScript 类型错误 / 依赖未安装 (npm install)"
    Pop-Location; exit 1
} finally { Pop-Location }
$stepDur = (Get-Date) - $stepStart
$assetCount = (Get-ChildItem (Join-Path $frontend "dist\assets") -File -ErrorAction SilentlyContinue).Count
Write-OK "前端构建完成 ($assetCount 个 assets, $(Format-Duration $stepDur.TotalSeconds))"

# ── [2/3] 后端打包 ──
Write-Step 2 3 "后端打包 (PyInstaller onedir)"
Write-Info "spec: $spec"
Write-Info "输出目录: backend\dist\OmniAgentBackend\"
$stepStart = Get-Date
Push-Location $backend
try {
    python -m PyInstaller $spec --noconfirm
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller 退出码 $LASTEXITCODE" }
} catch {
    Write-Err "后端打包失败: $_"
    Write-Info "常见原因: spec 配置错误 / 前端 dist 缺失 / 依赖未安装"
    Pop-Location; exit 1
} finally { Pop-Location }
$stepDur = (Get-Date) - $stepStart
Write-OK "后端打包完成 ($(Format-Duration $stepDur.TotalSeconds))"

# ── [3/3] 验证产物 ──
Write-Step 3 3 "产物验证"

if (Test-Path $distExe) {
    $exeSize = [math]::Round((Get-Item $distExe).Length / 1MB, 1)
    Write-OK "exe: ${exeSize}MB"
} else { Write-Err "exe 缺失: $distExe"; exit 1 }

if (Test-Path $distWeb) {
    Write-OK "前端已嵌入: _internal\web\index.html"
} else { Write-Err "web/index.html 缺失 (前端未嵌入, 检查 frontend\dist 是否存在)"; exit 1 }

if (Test-Path $distVer) {
    $ver = Get-Content $distVer -TotalCount 1
    Write-OK "版本: $ver"
} else { Write-Err "version.txt 缺失"; exit 1 }

$useDoc = Join-Path $distDir "OmniAgent使用说明.md"
if (Test-Path $useDoc) { Write-OK "使用说明: 已自动放入 exe 同级" }
else { Write-Info "使用说明: 未找到 (不影响运行)" }

# ── 完成 ──
$totalDur = (Get-Date) - $scriptStart
Write-Header "打包完成 (总耗时 $(Format-Duration $totalDur.TotalSeconds))"
Write-Host ""
Write-Host "  产物目录:" -ForegroundColor White
Write-Host "    $distDir" -ForegroundColor Green
Write-Host ""
Write-Host "  下一步 — 部署到 G:\OmniAgent-SPA:" -ForegroundColor White
Write-Host "    python backend\deploy_spa.py" -ForegroundColor Cyan
Write-Host ""