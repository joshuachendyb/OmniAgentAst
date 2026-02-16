# GitHub Push和Download备用指南

**创建时间**: 2026-02-12 21:35:24  
**版本**: v1.0  
**更新时间**: 2026-02-12 21:35:24  
**更新说明**: 初始版本

---

## 一、文档概述

### 1.1 编写目的

本文档旨在为用户提供GitHub访问的备用方案指南，解决GitHub连接不稳定、访问速度慢等问题。通过本文档，用户可以了解如何使用国内代理中转服务、FastGithub工具以及gh CLI优化GitHub操作体验。

### 1.2 适用范围

本文档适用于所有需要在Windows环境下访问GitHub的用户，尤其是以下场景：

- GitHub仓库push操作频繁失败或超时
- GitHub仓库clone速度极慢
- 需要在国内网络环境下高效使用GitHub
- 需要配置稳定可靠的GitHub访问方案

### 1.3 核心策略

针对GitHub访问的不同操作类型，我们采用差异化的备用方案策略：

| 操作类型 | 推荐方案 | 说明 |
|---------|---------|------|
| **Push操作** | githubfast.com | 国内加速服务，专为push优化 |
| **Download操作** | ghps.cc或kkgithub.com | 代理中转，下载速度快 |
| **日常浏览** | FastGithub | 全方位加速，支持所有操作 |
| **CLI操作** | gh CLI | 命令行工具，集成认证和操作 |

---

## 二、GitHub代理中转服务

### 2.1 术语说明

**重要概念区分**：

| 类型 | 说明 | 是否存储GitHub内容 | 实时性 |
|------|------|-------------------|--------|
| **代理中转服务** | 请求 → 代理服务器 → GitHub → 返回 | ❌ 不存储，只是转发 | ✅ 实时 |
| **镜像服务** | 完整复制GitHub内容到国内服务器 | ✅ 完整存储 | ⚠️ 有延迟 |

**本文档测试的服务（ghps.cc、kkgithub.com、githubfast.com）都是代理中转服务，不是镜像**。

### 2.2 代理中转服务概述

GitHub代理中转服务是通过在国内部署代理服务器，转发用户请求到GitHub，走优化线路从而加速访问。这些服务主要解决以下问题：

- GitHub原生访问速度慢（通常只有几十KB/s）
- Push操作经常超时失败
- 大文件下载需要等待很长时间
- 频繁的连接中断和重试

### 2.2 可用代理中转服务列表

#### 2.2.1 kkgithub.com

**服务地址**: `https://kkgithub.com`

**使用方式**: 直接替换URL中的github.com为kkgithub.com

**操作示例**:

```bash
# 原始clone命令
git clone https://github.com/username/repository.git

# 替换为kkgithub.com
git clone https://kkgithub.com/username/repository.git
```

**适用场景**:
- 日常仓库浏览和阅读
- 代码clone操作
- 小文件下载
- Web界面访问

**优点**:
- 访问速度快，稳定性好
- 支持Web界面访问
- 操作简单，只需替换域名

**缺点**:
- 不适合push操作
- 服务稳定性可能波动
- 部分私有仓库功能受限

#### 2.2.2 github.hscsec.cn

**服务地址**: `https://github.hscsec.cn`

**使用方式**: 直接替换URL中的github.com为github.hscsec.cn

**操作示例**:

```bash
# 原始clone命令
git clone https://github.com/anomalyco/opencode.git

# 替换为github.hscsec.cn
git clone https://github.hscsec.cn/anomalyco/opencode.git
```

**适用场景**:
- 代码下载和浏览
- Release文件下载
- 大文件获取
- 文档资源访问

**优点**:
- 国内访问速度快
- 安全性较高
- 服务稳定

**缺点**:
- 不支持push操作
- 服务稳定性可能波动
- 不支持私有仓库操作

#### 2.2.3 githubfast.com

**服务地址**: `https://githubfast.com`

**使用方式**: 直接替换URL中的github.com为githubfast.com

**操作示例**:

```bash
# 原始push命令
git push https://github.com/username/repository.git main

# 替换为githubfast.com
git push https://githubfast.com/username/repository.git main

# 使用ssh方式
# 编辑 ~/.ssh/config
Host githubfast.com
    HostName githubfast.com
    User git
    IdentityFile ~/.ssh/id_rsa
```

**适用场景**:
- Push操作（推荐首选）
- 大文件上传
- 需要快速响应的写操作
- CI/CD部署操作

**优点**:
- Push速度快，成功率高
- 专门优化写操作
- 连接稳定
- 支持大文件传输

