# Python 3.13 安装过程总结

**创建时间**: 2026-02-05 11:59:22

## 一、安装背景

| 项目 | 值 |
|-----|-----|
| 原版本 | Python 3.11.9 |
| 目标版本 | Python 3.13.11 |
| 安装原因 | memU框架要求Python 3.13+ |

## 二、遇到的问题

### 2.1 命令行安装器无法静默运行

| 尝试的命令 | 结果 | 问题原因 |
|-------|------|---------|
| `python313.exe /quiet ...` | ❌ 路径找不到 | Bash路径格式问题 |
| `D:\python313.exe /quiet ...` | ❌ 路径解析失败 | Windows路径在Git Bash中无法直接识别 |
| GUI模式安装 | ❌ 超时 | 需要用户交互 |

### 2.2 PATH更新权限问题

- 需要管理员权限修改系统PATH
- `reg add` 和 `setx` 命令都因权限或语法问题失败

## 三、解决方案：嵌入式版本

**最终方案**：使用Python嵌入式版本（Embeddable）

### 3.1 下载嵌入式版本



### 3.2 解压到指定目录



### 3.3 验证安装



## 三、解决方案：嵌入式版本

**最终方案**：使用Python嵌入式版本（Embeddable）

### 3.1 下载嵌入式版本

```bash
curl -L -o /d/python313-embed.zip \
  "https://www.python.org/ftp/python/3.13.11/python-3.13.11-embed-amd64.zip"
# 文件大小：~10.4MB
```

### 3.2 解压到指定目录

```bash
python -c "import zipfile; zipfile.ZipFile('D:/python313-embed.zip').extractall('C:/Python313')"
```

### 3.3 验证安装

```bash
C:/Python313/python --version
# 输出：Python 3.13.11
```

## 四、安装结果

| 项目 | 值 |
|-----|-----|
| **安装路径** | `C:\Python313\python.exe` |
| **版本** | `3.13.11` |
| **安装方式** | 解压即用（嵌入式） |
| **是否需要管理员权限** | 否 |
| **是否已加入PATH** | 否（需手动） |

## 五、当前使用方法

**完整路径调用**：
```bash
C:/Python313/python your_script.py
```

**临时添加PATH**（当前会话有效）：
```bash
export PATH="/c/Python313:/c/Python313/Scripts:$PATH"
python --version  # 3.13.11
```

**永久添加PATH**（需管理员CMD）：
```cmd
setx PATH "C:\Python313;C:\Python313\Scripts;%PATH%"
```

---

**更新时间**: 2026-02-05 11:59:22
