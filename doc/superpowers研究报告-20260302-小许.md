# superpowers 研究报告

**创建时间**: 2026-03-02 23:33:18  
**分析人**: 小许（专家级需求分析师）  
**用户**: 北京老陈  
**来源**: https://github.com/obra/superpowers

---

## 一、项目概述

### 1.1 项目定位

**superpowers** 是一个为 **OpenCode** 提供增强功能的插件系统，包含大量预构建的技能（skills）。

**核心理念**：为 OpenCode 提供类似于 Claude Code 的技能系统，让 AI 助手能够使用各种专业工具和功能。

**项目统计**：
- ⭐ **Stars**: 67.9k
- 🔀 **Forks**: 5.2k
- 📜 **Issues**: 108
- 🔀 **Pull requests**: 87
- 💻 **Languages**: 主要是 JavaScript/TypeScript

---

## 二、主要功能

### 2.1 自动上下文注入

**功能描述**：通过 `experimental.chat.system.transform` 钩子自动注入 superpowers 上下文。

**注入内容物**：
- 每次请求都会添加 "using-superpowers" 技能内容到系统提示
- 自动适配 Claude Code 的技能到 OpenCode

### 2.2 原生技能集成

**功能描述**：使用 OpenCode 原生的 `skill` 工具进行技能发现和加载。

**集成方式**：
- 技能通过符号链接到 `~/.config/opencode/skills/superpowers/`
- 使用 OpenCode 原生技能系统
- 每个技能有 `SKILL.md` 文件（带 YAML frontmatter）

### 2.3 工具映射

**功能描述**：自动将 Claude Code 的工具映射到 OpenCode 工具。

**映射表**：

| Claude Code 工具 | OpenCode 工具 |
|----------------|---------------|
| `TodoWrite` | `update_plan` |
| `Task`（带子代理） | OpenCode 的 `@mention` 系统 |
| `Skill` 工具 | OpenCode 原生 `skill` 工具 |
| 文件操作 | 原生 OpenCode 工具 |

---

## 三、技能系统

### 3.1 技能发现

**功能描述**：使用 OpenCode 原生的 `skill` 工具列出所有可用技能。

**命令**：
```
use skill tool to list skills
```

### 3.2 技能加载

**功能描述**：加载特定的技能到当前会话。

**命令**：
```
use skill tool to load superpowers/brainstorming
```

### 3.3 技能位置

**技能发现优先级**（从高到低）：

1. **项目技能**（`.opencode/skills/`）- 最高优先级
2. **个人技能**（`~/.config/opencode/skills/`）
3. **Superpowers 技能**（`~/.config/opencode/skills/superpowers/`）- 通过符号链接

### 3.4 自定义技能

#### 3.4.1 个人技能

**创建位置**：`~/.config/opencode/skills/`

**创建步骤**：
```bash
mkdir -p ~/.config/opencode/skills/my-skill
```

创建 `~/.config/opencode/skills/my-skill/SKILL.md`：
```markdown
---
name: my-skill
description: Use when [condition] - [what it does]
---

# My Skill

[Your skill content here]
```

#### 3.4.2 项目技能

**创建位置**：项目根目录下的 `.opencode/skills/`

**创建步骤**：
```bash
# 在你的 OpenCode 项目中
mkdir -p .opencode/skills/my-project-skill
```

创建 `.opencode/skills/my-project-skill/SKILL.md`：
```markdown
---
name: my-project-skill
description: Use when [condition] - [what it does]
---

# My Project Skill

[Your skill content here]
```

---

## 四、安装方法

### 4.1 快速安装

**方法**：让 OpenCode 自动安装

**提示词**：
```
Clone https://github.com/obra/superpowers to ~/.config/opencode/superpowers, 
then create directory ~/.config/opencode/plugins, 
then symlink ~/.config/opencode/superpowers/.opencode/plugins/superpowers.js 
to ~/.config/opencode/plugins/superpowers.js, 
then symlink ~/.config/opencode/superpowers/skills 
to ~/.config/opencode/skills/superpowers, 
then restart opencode.
```

### 4.2 手动安装

#### 4.2.1 前置条件

