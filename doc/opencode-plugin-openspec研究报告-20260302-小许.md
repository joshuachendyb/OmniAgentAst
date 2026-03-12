# opencode-plugin-openspec 研究报告

**创建时间**: 2026-03-02 23:40:49  
**分析人**: 小许（专家级需求分析师）  
**用户**: 北京老陈  
**来源**: https://github.com/Octane0411/opencode-plugin-openspec

---

## 一、项目概述

### 1.1 项目定位

**opencode-plugin-openspec** 是一个集成 **OpenSpec** 的 OpenCode 插件，提供专门的 **OpenSpec Architect** 代理模式，用于创建和编辑规范文件。

**核心理念**：为 OpenCode 提供专门的规划模式，解决规划阶段与实现阶段混淆的问题。

**项目统计**：
- ⭐ **Stars**: 30
- 🔀 **Forks**: 1
- 💻 **Languages**: TypeScript (100%)
- 📦 **License**: MIT
- 📦 **最新版本**: v0.1.2

---

## 二、解决的问题

### 2.1 问题背景

**问题描述**：使用 OpenCode 的标准"Build mode"创建或修改 OpenSpec 规划文档时，AI 代理通常会在规划阶段完成之前就开始实施代码修改，导致：

1. **过早编码**：规划尚未完成就开始写代码
2. **缺乏架构重点**：焦点过早从架构设计转移到实现
3. **设计与实现混淆**：规划阶段和实现阶段界限不清

### 2.2 解决方案

**opencode-plugin-openspec** 引入专门的 **OpenSpec Architect** 代理模式，配置为：

- ✅ **允许创建和编辑** OpenSpec 文档（如：`project.md`, `specs/**`）
- ✅ **防止修改**实现代码
- ✅ **完全专注**于规划和规范，确保设计与实现清晰分离

---

## 三、主要功能

### 3.1 自动检测

**功能描述**：自动检测当前工作区是否为 OpenSpec 项目。

**检测逻辑**：
- 识别 OpenSpec 项目结构的特征文件
- 根据检测结果启用相应功能

### 3.2 专用代理模式

**功能描述**：提供 **OpenSpec Architect** 代理模式，专门用于创建和编辑 OpenSpec 文件。

**代理特点**：
- 仅能修改规范文件
- 不能修改实现代码
- 专注于规划和规范

### 3.3 智能权限管理

**功能描述**：自动授予特定文件的写权限。

**授权的文件**：
- `project.md`
- `AGENTS.md`
- `openspec/**`
- `specs/**`

**只读安全**：
- 使用 `openspec-plan` 代理模式时，代码库其余部分保持只读
- 确保规划阶段不会意外修改实现代码

---

## 四、安装方法

### 4.1 为人类安装

**选项1：让代理执行（推荐）**

复制并粘贴此提示到你的 LLM 代理（Claude Code、AmpCode、Cursor 等）：
```
Install opencode-plugin-openspec by following the instructions here:
https://raw.githubusercontent.com/Octane0411/opencode-plugin-openspec/main/README.md
```

**选项2：手动安装**

将插件包名添加到你的 `opencode.json` 配置文件（通常位于 `~/.config/opencode/opencode.json` 或 `.opencode/opencode.json`）：

```jsonc
{
  "plugin": [
    "opencode-plugin-openspec"
  ]
}
```

OpenCode 会在下次运行时自动下载并安装插件。

### 4.2 为 LLM Agent 安装

如果你是负责设置此插件的 AI 代理，请遵循以下步骤：

**重要**：不要运行 `npm install` 或任何终端命令。你只需要编辑配置文件。

**步骤1：定位配置**
- 找到用户的 OpenCode 配置文件
- 通常位于 `~/.config/opencode/opencode.json` 或工作区根目录的 `.opencode/opencode.json`

**步骤2：读取配置**
- 读取配置文件内容

**步骤3：更新配置**
- 将 `"opencode-plugin-openspec"` 添加到 `plugin` 数组
- 如果 `plugin` 数组不存在，则创建它
    ```jsonc
    {
      "plugin": [
        "opencode-plugin-openspec"
      ]
    }
    ```

**步骤4：验证**
- 通知用户插件已添加
- 提示及插件将在下次 OpenCode 运行时安装

**注意**：你不需要运行 `npm install` 或手动下载包。OpenCode 会根据配置自动获取插件。

---

## 五、使用方法

