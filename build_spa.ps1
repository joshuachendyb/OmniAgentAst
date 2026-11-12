# ============================================================================
# build_spa.ps1 — SPA 同源打包自动化: 前端构建 + 后端 PyInstaller + 产物验证
# 创建: 2026-11-06 小欧
# 编辑历史:
#   2026-11-06 小欧 - 前置检查加版本下限(node>=18/python>=3.11): 版本过低时打包中段才暴露,
#     前置拦截更省时; 与 spec 的"dist 缺失硬报错"配套, 杜绝静默无前端包。
#   2026-11-12 小欧 - 增量打包: 用 git diff 上次打包 commit 检测变更路径, 分级处理:
#     仅 app/ 变化 → 直接复制(秒级); 仅前端变化 → build+复制(跳过 PyInstaller);
#     依赖/入口/spec 变化 → 完整 PyInstaller; --full 强制完整打包。
#     上次打包 commit 记录在 dist\.build_commit, 首次打包或记录缺失则完整打包。
# 用法: powershell -ExecutionPolicy Bypass -File build_spa.ps1
#       powershell -ExecutionPolicy Bypass -File build_spa.ps1 -Full   # 强制完整打包
#       或双击 build_spa.bat
# ============================================================================
param([switch]$Full)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$frontend = Join-Path $root "frontend"
$backend  = Join-Path $root "backend"
$spec     = Join-Path $backend "OmniAgentBackend.spec"
$distDir  = Join-Path $backend "dist\OmniAgentBackend"
$distExe  = Join-Path $distDir "OmniAgentBackend.exe"
$distWeb  = Join-Path $distDir "_internal\web\index.html"
$distVer  = Join-Path $distDir "_internal\version.txt"
$buildCommitFile = Join-Path $backend "build\.build_commit"

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
function Write-Warn($msg) { Write-Host "  [!] $msg" -ForegroundColor Yellow }

# ── 增量检测: 用 git diff 上次打包 commit 获取变更文件列表 ──
function Get-ChangeClassification {
    <#
    返回 hashtable:
      needFullBuild    — bool, 是否需要完整 PyInstaller
      needFrontendBuild — bool, 是否需要 npm run build
      needAppCopy      — bool, 是否需要复制 app/
      needWebCopy      — bool, 是否需要复制前端产物
      needConfigCopy   — bool, 是否需要复制配置文件
      changedFiles     — string[], 变更文件列表
      reason           — string, 判断说明
    #>
    $result = @{
        needFullBuild = $false
        needFrontendBuild = $false
        needAppCopy = $false
        needWebCopy = $false
        needConfigCopy = $false
        changedFiles = @()
        reason = ""
    }

    # 强制完整打包
    if ($Full) {
        $result.needFullBuild = $true
        $result.needFrontendBuild = $true
        $result.reason = "强制完整打包 (--full)"
        return $result
    }

    # 首次打包或记录缺失 → 完整打包
    if (-not (Test-Path $buildCommitFile)) {
        $result.needFullBuild = $true
        $result.needFrontendBuild = $true
        $result.reason = "首次打包(无 .build_commit 记录)"
        return $result
    }

    $lastCommit = (Get-Content $buildCommitFile -TotalCount 1).Trim()
    if (-not $lastCommit) {
        $result.needFullBuild = $true
        $result.needFrontendBuild = $true
        $result.reason = ".build_commit 为空"
        return $result
    }

    # 验证上次打包 commit 是否存在于 git 历史中
    $commitExists = try { git cat-file -t $lastCommit 2>$null } catch { $null }
    if ($commitExists -ne "commit") {
        $result.needFullBuild = $true
        $result.needFrontendBuild = $true
        $result.reason = "上次打包 commit $lastCommit 不存在于 git 历史"
        return $result
    }

    # 获取当前 commit
    $currentCommit = (git rev-parse HEAD).Trim()

    # 无任何新 commit 且工作区无变更 → 无需打包
    if ($lastCommit -eq $currentCommit) {
        # 检查工作区是否有未提交的变更
        $uncommitted = git status --porcelain 2>$null
        if (-not $uncommitted) {
            $result.reason = "无变更(上次打包 commit = 当前 commit, 工作区干净)"
            return $result
        }
    }

    # git diff 获取变更文件列表(含未提交的)
    $diffArgs = @("diff", "--name-only", $lastCommit)
    $diffOutput = git @diffArgs 2>$null
    if ($LASTEXITCODE -ne 0) {
        # git diff 失败 → 保守完整打包
        $result.needFullBuild = $true
        $result.needFrontendBuild = $true
        $result.reason = "git diff 失败, 保守完整打包"
        return $result
    }
    $result.changedFiles = $diffOutput | Where-Object { $_.Trim() } | ForEach-Object { $_.Trim() }

    # 加上未提交的工作区变更
    $statusOutput = git status --porcelain 2>$null
    foreach ($line in $statusOutput) {
        if ($line -match '^\s*[MADRC?]+\s+(.+)') {
            $filePath = $Matches[1].Trim()
            if ($filePath -notin $result.changedFiles) {
                $result.changedFiles += $filePath
            }
        }
    }

    if ($result.changedFiles.Count -eq 0) {
        $result.reason = "无变更"
        return $result
    }

    # ── 分类: 判断哪些层级的变更 ──
    $hasBackendAppChange = $false      # app/ 源码 → 可直接复制
    $hasFrontendSrcChange = $false     # frontend/src/ → 需要 npm run build
    $hasConfigChange = $false          # version.txt/config.yaml.example/OmniAgent.md → 可直接复制
    $hasFullBuildChange = $false       # 依赖/入口/spec → 必须完整 PyInstaller

    foreach ($f in $result.changedFiles) {
        # 必须完整 PyInstaller 的变更
        if ($f -match '^(backend/run_server\.py|backend/OmniAgentBackend\.spec|backend/requirements.*|backend/pyproject\.toml|backend/setup\.py|backend/setup\.cfg)') {
            $hasFullBuildChange = $true
            continue
        }
        # app/ 源码变更 → 可直接复制
        if ($f -match '^backend/app/') {
            $hasBackendAppChange = $true
            continue
        }
        # 前端源码变更 → 需要 npm run build
        if ($f -match '^frontend/') {
            $hasFrontendSrcChange = $true
            continue
        }
        # 配置文件变更 → 可直接复制
        if ($f -match '^(version\.txt|backend/config\.yaml\.example|OmniAgent\.md)') {
            $hasConfigChange = $true
            continue
        }
        # 其他文件(文档/测试/根目录脚本等) → 不影响打包
    }

    # 组合判断
    if ($hasFullBuildChange) {
        $result.needFullBuild = $true
        $result.needFrontendBuild = $true
        $result.reason = "依赖/入口/spec 变更, 必须完整 PyInstaller"
    } else {
        if ($hasFrontendSrcChange) {
            $result.needFrontendBuild = $true
            $result.needWebCopy = $true
        }
        if ($hasBackendAppChange) {
            $result.needAppCopy = $true
        }
        if ($hasConfigChange) {
            $result.needConfigCopy = $true
        }
        # 前端 build 后产物变了也需要复制
        if ($result.needFrontendBuild -and -not $hasFrontendSrcChange) {
            $result.needWebCopy = $true
        }
        $parts = @()
        if ($result.needFrontendBuild) { $parts += "前端build" }
        if ($result.needAppCopy) { $parts += "复制app/" }
        if ($result.needWebCopy) { $parts += "复制web/" }
        if ($result.needConfigCopy) { $parts += "复制配置" }
        $result.reason = if ($parts.Count -gt 0) { "增量更新: " + ($parts -join " + ") } else { "变更不影响打包产物" }
    }

    return $result
}

