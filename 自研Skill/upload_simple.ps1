# 上传 Doc2Md Skill 到 GitHub - PowerShell 脚本
# 目标: https://github.com/joshuachendyb/jizx

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Upload Doc2Md Skill to GitHub" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 配置
$UploadDir = "D:\2bktest\MDview\upload_ready"
$RepoUrl = "https://github.com/joshuachendyb/jizx.git"
$Username = "joshuachendyb"
$Password = "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"

Write-Host "[Step 1] Preparing upload..." -ForegroundColor Yellow
Write-Host "         Source: $UploadDir\doc2md-skill" -ForegroundColor Gray
Write-Host ""

Set-Location -Path $UploadDir

# 检查git
Write-Host "[Step 2] Checking Git..." -ForegroundColor Yellow
try {
    $gitVersion = git --version 2>$null
    if ($LASTEXITCODE -ne 0) { throw "Git not found" }
    Write-Host "         Git installed: $gitVersion" -ForegroundColor Green
} catch {
    Write-Host "         ERROR: Git not installed!" -ForegroundColor Red
    Write-Host "         Please install from https://git-scm.com/download/win" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host ""

# 克隆仓库
Write-Host "[Step 3] Cloning repository..." -ForegroundColor Yellow
if (Test-Path "jizx") {
    Write-Host "         Removing old directory..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force "jizx"
}

$AuthUrl = "https://$Username`:$Password@github.com/joshuachendyb/jizx.git"

try {
    git clone $AuthUrl 2>&1 | ForEach-Object { Write-Host "         $_" -ForegroundColor Gray }
    if ($LASTEXITCODE -ne 0) { throw "Clone failed" }
    Write-Host "         Clone successful" -ForegroundColor Green
} catch {
    Write-Host "         ERROR: Clone failed!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host ""

# 复制文件
Write-Host "[Step 4] Copying files..." -ForegroundColor Yellow
Set-Location -Path "$UploadDir\jizx"
New-Item -ItemType Directory -Name "doc2md-skill" -Force | Out-Null
Copy-Item -Path "$UploadDir\doc2md-skill\*" -Destination "doc2md-skill\" -Recurse -Force
Write-Host "         Files copied" -ForegroundColor Green
Write-Host ""

# Git提交
Write-Host "[Step 5] Git commit..." -ForegroundColor Yellow
git add doc2md-skill/

# 简化的提交信息（避免特殊字符）
$msg = "Add doc2md-skill v1.1.0 - Word to Markdown converter with batch processing and verification"
git commit -m "$msg" 2>&1 | ForEach-Object { Write-Host "         $_" -ForegroundColor Gray }
Write-Host "         Commit done" -ForegroundColor Green
Write-Host ""

# 推送
Write-Host "[Step 6] Pushing to GitHub..." -ForegroundColor Yellow
try {
    git remote set-url origin $AuthUrl
    git push origin main 2>&1 | ForEach-Object { Write-Host "         $_" -ForegroundColor Gray }
    if ($LASTEXITCODE -ne 0) { throw "Push failed" }
    Write-Host "         Push successful" -ForegroundColor Green
} catch {
    Write-Host "         ERROR: Push failed!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

git remote set-url origin $RepoUrl

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Upload Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Visit: https://github.com/joshuachendyb/jizx" -ForegroundColor Cyan
Write-Host ""

$open = Read-Host "Open GitHub in browser? (Y/N)"
if ($open -eq "Y" -or $open -eq "y") {
    Start-Process "https://github.com/joshuachendyb/jizx"
}

Write-Host ""
Read-Host "Press Enter to exit"
