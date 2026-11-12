# ============================================================================
# build_spa.ps1 — SPA 打包自动化: 前端构建 + 后端 PyInstaller + 产物验证
# 创建: 2026-11-06 小欧
# 编辑历史:
#   2026-11-06 小欧 - 前置检查加版本下限(node>=18/python>=3.11): 版本过低时打包中段才暴露,
#     前置拦截更省时; 与 spec 的"dist 缺失硬报错"配套, 杜绝静默无前端包。
#   2026-11-12 小欧 - 增量打包: 用 git diff 上次打包 commit 检测变更路径, 分级处理:
#     仅 app/ 变化 → 直接复制(秒级); 仅前端变化 → build+复制(跳过 PyInstaller);
#     依赖/入口/spec 变化 → 完整 PyInstaller; --full 强制完整打包。
#     上次打包 commit 记录在 build\.build_commit, 首次打包或记录缺失则完整打包。
#   2026-11-12 小欧 - 提示信息重新设计: 阶段标题简洁明确, 技术用词准确,
#     增量/完整判定结果清晰展示, 操作反馈精确(做了什么/耗时/产出)。
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

function Write-Phase($msg) {
    $line = "=" * 60
    Write-Host ""
    Write-Host $line -ForegroundColor Yellow
    Write-Host "  $msg" -ForegroundColor Yellow
    Write-Host $line -ForegroundColor Yellow
}

function Write-Step($msg) {
    Write-Host ""
    Write-Host "── $msg ──" -ForegroundColor Cyan
}