**缺点**:
- 下载速度一般，不是最优选择
- 需要提前配置认证信息
- 部分高级功能可能受限

#### 2.2.4 ghps.cc

**服务地址**: `https://ghps.cc`

**使用方式**: 直接替换URL中的github.com为ghps.cc

**操作示例**:

```bash
# 原始clone命令
git clone https://github.com/torvalds/linux.git

# 替换为ghps.cc
git clone https://ghps.cc/torvalds/linux.git
```

**适用场景**:
- 代码浏览和学习
- 开源项目贡献
- 技术研究
- 教育和研究用途

**优点**:
- 访问速度稳定
- 支持多个仓库
- 界面友好
- 免费使用

**缺点**:
- Push支持有限
- 大文件传输可能受限
- 服务可用性可能波动

### 2.3 代理中转服务选择策略

根据不同的操作类型，我们推荐以下选择策略：

#### 2.3.1 Download操作推荐

**首选**: `ghps.cc`

**备选**: `kkgithub.com` → `GitHub原生`

**原因**:
- ghps.cc在测试中访问速度最快（0.86秒首页响应）
- kkgithub.com时好时坏，不稳定
- GitHub原生虽然慢（130KB/s）但最稳定

**操作建议**:

```bash
# 第1选择：ghps.cc（推荐）
git clone https://ghps.cc/username/repository.git

# 第2选择：kkgithub.com（不稳定时使用）
git clone https://kkgithub.com/username/repository.git

# 第3选择：GitHub原生（最稳定）
git clone https://github.com/username/repository.git

# 大文件下载示例
curl -L -o file.zip https://ghps.cc/username/repo/releases/download/v1.0.0/file.zip
```

**注意**: `github.hscsec.cn` 在实际测试中完全不可用（超时），不推荐使用。

#### 2.3.2 Push操作推荐

**首选**: `githubfast.com`

**原因**:
- 专门优化push操作
- 传输速度快，连接稳定
- 支持大文件上传
- 失败率低

**操作建议**:

```bash
# 方式一：直接修改remote URL
git remote set-url origin https://githubfast.com/username/repository.git

# 方式二：使用配置文件（推荐）
# 编辑 ~/.gitconfig 或项目 .git/config
[remote "origin"]
    url = https://githubfast.com/username/repository.git
    fetch = +refs/heads/*:refs/remotes/origin/*
```

#### 2.3.3 混合使用策略

在实际使用中，我们经常需要同时进行下载和推送操作。以下是推荐的混合使用策略：

```bash
# 为fetch（下载）设置代理中转（首选ghps.cc）
git config remote.origin.url https://ghps.cc/username/repository.git

# 为push（推送）设置fast服务
git config remote.origin.pushurl https://githubfast.com/username/repository.git

# 或者使用git配置文件
[remote "origin"]
    url = https://ghps.cc/username/repository.git
    pushurl = https://githubfast.com/username/repository.git
```

**简化记忆口诀**:
```
下载找代理（ghps.cc）
推送找fast（githubfast）
懒人用代理
开发开APP
```

---

## 三、FastGithub工具与访问策略

### 3.0 FastGithub与githubfast.com的区别

**重要澄清**：FastGithub（软件）和githubfast.com（网站）是两个独立的东西！

| 名称 | 类型 | 位置/地址 | 作用 |
|------|------|-----------|------|
| **FastGithub** | Windows桌面软件 | `D:\30AI编程工具\fastgithub_win-x64\` | 代理加速GitHub所有操作 |
| **githubfast.com** | 代理中转网站 | `https://githubfast.com` | 替换GitHub域名使用 |

### 3.1 FastGithub概述

FastGithub是一个GitHub加速工具，通过优化网络连接和DNS解析，显著提升GitHub访问速度。与代理中转服务不同，FastGithub提供的是全方位的GitHub访问加速，包括：

- Git clone加速
- Git push加速
- Release文件下载加速
- GitHub Web界面加速
- Raw文件下载加速

### 3.2 FastGithub安装和配置

#### 3.2.1 安装FastGithub

FastGithub的安装目录位于: `D:\30AI编程工具\fastgithub_win-x64\`

**安装步骤**:

```bash
# 1. 进入安装目录
cd D:\30AI编程工具\fastgithub_win-x64

# 2. 以管理员身份运行FastGithub
# Windows右键选择"以管理员身份运行"
# 或者使用PowerShell
Start-Process -FilePath "D:\30AI编程工具\fastgithub_win-x64\fastgithub.exe" -Verb RunAs

