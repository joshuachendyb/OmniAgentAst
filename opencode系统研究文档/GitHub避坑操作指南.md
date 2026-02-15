# GitHub避坑操作指南

**创建时间**: 2026-02-12 17:30:00
**更新时间**: 2026-02-12 21:21:05
**版本**: v1.1

**说明**: v1.1新增Push和Download备用方案，补充国内镜像加速服务。

---

## 一、GitHub连接问题

### 1.1 问题现象
```
fatal: unable to access 'https://github.com/.../': OpenSSL SSL_connect: Connection reset by peer in connection to github.com:443
```

### 1.2 原因
网络连接到GitHub的443端口被封锁或不稳定。

### 1.3 解决方案

#### 方案1：安装FastGithub（推荐）
```bash
# 下载地址：https://github.com/WangGithubUser/FastGitHub/releases
# 下载 fastgithub_win-x64.zip

# 解压到：D:\30AI编程工具\fastgithub_win-x64\
# 双击运行：fastgithub.exe
```

#### 方案2：使用代理
```bash
# 设置代理
git config --global http.proxy http://127.0.0.1:端口
git config --global https.proxy http://127.0.0.1:端口
```

---

## 二、敏感信息阻止Push

### 2.1 问题现象
```
remote: Protect push - Sensitive data detected
remote: This push has been blocked because it contains sensitive API tokens.
remote: Contact GitHub Support to unblock.
```

### 2.2 原因
GitHub检测到历史commit中有敏感信息（API密钥、Token等）。

### 2.3 解决方案

#### 步骤1：识别敏感文件
```bash
# 常见敏感文件
tests/legacy/           # 包含历史敏感信息
项目敏感信息.txt        # 提取的敏感信息
```

#### 步骤2：从Git历史中删除
```bash
cd 项目目录

# 删除敏感文件夹
git filter-branch --force --index-filter \
  'git rm -r --cached --ignore-unmatch tests/legacy/' \
  --tag-name-filter cat -- --all

# 删除敏感文件
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch "项目敏感信息.txt"' \
  --tag-name-filter cat -- --all
```

#### 步骤3：清理垃圾
```bash
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

#### 步骤4：强制Push
```bash
git push --force origin main
```

---

## 三、分支管理问题

### 3.1 问题现象
GitHub上有两个默认分支（main和master），或者force push后旧分支还在。

### 3.2 解决方案

#### 在GitHub网站操作：
1. 打开：https://github.com/用户名/仓库/settings/branches
2. 在 **Default branch** 下拉菜单中选择 **main**
3. 点击 **Update**
4. 找到 **master** 分支，点击 **Delete branch**

---

## 四、gh CLI安装和使用

### 4.1 下载和安装
```bash
# 下载地址：https://github.com/cli/cli/releases
# 下载 gh_X.X.X_windows_amd64.zip

# 解压到：D:\30AI编程工具\gh_2.63.2_windows_amd64\
```

### 4.2 添加到环境变量
```bash
# 方法1：使用env_manager.py
python D:\50RuleTool\工具\env_manager.py --add-path "D:\30AI编程工具\gh_2.63.2_windows_amd64\bin"

# 方法2：手动添加到Path环境变量
# D:\30AI编程工具\gh_2.63.2_windows_amd64\bin
```

### 4.3 GitHub认证
```bash
# 执行认证命令
gh auth login --hostname github.com

# 根据提示在浏览器打开 https://github.com/login/device
# 输入验证码完成授权
```

### 4.4 在Git Bash中使用gh
```bash
# Git Bash中可能需要用PowerShell调用gh
"C:\Windows\System32\WindowsPowerShell\v1.0\PowerShell.exe" -Command "gh --version"
```

---

## 五、Release操作

### 5.1 创建Release

#### 方法1：使用gh CLI
```bash
gh release create v2.0.0 \
  --title "项目名 v2.0.0" \
  --notes "Release说明内容" \
  --repo 用户名/仓库名
```

#### 方法2：从文件读取Release说明
```bash
gh release create v2.0.0 \
  --title "项目名 v2.0.0" \
  --notes-file RELEASE_NOTES.md \
  --repo 用户名/仓库名
```

### 5.2 Release Notes格式问题

#### 错误做法
```bash
# 使用\n换行 - 不会生效
gh release create v1.4.0 --notes "第一行\n第二行"
```

#### 正确做法
```bash
# 使用文件方式传递多行内容
gh release create v1.4.0 \
  --notes-file RELEASE_NOTES_v1.4.0.md \
  --repo 用户名/仓库名