function Write-OK($msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Info($msg) { Write-Host "  [..] $msg" -ForegroundColor Gray }
function Write-Err($msg)  { Write-Host "  [FAIL] $msg" -ForegroundColor Red }
function Write-Skip($msg) { Write-Host "  [SKIP] $msg" -ForegroundColor DarkGray }

# ── 增量检测: 用 git diff 上次打包 commit 获取变更文件列表 ──
function Get-ChangeClassification {
    $result = @{
        needFullBuild = $false
        needFrontendBuild = $false
        needAppCopy = $false
        needWebCopy = $false
        needConfigCopy = $false
        changedFiles = @()
        reason = ""
    }

    if ($Full) {
        $result.needFullBuild = $true
        $result.needFrontendBuild = $true
        $result.reason = "强制完整打包 (--full 参数)"
        return $result
    }

    if (-not (Test-Path $buildCommitFile)) {
        $result.needFullBuild = $true
        $result.needFrontendBuild = $true
        $result.reason = "首次打包 (无历史打包记录)"
        return $result
    }

    $lastCommit = (Get-Content $buildCommitFile -TotalCount 1).Trim()
    if (-not $lastCommit) {
        $result.needFullBuild = $true
        $result.needFrontendBuild = $true
        $result.reason = "打包记录为空, 无法增量比对"
        return $result
    }

    $commitExists = try { git cat-file -t $lastCommit 2>$null } catch { $null }
    if ($commitExists -ne "commit") {
        $result.needFullBuild = $true
        $result.needFrontendBuild = $true
        $result.reason = "历史打包 commit 已不在 git 记录中"
        return $result
    }

    $currentCommit = (git rev-parse HEAD).Trim()

    if ($lastCommit -eq $currentCommit) {
        $uncommitted = git status --porcelain 2>$null
        if (-not $uncommitted) {
            $result.reason = "无变更 (代码与上次打包完全一致)"
            return $result
        }
    }

    $diffArgs = @("diff", "--name-only", $lastCommit)
    $diffOutput = git @diffArgs 2>$null
    if ($LASTEXITCODE -ne 0) {
        $result.needFullBuild = $true
        $result.needFrontendBuild = $true
        $result.reason = "git diff 执行失败, 保守走完整打包"
        return $result
    }
    $result.changedFiles = $diffOutput | Where-Object { $_.Trim() } | ForEach-Object { $_.Trim() }

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

    $hasBackendAppChange = $false
    $hasFrontendSrcChange = $false
    $hasConfigChange = $false
    $hasFullBuildChange = $false

    foreach ($f in $result.changedFiles) {
        if ($f -match '^(backend/run_server\.py|backend/OmniAgentBackend\.spec|backend/requirements.*|backend/pyproject\.toml|backend/setup\.py|backend/setup\.cfg)') {
            $hasFullBuildChange = $true
            continue
        }
        if ($f -match '^backend/app/') {
            $hasBackendAppChange = $true
            continue
        }
        if ($f -match '^frontend/') {
            $hasFrontendSrcChange = $true
            continue
        }
        if ($f -match '^(version\.txt|backend/config\.yaml\.example|OmniAgent\.md)') {
            $hasConfigChange = $true
            continue
        }
    }

    if ($hasFullBuildChange) {
        $result.needFullBuild = $true
        $result.needFrontendBuild = $true
        $result.reason = "入口/依赖/spec 变更 → 必须完整 PyInstaller 重新构建"
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
        if ($result.needFrontendBuild -and -not $hasFrontendSrcChange) {
            $result.needWebCopy = $true
        }
        $parts = @()
        if ($result.needFrontendBuild) { $parts += "前端构建" }
        if ($result.needAppCopy) { $parts += "app/ 源码同步" }
        if ($result.needWebCopy) { $parts += "web/ 产物同步" }
        if ($result.needConfigCopy) { $parts += "配置文件同步" }
        $result.reason = if ($parts.Count -gt 0) { "增量更新: " + ($parts -join " + ") } else { "变更不涉及打包产物" }
    }

    return $result
}

# ── 镜像同步 app/ 源码到打包目录 ──
function Sync-AppDirectory {
    $srcApp = Join-Path $backend "app"
    $dstApp = Join-Path $distDir "_internal\app"
    if (-not (Test-Path $srcApp)) { Write-Err "源目录不存在: $srcApp"; return $false }
    if (Test-Path $dstApp) {
        Remove-Item $dstApp -Recurse -Force
    }
    Copy-Item $srcApp $dstApp -Recurse -Force
    Get-ChildItem $dstApp -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
    return $true
}

# ── 镜像同步前端产物到打包目录 ──
function Sync-WebDirectory {
    $srcWeb = Join-Path $frontend "dist"
    $dstWeb = Join-Path $distDir "_internal\web"
    if (-not (Test-Path $srcWeb)) { Write-Err "前端构建产物不存在: $srcWeb"; return $false }
    if (Test-Path $dstWeb) {
        Remove-Item $dstWeb -Recurse -Force
    }
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

# ── 同步配置文件到打包目录 ──
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

# ── 同步使用说明到 exe 同级 ──
function Sync-UserDoc {
    $docDir = Join-Path $root "doc-打包与E2E"
    $docs = Get-ChildItem $docDir -Filter "OmniAgent智能助手(SPA版)使用说明*.md" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime
    if ($docs) {
        $docDst = Join-Path $distDir "OmniAgent使用说明.md"
        Copy-Item $docs[-1].FullName $docDst -Force
        Write-OK "使用说明: $($docs[-1].Name) → OmniAgent使用说明.md"
    } else {
        Write-Info "使用说明: 未找到匹配文件 (不影响运行)"
    }
}

# ════════════════════════════════════════════════════════════
#  OmniAgent SPA 打包流程
#  前端 (Vite) + 后端 (PyInstaller) → 单目录可执行产物
# ════════════════════════════════════════════════════════════
Write-Phase "OmniAgent SPA 打包"

# ── 阶段 0: 环境前置检查 ──
Write-Step "阶段 0/4: 环境前置检查"

$nodeVer = try { (node --version) 2>$null } catch { $null }
if (-not $nodeVer) { Write-Err "Node.js 未安装或不在 PATH"; exit 1 }
$nodeMajor = [int]($nodeVer -replace 'v','' -replace '\.\d+.*','')
if ($nodeMajor -lt 18) { Write-Err "Node.js 版本过低: $nodeVer (需 >= 18)"; exit 1 }
Write-OK "Node.js $nodeVer"

$pyVer = try { (python --version) 2>$null } catch { $null }
if (-not $pyVer) { Write-Err "Python 未安装或不在 PATH"; exit 1 }
$pyVerNum = $pyVer -replace 'Python ','' -replace '\s+',''
$pyParts = $pyVerNum -split '\.'
$pyMajor = [int]$pyParts[0]
$pyMinor = if ($pyParts.Count -gt 1) { [int]$pyParts[1] } else { 0 }
if ($pyMajor -lt 3 -or ($pyMajor -eq 3 -and $pyMinor -lt 11)) { Write-Err "Python 版本过低: $pyVer (需 >= 3.11)"; exit 1 }
Write-OK "Python $pyVer"

if (-not (Test-Path $spec)) { Write-Err "PyInstaller spec 文件不存在: $spec"; exit 1 }
Write-OK "PyInstaller spec: OmniAgentBackend.spec"

# ── 阶段 1: 变更检测 (增量判定) ──
Write-Step "阶段 1/4: 变更检测 (增量判定)"
Write-Info "基于 git diff 对比上次打包 commit, 判定本次操作级别"

$change = Get-ChangeClassification

if ($change.changedFiles.Count -gt 0) {
    Write-Info "变更文件 ($($change.changedFiles.Count) 个):"
    foreach ($f in $change.changedFiles) { Write-Host "    $f" -ForegroundColor Gray }
}
Write-Host ""
Write-Host "  判定结果: $($change.reason)" -ForegroundColor White

# 无需任何操作 — 跳过构建阶段, 直接进入部署选择
$skipBuild = -not $change.needFullBuild -and -not $change.needFrontendBuild -and -not $change.needAppCopy -and -not $change.needWebCopy -and -not $change.needConfigCopy
if ($skipBuild) {
    Write-Host ""
    Write-Phase "产物已是最新 — 无需重新打包"
    Write-Host "  产物目录: $distDir" -ForegroundColor Green
}

# ── 阶段 2: 前端构建 ──
if (-not $skipBuild) {
if ($change.needFrontendBuild) {
    Write-Step "阶段 2/4: 前端构建 (Vite 生产构建)"
    Write-Info "命令: npm run build (tsc 类型检查 + vite build 打包)"
    Write-Info "输出: frontend/dist/"
    $stepStart = Get-Date
    Push-Location $frontend
    try {
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "npm run build 退出码 $LASTEXITCODE" }
    } catch {
        Write-Err "前端构建失败: $_"
        Write-Info "常见原因: TypeScript 类型错误 / 依赖未安装 (需 npm install)"
        Pop-Location; exit 1
    } finally { Pop-Location }
    $stepDur = (Get-Date) - $stepStart
    $assetCount = (Get-ChildItem (Join-Path $frontend "dist\assets") -File -ErrorAction SilentlyContinue).Count
    Write-OK "前端构建完成 — $assetCount 个静态资源, 耗时 $(Format-Duration $stepDur.TotalSeconds)"
} else {
    Write-Step "阶段 2/4: 前端构建"
    Write-Skip "跳过 — 无前端源码变更"
}

# ── 阶段 3: 后端打包 ──
if ($change.needFullBuild) {
    Write-Step "阶段 3/4: 后端打包 (PyInstaller 完整构建)"
    Write-Info "模式: 完整构建 (重新生成 exe + 所有依赖)"
    Write-Info "spec: OmniAgentBackend.spec"
    Write-Info "输出: backend/dist/OmniAgentBackend/"
    $stepStart = Get-Date
    Push-Location $backend
    try {
        python -m PyInstaller $spec --noconfirm
        if ($LASTEXITCODE -ne 0) { throw "PyInstaller 退出码 $LASTEXITCODE" }
    } catch {
        Write-Err "PyInstaller 构建失败: $_"
        Write-Info "常见原因: spec 配置错误 / 前端 dist 缺失 / Python 依赖未安装"
        Pop-Location; exit 1
    } finally { Pop-Location }
    $stepDur = (Get-Date) - $stepStart
    Write-OK "PyInstaller 完整构建完成, 耗时 $(Format-Duration $stepDur.TotalSeconds)"
} else {
    Write-Step "阶段 3/4: 后端增量更新 (跳过 PyInstaller)"
    Write-Info "模式: 源码同步 (直接复制变更文件到打包目录, 不重新构建 exe)"
    $stepStart = Get-Date
    if ($change.needAppCopy) {
        Write-Info "同步 app/ 源码 → _internal/app/ (镜像同步: 删除旧目录后完整复制)"
        if (Sync-AppDirectory) {
            Write-OK "app/ 源码同步完成"
        } else { exit 1 }
    }
    if ($change.needWebCopy) {
        Write-Info "同步前端产物 → _internal/web/ (镜像同步)"
        if (Sync-WebDirectory) {
            Write-OK "前端产物同步完成"
        } else { exit 1 }
    }
    if ($change.needConfigCopy) {
        Write-Info "同步配置文件 → _internal/"
        $copied = Sync-ConfigFiles
        if ($copied.Count -gt 0) {
            Write-OK "配置文件同步完成: $($copied -join ', ')"
        }
    }
    Sync-UserDoc
    $stepDur = (Get-Date) - $stepStart
    Write-OK "增量更新完成, 耗时 $(Format-Duration $stepDur.TotalSeconds)"
}
}

# ── 阶段 4: 产物完整性验证 ──
Write-Step "阶段 4/4: 产物完整性验证"

if (Test-Path $distExe) {
    $exeSize = [math]::Round((Get-Item $distExe).Length / 1MB, 1)
    Write-OK "可执行文件: OmniAgentBackend.exe (${exeSize}MB)"
} else { Write-Err "可执行文件缺失: $distExe"; exit 1 }

if (Test-Path $distWeb) {
    Write-OK "前端页面: _internal/web/index.html (已嵌入)"
} else { Write-Err "前端页面缺失: _internal/web/index.html"; exit 1 }

if (Test-Path $distVer) {
    $ver = Get-Content $distVer -TotalCount 1
    Write-OK "版本标识: $ver"
} else { Write-Err "版本标识缺失: _internal/version.txt"; exit 1 }

$useDoc = Join-Path $distDir "OmniAgent使用说明.md"
if (Test-Path $useDoc) { Write-OK "使用说明: OmniAgent使用说明.md (已放入 exe 同级)" }
else { Write-Info "使用说明: 未找到 (不影响运行)" }

# ── 记录本次打包 commit (仅实际打包时更新) ──
if (-not $skipBuild) {
    $currentCommit = (git rev-parse HEAD).Trim()
    if ($currentCommit) {
        $buildParent = Split-Path $buildCommitFile -Parent
        if (-not (Test-Path $buildParent)) { New-Item $buildParent -ItemType Directory -Force | Out-Null }
        Set-Content $buildCommitFile $currentCommit -NoNewline
        Write-OK "打包基准 commit 已记录: $currentCommit"
    }
}

# ── 完成 ──
$totalDur = (Get-Date) - $scriptStart
if (-not $skipBuild) {
    Write-Phase "打包完成 — 总耗时 $(Format-Duration $totalDur.TotalSeconds)"
} else {
    Write-Phase "就绪 — 总耗时 $(Format-Duration $totalDur.TotalSeconds)"
}
Write-Host ""
Write-Host "  产物目录:" -ForegroundColor White
Write-Host "    $distDir" -ForegroundColor Green
Write-Host ""

# ── 部署选择 ──
$deployScript = Join-Path $backend "deploy_spa.py"
$deployBat = Join-Path $root "deploy_spa.bat"
$deployTarget = "G:\OmniAgent-SPA"
Write-Host "  是否部署到 $deployTarget ?" -ForegroundColor White
$choice = Read-Host "  输入 Y 部署, N 退出 (默认 N)"
if ($choice -eq 'Y' -or $choice -eq 'y') {
    Write-Host ""
    Write-Host "  执行部署脚本..." -ForegroundColor Cyan
    python $deployScript
    if ($LASTEXITCODE -ne 0) {
        Write-Err "部署失败 (退出码 $LASTEXITCODE)"
    }
} else {
    Write-Host ""
    Write-Host "  部署方式:" -ForegroundColor White
    Write-Host "    命令:   python backend\deploy_spa.py" -ForegroundColor Cyan
    Write-Host "    双击:   deploy_spa.bat" -ForegroundColor Cyan
}
Write-Host ""