# 3. 验证FastGithub是否运行成功
# 检查系统托盘是否有FastGithub图标
# 或者访问 http://localhost:8888 查看配置页面
```

#### 3.2.2 配置Git使用FastGithub

FastGithub运行后，会自动配置系统代理。以下是手动配置方法：

**方法一：设置Git代理**

```bash
# 设置HTTP/HTTPS代理
git config --global http.proxy http://127.0.0.1:8889
git config --global https.proxy http://127.0.0.1:8889

# 仅对GitHub设置代理
git config --global http.https://github.com.proxy http://127.0.0.1:8889

# 取消代理（如果需要）
git config --global --unset http.proxy
git config --global --unset https.proxy
```

**方法二：设置Git SSL验证跳过（可选，用于测试）**

```bash
# 跳过SSL验证（仅限测试环境）
git config --global http.sslVerify false
```

**方法三：使用FastGithub的CA证书（推荐）**

```bash
# 导入FastGithub的CA证书
# 证书位置通常在安装目录下
certutil -addstore -f Root "D:\30AI编程工具\fastgithub_win-x64\ca.cer"

# 这样可以保持SSL验证开启，同时享受FastGithub加速
```

#### 3.2.3 验证FastGithub配置

```bash
# 测试GitHub访问速度
curl -I https://github.com

# 测试通过代理访问
curl -I https://github.com --proxy http://127.0.0.1:8889

# 查看当前Git配置
git config --global --list | grep proxy
```

### 3.3 FastGithub高级配置

#### 3.3.1 绕过FastGithub（特定仓库）

```bash
# 对于不需要加速的仓库，可以单独配置
git config --global http.https://example.com.proxy ""

# 或者在项目级别配置
cd your-project
git config http.proxy ""
```

#### 3.3.2 FastGithub配置页面

FastGithub提供Web配置界面，访问地址: `http://localhost:8888`

**常用配置选项**:

| 配置项 | 说明 | 推荐设置 |
|-------|------|---------|
| Git加速 | 加速git协议访问 | 开启 |
| SSH加速 | 加速ssh协议访问 | 开启 |
| 下载加速 | 加速Release等文件下载 | 开启 |
| GitHub网页加速 | 加速Web界面访问 | 开启 |
| 直连模式 | 绕过代理直接连接 | 按需开启 |

### 3.4 FastGithub故障排除

#### 3.4.1 常见问题

**问题一：FastGithub启动后GitHub访问变慢**

**可能原因**:
- 代理配置错误
- 端口冲突
- 证书问题

**解决方法**:

```bash
# 1. 检查FastGithub是否正常运行
netstat -ano | findstr 8889

# 2. 检查端口占用
tasklist | findstr fastgithub

# 3. 重启FastGithub
# 关闭后重新以管理员身份运行

# 4. 检查Git代理配置
git config --global --list | grep proxy
```

**问题二：Push操作失败**

**可能原因**:
- 代理配置问题
- 认证信息错误
- 网络超时

**解决方法**:

```bash
# 1. 临时关闭代理尝试
git config --global http.proxy ""
git config --global https.proxy ""

# 2. 使用镜像服务
git remote set-url origin https://githubfast.com/username/repository.git

# 3. 检查认证
gh auth status

# 4. 使用SSH方式（如果配置了SSH key）
git remote set-url origin git@github.com:username/repository.git
```

---

## 四、gh CLI使用指南

### 4.1 gh CLI概述

gh CLI是GitHub官方的命令行工具，提供与GitHub交互的便捷方式。通过gh CLI，用户可以直接在终端中执行GitHub操作，如创建仓库、管理Issue、创建Pull Request等。

gh CLI目录: `D:\30AI编程工具\gh_2.63.2_windows_amd64\`

### 4.2 gh CLI安装和认证

#### 4.2.1 使用gh CLI

gh CLI已安装在指定目录，使用全路径调用：

```bash
# 检查gh版本
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" version

# 或者添加到PATH临时使用
$env:PATH += ";D:\30AI编程工具\gh_2.63.2_windows_amd64"
gh version
```

#### 4.2.2 GitHub认证

使用gh CLI前必须完成GitHub认证：

```bash
# 1. 启动认证流程
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" auth login

# 认证方式选择:
# 1. Login with a web browser - 通过浏览器登录（推荐）
# 2. Paste an authentication token - 粘贴认证令牌
# 3. Device Flow - 设备流认证

# 2. 选择认证方式1（浏览器登录）
# 系统会显示一个代码和URL
# 访问显示的URL，登录GitHub
# 输入显示的代码

# 3. 认证成功后验证
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" auth status