# ── 复制 app/ 源码到打包目录(镜像同步: 删除旧文件再复制) ──
function Sync-AppDirectory {
    $srcApp = Join-Path $backend "app"
    $dstApp = Join-Path $distDir "_internal\app"
    if (-not (Test-Path $srcApp)) { Write-Err "源 app/ 不存在: $srcApp"; return $false }
    # 删除旧目录再复制, 保证删除的文件不会残留
    if (Test-Path $dstApp) {
        Remove-Item $dstApp -Recurse -Force
    }
    Copy-Item $srcApp $dstApp -Recurse -Force
    # 清理 __pycache__
    Get-ChildItem $dstApp -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
    return $true
}

# ── 复制前端产物到打包目录(镜像同步) ──
function Sync-WebDirectory {
    $srcWeb = Join-Path $frontend "dist"
    $dstWeb = Join-Path $distDir "_internal\web"
    if (-not (Test-Path $srcWeb)) { Write-Err "前端 dist/ 不存在: $srcWeb"; return $false }
    if (Test-Path $dstWeb) {
        Remove-Item $dstWeb -Recurse -Force
    }
    # 逐文件复制(排除 stats.html, 与 spec 一致)
    New-Item $dstWeb -ItemType Directory -Force | Out-Null
    foreach ($f in (Get-ChildItem $srcWeb -Recurse -File)) {
        if ($f.Name -eq "stats.html") { continue }
        $relPath = $f.FullName.Substring($srcWeb.Length + 1)
        $dstPath = Join-Path $dstWeb $relPath
        $dstParent = Split-Path $dstPath -Parent
        if (-not (Test-Path $dstParent)) { New-Item $dstParent -ItemType Directory -Force | Out-Null }
        Copy-Item $f.FullName $dstPath -Force
    }
    return $true
}

# ── 复制配置文件到打包目录 ──
function Sync-ConfigFiles {
    $copied = @()
    $files = @(
        @{ src = (Join-Path $root "version.txt"); dst = (Join-Path $distDir "_internal\version.txt") },
        @{ src = (Join-Path $backend "config.yaml.example"); dst = (Join-Path $distDir "_internal\config.yaml.example") },
        @{ src = (Join-Path $root "OmniAgent.md"); dst = (Join-Path $distDir "_internal\OmniAgent.md") }
    )
    foreach ($pair in $files) {
        if (Test-Path $pair.src) {
            Copy-Item $pair.src $pair.dst -Force
            $copied += (Split-Path $pair.src -Leaf)
        }
    }
    return $copied
}