# 或者在GitHub网页上直接编辑Release说明
```

### 5.3 Release Notes示例
```markdown
## v2.0.0 - 项目重大更新版本

### 新增功能
- 功能1描述
- 功能2描述

### 技术改进
- 改进1描述
- 改进2描述

### 已知问题
- 问题1（解决方案）
```

---

## 六、版本Tag管理

### 6.1 创建版本Tag
```bash
# 创建带注释的Tag
git tag -a v1.0.0 -m "v1.0.0 - 版本说明"

# 批量创建序列Tag
for i in {0..9}; do
  git tag -a v1.5.$i -m "v1.5.$i - 版本说明"
done
```

### 6.2 推送Tag到GitHub
```bash
# 推送所有Tag
git push origin --tags

# 推送单个Tag
git push origin v1.0.0
```

### 6.3 删除本地Tag
```bash
# 删除单个Tag
git tag -d v1.0.0

# 删除所有本地Tag
git tag -l | xargs -r git tag -d
```

---

## 七、常见错误和解决方案

### 7.1 force push失败
```bash
# 错误
! [rejected]        main -> main (non-fast-forward)

# 解决方案
git push --force origin main
```

### 7.2 Tag已存在
```bash
# 错误
fatal: tag 'v1.0.0' already exists

# 解决方案
# 1. 删除已存在的Tag
git tag -d v1.0.0
# 2. 重新创建
git tag -a v1.0.0 -m "v1.0.0 - 新说明"
# 3. 强制推送
git push --force origin refs/tags/v1.0.0:refs/tags/v1.0.0
```

### 7.3 认证失败
```bash
# 错误
remote: Authentication failed.

# 解决方案
gh auth login --hostname github.com
```

---

## 八、环境变量设置问题

### 8.1 问题
使用Python脚本设置环境变量后，在Git Bash中不生效。

### 8.2 解决方案
```bash
# 1. 设置后需要关闭当前终端，重新打开新终端
# 2. 或者使用命令全路径执行

# Git Bash中执行gh
"D:/30AI编程工具/gh_2.63.2_windows_amd64/bin/gh.exe" --version

# Git Bash中调用PowerShell
"C:\Windows\System32\WindowsPowerShell\v1.0\PowerShell.exe" -Command "gh --version"
```

---

## 九、执行流程总结

### 9.1 日常Push流程
```bash
# 1. 添加文件
git add .

# 2. 提交
git commit -m "feat: 新功能描述"

# 3. 推送
git push origin main
```

### 9.2 遇到连接问题时
```bash
# 1. 确保FastGithub已运行
# 2. 重新Push
git push origin main
```

### 9.3 遇到敏感信息问题时
```bash
# 1. 识别敏感文件
# 2. 从历史中删除
# 3. 强制Push
git push --force origin main
```

### 9.4 创建Release流程
```bash
# 1. 准备Release说明文件
# 2. 创建Release
"C:\Windows\System32\WindowsPowerShell\v1.0\PowerShell.exe" -Command "gh release create v2.0.0 --title '项目名 v2.0.0' --notes-file RELEASE_NOTES.md --repo 用户名/仓库名"
```

---

## 十、工具和资源

### 10.1 必需工具
| 工具 | 下载地址 | 用途 |
|------|---------|------|
| FastGithub | GitHub Releases | GitHub加速 |
| gh CLI | GitHub Releases | GitHub命令行操作 |

### 10.2 工具存放位置
| 工具 | 存放目录 |
|------|---------|
| FastGithub | D:\30AI编程工具\fastgithub_win-x64\ |
| gh CLI | D:\30AI编程工具\gh_2.63.2_windows_amd64\ |

### 10.3 脚本存放位置
| 脚本 | 路径 |
|------|------|
| 环境变量管理 | D:\50RuleTool\工具\env_manager.py |
| GitHub操作 | D:\50RuleTool\工具\ |

---

## 十一、检查清单

### 11.1 Push前检查
- [ ] 代码已提交（git status 干净）
- [ ] 敏感信息已清理（如果有）
- [ ] FastGithub已运行（如果需要）
- [ ] 了解本次Push的影响范围

### 11.2 创建Release前检查
- [ ] Release说明文件已准备
- [ ] 版本号已创建对应的Tag
- [ ] 已决定是否上传二进制文件

### 11.3 解决问题后检查
- [ ] 问题已解决（重新执行命令验证）
- [ ] 没有引入新问题
- [ ] 文档已更新

---

**更新时间**: 2026-02-12 17:35:00
**版本**: v1.0