# 输出示例:
# ✓ Logged in to github.com as username
# - Token: ********************
# - Scopes: repo, read:org, workflow
```

#### 4.2.3 生成认证令牌

如果选择"粘贴认证令牌"方式，需要先生成令牌：

1. 访问GitHub设置页面: `https://github.com/settings/tokens`
2. 点击"Generate new token (classic)"
3. 设置令牌名称和过期时间
4. 选择权限范围（至少需要repo权限）
5. 生成令牌并复制

**注意**: 令牌只显示一次，请立即保存。

### 4.3 gh CLI常用操作

#### 4.3.1 仓库操作

```bash
# 1. Clone仓库（使用gh命令，带进度显示）
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" repo clone username/repository

# 2. 查看当前仓库信息
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" repo view --web

# 3. 创建新仓库
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" repo create my-new-repo --public --description "My new repository"

# 4. Fork仓库
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" repo fork username/repository

# 5. 同步fork的仓库
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" repo sync username/repository
```

#### 4.3.2 Issue操作

```bash
# 1. 查看Issue列表
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" issue list

# 2. 创建Issue
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" issue create --title "Bug: Application crashes" --body "Description of the bug"

# 3. 查看Issue详情
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" issue view 123

# 4. 关闭Issue
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" issue close 123
```

#### 4.3.3 Pull Request操作

```bash
# 1. 创建Pull Request
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" pr create --title "Add new feature" --body "Description of changes"

# 2. 查看Pull Request列表
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" pr list

# 3. 查看Pull Request详情
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" pr view 456

# 4. 合并Pull Request
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" pr merge 456 --squash --delete-branch
```

#### 4.3.4 Release操作

```bash
# 1. 查看Release列表
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" release list

# 2. 创建Release
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" release create v1.0.0 --title "Version 1.0.0" --notes "Release notes here"

# 3. 下载Release文件
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" release download v1.0.0
```

### 4.4 gh CLI与代理配置

#### 4.4.1 设置gh CLI代理

```bash
# 设置gh使用代理
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" config set http_proxy http://127.0.0.1:8889
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" config set https_proxy http://127.0.0.1:8889

# 清除代理设置
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" config unset http_proxy
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" config unset https_proxy
```

#### 4.4.2 gh CLI网络问题排查

```bash
# 1. 测试网络连接
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" api user

# 2. 查看详细调试信息
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" auth login --verbose

# 3. 检查认证状态
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" auth status --verbose
```

---

## 五、GitHub访问最佳实践

### 5.1 日常开发场景配置

#### 5.1.1 推荐配置方案

以下是一个完整的GitHub访问配置方案，适用于日常开发：

**步骤一：配置FastGithub**

```bash
# 1. 启动FastGithub（以管理员身份）
Start-Process -FilePath "D:\30AI编程工具\fastgithub_win-x64\fastgithub.exe" -Verb RunAs

# 2. 设置Git代理
git config --global http.proxy http://127.0.0.1:8889
git config --global https.proxy http://127.0.0.1:8889

# 3. 导入CA证书（保持SSL验证）
certutil -addstore -f Root "D:\30AI编程工具\fastgithub_win-x64\ca.cer"
```

**步骤二：配置镜像服务备用**

```bash
# 1. 配置fetch使用镜像
git config remote.origin.url https://kkgithub.com/username/repository.git
git config remote.origin.pushurl https://githubfast.com/username/repository.git

# 2. 或者分别设置
git remote set-url origin https://kkgithub.com/username/repository.git
git remote set-url --push origin https://githubfast.com/username/repository.git
```

**步骤三：配置gh CLI**

```bash
# 1. 将gh添加到PATH
$env:PATH += ";D:\30AI编程工具\gh_2.63.2_windows_amd64"

# 2. 完成认证
gh auth login

# 3. 设置gh使用代理（如果需要）
gh config set http_proxy http://127.0.0.1:8889
```

#### 5.1.2 配置文件示例

以下是一个完整的.gitconfig配置文件示例：

```ini
[user]
    name = Your Name
    email = your.email@example.com

[remote "origin"]
    url = https://kkgithub.com/username/repository.git
    pushurl = https://githubfast.com/username/repository.git

[http]
    proxy = http://127.0.0.1:8889
    sslVerify = true

[https]
    proxy = http://127.0.0.1:8889
    sslVerify = true

[credential]
    helper = manager

[core]
    editor = notepad++
    autocrlf = true
```

### 5.2 大文件传输配置

#### 5.2.1 Git LFS配置

对于大文件传输，推荐使用Git LFS：

