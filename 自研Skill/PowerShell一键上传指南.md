# 🚀 PowerShell 一键上传指南

## ⚡ 最简单的方法

### 方法1：双击运行（推荐）

1. **打开文件管理器**
2. **进入目录**: `D:\2bktest\MDview\upload_ready\`
3. **双击**: `一键上传到GitHub.bat`
4. **等待完成**

就是这么简单！

---

### 方法2：PowerShell 命令行

```powershell
# 进入目录
cd D:\2bktest\MDview\upload_ready

# 执行脚本
.\upload_to_github.ps1
```

**如果提示权限错误，先执行**:
```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
.\upload_to_github.ps1
```

---

## ✅ 脚本已配置好的内容

您的账号信息已写入脚本：
- **用户名**: joshuachendyb
- **邮箱/账号**: chendyg@qq.com
- **密码**: HMys0481

**脚本会自动使用这些信息登录GitHub，不需要手动输入！**

---

## 📂 上传前的检查清单

确认这些文件存在：
- [x] `doc2md-skill\doc2md_converter.py`
- [x] `doc2md-skill\README.md`
- [x] `doc2md-skill\SKILL.md`
- [x] `doc2md-skill\requirements.txt`
- [x] `doc2md-skill\.gitignore`
- [x] `upload_to_github.ps1`
- [x] `一键上传到GitHub.bat`

---

## 🎯 执行后会发生什么

1. **自动克隆** 您的 jizx 仓库
2. **自动创建** doc2md-skill 目录
3. **自动复制** 所有代码文件
4. **自动提交** 到git
5. **自动推送** 到GitHub
6. **显示结果** 和GitHub链接

**全程不需要手动输入！**

---

## 🔍 上传成功后的验证

脚本会提示：
```
========================================
  上传成功！
========================================

访问地址: https://github.com/joshuachendyb/jizx

文件已上传到 doc2md-skill/ 目录下
```

然后脚本会询问是否打开浏览器查看，输入 `Y` 即可。

---

## ⚠️ 可能的问题

### 1. 脚本无法执行（红色错误）

**解决**: 右键点击PowerShell，选择"以管理员身份运行"，然后执行：
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 2. 提示git未安装

**解决**: 下载安装 Git
- 地址：https://git-scm.com/download/win
- 安装时一路Next即可

### 3. 推送失败

**可能原因**:
- 网络问题（重试几次）
- 密码错误或账号需要2FA验证

**解决**: 如果自动推送失败，脚本会提示手动操作步骤。

---

## 📱 上传后的GitHub链接

**仓库地址**: https://github.com/joshuachendyb/jizx

**上传后访问**: https://github.com/joshuachendyb/jizx/tree/main/doc2md-skill

---

## 💡 小贴士

- **bat文件** 只是用来调用PowerShell脚本的
- **ps1文件** 是真正执行上传的脚本
- 两个文件在同一目录下，不要分开
- 密码已加密在脚本中，不会被明文显示

---

## 🎉 开始上传！

**现在就可以双击运行** `一键上传到GitHub.bat` 了！

如果一切顺利，大约30秒内就能完成上传。

---

**有问题随时问我！** ✨
