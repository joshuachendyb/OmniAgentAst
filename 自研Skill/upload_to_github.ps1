# 上传 Doc2Md Skill 到 GitHub - PowerShell 脚本
# 目标: https://github.com/joshuachendyb/jizx
# 上传路径: doc2md-skill/ 目录

# 设置编码
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  上传 Doc2Md Skill 到 GitHub" -ForegroundColor Cyan
Write-Host "  目标: https://github.com/joshuachendyb/jizx" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 配置
$UploadDir = "D:\2bktest\MDview\upload_ready"
$RepoUrl = "https://github.com/joshuachendyb/jizx.git"
$Username = "joshuachendyb"
$Password = "HMys0481"

Write-Host "[1/7] 准备上传..." -ForegroundColor Yellow
Write-Host "      源目录: $UploadDir\doc2md-skill" -ForegroundColor Gray
Write-Host "      目标: $RepoUrl" -ForegroundColor Gray
Write-Host ""

# 切换到上传目录
Set-Location -Path $UploadDir

# 检查git是否安装
Write-Host "[2/7] 检查Git安装..." -ForegroundColor Yellow
try {
    $gitVersion = git --version 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Git not found"
    }
    Write-Host "      已安装: $gitVersion" -ForegroundColor Green
} catch {
    Write-Host "      错误: Git未安装！" -ForegroundColor Red
    Write-Host "      请访问 https://git-scm.com/download/win 下载安装" -ForegroundColor Yellow
    Read-Host "按回车键退出"
    exit 1
}
Write-Host ""

# 配置git凭证（使用credential helper缓存）
Write-Host "[3/7] 配置Git凭证..." -ForegroundColor Yellow
# 设置凭证helper为cache，避免每次都输入
git config --global credential.helper cache
git config --global credential.helper 'cache --timeout=3600'
Write-Host "      已配置凭证缓存" -ForegroundColor Green
Write-Host ""

# 克隆仓库
Write-Host "[4/7] 克隆GitHub仓库..." -ForegroundColor Yellow
if (Test-Path "jizx") {
    Write-Host "      目录已存在，删除旧目录..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force "jizx"
}

# 构建带凭据的URL（仅用于克隆）
$AuthUrl = "https://$Username`:$Password@github.com/joshuachendyb/jizx.git"

try {
    git clone $AuthUrl 2>&1 | ForEach-Object { 
        if ($_ -match "error|fatal") {
            Write-Host "      $_" -ForegroundColor Red
        } else {
            Write-Host "      $_" -ForegroundColor Gray
        }
    }
    
    if ($LASTEXITCODE -ne 0) {
        throw "Clone failed"
    }
    Write-Host "      克隆成功" -ForegroundColor Green
} catch {
    Write-Host "      错误: 克隆失败！" -ForegroundColor Red
    Write-Host "      可能的原因：" -ForegroundColor Yellow
    Write-Host "      1. 网络连接问题" -ForegroundColor Yellow
    Write-Host "      2. 账号密码错误" -ForegroundColor Yellow
    Write-Host "      3. 仓库不存在" -ForegroundColor Yellow
    Read-Host "按回车键退出"
    exit 1
}
Write-Host ""

# 创建目录并复制文件
Write-Host "[5/7] 复制文件到 doc2md-skill 目录..." -ForegroundColor Yellow
Set-Location -Path "$UploadDir\jizx"
New-Item -ItemType Directory -Name "doc2md-skill" -Force | Out-Null

# 复制文件
Copy-Item -Path "$UploadDir\doc2md-skill\*" -Destination "doc2md-skill\" -Recurse -Force
Write-Host "      文件复制完成" -ForegroundColor Green
Write-Host ""

# 查看文件列表
Write-Host "      包含的文件:" -ForegroundColor Gray
Get-ChildItem "doc2md-skill\" | ForEach-Object {
    $size = if ($_.Length -gt 1024) { "{0:N0} KB" -f ($_.Length/1024) } else { "$($_.Length) B" }
    Write-Host "        - $($_.Name) ($size)" -ForegroundColor Gray
}
Write-Host ""

# Git操作
Write-Host "[6/7] Git提交..." -ForegroundColor Yellow
git add doc2md-skill/

$commitMessage = "Add doc2md-skill v1.1.0 - Word to Markdown converter with features: Smart recognition, Reliable Pandoc conversion (100%), Quality verification, Batch processing, Error recovery, History tracking"

git commit -m "$commitMessage" 2>&1 | ForEach-Object {
    Write-Host "      $_" -ForegroundColor Gray
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "      警告: 提交可能有问题，继续尝试推送..." -ForegroundColor Yellow
}
Write-Host "      提交完成" -ForegroundColor Green
Write-Host ""

# 推送 - 使用凭证URL
Write-Host "[7/7] 推送到GitHub..." -ForegroundColor Yellow
try {
    # 设置远程URL为带凭证的版本
    git remote set-url origin $AuthUrl
    
    git push origin main 2>&1 | ForEach-Object {
        if ($_ -match "error|fatal|rejected") {
            Write-Host "      $_" -ForegroundColor Red
        } elseif ($_ -match "Enumerating|Counting|Compressing|Writing|Total|done") {
            Write-Host "      $_" -ForegroundColor Gray
        } else {
            Write-Host "      $_" -ForegroundColor White
        }
    }
    
    if ($LASTEXITCODE -ne 0) {
        throw "Push failed"
    }
    
    Write-Host "      推送成功" -ForegroundColor Green
} catch {
    Write-Host ""
    Write-Host "      错误: 推送失败！" -ForegroundColor Red
    Write-Host "      尝试手动执行:" -ForegroundColor Yellow
    Write-Host "      cd $UploadDir\jizx" -ForegroundColor Cyan
    Write-Host "      git push origin main" -ForegroundColor Cyan
    Read-Host "按回车键退出"
    exit 1
}

# 恢复远程URL（移除密码）
git remote set-url origin $RepoUrl

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  上传成功！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  访问地址: https://github.com/joshuachendyb/jizx" -ForegroundColor Cyan
Write-Host ""
Write-Host "  文件已上传到 doc2md-skill/ 目录下" -ForegroundColor White
Write-Host ""

# 询问是否打开浏览器
$openBrowser = Read-Host "是否打开GitHub查看？(Y/N)"
if ($openBrowser -eq "Y" -or $openBrowser -eq "y") {
    Start-Process "https://github.com/joshuachendyb/jizx"
}

Write-Host ""
Read-Host "按回车键退出"