```bash
# 1. 安装Git LFS
git lfs install

# 2. 追踪大文件类型
git lfs track "*.zip"
git lfs track "*.psd"
git lfs track "*.mp4"

# 3. 查看当前追踪的文件类型
git lfs track

# 4. 使用Git LFS clone仓库
git lfs clone https://githubfast.com/username/large-repo.git
```

#### 5.2.2 镜像服务大文件传输

```bash
# 使用镜像服务传输大文件
git clone https://kkgithub.com/username/large-repo.git

# 或者直接使用浏览器下载Release文件
# 通过 kkgithub.com 或 github.hscsec.cn 下载
# 例如：https://kkgithub.com/username/repo/releases/download/v1.0.0/file.zip
```

### 5.3 网络不稳定环境配置

#### 5.3.1 Git重试配置

```bash
# 设置Git重试次数
git config --global http.lowSpeedLimit 1000
git config --global http.lowSpeedTime 60
git config --global http.maxRetries 5

# 设置超时时间
git config --global http.postBuffer 524288000  # 500MB
```

#### 5.3.2 SSH配置优化

编辑 ~/.ssh/config 文件：

```
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_rsa
    IdentitiesOnly yes
    ServerAliveInterval 60
    ServerAliveCountMax 3
    TCPKeepAlive yes

# 使用FastGithub的SSH加速（如果提供）
Host githubfast.com
    HostName githubfast.com
    User git
    IdentitiesOnly yes
    ServerAliveInterval 60
    ServerAliveCountMax 3
```

### 5.4 CI/CD环境配置

#### 5.4.1 GitHub Actions配置

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup Git
      run: |
        git config --global url."https://kkgithub.com/".insteadOf "https://github.com/"
        git config --global url."https://githubfast.com/".insteadOf "https://github.com/"
    
    - name: Install dependencies
      run: npm install
    
    - name: Build
      run: npm run build
```

#### 5.4.2 Jenkins配置

```bash
# Jenkinsfile中配置Git代理
environment {
    GIT_TERMINAL_PROMPT = 'false'
    http_proxy = 'http://proxy.example.com:8889'
    https_proxy = 'http://proxy.example.com:8889'
}

steps {
    sh '''
        git config --global url."https://kkgithub.com/".insteadOf "https://github.com/"
        git clone https://kkgithub.com/username/repo.git
    '''
}
```

---

## 六、故障排除指南

### 6.1 常见错误及解决方案

#### 6.1.1 连接超时错误

**错误信息**:

```
fatal: unable to access 'https://github.com/username/repository.git/': 
Failed to connect to github.com: Connection timed out
```

**解决方法**:

```bash
# 方法一：检查并重启FastGithub
# 1. 检查FastGithub是否运行
tasklist | findstr fastgithub

# 2. 如果没有运行，重新启动
Start-Process -FilePath "D:\30AI编程工具\fastgithub_win-x64\fastgithub.exe" -Verb RunAs

# 方法二：切换到镜像服务
git remote set-url origin https://kkgithub.com/username/repository.git

# 方法三：检查代理配置
git config --global --list | grep proxy
```

#### 6.1.2 认证错误

**错误信息**:

```
remote: Support for password authentication was removed on August 13, 2021.
fatal: Authentication failed for 'https://github.com/username/repository.git/'
```

**解决方法**:

```bash
# 方法一：使用gh CLI重新认证
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" auth login

# 方法二：使用SSH方式
# 1. 生成SSH key（如果没有）
ssh-keygen -t ed25519 -C "your.email@example.com"

# 2. 添加SSH key到GitHub
# 访问 https://github.com/settings/keys

# 3. 切换到SSH方式
git remote set-url origin git@github.com:username/repository.git

# 方法三：使用Personal Access Token
# 在密码提示时使用PAT代替密码
```

#### 6.1.3 SSL证书错误

**错误信息**:

```
fatal: unable to access 'https://github.com/username/repository.git/': 
SSL certificate problem: unable to get local issuer certificate
```

**解决方法**:

```bash
# 方法一：导入FastGithub的CA证书
certutil -addstore -f Root "D:\30AI编程工具\fastgithub_win-x64\ca.cer"

# 方法二：临时跳过SSL验证（仅限测试）
git config --global http.sslVerify false

# 方法三：更新系统证书
# 控制面板 -> Internet选项 -> 内容 -> 证书
```

#### 6.1.4 权限错误

**错误信息**:

```
remote: Permission to username/repository.git denied to other-user.
fatal: unable to access 'https://github.com/username/repository.git/': 
The requested URL returned error: 403
```

**解决方法**:

```bash
# 方法一：检查当前GitHub用户
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" auth status