### 5.1 基本使用流程

1. **在 OpenCode 中打开 OpenSpec 项目**
   - 插件会自动检测项目结构
   - 识别为 OpenSpec 项目后启用相应功能

2. **切换到 OpenSpec Architect 代理模式**
   - 在代理选择器中选择 **OpenSpec Architect**（颜色：#FF6B6B）
   - 此模式专门用于规划和规范

3. **开始规划你的架构**
   - 代理可以修改规范文件
   - 代理不能修改实现代码
   - 确保设计与实现清晰分离

### 5.2 权限说明

**OpenSpec Architect 代理模式的权限**：

| 操作 | 权限 | 说明 |
|------|--------|------|
| 创建/编辑规范文件 | ✅ 允许 | `project.md`, `AGENTS.md`, `openspec/**`, `specs/**` |
| 读取实现代码 | ✅ 允许 | 需要理解现有代码来规划 |
| 修改实现代码 | ❌ 禁止 | 防止规划阶段过早编码 |
| 创建新实现文件 | ❌ 禁止 | 保持专注在规划阶段 |

---

## 六、开发方法

### 6.1 克隆仓库

```bash
git clone https://github.com/Octane0411/opencode-plugin-openspec.git
cd opencode-plugin-openspec
```

### 6.2 安装依赖

```bash
bun install

```

### 6.3 构建插件

```bash
bun run build
```

### 6.4 运行监听模式

```bash
bun run watch
```

---

## 七、技术架构

### 7.1 插件结构

**主要组件**：
- 自动检测模块：识别 OpenSpec 项目结构
- 代理模式切换：提供 OpenSpec Architect 模式
- 权限管理系统：控制文件读写权限
- 配置管理：管理授权的文件列表

### 7.2 技术栈

| 技术 | 用途 |
|------|------|
| TypeScript | 主要开发语言 |
| Bun | 包管理器和运行时 |
| OpenCode Plugin API | 与 OpenCode 集成 |
| 文件权限系统 | 控制文件访问 |

---

## 八、适用场景

### 8.1 推荐使用场景

- ✅ **OpenSpec 项目规划**：使用专门的规划模式创建架构文档
- ✅ **规范文档编辑**：修改 `specs/` 下的规范文件
- ✅ **架构设计阶段**：专注于设计而非实现
- ✅ **多人协作**：确保规划阶段和实现阶段清晰分离

### 8.2 不推荐使用场景

- ❌ **实现阶段**：应该使用标准 OpenCode 模式
- ❌ **代码重构**：需要完全的代码访问权限
- ❌ **快速修复**：标准模式更合适

---

## 九、与 superpowers 对比

| 特性 | opencode-plugin-openspec | superpowers |
|--------|---------------------|------------|
| 主要功能 | OpenSpec 规划模式 | 技能系统 |
| 权限控制 | 限制修改实现代码 | 无限制 |
| 代理模式 | OpenSpec Architect | 多个技能 |
| 目标场景 | OpenSpec 项目 | 通用开发 |
| 安装复杂度 | 简单 | 需要符号链接 |

---

## 十、总结与建议

### 10.1 核心价值

1. **规划与实现分离**：确保架构设计阶段不会被实现代码干扰
2. **专用代理模式**：提供专门用于规划的代理配置
3. **智能权限管理**：自动管理文件读写权限
4. **防止过早编码**：限制在规划阶段修改实现代码
5. **专注架构设计**：让 AI 代理专注于规划和规范

### 10.2 安装建议

1. **推荐方法**：让 AI 代理自动安装
2. **手动方法**：编辑 `opencode.json` 配置文件
3. **验证安装**：下次运行 OpenCode 时自动安装
4. **权限问题**：确保 OpenCode 有写入权限

### 10.3 使用建议

1. **OpenSpec 项目**：强烈推荐使用此插件
2. **普通项目**：可选，根据需要启用
3. **切换时机**：规划阶段使用 OpenSpec Architect，实现阶段使用标准模式
4. **团队协作**：确保团队成员了解插件的作用和使用方法

---

**报告完成时间**: 2026-03-02 23:40:49  
**分析人**: 小许（专家级需求分析师）  
**用户**: 北京老陈  
**建议**: 
1. OpenSpec 项目强烈推荐安装此插件
2. 安装后切换到 OpenSpec Architect 代理模式
3. 确保规划阶段和实现阶段清晰分离