# ── 复制使用说明到 exe 同级 ──
function Sync-UserDoc {
    $docDir = Join-Path $root "doc-打包与E2E"
    $docs = Get-ChildItem $docDir -Filter "OmniAgent智能助手(SPA版)使用说明*.md" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime
    if ($docs) {
        $docDst = Join-Path $distDir "OmniAgent使用说明.md"
        Copy-Item $docs[-1].FullName $docDst -Force
        Write-OK "使用说明: $($docs[-1].Name) → OmniAgent使用说明.md"
    } else {
        Write-Info "使用说明: 未找到 (不影响运行)"
    }
}

Write-Header "SPA 同源打包开始"

# ── 前置检查 ──
Write-Step 0 3 "环境检查"
$nodeVer = try { (node --version) 2>$null } catch { $null }
if (-not $nodeVer) { Write-Err "node 未安装或不在 PATH"; exit 1 }
$nodeMajor = [int]($nodeVer -replace 'v','' -replace '\.\d+.*','')
if ($nodeMajor -lt 18) { Write-Err "node 版本过低: $nodeVer (需 >= 18)"; exit 1 }
Write-OK "Node.js $nodeVer"

$pyVer = try { (python --version) 2>$null } catch { $null }
if (-not $pyVer) { Write-Err "python 未安装或不在 PATH"; exit 1 }
$pyVerNum = $pyVer -replace 'Python ','' -replace '\s+',''
$pyParts = $pyVerNum -split '\.'
$pyMajor = [int]$pyParts[0]
$pyMinor = if ($pyParts.Count -gt 1) { [int]$pyParts[1] } else { 0 }
if ($pyMajor -lt 3 -or ($pyMajor -eq 3 -and $pyMinor -lt 11)) { Write-Err "python 版本过低: $pyVer (需 >= 3.11)"; exit 1 }
Write-OK "Python $pyVer"

if (-not (Test-Path $spec)) { Write-Err "spec 文件不存在: $spec"; exit 1 }
Write-OK "spec: OmniAgentBackend.spec"

# ── 增量检测 ──
Write-Step 1 3 "变更检测"
$change = Get-ChangeClassification

if ($change.changedFiles.Count -gt 0) {
    Write-Info "变更文件 ($($change.changedFiles.Count) 个):"
    foreach ($f in $change.changedFiles) { Write-Host "    $f" -ForegroundColor Gray }
}
Write-Info "判断: $($change.reason)"

# 无需任何操作
if (-not $change.needFullBuild -and -not $change.needFrontendBuild -and -not $change.needAppCopy -and -not $change.needWebCopy -and -not $change.needConfigCopy) {
    Write-OK "无变更需要打包, 产物已是最新"
    Write-Header "打包跳过 (无变更)"
    Write-Host "  产物目录: $distDir" -ForegroundColor Green
    exit 0
}

# ── [1/3] 前端构建(按需) ──
if ($change.needFrontendBuild) {
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
} else {
    Write-Step 1 3 "前端构建 — 跳过(无前端变更)"
}

# ── [2/3] 后端打包 ──
if ($change.needFullBuild) {
    Write-Step 2 3 "后端打包 (PyInstaller onedir) — 完整打包"
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
} else {
    Write-Step 2 3 "后端打包 — 增量更新(跳过 PyInstaller)"
    $stepStart = Get-Date
    if ($change.needAppCopy) {
        if (Sync-AppDirectory) {
            Write-OK "app/ 源码已同步到 _internal/app/"
        } else { exit 1 }
    }
    if ($change.needWebCopy) {
        if (Sync-WebDirectory) {
            Write-OK "前端产物已同步到 _internal/web/"
        } else { exit 1 }
    }
    if ($change.needConfigCopy) {
        $copied = Sync-ConfigFiles
        if ($copied.Count -gt 0) {
            Write-OK "配置文件已同步: $($copied -join ', ')"
        }
    }
    Sync-UserDoc
    $stepDur = (Get-Date) - $stepStart
    Write-OK "增量更新完成 ($(Format-Duration $stepDur.TotalSeconds))"
}

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
if (Test-Path $useDoc) { Write-OK "使用说明: 已放入 exe 同级" }
else { Write-Info "使用说明: 未找到 (不影响运行)" }

# ── 记录本次打包的 commit hash ──
$currentCommit = (git rev-parse HEAD).Trim()
if ($currentCommit) {
    $distParent = Split-Path $buildCommitFile -Parent
    if (-not (Test-Path $distParent)) { New-Item $distParent -ItemType Directory -Force | Out-Null }
    Set-Content $buildCommitFile $currentCommit -NoNewline
    Write-OK "已记录打包 commit: $currentCommit"
}

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