# 方法二：如果是私有仓库，确保有访问权限
# 访问 https://github.com/username/repository/settings/access

# 方法三：检查是否使用了错误的认证信息
# 清除旧认证，重新登录
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" auth logout
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" auth login
```

### 6.2 诊断工具和命令

#### 6.2.1 网络诊断

```bash
# 1. 测试DNS解析
nslookup github.com

# 2. 测试网络连通性
ping github.com

# 3. 测试端口连通性
telnet github.com 443

# 4. 查看路由
tracert github.com

# 5. 测试代理连通性
curl -I http://127.0.0.1:8889
```

#### 6.2.2 Git诊断

```bash
# 1. 查看Git配置
git config --list --show-origin

# 2. 测试GitHub连接（带详细输出）
git ls-remote -h https://github.com/username/repository.git HEAD --porcelain

# 3. 启用Git调试模式
GIT_TRACE=1 GIT_CURL_VERBOSE=1 git fetch

# 4. 检查证书配置
git config --get http.sslCAInfo
```

#### 6.2.3 gh CLI诊断

```bash
# 1. 检查gh CLI版本和配置
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" version
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" config list

# 2. 测试API连接
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" api rate_limit

# 3. 启用调试模式
"D:\30AI编程工具\gh_2.63.2_windows_amd64\gh.exe" api user --verbose
```

### 6.3 性能优化建议

#### 6.3.1 Git性能优化

```bash
# 1. 启用Git压缩
git config --global core.compression 9

# 2. 设置缓冲区大小
git config --global http.postBuffer 524288000

# 3. 启用并发下载
git config --global fetch.prune true
git config --global fetch.depth 1

# 4. 优化包文件
git config --global pack.windowMemory 256m
git config --global pack.packSizeLimit 2g
```

#### 6.3.2 网络性能优化

```bash
# 1. 使用HTTP/2（如果支持）
git config --global http.version HTTP/2

# 2. 设置连接复用
git config --global http.followRedirects true

# 3. 优化DNS缓存
# Windows PowerShell中
ipconfig /flushdns

# 4. 测试不同镜像服务速度
# 比较 clone 时间
time git clone https://kkgithub.com/username/repo.git
time git clone https://github.hscsec.cn/username/repo.git
time git clone https://github.com/username/repo.git
```

---

## 七、附录

### 7.1 相关资源链接

| 资源 | 链接 | 说明 |
|-----|------|------|
| GitHub官网 | https://github.com | GitHub官方网站 |
| FastGithub | https://github.com/dotnetcore/FastGithub | FastGithub项目主页 |
| gh CLI文档 | https://cli.github.com | gh CLI官方文档 |
| Git文档 | https://git-scm.com/doc | Git官方文档 |
| kkgithub.com | https://kkgithub.com | GitHub代理中转服务 |
| github.hscsec.cn | https://github.hscsec.cn | GitHub代理中转服务 |
| githubfast.com | https://githubfast.com | GitHub Push加速服务 |
| ghps.cc | https://ghps.cc | GitHub代理中转服务 |

### 7.2 命令速查表

#### 7.2.1 代理中转服务速查

| 操作 | 原始URL | kkgithub.com | github.hscsec.cn | githubfast.com |
|-----|---------|-------------|-----------------|----------------|
| Clone | github.com/xxx | kkgithub.com/xxx | github.hscsec.cn/xxx | githubfast.com/xxx |
| Push | github.com/xxx | 不支持 | 不支持 | githubfast.com/xxx |
| Web访问 | github.com/xxx | kkgithub.com/xxx | github.hscsec.cn/xxx | githubfast.com/xxx |

#### 7.2.2 Git命令速查

| 操作 | 命令 |
|-----|------|
| 设置代理 | git config --global http.proxy http://127.0.0.1:8889 |
| 清除代理 | git config --global --unset http.proxy |
| 查看代理 | git config --global --get http.proxy |
| 设置代理中转 | git remote set-url origin https://ghps.cc/username/repo.git |
| 查看remote | git remote -v |
| 启用LFS | git lfs install |
| 追踪大文件 | git lfs track "*.zip" |

#### 7.2.3 gh命令速查

| 操作 | 命令 |
|-----|------|
| 版本检查 | gh version |
| 认证状态 | gh auth status |
| 登录 | gh auth login |
| 登出 | gh auth logout |
| Clone仓库 | gh repo clone username/repo |
| 创建Issue | gh issue create --title "标题" --body "内容" |
| 查看Issue | gh issue list |
| 创建PR | gh pr create --title "标题" --body "内容" |
| 查看PR | gh pr list |
| 下载Release | gh release download v1.0.0 |

### 7.3 配置文件模板

#### 7.3.1 ~/.gitconfig 模板

```ini
[user]
    name = Your Name
    email = your.email@example.com