- [OpenCode.ai](https://opencode.ai) 已安装
- Git 已安装

#### 4.2.2 macOS / Linux 安装

**步骤1：安装或更新 Superpowers**
```bash
if [ -d ~/.config/opencode/superpowers ]; then
  cd ~/.config/opencode/superpowers && git pull
else
  git clone https://github.com/obra/superpowers.git ~/.config/opencode/superpowers
fi
```

**步骤2：创建目录**
```bash
mkdir -p ~/.config/opencode/plugins ~/.config/opencode/skills
```

**步骤3：移除旧的符号链接/目录（如果存在）**
```bash
rm -f ~/.config/opencode/plugins/superpowers.js
rm -rf ~/.config/opencode/skills/superpowers
```

**步骤4：创建符号链接**
```bash
ln -s ~/.config/opencode/superpowers/.opencode/plugins/superpowers.js ~/.config/opencode/plugins/superpowers.js
ln -s ~/.config/opencode/superpowers/skills ~/.config/opencode/skills/superpowers
```

**步骤5：重启 OpenCode**

**验证安装**：
```bash
ls -l ~/.config/opencode/plugins/superpowers.js
ls -l ~/.config/opencode/skills/superpowers
```

两者应该显示指向 superpowers 目录的符号链接。

#### 4.2.3 Windows 安装

**前置条件**：
- Git 已安装
- **开发者模式**已启用 **或** **管理员权限**
  - Windows 10：设置 → 更新和安全 → 针对开发者
  - Windows 11：设置 → 系统 → 针对开发者

**选项1：命令提示符**

以管理员身份运行，或启用开发者模式：

```cmd
:: 1. 安装 Superpowers
git clone https://github.com/obra/superpowers.git "%USERPROFILE%\.config\opencode\superpowers"

:: 2. 创建目录
mkdir "%USERPROFILE%\.config\opencode\plugins" 2>nul
mkdir "%USERPROFILE%\.config\opencode\skills" 2>nul

:: 3. 移除现有链接（重安装时安全）
del "%USERPROFILE%\.config\opencode\plugins\superpowers.js" 2>nul
rmdir "%USERPROFILE%\.config\opencode\skills\superpowers" 2>nul

:: 4. 创建插件符号链接（需要开发者模式或管理员权限）
mklink "%USERPROFILE%\.config\opencode\plugins\superpowers.js" "%USERPROFILE%\.config\opencode\superpowers\.opencode\plugins\superpowers.js"

:: 5. 创建技能目录连接（无需特殊权限）
mklink /J "%USERPROFILE%\.config\opencode\skills\superpowers" "%USERPROFILE%\.config\opencode\superpowers\skills"

:: 6. 重启 OpenCode
```

**选项2：PowerShell**

以管理员身份运行，或启用开发者模式：

```powershell
# 1. 安装 Superpowers
git clone https://github.com/obra/superpowers.git "$env:USERPROFILE\.config\opencode\superpowers"

# 2. 创建目录
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.config\opencode\plugins"
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.config\opencode\skills"

# 3. 移除现有链接（重安装时安全）
Remove-Item "$env:USERPROFILE\.config\opencode\plugins\superpowers.js" -Force -ErrorAction SilentlyContinue
Remove-Item "$env:USERPROFILE\.config\opencode\skills\superpowers" -Force -ErrorAction SilentlyContinue

# 4. 创建插件符号链接（需要开发者模式或管理员权限）
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.config\opencode\plugins\superpowers.js" -Target "$env:USERPROFILE\.config\opencode\superpowers\.opencode\plugins\superpowers.js"

# 5. 创建技能目录连接（无需特殊权限）
New-Item -ItemType Junction -Path "$env:USERPROFILE\.config\opencode\skills\superpowers" -Target "$env:USERPROFILE\.config\opencode\superpowers\skills"

# 6. 重启 OpenCode
```

**选项3：Git Bash**

**注意**：Git Bash 的原生命令 `ln` 会复制文件而不是创建符号链接。应该使用 `cmd //c mklink` 代替（`//c` 是 Git Bash 中调用 `/c` 的语法）。

```bash
# 1. 安装 Superpowers
git clone https://github.com/obra/superpowers.git ~/.config/opencode/superpowers

# 2. 创建目录
mkdir -p ~/.config/opencode/plugins ~/.config/opencode/skills

# 3. 移除现有链接（重安装时安全）
rm -f ~/.config/opencode/plugins/superpowers.js 2>/dev/null
rm -rf ~/.config/opencode/skills/superpowers 2>/dev/null

# 4. 创建插件符号链接（需要开发者模式或管理员权限）
cmd //c "mklink \"$(cygpath -w ~/.config/opencode/plugins/superpowers.js)\" \"$(cygpath -w ~/.config/opencode/superpowers/.opencode/plugins/superpowers.js)\""

# 5. 创建技能目录连接（无需特殊权限）
cmd //c "mklink /J \"$(cygpath -w ~/.config/opencode/skills/superpowers)\" \"$(cygpath -w ~/.config/opencode/superpowers\skills)\""

# 6. 重启 OpenCode
```

#### 4.2.4 WSL 用户

如果在 WSL 中运行 OpenCode，使用 [macOS / Linux](#42-macos--linux-安装) 说明。

#### 4.2.5 验证安装（Windows）

**命令提示符**：
```cmd
dir /AL "%USERPROFILE%\.config\opencode\plugins"
dir /AL "%USERPROFILE%\.config\opencode\skills"
```

**PowerShell**：
```powershell
Get-ChildItem "$env:USERPROFILE\.config\opencode\plugins" | Where-Object { $_.LinkType }
Get-ChildItem "$env:USERPROFILE\.config\opencode\skills" | Where-Object { $_.LinkType }
```

寻找输出中的 `<SYMLINK>` 或 `<JUNCTION>`。

---

## 五、架构说明

### 5.1 插件结构

**位置**：`~/.config/opencode/superpowers/.opencode/plugins/superpowers.js`

**组件**：
- `experimental.chat.system.transform` 钩子用于引导程序注入
- 读取并注入 "using-superpowers" 技能内容

### 5.2 技能结构

**位置**：`~/.config/opencode/skills/superpowers/`（指向 `~/.config/opencode/superpowers/skills/` 的符号链接）

**技能发现**：由 OpenCode 原生技能系统发现。每个技能都有一个带 YAML frontmatter 的 `SKILL.md` 文件。

---

## 六、更新方法

### 6.1 更新到最新版本

```bash
cd ~/.config/opencode/superpowers
git pull
```

重启 OpenCode 加载更新。

---

## 七、故障排除

### 7.1 插件未加载

1. 检查插件是否存在：`ls ~/.config/opencode/superpowers/.opencode/plugins/superpowers.js`
2. 检查符号链接/连接：`ls -l ~/.config/opencode/plugins/`（macOS/Linux）或 `dir /AL %USERPROFILE%\.config\opencode\plugins`（Windows）
3. 检查 OpenCode 日志：`opencode run "test" --print-logs --log-level DEBUG`
4. 在日志中寻找插件加载消息

### 7.2 技能未找到

1. 验证技能符号链接：`ls -l ~/.config/opencode/skills/superpowers`（应该指向 superpowers/skills/）
2. 使用 OpenCode 原生 `skill` 工具列出可用技能
3. 检查技能结构：每个技能需要一个带有效 frontmatter 的 `SKILL.md` 文件

### 7.3 Windows：找不到模块错误

如果在 Windows 上看到"找不到模块"错误：

**原因**：Git Bash 的 `ln -sf` 会复制文件而不是创建符号链接。

**修复**：使用 `mklink /J` 目录连接代替（参见 Windows 安装步骤）。

### 7.4 引导程序未出现

1. 验证 using-superpowers 技能是否存在：`ls ~/.config/opencode/superpowers/skills/using-superpowers/SKILL.md`
2. 检查 OpenCode 版本是否支持 `experimental.chat.system.transform` 钩子
3. 插件更改后重启 OpenCode

### 7.5 Windows 权限错误

**错误**："您没有足够的权限"

**解决方案**：
- 启用开发人员模式（适用于开发者）
- 以管理员身份运行终端（适用于管理员）

---

## 八、获取帮助

- 报告问题：https://github.com/obra/superpowers/issues
- 主文档：https://github.com/obra/superpowers
- OpenCode 文档：https://opencode.ai/docs/

---

## 九、测试

验证你的安装：

```bash
# 检查插件加载
opencode run --print-logs "hello" 2>&1 | grep -i superpowers

# 检查技能可被发现
opencode run "use skill tool to list all skills" 2>&1 | grep -i superpowers

# 检查引导程序注入
opencode run "what superpowers do you have?"
```

代理应该提到具有 superpowers 并且能够从 `superpowers/` 列出技能。

---

## 十、总结与建议

### 10.1 核心价值

1. **丰富的技能库**：提供了大量预构建的专业技能
2. **自动工具映射**：自动将 Claude Code 工具映射到 OpenCode
3. **原生技能集成**：使用 OpenCode 原生技能系统
4. **自定义技能支持**：支持个人技能和项目技能
5. **优先级管理**：项目技能 > 个人技能 > Superpowers 技能

### 10.2 适用场景

- ✅ 需要使用专业开发工具
- ✅ 需要自动化的任务流程
- ✅ 需要项目特定的技能
- ✅ 从 Claude Code 迁移到 OpenCode

### 10.3 安装建议

1. **检查前置条件**：确保已安装 Git 和 OpenCode
2. **Windows 特殊注意**：需要开发者模式或管理员权限
3. **符号链接问题**：Windows 下 Git Bash 会复制文件，使用 `mklink /J`
4. **验证安装**：安装后检查符号链接是否正确创建
5. **重启 OpenCode**：安装后必须重启才能生效

### 10.4 推荐的 shell 选择（Windows）

| Shell | 推荐度 | 说明 |
|------|--------|------|
| PowerShell | ⭐⭐⭐⭐⭐ | 原生支持，推荐使用 |
| 命令提示符 | ⭐⭐⭐⭐ | 原生支持，推荐使用 |
| Git Bash | ⭐ | 不推荐，`ln` 会复制文件而非创建符号链接 |
| WSL Bash | ⭐⭐⭐⭐ | 推荐，使用 Linux 安装步骤 |

---

**报告完成时间**: 2026-03-02 23:33:18  
**分析人**: 小许（专家级需求分析师）  
**用户**: 北京老陈  
**建议**: 
1. Windows 用户推荐使用 PowerShell 或命令提示符进行安装
2. 安装后验证符号链接是否正确创建
3. 重启 OpenCode 后验证插件和技能是否正常加载