[credential]
    helper = manager

[http]
    proxy = http://127.0.0.1:8889
    sslVerify = true
    lowSpeedLimit = 1000
    lowSpeedTime = 60
    maxRetries = 5

[https]
    proxy = http://127.0.0.1:8889
    sslVerify = true

[remote "origin"]
    url = https://kkgithub.com/username/repository.git
    pushurl = https://githubfast.com/username/repository.git

[core]
    compression = 9
    editor = notepad++
    autocrlf = true

[fetch]
    prune = true

[push]
    default = simple

[alias]
    lg = log --oneline --graph --decorate
    co = checkout
    br = branch
    ci = commit
    st = status
```

#### 7.3.2 ~/.ssh/config 模板

```
# GitHub
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_rsa
    IdentitiesOnly yes
    ServerAliveInterval 60
    ServerAliveCountMax 3
    TCPKeepAlive yes

# GitHub Fast（Push加速）
Host githubfast.com
    HostName githubfast.com
    User git
    IdentitiesOnly yes
    ServerAliveInterval 60
    ServerAliveCountMax 3
```

### 7.4 术语表

| 术语 | 说明 |
|-----|------|
| **代理中转服务** | 通过代理服务器转发请求到GitHub，走优化线路加速访问（不存储内容） |
| **镜像服务** | 完整复制GitHub内容到国内服务器（存储内容，可能有延迟） |
| **代理服务器** | 转发网络请求的中间服务器，可加速访问 |
| **CA证书** | 用于验证SSL/TLS连接安全性的证书 |
| **Personal Access Token** | GitHub的API访问认证令牌 |
| **SSH Key** | 用于SSH协议认证的密钥对 |
| **Git LFS** | Git Large File Storage，用于管理大文件 |
| **FastGithub** | GitHub加速工具，优化网络连接 |
| **gh CLI** | GitHub官方命令行工具 |
| **HTTP/HTTPS代理** | 通过代理服务器转发HTTP/HTTPS请求 |

---

### 附录一：代理中转服务实际测试结果汇总

**测试时间**: 2026-02-12 22:00-22:15  
**测试环境**: Windows + Git Bash + 国内网络  
**测试对象**: GitHub Release文件下载（约77MB）

#### 测试结果汇总表

| 服务 | 首页访问 | Release下载 | 实际下载体验 | 推荐等级 | 适用场景 |
|------|---------|-------------|-------------|---------|---------|
| **ghps.cc** | ✅ 302跳转<br>响应：0.86秒 | ✅ 302跳转 | 未完成完整下载测试 | ⭐⭐⭐⭐⭐ | **Download首选** |
| **GitHub原生** | ✅ 200 OK<br>响应：~1秒 | ✅ 200 OK | 130KB/s<br>77MB约10分钟 | ⭐⭐⭐⭐ | **稳定备用** |
| **kkgithub.com** | ✅ 301跳转<br>响应：10秒 | ✅ 302跳转 | ❌ 超时失败 | ⭐⭐ | **不稳定，慎用** |
| **githubfast.com** | ✅ 200 OK<br>响应：~1秒 | ✅ 302跳转 | ❌ 35秒超时 | ⭐⭐⭐ | **仅适合Push** |
| **github.hscsec.cn** | ❌ 超时<br>响应：23秒 | ❌ 超时 | ❌ 完全不通 | ⭐ | **不能用** |

#### 详细测试记录

**1. ghps.cc**
- 首页响应时间：0.86秒
- Release文件访问：正常跳转
- 优点：响应速度快
- 缺点：未完成完整下载测试
- **结论**：目前表现最佳，推荐作为Download首选

**2. GitHub原生**
- 首页响应时间：~1秒
- Release文件访问：正常
- 下载速度：130KB/s
- 优点：最稳定，不会出错
- 缺点：速度慢
- **结论**：作为备用方案最可靠

**3. kkgithub.com**
- 首页响应时间：10秒
- Release文件访问：正常跳转
- 实际下载：超时失败
- 优点：偶发性可用
- 缺点：不稳定，容易超时
- **结论**：时好时坏，不推荐作为主要方案

**4. githubfast.com**
- 首页响应时间：~1秒
- Release文件访问：正常跳转
- 实际下载：35秒超时
- 优点：首页访问快
- 缺点：下载速度不佳
- **结论**：适合Push操作，Download表现一般

**5. github.hscsec.cn**
- 首页响应时间：23秒后超时
- Release文件访问：超时
- 实际下载：无法测试
- 优点：无
- 缺点：完全无法访问
- **结论**：当前不可用，避开使用

#### 推荐使用策略

| 操作类型 | 第1选择 | 第2选择 | 第3选择 | 不推荐 |
|---------|---------|---------|---------|-------|
| **Download下载** | ghps.cc | GitHub原生 | kkgithub.com | github.hscsec.cn |
| **Push推送** | githubfast.com | GitHub原生 | FastGithub APP | github.hscsec.cn |
| **频繁开发** | FastGithub APP | githubfast.com | ghps.cc | github.hscsec.cn |

#### 快速选择口诀

```
下载用：ghps.cc > 原生 > kkgithub
推送用：githubfast > 原生
开发开：FastGithub APP
避开用：github.hscsec.cn
```

---

### 附录二：FastGithub与githubfast.com区别

| 对比项 | FastGithub | githubfast.com |
|--------|-----------|----------------|
| **类型** | Windows桌面应用程序 | 代理中转网站 |
| **位置** | D:\30AI编程工具\fastgithub_win-x64\ | https://githubfast.com |
| **使用方式** | 需要安装启动运行 | 直接浏览器访问或替换URL |
| **作用** | 代理加速所有GitHub操作 | 域名替换加速访问 |
| **优点** | 全方位加速，可靠性高 | 轻量级，无需安装 |
| **缺点** | 需要安装和启动 | 服务质量不稳定 |
| **适用场景** | 高频开发操作 | 偶尔使用 |

**关系澄清**：二者是独立的产品，解决的都是GitHub访问加速问题，但实现方式不同。根据实际情况选择使用。

---

### 附录三：FastGithub下载地址

#### 官方下载地址

| 来源 | 地址 | 说明 |
|------|------|------|
| **GitHub官方** | https://github.com/dotnetcore/FastGithub/releases | 项目作者发布的正式版本 |
| **Softonic下载站** | https://fastgithub.en.softonic.com/ | 第三方下载站，提供Windows版 |
| **本地位置** | `D:\30AI编程工具\fastgithub_win-x64\` | 已安装版本 |

#### GitHub官方版本下载命令

```bash
# 访问GitHub Releases页面
# 找到最新的 Windows 版本（.exe 或 .zip）

# 使用gh CLI下载（如果已安装）
gh release download -R dotnetcore/FastGithub -p "*win-x64*"

# 或者直接浏览器访问
# https://github.com/dotnetcore/FastGithub/releases
```

#### 安装步骤

1. **下载**：从上述地址下载Windows版本
2. **解压**：解压到 `D:\30AI编程工具\fastgithub_win-x64\`
3. **运行**：右键 `fastgithub.exe` → "以管理员身份运行"
4. **验证**：检查系统托盘是否有图标，或访问 http://localhost:8888

#### 版本信息

- **当前版本**: v2.1.4（2025年12月更新）
- **软件大小**: 约22MB
- **系统要求**: Windows 10/11
- **开发者**: dotnetcore

---

**文档更新时间**: 2026-02-12 22:25:00
**版本**: v1.2
**更新说明**: 添加FastGithub下载地址

---

## 参考文档

| 文档名称 | 文件路径 |
|---------|---------|
| 会话记录 | D:\2bktest\MDview\会话记录-2026-02-12.md |
| GitHub避坑操作指南 | D:\2bktest\MDview\GitHub避坑操作指南.md |
| Git使用规范 | D:\50RuleTool\规范与规则\git使用规范.md |
| 软件迭代代码备份规则 | D:\50RuleTool\规范与规则\软件迭代代码备份规则.md |
| AI助手安装程序铁规 | D:\50RuleTool\规范与规则\AI助手安装程序铁规.md |
| 笔记及日志写入规则 | D:\50RuleTool\规范与规则\笔记及日志写入规则.md |

---

## v1.3 版本更新说明（2026-02-12 22:35:00）

**术语修正**：
- ghps.cc、kkgithub.com、githubfast.com 是**代理中转服务**，不是"镜像"
- 代理中转：不存储GitHub内容，实时从GitHub获取
- 镜像：完整存储GitHub内容，可能有延迟

**代理中转服务与镜像的区别**：
| | 代理中转 | 镜像 |
|---|---|---|
| **是否存储内容** | ❌ 不存储 | ✅ 完整存储 |
| **实时性** | ✅ 实时 | ⚠️ 有延迟 |
| **技术原理** | 反向代理转发 | 完整同步副本 |

